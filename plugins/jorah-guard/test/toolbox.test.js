// jorah-guard and Jorah's toolbox (docs/runbooks/toolbox.md). Web text has talked Jorah into
// installing something: the install is always a card with the exact fields, whoever asks and
// however clean the chat; the full list marks the chat, the default list doesn't (review fix 6);
// proposing is inert and free.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { classify, cleanView, decide, viewBackstop } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";

const here = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(here, "..", "..", "..", "config", "permission-matrix.json"), "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };
const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const VOICE = { agentId: "main", sessionKey: "agent:main:voice-1", requester: { channel: "voice", senderIsOwner: true } };
const CARD = {
  id: "tb-0123456789", name: "orca-slicer", version: "2.3.1",
  source: "https://github.com/SoftFever/OrcaSlicer/releases/download/v2.3.1/OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.3.1.AppImage",
  sha256: "1111111111111111", licence: "AGPL-3.0-only", released: "2026-09-01", size: "120 MB download, 400 MB installed",
};

function fresh() {
  const state = new GuardState(mkdtempSync(join(tmpdir(), "jorah-guard-toolbox-")));
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(), parentOf: (k) => state.parentOf(k),
  };
  const run = (tool, params, ctx = ADAM) => {
    const d = decide({ tool, params, ctx, matrix, view, settings, run: { trigger: "user" } });
    if (d.taint && d.verdict !== "block") state.markTainted(ctx.sessionKey, d.taint);
    return d;
  };
  return { state, run };
}

test("matrix: the toolbox tools' classes", () => {
  assert.equal(classify(matrix, "toolbox_list"), "viewRead");
  assert.ok(!matrix.taintRead.includes("toolbox_list"));
  assert.equal(classify(matrix, "toolbox_propose"), "read");
  assert.equal(classify(matrix, "toolbox_install"), "confirmAlways");
  assert.equal(classify(matrix, "toolbox_remove"), "confirmAlways");
  for (const t of ["toolbox_install", "toolbox_remove"]) assert.ok(matrix.cardTitles[t], t);
});

test("an install is a card with every field in full, even in Adam's clean typed chat", () => {
  const { run } = fresh();
  const d = run("toolbox_install", CARD);
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to install a tool (runs offline, read-only to him)");
  for (const [k, v] of Object.entries(CARD)) assert.ok(d.description.includes(`${k}: ${v}`), `${k} shown in full`);
  assert.ok(!d.description.endsWith("…"));
});

test("after the web or by voice the card says why, and still shows the source in full", () => {
  const { run } = fresh();
  run("web_search", { query: "best headless slicer" });
  assert.equal(run("toolbox_list", { view: "full" }).verdict, "allow");
  const d = run("toolbox_install", CARD);
  assert.equal(d.verdict, "confirm");
  assert.match(d.description, /This chat has read outside text/);
  assert.ok(d.description.includes(`source: ${CARD.source}`));
  assert.equal(run("toolbox_install", CARD, VOICE).verdict, "confirm");
  assert.equal(run("toolbox_remove", { name: "uv", version: "0.9.18" }).verdict, "confirm");
});

test("the full list marks the chat; proposing doesn't need a card", () => {
  const { state, run } = fresh();
  assert.equal(run("toolbox_propose", { manifest: { name: "uv" } }).verdict, "allow");
  assert.equal(state.taintOf(ADAM.sessionKey), null);
  run("toolbox_list", { view: "full" });
  assert.match(state.taintOf(ADAM.sessionKey).source, /^toolbox_list \(view: full\)/);
});

// Review fix 6: a turn that starts with toolbox_list, project_list and supply_list leaves Adam's
// chat clean, so a memory save from his own words still needs no card.
test("the default list is a read, decided before the call: the chat stays clean", () => {
  const { state, run } = fresh();
  for (const params of [{}, { view: "installed" }]) {
    const d = run("toolbox_list", params);
    assert.equal(d.verdict, "allow");
    assert.equal(d.taint, undefined);
  }
  run("project_list", {});
  run("supply_list", {});
  assert.equal(state.taintOf(ADAM.sessionKey), null);
  assert.equal(run("agentmemory__memory_save", { content: "x" }).verdict, "allow", "a clean chat saves without a card");
});

