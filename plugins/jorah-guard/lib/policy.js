// jorah-guard v0's decision for one tool call (docs/plan/p5-plan.md 4.1 to 4.3). Pure: it reads
// the session view it is given and returns what to do, plus what to record. The caller applies
// it. Everything not explicitly allowed is blocked; anything the guard can't tell is treated as
// "this chat has read outside text".

import { realpathSync } from "node:fs";
import { posix } from "node:path";
import { forbidden, linkHygiene, normalise, onSiteAllowlist, urlCores, urlsIn, writtenTokens } from "./urls.js";
import { siteDecision } from "./sites.js";
import { isWrapper, unwrap } from "./wrapper.js";

const CARD_MAX = 500;
export const VOICE_CARD_HINT = "Say 'yes, go ahead' or tap here.";

// What a consult agent (matrix.consultAgents) may do: read, search, fetch. Nothing that writes,
// runs a command, reads other chats or starts work.
const CONSULT_CLASSES = new Set(["read", "search", "url"]);
const CONSULT_TOOLS = ["web_search", "x_search", "web_fetch", "browser", "price_compare", "tool_search", "tool_describe", "view_image"];
export const isConsultAgent = (matrix, agentId) => (matrix?.consultAgents ?? []).includes(String(agentId ?? "").toLowerCase());
// An extension of main (matrix.extensionAgents; Adam, 2026-11-25: "deep should act as an extension
// of main, so I want it to be able to access the same files and have the same permissions"). It
// gets main's rules for its own actions, and its session is as clean as the chat that started it:
// clean only when index.js saw the spawn come from Adam's own clean chat (State.markCleanChild),
// otherwise it counts as a chat that has read outside text. Main asks it without a card.
export const isExtensionAgent = (matrix, agentId) => (matrix?.extensionAgents ?? []).includes(String(agentId ?? "").toLowerCase());
// Main asks these without a card, and their finds go up to the chat that asked (issue #13).
export const isHelperAgent = (matrix, agentId) => isConsultAgent(matrix, agentId) || isExtensionAgent(matrix, agentId);
const actsAsMain = (matrix, agent) => agent === "main" || isExtensionAgent(matrix, agent);

export function classify(matrix, tool) {
  for (const cls of ["read", "taintRead", "viewRead", "search", "url", "fileWrite", "memoryWrite", "skill", "schedule", "spawn",
    "github", "message", "sandboxShell", "blocked", "proactiveSend", "localWrite", "confirmAlways", "cronOnly"]) {
    if ((matrix[cls] ?? []).includes(tool)) return cls;
  }
  return null;
}

// Who is asking, from the hook's context (G-S1, 2026-11-11; P5.4, 2026-11-13; 2026-11-22).
// Chat Completions callers arrive as "webchat", or as whatever x-openclaw-message-channel says, but
// never with a sender id. So Adam's own typing is Telegram *with* a sender id, or the CLI on the PC
// (no channel, no sender id, which a Chat Completions caller can't produce). OpenClaw 2026.10.9
// refuses plugin approval cards from the "voice" surface, so jorah-voice (the HUD's voice too)
// and jorah-phone send x-openclaw-message-channel: "webchat" and start the prompt with
// "[Spoken turn.". index.js recognises that marker in before_agent_run and passes run.voice = true
// so cards get voice wording ("Asked by voice", VOICE_CARD_HINT); the "voice" channel still counts
// as voice for old clients. "webchat" without the marker is typing in the Mac HUD or Control UI:
// it gets the exact same checks as voice, only the card says it was typed (so typing "[Spoken turn."
// by hand only changes wording). Any other channel is treated as not Adam's own chat.
export function typedByOwner(r) {
  if (r?.senderIsOwner !== true) return false;
  if (r.channel === "telegram") return typeof r.senderId === "string" && r.senderId.length > 0;
  return r.channel === undefined && r.senderId === undefined;
}

export function speaker(ctx = {}, settings = {}, run = {}) {
  const r = ctx.requester ?? null;
  const webchatRaw = r?.channel === "webchat";
  const voice = r?.channel === "voice" || (webchatRaw && run?.voice === true);
  const webchat = webchatRaw && !voice;
  const owner = r?.senderIsOwner === true;
  const typed = typedByOwner(r);
  const cleanKeys = settings.cleanSessionKeys ?? ["agent:main:main"];
  const cleanEligible = typed && cleanKeys.includes(ctx.sessionKey) && (ctx.agentId ?? "main") === "main";
  return { voice, webchat, owner, cleanEligible, typedByOwner: typed };
}

