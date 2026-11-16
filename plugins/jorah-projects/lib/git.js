// "The line's commits not yet on GitHub" (docs/plan/11-project-mode.md section 5): commits on the
// project's branch that no `github/*` ref has, as of the work repo's last fetch. The work repo is
// untrusted (runs write it), so git runs with no hooks, no fsmonitor, no system or global config,
// no pager and no prompt, and only read-only plumbing (rev-parse, rev-list).

import { execFile } from "node:child_process";

const TIMEOUT_MS = 5000;

function git(workDir, args, gitBin = "git") {
  return new Promise((resolve) => {
    execFile(gitBin, ["-C", workDir, "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "--no-pager", ...args], {
      timeout: TIMEOUT_MS,
      maxBuffer: 64 * 1024,
      env: {
        PATH: process.env.PATH ?? "/usr/bin:/bin",
        HOME: "/nonexistent",
        GIT_CONFIG_NOSYSTEM: "1",
        GIT_CONFIG_GLOBAL: "/dev/null",
        GIT_TERMINAL_PROMPT: "0",
        GIT_OPTIONAL_LOCKS: "0",
        LC_ALL: "C",
      },
    }, (error, stdout) => resolve({ ok: !error, code: error?.code ?? 0, out: String(stdout ?? "").trim() }));
  });
}

/**
 * { status: "ok", count, as_of: "the last fetch" } | { status: "no-branch" } | { status: "unknown", reason }.
 * A missing branch is said as such, never as 0 commits.
 */
export async function unpushed(workDir, branch, gitBin) {
  const head = await git(workDir, ["rev-parse", "--verify", "--quiet", `refs/heads/${branch}^{commit}`], gitBin);
  if (!head.ok) {
    const repo = await git(workDir, ["rev-parse", "--git-dir"], gitBin);
    if (!repo.ok) return { status: "unknown", reason: "the project folder isn't a readable git repo" };
    return { status: "no-branch", reason: `${branch} doesn't exist yet` };
  }
  const n = await git(workDir, ["rev-list", "--count", `refs/heads/${branch}`, "--not", "--remotes=github"], gitBin);
  if (!n.ok || !/^\d+$/.test(n.out)) return { status: "unknown", reason: "git couldn't count the commits" };
  const remotes = await git(workDir, ["for-each-ref", "--count=1", "--format=%(refname)", "refs/remotes/github/"], gitBin);
  if (remotes.ok && remotes.out === "") return { status: "unknown", reason: "the work repo has no github/* refs yet, so nothing to compare with" };
  return { status: "ok", count: Number(n.out), as_of: "the work repo's last fetch from Jorah's mirror" };
}
