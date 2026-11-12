// jorah-guard v0's decision for one tool call (docs/plan/p5-plan.md 4.1 to 4.3). Pure: it reads
// the session view it is given and returns what to do, plus what to record. The caller applies
// it. Everything not explicitly allowed is blocked; anything the guard can't tell is treated as
// "this chat has read outside text".

import { posix } from "node:path";
import { forbidden, normalise, onSiteAllowlist, urlsIn } from "./urls.js";

const CARD_MAX = 500;

export function classify(matrix, tool) {
  for (const cls of ["read", "taintRead", "search", "url", "fileWrite", "memoryWrite", "skill", "schedule", "spawn",
    "github", "message", "sandboxShell", "blocked"]) {
    if ((matrix[cls] ?? []).includes(tool)) return cls;
  }
  return null;
}

// Who is asking, from the hook's context. Voice arrives as "webchat" (G-S1, 2026-11-11); until the
// voice service sets a marker of its own, every webchat turn counts as voice.
export function speaker(ctx = {}, settings = {}) {
  const r = ctx.requester ?? null;
  const voice = r?.channel === "webchat";
  const owner = r?.senderIsOwner === true;
  const cleanKeys = settings.cleanSessionKeys ?? ["agent:main:main"];
  const cleanEligible = owner && !voice && cleanKeys.includes(ctx.sessionKey) && (ctx.agentId ?? "main") === "main";
  return { voice, owner, cleanEligible, typedByOwner: owner && !voice };
}

