// jorah-guard v0 (docs/plan/p5-plan.md section 4). Runs before every tool call at a high priority,
// ahead of jorah-github's card. Fails closed: an error, an unreadable matrix or unreadable state
// blocks the call. It cannot see inside Claude Code jobs or Dreaming, and a compromised Gateway
// process beats it (4.7).

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { GuardState } from "./lib/state.js";
import { AuditLog, argsHash } from "./lib/audit.js";
import { summarizeDay, readTail } from "./lib/today.js";
import { agentRunRequester, decide, hudKind, localTime, isExtensionAgent, isHelperAgent, proactiveRun, resultSeeds, sessionState, speaker, typedByOwner, typedInOwnApp, viewBackstop } from "./lib/policy.js";
import { findUrls, linkHygiene, normalise, onSiteAllowlist, ownTypedText, seenForms, strings, withoutTracking, writtenTokens } from "./lib/urls.js";
import { loadSites } from "./lib/sites.js";

const PRIORITY = 1000;

// Hygiene for a link going up from a consult child: verified finds may be long (search-result shop
// links carry parameters), never carry a credential-like parameter or token.
const upHygienic = (u, matrix) => linkHygiene(u, { maxChars: matrix.urlSeenMaxChars ?? 1000, credentialParams: matrix.urlCredentialParams }) === null;
const REMOVED = "[link removed: not from a source you gave me]";

function promptText(prompt) {
  if (typeof prompt === "string") return prompt;
  if (Array.isArray(prompt)) return prompt.map((p) => (typeof p?.text === "string" ? p.text : strings(p).join("\n"))).join("\n");
  return strings(prompt).join("\n");
}

function loadMatrix(file) {
  try {
    const m = JSON.parse(readFileSync(file, "utf8"));
    return m && m.version === 1 ? m : null;
  } catch {
    return null;
  }
}

