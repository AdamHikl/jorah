// The checks and git plumbing behind Jorah's GitHub tools. No OpenClaw imports, so it tests alone.
//
// Safety model:
// - Only branches named jorah/<something> are pushed, never forced, only to a repo Adam listed.
// - The work repo was written by a sandboxed Claude Code session, so it is untrusted: its hooks and
//   .git/config could run code or redirect the push. Nothing runs inside it except a fetch *from*
//   it into a mirror this plugin owns (git treats serving a fetch from an untrusted repo as safe).
//   The push runs from that mirror, with hooks off, no credential helper and the token supplied
//   through GIT_ASKPASS to that one process.
// - GitHub rulesets on each repo enforce jorah/** server-side too (scripts/github/protect-repo.sh).

import { execFile } from "node:child_process";
import { mkdirSync, readFileSync, realpathSync, statSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);

export const DEFAULTS = Object.freeze({
  tokenFile: "/home/jorah/.config/jorah-github/token",
  workDir: "/home/jorah/work",
  mirrorDir: "/home/jorah/.jorah-github/mirrors",
});

const BRANCH = /^jorah\/[A-Za-z0-9][A-Za-z0-9._-]*(\/[A-Za-z0-9][A-Za-z0-9._-]*)*$/;
const REPO = /^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/;
const PROJECT = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

export function settings(pluginConfig = {}) {
  const repos = pluginConfig.repos && typeof pluginConfig.repos === "object" ? pluginConfig.repos : {};
  for (const [project, repo] of Object.entries(repos)) {
    if (!PROJECT.test(project) || !REPO.test(repo)) throw new Error(`jorah-github: bad repos entry ${project}`);
  }
  return {
    account: typeof pluginConfig.account === "string" ? pluginConfig.account : "",
    tokenFile: pluginConfig.tokenFile ?? DEFAULTS.tokenFile,
    workDir: pluginConfig.workDir ?? DEFAULTS.workDir,
    mirrorDir: pluginConfig.mirrorDir ?? DEFAULTS.mirrorDir,
    repos,
  };
}

/** Checks a request. Returns {project, repo, branch, source} or throws with a reason Jorah can say. */
export function check(config, { project, branch }) {
  if (typeof project !== "string" || !PROJECT.test(project)) throw new Error("project must be a folder name under ~/work");
  const repo = config.repos[project];
  if (!repo) throw new Error(`${project} isn't on Adam's list of repos Jorah may push to`);
  if (typeof branch !== "string" || !BRANCH.test(branch) || branch.includes("..") || branch.endsWith(".lock")) {
    throw new Error("only branches named jorah/<task> can be pushed");
  }
  const work = realpathSync(config.workDir);
  const source = realpathSync(join(config.workDir, project));
  if (!source.startsWith(work + "/")) throw new Error("project folder must be inside ~/work");
  return { project, repo, branch, source };
}

export function readToken(path) {
  if (statSync(path).mode & 0o077) throw new Error("token file must be readable by its owner only");
  const token = readFileSync(path, "utf8").trim();
  if (token.length < 20) throw new Error("token file holds no token");
  return token;
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
export async function mirrorBranch(config, { project, repo, branch, source }) {
  mkdirSync(config.mirrorDir, { recursive: true, mode: 0o700 });
  const mirror = join(config.mirrorDir, `${project}.git`);
  if (!existsSync(mirror)) await git(["init", "--bare", "--quiet", mirror]);
  // Only this repo, set every time, so a stale or edited remote can't redirect the push.
  await git(["--git-dir", mirror, "config", "remote.origin.url", `https://github.com/${repo}.git`]);
  await git(["--git-dir", mirror, "fetch", "--no-tags", "--quiet", source, `+refs/heads/${branch}:refs/heads/${branch}`]);
  const head = await git(["--git-dir", mirror, "rev-parse", `refs/heads/${branch}`]);
  const log = await git(["--git-dir", mirror, "log", "--format=%h %s", "-n", "10", `refs/heads/${branch}`]);
  return { mirror, head, log };
}

/** Push from the mirror. Never forced: GitHub refuses anything that isn't a fast-forward. */
export async function pushBranch(config, target, token, { gitImpl = git } = {}) {
  const { mirror } = target;
  const askpass = join(config.mirrorDir, "askpass.sh");
  writeFileSync(askpass, '#!/bin/sh\ncase "$1" in Username*) printf %s "$JORAH_GH_USER";; *) printf %s "$JORAH_GH_TOKEN";; esac\n', { mode: 0o700 });
  await gitImpl(["--git-dir", mirror, "push", "--porcelain", "origin", `refs/heads/${target.branch}:refs/heads/${target.branch}`], {
    env: { GIT_ASKPASS: askpass, JORAH_GH_USER: config.account || "x-access-token", JORAH_GH_TOKEN: token },
  });
  return { pushed: `${target.repo}:${target.branch}` };
}

export async function openPullRequest(config, { repo, branch }, { title, body, base }, token, fetchImpl = fetch) {
  const headers = { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "jorah-github" };
  let target = base;
  if (!target) {
    const info = await fetchImpl(`https://api.github.com/repos/${repo}`, { headers });
    if (!info.ok) throw new Error(`GitHub said ${info.status} reading ${repo}`);
    target = (await info.json()).default_branch;
  }
  const res = await fetchImpl(`https://api.github.com/repos/${repo}/pulls`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ title, body: `${body ?? ""}\n\nOpened by Jorah, approved by Adam.`.trim(), head: branch, base: target, draft: true }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`GitHub said ${res.status}: ${data.message ?? "no reason given"}`);
  return { url: data.html_url, number: data.number, base: target };
}

/** Text for Adam's approval prompt. */
export function describe(toolName, params, config) {
  const repo = config.repos?.[params?.project] ?? "a repo not on the list";
  if (toolName === "github_open_pr") return `Open a draft pull request on ${repo} from ${params?.branch}: "${params?.title ?? ""}"`;
  return `Push branch ${params?.branch} from ~/work/${params?.project} to ${repo}`;
}
