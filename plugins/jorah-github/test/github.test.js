import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, chmodSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EXCLUDE_MARKER, PROBE_BRANCH, READ, appJwt, check, checkCloneName, checkProject, checkRules, cloneFlow, cloneFromMirror, describe, mirrorBranch, prFlow, pushBranch, pushFlow, readKey, repoToken, settings, syncMirror } from "../github.js";
import { generateKeyPairSync, createVerify } from "node:crypto";

const g = (cwd, ...args) => execFileSync("git", ["-c", "user.name=T", "-c", "user.email=t@t", ...args], { cwd, encoding: "utf8" }).trim();

function world() {
  const root = mkdtempSync(join(tmpdir(), "jorah-gh-"));
  const work = join(root, "work");
  const project = join(work, "proj");
  mkdirSync(project, { recursive: true });
  g(project, "init", "-q", "-b", "main");
  writeFileSync(join(project, "a.txt"), "a\n");
  g(project, "add", "a.txt");
  g(project, "commit", "-q", "-m", "first");
  g(project, "checkout", "-q", "-b", "jorah/task");
  writeFileSync(join(project, "b.txt"), "b\n");
  g(project, "add", "b.txt");
  g(project, "commit", "-q", "-m", "add b");
  const config = settings({ appId: "5686503", workDir: work, mirrorDir: join(root, "mirrors"), repos: { proj: "AdamHikl/proj" } });
  return { root, work, project, config };
}

test("only jorah/ branches of listed projects pass", () => {
  const { config } = world();
  assert.equal(check(config, { project: "proj", branch: "jorah/task" }).repo, "AdamHikl/proj");
  for (const branch of ["main", "jorah/", "jorah/../main", "feature/x", "jorah/x.lock", "+jorah/x", "jorah/x:main", "refs/heads/main"]) {
    assert.throws(() => check(config, { project: "proj", branch }), /jorah\/<task>/, branch);
  }
  assert.throws(() => check(config, { project: "other", branch: "jorah/task" }), /isn't one of Adam's repos/);
  assert.throws(() => check(config, { project: "../proj", branch: "jorah/task" }), /folder name/);
});

test("bad repo names in config are refused", () => {
  assert.throws(() => settings({ repos: { proj: "https://evil.example/x" } }), /bad repos entry/);
});

test("the mirror gets the branch, and the work repo's hook and remotes have no effect", async () => {
  const { root, project, config } = world();
  const marker = join(root, "HOOK-RAN");
  mkdirSync(join(project, ".git", "hooks"), { recursive: true });
  for (const hook of ["pre-push", "post-checkout", "reference-transaction", "pre-auto-gc"]) {
    writeFileSync(join(project, ".git", "hooks", hook), `#!/bin/sh\ntouch ${marker}\n`);
    chmodSync(join(project, ".git", "hooks", hook), 0o755);
  }
  g(project, "config", "remote.origin.url", "https://evil.example/steal.git");
  g(project, "config", "url.https://evil.example/.insteadOf", "https://github.com/");
  g(project, "config", "core.fsmonitor", `touch ${marker}`);
  const target = check(config, { project: "proj", branch: "jorah/task" });
  const mirrored = await mirrorBranch(config, target);
  assert.match(mirrored.log, /add b/);
  assert.equal(existsSync(marker), false, "a hook or fsmonitor in the work repo ran");
  const url = execFileSync("git", ["--git-dir", mirrored.mirror, "config", "remote.origin.url"], { encoding: "utf8" }).trim();
  assert.equal(url, "https://github.com/AdamHikl/proj.git");
});

test("a stale mirror remote is reset to the listed repo", async () => {
  const { config } = world();
  const target = check(config, { project: "proj", branch: "jorah/task" });
  const first = await mirrorBranch(config, target);
  execFileSync("git", ["--git-dir", first.mirror, "config", "remote.origin.url", "https://evil.example/x.git"]);
  const again = await mirrorBranch(config, target);
  assert.equal(execFileSync("git", ["--git-dir", again.mirror, "config", "remote.origin.url"], { encoding: "utf8" }).trim(), "https://github.com/AdamHikl/proj.git");
});

