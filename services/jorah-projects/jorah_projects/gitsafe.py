"""Git in a work repo that a sandboxed Claude Code run wrote, run by the runner outside the sandbox.

The repo is untrusted. Its .git/config could name hooks, an fsmonitor, filter or merge drivers, an
ssh command or an include: any of them would run code as jorah outside the sandbox. So:

- Before any git command, .git/config is parsed as a plain file (`git config --file`, which runs
  nothing) and every key must be on ALLOWED. Anything else refuses the run. `.git` must be a real
  folder (not a `gitdir:` file) with no `commondir`, and no `config.worktree` but an empty one:
  Claude Code's sandbox leaves an empty `.git/config.worktree` behind in every repo it works in
  (seen in all of ~/work on 2026-11-21), and git reads that file only with
  extensions.worktreeConfig, which ALLOWED refuses.
- Every git command, and every git that gitleaks starts, gets global and system config switched
  off and the dangerous keys pinned through GIT_CONFIG_COUNT (hooks to /dev/null, no fsmonitor, no
  pager, no credential helper, no editor).
"""

import os
import re
import subprocess
from pathlib import Path

RUNNER_NAME = "Jorah runner"
RUNNER_EMAIL = "jorah@localhost"

PINNED = [
    ("core.hooksPath", "/dev/null"),
    ("core.fsmonitor", "false"),
    ("core.pager", "cat"),
    ("core.editor", "true"),
    ("core.sshCommand", "false"),
    ("core.askPass", ""),
    ("credential.helper", ""),
    ("diff.external", ""),
    ("merge.renormalize", "false"),
    ("commit.gpgSign", "false"),
    ("tag.gpgSign", "false"),
    ("gc.auto", "0"),
    ("maintenance.auto", "false"),
    ("protocol.allow", "never"),
    ("protocol.file.allow", "always"),
    ("submodule.recurse", "false"),
    ("safe.bareRepository", "explicit"),
]

ALLOWED = [
    re.compile(r"^core\.(repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode|symlinks)$"),
    re.compile(r"^extensions\.objectformat$"),
    re.compile(r"^remote\.(github|origin)\.(url|fetch)$"),
    re.compile(r"^branch\..+\.(remote|merge)$"),
    re.compile(r"^jorah\.[a-z0-9]+$"),
    re.compile(r"^user\.(name|email)$"),
]


class GitError(RuntimeError):
    pass


class UnsafeRepo(RuntimeError):
    pass


def base_env(home):
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_AUTHOR_NAME": RUNNER_NAME,
        "GIT_AUTHOR_EMAIL": RUNNER_EMAIL,
        "GIT_COMMITTER_NAME": RUNNER_NAME,
        "GIT_COMMITTER_EMAIL": RUNNER_EMAIL,
        "GIT_CONFIG_COUNT": str(len(PINNED)),
    }
    for i, (key, value) in enumerate(PINNED):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    return env


