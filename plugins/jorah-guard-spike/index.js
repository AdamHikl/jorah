// P5 spikes G-S1 to G-S5 (docs/plan/p5-plan.md section 5), for the jorah-dev scratch profile only.
// Records what each hook sees, as JSONL. It never blocks and never changes anything. Values of
// arguments, results and messages are left out unless logValues is on; then only short ones.

import { appendFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { homedir } from "node:os";

const URL_RE = /https?:\/\/[^\s"'<>)\]]+/g;

// Shape of a value without its content: type, keys or length.
export function shape(value, depth = 0) {
  if (value === null || value === undefined) return value === null ? "null" : "undefined";
  if (Array.isArray(value)) return depth > 1 ? `array(${value.length})` : value.slice(0, 5).map((v) => shape(v, depth + 1));
  if (typeof value === "object") {
    if (depth > 1) return `object(${Object.keys(value).length})`;
    return Object.fromEntries(Object.keys(value).slice(0, 30).map((k) => [k, shape(value[k], depth + 1)]));
  }
  if (typeof value === "string") return `string(${value.length})`;
  return typeof value;
}

// Context fields that answer G-S1. Sender ids are reduced to "present", never the id.
export function context(ctx = {}) {
  const r = ctx.requester;
  return {
    keys: Object.keys(ctx),
    agentId: ctx.agentId,
    sessionKey: ctx.sessionKey,
    runId: ctx.runId ? "present" : undefined,
    toolCallId: typeof ctx.toolCallId === "string" ? ctx.toolCallId : undefined,
    messageProvider: ctx.messageProvider,
    channelId: ctx.channelId,
    toolKind: ctx.toolKind,
    toolInputKind: ctx.toolInputKind,
    requester: r
      ? { keys: Object.keys(r), channel: r.channel, accountId: r.accountId ? "present" : undefined, senderId: r.senderId ? "present" : undefined, senderIsOwner: r.senderIsOwner, roleIds: r.roleIds ? r.roleIds.length : undefined }
      : null,
    parent: ["requesterSessionKey", "parentSessionKey", "spawnedBy"].filter((k) => ctx[k] !== undefined).map((k) => [k, ctx[k]]),
  };
}

function textOf(value) {
  try { return typeof value === "string" ? value : JSON.stringify(value ?? ""); } catch { return ""; }
}

export function record(hook, event = {}, ctx = {}, logValues = false) {
  const out = { t: new Date().toISOString(), hook, ctx: context(ctx) };
  if (event.toolName !== undefined) out.toolName = event.toolName;
  if (event.toolKind !== undefined) out.toolKind = event.toolKind;
  if (event.derivedPaths !== undefined) out.derivedPaths = logValues ? event.derivedPaths : shape(event.derivedPaths);
  if (event.params !== undefined) {
    out.paramKeys = Object.keys(event.params ?? {});
    // tool_call wraps the real tool: name the inner one (G-S2, matrix lines).
    for (const k of ["name", "tool", "toolName", "action", "agentId", "runtime", "mode"]) {
      const v = event.params?.[k];
      if (typeof v === "string" && v.length <= 60) out[`param.${k}`] = v;
    }
    if (logValues) out.params = JSON.parse(textOf(event.params).slice(0, 2000) || "{}", (_k, v) => (typeof v === "string" ? v.slice(0, 200) : v));
  }
  if (hook === "after_tool_call") {
    const text = textOf(event.result);
    out.result = { present: event.result !== undefined, shape: shape(event.result), chars: text.length, urls: (text.match(URL_RE) ?? []).length };
    out.error = event.error ? "present" : undefined;
  }
  if (hook === "message_sending" || hook === "reply_payload_sending" || hook === "message_received") {
    out.eventShape = shape(event);
    const text = textOf(event.content ?? event.payload?.text ?? event.text ?? "");
    out.textChars = text.length;
    out.textUrls = (text.match(URL_RE) ?? []).length;
  }
  return out;
}

export default {
  id: "jorah-guard-spike",
  name: "Jorah guard spike",
  description: "Observation only: what OpenClaw's hooks see.",
  register(api) {
    const cfg = api.pluginConfig ?? {};
    const file = cfg.logFile ?? join(homedir(), ".openclaw-jorah-dev", "spike", "hooks.jsonl");
    mkdirSync(dirname(file), { recursive: true, mode: 0o700 });
    const write = (line) => {
      try { appendFileSync(file, JSON.stringify(line) + "\n", { mode: 0o600 }); } catch (e) { api.logger.warn(`guard-spike: ${e?.message}`); }
    };
    const watch = (hook, priority) =>
      api.on(hook, (event, ctx) => { write({ ...record(hook, event, ctx, cfg.logValues === true), priority }); return undefined; }, { priority });
    // G-S5: two before_tool_call handlers at different priorities, to see the order they run in.
    watch("before_tool_call", 100);
    watch("before_tool_call", -100);
    for (const hook of ["after_tool_call", "message_received", "message_sending", "reply_payload_sending"]) watch(hook, 0);
    api.logger.info(`guard-spike: recording to ${file}`);
  },
};
