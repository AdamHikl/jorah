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
    "github", "message", "sandboxShell", "blocked", "proactiveSend", "localWrite", "ownWordsWrite", "confirmAlways", "cronOnly"]) {
    if ((matrix[cls] ?? []).includes(tool)) return cls;
  }
  return null;
}

// Who is asking, from the hook's context (G-S1, 2026-11-11; P5.4, 2026-11-13; 2026-11-22;
// ADR 0011, 2026-11-26). Adam's own typing is Telegram *with* a sender id, the CLI on the PC (no
// channel, no sender id, which a Chat Completions caller can't produce), or, since Adam's decision
// of 2026-11-26 ("Same as Telegram"), the Mac HUD: a "webchat" turn OpenClaw marks as the owner's,
// sorted by index.js in before_agent_run as run.hud === "typed". That needs a run id the Gateway
// didn't give its HTTP APIs ("chatcmpl_", "resp_": jorah-voice and jorah-phone use Chat
// Completions), no "[Spoken turn." (their marker) and no "[Typed by Claude Code" (HUD drive mode's
// marker, ADR 0012) near the start, and the line as sent, which index.js takes from
// before_prompt_build: OpenClaw 2026.11.6 hands before_agent_run the line with other plugins'
// context before and after it, so a webchat run without that line is never typing. A run index.js
// never saw stays untrusted. Spoken webchat
// turns get voice checks and wording (run.voice or run.hud === "spoken"); drive turns keep every
// card; other webchat turns keep them too (WEBCHAT). Any other channel is not Adam's own chat.
// settings.hudTypingIsAdam === false turns the HUD rule off (cards for all webchat, as before).
// HUD typing counts only in the main agent's clean chat (settings.cleanSessionKeys, run.sessionKey
// and run.agentId), where Adam types; OpenClaw's own webchat runs elsewhere (a HUD "+" chat, a
// skill review) don't count. A child session (run.child: a subagent, or a session the guard saw
// spawned) is never typing on any channel: its prompt is a brief another run wrote, and OpenClaw
// copies the parent's owner flag and channel onto it (subagent-spawn, 2026.11.6).
export const HTTP_RUN_ID = /^(chatcmpl|resp)_/;

export function typedByOwner(r, run = {}, settings = {}) {
  if (r?.senderIsOwner !== true) return false;
  if (run?.child === true) return false;
  if (r.channel === "telegram") return typeof r.senderId === "string" && r.senderId.length > 0;
  if (r.channel === "webchat") {
    const keys = settings?.cleanSessionKeys ?? ["agent:main:main"];
    return settings?.hudTypingIsAdam !== false && run?.hud === "typed"
      && keys.includes(run?.sessionKey) && (run?.agentId ?? "main") === "main";
  }
  return r.channel === undefined && r.senderId === undefined;
}

// A session another run started: an OpenClaw subagent key, or one the guard recorded as spawned.
export function childSession(key, parentOf = () => null) {
  const k = String(key ?? "");
  return /:subagent:/.test(k) || !!parentOf(k);
}

// How before_agent_run sorts a webchat turn (ADR 0011): by the Gateway-set run id, the run's
// trigger and the markers near the start of the raw prompt or of the typed text (a metadata block
// may come first). A run started by a heartbeat, cron job or event ("background") is never typing,
// even when it carries a webchat requester.
export function hudKind(runId, heads, trigger) {
  const near = (m) => heads.some((h) => String(h ?? "").slice(0, 200).includes(m));
  if (near("[Spoken turn.")) return "spoken";
  if (near("[Typed by Claude Code")) return "drive";
  if (typeof trigger === "string" && trigger !== "user") return "background";
  if (typeof runId !== "string" || runId.length === 0) return "unknown";
  if (HTTP_RUN_ID.test(runId)) return "http";
  return "typed";
}

// Who asked for an agent run, as before_agent_run sees it. OpenClaw 2026.11.6 (live 2026-11-22)
// no longer puts the requester on that hook's context, only on tool hooks: the channel and the
// trigger are on the context, the sender on the event (runBeforeAgentRunGate). This rebuilds the
// same shape from those. A run with no channel stays without a requester (never typing), and a
// run started by a heartbeat, cron job or event gets none either.
export function agentRunRequester(event, ctx) {
  if (ctx?.requester) return ctx.requester;
  if (typeof ctx?.trigger === "string" && ctx.trigger !== "user") return undefined;
  const channel = typeof ctx?.channel === "string" && ctx.channel.length > 0 ? ctx.channel : undefined;
  if (!channel) return undefined;
  const id = [event?.senderId, ctx?.senderId].find((v) => typeof v === "string" && v.length > 0);
  return { channel, ...(id ? { senderId: id } : {}), senderIsOwner: event?.senderIsOwner === true };
}

