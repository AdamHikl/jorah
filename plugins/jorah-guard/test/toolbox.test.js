// jorah-guard and Jorah's toolbox (docs/runbooks/toolbox.md). Web text has talked Jorah into
// installing something: the install is always a card with the exact fields, whoever asks and
// however clean the chat; listing marks the chat; proposing is inert and free.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { classify, decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";

const here = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(here, "..", "..", "..", "config", "permission-matrix.json"), "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };
const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const VOICE = { agentId: "main", sessionKey: "agent:main:voice-1", requester: { channel: "webchat", senderIsOwner: true } };
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
  assert.equal(classify(matrix, "toolbox_list"), "taintRead");
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
  assert.equal(run("toolbox_list", {}).verdict, "allow");
  const d = run("toolbox_install", CARD);
  assert.equal(d.verdict, "confirm");
  assert.match(d.description, /This chat has read outside text/);
  assert.ok(d.description.includes(`source: ${CARD.source}`));
  assert.equal(run("toolbox_install", CARD, VOICE).verdict, "confirm");
  assert.equal(run("toolbox_remove", { name: "uv", version: "0.9.18" }).verdict, "confirm");
});

test("listing marks the chat; proposing doesn't need a card", () => {
  const { state, run } = fresh();
  assert.equal(run("toolbox_propose", { manifest: { name: "uv" } }).verdict, "allow");
  assert.equal(state.taintOf(ADAM.sessionKey), null);
  run("toolbox_list", {});
  assert.ok(state.taintOf(ADAM.sessionKey));
});

test("frozen: nothing installs or is removed", () => {
  const { state, run } = fresh();
  state.freeze("test");
  assert.ok(state.frozen());
  assert.equal(run("toolbox_install", CARD).verdict, "block");
  assert.equal(run("toolbox_remove", { name: "uv", version: "1" }).verdict, "block");
});
