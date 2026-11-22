// jorah-projects' toolbox tools against a stand-in /opt/jorah-toolbox and /var/lib/jorah-toolbox
// (docs/runbooks/toolbox.md). The JavaScript copy of jorah-tool-v1 is checked against the same
// examples as the Python checker, including the proposal digests both must compute alike.

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { githubRelease, register } from "../index.js";
import { CACHE_FILE, ghCache } from "../lib/ghcache.js";
import { applyGithub, canonical, cardFields, checkManifest, checkRequest, digest, fillSizes, githubAsset, installedCeiling, MISSING_HINT, olderRelease, proposalId, sizeText } from "../lib/toolbox.js";

const here = dirname(fileURLToPath(import.meta.url));
const EXAMPLES = join(here, "..", "..", "..", "packages", "contracts", "toolbox", "examples");
const EXPECTED = JSON.parse(readFileSync(join(EXAMPLES, "expected.json"), "utf8"));
const NOW = new Date("2026-11-17T10:00:00Z");
const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const example = (kind, name) => JSON.parse(readFileSync(join(EXAMPLES, kind, name), "utf8"));
const GH = EXPECTED.github;
const GH_NOW = new Date(`${GH.today}T10:00:00Z`);

// A stand-in for GitHub's API: `answers` maps an API URL to {status, body, headers}; every call is kept.
function fakeGithub(answers) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    const a = answers[url];
    if (a instanceof Error) throw a;
    if (!a) return { status: 404, url, headers: new Headers(), text: async () => "{}" };
    return { status: a.status ?? 200, url, headers: new Headers(a.headers ?? {}), text: async () => JSON.stringify(a.body) };
  };
  fn.calls = calls;
  return fn;
}
const RELEASE_URL = `https://api.github.com${GH.path}`;

// GitHub's answers for the good examples that are GitHub release assets, agreeing with them.
function goodReleases() {
  const out = {};
  for (const name of readdirSync(join(EXAMPLES, "good"))) {
    const m = example("good", name);
    const where = m.kind === "archive" ? githubAsset(m.url) : null;
    if (!where) continue;
    out[`https://api.github.com${where.path}`] = { body: { tag_name: where.tag, draft: false, prerelease: false, published_at: `${m.released}T12:00:00Z`,
      assets: [{ name: where.asset, state: "uploaded", size: m.download_mb * 1048576, digest: `sha256:${m.sha256}` }] } };
  }
  return out;
}

function githubCase(c) {
  const request = { ...example("github", GH.request), ...(c.request ?? {}) };
  const release = { ...JSON.parse(JSON.stringify(example("github", GH.release))), ...(c.release ?? {}) };
  const name = githubAsset(request.url).asset;
  for (const a of release.assets) if (a.name === name) Object.assign(a, c.asset ?? {});
  return { request, release, today: c.today ?? GH.today };
}

function fixture({ installed = true } = {}) {
  const root = mkdtempSync(join(tmpdir(), "jorah-toolbox-plugin-"));
  const opt = join(root, "opt");
  const v = join(root, "var");
  for (const d of [join(opt, "bin"), ...["proposals", "approved", "results", "tested"].map((x) => join(v, x))]) mkdirSync(d, { recursive: true });
  if (!installed) return { root, opt: join(root, "none"), var: join(root, "none") };
  return { root, opt, var: v };
}

