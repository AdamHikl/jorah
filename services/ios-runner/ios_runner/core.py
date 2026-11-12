"""The runner's verbs, shaped by docs/contracts/jorah-ios-v1.md.

Every verb takes a JSON object whose fields are checked against fixed rules
before anything runs. Every command is an argument array run with shell=False.
Nothing from a request is joined into a string, used as a path, a flag, an
environment variable or a build setting. A tier is claimed only after its own
check; anything the runner cannot determine is null or state "unknown"."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import CONTRACT, DEVICE_RE, PREPARE_STEPS, PROJECT_RE, Config, Project

RUNNER_VERSION = "2.1.0"

TASK_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^(\d{8}T\d{6}Z)-([a-z0-9][a-z0-9-]{0,39})-([0-9a-f]{6})$")
CONFIGURATIONS = ("Debug", "Release")
TERMINAL = ("succeeded", "failed", "cancelled", "unknown")
TAIL_BYTES = 16 * 1024
MAX_LOG_PAGE = 262144

RETRYABLE = {
    "BAD_ARGUMENT": False, "PROJECT_NOT_ALLOWED": False, "REF_NOT_FOUND": False, "SYNC_FAILED": True,
    "TREE_DIRTY": False, "BUSY": True, "BUILD_FAILED": False, "SIGNING_FAILED": False, "INSTALL_DISABLED": False,
    "DEVICE_NOT_ALLOWED": False, "DEVICE_UNAVAILABLE": True, "RUN_NOT_FOUND": False, "NOT_INSTALLABLE": False,
    "ARTIFACT_MISSING": False, "INSTALL_FAILED": False, "LAUNCH_FAILED": False, "TIMEOUT": False,
    "RUNNER_ERROR": False, "CONTRACT_MISMATCH": False,
    "SIMULATOR_DISABLED": False, "SIMULATOR_NOT_FOUND": False, "SIMULATOR_UNAVAILABLE": True,
    "TERMINATE_FAILED": False, "SCREENSHOT_FAILED": False,
}

SIGNING_HINTS = ("signing certificate", "provisioning profile", "no profiles for", "code signing", "codesign",
                 "errsecinternalcomponent", "signing for", "development team", "no account for team")


class ApiError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self):
        return {"code": self.code, "message": self.message, "retryable": RETRYABLE.get(self.code, False)}


def error_dict(code, message):
    return ApiError(code, message).as_dict()


def envelope(ok: bool, error: Optional[dict] = None, **payload):
    return {"contract": CONTRACT, "ok": ok, **payload, "error": error}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(project: str) -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{project}-" + secrets.token_hex(3)


def write_json(path: Path, data):
    tmp = path.parent / (path.name + f".{secrets.token_hex(4)}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.chmod(tmp, 0o640)
    os.replace(tmp, path)


def tree_digest(root: Path):
    """bytes and sha256 of a file, or of a bundle folder: SHA-256 over each
    entry's relative path and content hash, sorted, so the same bundle always
    gives the same digest."""
    if root.is_file():
        h = hashlib.sha256()
        with open(root, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return root.stat().st_size, h.hexdigest()
    total = 0
    outer = hashlib.sha256()
    entries = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            entries.append(Path(dirpath) / name)
    for p in sorted(entries, key=lambda x: str(x.relative_to(root))):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            outer.update(f"{rel}\0link\0{os.readlink(p)}\n".encode())
        elif p.is_file():
            size, digest = tree_digest(p)
            total += size
            outer.update(f"{rel}\0file\0{digest}\n".encode())
        else:
            outer.update(f"{rel}\0dir\n".encode())
    return total, outer.hexdigest()


# --- request fields ---------------------------------------------------------


def _fields(body, required, optional):
    if not isinstance(body, dict):
        raise ApiError("BAD_ARGUMENT", "The request must be a JSON object.")
    extra = set(body) - set(required) - set(optional)
    if extra:
        raise ApiError("BAD_ARGUMENT", f"Unknown field: {sorted(extra)[0]}.")
    missing = [k for k in required if k not in body]
    if missing:
        raise ApiError("BAD_ARGUMENT", f"Missing field: {missing[0]}.")


def _str(body, key, regex, what):
    value = body.get(key)
    if not isinstance(value, str) or not regex.match(value):
        raise ApiError("BAD_ARGUMENT", f"{what} is not valid.")
    return value


def _int(body, key, low, high, default):
    value = body.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ApiError("BAD_ARGUMENT", f"{key} must be a whole number from {low} to {high}.")
    return value


def check_ref(ref) -> str:
    """sync takes only main or jorah/<task> (issue 8's limit, amended into the contract)."""
    if ref == "main":
        return ref
    if isinstance(ref, str) and ref.startswith("jorah/"):
        task = ref[len("jorah/"):]
        if TASK_RE.match(task) and ".." not in task and not task.endswith((".", ".lock")):
            return ref
    raise ApiError("BAD_ARGUMENT", "ref must be main or jorah/<task>.")


# --- logs -------------------------------------------------------------------


class CappedLog:
    """Keeps the first three quarters of the cap and the most recent quarter,
    dropping the middle with a note: xcodebuild's errors come at the end.
    Counts errors and warnings on every line, including dropped ones."""

    def __init__(self, path: Path, cap: int):
        self.path = path
        self.head_cap = cap - cap // 4
        self.tail_cap = cap // 4
        self.handle = open(path, "wb")
        os.chmod(path, 0o640)
        self.written = 0
        self.dropped = 0
        self.tail = bytearray()
        self.lock = threading.Lock()
        self.closed = False

    def write(self, data: bytes):
        with self.lock:
            if self.closed:
                return
            room = self.head_cap - self.written
            if room > 0:
                part = data[:room]
                self.handle.write(part)
                self.handle.flush()
                self.written += len(part)
                data = data[room:]
            if data:
                self.tail += data
                if len(self.tail) > self.tail_cap:
                    cut = len(self.tail) - self.tail_cap
                    self.dropped += cut
                    del self.tail[:cut]

    def note(self, text: str):
        self.write(text.encode())

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            if self.dropped:
                self.handle.write(f"\n[... {self.dropped} bytes dropped by the log cap ...]\n".encode())
            self.handle.write(bytes(self.tail))
            self.handle.close()


class Summary:
    ERROR_RE = re.compile(r"(^|: )(fatal )?error: ")
    WARNING_RE = re.compile(r"(^|: )warning: ")

    def __init__(self):
        self.errors = 0
        self.warnings = 0
        self.first_errors: List[str] = []
        self.error_lines: List[str] = []
        self.partial = b""

    def feed(self, data: bytes):
        data = self.partial + data
        lines = data.split(b"\n")
        self.partial = lines.pop()
        for raw in lines:
            self.line(raw.decode("utf-8", "replace").rstrip("\r"))

    def line(self, text):
        if self.ERROR_RE.search(text):
            self.errors += 1
            if len(self.first_errors) < 5 and text.strip() not in self.first_errors:
                self.first_errors.append(text.strip()[:300])
            if len(self.error_lines) < 200:
                self.error_lines.append(text.lower())
        elif self.WARNING_RE.search(text):
            self.warnings += 1

    def finish(self):
        if self.partial:
            self.line(self.partial.decode("utf-8", "replace"))
            self.partial = b""


# --- the runner -------------------------------------------------------------


class Busy(Exception):
    pass


class GlobalLock:
    """One run at a time on this Mac (contract: BUSY). flock goes with the
    process, so a crash cannot leave it held."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self):
        handle = open(self.path, "a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise Busy()
        self.handle = handle
        return self

    def release(self):
        if self.handle:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None

    def held_elsewhere(self) -> bool:
        try:
            self.acquire()
        except Busy:
            return True
        self.release()
        return False


class StepFailed(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class RunContext:
    """One run: its file, its log, the process it is waiting on."""

    def __init__(self, runner: "Runner", run: dict, project: Project):
        self.runner = runner
        self.run = run
        self.project = project
        self.dir = runner.runs_dir / run["run_id"]
        self.dir.mkdir(mode=0o750)
        self.log_path = self.dir / "run.log"
        self.log = CappedLog(self.log_path, runner.config.max_log_bytes)
        self.summary: Optional[Summary] = None
        self.proc: Optional[subprocess.Popen] = None
        self.error: Optional[dict] = None
        self.cancelled = False
        self.failure_code = "RUNNER_ERROR"  # what a non-zero exit of the current step means
        self.install_target = None
        self.seq = time.time_ns()
        self.save()

    def save(self):
        write_json(self.dir / "run.json", {"run": self.run, "error": self.error, "owner_pid": os.getpid(),
                                           "seq": self.seq, "log_dropped": self.log.dropped,
                                           "log_closed": self.log.closed})

    def set(self, **fields):
        self.run.update(fields)
        self.save()

    def step(self, name, argv, cwd, timeout_key, project_env=False, capture=False, scan=False):
        """Runs one argument array with its output in the capped log. Raises
        StepFailed on a non-zero exit, a timeout or a missing tool."""
        timeout = self.runner.config.timeouts[timeout_key]
        env = self.runner.env(self.project if project_env else None)
        self.log.note(f"\n=== {name}: {json.dumps(argv)} (cwd {cwd}, timeout {timeout}s) ===\n")
        captured = bytearray()
        try:
            proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, start_new_session=True, shell=False)
        except OSError as e:
            self.log.note(f"could not start {argv[0]}: {e.strerror}\n")
            raise StepFailed("RUNNER_ERROR", f"Could not start {argv[0]}.")
        self.proc = proc
        if scan and self.summary is None:
            self.summary = Summary()

        def pump():
            for chunk in iter(lambda: proc.stdout.read1(65536), b""):
                self.log.write(chunk)
                if scan:
                    self.summary.feed(chunk)
                if capture and len(captured) < 1 << 20:
                    captured.extend(chunk)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_group(proc)
            code = None
        reader.join(timeout=5)
        self.proc = None
        if scan:
            self.summary.finish()
        if self.cancelled:
            raise StepFailed("RUNNER_ERROR", "The runner stopped while this run was going.")
        if timed_out:
            self.log.note(f"\n[{name} timed out after {timeout}s; process group killed]\n")
            raise StepFailed("TIMEOUT", f"{name} took longer than {int(timeout)} seconds.")
        if code != 0:
            raise StepFailed("STEP", f"{name} exited {code}.")
        return bytes(captured)


def kill_group(proc):
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def find_app(products: Path, bundle_id: str) -> Optional[Path]:
    if not products.is_dir():
        return None
    for app in sorted(products.glob("*.app")):
        try:
            with open(app / "Info.plist", "rb") as f:
                if plistlib.load(f).get("CFBundleIdentifier") == bundle_id:
                    return app
        except (OSError, plistlib.InvalidFileException, ValueError):
            continue
    return None


TIER_NOTES = {
    ("simulator", "build"): "Built for the simulator. Not installed, not launched.",
    ("device", "build"): "Built and signed for Development. Not installed, not launched.",
    ("archive", "build"): "Archived and signed for Development. Not exported, not uploaded, not installed.",
    ("install", "build"): "The build was proved earlier. This install was not.",
    ("install", "install"): "Installed on the device. Not launched.",
    ("install", "launch"): "Launched on the device. Says nothing about whether any feature works.",
    ("sim-install", "build"): "The simulator build was proved earlier. This install was not.",
    ("sim-install", "install"): "Installed on the simulator. Not launched.",
    ("sim-install", "launch"): "Launched on the simulator. Says nothing about whether any feature works.",
    ("sim-launch", "launch"): "Launched the copy already on the simulator; which build that is was not checked. "
                              "Says nothing about whether any feature works.",
    ("sim-screenshot", "none"): "A screenshot of the simulator's screen. It proves no install or launch.",
}


def tier_note(kind, tier):
    return TIER_NOTES.get((kind, tier), "Nothing was proved.")


# Imported here, after the helpers it uses are defined, because it imports them from this module.
from .simulator import SimulatorVerbs  # noqa: E402


class Runner(SimulatorVerbs):
    def __init__(self, config: Config, background: bool):
        self.config = config
        self.background = background  # serve: builds run in a thread and the reply comes at once
        config.state_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.runs_dir = config.state_dir / "runs"
        self.runs_dir.mkdir(exist_ok=True, mode=0o750)
        (config.state_dir / "locks").mkdir(exist_ok=True, mode=0o750)
        self.lock_path = config.state_dir / "locks" / "runner.lock"
        self.active: Dict[str, RunContext] = {}
        self.active_lock = threading.Lock()

    # environment

    def env(self, project: Optional[Project] = None):
        env = {}
        if project:
            env.update(project.env)
        env.update({
            "PATH": ":".join(self.config.path),
            "HOME": os.environ.get("HOME", "/var/empty"),
            "LANG": "en_US.UTF-8",
            "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
            "CI": "1",
        })
        if self.config.developer_dir:
            env["DEVELOPER_DIR"] = self.config.developer_dir
        return env

    def quick(self, argv, cwd, timeout_key="git", merge=True):
        """A short command whose output is needed (git queries, devicectl and
        simctl lists). Returns (exit code or None on timeout/missing, output).
        merge=False drops stderr, for output that must parse as JSON."""
        try:
            proc = subprocess.Popen(argv, cwd=str(cwd), env=self.env(), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT if merge else subprocess.DEVNULL, start_new_session=True,
                                    shell=False)
        except OSError:
            return None, b""
        try:
            out, _ = proc.communicate(timeout=self.config.timeouts[timeout_key])
        except subprocess.TimeoutExpired:
            kill_group(proc)
            return None, b""
        return proc.returncode, out

    # dispatch

    def dispatch(self, verb: str, body) -> dict:
        try:
            handler = {
                "sync": self.sync,
                "build-sim": lambda b: self.build(b, "simulator"),
                "build-device": lambda b: self.build(b, "device"),
                "archive": lambda b: self.build(b, "archive"),
                "install-device": self.install,
                "status": self.status,
                "log": self.log,
                "devices": self.devices,
                "sim-list": self.sim_list,
                "sim-boot": self.sim_boot,
                "sim-shutdown": self.sim_shutdown,
                "sim-install": self.sim_install,
                "sim-launch": self.sim_launch,
                "sim-terminate": self.sim_terminate,
                "sim-screenshot": self.sim_screenshot,
                "sim-screenshot-read": self.sim_screenshot_read,
            }.get(verb)
            if handler is None:
                raise ApiError("BAD_ARGUMENT", "Unknown verb.")
            return handler(body)
        except ApiError as e:
            return envelope(False, e.as_dict())

    def health(self):
        busy = bool(self.active) or GlobalLock(self.lock_path).held_elsewhere()
        return {"contract": CONTRACT, "runner_version": RUNNER_VERSION, "busy": busy}

    def project(self, body) -> Project:
        name = body.get("project")
        if not isinstance(name, str) or not PROJECT_RE.match(name):
            raise ApiError("BAD_ARGUMENT", "project is not a valid name.")
        if name not in self.config.projects:
            raise ApiError("PROJECT_NOT_ALLOWED", f"Project {name} is not in the allowlist.")
        return self.config.projects[name]

    def take_lock(self) -> GlobalLock:
        try:
            return GlobalLock(self.lock_path).acquire()
        except Busy:
            raise ApiError("BUSY", "Another run is going. One run at a time.")

    # sync

    def sync(self, body):
        _fields(body, ["project"], ["ref"])
        project = self.project(body)
        ref = check_ref(body.get("ref", "main"))
        lock = self.take_lock()
        try:
            git = ["git", "-C", str(project.path)]
            code, _ = self.quick(git + ["ls-remote", "--exit-code", "origin", f"refs/heads/{ref}"], project.path)
            if code == 2:
                raise ApiError("REF_NOT_FOUND", f"Branch {ref} is not in {project.repo}.")
            if code != 0:
                raise ApiError("SYNC_FAILED", f"Could not reach {project.repo}.")
            code, _ = self.quick(git + ["fetch", "--no-tags", "origin",
                                        f"+refs/heads/{ref}:refs/remotes/origin/{ref}"], project.path)
            if code != 0:
                raise ApiError("SYNC_FAILED", f"Fetching {ref} from {project.repo} failed.")
            code, out = self.quick(git + ["rev-parse", "--verify", "--quiet",
                                          f"refs/remotes/origin/{ref}^{{commit}}"], project.path)
            commit = out.decode().strip()
            if code != 0 or not COMMIT_RE.match(commit):
                raise ApiError("REF_NOT_FOUND", f"Branch {ref} did not resolve to a commit.")
            code, out = self.quick(git + ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
                                   project.path)
            head = out.decode().strip()
            default_branch = head[len("origin/"):] if code == 0 and head.startswith("origin/") else None
            return envelope(True, None, project=project.name, ref=ref, commit=commit, repo=project.repo,
                            default_branch=default_branch)
        finally:
            lock.release()

    # builds

    def new_run(self, project: Project, kind: str, configuration: str, commit: str, **extra) -> RunContext:
        run = {
            "run_id": new_run_id(project.name),
            "project": project.name,
            "kind": kind,
            "configuration": configuration,
            "repo": project.repo,
            "commit": commit,
            "state": "queued",
            "tier": "none",
            "tier_note": tier_note(kind, "none"),
            "started_at": now_iso(),
            "finished_at": None,
            "artifact": None,
            "device": None,
            "simulator": None,
            "summary": {"errors": None, "warnings": None, "first_errors": []},
            "log": {"bytes": 0, "tail": "", "complete": False},
            **extra,
        }
        ctx = RunContext(self, run, project)
        with self.active_lock:
            self.active[run["run_id"]] = ctx
        return ctx

    def build(self, body, kind):
        _fields(body, ["project", "commit"], ["configuration"])
        project = self.project(body)
        commit = _str(body, "commit", COMMIT_RE, "commit (40 hex)")
        configuration = body.get("configuration", "Debug")
        if configuration not in CONFIGURATIONS:
            raise ApiError("BAD_ARGUMENT", "configuration must be Debug or Release.")
        lock = self.take_lock()
        try:
            git = ["git", "-C", str(project.path)]
            code, _ = self.quick(git + ["cat-file", "-e", f"{commit}^{{commit}}"], project.path)
            if code != 0:
                raise ApiError("REF_NOT_FOUND", "That commit is not in the runner's clone. Sync first.")
            code, out = self.quick(git + ["status", "--porcelain", "--", "."], project.path)
            if code != 0:
                raise ApiError("RUNNER_ERROR", "git could not read the clone's state.")
            if out.strip():
                raise ApiError("TREE_DIRTY", "The runner's clone has changes. It never resets or stashes.")
            ctx = self.new_run(project, kind, configuration, commit)
        except BaseException:
            lock.release()
            raise
        if self.background:
            threading.Thread(target=self._work, args=(ctx, lock), daemon=True).start()
            time.sleep(0.05)
            return self.reply(ctx.run["run_id"])
        self._work(ctx, lock)
        return self.reply(ctx.run["run_id"])

    def _work(self, ctx: RunContext, lock: GlobalLock):
        try:
            ctx.set(state="running")
            if ctx.run["kind"] == "install":
                self._install(ctx)
            elif ctx.run["kind"].startswith("sim-"):
                self._sim_work(ctx)
            else:
                self._build(ctx)
            ctx.set(state="succeeded")
        except StepFailed as e:
            code = e.code
            if code == "STEP":
                code = ctx.failure_code
            ctx.error = error_dict(code, e.message)
            ctx.set(state="cancelled" if ctx.cancelled else "failed")
        except Exception as e:  # a runner bug still leaves an honest result
            ctx.log.note(f"\n[runner error: {type(e).__name__}]\n")
            ctx.error = error_dict("RUNNER_ERROR", f"The runner hit an internal error ({type(e).__name__}).")
            ctx.set(state="unknown")
        finally:
            ctx.log.close()
            summary = ctx.summary
            if summary is not None:
                ctx.run["summary"] = {"errors": summary.errors, "warnings": summary.warnings,
                                      "first_errors": summary.first_errors}
            ctx.set(finished_at=now_iso())
            with self.active_lock:
                self.active.pop(ctx.run["run_id"], None)
            lock.release()
            self.prune()

    def _checkout(self, ctx: RunContext):
        root = ctx.project.path
        out = ctx.step("head", ["git", "-C", str(root), "rev-parse", "HEAD"], root, "git", capture=True)
        if out.decode().strip() != ctx.run["commit"]:
            ctx.failure_code = "RUNNER_ERROR"
            ctx.step("checkout", ["git", "-C", str(root), "switch", "--detach", ctx.run["commit"]], root, "git")

    def _prepare(self, ctx: RunContext):
        p = ctx.project
        failed = None
        try:
            for item in p.prepare:
                argv, where = PREPARE_STEPS[item.step]
                if item.dir:
                    cwd = p.path / item.dir
                else:
                    cwd = p.path if where == "root" else p.xcode_dir()
                ctx.failure_code = "BUILD_FAILED"
                try:
                    ctx.step(f"prepare:{item.step}", list(argv), cwd, "prepare", project_env=True)
                except StepFailed as e:
                    failed = e if e.code != "STEP" else StepFailed("BUILD_FAILED", f"Prepare step {item.step} failed.")
                    break
        finally:
            if p.restore:
                # Puts back tracked files the prepare steps rewrite (Threadfolio's package.json).
                # The tree was clean before the run, so only the run's own changes are undone.
                ctx.failure_code = "RUNNER_ERROR"
                ctx.step("restore", ["git", "-C", str(p.path), "checkout", "--", *p.restore], p.path, "git")
        if failed:
            raise failed

    def signing_args(self, ctx: RunContext) -> List[str]:
        p = ctx.project
        s = p.signing
        if s.style == "automatic":
            args = ["CODE_SIGN_STYLE=Automatic"]
            if p.team:
                args.append(f"DEVELOPMENT_TEAM={p.team}")
            if s.allow_provisioning_updates:
                args.insert(0, "-allowProvisioningUpdates")
            return args
        lines = ["// Written by the Jorah iOS runner for one run. Manual Development signing.",
                 "CODE_SIGN_STYLE = Manual", "CODE_SIGN_IDENTITY = Apple Development"]
        if p.team:
            lines.append(f"DEVELOPMENT_TEAM = {p.team}")
        if s.profiles:
            for target, profile in sorted(s.profiles.items()):
                lines.append(f"JORAH_PROFILE_{target} = {profile}")
            lines.append("PROVISIONING_PROFILE_SPECIFIER = $(JORAH_PROFILE_$(TARGET_NAME))")
        xcconfig = ctx.dir / "signing.xcconfig"
        xcconfig.write_text("\n".join(lines) + "\n")
        return ["-xcconfig", str(xcconfig)]

    def check_development_signature(self, ctx: RunContext, app: Path):
        ctx.failure_code = "SIGNING_FAILED"
        out = ctx.step("codesign", ["codesign", "--display", "--verbose=2", str(app)], app.parent, "codesign",
                       capture=True)
        authorities = [line.split("=", 1)[1] for line in out.decode(errors="replace").splitlines()
                       if line.startswith("Authority=")]
        if not authorities:
            raise StepFailed("SIGNING_FAILED", "The app is not signed.")
        if not authorities[0].startswith(("Apple Development:", "iPhone Developer:")):
            raise StepFailed("SIGNING_FAILED", "The app is not signed with a Development certificate.")

    def _build(self, ctx: RunContext):
        p = ctx.project
        kind = ctx.run["kind"]
        conf = ctx.run["configuration"]
        self._checkout(ctx)
        self._prepare(ctx)
        derived = self.config.state_dir / "derived" / p.name / kind
        derived.mkdir(parents=True, exist_ok=True)
        handoff = self.config.handoff_dir / ctx.run["run_id"]
        destination = "generic/platform=iOS Simulator" if kind == "simulator" else "generic/platform=iOS"
        argv = ["xcodebuild", *p.container_args(), "-scheme", p.scheme, "-configuration", conf,
                "-destination", destination, "-derivedDataPath", str(derived)]
        if kind == "simulator":
            argv += ["build", "CODE_SIGNING_ALLOWED=NO"]
        else:
            argv += self.signing_args(ctx)
            if kind == "archive":
                self._make_handoff(handoff)
                argv += ["-archivePath", str(handoff / f"{p.scheme}.xcarchive"), "archive"]
            else:
                argv += ["build"]
        ctx.failure_code = "BUILD_FAILED"
        try:
            ctx.step("xcodebuild", argv, p.path, "build", project_env=True, scan=True)
        except StepFailed as e:
            if e.code == "STEP":
                lines = " ".join(ctx.summary.error_lines) if ctx.summary else ""
                code = "SIGNING_FAILED" if kind != "simulator" and any(h in lines for h in SIGNING_HINTS) \
                    else "BUILD_FAILED"
                raise StepFailed(code, "xcodebuild failed." if code == "BUILD_FAILED"
                                 else "xcodebuild failed on signing.")
            raise
        if kind == "archive":
            archive = handoff / f"{p.scheme}.xcarchive"
            app = find_app(archive / "Products" / "Applications", p.bundle_id)
            if not app:
                raise StepFailed("BUILD_FAILED", "xcodebuild exited 0 but the archive has no app with the bundle ID.")
            self.check_development_signature(ctx, app)
            size, digest = tree_digest(archive)
            ctx.set(artifact={"kind": "xcarchive", "path": str(archive), "bytes": size, "sha256": digest})
        else:
            sdk = "iphonesimulator" if kind == "simulator" else "iphoneos"
            app = find_app(derived / "Build" / "Products" / f"{conf}-{sdk}", p.bundle_id)
            if not app:
                raise StepFailed("BUILD_FAILED", "xcodebuild exited 0 but no app with the bundle ID was built.")
            if kind == "device":
                self.check_development_signature(ctx, app)
            self._make_handoff(handoff)
            target = handoff / app.name
            shutil.copytree(app, target, symlinks=True)
            size, digest = tree_digest(target)
            ctx.set(artifact={"kind": "app", "path": str(target), "bytes": size, "sha256": digest})
        ctx.set(tier="build", tier_note=tier_note(kind, "build"))

    def _make_handoff(self, folder: Path):
        if folder.exists():
            return
        try:
            self.config.handoff_dir.mkdir(parents=True, exist_ok=True)
            folder.mkdir(mode=0o750)
        except OSError as e:
            raise StepFailed("RUNNER_ERROR", f"Cannot create the handoff folder ({e.strerror}).")

    # devices and install

    def device_list(self):
        """devicectl's view, by UDID. None when devicectl could not answer."""
        tmp = self.config.state_dir / f"devices-{secrets.token_hex(4)}.json"
        try:
            code, _ = self.quick(["xcrun", "devicectl", "list", "devices", "--json-output", str(tmp)],
                                 self.config.state_dir, "devices")
            if code != 0:
                return None
            data = json.loads(tmp.read_text())
            out = {}
            for d in data.get("result", {}).get("devices", []):
                props = d.get("properties") or {}
                hw = props.get("hardware") or d.get("hardwareProperties") or {}
                conn = props.get("connection") or d.get("connectionProperties") or {}
                state = props.get("state") or d.get("deviceProperties") or {}
                software = props.get("software") or {}
                os_version = (software.get("osVersionNumber") or {}).get("stringValue") \
                    if isinstance(software.get("osVersionNumber"), dict) \
                    else (d.get("deviceProperties") or {}).get("osVersionNumber")
                udid = str(hw.get("udid", "")).upper()
                if not udid:
                    continue
                out[udid] = {
                    "model": hw.get("marketingName") or hw.get("productType"),
                    "os_version": os_version,
                    # "available (paired)" in devicectl's table: paired and booted [inference, checked in issue 12]
                    "connected": conn.get("pairingState") == "paired" and state.get("bootState") == "booted",
                }
            return out
        except (OSError, ValueError, AttributeError, TypeError):
            return None
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def devices(self, body):
        _fields(body or {}, [], [])
        seen = self.device_list()
        devices = []
        for alias, udid in sorted(self.config.devices.items()):
            info = (seen or {}).get(udid.upper())
            devices.append({
                "alias": alias,
                "model": info["model"] if info else None,
                "os_version": info["os_version"] if info else None,
                "connected": None if seen is None else bool(info and info["connected"]),
            })
        return envelope(True, None, devices=devices)

    def install(self, body):
        _fields(body, ["build_run_id", "device"], ["launch"])
        if not self.config.install_allowed:
            raise ApiError("INSTALL_DISABLED", "Installing on a device is turned off.")
        alias = body.get("device")
        if not isinstance(alias, str) or not DEVICE_RE.match(alias):
            raise ApiError("BAD_ARGUMENT", "device is not a valid name.")
        if alias not in self.config.devices:
            raise ApiError("DEVICE_NOT_ALLOWED", f"Device {alias} is not in the allowlist.")
        launch = body.get("launch", False)
        if not isinstance(launch, bool):
            raise ApiError("BAD_ARGUMENT", "launch must be true or false.")
        build_id = _str(body, "build_run_id", RUN_ID_RE, "build_run_id")
        stored = self.load(build_id)
        build = stored["run"]
        if build.get("kind") != "device" or build.get("state") != "succeeded" or not build.get("artifact"):
            raise ApiError("NOT_INSTALLABLE", "That run is not a finished device build.")
        project = self.config.projects.get(build["project"])
        if project is None:
            raise ApiError("PROJECT_NOT_ALLOWED", f"Project {build['project']} is no longer in the allowlist.")
        lock = self.take_lock()
        try:
            ctx = self.new_run(project, "install", build["configuration"], build["commit"], build_run_id=build_id)
            ctx.install_target = (alias, self.config.devices[alias], launch, build["artifact"])
        except BaseException:
            lock.release()
            raise
        self._work(ctx, lock)  # install is synchronous in the contract
        return self.reply(ctx.run["run_id"])

    def _devicectl_json(self, ctx: RunContext, name, argv, timeout_key):
        out = ctx.dir / f"{name}.json"
        ctx.step(name, argv + ["--json-output", str(out)], ctx.dir, timeout_key)
        try:
            return json.loads(out.read_text())
        except (OSError, ValueError):
            return {}

    def _check_artifact(self, artifact) -> Path:
        app = Path(artifact["path"])
        if not app.exists():
            raise StepFailed("ARTIFACT_MISSING", "The built app is gone from the handoff folder.")
        size, digest = tree_digest(app)
        if digest != artifact.get("sha256"):
            raise StepFailed("ARTIFACT_MISSING", "The built app changed since it was built.")
        return app

    def _install(self, ctx: RunContext):
        alias, udid, launch, artifact = ctx.install_target
        app = self._check_artifact(artifact)
        ctx.set(artifact=dict(artifact), tier="build", tier_note=tier_note("install", "build"))
        seen = self.device_list()
        info = (seen or {}).get(udid.upper())
        ctx.set(device={"alias": alias, "model": info["model"] if info else None,
                        "os_version": info["os_version"] if info else None})
        if seen is None:
            raise StepFailed("DEVICE_UNAVAILABLE", "devicectl could not list devices.")
        if not info or not info["connected"]:
            raise StepFailed("DEVICE_UNAVAILABLE", f"{alias} is not connected, or not paired.")
        ctx.failure_code = "INSTALL_FAILED"
        result = self._devicectl_json(ctx, "install", ["xcrun", "devicectl", "device", "install", "app",
                                                        "--device", udid, str(app)], "install")
        bundle = ctx.project.bundle_id
        installed = [a.get("bundleID") or a.get("bundleIdentifier")
                     for a in (result.get("result") or {}).get("installedApplications", []) if isinstance(a, dict)]
        if bundle not in installed:
            raise StepFailed("INSTALL_FAILED", "devicectl did not report the app as installed.")
        listed = self._devicectl_json(ctx, "apps", ["xcrun", "devicectl", "device", "info", "apps", "--device", udid,
                                                     "--bundle-id", bundle], "install")
        apps = [a.get("bundleIdentifier") or a.get("bundleID")
                for a in (listed.get("result") or {}).get("apps", []) if isinstance(a, dict)]
        if bundle not in apps:
            raise StepFailed("INSTALL_FAILED", "The device does not list the app after the install.")
        ctx.set(tier="install", tier_note=tier_note("install", "install"))
        if not launch:
            return
        ctx.failure_code = "LAUNCH_FAILED"
        result = self._devicectl_json(ctx, "launch", ["xcrun", "devicectl", "device", "process", "launch",
                                                       "--device", udid, "--terminate-existing", bundle], "launch")
        pid = ((result.get("result") or {}).get("process") or {}).get("processIdentifier")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise StepFailed("LAUNCH_FAILED", "devicectl did not report a process for the app. Is the phone locked?")
        ctx.set(process_id=pid, tier="launch", tier_note=tier_note("install", "launch"))

    # status and log

    def load(self, run_id) -> dict:
        folder = self.runs_dir / run_id
        try:
            stored = json.loads((folder / "run.json").read_text())
        except (OSError, ValueError):
            raise ApiError("RUN_NOT_FOUND", "There is no run with that ID.")
        run = stored["run"]
        if run["state"] in ("queued", "running") and run_id not in self.active and not pid_alive(stored.get("owner_pid")):
            # The process that owned it is gone: the runner lost track. Never guessed.
            run["state"] = "unknown"
            run["finished_at"] = run.get("finished_at") or now_iso()
            stored["error"] = error_dict("RUNNER_ERROR", "The runner stopped while this run was going.")
            stored["log_closed"] = True
            write_json(folder / "run.json", stored)
        run["log"] = self.log_view(folder, stored, run)
        return stored

    def log_view(self, folder, stored, run):
        path = folder / "run.log"
        try:
            size = path.stat().st_size
            with open(path, "rb") as f:
                f.seek(max(0, size - TAIL_BYTES))
                tail = f.read()
        except OSError:
            return {"bytes": None, "tail": "", "complete": False}
        if size > TAIL_BYTES:
            cut = tail.find(b"\n")
            tail = tail[cut + 1:] if cut >= 0 else tail
        done = run["state"] in TERMINAL and stored.get("log_closed", True)
        return {"bytes": size, "tail": tail.decode("utf-8", "replace"),
                "complete": bool(done and not stored.get("log_dropped"))}

    def reply(self, run_id):
        stored = self.load(run_id)
        return envelope(stored["error"] is None, stored["error"], run=stored["run"])

    def status(self, body):
        _fields(body or {}, [], ["run_id", "wait_seconds"])
        body = body or {}
        wait = _int(body, "wait_seconds", 0, 120, 0)
        if "run_id" not in body:
            if wait:
                raise ApiError("BAD_ARGUMENT", "wait_seconds needs run_id.")
            runs = []
            for run_id in self.recent(10):
                try:
                    runs.append(self.load(run_id)["run"])
                except ApiError:
                    continue
            return envelope(True, None, runs=runs)
        run_id = _str(body, "run_id", RUN_ID_RE, "run_id")
        deadline = time.monotonic() + wait
        while True:
            stored = self.load(run_id)
            if stored["run"]["state"] in TERMINAL or time.monotonic() >= deadline:
                return envelope(stored["error"] is None, stored["error"], run=stored["run"])
            time.sleep(0.25)

    def log(self, body):
        _fields(body, ["run_id"], ["offset", "max_bytes"])
        run_id = _str(body, "run_id", RUN_ID_RE, "run_id")
        offset = _int(body, "offset", 0, 1 << 40, 0)
        max_bytes = _int(body, "max_bytes", 1, MAX_LOG_PAGE, MAX_LOG_PAGE)
        stored = self.load(run_id)
        path = self.runs_dir / run_id / "run.log"
        try:
            total = path.stat().st_size
            with open(path, "rb") as f:
                f.seek(min(offset, total))
                data = f.read(max_bytes)
        except OSError:
            raise ApiError("RUN_NOT_FOUND", "That run has no log.")
        finished = stored["run"]["state"] in TERMINAL
        return envelope(True, None, offset=min(offset, total), bytes=len(data), total_bytes=total,
                        eof=finished and offset + len(data) >= total, text=data.decode("utf-8", "replace"))

    def recent(self, count):
        items = []
        for name in os.listdir(self.runs_dir):
            if not RUN_ID_RE.match(name):
                continue
            try:
                seq = json.loads((self.runs_dir / name / "run.json").read_text()).get("seq", 0)
            except (OSError, ValueError):
                seq = 0
            items.append((seq, name))
        return [name for _, name in sorted(items, reverse=True)[:count]]

    def prune(self):
        """Rotation: keeps the newest keepRuns run records and logs. Artifacts in
        the handoff folder are Adam's and never deleted here."""
        keep = set(self.recent(self.config.keep_runs))
        with self.active_lock:
            keep |= set(self.active)
        for name in os.listdir(self.runs_dir):
            if RUN_ID_RE.match(name) and name not in keep:
                shutil.rmtree(self.runs_dir / name, ignore_errors=True)

    def mark_stale(self):
        """At start: any run a dead process left queued or running becomes unknown."""
        for name in os.listdir(self.runs_dir):
            if RUN_ID_RE.match(name):
                try:
                    self.load(name)
                except ApiError:
                    pass

    def cancel_all(self):
        with self.active_lock:
            contexts = list(self.active.values())
        for ctx in contexts:
            ctx.cancelled = True
            if ctx.proc:
                kill_group(ctx.proc)


def pid_alive(pid) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