// A plugin command typed in Adam's paired Mac HUD or Control UI (2026-11-26, ADR 0012). OpenClaw
// counts a command's sender as owner only with operator.admin or commands.ownerAllowFrom, and the
// HUD pairs with operator.read, .write and .approvals, so senderIsOwner is false there. A chat.send
// command carries the client's scopes in gatewayClientScopes (OpenClaw's own device-pair and
// talk-voice commands read the same field). Spoken turns can't get here: jorah-voice and
// jorah-phone put "[Spoken turn." before the words, and OpenClaw runs only messages that start
// with "/". Used only for the safe-direction commands: careful mode on, and /jorah-today.
export function typedInOwnApp(c) {
  if (c?.channel !== "webchat" || c?.isAuthorizedSender !== true) return false;
  const scopes = c?.gatewayClientScopes;
  if (!Array.isArray(scopes) || !scopes.includes("operator.write")) return false;
  return !String(c?.commandBody ?? "").includes("[Spoken turn.");
}

export function speaker(ctx = {}, settings = {}, run = {}) {
  const r = ctx.requester ?? null;
  const webchatRaw = r?.channel === "webchat";
  const voice = r?.channel === "voice" || (webchatRaw && (run?.voice === true || run?.hud === "spoken"));
  const webchat = webchatRaw && !voice;
  const drive = webchat && run?.hud === "drive";
  const owner = r?.senderIsOwner === true;
  const typed = !voice && !drive && typedByOwner(r, { ...run, sessionKey: ctx.sessionKey, agentId: ctx.agentId }, settings);
  const cleanKeys = settings.cleanSessionKeys ?? ["agent:main:main"];
  const cleanEligible = typed && cleanKeys.includes(ctx.sessionKey) && (ctx.agentId ?? "main") === "main";
  return { voice, webchat, drive, owner, cleanEligible, typedByOwner: typed };
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

const WEBCHAT = "from the HUD or the web chat, not known to be typed by Adam";
const DRIVE = "typed by Claude Code in HUD drive mode";

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
  else if (who.drive) source = DRIVE;
  else if (who.webchat && !who.typedByOwner) source = WEBCHAT;
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

// Does every sentence of the text come from one of Adam's own typed messages in this chat (Adam,
// 2026-11-25: "can't we make a system that decides")? Only messages that asked to remember
// something, or are short (300 characters or fewer), count: a long one may be a pasted email or
// page. Each sentence needs 80% of its words in one such message, and every number, address, path
// or dotted name must appear in his messages as typed (dates excepted): those are what carry data.
const TOKEN_RE = /[\p{L}\p{N}][\p{L}\p{N}._@\/:+-]*[\p{L}\p{N}]|\p{N}/gu;
const EXACT = /[\p{N}@\/:]|\p{L}\.\p{L}/u;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const NEG = /\b(not|no|never|none|nothing|without|nie|nikdy|bez)\b|n['’]t\b/i;

export function ownChatWords(content, messages) {
  const text = String(content ?? "");
  if (text.trim().length === 0 || text.length > 600) return false;
  const own = (Array.isArray(messages) ? messages : []).map(String).filter((m) => m.length <= 300 || ASKED.test(m));
  if (own.length === 0) return false;
  const typed = new Set(own.join("\n").toLowerCase().match(TOKEN_RE) ?? []);
  for (const t of text.match(TOKEN_RE) ?? []) {
    if (EXACT.test(t) && !DATE.test(t) && !typed.has(t.toLowerCase())) return false;
  }
  const vocab = own.map((m) => ({ len: m.length, neg: NEG.test(m), words: new Set(m.toLowerCase().match(WORD_RE) ?? []) }));
  let any = false;
  for (const s of text.split(/[.!?;]+(?=\s|$)|\n+/).map((x) => x.trim()).filter(Boolean)) {
    const words = s.replace(/\b\d{4}-\d{2}-\d{2}\b/g, " ").toLowerCase().match(WORD_RE)?.filter((w) => !STOP.has(w)) ?? [];
    if (words.length === 0) continue;
    any = true;
    // A "not" dropped or added turns his words around.
    const from = vocab.some((m) => words.filter((w) => m.words.has(w)).length / words.length >= 0.8 && s.length <= 3 * m.len + 40 && NEG.test(s) === m.neg);
    if (!from) return false;
  }
  return any;
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

// A drive turn says so even in a chat that has read outside text (fix of 2026-11-27): the card
// used to name only the outside text, so Adam couldn't tell Claude Code had typed the line.
const why = (s) => (s.voice ? "Asked by voice: confirm only if this was you."
  : s.drive ? "Typed by Claude Code in HUD drive mode, not by Adam: only Adam allows, in the HUD or Telegram."
    + (s.source && s.source !== DRIVE ? ` This chat has also read outside text (${short(s.source, 80)}).` : "")
  : s.source === WEBCHAT ? "From the HUD or the web chat, but not known to be Adam's typing: confirm only if this was you."
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

// Careful mode (docs/plan/13-autonomy.md 6.6): while Adam's /jorah-careful is on, every write the
// guard would let main or deep make alone becomes a card. Reading, searching and asking deep stay
// free; blocks and cards stay as they are. view.careful() returns the ISO time it ends, or null.
const CAREFUL_CLASSES = new Set(["fileWrite", "memoryWrite", "skill", "schedule", "localWrite", "ownWordsWrite", "spawn"]);

// "Thu 14:05" in Adam's time zone; the raw value if it isn't a date.
export function localTime(iso, timeZone = "Europe/Bratislava") {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("en-GB", { timeZone, weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });
}

export function decide(args) {
  const d = decideBase(args);
  if (d.verdict !== "allow") return d;
  const { tool, params = {}, ctx = {}, matrix, view, settings = {}, run = {} } = args;
  const until = view?.careful?.() ?? null;
  if (!until || !actsAsMain(matrix, ctx.agentId ?? "unknown")) return d;
  const cls = classify(matrix, tool);
  if (!CAREFUL_CLASSES.has(cls)) return d;
  if ((matrix.readActions ?? []).includes(typeof params.action === "string" ? params.action : "")) return d;
  if (cls === "spawn" && params.runtime !== "acp" && isHelperAgent(matrix, params.agentId)) return d;
  const state = sessionState(view, ctx, settings, run, matrix);
  const c = card(cardTitle(matrix, tool), [`Careful mode is on until ${localTime(until)} (Adam's /jorah-careful): every write asks first.`, ...paramLines(params)],
    { voice: state.voice, severity: cardSeverity(cls, params) });
  return d.taint ? { ...c, taint: d.taint } : c;
}

function decideBase({ tool, params = {}, ctx = {}, derivedPaths, matrix, view, settings = {}, run = {} }) {
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
      // The transcript of a clean extension child (deep asked from Adam's clean chat) that has read
      // no outside text holds only this guard's clean words: reading it marks nothing (2026-11-25).
      const target = params.sessionKey ?? params.key;
      if (tool === "sessions_history" && typeof target === "string" && view.cleanChild?.(target) && view.taintOf?.(target)?.tainted !== true) {
        return { verdict: "allow" };
      }
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
      // Jorah's own rules files at the top of his workspace: always a card, even in Adam's clean
      // chat (docs/plan/13-autonomy.md 6.2). A project's AGENTS.md under ~/work is a different path.
      const self = paths.filter((p) => (matrix.selfFiles ?? []).includes(p));
      if (self.length > 0) {
        return card("Jorah wants to change its own rules", [state.tainted ? why(state) : "Jorah's own rules files always ask Adam first.",
          `Files: ${short(self.join(", "), 120)}`, `Adds: ${short(addedText(tool, params), 300)}`], cardOpts);
      }
      if (!state.tainted) return { verdict: "allow" };
      const added = addedText(tool, params);
      if (kinds.includes("rules")) {
        return card("Jorah wants to change its own rules", [why(state), `Files: ${short(paths.join(", "), 120)}`, `Adds: ${short(added, 300)}`], cardOpts);
      }
      if (kinds.includes("memory")) {
        if (state.typedByOwner && (coveredByWords(added, view.wordsOf(key)) || ownChatWords(added, view.typedOf?.(key)))) return { verdict: "allow", reason: "Adam's own words" };
        return card("Jorah wants to save to memory", [why(state), `File: ${short(paths.join(", "), 80)}`, `Text: ${short(added, 320)}`], cardOpts);
      }
      return { verdict: "allow" };
    }

    case "memoryWrite": {
      if (!state.tainted || readAction) return { verdict: "allow" };
      const added = addedText(tool, params);
      if (state.typedByOwner && (coveredByWords(added, view.wordsOf(key)) || ownChatWords(added, view.typedOf?.(key)))) return { verdict: "allow", reason: "Adam's own words" };
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
      // brief's URLs are still checked, and the answer marks this chat.
      // An extension agent (deep since 2026-11-25) may write and use main's tools, but its session is
      // only as clean as this chat was when it asked (index.js marks it), so after outside text its
      // writes and sends get the same cards main's would. Adam: "just make it so that the main agent
      // can elevate the issue to opus and he then tries to solve it". A clean one's answer marks this
      // chat only once the child itself has read outside text (state.taintedChildOf); any other
      // spawn's answer marks it at once.
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

    // An open loop (docs/plan/13-autonomy.md 4.4): saved alone only in Adam's own clean chat when
    // every sentence of who and what comes from a message he typed there; otherwise the card shows
    // the exact fields and it is saved only on Allow once.
    case "ownWordsWrite": {
      const text = [params.who, params.what].map((v) => textOf(v ?? "")).join(". ");
      if (!state.tainted && state.typedByOwner && ownChatWords(text, view.typedOf?.(key))) return { verdict: "allow", reason: "Adam's own words" };
      return card(cardTitle(matrix, tool), [state.tainted ? why(state) : "", ...paramLines(params)], cardOpts);
    }

    // Always a card with the exact fields, whoever asks.
    case "confirmAlways":
      return card(cardTitle(matrix, tool), [state.tainted ? why(state) : "", ...paramLines(params)], cardOpts);

    // The tick drains the outbox; outside its automation the lines would be lost.
    case "cronOnly":
      return isCronSession(key) ? { verdict: "allow" } : { verdict: "block", reason: `${tool} runs only in its automation` };

    default:
      return { verdict: "block", reason: `${tool} isn't in Jorah's permission list yet` };
  }
}
