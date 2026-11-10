// The checks and git plumbing behind Jorah's GitHub tools. No OpenClaw imports, so it tests alone.
//
// Safety model:
// - Any repo of Adam's GitHub account (config `owner`) can be cloned and synced, read-only.
// - Only branches named jorah/<something> are pushed, never forced, and only after a live check
//   that the repo's rulesets confine the App to jorah/** (checkRules). A repo without them is
//   sync-only: "this repo isn't protected yet".
// - The work repo was written by a sandboxed Claude Code session, so it is untrusted: its hooks and
//   .git/config could run code or redirect the push. Nothing runs inside it except a fetch *from*
//   it into a mirror this plugin owns (git treats serving a fetch from an untrusted repo as safe).
//   The push runs from that mirror, with hooks off, no credential helper and the token supplied
//   through GIT_ASKPASS to that one process.
// - GitHub rulesets on each repo enforce jorah/** server-side too (scripts/github/protect-repo.sh).
// - A clone in ~/work comes from the plugin's mirror, never from GitHub straight into the work
//   folder, so no token or network is ever used inside a folder the sandbox can write.

import { execFile } from "node:child_process";
import { createSign } from "node:crypto";
import { lstatSync, mkdirSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);

export const DEFAULTS = Object.freeze({
  keyFile: "/home/jorah/.config/jorah-github/app.pem",
  workDir: "/home/jorah/work",
  mirrorDir: "/home/jorah/.jorah-github/mirrors",
});

const BRANCH = /^jorah\/[A-Za-z0-9][A-Za-z0-9._-]*(\/[A-Za-z0-9][A-Za-z0-9._-]*)*$/;
const REPO = /^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/;
const PROJECT = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const OWNER = /^[A-Za-z0-9-]+$/;

export function settings(pluginConfig = {}) {
  const owner = pluginConfig.owner == null ? "" : String(pluginConfig.owner);
  if (owner && !OWNER.test(owner)) throw new Error("jorah-github: owner must be a GitHub account name");
  const repos = pluginConfig.repos && typeof pluginConfig.repos === "object" ? pluginConfig.repos : {};
  for (const [project, repo] of Object.entries(repos)) {
    if (!PROJECT.test(project) || typeof repo !== "string" || !REPO.test(repo)) throw new Error(`jorah-github: bad repos entry ${project}`);
    if (owner && repo.split("/")[0].toLowerCase() !== owner.toLowerCase()) throw new Error(`jorah-github: repos entry ${project} isn't ${owner}'s`);
  }
  const appId = String(pluginConfig.appId ?? "");
  if (appId && !/^[0-9]+$/.test(appId)) throw new Error("jorah-github: appId must be the App's number");
  return {
    appId,
    keyFile: pluginConfig.keyFile ?? DEFAULTS.keyFile,
    workDir: pluginConfig.workDir ?? DEFAULTS.workDir,
    mirrorDir: pluginConfig.mirrorDir ?? DEFAULTS.mirrorDir,
    owner,
    repos,
  };
}

/**
 * Checks a project name. Returns {project, repo}. The repos map wins (a folder named differently
 * from its repo); otherwise the folder name is the repo name under the configured owner.
 */
export function checkProject(config, project) {
  if (typeof project !== "string" || !PROJECT.test(project)) throw new Error("project must be a folder name under ~/work");
  const repo = config.repos[project] ?? (config.owner ? `${config.owner}/${project}` : undefined);
  if (!repo || !REPO.test(repo)) throw new Error(`${project} isn't one of Adam's repos Jorah may work on`);
  return { project, repo };
}

/** For github_clone: "robot_tour" or "AdamHikl/robot_tour" (the owner's only). */
export function checkCloneName(config, name) {
  if (typeof name !== "string") throw new Error("repo must be a repo name, e.g. robot_tour");
  let project = name;
  if (name.includes("/")) {
    const [owner, rest] = name.split("/", 2);
    if (!config.owner || owner.toLowerCase() !== config.owner.toLowerCase() || name.split("/").length !== 2) {
      throw new Error(`only ${config.owner || "the configured owner"}'s repos can be cloned`);
    }
    project = rest;
  }
  return checkProject(config, project);
}