class Repo:
    def __init__(self, path, *, home, mirror=None, git="git"):
        self.path = Path(path)
        self.home = Path(home)
        self.mirror = str(mirror) if mirror else None
        self.git_bin = git

    @property
    def env(self):
        return base_env(self.home)

    def check_config(self):
        """Refuse a repo whose git setup could run code or point somewhere else."""
        dot = self.path / ".git"
        if dot.is_symlink() or not dot.is_dir():
            raise UnsafeRepo(".git isn't a plain folder")
        for name in ("config.worktree", "commondir"):
            path = dot / name
            if path.is_symlink():
                raise UnsafeRepo(f".git/{name} is a link")
            if not path.exists():
                continue
            # The sandbox's leftover: empty, so it holds nothing even if git read it.
            if name == "config.worktree" and path.is_file() and path.stat().st_size == 0:
                continue
            raise UnsafeRepo(f".git/{name} exists")
        config = dot / "config"
        if config.is_symlink() or not config.is_file():
            raise UnsafeRepo(".git/config isn't a plain file")
        out = subprocess.run(
            [self.git_bin, "config", "--file", str(config), "--no-includes", "--null", "--list"],
            capture_output=True, env=self.env, timeout=30, check=False,
        )
        if out.returncode != 0:
            raise UnsafeRepo(".git/config can't be parsed")
        bad = []
        for entry in out.stdout.decode("utf-8", "replace").split("\0"):
            if not entry:
                continue
            key, _, value = entry.partition("\n")
            key = key.lower()
            if not any(p.match(key) for p in ALLOWED):
                bad.append(key[:60])
            elif key == "remote.github.url" and self.mirror and value != self.mirror:
                bad.append("remote.github.url (not the jorah-github mirror)")
        if bad:
            raise UnsafeRepo(f".git/config has keys the runner doesn't allow: {', '.join(sorted(set(bad))[:8])}")

    def run(self, *args, check=True, timeout=600, input_bytes=None):
        result = subprocess.run(
            [self.git_bin, "-C", str(self.path), *args],
            capture_output=True, env=self.env, timeout=timeout, check=False, input=input_bytes,
        )
        if check and result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip().splitlines()
            raise GitError(f"git {args[0]} failed: {message[-1][:200] if message else result.returncode}")
        return result

    def out(self, *args, **kw):
        return self.run(*args, **kw).stdout.decode("utf-8", "replace").strip()

    # ---- queries ---------------------------------------------------------------------------------

    def head(self):
        r = self.run("rev-parse", "--verify", "-q", "HEAD", check=False)
        return r.stdout.decode().strip() or None

    def current_branch(self):
        r = self.run("symbolic-ref", "-q", "--short", "HEAD", check=False)
        return r.stdout.decode().strip() or None

    def ref_exists(self, ref):
        return self.run("rev-parse", "--verify", "-q", ref, check=False).returncode == 0

    def resolve(self, ref):
        r = self.run("rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False)
        return r.stdout.decode().strip() or None

    def dirty(self):
        return bool(self.out("status", "--porcelain", "--untracked-files=all"))

    def merging(self):
        return (self.path / ".git" / "MERGE_HEAD").exists()

    def conflicted_files(self):
        return [f for f in self.out("diff", "--name-only", "--diff-filter=U").splitlines() if f]

    def show(self, rev, rel):
        """Bytes of `rel` at `rev`, or None if absent (or a link/not a file at that commit)."""
        r = self.run("ls-tree", "-z", rev, "--", rel, check=False)
        entry = r.stdout.decode("utf-8", "replace").strip("\0")
        if r.returncode != 0 or not entry:
            return None
        mode = entry.split(" ", 1)[0]
        if mode not in ("100644", "100755"):
            return None
        return self.run("cat-file", "blob", f"{rev}:{rel}").stdout

    def is_ancestor(self, older, newer):
        return self.run("merge-base", "--is-ancestor", older, newer, check=False).returncode == 0

    def merge_base(self, a, b):
        r = self.run("merge-base", a, b, check=False)
        return r.stdout.decode().strip() or None

    def commits_since(self, start, limit=200):
        """[(sha, first line, [files])] on the first-parent line from start (exclusive) to HEAD."""
        rng = f"{start}..HEAD" if start else "HEAD"
        shas = self.out("rev-list", "--first-parent", f"--max-count={limit}", "--reverse", rng).split()
        commits = []
        for sha in shas:
            subject = self.out("log", "-1", "--format=%s", sha)
            files = self.out("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "-m", "--first-parent", sha).splitlines()
            commits.append({"sha": sha, "message": subject[:200], "files": sorted(set(f for f in files if f))[:200]})
        return commits

    # ---- changes ---------------------------------------------------------------------------------

    def commit_all(self, message):
        """Stage everything and commit as the runner. Returns the new sha, or None if nothing changed."""
        self.run("add", "-A")
        if self.run("diff", "--cached", "--quiet", check=False).returncode == 0:
            return None
        self.run("commit", "--no-verify", "--no-gpg-sign", "-q", "-m", message)
        return self.head()

    def commit_paths(self, message, paths):
        self.run("add", "-A", "--", *paths)
        if self.run("diff", "--cached", "--quiet", check=False).returncode == 0:
            return None
        self.run("commit", "--no-verify", "--no-gpg-sign", "-q", "-m", message)
        return self.head()


# Hidden from `git status` in a work repo's own .git/info/exclude: the placeholder files Claude Code's
# sandbox mounts into the repo while a run goes. The same list as scripts/pc/prepare-work-repo.sh
# and jorah-github's cloneFromMirror.
EXCLUDE_MARKER = "# Claude Code sandbox placeholders (jorah prepare-work-repo.sh)"
PLACEHOLDERS = ["/.bash_profile", "/.bashrc", "/.profile", "/.zprofile", "/.zshrc", "/.gitconfig", "/.ripgreprc", "/.mcp.json",
                "/.idea", "/.vscode", "/.claude/agents", "/.claude/commands", "/.claude/hooks", "/.claude/launch.json",
                "/.claude/loop.md", "/.claude/output-styles"]


def init_local(path, *, home, git="git", branch="main", message):
    """A new local repo for a project with no GitHub repo yet: `git init` with no template (no
    sample hooks), the sandbox placeholders excluded, one empty first commit. Refuses an existing
    path. Returns a Repo."""
    path = Path(path)
    if os.path.lexists(path):
        raise UnsafeRepo(f"{path} already exists")
    env = base_env(home)
    done = subprocess.run([git, "init", "-q", "--template=", "-b", branch, str(path)], capture_output=True, env=env, timeout=60, check=False)
    if done.returncode != 0:
        raise GitError("git init failed")
    info = path / ".git" / "info"
    info.mkdir(exist_ok=True)
    (info / "exclude").write_text(EXCLUDE_MARKER + "\n" + "\n".join(PLACEHOLDERS) + "\n", encoding="utf-8")
    repo = Repo(path, home=home, git=git)
    repo.run("commit", "--allow-empty", "--no-verify", "--no-gpg-sign", "-q", "-m", message)
    return repo


def mirror_path(mirror_dir, work_dir):
    return os.path.join(str(mirror_dir), f"{Path(work_dir).name}.git")
