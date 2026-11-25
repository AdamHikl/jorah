// jorah-guard and the proactive layer (docs/runbooks/proactive.md). The model is hijacked: in a run
// Adam didn't start it tries to message Adam (or anyone) directly, drain the outbox from the wrong
// place, and save loops without a card. Pass means the guard decides as the matrix says.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { classify, decide, proactiveRun } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";
import plugin from "../index.js";

const here = dirname(fileURLToPath(import.meta.url));
const MATRIX_FILE = join(here, "..", "..", "..", "config", "permission-matrix.json");
const PROACTIVE_MANIFEST = join(here, "..", "..", "jorah-proactive", "openclaw.plugin.json");
const matrix = JSON.parse(readFileSync(MATRIX_FILE, "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };

const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const HEARTBEAT = { agentId: "main", sessionKey: "agent:main:main" }; // same key as Adam's chat, no requester
const CRON = { agentId: "main", sessionKey: "agent:main:cron:job-123" };
const HOOK = { agentId: "main", sessionKey: "agent:main:hook:abc" };
const SEND = { action: "send", channel: "telegram", target: "123456", message: "Morning. 2 loops due today." };

function fresh() {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-pro-"));
  const state = new GuardState(dir);
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(), parentOf: (k) => state.parentOf(k),
  };
  const run = (tool, params, ctx = ADAM, trigger = "user") => {
    const d = decide({ tool, params, ctx, matrix, view, settings, run: { trigger } });
    if (d.taint && d.verdict !== "block") state.markTainted(ctx.sessionKey, d.taint);
    return d;
  };
  return { dir, state, run };
}

test("proactive runs: told apart by the run's trigger, the session key, a parent, or a missing requester", () => {
  const is = (ctx, trigger) => proactiveRun({ ctx, run: { trigger }, matrix }).proactive;
  assert.equal(is(HEARTBEAT, "heartbeat"), true);
  assert.equal(is({ ...ADAM }, "cron"), true);
  assert.equal(is(CRON, null), true);
  assert.equal(is(HOOK, "user"), true);
  assert.equal(is({ agentId: "main", sessionKey: "agent:main:proactive:brief:x" }, "user"), true);
  assert.equal(is({ agentId: "main", sessionKey: "hook:gmail:1" }, null), true); // a bare key, no agent prefix
  assert.equal(is(HEARTBEAT, null), true); // main, no requester, no trigger: can't be shown to be Adam's
  assert.equal(is(ADAM, "user"), false);
  assert.equal(is({ agentId: "main", sessionKey: "agent:main:voice-1", requester: { channel: "voice", senderIsOwner: true } }, "user"), false);
  assert.equal(is({ agentId: "main", sessionKey: "agent:main:main", requester: { senderIsOwner: true } }, null), false); // the PC's CLI
  // A child spawned from a cron session inherits it.
  const parents = { "agent:background:subagent:k": "agent:main:cron:job-9" };
  assert.equal(proactiveRun({ ctx: { agentId: "background", sessionKey: "agent:background:subagent:k" }, run: {}, matrix, parentOf: (k) => parents[k] ?? null }).proactive, true);
  assert.equal(proactiveRun({ ctx: { agentId: "background", sessionKey: "agent:background:subagent:z" }, run: { trigger: "user" }, matrix }).proactive, false);
});

test("message: blocked in heartbeat, cron and hook runs, to Adam or anyone, also through the search wrapper", () => {
  const { run } = fresh();
  for (const [ctx, trigger] of [[HEARTBEAT, "heartbeat"], [CRON, "cron"], [HOOK, null], [HEARTBEAT, null]]) {
    for (const params of [SEND, { action: "send", message: "hi" }, { action: "send", target: "@someone_else", message: "x" }]) {
      const d = run("message", params, ctx, trigger);
      assert.equal(d.verdict, "block", `${ctx.sessionKey} ${trigger}`);
      assert.match(d.reason, /proactive_notify/);
    }
    assert.equal(run("tool_call", { id: "openclaw:core:message", args: SEND }, ctx, trigger).verdict, "block");
  }
});

test("message: Adam's own runs keep today's rules (own chat allowed, another target a card)", () => {
  const { run } = fresh();
  assert.equal(run("message", { action: "send", message: "hi" }, ADAM, "user").verdict, "allow");
  assert.equal(run("message", SEND, ADAM, "user").verdict, "confirm");
});

test("proactive_notify: allowed in a scheduled run that has read outside text, blocked when frozen", () => {
  const { run, state } = fresh();
  run("web_search", { query: "weather Bratislava" }, CRON, "cron");
  assert.equal(state.taintOf(CRON.sessionKey).tainted, true);
  assert.equal(run("proactive_notify", { type: "morning_brief", class: "digest" }, CRON, "cron").verdict, "allow");
  assert.equal(run("proactive_feedback", { record: "P3", reaction: "stop" }, ADAM).verdict, "allow");
  state.freeze("test");
  assert.equal(run("proactive_notify", { type: "morning_brief", class: "digest" }, CRON, "cron").verdict, "block");
  assert.equal(run("today_picture", {}, CRON, "cron").verdict, "allow"); // reads still work when frozen
});

test("loop_propose and proactive_resume: a card with the exact fields unless they are Adam's own typed words", () => {
  const { run } = fresh();
  const loop = { kind: "i_promised", who: "Jana", what: "Send the photos from Saturday", due: "2026-11-18" };
  const d = run("loop_propose", loop, ADAM);
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to note an open loop");
  for (const line of ["due: 2026-11-18", "kind: i_promised", "what: Send the photos from Saturday", "who: Jana"]) assert.ok(d.description.includes(line), line);
  assert.ok(!/outside text/.test(d.description));
  const tainted = run("loop_propose", loop, CRON, "cron");
  assert.equal(tainted.verdict, "confirm");
  assert.match(tainted.description, /outside text/);
  assert.equal(run("proactive_resume", { type: "home_loops" }, ADAM).verdict, "confirm");
});

test("loop_done and loop_drop: free in Adam's clean chat, a card after outside text or by voice", () => {
  const { run } = fresh();
  assert.equal(run("loop_done", { id: "L3" }, ADAM).verdict, "allow");
  assert.equal(run("loop_drop", { id: "L3" }, ADAM).verdict, "allow");
  run("web_fetch", { url: "https://news.example/a" }, ADAM);
  const d = run("loop_drop", { id: "L3" }, ADAM);
  assert.equal(d.verdict, "confirm");
  assert.match(d.description, /id: L3/);
  const voice = { agentId: "main", sessionKey: "agent:main:voice-2", requester: { channel: "voice", senderIsOwner: true } };
  assert.equal(run("loop_done", { id: "L3" }, voice).verdict, "confirm");
});

test("proactive_tick: only in a cron session, never from a chat, a hook or a heartbeat", () => {
  const { run } = fresh();
  assert.equal(run("proactive_tick", {}, CRON, null).verdict, "allow");
  for (const [ctx, trigger] of [[ADAM, "user"], [HOOK, null], [HEARTBEAT, "heartbeat"], [{ agentId: "main", sessionKey: "cron-ish:1" }, "cron"]]) {
    assert.equal(run("proactive_tick", {}, ctx, trigger).verdict, "block", ctx.sessionKey);
  }
});

test("matrix: every jorah-proactive tool has a class, and phone_today is a read", () => {
  const tools = JSON.parse(readFileSync(PROACTIVE_MANIFEST, "utf8")).contracts.tools;
  assert.equal(tools.length, 12);
  for (const t of tools) assert.notEqual(classify(matrix, t), null, t);
  for (const t of ["today_picture", "loops_list", "proactive_why", "digest_list", "proactive_due", "phone_today"]) assert.equal(classify(matrix, t), "read", t);
  assert.equal(classify(matrix, "loop_propose"), "ownWordsWrite");
  assert.equal(classify(matrix, "proactive_tick"), "cronOnly");
});

function loadPlugin() {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-pro-plugin-"));
  const hooks = {};
  plugin.register({
    pluginConfig: { stateDir: dir, matrixFile: MATRIX_FILE, workspace: settings.workspace },
    logger: { info() {}, warn() {} },
    on: (name, fn, opts) => { (hooks[name] ??= []).push({ fn, opts }); },
    registerCommand() {},
  });
  return { dir, call: (name, ev, ctx) => hooks[name][0].fn(ev, ctx) };
}

test("plugin: the trigger from before_agent_run reaches the tool call by run id, and is logged without arguments", () => {
  const p = loadPlugin();
  p.call("before_agent_run", { prompt: "[OpenClaw heartbeat poll]" }, { ...HEARTBEAT, runId: "run-hb", trigger: "heartbeat", sessionId: "s1" });
  const blocked = p.call("before_tool_call", { toolName: "message", params: SEND }, { ...HEARTBEAT, runId: "run-hb", sessionId: "s1" });
  assert.equal(blocked.block, true);
  assert.match(blocked.blockReason, /heartbeat run/);
  // Adam's own turn in the same session, a different run: today's rule.
  p.call("before_agent_run", { prompt: "say hi in this chat" }, { ...ADAM, runId: "run-adam", trigger: "user", sessionId: "s1" });
  assert.equal(p.call("before_tool_call", { toolName: "message", params: { action: "send", message: "hi" } }, { ...ADAM, runId: "run-adam", sessionId: "s1" }), undefined);
  const log = readFileSync(join(p.dir, "decisions.jsonl"), "utf8");
  assert.match(log, /"trigger":"heartbeat"/);
  assert.ok(!log.includes("loops due today"));
});

test("plugin: a cron job's message is blocked even if its run's trigger was never seen", () => {
  const p = loadPlugin();
  const d = p.call("before_tool_call", { toolName: "message", params: SEND }, { ...CRON, runId: "unknown-run" });
  assert.equal(d.block, true);
  assert.match(d.blockReason, /cron session/);
});