export default {
  id: "jorah-guard",
  name: "Jorah guard",
  description: "Taint, write confirmations, a URL rule, voice rules and a freeze for Jorah's tools.",
  register(api) {
    const cfg = api.pluginConfig ?? {};
    const stateDir = cfg.stateDir ?? join(homedir(), ".jorah-guard");
    const settings = {
      workspace: cfg.workspace ?? join(homedir(), "workspace"),
      cleanSessionKeys: cfg.cleanSessionKeys ?? ["agent:main:main"],
      // ADR 0011 (Adam, 2026-11-26): typing in the Mac HUD counts as Adam's own chat. false = off.
      hudTypingIsAdam: cfg.hudTypingIsAdam !== false,
    };
    const matrixFile = cfg.matrixFile ?? "/opt/jorah/config/permission-matrix.json";
    // Site readers (lib/sites.js): the site files and the private file, re-read every 30 s so a new
    // site needs no restart. A broken file disables only that site; errors are logged once each.
    const sitesDir = cfg.sitesDir ?? "/opt/jorah/config/sites";
    const sitesPrivateFile = cfg.sitesPrivateFile ?? "/etc/jorah/sites.private.json";
    let sitesCache = { at: 0, value: new Map(), errors: "" };
    settings.sites = () => {
      if (Date.now() - sitesCache.at < 30000) return sitesCache.value;
      const { sites, errors } = loadSites({ dir: sitesDir, privateFile: sitesPrivateFile, allowTest: cfg.allowTestSites === true });
      const e = errors.join("; ");
      if (e && e !== sitesCache.errors) api.logger.warn(`jorah-guard: sites: ${e}`);
      sitesCache = { at: Date.now(), value: sites, errors: e };
      return sites;
    };
    const state = new GuardState(stateDir);
    const audit = new AuditLog(join(stateDir, "decisions.jsonl"));
    let matrix = loadMatrix(matrixFile);

    // The log never holds argument values: URLs in a reason (which may carry data) become <url>.
    const redact = (s) => (s == null ? null : String(s).replace(/\b(?:[a-z][a-z0-9+.-]*:\/\/|file:|data:|javascript:)[^\s,)]+/gi, "<url>").slice(0, 200));
    const log = (entry) => {
      try { audit.write({ ...entry, reason: redact(entry.reason) }); } catch (e) { api.logger.warn(`jorah-guard: audit write failed: ${e?.message}`); }
    };
    const view = {
      taintOf: (k) => state.taintOf(k),
      hasSeen: (k, u) => state.hasSeen(k, u),
      typedSeen: (k, u) => state.typedSeen(k, u),
      wordsOf: (k) => state.wordsOf(k),
      typedOf: (k) => state.typedOf(k),
      readRepos: (k) => state.readRepos(k),
      countAcp: (k) => state.countAcp(k),
      frozen: () => state.frozen(),
      careful: () => state.careful(),
      parentOf: (k) => state.parentOf(k),
      cleanChild: (k) => state.cleanChild(k),
    };
    // Spawns of an extension agent waiting for their child's key: toolCallId -> how clean the
    // asking chat was at that moment (before this spawn marked it "worker result").
    const extensionSpawns = new Map();

    // MCP tools called through the search wrapper arrive without a requester (P5.4, agentmemory on
    // jorah-dev), though the same run's other calls carry one. The run id is set by the Gateway, not
    // the model, so a missing requester is taken from the same run; with no match it stays missing.
    const runs = new Map(); // runId -> requester
    const remember = (ctx) => {
      if (!ctx?.runId || !ctx?.requester) return;
      runs.set(ctx.runId, ctx.requester);
      if (runs.size > 500) runs.delete(runs.keys().next().value);
    };
    const withRequester = (ctx) =>
      ctx && !ctx.requester && ctx.runId && runs.has(ctx.runId) ? { ...ctx, requester: runs.get(ctx.runId) } : ctx;

    // The run's trigger ("user", "heartbeat", "cron", ...) reaches before_agent_run but not
    // before_tool_call (OpenClaw 2026.10.9), so it is kept per run id, which the Gateway sets.
    const triggers = new Map(); // runId -> trigger
    const rememberTrigger = (ctx) => {
      if (!ctx?.runId || typeof ctx.trigger !== "string") return;
      triggers.set(ctx.runId, ctx.trigger.slice(0, 40));
      if (triggers.size > 500) triggers.delete(triggers.keys().next().value);
    };

    // Spoken-turn marker for webchat turns (2026-11-22): OpenClaw 2026.10.9 refuses plugin approval
    // cards from "voice", so jorah-voice and jorah-phone send x-openclaw-message-channel: "webchat"
    // with a prompt starting with "[Spoken turn.". Remember it per runId (or sessionKey when runId
    // is absent) and clear it on the next before_agent_run for that session. Typing the marker by
    // hand only changes wording, because voice and webchat get the same checks.
    const spokenRuns = new Set(); // runIds for spoken webchat turns
    const spokenSessions = new Set(); // sessionKeys for spoken webchat turns without a runId
    const sessionSpokenRun = new Map(); // sessionKey -> last spoken runId
    const capSet = (set, value) => {
      set.add(value);
      if (set.size > 500) set.delete(set.values().next().value);
    };
    const clearSpoken = (key) => {
      if (!key) return;
      spokenSessions.delete(key);
      const prevRun = sessionSpokenRun.get(key);
      if (prevRun) {
        spokenRuns.delete(prevRun);
        sessionSpokenRun.delete(key);
      }
    };
    const rememberSpoken = (ctx, key, spoken) => {
      clearSpoken(key);
      if (!spoken) return;
      if (ctx?.runId) {
        capSet(spokenRuns, ctx.runId);
        if (key) {
          sessionSpokenRun.set(key, ctx.runId);
          if (sessionSpokenRun.size > 500) sessionSpokenRun.delete(sessionSpokenRun.keys().next().value);
        }
      } else if (key) {
        capSet(spokenSessions, key);
      }
    };
    // How each webchat run was sorted in before_agent_run (ADR 0011): "typed" (Adam in the HUD),
    // "spoken", "drive", "background", "http" or "unknown". Tool calls take it by run id; a run missing here
    // (never seen, or forgotten after 500 newer ones) is not Adam's typing.
    const hudRuns = new Map(); // runId -> kind
    const rememberHud = (runId, kind) => {
      if (typeof runId !== "string" || !runId) return;
      hudRuns.delete(runId);
      hudRuns.set(runId, kind);
      if (hudRuns.size > 500) hudRuns.delete(hudRuns.keys().next().value);
    };

    const isSpokenRun = (ctx) =>
      Boolean((ctx?.runId && spokenRuns.has(ctx.runId)) || (ctx?.sessionKey && spokenSessions.has(ctx.sessionKey)));

    // Calls the guard blocked: their result (if the Gateway reports one) holds the refusal, which
    // quotes the URL, so it never adds seen URLs.
    const blockedCalls = new Set();
    const noteBlocked = (id) => {
      if (typeof id !== "string") return;
      blockedCalls.add(id);
      if (blockedCalls.size > 500) blockedCalls.delete(blockedCalls.values().next().value);
    };

    api.on("before_tool_call", (event, rawCtx) => {
      const tool = event?.toolName;
      remember(rawCtx);
      const ctx = withRequester(rawCtx);
      try {
        state.enter(ctx?.sessionKey, ctx?.sessionId);
        if (!matrix) matrix = loadMatrix(matrixFile);
        const run = { trigger: (ctx?.runId && triggers.get(ctx.runId)) || null, voice: isSpokenRun(ctx), hud: (ctx?.runId && hudRuns.get(ctx.runId)) || null };
        const before = sessionState(view, ctx ?? {}, settings, run, matrix ?? {});
        const taintedBefore = before.tainted;
        const d = decide({ tool, params: event?.params ?? {}, ctx: ctx ?? {}, derivedPaths: event?.derivedPaths, matrix, view, settings, run });
        const spawnCall = event?.toolCallId ?? ctx?.toolCallId;
        let cleanSpawn = false;
        if (tool === "sessions_spawn" && matrix && isExtensionAgent(matrix, event?.params?.agentId) && d.verdict !== "block" && typeof spawnCall === "string") {
          const pro = proactiveRun({ ctx: ctx ?? {}, run, matrix, parentOf: (k) => state.parentOf(k) });
          cleanSpawn = !taintedBefore && !pro.proactive;
          extensionSpawns.set(spawnCall, { clean: cleanSpawn, why: taintedBefore ? before.source : pro.why });
          if (extensionSpawns.size > 200) extensionSpawns.delete(extensionSpawns.keys().next().value);
        }
        // Record before the tool runs, so its output can never arrive in a session still marked clean.
        // A clean extension spawn is the exception: its answer marks this chat only once the child
        // reads outside text (State.taintedChildOf), or now in after_tool_call if it isn't marked clean.
        if (d.taint && d.verdict !== "block" && !cleanSpawn) state.markTainted(ctx?.sessionKey, d.taint);
        if (d.readRepo && d.verdict !== "block") state.markReadPrivateRepo(ctx?.sessionKey, d.readRepo);
        // What the model writes after outside text may come back in a later result (a page that
        // echoes a search, the shared browser): remember it so it is never taken as seen.
        // A brief to a consult agent is recorded whatever the taint: what the child finds may go up
        // to this chat (issue #13), so a URL main wrote in the brief must never come back as found.
        const brief = tool === "sessions_spawn" && !!matrix && isHelperAgent(matrix, event?.params?.agentId);
        if ((taintedBefore || brief) && d.verdict !== "block") state.addWritten(ctx?.sessionKey, writtenTokens(event?.params ?? {}));
        if (d.verdict === "block") noteBlocked(event?.toolCallId ?? ctx?.toolCallId);
        // For the review: how the sender was classed, and the channel's name only (never ids).
        const who = speaker(ctx ?? {}, settings, run);
        const from = who.voice ? "voice" : who.drive ? "drive" : who.webchat ? (who.typedByOwner ? "hud-typed" : "webchat")
          : who.typedByOwner ? "adam-typed" : ctx?.requester ? "other" : "none";
        log({ session: ctx?.sessionKey ?? null, agent: ctx?.agentId ?? null, call: ctx?.toolCallId ?? null, from, channel: ctx?.requester?.channel ?? null, trigger: run.trigger, tool, verdict: d.verdict, reason: d.reason ?? d.title ?? null, args: argsHash(event?.params), readAction: (matrix?.readActions ?? []).includes(event?.params?.action) || undefined });
        if (d.verdict === "allow") return undefined;
        if (d.verdict === "block") return { block: true, blockReason: `jorah-guard: ${d.reason}` };
        return {
          requireApproval: {
            title: d.title,
            description: d.description,
            severity: d.severity ?? "critical",
            allowedDecisions: ["allow-once", "deny"],
            timeoutMs: 5 * 60 * 1000,
            pluginId: "jorah-guard",
          },
        };
      } catch (error) {
        log({ session: ctx?.sessionKey ?? null, agent: ctx?.agentId ?? null, call: ctx?.toolCallId ?? null, tool, verdict: "block", reason: `guard error: ${error?.message ?? error}` });
        return { block: true, blockReason: "jorah-guard: the guard couldn't check this call, so it is blocked." };
      }
    }, { priority: PRIORITY });

    // Collect URLs from outside readers' results (G-S2, policy.resultSeeds) and link spawned
    // children to their parent session.
    api.on("after_tool_call", (event, ctx) => {
      try {
        const key = ctx?.sessionKey;
        state.enter(key, ctx?.sessionId);
        const callId = event?.toolCallId ?? ctx?.toolCallId;
        const refused = event?.error != null || (typeof callId === "string" && blockedCalls.has(callId));
        if (!matrix) matrix = loadMatrix(matrixFile);
        // Review fix 6: a clean-view toolbox_list was decided before it ran (policy.cleanView). If
        // its result isn't the clean view after all, mark the chat now. Only ever adds a mark.
        const late = matrix && viewBackstop({ tool: event?.toolName, params: event?.params ?? {}, result: event?.result, error: event?.error, matrix });
        if (late) {
          state.markTainted(key, late);
          log({ session: key ?? null, agent: ctx?.agentId ?? null, call: callId ?? null, tool: event?.toolName, verdict: "late-mark", reason: late });
        }
        if (!refused && matrix) {
          const urls = resultSeeds({ tool: event?.toolName, params: event?.params ?? {}, result: event?.result, matrix, wrote: (cores) => state.wrote(key, cores) });
          const forms = urls.flatMap(seenForms);
          state.addSeen(key, forms);
          // A consult child's (deep's) own finds count as seen in the chat that asked it, so the
          // shop and source links it reports survive the reply rule there (issue #13). Only links
          // that pass link hygiene go up; deep's own written words were already left out above.
          const parent = state.parentOf(key);
          if (parent && isHelperAgent(matrix, ctx?.agentId)) state.addSeen(parent, forms.filter((u) => upHygienic(u, matrix)));
        }
        const child = event?.result?.details?.childSessionKey;
        if (event?.toolName === "sessions_spawn" && typeof child === "string") {
          state.linkChild(child, key);
          const asked = typeof callId === "string" ? extensionSpawns.get(callId) : undefined;
          if (asked) {
            extensionSpawns.delete(callId);
            if (asked.clean && !refused) state.markCleanChild(child, key);
            else {
              state.markTainted(child, `asked from a chat that wasn't clean: ${asked.why}`);
              if (asked.clean) state.markTainted(key, "worker result");
            }
          } else if (matrix && isExtensionAgent(matrix, event?.params?.agentId)) {
            // No record of how clean the asking chat was: its answer marks this chat, as before.
            state.markTainted(key, "worker result");
          }
          if (matrix && isHelperAgent(matrix, event?.params?.agentId)) state.addSeen(key, state.ownOutsideSeen(child).filter((u) => upHygienic(u, matrix)));
        } else if (event?.toolName === "sessions_spawn" && typeof callId === "string" && extensionSpawns.get(callId)?.clean) {
          // A clean spawn whose result names no child: whatever it started can't be tracked.
          extensionSpawns.delete(callId);
          state.markTainted(key, "worker result");
        }
      } catch (e) {
        api.logger.warn(`jorah-guard: after_tool_call: ${e?.message}`);
      }
      return undefined;
    });

    // Adam's own words for this turn: URLs in them count as seen, and a memory line taken from them
    // saves without asking. Needs hooks.allowConversationAccess; without it every such save asks.
    api.on("before_agent_run", (event, ctx) => {
      try {
        const key = ctx?.sessionKey ?? event?.sessionKey;
        remember(ctx);
        rememberTrigger(ctx);
        state.enter(key, ctx?.sessionId ?? event?.sessionId);
        const r = agentRunRequester(event, ctx);
        const rawPrompt = promptText(event?.prompt);
        // Only the text Adam typed: quoted messages and the chat window OpenClaw adds can hold
        // Jorah's own earlier words.
        const prompt = ownTypedText(rawPrompt);
        // Markers near the start, not only at it: OpenClaw may put an envelope such as a timestamp
        // or a metadata block first, so the typed text is checked too (ADR 0011).
        const hud = r?.channel === "webchat" ? hudKind(ctx?.runId, [rawPrompt, prompt], ctx?.trigger) : null;
        if (hud) rememberHud(ctx?.runId, hud);
        rememberSpoken(ctx, key, hud === "spoken");
        // Only Adam's own typed turns count (Telegram, the CLI, the HUD); voice, drive mode,
        // children and unknown senders don't.
        if (!typedByOwner(r, { hud }, settings)) { state.setWords(key, ""); return undefined; }
        state.setWords(key, prompt);
        state.addTyped(key, prompt);
        state.addSeen(key, findUrls(prompt).flatMap(seenForms), "adam");
      } catch (e) {
        api.logger.warn(`jorah-guard: before_agent_run: ${e?.message}`);
      }
      return undefined;
    });

    // /new and /reset keep the sessionId but empty the context: start the chat's record again.
    api.on("before_reset", (event, ctx) => {
      try {
        const key = ctx?.sessionKey ?? event?.sessionKey;
        if (key) { clearSpoken(key); state.reset(key); log({ session: key, tool: "before_reset", verdict: "reset" }); }
      } catch (e) {
        api.logger.warn(`jorah-guard: before_reset: ${e?.message}`);
      }
      return undefined;
    });

    // Telegram replies only (G-S3): in a chat that has read outside text, strip links nobody gave.
    // A link that passes goes out without common tracking parameters (utm_*, gclid, fbclid, ...):
    // they are only cut out, nothing is added, and the link is checked as it was seen.
    api.on("message_sending", (event, ctx) => {
      try {
        const key = ctx?.sessionKey;
        // Delivery hooks carry no requester, so use the recorded taint; an unknown chat counts as tainted.
        const tainted = !key || state.taintOf(key)?.tainted === true;
        if (!tainted || typeof event?.content !== "string") return undefined;
        let removed = false;
        let tidied = false;
        const content = event.content.replace(/\bhttps?:[^\s"'<>`\\]+/gi, (raw) => {
          const core = raw.replace(/[),.;:!?\]}>]+$/, "");
          const n = normalise(core, { keepHash: true });
          const ok = n && ((key ? state.hasSeen(key, n) : state.anySeen(n)) || onSiteAllowlist(n, matrix?.siteAllowlist ?? []));
          if (!ok) {
            removed = true;
            return REMOVED;
          }
          const clean = withoutTracking(core);
          if (clean === core) return raw;
          tidied = true;
          return `${clean}${raw.slice(core.length)}`;
        });
        if (removed) log({ session: key ?? null, tool: "message_sending", verdict: "rewrite", reason: "unseen link removed" });
        if (tidied) log({ session: key ?? null, tool: "message_sending", verdict: "tidy", reason: "tracking parameters removed" });
        return removed || tidied ? { content } : undefined;
      } catch (e) {
        api.logger.warn(`jorah-guard: message_sending: ${e?.message}`);
        return undefined;
      }
    });

    api.registerCommand({
      name: "jorah-freeze",
      description: "Freeze Jorah: every action beyond reading is blocked until Adam clears it at a terminal.",
      requireAuth: true,
      handler: async (ctx) => {
        if (ctx?.senderIsOwner !== true) {
          return { text: typedInOwnApp(ctx) ? "Freezing works only from Telegram." : "Only Adam can freeze Jorah." };
        }
        state.freeze(ctx?.channel ?? "command");
        log({ session: ctx?.sessionKey ?? null, tool: "/jorah-freeze", verdict: "freeze" });
        return { text: "Frozen. Jorah can still read and answer, nothing more. Clear it at a terminal with scripts/pc/guard-unfreeze.sh." };
      },
    });

    // Careful mode (docs/plan/13-autonomy.md 6.6): a soft pause Adam sets and lifts in chat.
    api.registerCommand({
      name: "jorah-careful",
      description: "Careful mode: every write Jorah would make alone asks first, for 24 hours. \"/jorah-careful off\" ends it.",
      acceptsArgs: true,
      requireAuth: true,
      handler: async (ctx) => {
        // Turning it on only tightens, so Adam's paired HUD may do it too; turning it off stays on
        // Telegram (2026-11-26), so a line typed in the HUD (or by drive mode) can't lift it.
        const owner = ctx?.senderIsOwner === true;
        const inApp = !owner && typedInOwnApp(ctx);
        if (!owner && !inApp) return { text: "Only Adam can change careful mode." };
        const arg = String(ctx?.args ?? "").trim().toLowerCase();
        if (arg === "off") {
          if (!owner) return { text: "Careful mode can be turned off only from Telegram: /jorah-careful off." };
          state.clearCareful();
          log({ session: ctx?.sessionKey ?? null, tool: "/jorah-careful", verdict: "careful-off" });
          return { text: "Careful mode off. Jorah's usual rules apply again." };
        }
        if (arg !== "" && arg !== "on") return { text: "Use /jorah-careful to turn it on for 24 hours, or /jorah-careful off." };
        const until = state.setCareful(ctx?.channel ?? "command");
        log({ session: ctx?.sessionKey ?? null, tool: "/jorah-careful", verdict: "careful", reason: inApp ? "typed in the HUD" : undefined });
        const off = inApp ? "/jorah-careful off on Telegram ends it." : "/jorah-careful off ends it.";
        return { text: `Careful mode on until ${localTime(until)}. Every write Jorah would make alone (files, memory, skills, schedules, records, coding and background jobs) asks you first. Reading, searching and asking deep stay free. ${off}` };
      },
    });

    api.registerCommand({
      name: "jorah-today",
      description: "What Jorah did alone today, cards shown and calls blocked, from the guard's log.",
      requireAuth: true,
      handler: async (ctx) => {
        // Read-only, so Adam's paired HUD may ask too (2026-11-26); voice can't (typedInOwnApp).
        if (ctx?.senderIsOwner !== true && !typedInOwnApp(ctx)) return { text: "Only Adam can see this." };
        try {
          return { text: summarizeDay(readTail(join(stateDir, "decisions.jsonl")), { matrix }) };
        } catch (e) {
          return { text: `The guard's log couldn't be read (${String(e?.message ?? e).slice(0, 80)}), so today's activity is unknown.` };
        }
      },
    });

    api.registerCommand({
      name: "jorah-status",
      description: "Show the guard's state for this chat.",
      requireAuth: true,
      handler: async (ctx) => {
        const t = state.taintOf(ctx?.sessionKey);
        return {
          text: [
            state.frozen() ? "Frozen: yes (clear at a terminal)." : "Frozen: no.",
            state.careful() ? `Careful mode: on until ${localTime(state.careful())}.` : "Careful mode: off.",
            t?.tainted ? `This chat has read outside text: ${t.source}.` : "This chat hasn't read outside text.",
            matrix ? "Permission list: loaded." : "Permission list: UNREADABLE, so every tool is blocked.",
          ].join("\n"),
        };
      },
    });

    api.logger.info(`jorah-guard: ${matrix ? "matrix loaded" : "MATRIX UNREADABLE, blocking everything"}; state ${state.broken ? `BROKEN (${state.broken})` : "ok"}`);
  },
};
