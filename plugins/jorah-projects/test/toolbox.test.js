// jorah-projects' toolbox tools against a stand-in /opt/jorah-toolbox and /var/lib/jorah-toolbox
// (docs/runbooks/toolbox.md). The JavaScript copy of jorah-tool-v1 is checked against the same
// examples as the Python checker, including the proposal digests both must compute alike.

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { register } from "../index.js";
import { canonical, cardFields, checkManifest, digest, proposalId } from "../lib/toolbox.js";

const here = dirname(fileURLToPath(import.meta.url));
const EXAMPLES = join(here, "..", "..", "..", "packages", "contracts", "toolbox", "examples");
const EXPECTED = JSON.parse(readFileSync(join(EXAMPLES, "expected.json"), "utf8"));
const NOW = new Date("2026-11-17T10:00:00Z");
const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const example = (kind, name) => JSON.parse(readFileSync(join(EXAMPLES, kind, name), "utf8"));

function fixture({ installed = true } = {}) {
  const root = mkdtempSync(join(tmpdir(), "jorah-toolbox-plugin-"));
  const opt = join(root, "opt");
  const v = join(root, "var");
  for (const d of [join(opt, "bin"), ...["proposals", "approved", "results", "tested"].map((x) => join(v, x))]) mkdirSync(d, { recursive: true });
  if (!installed) return { root, opt: join(root, "none"), var: join(root, "none") };
  return { root, opt, var: v };
}

function load(fx) {
  const tools = new Map();
  const hooks = {};
  register({
    pluginConfig: { registryFile: join(fx.root, "projects.json"), stateRoot: join(fx.root, "state"), workRoot: join(fx.root, "work"),
      guardStateDir: join(fx.root, "guard"), toolboxDir: fx.opt, toolboxVar: fx.var },
    logger: { info: () => {}, warn: () => {} },
    on: (name, fn) => { (hooks[name] ??= []).push(fn); },
    registerTool: (t) => tools.set(t.name, t),
  }, { now: () => NOW });
  let n = 0;
  return async (name, params = {}, ctx = ADAM) => {
    const id = `call-${++n}`;
    for (const h of hooks.before_tool_call ?? []) h({ toolName: name, params, toolCallId: id }, ctx);
    return JSON.parse((await tools.get(name).execute(id, params)).content[0].text);
  };
}

test("contract: the JavaScript copy agrees with the Python checker on every example", () => {
  for (const name of readdirSync(join(EXAMPLES, "good"))) {
    assert.deepEqual(checkManifest(example("good", name), EXPECTED.today), [], name);
    assert.equal(digest(example("good", name)), EXPECTED.digests[name], `${name}: the digest must match Python's`);
  }
  for (const [name, reason] of Object.entries(EXPECTED.bad)) {
    const problems = checkManifest(example("bad", name), EXPECTED.today);
    assert.ok(problems.some((p) => p.includes(reason)), `${name}: ${JSON.stringify(problems)}`);
  }
});

test("contract: canonical JSON is Python's sorted, spaceless form, non-ASCII kept", () => {
  assert.equal(canonical({ b: [1, "é"], a: { d: null, c: true } }), '{"a":{"c":true,"d":null},"b":[1,"é"]}');
  assert.match(proposalId(example("good", "uv.json")), /^tb-[0-9a-f]{10}$/);
});

test("toolbox_propose writes an inert proposal and returns the card's exact fields", async () => {
  const fx = fixture();
  const call = load(fx);
  const m = example("good", "orca-slicer.json");
  const r = await call("toolbox_propose", { manifest: m });
  assert.equal(r.status, "proposed");
  assert.deepEqual(r.card, cardFields(m, proposalId(m)));
  const saved = JSON.parse(readFileSync(join(fx.var, "proposals", `${r.id}.json`), "utf8"));
  assert.deepEqual(saved.manifest, m);
  assert.deepEqual(saved.from, { via: "telegram" });
  assert.deepEqual(readdirSync(join(fx.var, "approved")), [], "proposing approves nothing");
  assert.equal((await call("toolbox_propose", { manifest: m })).status, "already proposed");
});

test("toolbox_propose refuses a request that breaks the contract", async () => {
  const call = load(fixture());
  const r = await call("toolbox_propose", { manifest: example("bad", "network-needed.json") });
  assert.equal(r.status, "refused");
  assert.ok(r.problems.some((p) => p.startsWith("sandbox:")));
});

