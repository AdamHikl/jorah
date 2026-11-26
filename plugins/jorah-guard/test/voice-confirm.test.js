// jorah-guard severity and voice card first-line hint tests (ADR 0010).

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { cardSeverity, decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";
import plugin from "../index.js";

const here = dirname(fileURLToPath(import.meta.url));
const MATRIX_FILE = join(here, "..", "..", "..", "config", "permission-matrix.json");
const matrix = JSON.parse(readFileSync(MATRIX_FILE, "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };

const TELEGRAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const VOICE = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "voice", senderIsOwner: true } };

function fresh() {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-vc-"));
  const state = new GuardState(dir);
  const view = {
    taintOf: (k) => state.taintOf(k),
    hasSeen: (k, u) => state.hasSeen(k, u),
    wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k),
    countAcp: (k) => state.countAcp(k),
    frozen: () => state.frozen(),
    parentOf: (k) => state.parentOf(k),
  };
  const run = (tool, params, ctx = TELEGRAM) => {
    const d = decide({ tool, params, ctx, matrix, view, settings });
    if (d.taint && d.verdict !== "block") state.markTainted(ctx.sessionKey, d.taint);
    return d;
  };
  return { dir, state, run };
}

test("severity is critical for actions that leave the PC and warning otherwise", () => {
  assert.equal(cardSeverity("github", { project: "proj", branch: "jorah/x" }), "critical");
  assert.equal(cardSeverity("message", { to: "@someone", text: "hi" }), "critical");
  assert.equal(cardSeverity("schedule", { action: "add", job: { schedule: { kind: "every" }, message: "water plants" } }), "critical");
  assert.equal(cardSeverity("schedule", { action: "add", job: { schedule: { kind: "at" }, message: "fetch https://example.com" } }), "critical");
  assert.equal(cardSeverity("schedule", { action: "add", job: { schedule: { kind: "at" }, message: "water plants" } }), "warning");
  assert.equal(cardSeverity("memoryWrite", { content: "x" }), "warning");
  assert.equal(cardSeverity("spawn", { runtime: "acp", task: "x" }), "warning");

  const { run } = fresh();
  const msg = run("message", { action: "send", to: "@other", message: "hello" }, VOICE);
  assert.equal(msg.verdict, "confirm");
  assert.equal(msg.severity, "critical");

  const cronRec = run("automations", { action: "add", job: { schedule: { kind: "every" }, message: "stretch" } }, VOICE);
  assert.equal(cronRec.verdict, "confirm");
  assert.equal(cronRec.severity, "critical");

  const cronFetch = run("automations", { action: "add", job: { schedule: { kind: "at" }, message: "fetch news" } }, VOICE);
  assert.equal(cronFetch.verdict, "confirm");
  assert.equal(cronFetch.severity, "critical");

  const oneOff = run("automations", { action: "add", job: { schedule: { kind: "at" }, message: "water the plant" } }, VOICE);
  assert.equal(oneOff.verdict, "confirm");
  assert.equal(oneOff.severity, "warning");

  const mem = run("edit", { path: "MEMORY.md", edits: [{ newText: "plant needs water" }] }, VOICE);
  assert.equal(mem.verdict, "confirm");
  assert.equal(mem.severity, "warning");
});