/** Checks a request. Returns {project, repo, branch, source} or throws with a reason Jorah can say. */
export function check(config, { project, branch }) {
  const { repo } = checkProject(config, project);
  if (typeof branch !== "string" || !BRANCH.test(branch) || branch.includes("..") || branch.endsWith(".lock")) {
    throw new Error("only branches named jorah/<task> can be pushed");
  }
  const work = realpathSync(config.workDir);
  const source = realpathSync(join(config.workDir, project));
  if (!source.startsWith(work + "/")) throw new Error("project folder must be inside ~/work");
  return { project, repo, branch, source };
}

export function readKey(path) {
  if (statSync(path).mode & 0o077) throw new Error("the App's key file must be readable by its owner only");
  const key = readFileSync(path, "utf8");
  if (!key.includes("PRIVATE KEY")) throw new Error("the App's key file holds no private key");
  return key;
}

function lexists(path) {
  try { lstatSync(path); return true; } catch { return false; }
}

const b64url = (data) => Buffer.from(data).toString("base64url");

/** A 9-minute JSON Web Token proving "I am this App", signed with its private key. */
export function appJwt(appId, key, now = Date.now()) {
  const iat = Math.floor(now / 1000) - 60;
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = b64url(JSON.stringify({ iat, exp: iat + 540, iss: appId }));
  const signature = createSign("RSA-SHA256").update(`${head}.${body}`).sign(key);
  return `${head}.${body}.${b64url(signature)}`;
}

const API = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "jorah-github" };

export const WRITE = Object.freeze({ contents: "write", pull_requests: "write" });
export const READ = Object.freeze({ contents: "read" });

/** A 1-hour token for one repo, with only the given permissions (default: push and pull requests). */
export async function repoToken(config, repo, { fetchImpl = fetch, now = Date.now(), permissions = WRITE } = {}) {
  if (!config.appId) throw new Error("the App's ID isn't set");
  const jwt = appJwt(config.appId, readKey(config.keyFile), now);
  const headers = { ...API, Authorization: `Bearer ${jwt}` };
  const found = await fetchImpl(`https://api.github.com/repos/${repo}/installation`, { headers });
  if (found.status === 404) throw new Error(`jorah-bot isn't installed on ${repo}`);
  if (!found.ok) throw new Error(`GitHub said ${found.status} finding the App on ${repo}`);
  const { id } = await found.json();
  const res = await fetchImpl(`https://api.github.com/app/installations/${id}/access_tokens`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ repositories: [repo.split("/")[1]], permissions }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.token) throw new Error(`GitHub said ${res.status} making a token: ${data.message ?? "no reason given"}`);
  return data.token;
}

// Settings for every git call: ignore global and system config, no hooks, no prompts, no helpers.
function gitEnv(extra = {}) {
  return {
    PATH: "/usr/bin:/bin",
    HOME: "/nonexistent",
    GIT_CONFIG_NOSYSTEM: "1",
    GIT_CONFIG_GLOBAL: "/dev/null",
    GIT_TERMINAL_PROMPT: "0",
    LANG: "C",
    ...extra,
  };
}
const SAFE = ["-c", "core.hooksPath=/dev/null", "-c", "credential.helper=", "-c", "protocol.file.allow=always"];

async function git(args, opts = {}) {
  const { stdout } = await run("git", [...SAFE, ...args], { env: gitEnv(opts.env), cwd: opts.cwd, timeout: opts.timeout ?? 120000, maxBuffer: 4 << 20 });
  return stdout.trim();
}