test("toolbox_install queues exactly the proposal Adam's card showed", async () => {
  const fx = fixture();
  const call = load(fx);
  const m = example("good", "uv.json");
  const { id, card } = await call("toolbox_propose", { manifest: m });

  const wrong = await call("toolbox_install", { ...card, source: "https://github.com/evil/uv/releases/download/0.9.18/uv.tar.gz" });
  assert.equal(wrong.status, "refused");
  assert.match(wrong.reason, /source/);
  assert.deepEqual(readdirSync(join(fx.var, "approved")), []);

  const r = await call("toolbox_install", card);
  assert.equal(r.status, "approved");
  const approval = JSON.parse(readFileSync(join(fx.var, "approved", `${id}.json`), "utf8"));
  assert.equal(approval.action, "install");
  assert.deepEqual(approval.manifest, m);
  assert.equal(approval.digest, EXPECTED.digests["uv.json"]);
  assert.equal(statSync(join(fx.var, "approved", `${id}.json`)).mode & 0o777, 0o644);
});

test("toolbox_install refuses a proposal edited after it was proposed", async () => {
  const fx = fixture();
  const call = load(fx);
  const { id, card } = await call("toolbox_propose", { manifest: example("good", "uv.json") });
  const path = join(fx.var, "proposals", `${id}.json`);
  const p = JSON.parse(readFileSync(path, "utf8"));
  p.manifest.url = "https://github.com/evil/uv/releases/download/0.9.18/x.tar.gz";
  writeFileSync(path, JSON.stringify(p));
  const r = await call("toolbox_install", card);
  assert.equal(r.status, "refused");
  assert.match(r.reason, /doesn't match its id/);
});

test("toolbox_install: an unknown id, and a toolbox that isn't installed", async () => {
  const fields = cardFields(example("good", "uv.json"), "tb-0123456789");
  assert.match((await load(fixture())("toolbox_install", fields)).reason, /no proposal tb-0123456789/);
  assert.equal((await load(fixture({ installed: false }))("toolbox_list")).status, "unavailable");
});

test("toolbox_list: installed tools with smoke test and learning, waiting proposals, root commands", async () => {
  const fx = fixture();
  const call = load(fx);
  writeFileSync(join(fx.opt, "installed.json"), JSON.stringify({ v: 1, tools: {
    uv: { id: "tb-aaaaaaaaaa", name: "uv", version: "0.9.18", kind: "archive", commands: ["uv", "uvx"], licence: "Apache-2.0 OR MIT", source: "https://x.example/uv" },
  } }));
  writeFileSync(join(fx.var, "tested", "uv.json"), JSON.stringify({ name: "uv", id: "tb-aaaaaaaaaa", ok: true, exit: 0, output: "uv 0.9.18", learn: { run: "r1", outcome: "ok", notes: true } }));
  const java = example("good", "java.json");
  const { id: javaId } = await call("toolbox_propose", { manifest: java });
  const { id: orcaId } = await call("toolbox_propose", { manifest: example("good", "orca-slicer.json") });
  writeFileSync(join(fx.var, "results", `${javaId}.json`), JSON.stringify({ id: javaId, name: "java", version: java.version, action: "install", status: "needs-root",
    at: "2026-11-17T10:00:00+00:00", rootCommand: `bash /opt/jorah/scripts/pc/toolbox-apt.sh ${javaId}` }));
  const r = await call("toolbox_list");
  assert.equal(r.status, "ok");
  assert.equal(r.installed[0].smoke_test.ok, true);
  assert.equal(r.installed[0].learning.notes, true);
  assert.equal(r.installed[0].notes, "~/work/.toolbox/notes/uv.md");
  assert.deepEqual(r.waiting_for_card.map((w) => w.id), [orcaId], "a request waiting on Adam's root command isn't waiting for a card");
  assert.equal(r.waiting_for_card[0].card.source, example("good", "orca-slicer.json").url);
  const root = r.recent_results.find((x) => x.id === javaId);
  assert.match(root.root_command, /toolbox-apt\.sh tb-/);
  assert.match(root.how, /wsl -d jorah -u root/);
});

test("toolbox_remove: always for an installed tool and version, into the installer's queue", async () => {
  const fx = fixture();
  const call = load(fx);
  writeFileSync(join(fx.opt, "installed.json"), JSON.stringify({ v: 1, tools: { uv: { id: "tb-aaaaaaaaaa", version: "0.9.18", kind: "archive" } } }));
  assert.match((await call("toolbox_remove", { name: "uv", version: "0.9.17" })).reason, /is version 0.9.18/);
  const r = await call("toolbox_remove", { name: "uv", version: "0.9.18" });
  assert.equal(r.status, "approved");
  const [file] = readdirSync(join(fx.var, "approved"));
  assert.match(file, /^rm-uv-[0-9a-f]{8}\.json$/);
  assert.equal(JSON.parse(readFileSync(join(fx.var, "approved", file), "utf8")).action, "remove");
  assert.ok(!existsSync(join(fx.var, "approved", "tb-aaaaaaaaaa.json")));
});