// Proactive runs (docs/runbooks/proactive.md, spike of 2026-11-15 on OpenClaw 2026.10.9 source):
// before_agent_run's context carries the run's trigger ("user", "heartbeat", "cron", "event", ...)
// and runId, but before_tool_call's carries only runId, so index.js remembers the trigger per run
// and hands it in as run.trigger. Isolated cron runs use agent:<id>:cron:<jobId> and webhook turns
// agent:<id>:hook:..., but a heartbeat runs in agent:main:main like Adam's own chat, so only the
// trigger tells them apart. A main-agent run with no requester and no recorded trigger can't be
// shown to be Adam's, so it counts as proactive too. Children of a proactive session inherit it.
const sessionRest = (key) => {
  const k = String(key ?? "");
  const m = /^agent:[^:]+:(.*)$/.exec(k);
  return m ? m[1] : k;
};

export function proactiveRun({ ctx = {}, run = {}, matrix = {}, parentOf = () => null }) {
  const p = matrix.proactive ?? {};
  const triggers = p.triggers ?? ["cron", "heartbeat"];
  const kinds = p.sessionKinds ?? ["cron", "hook", "proactive"];
  const keyed = (key) => kinds.some((kind) => sessionRest(key).startsWith(`${kind}:`));
  if (run.trigger && triggers.includes(run.trigger)) return { proactive: true, why: `a ${run.trigger} run` };
  if (keyed(ctx.sessionKey)) return { proactive: true, why: `a ${sessionRest(ctx.sessionKey).split(":")[0]} session` };
  let parent = parentOf(ctx.sessionKey);
  for (let i = 0; parent && i < 10; i++, parent = parentOf(parent)) {
    if (keyed(parent)) return { proactive: true, why: `started from ${sessionRest(parent).split(":")[0]} session` };
  }
  if ((ctx.agentId ?? "main") === "main" && !ctx.requester && !run.trigger) return { proactive: true, why: "a run with no requester and no known trigger" };
  return { proactive: false };
}

// viewRead (review fix 6, 2026-11-22): a tool whose call says, in its `view` argument, whether
// its result may carry text a run, a tool or a web page wrote. Whether a chat is marked has to be
// decided here, before the tool runs: after_tool_call is observation only (handlers run
// concurrently, a failed one is skipped, `result` is optional; OpenClaw docs
// plugins/hooks/tool-policy.md), so a taint set from the result could come after the model has
// read it, or never. So the call itself chooses: no arguments, or exactly { view: "installed" },
// is a read, and the plugin promises that view holds only fields matching its own strict shapes;
// any other argument, or any other value, is a taintRead. viewBackstop below then checks the
// result as a second line, and only ever adds a mark.
export function cleanView(params) {
  const p = params && typeof params === "object" ? params : {};
  const keys = Object.keys(p);
  return keys.every((k) => k === "view") && (p.view === undefined || p.view === "installed");
}

// After a clean-view call: if the result isn't the plugin's clean view (an older plugin that
// ignores `view`, an error, no result), mark the chat anyway. Never removes a mark.
export function viewBackstop({ tool, params, result, error, matrix }) {
  if (classify(matrix, tool) !== "viewRead" || !cleanView(params)) return null;
  const d = result?.details;
  if (error == null && d && typeof d === "object" && (d.view === "installed" || (d.status === "unavailable" && Object.keys(d).length <= 2))) return null;
  return `${tool} (its result wasn't the clean view)`;
}

const isCronSession = (key) => sessionRest(key).startsWith("cron:");

const WEBCHAT = "typed in the HUD or the web chat";

// Session state as the policy needs it.
export function sessionState(view, ctx, settings, run = {}, matrix = {}) {
  const who = speaker(ctx, settings, run);
  const recorded = view.taintOf(ctx.sessionKey);
  let source = null;
  if (recorded?.tainted) source = recorded.source;
  else if (isExtensionAgent(matrix, ctx.agentId)) {
    if (!view.cleanChild?.(ctx.sessionKey)) source = `not started from Adam's own clean chat (${ctx.sessionKey ?? "no session key"})`;
  }
  else if (who.voice) source = "asked by voice";
  else if (who.webchat) source = WEBCHAT;
  else if (!who.cleanEligible) source = ctx.sessionKey ? `not Adam's own chat (${ctx.sessionKey})` : "no session key";
  return { ...who, tainted: source !== null, source };
}