test("voice cards start with the voice instruction line while non-voice cards do not", () => {
  const { run } = fresh();
  const memVoice = run("edit", { path: "MEMORY.md", edits: [{ newText: "plant needs water" }] }, VOICE);
  assert.equal(memVoice.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");
  assert.match(memVoice.description, /\nAsked by voice: confirm only if this was you\./);

  const msgVoice = run("message", { action: "send", to: "@other", message: "hello" }, VOICE);
  assert.equal(msgVoice.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");
  assert.match(msgVoice.description, /To: @other/);

  run("web_search", { query: "q" }, TELEGRAM);
  const memTg = run("edit", { path: "MEMORY.md", edits: [{ newText: "plant needs water" }] }, TELEGRAM);
  assert.equal(memTg.verdict, "confirm");
  assert.doesNotMatch(memTg.description, /Say 'yes, go ahead'/);
});

test("plugin sets requireApproval.severity from decide() and falls back fail-closed", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-sev-"));
  const hooks = {};
  plugin.register({
    pluginConfig: { stateDir: dir, matrixFile: MATRIX_FILE, workspace: settings.workspace },
    logger: { info() {}, warn() {} },
    on: (name, fn) => { (hooks[name] ??= []).push(fn); },
    registerCommand() {},
  });
  const call = (ev, ctx) => hooks.before_tool_call[0](ev, ctx);

  const local = call({ toolName: "edit", params: { path: "MEMORY.md", edits: [{ newText: "x" }] } }, VOICE);
  assert.equal(local.requireApproval.severity, "warning");
  assert.equal(local.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");

  const leaves = call({ toolName: "message", params: { action: "send", to: "@x", message: "hi" } }, VOICE);
  assert.equal(leaves.requireApproval.severity, "critical");
  assert.equal(leaves.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");
});

test("webchat spoken marker gives voice wording without leaking to next run, voice stays voice, telegram unchanged", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-spoken-"));
  const hooks = {};
  plugin.register({
    pluginConfig: { stateDir: dir, matrixFile: MATRIX_FILE, workspace: settings.workspace },
    logger: { info() {}, warn() {} },
    on: (name, fn) => { (hooks[name] ??= []).push(fn); },
    registerCommand() {},
  });
  const start = (ev, ctx) => hooks.before_agent_run[0](ev, ctx);
  const call = (ev, ctx) => hooks.before_tool_call[0](ev, ctx);

  const webchatBase = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "webchat", senderIsOwner: true } };
  const editMem = { toolName: "edit", params: { path: "MEMORY.md", edits: [{ newText: "plant needs water" }] } };

  // 1. webchat run starting with [Spoken turn. (by runId) gets voice wording.
  start({ prompt: "[Spoken turn.]\n\nRemember the plant needs water." }, { ...webchatBase, runId: "run-spoken" });
  const spokenCard = call(editMem, { ...webchatBase, runId: "run-spoken" });
  assert.equal(spokenCard.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");
  assert.match(spokenCard.requireApproval.description, /\nAsked by voice: confirm only if this was you\./);

  // Wrapped/missing-requester call in the same runId inherits both requester and voice wording.
  const wrapped = call(editMem, { agentId: "main", sessionKey: "agent:main:main", runId: "run-spoken" });
  assert.equal(wrapped.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");

  // Parts array with leading whitespace also counts as spoken.
  start({ prompt: [{ type: "text", text: "  [Spoken turn. Brief]\n\nSave this" }] }, { ...webchatBase, runId: "run-parts" });
  const partsCard = call(editMem, { ...webchatBase, runId: "run-parts" });
  assert.equal(partsCard.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");

  // 2. Next run in the same session without the marker is Adam typing in the HUD (ADR 0011,
  // 2026-11-26): his own words save without a card, and nothing leaks across runIds.
  start({ prompt: "Remember the plant needs water." }, { ...webchatBase, runId: "run-hud" });
  assert.equal(call(editMem, { ...webchatBase, runId: "run-hud" }), undefined);

  // 3. Keyed by sessionKey when runId is absent, and cleared on the next before_agent_run for that session.
  start({ prompt: "[Spoken turn.]\n\nSave this" }, webchatBase);
  const noRunSpoken = call(editMem, webchatBase);
  assert.equal(noRunSpoken.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");

  start({ prompt: "Typed in HUD without runId" }, webchatBase);
  const noRunHud = call(editMem, webchatBase);
  assert.doesNotMatch(noRunHud.requireApproval.description, /Say 'yes, go ahead'/);
  assert.match(noRunHud.requireApproval.description, /From the HUD or the web chat, but not known to be Adam's typing: confirm only if this was you\./);

  // 4. Legacy "voice" channel still counts as voice.
  const oldVoice = call(editMem, { ...VOICE, runId: "run-old-voice" });
  assert.equal(oldVoice.requireApproval.description.split("\n")[0], "Say 'yes, go ahead' or tap here.");
  assert.match(oldVoice.requireApproval.description, /\nAsked by voice: confirm only if this was you\./);

  // 5. Telegram is unchanged (even if prompt starts with [Spoken turn.): clean Telegram edit is allowed.
  start({ prompt: "[Spoken turn.]\n\nRemember that the plant needs water." }, { ...TELEGRAM, sessionKey: "agent:main:main", runId: "run-tg" });
  assert.equal(call(editMem, { ...TELEGRAM, sessionKey: "agent:main:main", runId: "run-tg" }), undefined);

  // Verify audit log recorded "voice" for the spoken webchat run and "hud-typed" for the HUD run.
  const entries = readFileSync(join(dir, "decisions.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
  assert.equal(entries[0].from, "voice");
  assert.equal(entries[0].channel, "webchat");
  assert.equal(entries[3].from, "hud-typed");
  assert.equal(entries[3].channel, "webchat");
});
