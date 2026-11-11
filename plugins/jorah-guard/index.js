// jorah-guard v0 (docs/plan/p5-plan.md section 4). Runs before every tool call at a high priority,
// ahead of jorah-github's card. Fails closed: an error, an unreadable matrix or unreadable state
// blocks the call. It cannot see inside Claude Code jobs or Dreaming, and a compromised Gateway
// process beats it (4.7).

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { GuardState } from "./lib/state.js";
import { AuditLog, argsHash } from "./lib/audit.js";
import { decide } from "./lib/policy.js";
import { findUrls, normalise, onSiteAllowlist, strings, urlsIn } from "./lib/urls.js";

const PRIORITY = 1000;
const REMOVED = "[link removed: not from a source you gave me]";

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
    };
    const matrixFile = cfg.matrixFile ?? "/opt/jorah/config/permission-matrix.json";
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
      wordsOf: (k) => state.wordsOf(k),
      readRepos: (k) => state.readRepos(k),
      countAcp: (k) => state.countAcp(k),
      frozen: () => state.frozen(),
    };

    api.on("before_tool_call", (event, ctx) => {
      const tool = event?.toolName;
      try {
        if (!matrix) matrix = loadMatrix(matrixFile);
        const d = decide({ tool, params: event?.params ?? {}, ctx: ctx ?? {}, derivedPaths: event?.derivedPaths, matrix, view, settings });
        // Record before the tool runs, so its output can never arrive in a session still marked clean.
        if (d.taint && d.verdict !== "block") state.markTainted(ctx?.sessionKey, d.taint);
        if (d.readRepo && d.verdict !== "block") state.markReadPrivateRepo(ctx?.sessionKey, d.readRepo);
        log({ session: ctx?.sessionKey ?? null, agent: ctx?.agentId ?? null, tool, verdict: d.verdict, reason: d.reason ?? d.title ?? null, args: argsHash(event?.params) });
        if (d.verdict === "allow") return undefined;
        if (d.verdict === "block") return { block: true, blockReason: `jorah-guard: ${d.reason}` };
        return {
          requireApproval: {
            title: d.title,
            description: d.description,
            severity: "warning",
            allowedDecisions: ["allow-once", "deny"],
            timeoutMs: 5 * 60 * 1000,
            pluginId: "jorah-guard",
          },
        };
      } catch (error) {
        log({ session: ctx?.sessionKey ?? null, agent: ctx?.agentId ?? null, tool, verdict: "block", reason: `guard error: ${error?.message ?? error}` });
        return { block: true, blockReason: "jorah-guard: the guard couldn't check this call, so it is blocked." };
      }
    }, { priority: PRIORITY });

    // Collect URLs from results (G-S2) and link spawned children to their parent session.
    api.on("after_tool_call", (event, ctx) => {
      try {
        const key = ctx?.sessionKey;
        const urls = urlsIn(event?.result).map(normalise).filter(Boolean);
        state.addSeen(key, urls);
        const child = event?.result?.details?.childSessionKey;
        if (event?.toolName === "sessions_spawn" && typeof child === "string") state.linkChild(child, key);
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
        // Only Adam's own typed turns count; voice, the Control UI, children and unknown senders don't.
        const r = ctx?.requester;
        if (!(r?.senderIsOwner === true && r?.channel !== "webchat")) { state.setWords(key, ""); return undefined; }
        const prompt = typeof event?.prompt === "string" ? event.prompt : strings(event?.prompt).join("\n");
        state.setWords(key, prompt);
        state.addSeen(key, findUrls(prompt).map(normalise).filter(Boolean));
      } catch (e) {
        api.logger.warn(`jorah-guard: before_agent_run: ${e?.message}`);
      }
      return undefined;
    });

    // Telegram replies only (G-S3): in a chat that has read outside text, strip links nobody gave.
    api.on("message_sending", (event, ctx) => {
      try {
        const key = ctx?.sessionKey;
        // Delivery hooks carry no requester, so use the recorded taint; an unknown chat counts as tainted.
        const tainted = !key || state.taintOf(key)?.tainted === true;
        if (!tainted || typeof event?.content !== "string") return undefined;
        let changed = false;
        const content = event.content.replace(/\bhttps?:[^\s"'<>`\\]+/gi, (raw) => {
          const n = normalise(raw.replace(/[),.;:!?\]}>]+$/, ""));
          const ok = n && ((key ? state.hasSeen(key, n) : state.anySeen(n)) || onSiteAllowlist(n, matrix?.siteAllowlist ?? []));
          if (ok) return raw;
          changed = true;
          return REMOVED;
        });
        if (changed) log({ session: key ?? null, tool: "message_sending", verdict: "rewrite", reason: "unseen link removed" });
        return changed ? { content } : undefined;
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
        if (ctx?.senderIsOwner !== true) return { text: "Only Adam can freeze Jorah." };
        state.freeze(ctx?.channel ?? "command");
        log({ session: ctx?.sessionKey ?? null, tool: "/jorah-freeze", verdict: "freeze" });
        return { text: "Frozen. Jorah can still read and answer, nothing more. Clear it at a terminal with scripts/pc/guard-unfreeze.sh." };
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
            t?.tainted ? `This chat has read outside text: ${t.source}.` : "This chat hasn't read outside text.",
            matrix ? "Permission list: loaded." : "Permission list: UNREADABLE, so every tool is blocked.",
          ].join("\n"),
        };
      },
    });

    api.logger.info(`jorah-guard: ${matrix ? "matrix loaded" : "MATRIX UNREADABLE, blocking everything"}; state ${state.broken ? `BROKEN (${state.broken})` : "ok"}`);
  },
};