const WORD_RE = /[\p{L}\p{N}]{3,}/gu;
const STOP = new Set(["the", "and", "that", "this", "with", "for", "you", "are", "was", "his", "her", "its", "from",
  "have", "has", "not", "but", "all", "any", "can", "will", "remember", "adam", "adam's", "save", "note"]);

// Does the text to be saved come from Adam's own message? At least 80% of its words must be in
// his words, and it may not be much longer than them (p5-plan 4.2, D2).
const ASKED = /\b(remember|save|note (this|that|down)|write (this|that) down|keep in mind|don't forget|zapam[aä]taj|ulo[zž])/i;

export function coveredByWords(content, words) {
  if (!ASKED.test(String(words ?? ""))) return false;
  const c = String(content ?? "").toLowerCase().match(WORD_RE)?.filter((w) => !STOP.has(w)) ?? [];
  if (c.length === 0) return false;
  const w = new Set(String(words ?? "").toLowerCase().match(WORD_RE) ?? []);
  if (w.size === 0) return false;
  const hit = c.filter((x) => w.has(x)).length;
  return hit / c.length >= 0.8 && String(content).length <= 3 * String(words).length + 40;
}

function textOf(value) {
  if (typeof value === "string") return value;
  try { return JSON.stringify(value ?? ""); } catch { return ""; }
}

function short(text, n) {
  const t = String(text ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

function card(title, lines, { voice = false, severity = "warning" } = {}) {
  const all = voice ? [VOICE_CARD_HINT, ...lines] : lines;
  let description = all.filter(Boolean).join("\n");
  if (description.length > CARD_MAX) description = `${description.slice(0, CARD_MAX - 1)}…`;
  return { verdict: "confirm", title: short(title, 78), description, severity };
}

export function cardSeverity(cls, params = {}) {
  if (cls === "github" || cls === "message") return "critical";
  if (cls === "schedule") {
    const job = params?.job ?? params;
    const prompt = textOf(job?.message ?? job?.prompt ?? job?.task ?? job?.payload ?? job);
    const fetches = urlsIn(job).length > 0 || /\b(fetch|browse|web|search|http)/i.test(prompt);
    return (!isOneOff(params) || fetches) ? "critical" : "warning";
  }
  return "warning";
}

const cardTitle = (matrix, tool) => matrix.cardTitles?.[tool] ?? `Jorah wants to use ${tool}`;

// The exact arguments, one line each, in a fixed order: what Adam approves is what runs.
function paramLines(params = {}) {
  return Object.keys(params).sort().map((k) => `${short(k, 20)}: ${short(textOf(params[k]), 160)}`);
}

const why = (s) => (s.voice ? "Asked by voice: confirm only if this was you."
  : s.source === WEBCHAT ? "Typed in the HUD or the web chat, not Telegram: confirm only if this was you."
    : `This chat has read outside text (${short(s.source, 80)}).`);

// Paths an edit or patch touches, relative to the workspace when possible.
export function targetPaths(tool, params = {}, derived, workspace) {
  const out = new Set();
  for (const k of ["path", "file_path", "filePath", "file", "target"]) if (typeof params[k] === "string") out.add(params[k]);
  if (Array.isArray(derived)) for (const p of derived) if (typeof p === "string") out.add(p);
  if (tool === "apply_patch") {
    const text = textOf(params.patch ?? params.input ?? params);
    for (const m of text.matchAll(/\*\*\* (?:Add|Update|Delete) File: ([^\n\\"]+)/g)) out.add(m[1].trim());
    for (const m of text.matchAll(/\*\*\* Move to: ([^\n\\"]+)/g)) out.add(m[1].trim());
  }
  return [...out].map((p) => {
    let rel = p.replace(/^~\//, "/home/jorah/");
    if (workspace && rel.startsWith(`${workspace}/`)) rel = rel.slice(workspace.length + 1);
    return posix.normalize(rel.replace(/^\.\//, "")).replace(/^(\.\.\/)+/, "../");
  });
}

function fileKind(rel, matrix) {
  const match = (list) => (list ?? []).some((f) => (f.endsWith("/") ? rel.startsWith(f) || rel.includes(`/${f}`) : rel === f || rel.endsWith(`/${f}`)));
  if (match(matrix.rulesFiles)) return "rules";
  if (match(matrix.memoryFiles)) return "memory";
  return "other";
}

// The text an edit would add: new text of edits, the content of a write, the + lines of a patch.
export function addedText(tool, params = {}) {
  if (tool === "edit") {
    const edits = Array.isArray(params.edits) ? params.edits : [params];
    return edits.map((e) => e?.newText ?? e?.new_string ?? e?.newString ?? e?.replacement ?? "").join("\n");
  }
  if (tool === "write") return textOf(params.content ?? params.text ?? "");
  if (tool === "apply_patch") {
    return textOf(params.patch ?? params.input ?? "").split("\n").filter((l) => l.startsWith("+") && !l.startsWith("+++")).map((l) => l.slice(1)).join("\n");
  }
  return textOf(params.content ?? params.text ?? params.body ?? params.lesson ?? params.instructions ?? params);
}

function isOneOff(params) {
  const job = params?.job ?? params;
  const kind = job?.schedule?.kind ?? job?.kind;
  return kind === "at" || kind === "once" || typeof job?.at === "string" || typeof job?.runAt === "string";
}

// Check every URL in a value: never a local or private address; in a session that has read
// outside text, only URLs seen before or on Adam's site list.
// URL-like parameters without a scheme ("attacker.example/x") are checked as https URLs.
export function urlParams(value) {
  const out = [];
  if (value && typeof value === "object") {
    for (const k of ["url", "targetUrl", "href", "uri", "link"]) {
      const v = value[k];
      if (typeof v === "string" && v.trim() && !/^[a-z][a-z0-9+.-]*:/i.test(v.trim())) out.push(`https://${v.trim().replace(/^\/+/, "")}`);
    }
    for (const v of Object.values(value)) if (v && typeof v === "object") out.push(...urlParams(v));
  }
  return out;
}

// A fetch never sends the fragment, so web_fetch compares without it; the browser and anything
// else compare with it, because a page's own script can read it. Links Adam typed skip the
// hygiene rule (he chose them); everything else in a chat with outside text must pass it.
export function checkUrls(value, state, view, sessionKey, matrix, tool = "") {
  for (const raw of [...urlsIn(value), ...urlParams(value)]) {
    const bad = forbidden(raw);
    if (bad) return `${short(raw, 60)}: ${bad}`;
    if (!state.tainted) continue;
    const n = normalise(raw, { keepHash: tool !== "web_fetch" });
    if (!n) return `${short(raw, 60)}: not a valid URL`;
    const seen = view.hasSeen(sessionKey, n);
    if (!view.typedSeen?.(sessionKey, n)) {
      // A link an outside reader returned (and the model didn't write, resultSeeds) may be longer:
      // search-result shop links carry query parameters (issue #15). The credential checks stay.
      const maxChars = seen ? (matrix.urlSeenMaxChars ?? 1000) : (matrix.urlMaxChars ?? 250);
      const dirty = linkHygiene(raw, { maxChars, credentialParams: matrix.urlCredentialParams });
      if (dirty) return `${short(raw, 60)}: ${dirty}, and this chat has read outside text`;
    }
    if (seen || onSiteAllowlist(n, matrix.siteAllowlist)) continue;
    return `${short(raw, 60)} wasn't in your message or an earlier result, and this chat has read outside text`;
  }
  return null;
}

// Which tools' results may add seen URLs (G-S2, narrowed 2026-11-19 after the laundering
// finding): only outside readers named in the matrix's urlSources, through the search wrapper
// too. read, write, memory, sessions, exec, cards and unknown tools never do, because the model
// can put any text there. Even from an outside reader, a URL contained in the model's own words
// (this call's arguments, or anything it wrote in this chat after outside text, see
// state.wrote) is not seen: tools and pages echo what they are sent.
export function seedTool(matrix, tool, params = {}) {
  let name = tool;
  if (isWrapper(tool)) {
    const w = unwrap(params);
    if (w.malformed) return null;
    name = w.inner;
  }
  return (matrix?.urlSources ?? []).includes(name) ? name : null;
}

export function resultSeeds({ tool, params = {}, result, matrix, wrote = () => false }) {
  if (!seedTool(matrix, tool, params)) return [];
  const own = writtenTokens(params);
  const out = [];
  for (const raw of urlsIn(result)) {
    const n = normalise(raw, { keepHash: true });
    if (!n) continue;
    const cores = [...urlCores(raw), ...urlCores(n)];
    if (own.some((t) => cores.some((c) => t.includes(c)))) continue;
    if (wrote(cores)) continue;
    out.push(raw);
  }
  return out;
}

/**
 * @returns {{ verdict: "allow"|"block"|"confirm", reason?: string, title?: string, description?: string,
 *             taint?: string, readRepo?: string }}
 */
export const MAX_IMAGES_PER_CALL = 5;

// The pictures a view_image call names: its `path` and the distinct strings in `paths`, as
// OpenClaw's image tool reads them (2026.11.6, src/agents/tools/image-tool.ts).
export function imagePaths(params) {
  const all = [
    ...(typeof params?.path === "string" ? [params.path] : []),
    ...(Array.isArray(params?.paths) ? params.paths.filter((p) => typeof p === "string") : []),
  ];
  return [...new Set(all.map((p) => p.trim()).filter(Boolean))];
}
export const imageCount = (params) => imagePaths(params).length;

const hasScheme = (p) => /^[a-z][a-z0-9+.-]*:/i.test(p);

// Where Adam's pictures are (2026-11-25): OpenClaw's attachment store, the workspace's copy of
// it, and the pictures Jorah kept (picture_save). matrix.consultPictureRoots overrides it.
const CONSULT_PICTURE_ROOTS = ["/home/jorah/.openclaw-jorah/media/inbound", "/home/jorah/workspace/media/inbound", "/home/jorah/workspace/files/pictures"];
const PICTURE_EXT = /\.(jpe?g|png|webp|gif|heic|heif)$/i;

// A consult agent's view_image (Adam's yes, 2026-11-25, so deep can study the photos he sends):
// local picture files in those folders, by absolute path, never a URL. deep reads the web, so a
// page could ask it to fetch an address with Adam's data in it, or to open another file on the PC.
export function consultPictureProblem(paths, roots = CONSULT_PICTURE_ROOTS) {
  for (const p of paths) {
    if (hasScheme(p)) return `${short(p, 60)}: deep looks only at picture files on the PC, never a web address`;
    const n = posix.normalize(p);
    if (!p.startsWith("/") || p.includes("\0") || n !== p.replace(/\/+$/, "")) return `${short(p, 60)}: not a plain absolute path`;
    if (!roots.some((r) => n.startsWith(`${r.replace(/\/+$/, "")}/`))) return `${short(p, 60)}: deep looks only at the pictures Adam sent (${roots.join(", ")})`;
    if (!PICTURE_EXT.test(n)) return `${short(p, 60)}: not a picture file (jpg, png, webp, gif, heic)`;
    // A link inside those folders mustn't lead out of them. A file that isn't there fails in the tool.
    const real = realOrNull(n);
    if (real && !roots.some((r) => real.startsWith(`${realOrNull(r) ?? r}/`))) return `${short(p, 60)}: leads out of Adam's picture folders`;
  }
  return null;
}
function realOrNull(p) {
  try { return realpathSync(p); } catch { return null; }
}

export function decide({ tool, params = {}, ctx = {}, derivedPaths, matrix, view, settings = {}, run = {} }) {
  if (!matrix || typeof matrix !== "object") return { verdict: "block", reason: "permission matrix unreadable" };
  if (typeof tool !== "string" || tool.length === 0) return { verdict: "block", reason: "no tool name" };

  // Site readers (lib/sites.js) come first: the reader agent gets only its own rules, and no one
  // else may reach for a signed-in site browser. A missing site list means no site is set up.
  const site = siteDecision({ tool, params, agent: ctx.agentId, sessionKey: ctx.sessionKey, sites: settings.sites?.() ?? new Map() });
  if (site) {
    if (site.verdict === "allow" && view.frozen()) return { verdict: "block", reason: "Jorah is frozen (/jorah-freeze). Adam clears it at a terminal." };
    return site;
  }

  // The search wrapper (tool_call in 10.9, dispatch_action in 10.33, lib/wrapper.js): decide on the
  // inner call now only to block early; the hook runs again on the inner tool with its real name
  // (G-S2), where cards and taint are handled. Never a card here. A wrapper call the guard can't
  // read is blocked (until 2026-11-20 a tool_call naming no tool was let through to fail in OpenClaw).
  if (isWrapper(tool)) {
    const w = unwrap(params);
    if (w.malformed) return { verdict: "block", reason: w.malformed };
    const d = decide({ tool: w.inner, params: w.args, ctx, matrix, view, settings, run });
    return d.verdict === "block" ? d : { verdict: "allow", reason: `wrapper for ${w.inner}` };
  }

  // Pictures per view_image call (2026-11-25): claude-cli hands each result to the Gateway as one
  // JSON line of at most 8 MB, and 14 pictures broke that, failing the whole turn. Five fit.
  if (tool === "view_image") {
    const n = imageCount(params);
    if (n > MAX_IMAGES_PER_CALL) {
      return { verdict: "block", reason: `view_image takes at most ${MAX_IMAGES_PER_CALL} pictures a call and this one has ${n}. Look at them in batches of ${MAX_IMAGES_PER_CALL} or fewer, note what each shows, then go on with the next batch.` };
    }
  }

  const named = classify(matrix, tool);
  const cls = named === "viewRead" ? (cleanView(params) ? "read" : "taintRead") : named;
  const state = sessionState(view, ctx, settings, run, matrix);
  const key = ctx.sessionKey;
  const agent = ctx.agentId ?? "unknown";
  const action = typeof params.action === "string" ? params.action : "";
  const readAction = (matrix.readActions ?? []).includes(action);

  if (view.frozen() && cls !== "read") return { verdict: "block", reason: "Jorah is frozen (/jorah-freeze). Adam clears it at a terminal." };

  // A consult agent (`deep`) only thinks, reads and searches the web. That is what lets main ask it
  // without a card (case "spawn"). The config takes its shell, writes and sessions tools away
  // (config/pc/deep-consult.patch.json5); this holds even if the config drifts.
  if (isConsultAgent(matrix, agent) && !CONSULT_CLASSES.has(cls)) {
    return { verdict: "block", reason: `${agent} only thinks, reads and searches the web; ${tool} is main's or background's job` };
  }
  // Only the listed tools, whatever their class (2026-11-22): on the Max lane deep runs outside the
  // sandbox (claude-cli can't honour it), so the sandbox's tool list no longer narrows it. A "read"
  // such as memory_get, supply_list or read would let a page's instructions pull Adam's data into
  // a search query. On the Max lane the config says the same (config/pc/max-lane.patch.json5, tools.allow).
  if (isConsultAgent(matrix, agent) && !(matrix.consultTools ?? CONSULT_TOOLS).includes(tool)) {
    return { verdict: "block", reason: `${agent} uses only ${(matrix.consultTools ?? CONSULT_TOOLS).join(", ")}; ${tool} isn't one` };
  }
  if (tool === "view_image") {
    const pics = imagePaths(params);
    if (isConsultAgent(matrix, agent)) {
      const bad = consultPictureProblem(pics, matrix.consultPictureRoots ?? CONSULT_PICTURE_ROOTS);
      if (bad) return { verdict: "block", reason: `Not opened: ${bad}.` };
    } else {
      // A picture from the web is fetched like a page: the same URL rule as web_fetch, and its
      // content is outside text.
      const urls = pics.filter(hasScheme);
      if (urls.length) {
        const bad = checkUrls({ paths: urls }, state, view, key, matrix, tool);
        if (bad) return { verdict: "block", reason: `Not opened: ${bad}.` };
        return { verdict: "allow", taint: `view_image ${short(urls[0], 60)}` };
      }
    }
  }
  // A consult agent's browser only reads (issue #15: shops that render prices with JavaScript):
  // open, navigate, snapshot, text and screenshot in Jorah's own headless profile. No clicking,
  // typing, page settings or network log, no signed-in or host profile, no dashboards.
  if (isConsultAgent(matrix, agent) && tool === "browser") {
    const act = textOf(params.action ?? params.request?.action ?? "");
    const allowed = matrix.consultBrowserActions ?? ["status", "start", "tabs", "open", "focus", "close", "navigate", "snapshot", "text", "screenshot"];
    if (!allowed.includes(act)) return { verdict: "block", reason: `${agent}'s browser only reads pages (open, navigate, snapshot, text, screenshot); "${short(act, 20)}" isn't one` };
    if (params.profile !== undefined && params.profile !== (matrix.consultBrowserProfile ?? "openclaw")) return { verdict: "block", reason: `${agent} may use only Jorah's own browser profile` };
    if ((params.target !== undefined && params.target !== "sandbox") || params.node !== undefined || params.dashboard !== undefined) return { verdict: "block", reason: `${agent}'s browser takes no target, node or dashboard: it uses Jorah's own headless profile` };
  }

  const cardOpts = { voice: state.voice, severity: cardSeverity(cls, params) };

  switch (cls) {
    case "read":
      return { verdict: "allow" };

    case "taintRead": {
      const repo = params.repo ?? params.project;
      const full = named === "viewRead" ? ` (view: ${short(textOf(params.view ?? "?"), 20)})` : "";
      return { verdict: "allow", taint: `${tool}${full}${repo ? ` ${short(repo, 40)}` : ""}`, readRepo: typeof repo === "string" ? repo : undefined };
    }

    case "search": {
      const q = textOf(params.query ?? params.q ?? "");
      if (state.tainted && q.length > (matrix.searchQueryMaxChars ?? 200)) return { verdict: "block", reason: "search query too long for a chat that has read outside text" };
      return { verdict: "allow", taint: `${tool} results` };
    }

    case "url": {
      const bad = checkUrls(params, state, view, key, matrix, tool);
      if (bad) return { verdict: "block", reason: `Not opened: ${bad}.` };
      const evalish = /evaluate|wait.*fn|\bfn\b|expression/i.test(textOf(params.kind ?? params.request?.kind ?? "")) || "fn" in params || "expression" in params;
      if (evalish) return { verdict: "block", reason: "page JavaScript is off for Jorah's browser" };
      const kind = textOf(params.request?.kind ?? params.kind ?? params.action ?? "");
      if (tool === "browser" && state.tainted && /\b(type|fill|press|select|upload|drag|keyboard)\b/i.test(kind)) {
        const typed = params.request?.text ?? params.text ?? params.value ?? params.values ?? params.request ?? "";
        return card("Jorah wants to type into a web page", [why(state), `Action: ${short(kind, 30)}`, `Text: ${short(textOf(typed), 300)}`], cardOpts);
      }
      const host = urlsIn(params).map((u) => { try { return new URL(u).hostname; } catch { return "?"; } })[0];
      return { verdict: "allow", taint: `${tool}${host ? ` ${host}` : ""}` };
    }

    case "fileWrite": {
      if (!actsAsMain(matrix, agent)) return { verdict: "allow" }; // other agents write only inside their sandbox
      const paths = targetPaths(tool, params, derivedPaths, settings.workspace);
      const kinds = paths.map((p) => fileKind(p, matrix));
      if (paths.length === 0) {
        return state.tainted ? card("Jorah wants to change a file", [why(state), `${tool} with no clear target.`], cardOpts) : { verdict: "allow" };
      }
      if (!state.tainted) return { verdict: "allow" };
      const added = addedText(tool, params);
      if (kinds.includes("rules")) {
        return card("Jorah wants to change its own rules", [why(state), `Files: ${short(paths.join(", "), 120)}`, `Adds: ${short(added, 300)}`], cardOpts);
      }
      if (kinds.includes("memory")) {
        if (state.typedByOwner && coveredByWords(added, view.wordsOf(key))) return { verdict: "allow", reason: "Adam's own words" };
        return card("Jorah wants to save to memory", [why(state), `File: ${short(paths.join(", "), 80)}`, `Text: ${short(added, 320)}`], cardOpts);
      }
      return { verdict: "allow" };
    }

    case "memoryWrite": {
      if (!state.tainted || readAction) return { verdict: "allow" };
      const added = addedText(tool, params);
      if (state.typedByOwner && coveredByWords(added, view.wordsOf(key))) return { verdict: "allow", reason: "Adam's own words" };
      return card("Jorah wants to save to memory", [why(state), `Tool: ${tool}`, `Text: ${short(added, 320)}`], cardOpts);
    }

    case "skill": {
      if (readAction || action === "") return action === "" && state.tainted
        ? card("Jorah wants to change a skill", [why(state), `skill_workshop with no action.`], cardOpts) : { verdict: "allow" };
      if (!state.tainted) return { verdict: "allow" };
      return card("Jorah wants to change a learned skill", [why(state), `${action} ${short(params.name, 60)}`, `Content: ${short(addedText(tool, params), 300)}`], cardOpts);
    }

    case "schedule": {
      if (readAction) return { verdict: "allow" };
      const job = params.job ?? params;
      const prompt = textOf(job?.message ?? job?.prompt ?? job?.task ?? job?.payload ?? job);
      const fetches = urlsIn(job).length > 0 || /\b(fetch|browse|web|search|http)/i.test(prompt);
      if (!state.tainted && isOneOff(params) && !fetches) return { verdict: "allow" };
      const bad = checkUrls(job, state, view, key, matrix);
      if (bad) return { verdict: "block", reason: `Schedule refused: ${bad}.` };
      return card("Jorah wants to create or change a schedule", [state.tainted ? why(state) : "", `${tool} ${action}`, `Job: ${short(prompt, 330)}`], cardOpts);
    }

    case "spawn": {
      const bad = checkUrls(params.task ?? params.message ?? "", state, view, key, matrix);
      if (bad) return { verdict: "block", reason: `Brief refused: ${bad}.` };
      const acp = params.runtime === "acp";
      const who = acp ? `Claude Code in ${short(params.cwd ?? "?", 60)}` : `the ${short(params.agentId ?? "?", 20)} agent`;
      if (acp && (state.tainted || view.countAcp(key) > (matrix.acpSpawnsPerHourWithoutConfirm ?? 3))) {
        return { ...card("Jorah wants to start a coding job", [state.tainted ? why(state) : "More than 3 jobs this hour.", `Who: ${who}`, `Brief: ${short(params.task, 330)}`], cardOpts), taint: "worker result" };
      }
      // Asking `deep` (Opus) never needs a card (Adam, 2026-11-21: "it doesn't need to ask my
      // permission, just make it work"). It has no shell and no writes (above), so its only ways out
      // are web_search and web_fetch, which this guard checks in its session as in main's: a child
      // is never Adam's own chat. A brief can't send data anywhere main couldn't send it itself. The
      // brief's URLs are still checked, and the answer still marks this chat.
      // An extension agent (deep since 2026-11-25) may write and use main's tools, but its session is
      // only as clean as this chat was when it asked (index.js marks it), so after outside text its
      // writes and sends get the same cards main's would. Adam: "just make it so that the main agent
      // can elevate the issue to opus and he then tries to solve it".
      if (!acp && isHelperAgent(matrix, params.agentId)) return { verdict: "allow", taint: "worker result" };
      // background has a sandboxed shell with internet access, so a brief written after outside
      // text could carry data out past the URL rule. Show it to Adam first.
      if (!acp && state.tainted) return { ...card("Jorah wants to start a job", [why(state), `Who: ${who}`, `Brief: ${short(params.task, 330)}`], cardOpts), taint: "worker result" };
      return { verdict: "allow", taint: "worker result" };
    }

    case "github": {
      const project = String(params.project ?? "");
      if (state.tainted && (matrix.selfRepos ?? []).includes(project)) {
        return { verdict: "block", reason: "Jorah's own repo can't be pushed from a chat that has read outside text. Ask again in a new chat." };
      }
      const others = (view.readRepos(key) ?? []).filter((r) => r !== project && !r.endsWith(`/${project}`));
      if (state.tainted && others.length > 0) {
        return { verdict: "block", reason: `This chat also read ${short(others.join(", "), 60)}, so code can't be pushed to ${project} from it. Ask again in a new chat.` };
      }
      return { verdict: "allow" }; // jorah-github then asks Adam with its own card
    }

    case "message": {
      const pro = proactiveRun({ ctx, run, matrix, parentOf: (k) => view.parentOf?.(k) ?? null });
      if (pro.proactive && !readAction) {
        return { verdict: "block", reason: `this is ${pro.why}: scheduled and background runs tell Adam things only through ${matrix.proactive?.sendTool ?? "proactive_notify"}` };
      }
      const target = params.to ?? params.target ?? params.chatId ?? params.recipient;
      if (target === undefined) return { verdict: "allow" };
      return card("Jorah wants to send a message", [state.tainted ? why(state) : "", `To: ${short(target, 60)}`, `Text: ${short(params.text ?? params.message ?? params.content, 300)}`], cardOpts);
    }

    case "sandboxShell":
      return actsAsMain(matrix, agent) ? { verdict: "block", reason: `${agent} has no shell; background does shell work` } : { verdict: "allow" };

    case "blocked":
      return { verdict: "block", reason: `${tool} is not allowed` };

    // Proactive layer (docs/runbooks/proactive.md). proactive_notify decides in code and only
    // queues, so it is allowed even after outside text; frozen still blocks it (above).
    case "proactiveSend":
      return { verdict: "allow" };

    // The plugin's own small records (closing a loop): free in a clean chat, a card after outside text.
    case "localWrite":
      return state.tainted ? card(cardTitle(matrix, tool), [why(state), ...paramLines(params)], cardOpts) : { verdict: "allow" };

    // Always a card with the exact fields, whoever asks (a loop is saved only on Allow once).
    case "confirmAlways":
      return card(cardTitle(matrix, tool), [state.tainted ? why(state) : "", ...paramLines(params)], cardOpts);

    // The tick drains the outbox; outside its automation the lines would be lost.
    case "cronOnly":
      return isCronSession(key) ? { verdict: "allow" } : { verdict: "block", reason: `${tool} runs only in its automation` };

    default:
      return { verdict: "block", reason: `${tool} isn't in Jorah's permission list yet` };
  }
}