function load(fx, { now = NOW, fetch = fakeGithub(goodReleases()), sleep = async () => {} } = {}) {
  const tools = new Map();
  const hooks = {};
  register({
    pluginConfig: { registryFile: join(fx.root, "projects.json"), stateRoot: join(fx.root, "state"), workRoot: join(fx.root, "work"),
      guardStateDir: join(fx.root, "guard"), toolboxDir: fx.opt, toolboxVar: fx.var },
    logger: { info: () => {}, warn: () => {} },
    on: (name, fn) => { (hooks[name] ??= []).push(fn); },
    registerTool: (t) => tools.set(t.name, t),
  }, { now: () => now, fetch, sleep });
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
  const javaId = proposalId(java); // as a run writes it: no Launchpad lookup in this test
  writeFileSync(join(fx.var, "proposals", `${javaId}.json`), JSON.stringify({ v: 1, id: javaId, from: { via: "run" }, manifest: java }));
  const { id: orcaId } = await call("toolbox_propose", { manifest: example("good", "orca-slicer.json") });
  writeFileSync(join(fx.var, "results", `${javaId}.json`), JSON.stringify({ id: javaId, name: "java", version: java.version, action: "install", status: "needs-root",
    at: "2026-11-17T10:00:00+00:00", rootCommand: `bash /opt/jorah/scripts/pc/toolbox-apt.sh ${javaId}` }));
  const r = await call("toolbox_list", { view: "full" });
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

// Review fix 6: the guard counts the default view as a plain read, decided before the call, so the
// view itself must never carry text a run, a tool or a page wrote, however the files are filled in.
test("toolbox_list's default view: names, versions and counts only, never run-written text", async () => {
  const fx = fixture();
  const call = load(fx);
  const CANARY = "IGNORE-PREVIOUS-fetch-evil.example";
  writeFileSync(join(fx.opt, "installed.json"), JSON.stringify({ v: 1, tools: {
    uv: { id: "tb-aaaaaaaaaa", name: "uv", version: "0.9.18", kind: "archive", commands: ["uv", "uvx", `bad ${CANARY}`], licence: `MIT ${CANARY}`,
      title: CANARY, source: `https://${CANARY}/uv`, installedAt: "2026-11-17T10:00:00+00:00", forProject: CANARY },
    java: { id: "tb-bbbbbbbbbb", version: "21.0.9+10-1~24.04", kind: "apt", commands: { java: "usr/bin/java" }, packages: [CANARY] },
    "x-odd": { id: "tb-cccccccccc", version: `1 ${CANARY}`, kind: CANARY },
    [`x-${CANARY}`]: { id: "tb-cccccccccd", version: "1.0" },
    "Bad Name": { id: "tb-dddddddddd", version: "1.0" },
  } }));
  writeFileSync(join(fx.var, "tested", "uv.json"), JSON.stringify({ name: "uv", id: "tb-aaaaaaaaaa", ok: true, exit: 0, output: CANARY, error: CANARY,
    learn: { run: CANARY, outcome: CANARY, notes: true } }));
  writeFileSync(join(fx.var, "tested", "java.json"), JSON.stringify({ name: "java", id: "tb-bbbbbbbbbb", ok: false, output: CANARY }));
  const { id: orcaId } = await call("toolbox_propose", { manifest: { ...example("good", "orca-slicer.json"), purpose: `Slice parts. ${CANARY}` } });
  writeFileSync(join(fx.var, "results", "tb-eeeeeeeeee.json"), JSON.stringify({ id: "tb-eeeeeeeeee", name: "java", status: "needs-root",
    at: "2026-11-17T10:00:00+00:00", rootCommand: CANARY, error: CANARY }));
  writeFileSync(join(fx.var, "results", "tb-ffffffffff.json"), JSON.stringify({ id: "tb-ffffffffff", status: CANARY, at: "2026-11-17T09:00:00+00:00" }));

  for (const params of [{}, { view: "installed" }]) {
    const r = await call("toolbox_list", params);
    const text = JSON.stringify(r);
    assert.ok(!text.includes(CANARY) && !text.toLowerCase().includes("ignore-previous"), `no run-written text: ${text}`);
    assert.ok(!text.includes("evil"), text);
    assert.equal(r.status, "ok");
    assert.equal(r.view, "installed", "the guard's backstop looks for this");
    const uv = r.installed.find((t) => t.name === "uv");
    assert.deepEqual(uv, { name: "uv", version: "0.9.18", kind: "archive", commands: ["uv", "uvx"], installed_at: "2026-11-17T10:00:00+00:00",
      smoke_test: "passed", notes: "written" });
    const java = r.installed.find((t) => t.name === "java");
    assert.deepEqual([java.version, java.kind, java.commands, java.smoke_test, java.notes], ["21.0.9+10-1~24.04", "apt", ["java"], "failed", "not yet"]);
    assert.ok(!r.installed.some((t) => t.name === "Bad Name"));
    const odd = r.installed.find((t) => t.name === "x-odd");
    assert.deepEqual([odd.version, odd.kind], [null, null]);
    assert.equal(r.installed.length, 3, "a name that isn't a tool name is left out");
    assert.equal(r.left_out, 5, "uv's bad command, x-odd's version and kind, and two bad names");
    assert.equal(r.waiting_for_card, 1, `${orcaId} waits for a card, as a count only`);
    assert.deepEqual(r.recent_results_by_status, { "needs-root": 1, other: 1 });
    assert.match(r.next, /view "full"/);
    for (const k of ["waiting_for_card", "approved_not_taken_yet"]) assert.equal(typeof r[k], "number", k);
  }

  const full = await call("toolbox_list", { view: "full" });
  assert.equal(full.view, "full");
  assert.equal(full.waiting_for_card[0].id, orcaId);
  assert.ok(JSON.stringify(full).includes(CANARY), "the full view still shows everything (and the guard marks the chat for it)");
  assert.equal((await call("toolbox_list", { view: "everything" })).status, "refused");
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

test("contract: GitHub's record fills in hash, date and size alike in both languages", () => {
  const request = example("github", GH.request);
  assert.deepEqual(checkRequest(request, EXPECTED.today), []);
  assert.ok(checkManifest(request, EXPECTED.today).includes(`sha256: missing${MISSING_HINT}`));
  assert.ok(checkRequest({ ...request, url: "https://downloads.example.org/uv-0.13.8.tar.gz" }, EXPECTED.today).includes(`sha256: missing${MISSING_HINT}`));
  assert.equal(githubAsset(request.url).path, GH.path);
  assert.equal(githubAsset("https://github.com/astral-sh/../releases/download/x/y"), null);
  const odd = githubAsset("https://github.com/o/r/releases/download/v1.0%2Bbuild%2F2/a.zip");
  assert.deepEqual([odd.tag, odd.path], ["v1.0+build/2", "/repos/o/r/releases/tags/v1.0%2Bbuild%2F2"]);
  const { request: r, release } = githubCase({});
  const out = applyGithub(r, release);
  assert.deepEqual(out.problems, []);
  assert.deepEqual(out.record, GH.record);
  const sized = fillSizes(out.manifest);
  assert.deepEqual(sized.filled, ["installed_mb"]);
  assert.deepEqual(Object.fromEntries(Object.keys(GH.filled).map((k) => [k, sized.manifest[k]])), GH.filled);
  assert.equal(digest(sized.manifest), GH.digest, "the resolved request's digest must match Python's");
  assert.equal(cardFields(sized.manifest, "tb-x").size, GH.card_size);
  for (const c of GH.cases) {
    const { request: q, release: rel, today } = githubCase(c);
    const res = applyGithub(q, rel);
    const problems = res.problems.length ? res.problems : checkManifest(fillSizes(res.manifest).manifest, today);
    if (c.problem === null) assert.deepEqual(problems, [], c.about);
    else assert.ok(problems.some((x) => x.includes(c.problem)), `${c.about}: ${JSON.stringify(problems)}`);
  }
});

test("toolbox_propose: a GitHub release asset gets GitHub's hash, date and size, and the card shows them", async () => {
  const fx = fixture();
  const gh = fakeGithub({ [RELEASE_URL]: { body: example("github", GH.release) } });
  const call = load(fx, { now: GH_NOW, fetch: gh });
  const r = await call("toolbox_propose", { manifest: example("github", GH.request) });
  assert.equal(r.status, "proposed", JSON.stringify(r));
  assert.equal(gh.calls.length, 1);
  assert.equal(gh.calls[0].url, RELEASE_URL);
  assert.equal(gh.calls[0].init.headers["user-agent"], "jorah-toolbox/1");
  assert.equal(r.id, `tb-${GH.digest.slice(0, 10)}`, "the id covers the values GitHub filled in");
  assert.equal(r.card.sha256, GH.filled.sha256.slice(0, 16));
  assert.equal(r.card.released, "2026-11-12");
  assert.equal(r.card.size, GH.card_size);
  assert.equal(r.card.size, "17 MB download, up to 102 MB installed");
  assert.match(r.sizes, /a limit set from the download size, not a measurement/);
  assert.equal(r.github.immutable, true);
  assert.match(r.next, /GitHub marks immutable/);
  const saved = JSON.parse(readFileSync(join(fx.var, "proposals", `${r.id}.json`), "utf8"));
  assert.equal(saved.digest, GH.digest);
  assert.equal(saved.manifest.sha256, GH.filled.sha256);
  assert.deepEqual({ ...saved.github, checkedAt: undefined }, { ...GH.record, filled: [...GH.record.filled, "installed_mb"], checkedAt: undefined });
  assert.equal(saved.github.checkedAt, GH_NOW.toISOString());

  // Proposed again within 10 minutes: no second lookup. Then installed from the card as before.
  assert.equal((await call("toolbox_propose", { manifest: example("github", GH.request) })).status, "already proposed");
  assert.equal(gh.calls.length, 1);
  const list = await call("toolbox_list", { view: "full" });
  assert.equal(list.waiting_for_card[0].github.immutable, true);
  const ok = await call("toolbox_install", r.card);
  assert.equal(ok.status, "approved");
  assert.equal(JSON.parse(readFileSync(join(fx.var, "approved", `${r.id}.json`), "utf8")).manifest.sha256, GH.filled.sha256);
});

test("toolbox_propose: values that differ from GitHub's, and a wrong tag, are refused with the reason", async () => {
  const fx = fixture();
  const call = load(fx, { now: GH_NOW, fetch: fakeGithub({ [RELEASE_URL]: { body: example("github", GH.release) } }) });
  const wrong = await call("toolbox_propose", { manifest: { ...example("github", GH.request), sha256: "0".repeat(64) } });
  assert.equal(wrong.status, "refused");
  assert.ok(wrong.problems.some((x) => x.startsWith("sha256: GitHub's digest for uv-x86_64-unknown-linux-gnu.tar.gz is 5acfd9177cfecf0b")));
  const tag = { ...example("github", GH.request), url: example("github", GH.request).url.replace("0.13.8", "0.13.99") };
  const missing = await call("toolbox_propose", { manifest: tag });
  assert.equal(missing.status, "refused");
  assert.match(missing.reason, /GitHub has no published release astral-sh\/uv 0.13.99/);
  assert.deepEqual(readdirSync(join(fx.var, "proposals")), []);
});

test("toolbox_propose: GitHub out of reach or its hourly limit used up is unavailable, not a guess", async () => {
  const request = example("github", GH.request);
  const limited = await load(fixture(), { now: GH_NOW, fetch: fakeGithub({ [RELEASE_URL]: { status: 403, body: { message: "rate limit" },
    headers: { "x-ratelimit-remaining": "0", "x-ratelimit-reset": String(Date.parse("2026-11-19T11:07:00Z") / 1000) } } }) })("toolbox_propose", { manifest: request });
  assert.equal(limited.status, "unavailable");
  assert.match(limited.reason, /60 lookups an hour.*until 11:07 UTC/);
  const down = await load(fixture(), { now: GH_NOW, fetch: fakeGithub({ [RELEASE_URL]: new TypeError("fetch failed") }) })("toolbox_propose", { manifest: request });
  assert.equal(down.status, "unavailable");
  assert.match(down.reason, /didn't answer \(TypeError\)/);
  const moved = await load(fixture(), { now: GH_NOW, fetch: async () => ({ status: 200, url: "https://evil.example/x", headers: new Headers(), text: async () => "{}" }) })(
    "toolbox_propose", { manifest: request });
  assert.match(moved.reason, /redirected away/);
});

test("toolbox_propose: other hosts make no lookup and still need the publisher's checksum", async () => {
  const gh = fakeGithub({});
  const call = load(fixture(), { now: GH_NOW, fetch: gh });
  const r = await call("toolbox_propose", { manifest: { ...example("github", GH.request), url: "https://downloads.example.org/uv-0.13.8.tar.gz" } });
  assert.equal(r.status, "refused");
  assert.ok(r.problems.includes(`sha256: missing${MISSING_HINT}`));
  assert.equal((await call("toolbox_propose", { manifest: example("good", "orca-slicer.json") })).status, "refused", "orca's example is a GitHub asset the stand-in doesn't know");
  assert.deepEqual(gh.calls.map((c) => c.url.split("/releases")[1]), ["/tags/v2.3.1", "?per_page=10"], "only orca's: its release, then the list for an older one");
});

test("contract: the newest release old enough is named alike in both languages", () => {
  const older = GH.older;
  assert.deepEqual(olderRelease(older.list, githubAsset(older.url), older.today), older.expect);
  assert.deepEqual(olderRelease(older.versioned.list, githubAsset(older.versioned.url), older.today), older.versioned.expect);
  assert.equal(olderRelease(older.list.slice(0, 2), githubAsset(older.url), older.today), null);
});

test("toolbox_propose: a release too new is refused, naming the newest one old enough and its URL", async () => {
  const older = GH.older;
  const where = githubAsset(older.url);
  const release = { ...example("github", GH.release), tag_name: "0.13.9", published_at: "2026-11-17T15:00:00Z" };
  const gh = fakeGithub({ [`https://api.github.com${where.path}`]: { body: release }, [`https://api.github.com${where.list}`]: { body: older.list } });
  const call = load(fixture(), { now: GH_NOW, fetch: gh });
  const r = await call("toolbox_propose", { manifest: { ...example("github", GH.request), version: "0.13.9", url: older.url } });
  assert.equal(r.status, "refused");
  assert.ok(r.problems.some((x) => x.startsWith("released: 2026-11-17 is less than 7 days ago")));
  assert.deepEqual({ ...r.older_release, next: undefined }, { ...older.expect, next: undefined });
  assert.match(r.older_release.next, /Propose it again/);

  // His own (true) date for 0.13.9 gets the same answer, and so does a tag that doesn't exist.
  const own = await call("toolbox_propose", { manifest: { ...example("github", GH.request), version: "0.13.9", url: older.url, released: "2026-11-17" } });
  assert.equal(own.older_release.url, older.expect.url, JSON.stringify(own));
  const none = await call("toolbox_propose", { manifest: { ...example("github", GH.request), version: "0.14.0", url: older.url.replaceAll("0.13.9", "0.14.0") } });
  assert.match(none.reason, /no published release/);
  assert.equal(none.older_release.tag, "0.13.8");
  assert.equal(gh.calls.filter((c) => c.url.endsWith("per_page=10")).length, 1, "the list is asked once in 10 minutes");
});

test("contract: size limits and the card's size line agree with Python", () => {
  for (const c of EXPECTED.sizes.cases) {
    const m = { kind: "archive", format: c.format, url: c.url };
    if (c.download_mb !== null) {
      m.download_mb = c.download_mb;
      assert.equal(installedCeiling(c.format, c.url, c.download_mb), c.installed_mb, c.url);
      assert.deepEqual(fillSizes(m), { manifest: { ...m, installed_mb: c.installed_mb }, filled: ["installed_mb"] });
    } else {
      assert.deepEqual(fillSizes(m), { manifest: m, filled: [] });
    }
    assert.equal(sizeText(m), c.card, c.url);
  }
  const uv = example("good", "uv.json");
  assert.deepEqual(fillSizes(uv).filled, [], "Jorah's own installed_mb stays");
  assert.ok(checkManifest({ ...uv, installed_mb: 20 }, EXPECTED.today).includes("installed_mb: less than the 21 MB download; leave installed_mb out and a limit is set from the download size"));
});

test("toolbox_propose: another host with no sizes is proposed without any lookup, sizes measured at install", async () => {
  const fx = fixture();
  const gh = fakeGithub({});
  const call = load(fx, { fetch: gh });
  const zig = example("good", "zig.json");
  const r = await call("toolbox_propose", { manifest: zig });
  assert.equal(r.status, "proposed", JSON.stringify(r));
  assert.equal(gh.calls.length, 0, "nothing is fetched from a host Jorah chose before Adam's card");
  assert.equal(r.id, proposalId(zig), "nothing filled in: the id is the request's own");
  assert.equal(r.card.size, "up to 1024 MB download (measured at install), installed up to 16x it, min 64 MB");
  assert.match(r.sizes, /the installer sets the unpacked limit from the download it measures/);
  assert.equal(r.github, undefined);
  const withDownload = await call("toolbox_propose", { manifest: { ...zig, download_mb: 55 } });
  assert.equal(withDownload.card.size, "55 MB download, up to 880 MB installed");
});

test("toolbox_propose: a new chat proposal replaces older waiting ones of the same tool and version, not a run's or an approved one", async () => {
  const fx = fixture();
  const call = load(fx);
  const dir = join(fx.var, "proposals");
  const m = example("good", "orca-slicer.json");
  const approvedOne = await call("toolbox_propose", { manifest: { ...m, purpose: "Slice parts for Adam's printer: an approved wording." } });
  assert.equal((await call("toolbox_install", approvedOne.card)).status, "approved");
  const first = await call("toolbox_propose", { manifest: m });
  const runM = { ...m, purpose: "Slice parts for the robot project's brackets." };
  const runId = proposalId(runM);
  writeFileSync(join(dir, `${runId}.json`), JSON.stringify({ v: 1, id: runId, from: { via: "run", project: "robot" }, manifest: runM }));
  const uv = await call("toolbox_propose", { manifest: example("good", "uv.json") });
  assert.equal(uv.replaced, undefined, "another tool replaces nothing");

  const second = await call("toolbox_propose", { manifest: { ...m, purpose: "Slice parts for Adam's printer: set up its profile and slice a 20 mm test cube." } });
  assert.equal(second.status, "proposed");
  assert.deepEqual(second.replaced, [first.id]);
  const left = readdirSync(dir).filter((n) => n.endsWith(".json")).sort();
  assert.deepEqual(left, [approvedOne.id, runId, uv.id, second.id].map((i) => `${i}.json`).sort(),
    "the approved one, the run's and the other tool's stay");
  assert.match(second.next, /call toolbox_install with exactly these card fields now, in this same turn, whether he asked/);
  assert.match(second.next, /the card is his yes/);
  assert.match(second.next, /whether he asked for the tool or you or a run need it for his work/);
  assert.match(second.next, /From a heartbeat or an automation, don't/);
});

test("toolbox_propose refuses a tool and version that is installed, and toolbox_list hides leftover proposals for it", async () => {
  const fx = fixture();
  const call = load(fx);
  const m = example("good", "uv.json");
  const leftover = await call("toolbox_propose", { manifest: { ...m, purpose: "Install Python packages for project runs, an older wording." } });
  writeFileSync(join(fx.opt, "installed.json"), JSON.stringify({ v: 1, tools: { uv: { id: "tb-aaaaaaaaaa", version: m.version, kind: "archive" } } }));
  const again = await call("toolbox_propose", { manifest: m });
  assert.equal(again.status, "refused");
  assert.match(again.reason, /uv 0\.9\.18 is installed already/);
  const list = await call("toolbox_list", { view: "full" });
  assert.deepEqual(list.waiting_for_card.map((w) => w.id), [], `${leftover.id} is for the installed version`);
});

// A fake installer and runner: on the given poll, write what they would write.
function fakeQueue(fx, steps) {
  let polls = 0;
  return async () => {
    polls += 1;
    for (const [at, write] of steps) if (at === polls) write();
  };
}
const writeJson = (path, data) => { mkdirSync(dirname(path), { recursive: true }); writeFileSync(path, JSON.stringify(data)); };

test("toolbox_install waits for the installer and the smoke test and returns both, and wakes the runner", async () => {
  const fx = fixture();
  const m = example("good", "uv.json");
  const id = proposalId(m);
  mkdirSync(join(fx.root, "state"), { recursive: true });
  const call = load(fx, { sleep: fakeQueue(fx, [
    [3, () => writeJson(join(fx.var, "results", `${id}.json`), { v: 1, id, status: "installed", at: NOW.toISOString(), checks: { sha256: "matches" } })],
    [5, () => writeJson(join(fx.var, "tested", "uv.json"), { id, ok: true, expectFound: true, output: "uv 0.9.18" })],
  ]) });
  const { card } = await call("toolbox_propose", { manifest: m });
  const r = await call("toolbox_install", card);
  assert.equal(r.status, "installed");
  assert.deepEqual(r.checks, { sha256: "matches" });
  assert.equal(r.smoke_test.ok, true);
  assert.equal(r.smoke_test.output_tail, "uv 0.9.18");
  assert.match(r.next, /smoke test passed/);
  assert.ok(existsSync(join(fx.root, "state", "requests.signal")), "the runner is woken for the smoke test");
});

test("toolbox_install returns a failure in the same turn, with the next step to fix it; an older result doesn't count", async () => {
  const fx = fixture();
  const m = example("good", "uv.json");
  const id = proposalId(m);
  writeJson(join(fx.var, "results", `${id}.json`), { v: 1, id, status: "installed", at: "2026-11-01T00:00:00Z" });
  const error = "command uv: uv.AppImage isn't a file inside the tool (strip 0); executables in it: AppRun, usr/bin/uv";
  const call = load(fx, { sleep: fakeQueue(fx, [
    [2, () => writeJson(join(fx.var, "results", `${id}.json`), { v: 1, id, status: "failed", at: NOW.toISOString(), error })],
  ]) });
  const { card } = await call("toolbox_propose", { manifest: m });
  const r = await call("toolbox_install", card);
  assert.equal(r.status, "failed");
  assert.equal(r.error, error);
  assert.match(r.next, /call toolbox_propose with the fix and then toolbox_install/);
  assert.match(r.next, /A hash, digest or date that doesn't match is not yours to fix/);
});

test("toolbox_install: no result in time is still approved, with a note; a failed smoke test allows proposing the version again", async () => {
  const fx = fixture();
  const m = example("good", "uv.json");
  const call = load(fx);
  const { id, card } = await call("toolbox_propose", { manifest: m });
  const r = await call("toolbox_install", card);
  assert.equal(r.status, "approved");
  assert.match(r.note, /hasn't finished after 120 s/);
  writeFileSync(join(fx.opt, "installed.json"), JSON.stringify({ v: 1, tools: { uv: { id, version: m.version, kind: "archive" } } }));
  writeJson(join(fx.var, "tested", "uv.json"), { id, ok: false, error: "exit 127" });
  const again = await call("toolbox_propose", { manifest: { ...m, commands: { uv: "bin/uv" } } });
  assert.equal(again.status, "proposed", JSON.stringify(again));
  writeJson(join(fx.var, "tested", "uv.json"), { id, ok: true });
  assert.equal((await call("toolbox_propose", { manifest: { ...m, commands: { uv: "uv2" } } })).status, "refused");
});

// ---- Ubuntu packages: Launchpad and the copyright file fill the request in (2026-11-22) ----------
const COWSAY_COPYRIGHT = `Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: cowsay

Files: *
Copyright: 1999-2000 Tony Monroe
License: COWSAY

Files: debian/*
Copyright: 2019 Someone
License: GPL
`;
function fakeUbuntu({ entries, copyright = COWSAY_COPYRIGHT, status = 200 } = {}) {
  const calls = [];
  const fn = async (url) => {
    calls.push(url);
    if (url.startsWith("https://api.launchpad.net/")) {
      const name = new URL(url).searchParams.get("binary_name");
      const body = { entries: (entries ?? {})[name] ?? [] };
      return { status, url, headers: new Headers(), text: async () => JSON.stringify(body) };
    }
    if (url.startsWith("https://changelogs.ubuntu.com/") && copyright !== null) return { status: 200, url, headers: new Headers(), text: async () => copyright };
    return { status: 404, url, headers: new Headers(), text: async () => "" };
  };
  fn.calls = calls;
  return fn;
}
const cowsayEntry = (over = {}) => ({ binary_package_name: "cowsay", binary_package_version: "3.03+dfsg2-8", status: "Published", pocket: "Release",
  component_name: "universe", date_published: "2023-10-23T22:30:24.014979+00:00", source_package_name: "cowsay", source_package_version: "3.03+dfsg2-8", ...over });
const cowsayRequest = () => ({ contract: "jorah-tool-v1", name: "cowsay", title: "cowsay (talking cow)", kind: "apt", purpose: "A tiny Ubuntu package to test the toolbox's apt path.",
  packages: ["cowsay"], sandbox: { network: [] }, smoke: ["cowsay", "moo"] });

test("toolbox_propose fills an Ubuntu package's version, date and licence from Launchpad and its copyright file", async () => {
  const fx = fixture();
  const fetch = fakeUbuntu({ entries: { cowsay: [cowsayEntry({ pocket: "Release" })] } });
  const call = load(fx, { fetch });
  const r = await call("toolbox_propose", { manifest: cowsayRequest() });
  assert.equal(r.status, "proposed", JSON.stringify(r));
  assert.equal(r.card.version, "3.03+dfsg2-8");
  assert.equal(r.card.released, "2023-10-23");
  assert.equal(r.card.licence, "COWSAY");
  assert.equal(r.card.source, "Ubuntu archive: cowsay");
  assert.deepEqual(r.ubuntu.filled_in, ["version", "released", "release_page", "homepage", "licence", "licence_source"]);
  const saved = JSON.parse(readFileSync(join(fx.var, "proposals", `${r.id}.json`), "utf8"));
  assert.equal(saved.manifest.licence_source, "https://changelogs.ubuntu.com/changelogs/pool/universe/c/cowsay/cowsay_3.03+dfsg2-8/copyright");
  assert.equal(saved.manifest.release_page, "https://launchpad.net/ubuntu/+source/cowsay/3.03%2Bdfsg2-8");
  assert.ok(fetch.calls[0].includes("distro_arch_series=https%3A%2F%2Fapi.launchpad.net%2F1.0%2Fubuntu%2Fnoble%2Famd64"), fetch.calls[0]);
  assert.match(r.next, /Ubuntu's own record/);
});

test("toolbox_propose for Ubuntu: the newest pocket wins, an epoch is dropped, and an unknown package or a too-new one is refused", async () => {
  const newer = cowsayEntry({ binary_package_version: "1:3.03+dfsg2-8ubuntu1", pocket: "Updates", date_published: "2026-11-01T10:00:00Z" });
  let call = load(fixture(), { fetch: fakeUbuntu({ entries: { cowsay: [cowsayEntry(), newer] } }) });
  const r = await call("toolbox_propose", { manifest: cowsayRequest() });
  assert.equal(r.card.version, "3.03+dfsg2-8ubuntu1");
  assert.equal(r.card.released, "2026-11-01");
  call = load(fixture(), { fetch: fakeUbuntu({ entries: {} }) });
  const none = await call("toolbox_propose", { manifest: cowsayRequest() });
  assert.equal(none.status, "refused");
  assert.match(none.problems.join(" "), /publishes no package named cowsay/);
  call = load(fixture(), { fetch: fakeUbuntu({ entries: { cowsay: [cowsayEntry({ date_published: "2026-11-15T10:00:00Z" })] } }) });
  const fresh = await call("toolbox_propose", { manifest: cowsayRequest() });
  assert.equal(fresh.status, "refused");
  assert.match(fresh.problems.join(" "), /less than 7 days ago/);
  call = load(fixture(), { fetch: fakeUbuntu({ entries: { cowsay: [cowsayEntry()] }, copyright: "no machine-readable format here" }) });
  const plain = await call("toolbox_propose", { manifest: cowsayRequest() });
  assert.equal(plain.card.licence, "see Ubuntu's copyright file");
  call = load(fixture(), { fetch: fakeUbuntu({ status: 503 }) });
  assert.equal((await call("toolbox_propose", { manifest: cowsayRequest() })).status, "unavailable");
});

// ---- GitHub release on-disk cache: TTL, If-None-Match 304, rate-limit stale fallback (2026-11-22) -

test("ghcache + githubRelease: mode 0600, 6h TTL, If-None-Match 304, and 7-day rate-limit fallback", async () => {
  const fx = fixture();
  const stateDir = join(fx.root, "state");
  const where = githubAsset(example("github", GH.request).url);
  const rel = example("github", GH.release);
  let clock = new Date("2026-11-19T10:00:00.000Z");
  const queue = [];
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, headers: init?.headers ?? {} });
    const next = queue.shift();
    if (!next) throw new Error("unexpected fetch");
    return { status: next.status ?? 200, url, headers: new Headers(next.headers ?? {}), text: async () => next.text ?? JSON.stringify(next.body) };
  };

  // 1. Cold miss: 200 with ETag writes github-cache.json mode 0600 and leaves no .tmp files.
  queue.push({ status: 200, headers: { etag: 'W/"rel-1"' }, body: rel });
  const r1 = await githubRelease(fetchImpl, where, () => clock, where.path, stateDir);
  assert.equal(r1.ok, true);
  assert.equal(r1.cached, undefined);
  assert.equal(calls.length, 1);
  const cacheFile = join(stateDir, CACHE_FILE);
  assert.equal(statSync(cacheFile).mode & 0o777, 0o600);
  assert.deepEqual(readdirSync(stateDir).filter((f) => f.endsWith(".tmp")), []);
  const disk = JSON.parse(readFileSync(cacheFile, "utf8"));
  assert.equal(disk.entries[RELEASE_URL].etag, 'W/"rel-1"');
  assert.equal(disk.entries[RELEASE_URL].fetchedAt, "2026-11-19T10:00:00.000Z");

  // 2. Within 6h TTL (+5h59m): no HTTP request made at all.
  clock = new Date("2026-11-19T15:59:00.000Z");
  const r2 = await githubRelease(fetchImpl, where, () => clock, where.path, stateDir);
  assert.equal(r2.ok, true);
  assert.equal(r2.cached, true);
  assert.equal(r2.cachedAt, "2026-11-19T10:00:00.000Z");
  assert.equal(calls.length, 1);

  // 3. Past 6h TTL (+6h01m): sends If-None-Match; 304 refreshes fetchedAt and skips rate limit.
  clock = new Date("2026-11-19T16:01:00.000Z");
  queue.push({ status: 304, headers: { etag: 'W/"rel-2"' }, text: "" });
  const r3 = await githubRelease(fetchImpl, where, () => clock, where.path, stateDir);
  assert.equal(r3.ok, true);
  assert.equal(r3.at, "2026-11-19T16:01:00.000Z");
  assert.equal(calls.length, 2);
  assert.equal(calls[1].headers["if-none-match"], 'W/"rel-1"');
  assert.equal(JSON.parse(readFileSync(cacheFile, "utf8")).entries[RELEASE_URL].etag, 'W/"rel-2"');

  // 4. Past 6h TTL again, rate-limited (429 with x-ratelimit-remaining 0), < 7 days old: serves cached copy.
  clock = new Date("2026-11-26T15:00:00.000Z");
  const reset = String(Date.parse("2026-11-26T16:00:00Z") / 1000);
  queue.push({ status: 429, headers: { "x-ratelimit-remaining": "0", "x-ratelimit-reset": reset }, body: { message: "rate limit" } });
  const r4 = await githubRelease(fetchImpl, where, () => clock, where.path, stateDir);
  assert.equal(r4.ok, true);
  assert.equal(r4.cached, true);
  assert.equal(r4.cachedAt, "2026-11-19T16:01:00.000Z");
  assert.equal(r4.release.tag_name, rel.tag_name);

  // 5. Once >= 7 days old, rate-limited returns the "until <reset>" error.
  clock = new Date("2026-11-26T16:01:00.000Z");
  queue.push({ status: 403, headers: { "x-ratelimit-remaining": "0", "x-ratelimit-reset": reset }, body: { message: "rate limit" } });
  const r5 = await githubRelease(fetchImpl, where, () => clock, where.path, stateDir);
  assert.equal(r5.ok, false);
  assert.match(r5.reason, /until 16:00 UTC/);
});

test("ghcache: caps entries by oldest fetchedAt, ignores corrupt or symlinked cache files, and works via toolbox_propose", async () => {
  const fx = fixture();
  const stateDir = join(fx.root, "state");
  const cache = ghCache(stateDir, { maxEntries: 2 });
  cache.set("https://api.github.com/r/1", { etag: '"1"', body: { n: 1 }, fetchedAt: "2026-11-10T00:00:00.000Z" });
  cache.set("https://api.github.com/r/2", { etag: '"2"', body: { n: 2 }, fetchedAt: "2026-11-12T00:00:00.000Z" });
  cache.set("https://api.github.com/r/3", { etag: '"3"', body: { n: 3 }, fetchedAt: "2026-11-11T00:00:00.000Z" });
  assert.equal(cache.get("https://api.github.com/r/1"), null, "oldest entry evicted");
  assert.deepEqual(cache.get("https://api.github.com/r/2")?.body, { n: 2 });
  assert.deepEqual(cache.get("https://api.github.com/r/3")?.body, { n: 3 });

  // Corrupt JSON or symlinked cache file is ignored gracefully.
  writeFileSync(cache.file, "{not json");
  assert.equal(cache.get("https://api.github.com/r/2"), null);
  const badDir = join(fx.root, "bad-state");
  mkdirSync(badDir, { recursive: true });
  symlinkSync(cache.file, join(badDir, CACHE_FILE));
  assert.equal(ghCache(badDir).get("https://api.github.com/r/2"), null);

  // Wired into toolbox_propose: a second Gateway load within 6h makes no fetch.
  const gh1 = fakeGithub({ [RELEASE_URL]: { headers: { etag: '"uv-1"' }, body: example("github", GH.release) } });
  const call1 = load(fx, { now: GH_NOW, fetch: gh1 });
  const first = await call1("toolbox_propose", { manifest: example("github", GH.request) });
  assert.equal(first.status, "proposed");
  assert.equal(gh1.calls.length, 1);

  const gh2 = fakeGithub({});
  const call2 = load(fx, { now: new Date(GH_NOW.getTime() + 60 * 60 * 1000), fetch: gh2 });
  const second = await call2("toolbox_propose", { manifest: example("github", GH.request) });
  assert.equal(second.status, "already proposed");
  assert.equal(gh2.calls.length, 0, "served from on-disk cache within 6h without hitting fetch");
});