/** Fetch the branch from the untrusted work repo into this plugin's own bare mirror. */
export async function mirrorBranch(config, { project, repo, branch, source }, { remoteBase = "https://github.com/" } = {}) {
  mkdirSync(config.mirrorDir, { recursive: true, mode: 0o700 });
  const mirror = join(config.mirrorDir, `${project}.git`);
  if (!existsSync(mirror)) await git(["init", "--bare", "--quiet", mirror]);
  // Only this repo, set every time, so a stale or edited remote can't redirect the push.
  await git(["--git-dir", mirror, "config", "remote.origin.url", `${remoteBase}${repo}.git`]);
  await git(["--git-dir", mirror, "fetch", "--no-tags", "--quiet", source, `+refs/heads/${branch}:refs/heads/${branch}`]);
  const head = await git(["--git-dir", mirror, "rev-parse", `refs/heads/${branch}`]);
  const log = await git(["--git-dir", mirror, "log", "--format=%h %s", "-n", "10", `refs/heads/${branch}`]);
  return { mirror, head, log };
}

function writeAskpass(config) {
  const askpass = join(config.mirrorDir, "askpass.sh");
  writeFileSync(askpass, '#!/bin/sh\ncase "$1" in Username*) printf %s "$JORAH_GH_USER";; *) printf %s "$JORAH_GH_TOKEN";; esac\n', { mode: 0o700 });
  return askpass;
}

/**
 * Refresh the mirror from GitHub: every branch lands under refs/remotes/github/*, apart from the
 * refs/heads/jorah/* branches waiting to be pushed. The work repo then fetches from the mirror
 * inside Claude Code's sandbox (remote "github"), with no network and no token.
 */
export async function syncMirror(config, { project, repo }, token, { gitImpl = git, remoteBase = "https://github.com/" } = {}) {
  mkdirSync(config.mirrorDir, { recursive: true, mode: 0o700 });
  const mirror = join(config.mirrorDir, `${project}.git`);
  if (!existsSync(mirror)) await gitImpl(["init", "--bare", "--quiet", mirror]);
  // remoteBase is a test seam only; nothing in the plugin's config can change it.
  await gitImpl(["--git-dir", mirror, "config", "remote.origin.url", `${remoteBase}${repo}.git`]);
  const askpass = writeAskpass(config);
  await gitImpl(["--git-dir", mirror, "fetch", "--prune", "--no-tags", "--quiet", "origin", "+refs/heads/*:refs/remotes/github/*"], {
    env: { GIT_ASKPASS: askpass, JORAH_GH_USER: "x-access-token", JORAH_GH_TOKEN: token },
    timeout: 10 * 60 * 1000,
  });
  const branches = await gitImpl(["--git-dir", mirror, "for-each-ref", "--format=%(refname:lstrip=3) %(objectname:short)", "refs/remotes/github/"]);
  return { mirror, branches: String(branches ?? "").split("\n").filter(Boolean) };
}

/** Push from the mirror. Never forced: GitHub refuses anything that isn't a fast-forward. */
export async function pushBranch(config, target, token, { gitImpl = git } = {}) {
  const { mirror } = target;
  const askpass = writeAskpass(config);
  await gitImpl(["--git-dir", mirror, "push", "--porcelain", "origin", `refs/heads/${target.branch}:refs/heads/${target.branch}`], {
    env: { GIT_ASKPASS: askpass, JORAH_GH_USER: "x-access-token", JORAH_GH_TOKEN: token },
    timeout: 10 * 60 * 1000,
  });
  return { pushed: `${target.repo}:${target.branch}` };
}

/** The repo's default branch, from the API. */
export async function defaultBranch(repo, token, fetchImpl = fetch) {
  const info = await fetchImpl(`https://api.github.com/repos/${repo}`, { headers: { ...API, Authorization: `Bearer ${token}` } });
  if (!info.ok) throw new Error(`GitHub said ${info.status} reading ${repo}`);
  const name = (await info.json()).default_branch;
  if (typeof name !== "string" || !name || name.startsWith("-") || name.includes("..")) throw new Error(`GitHub gave no usable default branch for ${repo}`);
  return name;
}