test("anything but the default view marks the chat before the call runs", () => {
  assert.equal(cleanView(undefined), true);
  assert.equal(cleanView({}), true);
  assert.equal(cleanView({ view: "installed" }), true);
  for (const params of [{ view: "full" }, { view: "Installed" }, { view: ["installed"] }, { view: null }, { view: "installed", extra: 1 }, { detail: true }]) {
    assert.equal(cleanView(params), false, JSON.stringify(params));
    const { state, run } = fresh();
    assert.equal(run("toolbox_list", params).verdict, "allow");
    assert.ok(state.taintOf(ADAM.sessionKey)?.tainted, `${JSON.stringify(params)} marks the chat`);
  }
});

test("frozen: the default list still reads, the full list doesn't", () => {
  const { state, run } = fresh();
  state.freeze("test");
  assert.equal(run("toolbox_list", {}).verdict, "allow");
  assert.equal(run("toolbox_list", { view: "full" }).verdict, "block");
});

test("backstop: a clean-view call whose result isn't the clean view marks the chat afterwards", () => {
  const ok = { details: { status: "ok", view: "installed", installed: [] } };
  assert.equal(viewBackstop({ tool: "toolbox_list", params: {}, result: ok, matrix }), null);
  assert.equal(viewBackstop({ tool: "toolbox_list", params: {}, result: { details: { status: "unavailable", reason: "not installed" } }, matrix }), null);
  // An older plugin that ignores `view` returns the full list: mark.
  assert.match(viewBackstop({ tool: "toolbox_list", params: {}, result: { details: { status: "ok", installed: [], waiting_for_card: [{ purpose: "x" }] } }, matrix }), /wasn't the clean view/);
  assert.ok(viewBackstop({ tool: "toolbox_list", params: { view: "installed" }, result: { details: { status: "ok", view: "full" } }, matrix }));
  // An unreadable outcome counts as unknown, so it marks too.
  assert.ok(viewBackstop({ tool: "toolbox_list", params: {}, result: undefined, matrix }));
  assert.ok(viewBackstop({ tool: "toolbox_list", params: {}, result: ok, error: "boom", matrix }));
  assert.ok(viewBackstop({ tool: "toolbox_list", params: {}, result: { details: { status: "unavailable", reason: "x", waiting_for_card: [] } }, matrix }));
  // Not a clean-view call, or not a viewRead tool: nothing to do (the full view was marked before it ran).
  assert.equal(viewBackstop({ tool: "toolbox_list", params: { view: "full" }, result: undefined, matrix }), null);
  assert.equal(viewBackstop({ tool: "project_list", params: {}, result: undefined, matrix }), null);
});

test("backstop through the plugin's after_tool_call hook", async () => {
  const { default: plugin } = await import("../index.js");
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-toolbox-hook-"));
  const hooks = {};
  plugin.register({
    pluginConfig: { stateDir: dir, matrixFile: join(here, "..", "..", "..", "config", "permission-matrix.json"), sitesDir: join(dir, "none"), sitesPrivateFile: join(dir, "none.json") },
    logger: { info: () => {}, warn: () => {} },
    on: (name, fn) => { hooks[name] = fn; },
    registerCommand: () => {},
  });
  const ctx = { ...ADAM, runId: "r1", toolCallId: "c1" };
  hooks.before_agent_run({ prompt: "what's in your toolbox?" }, { ...ctx, trigger: "user" });
  assert.equal(hooks.before_tool_call({ toolName: "toolbox_list", params: {}, toolCallId: "c1" }, ctx), undefined);
  hooks.after_tool_call({ toolName: "toolbox_list", params: {}, toolCallId: "c1", result: { details: { status: "ok", view: "installed", installed: [] } } }, ctx);
  const t = new GuardState(dir).taintOf(ADAM.sessionKey);
  assert.ok(!t?.tainted, "the clean view leaves the chat clean");
  hooks.before_tool_call({ toolName: "toolbox_list", params: {}, toolCallId: "c2" }, { ...ctx, toolCallId: "c2" });
  hooks.after_tool_call({ toolName: "toolbox_list", params: {}, toolCallId: "c2", result: { details: { status: "ok", installed: [], waiting_for_card: [] } } }, { ...ctx, toolCallId: "c2" });
  assert.match(new GuardState(dir).taintOf(ADAM.sessionKey).source, /wasn't the clean view/);
  const rows = readFileSync(join(dir, "decisions.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
  assert.ok(rows.some((r) => r.verdict === "late-mark" && r.tool === "toolbox_list"));
});

test("frozen: nothing installs or is removed", () => {
  const { state, run } = fresh();
  state.freeze("test");
  assert.ok(state.frozen());
  assert.equal(run("toolbox_install", CARD).verdict, "block");
  assert.equal(run("toolbox_remove", { name: "uv", version: "1" }).verdict, "block");
});
