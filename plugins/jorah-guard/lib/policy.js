// jorah-guard v0's decision for one tool call (docs/plan/p5-plan.md 4.1 to 4.3). Pure: it reads
// the session view it is given and returns what to do, plus what to record. The caller applies
// it. Everything not explicitly allowed is blocked; anything the guard can't tell is treated as
// "this chat has read outside text".

import { posix } from "node:path";
import { forbidden, linkHygiene, normalise, onSiteAllowlist, urlCores, urlsIn, writtenTokens } from "./urls.js";
import { siteDecision } from "./sites.js";
import { isWrapper, unwrap } from "./wrapper.js";

const CARD_MAX = 500;
export const VOICE_CARD_HINT = "Say 'yes, go ahead' or tap here.";

// What a consult agent (matrix.consultAgents) may do: read, search, fetch. Nothing that writes,
// runs a command, reads other chats or starts work.
const CONSULT_CLASSES = new Set(["read", "search", "url"]);
export const isConsultAgent = (matrix, agentId) => (matrix.consultAgents ?? []).includes(String(agentId ?? "").toLowerCase());

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
export function sessionState(view, ctx, settings, run = {}) {
  const who = speaker(ctx, settings, run);
  const recorded = view.taintOf(ctx.sessionKey);
  let source = null;
  if (recorded?.tainted) source = recorded.source;
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

  const named = classify(matrix, tool);
  const cls = named === "viewRead" ? (cleanView(params) ? "read" : "taintRead") : named;
  const state = sessionState(view, ctx, settings, run);
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
  // A consult agent's browser only reads (issue #15: shops that render prices with JavaScript):
  // open, navigate, snapshot, text and screenshot in Jorah's own headless profile. No clicking,
  // typing, page settings or network log, no signed-in or host profile, no dashboards.
  if (isConsultAgent(matrix, agent) && tool === "browser") {
    const act = textOf(params.action ?? params.request?.action ?? "");
    const allowed = matrix.consultBrowserActions ?? ["status", "start", "tabs", "open", "focus", "close", "navigate", "snapshot", "text", "screenshot"];
    if (!allowed.includes(act)) return { verdict: "block", reason: `${agent}'s browser only reads pages (open, navigate, snapshot, text, screenshot); "${short(act, 20)}" isn't one` };
    if (params.profile !== undefined && params.profile !== (matrix.consultBrowserProfile ?? "openclaw")) return { verdict: "block", reason: `${agent} may use only Jorah's own browser profile` };
    if ((params.target !== undefined && params.target !== "sandbox") || params.node !== undefined || params.dashboard !== undefined) return { verdict: "block", reason: `${agent}'s browser stays in its sandbox` };
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
      if (agent !== "main") return { verdict: "allow" }; // other agents write only inside their sandbox
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
      if (!acp && isConsultAgent(matrix, params.agentId)) return { verdict: "allow", taint: "worker result" };
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
      return agent === "main" ? { verdict: "block", reason: "main has no shell; background does shell work" } : { verdict: "allow" };

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