test("push names the exact branch, never forced, token only through askpass", async () => {
  const { config } = world();
  const target = check(config, { project: "proj", branch: "jorah/task" });
  const mirrored = await mirrorBranch(config, target);
  let seen;
  await pushBranch(config, { ...target, ...mirrored }, "fake-token-for-tests-only", { gitImpl: async (args, opts) => { seen = { args, opts }; } });
  assert.deepEqual(seen.args.slice(-2), ["origin", "refs/heads/jorah/task:refs/heads/jorah/task"]);
  assert.ok(!seen.args.some((a) => a.startsWith("+") || a === "--force" || a === "-f"));
  assert.ok(!seen.args.join(" ").includes("fake-token"), "token in argv");
  assert.equal(seen.opts.env.JORAH_GH_TOKEN, "fake-token-for-tests-only");
  assert.equal(seen.opts.env.JORAH_GH_USER, "x-access-token");
  const askpass = readFileSync(seen.opts.env.GIT_ASKPASS, "utf8");
  assert.ok(!askpass.includes("fake-token"), "token written to disk");
});

function keyFile(mode = 0o600) {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const dir = mkdtempSync(join(tmpdir(), "jorah-key-"));
  const f = join(dir, "app.pem");
  writeFileSync(f, privateKey.export({ type: "pkcs1", format: "pem" }), { mode });
  chmodSync(f, mode);
  return { f, publicKey };
}

test("the App's key file must be private", () => {
  const { f } = keyFile(0o644);
  assert.throws(() => readKey(f), /owner only/);
  chmodSync(f, 0o600);
  assert.match(readKey(f), /PRIVATE KEY/);
});

test("the JWT names the App, lasts under 10 minutes and verifies with the public key", () => {
  const { f, publicKey } = keyFile();
  const jwt = appJwt("5686503", readKey(f), Date.UTC(2026, 10, 9, 20, 0, 0));
  const [head, body, sig] = jwt.split(".");
  const claims = JSON.parse(Buffer.from(body, "base64url").toString());
  assert.equal(claims.iss, "5686503");
  assert.ok(claims.exp - claims.iat <= 600);
  assert.ok(createVerify("RSA-SHA256").update(`${head}.${body}`).verify(publicKey, Buffer.from(sig, "base64url")));
});

test("the token is asked for one repo, contents and pull requests only", async () => {
  const { f } = keyFile();
  const config = settings({ appId: "5686503", keyFile: f, repos: { threadfolio: "AdamHikl/threadfolio" } });
  const calls = [];
  const fetchImpl = async (url, opts = {}) => {
    calls.push({ url, opts });
    if (url.endsWith("/installation")) return { ok: true, status: 200, json: async () => ({ id: 42 }) };
    return { ok: true, status: 201, json: async () => ({ token: "fake-installation-token" }) };
  };
  assert.equal(await repoToken(config, "AdamHikl/threadfolio", { fetchImpl }), "fake-installation-token");
  assert.equal(calls[0].url, "https://api.github.com/repos/AdamHikl/threadfolio/installation");
  assert.equal(calls[1].url, "https://api.github.com/app/installations/42/access_tokens");
  assert.deepEqual(JSON.parse(calls[1].opts.body), { repositories: ["threadfolio"], permissions: { contents: "write", pull_requests: "write" } });
});

