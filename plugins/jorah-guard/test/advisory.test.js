// GHSA-pw3x-g8v8-fvj2: the built-in `openclaw` tool can apply config changes without approval in a
// Full Access run. It is named as blocked in the matrix, so it never rests on "unknown tool".

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";

const here = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(here, "..", "..", "..", "config", "permission-matrix.json"), "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };
const TELEGRAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };

function run(tool, params, ctx = TELEGRAM) {
  const state = new GuardState(mkdtempSync(join(tmpdir(), "jorah-guard-")));
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(),
  };
  return decide({ tool, params, ctx, matrix, view, settings });
}

test("the openclaw tool is blocked by name, even in Adam's clean typed chat", () => {
  assert.ok(matrix.blocked.includes("openclaw"));
  const d = run("openclaw", { action: "config_set", path: "tools.elevated.enabled", value: true });
  assert.equal(d.verdict, "block");
  assert.match(d.reason, /openclaw is not allowed/);
});

test("the openclaw tool is blocked through the search wrapper, namespaced or not", () => {
  for (const id of ["openclaw", "openclaw:core:openclaw"]) {
    const d = run("tool_call", { id, args: { action: "config_set" } });
    assert.equal(d.verdict, "block");
    assert.match(d.reason, /openclaw is not allowed/);
  }
});

test("the openclaw tool is blocked for background and deep too", () => {
  for (const agentId of ["background", "deep"]) {
    const d = run("openclaw", { action: "plugin_install" }, { agentId, sessionKey: `agent:${agentId}:main`, requester: { senderIsOwner: false } });
    assert.equal(d.verdict, "block");
  }
});
