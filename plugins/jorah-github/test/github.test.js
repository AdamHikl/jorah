import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, chmodSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { READ, appJwt, check, describe, mirrorBranch, pushBranch, readKey, repoToken, settings, syncMirror } from "../github.js";
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
  assert.throws(() => check(config, { project: "other", branch: "jorah/task" }), /isn't on Adam's list/);
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
  assert.match(describe("github_push_branch", { project: "nope", branch: "jorah/x" }, config), /not on the list/);
});

test("every call to the tools waits for Adam; searches and wrappers don't prompt", async () => {
  const { default: plugin } = await import("../index.js");
  const hooks = {}, tools = {};
  plugin.register({ pluginConfig: { repos: { proj: "AdamHikl/proj" } }, logger: { info() {}, warn() {} }, on: (n, f) => (hooks[n] = f), registerTool: (t) => (tools[t.name] = t) });
  assert.deepEqual(Object.keys(tools).sort(), ["github_open_pr", "github_push_branch", "github_sync"]);
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