// Session state as the policy needs it.
export function sessionState(view, ctx, settings) {
  const who = speaker(ctx, settings);
  const recorded = view.taintOf(ctx.sessionKey);
  let source = null;
  if (recorded?.tainted) source = recorded.source;
  else if (who.voice) source = "asked by voice";
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

function card(title, lines) {
  let description = lines.filter(Boolean).join("\n");
  if (description.length > CARD_MAX) description = `${description.slice(0, CARD_MAX - 1)}…`;
  return { verdict: "confirm", title: short(title, 78), description };
}

const why = (s) => (s.voice ? "Asked by voice: confirm only if this was you." : `This chat has read outside text (${short(s.source, 80)}).`);

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

export function checkUrls(value, state, view, sessionKey, matrix) {
  for (const raw of [...urlsIn(value), ...urlParams(value)]) {
    const bad = forbidden(raw);
    if (bad) return `${short(raw, 60)}: ${bad}`;
    if (!state.tainted) continue;
    const n = normalise(raw);
    if (n && (view.hasSeen(sessionKey, n) || onSiteAllowlist(n, matrix.siteAllowlist))) continue;
    return `${short(raw, 60)} wasn't in your message or an earlier result, and this chat has read outside text`;
  }
  return null;
}

/**
 * @returns {{ verdict: "allow"|"block"|"confirm", reason?: string, title?: string, description?: string,
 *             taint?: string, readRepo?: string }}
 */
export function decide({ tool, params = {}, ctx = {}, derivedPaths, matrix, view, settings = {} }) {
  if (!matrix || typeof matrix !== "object") return { verdict: "block", reason: "permission matrix unreadable" };
  if (typeof tool !== "string" || tool.length === 0) return { verdict: "block", reason: "no tool name" };

  // The search wrapper: decide on the inner call now only to block early; the hook runs again on the
  // inner tool with its real name (G-S2), where cards and taint are handled. Never a card here.
  if (tool === "tool_call") {
    // Inner ids may be namespaced ("openclaw:core:web_fetch", P5.4): the last part is the tool name.
    const raw = typeof params.id === "string" ? params.id : typeof params.name === "string" ? params.name : null;
    const inner = raw ? raw.split(":").pop() : null;
    if (!inner) return { verdict: "allow", reason: "wrapper without a named tool" };
    const d = decide({ tool: inner, params: params.args ?? params.arguments ?? {}, ctx, matrix, view, settings });
    return d.verdict === "block" ? d : { verdict: "allow", reason: `wrapper for ${inner}` };
  }

  const cls = classify(matrix, tool);
  const state = sessionState(view, ctx, settings);
  const key = ctx.sessionKey;
  const agent = ctx.agentId ?? "unknown";
  const action = typeof params.action === "string" ? params.action : "";
  const readAction = (matrix.readActions ?? []).includes(action);

  if (view.frozen() && cls !== "read") return { verdict: "block", reason: "Jorah is frozen (/jorah-freeze). Adam clears it at a terminal." };

  switch (cls) {
    case "read":
      return { verdict: "allow" };

    case "taintRead": {
      const repo = params.repo ?? params.project;
      return { verdict: "allow", taint: `${tool}${repo ? ` ${short(repo, 40)}` : ""}`, readRepo: typeof repo === "string" ? repo : undefined };
    }

    case "search": {
      const q = textOf(params.query ?? params.q ?? "");
      if (state.tainted && q.length > (matrix.searchQueryMaxChars ?? 200)) return { verdict: "block", reason: "search query too long for a chat that has read outside text" };
      return { verdict: "allow", taint: `${tool} results` };
    }

    case "url": {
      const bad = checkUrls(params, state, view, key, matrix);
      if (bad) return { verdict: "block", reason: `Not opened: ${bad}.` };
      const evalish = /evaluate|wait.*fn|\bfn\b|expression/i.test(textOf(params.kind ?? params.request?.kind ?? "")) || "fn" in params || "expression" in params;
      if (evalish) return { verdict: "block", reason: "page JavaScript is off for Jorah's browser" };
      const kind = textOf(params.request?.kind ?? params.kind ?? params.action ?? "");
      if (tool === "browser" && state.tainted && /\b(type|fill|press|select|upload|drag|keyboard)\b/i.test(kind)) {
        const typed = params.request?.text ?? params.text ?? params.value ?? params.values ?? params.request ?? "";
        return card("Jorah wants to type into a web page", [why(state), `Action: ${short(kind, 30)}`, `Text: ${short(textOf(typed), 300)}`]);
      }
      const host = urlsIn(params).map((u) => { try { return new URL(u).hostname; } catch { return "?"; } })[0];
      return { verdict: "allow", taint: `${tool}${host ? ` ${host}` : ""}` };
    }

    case "fileWrite": {
      if (agent !== "main") return { verdict: "allow" }; // other agents write only inside their sandbox
      const paths = targetPaths(tool, params, derivedPaths, settings.workspace);
      const kinds = paths.map((p) => fileKind(p, matrix));
      if (paths.length === 0) {
        return state.tainted ? card("Jorah wants to change a file", [why(state), `${tool} with no clear target.`]) : { verdict: "allow" };
      }
      if (!state.tainted) return { verdict: "allow" };
      const added = addedText(tool, params);
      if (kinds.includes("rules")) {
        return card("Jorah wants to change its own rules", [why(state), `Files: ${short(paths.join(", "), 120)}`, `Adds: ${short(added, 300)}`]);
      }
      if (kinds.includes("memory")) {
        if (state.typedByOwner && coveredByWords(added, view.wordsOf(key))) return { verdict: "allow", reason: "Adam's own words" };
        return card("Jorah wants to save to memory", [why(state), `File: ${short(paths.join(", "), 80)}`, `Text: ${short(added, 320)}`]);
      }
      return { verdict: "allow" };
    }

    case "memoryWrite": {
      if (!state.tainted || readAction) return { verdict: "allow" };
      const added = addedText(tool, params);
      if (state.typedByOwner && coveredByWords(added, view.wordsOf(key))) return { verdict: "allow", reason: "Adam's own words" };
      return card("Jorah wants to save to memory", [why(state), `Tool: ${tool}`, `Text: ${short(added, 320)}`]);
    }

    case "skill": {
      if (readAction || action === "") return action === "" && state.tainted
        ? card("Jorah wants to change a skill", [why(state), `skill_workshop with no action.`]) : { verdict: "allow" };
      if (!state.tainted) return { verdict: "allow" };
      return card("Jorah wants to change a learned skill", [why(state), `${action} ${short(params.name, 60)}`, `Content: ${short(addedText(tool, params), 300)}`]);
    }

    case "schedule": {
      if (readAction) return { verdict: "allow" };
      const job = params.job ?? params;
      const prompt = textOf(job?.message ?? job?.prompt ?? job?.task ?? job?.payload ?? job);
      const fetches = urlsIn(job).length > 0 || /\b(fetch|browse|web|search|http)/i.test(prompt);
      if (!state.tainted && isOneOff(params) && !fetches) return { verdict: "allow" };
      const bad = checkUrls(job, state, view, key, matrix);
      if (bad) return { verdict: "block", reason: `Schedule refused: ${bad}.` };
      return card("Jorah wants to create or change a schedule", [state.tainted ? why(state) : "", `${tool} ${action}`, `Job: ${short(prompt, 330)}`]);
    }

    case "spawn": {
      const bad = checkUrls(params.task ?? params.message ?? "", state, view, key, matrix);
      if (bad) return { verdict: "block", reason: `Brief refused: ${bad}.` };
      const acp = params.runtime === "acp";
      const who = acp ? `Claude Code in ${short(params.cwd ?? "?", 60)}` : `the ${short(params.agentId ?? "?", 20)} agent`;
      if (acp && (state.tainted || view.countAcp(key) > (matrix.acpSpawnsPerHourWithoutConfirm ?? 3))) {
        return { ...card("Jorah wants to start a coding job", [state.tainted ? why(state) : "More than 3 jobs this hour.", `Who: ${who}`, `Brief: ${short(params.task, 330)}`]), taint: "worker result" };
      }
      // background and deep have a sandboxed shell with internet access, so a brief written after
      // outside text could carry data out past the URL rule. Show it to Adam first.
      if (!acp && state.tainted) return { ...card("Jorah wants to start a job", [why(state), `Who: ${who}`, `Brief: ${short(params.task, 330)}`]), taint: "worker result" };
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
      const target = params.to ?? params.target ?? params.chatId ?? params.recipient;
      if (target === undefined) return { verdict: "allow" };
      return card("Jorah wants to send a message", [state.tainted ? why(state) : "", `To: ${short(target, 60)}`, `Text: ${short(params.text ?? params.message ?? params.content, 300)}`]);
    }

    case "sandboxShell":
      return agent === "main" ? { verdict: "block", reason: "main has no shell; background does shell work" } : { verdict: "allow" };

    case "blocked":
      return { verdict: "block", reason: `${tool} is not allowed` };

    default:
      return { verdict: "block", reason: `${tool} isn't in Jorah's permission list yet` };
  }
}
