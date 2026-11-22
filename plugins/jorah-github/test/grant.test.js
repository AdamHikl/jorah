// Level 2's standing push grant (WS5, issue #19): every invariant must hold for a push to skip
// Adam's card, and every push is logged for the digest.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { check, logProjectPush, settings, standingGrant, GRANT_MAX_FILE } from "../github.js";

const g = (cwd, ...args) => execFileSync("git", ["-c", "user.name=T", "-c", "user.email=t@t", ...args], { cwd, encoding: "utf8" }).trim();

function grantWorld({ grant = true, level = 2, state = {}, entry = {}, selfRepos } = {}) {
  const root = mkdtempSync(join(tmpdir(), "jorah-grant-"));
  const work = join(root, "work");
  const project = join(work, "proj");
  mkdirSync(project, { recursive: true });
  g(project, "init", "-q", "-b", "main");
  writeFileSync(join(project, "a.txt"), "a\n");
  g(project, "add", "a.txt");
  g(project, "commit", "-q", "-m", "first");
  const registry = join(root, "projects.json");
  const stateDir = join(root, "jorah-projects");
  const guard = join(root, "guard");
  mkdirSync(guard);
  writeFileSync(registry, JSON.stringify({ proj: { repo: "AdamHikl/proj", workDir: project, branch: "jorah/line", level, ...entry } }));
  mkdirSync(join(stateDir, "proj"), { recursive: true });
  writeFileSync(join(stateDir, "proj", "state.json"), JSON.stringify({ v: 1, paused: false, pushBlocked: false, cleanHead: "abc123", ...state }));
  const config = settings({ appId: "1", workDir: work, mirrorDir: join(root, "mirrors"), repos: { proj: "AdamHikl/proj" }, projectsRegistry: registry,
    projectsStateDir: stateDir, guardStateDir: guard, standingGrant: grant, ...(selfRepos ? { selfRepos } : {}) });
  return { root, project, config, guard, stateDir, target: check(config, { project: "proj", branch: "jorah/line" }) };
}

const listing = (files = [{ status: "modified", path: "src/arm.py" }], head = "abc123") => ({ head, base: "main", files });
const sizes = (n = 100) => async () => String(n);

test("on, level 2, scanned head, plain files: no card", async () => {
  const w = grantWorld();
  assert.deepEqual(await standingGrant(w.config, w.target, listing(), { gitImpl: sizes() }), { ok: true, project: "proj" });
});

test("off by default: Adam's written yes turns it on", async () => {
  const w = grantWorld({ grant: false });
  assert.equal(settings({}).standingGrant, false);
  assert.match((await standingGrant(w.config, w.target, listing(), { gitImpl: sizes() })).why, /off/);
});

test("each invariant on its own keeps the card", async () => {
  const cases = [
    [{ level: 1 }, /level 1/],
    [{ state: { pushBlocked: true } }, /push block/],
    [{ state: { pushBlocked: undefined } }, /push block/],
    [{ state: { cleanHead: "other" } }, /secret scan/],
    [{ state: { paused: true } }, /paused/],
    [{ entry: { repo: "AdamHikl/else" } }, /registry repo/],
    [{ selfRepos: ["proj"] }, /own repo/],
  ];
  for (const [opts, why] of cases) {
    const w = grantWorld(opts);
    const r = await standingGrant(w.config, w.target, listing(), { gitImpl: sizes() });
    assert.equal(r.ok, false, JSON.stringify(opts));
    assert.match(r.why, why);
  }
});

test("frozen, a .github file, a file over 5 MB, an unreadable size or listing keep the card", async () => {
  const w = grantWorld();
  writeFileSync(join(w.guard, "FROZEN"), "x");
  assert.match((await standingGrant(w.config, w.target, listing(), { gitImpl: sizes() })).why, /frozen/);
  const v = grantWorld();
  assert.match((await standingGrant(v.config, v.target, listing([{ status: "added", path: ".github/workflows/x.yml" }]), { gitImpl: sizes() })).why, /\.github/);
  assert.match((await standingGrant(v.config, v.target, listing([{ status: "renamed", path: "ci.yml", from: ".github/ci.yml" }]), { gitImpl: sizes() })).why, /\.github/);
  assert.match((await standingGrant(v.config, v.target, listing(), { gitImpl: sizes(GRANT_MAX_FILE + 1) })).why, /over 5 MB/);
  assert.match((await standingGrant(v.config, v.target, listing(), { gitImpl: async () => { throw new Error("no"); } })).why, /size/);
  assert.match((await standingGrant(v.config, v.target, { error: "took too long" }, { gitImpl: sizes() })).why, /listed/);
  // A deleted file needs no size.
  assert.equal((await standingGrant(v.config, v.target, listing([{ status: "deleted", path: "big.bin" }]), { gitImpl: async () => { throw new Error("no"); } })).ok, true);
});

test("an unreadable registry or state means no grant", async () => {
  const w = grantWorld();
  writeFileSync(join(w.stateDir, "proj", "state.json"), "{nope");
  assert.equal((await standingGrant(w.config, w.target, listing(), { gitImpl: sizes() })).ok, false);
});

test("every push is logged for the project's digest, with who let it through", () => {
  const w = grantWorld();
  assert.equal(logProjectPush(w.config, w.target, { head: "abc123", base: "main", files: [{ status: "modified", path: "src/arm.py" }], by: "standing grant", at: new Date("2026-11-22T10:00:00Z") }), true);
  const line = JSON.parse(readFileSync(join(w.stateDir, "proj", "pushes.jsonl"), "utf8").trim());
  assert.deepEqual(line, { v: 1, at: "2026-11-22T10:00:00.000Z", repo: "AdamHikl/proj", branch: "jorah/line", head: "abc123", base: "main", by: "standing grant", files: [{ status: "modified", path: "src/arm.py" }], more: 0 });
  assert.equal(realpathSync(w.project), w.target.source);
});