test("a repo without the App says so", async () => {
  const { f } = keyFile();
  const config = settings({ appId: "5686503", keyFile: f, repos: {} });
  await assert.rejects(repoToken(config, "AdamHikl/x", { fetchImpl: async () => ({ ok: false, status: 404, json: async () => ({}) }) }), /isn't installed on AdamHikl\/x/);
});

test("a non-numeric App ID is refused", () => {
  assert.throws(() => settings({ appId: "jorah-bot" }), /App's number/);
});

test("approval text names repo and branch", () => {
  const config = settings({ repos: { proj: "AdamHikl/proj" } });
  assert.equal(describe("github_push_branch", { project: "proj", branch: "jorah/x" }, config), "Push branch jorah/x from ~/work/proj to AdamHikl/proj");
  assert.match(describe("github_push_branch", { project: "nope", branch: "jorah/x" }, config), /a repo Jorah may not use/);
});

test("every call to the tools waits for Adam; searches and wrappers don't prompt", async () => {
  const { default: plugin } = await import("../index.js");
  const hooks = {}, tools = {};
  plugin.register({ pluginConfig: { repos: { proj: "AdamHikl/proj" } }, logger: { info() {}, warn() {} }, on: (n, f) => (hooks[n] = f), registerTool: (t) => (tools[t.name] = t) });
  assert.deepEqual(Object.keys(tools).sort(), ["github_clone", "github_open_pr", "github_push_branch", "github_sync"]);
  assert.equal(hooks.before_tool_call({ toolName: "github_clone", params: { repo: "proj" } }), undefined, "clone only reads: no prompt");
  assert.equal(hooks.before_tool_call({ toolName: "github_sync", params: { project: "proj" } }), undefined, "sync is read-only: no prompt");
  assert.equal(tools.github_push_branch.catalogMode, undefined, "must be findable through tool search");
  const direct = hooks.before_tool_call({ toolName: "github_push_branch", params: { project: "proj", branch: "jorah/x" } });
  assert.equal(direct.requireApproval.description, "Push branch jorah/x from ~/work/proj to AdamHikl/proj");
  assert.deepEqual(direct.requireApproval.allowedDecisions, ["allow-once", "deny"]);
  const pr = hooks.before_tool_call({ toolName: "github_open_pr", params: { project: "proj", branch: "jorah/x", title: "T" } });
  assert.match(pr.requireApproval.description, /draft pull request on AdamHikl\/proj/);
  // The wrapper and a search are not calls; the inner tool's own hook run asks for approval.
  assert.equal(hooks.before_tool_call({ toolName: "tool_call", params: { id: "github_push_branch", args: { project: "proj", branch: "jorah/x" } } }), undefined);
  assert.equal(hooks.before_tool_call({ toolName: "tool_search", params: { query: "github_push_branch" } }), undefined);
  assert.equal(hooks.before_tool_call({ toolName: "web_search", params: { q: "x" } }), undefined);
  // Missing arguments: refused, never an empty prompt.
  for (const params of [{}, { project: "proj" }, { branch: "jorah/x" }, undefined]) {
    const r = hooks.before_tool_call({ toolName: "github_push_branch", params });
    assert.equal(r.block, true);
    assert.equal(r.requireApproval, undefined);
  }
});

test("sync fills github/* in the mirror, keeps waiting jorah/* branches, and the work repo can fetch it", async () => {
  const { root, project, config } = world();
  // A stand-in for GitHub: a bare repo with main and a feature branch.
  const remoteBase = join(root, "gh") + "/";
  const origin = join(remoteBase, "AdamHikl", "proj.git");
  mkdirSync(join(remoteBase, "AdamHikl"), { recursive: true });
  g(root, "clone", "-q", "--bare", project, origin);
  // A jorah/ branch already waiting in the mirror must survive the sync.
  const target = check(config, { project: "proj", branch: "jorah/task" });
  const waiting = await mirrorBranch(config, target);
  const result = await syncMirror(config, { project: "proj", repo: "AdamHikl/proj" }, "fake-token-for-tests-only", { remoteBase });
  assert.ok(result.branches.some((b) => b.startsWith("main ")), result.branches.join(","));
  const heads = execFileSync("git", ["--git-dir", result.mirror, "for-each-ref", "--format=%(refname)", "refs/heads/"], { encoding: "utf8" });
  assert.match(heads, /refs\/heads\/jorah\/task/);
  assert.equal(waiting.mirror, result.mirror);
  // The work repo's remote "github" reads the mirror, as Claude Code does in its sandbox.
  g(project, "remote", "add", "github", result.mirror);
  g(project, "config", "remote.github.fetch", "+refs/remotes/github/*:refs/remotes/github/*");
  g(project, "fetch", "-q", "github");
  assert.match(g(project, "branch", "-r"), /github\/main/);
});

test("sync asks GitHub for a read-only token", async () => {
  const { f } = keyFile();
  const config = settings({ appId: "5686503", keyFile: f, repos: {} });
  let body;
  const fetchImpl = async (url, opts = {}) => {
    if (url.endsWith("/installation")) return { ok: true, status: 200, json: async () => ({ id: 7 }) };
    body = JSON.parse(opts.body);
    return { ok: true, status: 201, json: async () => ({ token: "fake-installation-token" }) };
  };
  await repoToken(config, "AdamHikl/threadfolio", { fetchImpl, permissions: READ });
  assert.deepEqual(body.permissions, { contents: "read" });
});

// --- Any repo of the owner, github_clone and the live rule check (2026-11-10) ---

test("with an owner, any repo name of that owner is allowed; the repos map still renames folders", () => {
  const config = settings({ owner: "AdamHikl", repos: { "mizyun-web": "AdamHikl/mizyun" } });
  assert.deepEqual(checkProject(config, "robot_tour"), { project: "robot_tour", repo: "AdamHikl/robot_tour" });
  assert.deepEqual(checkProject(config, "mizyun-web"), { project: "mizyun-web", repo: "AdamHikl/mizyun" });
  for (const bad of ["../x", "a/b", "", ".hidden", "-x", "x y", "x;y"]) assert.throws(() => checkProject(config, bad), /folder name/, bad);
  assert.throws(() => checkProject(settings({}), "robot_tour"), /isn't one of Adam's repos/, "no owner, no map: nothing allowed");
  assert.throws(() => settings({ owner: "AdamHikl", repos: { x: "someone-else/x" } }), /isn't AdamHikl's/);
  assert.throws(() => settings({ owner: "Adam/Hikl" }), /account name/);
  assert.throws(() => settings({ owner: "https://evil.example" }), /account name/);
});

test("clone names: the bare repo name or owner/name, nothing else", () => {
  const config = settings({ owner: "AdamHikl" });
  assert.equal(checkCloneName(config, "robot_tour").repo, "AdamHikl/robot_tour");
  assert.equal(checkCloneName(config, "adamhikl/robot_tour").project, "robot_tour");
  for (const bad of ["someone/robot_tour", "AdamHikl/a/b", "AdamHikl/../x", "../x", 42, undefined]) assert.throws(() => checkCloneName(config, bad), undefined, String(bad));
});

const RULESET = ["creation", "update", "deletion", "non_fast_forward"];

/** A stand-in for GitHub's API. `rules` maps a branch name to its rule types. */
function fakeApi({ rules = { main: RULESET, [PROBE_BRANCH]: RULESET }, defaultBranch = "main", status = {} } = {}) {
  const calls = [];
  const fetchImpl = async (url, opts = {}) => {
    calls.push({ url, opts, body: opts.body ? JSON.parse(opts.body) : undefined });
    const reply = (code, data) => ({ ok: code < 300, status: code, json: async () => data });
    if (url.endsWith("/installation")) return reply(200, { id: 42 });
    if (url.endsWith("/access_tokens")) return reply(201, { token: "fake-installation-token" });
    const m = url.match(/\/rules\/branches\/(.+)\?per_page=100$/);
    if (m) {
      const branch = decodeURIComponent(m[1]);
      if (status.rules) return reply(status.rules, { message: "nope" });
      return reply(200, (rules[branch] ?? []).map((type) => ({ type, ruleset_source_type: "Repository", ruleset_id: 1 })));
    }
    if (url.endsWith("/pulls")) return reply(201, { html_url: "https://github.com/AdamHikl/proj/pull/7", number: 7 });
    if (/\/repos\/[^/]+\/[^/]+$/.test(url)) return reply(status.repo ?? 200, { default_branch: defaultBranch });
    return reply(404, {});
  };
  return { fetchImpl, calls };
}

test("the rule check passes only with the jorah ruleset on the default branch and outside jorah/**", async () => {
  const ok = fakeApi();
  assert.deepEqual(await checkRules("AdamHikl/proj", "fake-installation-token", { fetchImpl: ok.fetchImpl }), { defaultBranch: "main", rules: [...RULESET].sort() });
  const urls = ok.calls.map((c) => c.url);
  assert.deepEqual(urls, [
    "https://api.github.com/repos/AdamHikl/proj",
    "https://api.github.com/repos/AdamHikl/proj/rules/branches/main?per_page=100",
    `https://api.github.com/repos/AdamHikl/proj/rules/branches/${PROBE_BRANCH}?per_page=100`,
  ]);
  assert.ok(ok.calls.every((c) => c.opts.headers.Authorization === "Bearer fake-installation-token"));
  assert.ok(!PROBE_BRANCH.startsWith("jorah/"), "the probe must sit outside jorah/**");

  const cases = [
    [{ rules: {} }, /isn't protected yet.*main branch accepts updates.*only sync/],
    [{ rules: { main: ["deletion", "non_fast_forward"], [PROBE_BRANCH]: RULESET } }, /isn't protected yet/],
    [{ rules: { main: RULESET, [PROBE_BRANCH]: ["update"] } }, /isn't protected yet.*outside jorah/],
    [{ rules: { main: RULESET, [PROBE_BRANCH]: [] } }, /isn't protected yet/],
    [{ status: { rules: 403 } }, /couldn't read .* branch rules \(GitHub said 403\)/],
    [{ status: { repo: 404 } }, /GitHub said 404 reading/],
  ];
  for (const [opts, reason] of cases) {
    await assert.rejects(checkRules("AdamHikl/proj", "t", { fetchImpl: fakeApi(opts).fetchImpl }), reason, JSON.stringify(opts));
  }
  // A non-default branch name with a slash is asked for path by path.
  const slash = fakeApi({ rules: { "release/1": RULESET, [PROBE_BRANCH]: RULESET }, defaultBranch: "release/1" });
  await checkRules("AdamHikl/proj", "t", { fetchImpl: slash.fetchImpl });
  assert.match(slash.calls[1].url, /rules\/branches\/release\/1\?/);
  // Nonsense from GitHub fails closed.
  const junk = async (url) => ({ ok: true, status: 200, json: async () => (url.includes("/rules/") ? { rules: "x" } : { default_branch: "main" }) });
  await assert.rejects(checkRules("AdamHikl/proj", "t", { fetchImpl: junk }), /made no sense/);
});

/** world() plus a key, owner config and a stand-in GitHub git server holding the project. */
function ownerWorld() {
  const w = world();
  const { f } = keyFile();
  const remoteBase = join(w.root, "gh") + "/";
  const origin = join(remoteBase, "AdamHikl", "proj.git");
  mkdirSync(join(remoteBase, "AdamHikl"), { recursive: true });
  g(w.root, "clone", "-q", "--bare", w.project, origin);
  g(origin, "branch", "-D", "jorah/task");
  const config = settings({ appId: "5686503", keyFile: f, owner: "AdamHikl", workDir: w.work, mirrorDir: join(w.root, "mirrors") });
  return { ...w, config, remoteBase, origin };
}

test("a push goes through only after the rule check passes, with the write token", async () => {
  const { config, remoteBase, origin } = ownerWorld();
  const api = fakeApi();
  const { result } = await pushFlow(config, { project: "proj", branch: "jorah/task" }, { fetchImpl: api.fetchImpl, remoteBase });
  assert.equal(result.pushed, "AdamHikl/proj:jorah/task");
  assert.match(g(origin, "branch", "--list", "jorah/task"), /jorah\/task/);
  assert.deepEqual(api.calls[1].body.permissions, { contents: "write", pull_requests: "write" });
  assert.ok(api.calls.some((c) => c.url.includes("/rules/branches/main")), "rules were checked");
});

test("a repo without the ruleset is sync-only: the push is refused and nothing reaches GitHub", async () => {
  const { config, remoteBase, origin } = ownerWorld();
  const api = fakeApi({ rules: { main: ["deletion", "non_fast_forward"] } });
  await assert.rejects(pushFlow(config, { project: "proj", branch: "jorah/task" }, { fetchImpl: api.fetchImpl, remoteBase }), /this repo isn't protected yet/);
  assert.equal(g(origin, "branch", "--list", "jorah/task"), "");
  let pushed = false;
  await assert.rejects(pushFlow(config, { project: "proj", branch: "jorah/task" }, { fetchImpl: fakeApi({ status: { rules: 500 } }).fetchImpl, remoteBase, gitImpl: async () => { pushed = true; } }), /couldn't read/);
  assert.equal(pushed, false, "a failed rule read must not push");
});

test("a pull request is checked against the rules too, and opens as a draft", async () => {
  const { config } = ownerWorld();
  const refused = fakeApi({ rules: {} });
  await assert.rejects(prFlow(config, { project: "proj", branch: "jorah/task", title: "T" }, { fetchImpl: refused.fetchImpl }), /isn't protected yet/);
  assert.ok(!refused.calls.some((c) => c.url.endsWith("/pulls")), "no pull request call when unprotected");
  const ok = fakeApi();
  const { pr } = await prFlow(config, { project: "proj", branch: "jorah/task", title: "T", body: "B" }, { fetchImpl: ok.fetchImpl });
  assert.equal(pr.number, 7);
  const post = ok.calls.find((c) => c.url.endsWith("/pulls"));
  assert.deepEqual({ head: post.body.head, base: post.body.base, draft: post.body.draft }, { head: "jorah/task", base: "main", draft: true });
});

test("clone: from the mirror (never GitHub) into ~/work/<repo>, on the default branch, prepared for Claude Code", async () => {
  const { root, config, remoteBase, origin, work } = ownerWorld();
  // Move the stand-in GitHub repo to a fresh name with a second branch, so "proj" doesn't exist yet in ~/work.
  const newOrigin = join(remoteBase, "AdamHikl", "robot_tour.git");
  g(root, "clone", "-q", "--bare", origin, newOrigin);
  g(newOrigin, "branch", "feature", "main");
  const api = fakeApi();
  const { target, cloned, synced } = await cloneFlow(config, "robot_tour", { fetchImpl: api.fetchImpl, remoteBase });
  assert.equal(target.repo, "AdamHikl/robot_tour");
  assert.deepEqual(api.calls[1].body.permissions, { contents: "read" }, "read-only token");
  assert.ok(!api.calls.some((c) => c.url.includes("/rules/")), "reading needs no rule check");
  const dest = join(work, "robot_tour");
  assert.equal(cloned.path, dest);
  assert.equal(g(dest, "rev-parse", "--abbrev-ref", "HEAD"), "main");
  assert.equal(readFileSync(join(dest, "a.txt"), "utf8"), "a\n");
  assert.equal(g(dest, "remote"), "github", "only the mirror remote, no origin on GitHub");
  assert.equal(g(dest, "remote", "get-url", "github"), synced.mirror);
  assert.match(g(dest, "branch", "-r"), /github\/feature/);
  const exclude = readFileSync(join(dest, ".git", "info", "exclude"), "utf8");
  assert.ok(exclude.includes(EXCLUDE_MARKER) && exclude.includes("/.claude/hooks") && exclude.includes("/.bashrc"));
  // The work repo's config holds no token and no GitHub URL.
  const cfg = readFileSync(join(dest, ".git", "config"), "utf8");
  assert.ok(!cfg.includes("github.com") && !cfg.includes("fake-installation-token"), cfg);
  // Claude Code in the sandbox can then fetch from the mirror and branch.
  g(dest, "fetch", "-q", "github");
  g(dest, "checkout", "-q", "-b", "jorah/docs", "github/main");
  // A second clone is refused before anything is fetched.
  const again = fakeApi();
  await assert.rejects(cloneFlow(config, "robot_tour", { fetchImpl: again.fetchImpl, remoteBase }), /already exists; use github_sync/);
  assert.equal(again.calls.length, 0);
});

test("clone refuses other owners and an existing folder, and leaves nothing half-made", async () => {
  const { config, remoteBase, work, root } = ownerWorld();
  await assert.rejects(cloneFlow(config, "someone/robot_tour", { fetchImpl: fakeApi().fetchImpl, remoteBase }), /only AdamHikl's repos/);
  await assert.rejects(cloneFlow(config, "proj", { fetchImpl: fakeApi().fetchImpl, remoteBase }), /already exists/);
  // A default branch the mirror doesn't have: the clone fails and removes its folder.
  const mirror = join(root, "empty.git");
  g(root, "init", "-q", "--bare", mirror);
  await assert.rejects(cloneFromMirror(config, { project: "fresh", repo: "AdamHikl/fresh" }, { mirror, branch: "main" }));
  assert.equal(existsSync(join(work, "fresh")), false);
  // A symlink in the way counts as existing.
  execFileSync("ln", ["-s", join(root, "nowhere"), join(work, "linked")]);
  await assert.rejects(cloneFromMirror(config, { project: "linked", repo: "AdamHikl/linked" }, { mirror, branch: "main" }), /already exists/);
});

test("approval text works for any repo of the owner", () => {
  const config = settings({ owner: "AdamHikl" });
  assert.equal(describe("github_push_branch", { project: "robot_tour", branch: "jorah/x" }, config), "Push branch jorah/x from ~/work/robot_tour to AdamHikl/robot_tour");
  assert.match(describe("github_open_pr", { project: "robot_tour", branch: "jorah/x", title: "T" }, config), /draft pull request on AdamHikl\/robot_tour/);
});