// A branch name outside jorah/**: the "jorah: only jorah/**" ruleset must cover it as well.
export const PROBE_BRANCH = "jorah-bot-rules-probe";

async function branchRules(repo, branch, token, fetchImpl) {
  const path = branch.split("/").map(encodeURIComponent).join("/");
  const res = await fetchImpl(`https://api.github.com/repos/${repo}/rules/branches/${path}?per_page=100`, { headers: { ...API, Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`couldn't read ${repo}'s branch rules (GitHub said ${res.status}), so nothing was pushed`);
  const rules = await res.json().catch(() => null);
  if (!Array.isArray(rules)) throw new Error(`GitHub's answer about ${repo}'s branch rules made no sense, so nothing was pushed`);
  return new Set(rules.map((r) => r?.type).filter((t) => typeof t === "string"));
}

/**
 * Live check, with the installation token, right before every push and pull request: the default
 * branch must refuse updates, and a branch outside jorah/** must refuse creation and updates. That
 * is what the "jorah: only jorah/**" ruleset does. Without it, the repo is sync-only. Fails closed.
 */
export async function checkRules(repo, token, { fetchImpl = fetch, branch } = {}) {
  const main = branch ?? (await defaultBranch(repo, token, fetchImpl));
  const notProtected = `this repo isn't protected yet: ${repo} has no "jorah: only jorah/**" ruleset`;
  const onMain = await branchRules(repo, main, token, fetchImpl);
  if (!onMain.has("update")) throw new Error(`${notProtected} (its ${main} branch accepts updates), so Jorah can only sync it`);
  const onProbe = await branchRules(repo, PROBE_BRANCH, token, fetchImpl);
  if (!onProbe.has("creation") || !onProbe.has("update")) throw new Error(`${notProtected} (branches outside jorah/** aren't covered), so Jorah can only sync it`);
  return { defaultBranch: main, rules: [...onMain].sort() };
}

export async function openPullRequest(config, { repo, branch }, { title, body, base }, token, fetchImpl = fetch) {
  const headers = { ...API, Authorization: `Bearer ${token}` };
  const target = base || (await defaultBranch(repo, token, fetchImpl));
  const res = await fetchImpl(`https://api.github.com/repos/${repo}/pulls`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ title, body: `${body ?? ""}\n\nOpened by Jorah, approved by Adam.`.trim(), head: branch, base: target, draft: true }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`GitHub said ${res.status}: ${data.message ?? "no reason given"}`);
  return { url: data.html_url, number: data.number, base: target };
}

// Hidden from `git status` in the work repo's own .git/info/exclude: the placeholder files Claude
// Code's sandbox mounts into the repo while a job runs. Same list as scripts/pc/prepare-work-repo.sh.
export const EXCLUDE_MARKER = "# Claude Code sandbox placeholders (jorah prepare-work-repo.sh)";
const PLACEHOLDERS = ["/.bash_profile", "/.bashrc", "/.profile", "/.zprofile", "/.zshrc", "/.gitconfig", "/.ripgreprc", "/.mcp.json", "/.idea", "/.vscode", "/.claude/agents", "/.claude/commands", "/.claude/hooks", "/.claude/launch.json", "/.claude/loop.md", "/.claude/output-styles"];

/**
 * Make ~/work/<project> from the plugin's mirror (already synced from GitHub): remote "github"
 * reads the mirror, the default branch is checked out, sandbox placeholders are excluded. Refuses
 * if the folder exists. No token and no network: the mirror is a local path.
 */
export async function cloneFromMirror(config, { project, repo }, { mirror, branch }, { gitImpl = git } = {}) {
  const dest = join(config.workDir, project);
  if (lexists(dest)) throw new Error(`~/work/${project} already exists; use github_sync to update it`);
  if (!existsSync(join(mirror, "HEAD"))) throw new Error(`no mirror of ${repo} yet`);
  mkdirSync(config.workDir, { recursive: true });
  await gitImpl(["init", "--quiet", "-b", branch, dest]);
  try {
    await gitImpl(["-C", dest, "remote", "add", "github", mirror]);
    await gitImpl(["-C", dest, "config", "remote.github.fetch", "+refs/remotes/github/*:refs/remotes/github/*"]);
    await gitImpl(["-C", dest, "fetch", "--no-tags", "--quiet", "github"], { timeout: 10 * 60 * 1000 });
    await gitImpl(["-C", dest, "checkout", "--quiet", "--no-track", "-B", branch, `refs/remotes/github/${branch}`]);
    const exclude = join(dest, ".git", "info", "exclude");
    mkdirSync(join(dest, ".git", "info"), { recursive: true });
    const before = existsSync(exclude) ? readFileSync(exclude, "utf8") : "";
    if (!before.includes(EXCLUDE_MARKER)) writeFileSync(exclude, `${before}${before && !before.endsWith("\n") ? "\n" : ""}${EXCLUDE_MARKER}\n${PLACEHOLDERS.join("\n")}\n`);
  } catch (error) {
    // Leave no half-made folder behind, so a retry isn't refused as "already exists".
    rmSync(dest, { recursive: true, force: true });
    throw error;
  }
  const head = await gitImpl(["-C", dest, "log", "--format=%h %s", "-n", "1", "HEAD"]);
  return { path: dest, branch, head };
}

/** Text for Adam's approval prompt. */
export function describe(toolName, params, config) {
  let repo = "a repo Jorah may not use";
  try { repo = checkProject(config, params?.project).repo; } catch { /* stays as above */ }
  if (toolName === "github_open_pr") return `Open a draft pull request on ${repo} from ${params?.branch}: "${params?.title ?? ""}"`;
  return `Push branch ${params?.branch} from ~/work/${params?.project} to ${repo}`;
}

// The tools' whole flows, with GitHub and git swappable so tests can use a stand-in GitHub.
// `remoteBase` is a test seam only; nothing in the plugin's config can change it.

/** github_push_branch: name and folder checks, live rule check, mirror, push. */
export async function pushFlow(config, p, { fetchImpl = fetch, gitImpl, remoteBase } = {}) {
  const target = check(config, p);
  const token = await repoToken(config, target.repo, { fetchImpl });
  await checkRules(target.repo, token, { fetchImpl });
  const mirrored = await mirrorBranch(config, target, remoteBase ? { remoteBase } : {});
  const result = await pushBranch(config, { ...target, ...mirrored }, token, gitImpl ? { gitImpl } : {});
  return { target, mirrored, result };
}

/** github_open_pr: name and folder checks, live rule check, draft pull request. */
export async function prFlow(config, p, { fetchImpl = fetch } = {}) {
  const target = check(config, p);
  const token = await repoToken(config, target.repo, { fetchImpl });
  await checkRules(target.repo, token, { fetchImpl });
  return { target, pr: await openPullRequest(config, target, p, token, fetchImpl) };
}

/** github_sync: read-only token, every branch into the mirror. */
export async function syncFlow(config, project, { fetchImpl = fetch, remoteBase } = {}) {
  const target = checkProject(config, project);
  const token = await repoToken(config, target.repo, { fetchImpl, permissions: READ });
  return { target, synced: await syncMirror(config, target, token, remoteBase ? { remoteBase } : {}) };
}

/** github_clone: read-only token, sync the mirror, then make ~/work/<repo> from the mirror. */
export async function cloneFlow(config, name, { fetchImpl = fetch, remoteBase } = {}) {
  const target = checkCloneName(config, name);
  if (lexists(join(config.workDir, target.project))) throw new Error(`~/work/${target.project} already exists; use github_sync to update it`);
  const token = await repoToken(config, target.repo, { fetchImpl, permissions: READ });
  const branch = await defaultBranch(target.repo, token, fetchImpl);
  const synced = await syncMirror(config, target, token, remoteBase ? { remoteBase } : {});
  const cloned = await cloneFromMirror(config, target, { mirror: synced.mirror, branch });
  return { target, synced, cloned };
}
