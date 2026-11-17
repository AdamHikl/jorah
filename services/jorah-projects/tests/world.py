"""A small world for the runner's tests: a local bare repo as GitHub, jorah-github's mirror, the work
clone in ~/work, a stand-in `claude` that edits and commits as told, and a stand-in sync command.

Nothing here needs the network, a model or an install beyond git, PyYAML and (for the secret
tests) gitleaks.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SERVICE = HERE.parent
REPO_ROOT = SERVICE.parents[1]
sys.path.insert(0, str(SERVICE))

from jorah_projects import claude, config, contract, fsio, runner  # noqa: E402

CONTRACT = REPO_ROOT / "packages/contracts/project"  # WS1's jorah-project-v1, the real one
TZ = ZoneInfo("Europe/Bratislava")
GIT_ID = {"GIT_AUTHOR_NAME": "Adam", "GIT_AUTHOR_EMAIL": "adam@example.invalid",
          "GIT_COMMITTER_NAME": "Adam", "GIT_COMMITTER_EMAIL": "adam@example.invalid",
          "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}

CHARTER = "# Charter\n\nMission: water trees.\n\n## Decision rights\n\nJorah decides software. Adam keeps money.\n"
BACKLOG = {"version": 1, "items": [
    {"id": "T-0001", "title": "Size the drive motors", "track": "eng", "status": "ready", "priority": 2,
     "depends_on": [], "blocked_on": None, "acceptance": "Torque per wheel", "evidence": [],
     "created": "2026-11-16", "updated": "2026-11-16"},
    {"id": "T-0002", "title": "Time the tap's flow", "track": "adam", "status": "blocked", "priority": 3, "adam_task": "A-0001",
     "depends_on": [], "blocked_on": "A-0001", "acceptance": "Three times", "evidence": [],
     "created": "2026-11-16", "updated": "2026-11-16"},
]}
QUESTIONS = {"version": 1, "questions": [
    {"id": "Q-0001", "asked": "2026-11-16", "question": "Who is the first customer?", "why_it_matters": "Size and price",
     "options": [{"key": "A", "text": "Garden owners", "consequence": "Small"}, {"key": "B", "text": "Landscaping firms", "consequence": "Labour"}],
     "recommendation": "B", "default_if_silent": None, "decide_by": "2026-11-20", "status": "open", "answer": None},
    {"id": "Q-0002", "asked": "2026-11-16", "question": "Hours a week for hands-on tasks?", "why_it_matters": "Planning",
     "options": [{"key": "A", "text": "Weekends, 2 hours", "consequence": "Two tasks a week"}, {"key": "B", "text": "More", "consequence": "Faster build"}],
     "recommendation": "A", "default_if_silent": "A", "decide_by": "2026-11-18", "status": "open", "answer": None},
]}
TASKS = {"version": 1, "tasks": [
    {"id": "A-0001", "title": "Time the tap's flow", "why": "Fill time", "when": "Any day, 10 minutes",
     "steps": ["Fill a 10 L bucket", "Time it"], "materials": ["bucket"], "send_back": "Three times", "status": "open", "result": None},
]}

FAKE_CLAUDE = textwrap.dedent('''\
    #!{python}
    """Stand-in for Claude Code: does what behaviour.json beside it says, and speaks stream-json."""
    import json, os, subprocess, sys, time
    from pathlib import Path
    import yaml

    here = Path(__file__).resolve().parent
    brief = sys.stdin.read()
    with open(here / "calls.jsonl", "a") as log:
        log.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "brief": brief,
                              "env": {{k: os.environ.get(k) for k in ("CLAUDE_CONFIG_DIR", "HOME", "CLAUDE_CODE_TMPDIR", "PATH", "BENCH_MARK")}}}}) + "\\n")
    steps = json.loads((here / "behaviour.json").read_text())
    env = dict(os.environ, GIT_AUTHOR_NAME="Jorah", GIT_AUTHOR_EMAIL="jorah@localhost", GIT_COMMITTER_NAME="Jorah",
               GIT_COMMITTER_EMAIL="jorah@localhost", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    def git(*args):
        subprocess.run(["git", *args], check=True, env=env, capture_output=True)
    def out(obj):
        print(json.dumps(obj), flush=True)
    out({{"type": "system", "subtype": "init", "session_id": "fake"}})
    code, result = 0, {{"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "terminal_reason": "completed", "result": "done"}}
    for step in steps:
        op = step["op"]
        if op == "write":
            p = Path(step["path"]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(step["text"])
        elif op == "yaml":
            p = Path(step["file"]); doc = yaml.safe_load(p.read_text())
            lst = doc[step["list"]]
            for item in lst:
                if item["id"] == step["id"]:
                    item.update(step["set"])
            p.write_text(yaml.safe_dump(doc, sort_keys=False))
        elif op == "yaml_add":
            p = Path(step["file"]); doc = yaml.safe_load(p.read_text())
            doc[step["list"]].append(step["item"]); p.write_text(yaml.safe_dump(doc, sort_keys=False))
        elif op == "commit":
            git("add", "-A"); git("commit", "-q", "-m", step["message"])
        elif op == "git":
            git(*step["args"])
        elif op == "emit":
            out(step["line"])
        elif op == "sleep":
            time.sleep(step["seconds"])
        elif op == "exit":
            code = step["code"]
        elif op == "result":
            result.update(step["set"])
    out({{"type": "assistant", "message": {{"content": [{{"type": "text", "text": "working"}}]}}}})
    out(result)
    sys.exit(code)
''')

FAKE_SYNC = textwrap.dedent('''\
    #!{python}
    """Stand-in for jorah-github-sync.mjs [sync|clone]: fetch the bare "GitHub" into the mirror (and for
    clone make the work folder from it, as cloneFromMirror does), print one JSON line."""
    import json, os, subprocess, sys
    argv = sys.argv[1:]
    action = argv.pop(0) if argv and not argv[0].startswith("--") else "sync"
    args = dict(zip(argv[0::2], argv[1::2]))
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "sync-calls.jsonl"), "a") as log:
        log.write(json.dumps([action, *argv]) + "\\n")
    if os.path.exists(os.path.join(here, "sync-fails")):
        print(json.dumps({{"ok": False, "error": "GitHub said 502"}})); sys.exit(1)
    gh = os.path.join(here, "github", args["--repo"] + ".git")
    if not os.path.exists(gh):
        print(json.dumps({{"ok": False, "error": "there's no repo named " + args["--repo"]}})); sys.exit(1)
    mirror = os.path.join(args["--mirror-dir"], args["--project"] + ".git")
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="x", GIT_AUTHOR_EMAIL="x@x", GIT_COMMITTER_NAME="x", GIT_COMMITTER_EMAIL="x@x")
    def git(*a):
        subprocess.run(["git", *a], check=True, env=env, capture_output=True)
    if not os.path.exists(mirror):
        git("init", "--bare", "-q", mirror)
    git("--git-dir", mirror, "fetch", "-q", "--prune", gh, "+refs/heads/*:refs/remotes/github/*")
    git("--git-dir", mirror, "config", "jorah.defaultBranch", "main")
    out = {{"ok": True, "project": args["--project"], "repo": args["--repo"], "mirror": mirror, "defaultBranch": "main", "branches": 1}}
    if action == "clone":
        dest = os.path.join(args["--work-dir"], args["--project"])
        if os.path.lexists(dest):
            print(json.dumps({{"ok": False, "error": "already exists"}})); sys.exit(1)
        git("init", "-q", "-b", "main", dest)
        git("-C", dest, "remote", "add", "github", mirror)
        git("-C", dest, "config", "remote.github.fetch", "+refs/remotes/github/*:refs/remotes/github/*")
        git("-C", dest, "fetch", "-q", "github")
        git("-C", dest, "checkout", "-q", "--no-track", "-B", "main", "refs/remotes/github/main")
        out.update(path=dest, branch="main")
    print(json.dumps(out))
''')


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env={**os.environ, **GIT_ID}, capture_output=True, check=check, text=True)


class Clock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, **delta):
        self.at = self.at + timedelta(**delta)


class World:
    def __init__(self, name="robot", *, entry=None, files=None, clone=True, github=True):
        self.tmp = Path(tempfile.mkdtemp(prefix="jorah-projects-test-"))
        self.name = name
        self.repo = f"AdamHikl/{name}"
        home = self.tmp / "home"
        (home / ".jorah-guard").mkdir(parents=True)
        (home / "work").mkdir()
        (home / ".config/jorah-projects").mkdir(parents=True)
        self.tools = self.tmp / "tools"
        self.tools.mkdir()
        self.github = self.tools / "github" / f"{self.repo}.git"
        self.mirror_dir = home / ".jorah-github/mirrors"
        self.mirror_dir.mkdir(parents=True)
        self.work = home / "work" / name
        self.home = home

        # GitHub: main with the project folder (github=False: no repo yet, `make_github` later).
        self.seed = None
        if github:
            self.make_github(files if files is not None else self.default_files())

        # Tools.
        self.claude_bin = self.tools / "claude"
        self.claude_bin.write_text(FAKE_CLAUDE.format(python=sys.executable))
        self.claude_bin.chmod(0o755)
        self.behave([])
        sync = self.tools / "sync"
        sync.write_text(FAKE_SYNC.format(python=sys.executable))
        sync.chmod(0o755)

        # The work clone from the mirror, as github_clone makes it.
        self.mirror = self.mirror_dir / f"{name}.git"
        if clone:
            subprocess.run([str(sync), "clone", "--project", name, "--repo", self.repo, "--mirror-dir", str(self.mirror_dir),
                            "--work-dir", str(home / "work")], check=True, capture_output=True)
            (self.tools / "sync-calls.jsonl").unlink()

        cfg = home / ".claude-jorah"
        cfg.mkdir()
        for name in ("project-settings.json", "project-settings-web.json", "project-settings-setup.json", "project-settings-setup-web.json"):
            (cfg / name).write_text("{}")
        (home / "sandbox").mkdir()

        self.settings = config.Settings(
            registry=home / ".config/jorah-projects/projects.json",
            runner_file=home / ".config/jorah-projects/runner.json",
            state_root=home / ".jorah-projects", work_root=home / "work", mirror_dir=self.mirror_dir,
            freeze_file=home / ".jorah-guard/FROZEN", claude_bin=self.claude_bin, claude_config_dir=cfg,
            sandbox_dir=home / "sandbox", contracts=CONTRACT, gitleaks_bin=shutil.which("gitleaks") or "/nonexistent/gitleaks",
            sync_cmd=[str(sync)], git_bin=shutil.which("git"), github_app_id="5686503", github_owner="AdamHikl",
            kill_grace_seconds=1, bench_env={"robotics": self.tools / "bench-env.sh"}, require_root_owned_bench=False,
            templates=REPO_ROOT / "templates/project",
        )
        self.entry = {"repo": self.repo, "workDir": str(self.work), "branch": "jorah/line", "stateDir": "project",
                      "level": 0, "schedule": ["02:30", "10:30", "16:30"],
                      "limits": {"runsPerDay": 3, "minutesPerRun": 45, "maxTurns": 200}, "web": True, "bench": None, "paused": False}
        self.entry.update(entry or {})
        self.write_registry()
        self.clock = Clock(datetime(2026, 11, 17, 11, 0, tzinfo=TZ))
        self.free = 100 * 1024**3
        self.minutes = None
        self.logs = []

    def make_github(self, files):
        """Adam's repo on GitHub, a bare repo with `files` on main."""
        seed = self.tmp / "seed"
        seed.mkdir()
        git(seed, "init", "-q", "-b", "main")
        for rel, text in files.items():
            p = seed / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "Bootstrap project mode")
        self.github.parent.mkdir(parents=True, exist_ok=True)
        git(self.tmp, "clone", "-q", "--bare", str(seed), str(self.github))
        self.seed = seed
        git(seed, "remote", "add", "gh", str(self.github))

    def sync_calls(self):
        path = self.tools / "sync-calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def intake(self, text):
        """What the plugin's project_start writes."""
        inbox = self.state_dir / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "intake.md").write_text(text)

    @staticmethod
    def default_files():
        return {
            "README.md": "# Robot\n",
            "project/CHARTER.md": CHARTER,
            "project/backlog.yaml": fsio.dump_yaml(BACKLOG).decode(),
            "project/questions.yaml": fsio.dump_yaml(QUESTIONS).decode(),
            "project/adam-tasks.yaml": fsio.dump_yaml(TASKS).decode(),
            "project/DECISIONS.md": "# Decisions\n",
        }

    def write_registry(self):
        path = Path(self.settings.registry)
        path.write_text(json.dumps({self.name: self.entry}))
        path.chmod(0o600)

    def behave(self, steps):
        (self.tools / "behaviour.json").write_text(json.dumps(steps))

    def calls(self):
        path = self.tools / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def runner(self):
        def claude_run(settings, project, brief, *, minutes, setup=False):
            return claude.run(settings, project, brief, minutes=self.minutes if self.minutes is not None else minutes, setup=setup)
        return runner.Runner(self.settings, now=self.clock, disk_free=lambda _p: self.free, claude_run=claude_run, log=self.logs.append)

    @property
    def state_dir(self):
        return self.settings.project_state(self.name)

    def request(self, kind="run-now", rid=None):
        import uuid
        folder = self.state_dir / "requests"
        folder.mkdir(parents=True, exist_ok=True)
        rid = rid or str(uuid.uuid4())
        (folder / f"{rid}.json").write_text(json.dumps({"v": 1, "id": rid, "type": kind, "by": "adam", "at": "2026-11-17T10:00:00+01:00"}))
        return rid

    def tick(self):
        return self.runner().tick()

    def run_now(self):
        self.request()
        records = self.tick()
        assert len(records) == 1, (records, self.logs)
        return records[0]

    def outbox(self, record):
        return json.loads((self.state_dir / "outbox" / f"{record['id']}.json").read_text())

    def state(self):
        return json.loads((self.state_dir / "state.json").read_text())

    def usage(self):
        path = Path(self.settings.state_root) / "usage.json"
        return json.loads(path.read_text()) if path.exists() else None

    def yaml(self, rel):
        return fsio.parse_yaml((self.work / rel).read_bytes())

    def item(self, rel, list_name, item_id):
        return next(x for x in self.yaml(rel)[list_name] if x["id"] == item_id)

    def contract_problems(self):
        """WS1's own checker over the work tree's project folder."""
        return contract.load(CONTRACT).check_project(self.work / "project")

    def log(self, *args):
        return git(self.work, "log", *args).stdout

    def push_main(self, rel, text, message="Adam's change"):
        """Adam commits on GitHub's main."""
        p = self.seed / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        git(self.seed, "add", "-A")
        git(self.seed, "commit", "-q", "-m", message)
        git(self.seed, "push", "-q", "gh", "main")

    def answer(self, question, key=None, note=None, rid=None):
        import uuid
        inbox = self.state_dir / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        entry = {"v": 1, "id": rid or str(uuid.uuid4()), "question": question, "key": key, "note": note, "by": "adam", "via": "telegram", "at": "2026-11-17T10:00:00+01:00"}
        with open(inbox / "answers.jsonl", "a") as handle:
            handle.write(json.dumps(entry) + "\n")
        return entry["id"]

    def result(self, task, text=None, files=None):
        import uuid
        folder = self.state_dir / "inbox/results"
        (folder / "files").mkdir(parents=True, exist_ok=True)
        names = []
        for name, data in (files or {}).items():
            (folder / "files" / name).write_bytes(data)
            names.append(name)
        rid = str(uuid.uuid4())
        (folder / f"{rid}.json").write_text(json.dumps({"v": 1, "id": rid, "task": task, "text": text, "files": names, "by": "adam", "via": "telegram", "at": "2026-11-17T10:00:00+01:00"}))
        return rid

    def cleanup(self):
        def writable(func, path, _exc):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            func(path)
        shutil.rmtree(self.tmp, ignore_errors=True)


def wt(world, rel):
    """A path in the work tree, for the stand-in claude's steps (it runs with the work dir as cwd)."""
    return str(Path(world.work) / rel)


def utc(dt):
    return dt.astimezone(timezone.utc)
