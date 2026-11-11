"""Fixed-verb iOS build runner for the Mac (issue 8).

Every verb takes typed arguments only. Each argument is checked against a
pattern or an allowlist before anything runs, and every command runs as an
argument array with shell=False. Nothing from a request is ever joined into a
shell string. The runner does not know or care how a request reached it.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import plistlib
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1

# Exit codes of the runner itself, as the transport sees them.
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2
EXIT_BUSY = 3
EXIT_TIMEOUT = 4

PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DEVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
TASK_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
RUN_ID_RE = re.compile(r"^\d{8}T\d{9}Z-[0-9a-f]{8}$")  # UTC to the millisecond, then random
SCHEME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
CONFIGURATION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
UDID_RE = re.compile(r"^[A-Fa-f0-9-]{8,64}$")
TEAM_RE = re.compile(r"^[A-Z0-9]{10}$")

# The only prepare steps there are. A project picks from these by name.
# Each is (argv, where it runs: "root" or "xcode", the folder holding the
# workspace or project file).
PREPARE_STEPS = {
    "pnpm-install": (["pnpm", "install", "--frozen-lockfile"], "root"),
    "npm-ci": (["npm", "ci"], "root"),
    "pod-install": (["pod", "install"], "xcode"),
    "expo-prebuild": (["pnpm", "exec", "expo", "prebuild", "--platform", "ios", "--no-install"], "root"),
}

DEFAULT_TIMEOUTS = {
    "git": 300,
    "prepare": 1800,
    "build": 3600,
    "archive": 3600,
    "export": 900,
    "install": 600,
    "launch": 120,
    "devices": 60,
    "codesign": 60,
}

DEFAULT_PATH = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/opt/homebrew/bin"]


class Refused(Exception):
    """A request the runner will not run. Nothing has started."""


class ConfigError(Exception):
    """The project file is missing, unsafe or malformed."""


# --- config ---------------------------------------------------------------


@dataclass
class Project:
    name: str
    path: Path
    scheme: str
    configuration: str
    bundle_id: str
    workspace: str | None = None
    project: str | None = None
    prepare: list[str] = field(default_factory=list)
    team_id: str | None = None

    def container_args(self) -> list[str]:
        if self.workspace:
            return ["-workspace", str(self.path / self.workspace)]
        return ["-project", str(self.path / self.project)]

    def xcode_dir(self) -> Path:
        return (self.path / (self.workspace or self.project)).parent


@dataclass
class Config:
    state_dir: Path
    handoff_dir: Path
    path: list[str]
    developer_dir: str | None
    max_log_bytes: int
    keep_runs: int
    timeouts: dict[str, int]
    projects: dict[str, Project]
    devices: dict[str, str]


def _relative(value, what):
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{what} must be a non-empty string")
    p = Path(value)
    if p.is_absolute() or ".." in p.parts or value.startswith("-"):
        raise ConfigError(f"{what} must be a relative path inside the project")
    return value


def _match(regex, value, what):
    if not isinstance(value, str) or not regex.match(value):
        raise ConfigError(f"{what} is not allowed: {value!r}")
    return value


def load_config(path: Path) -> Config:
    try:
        st = path.stat()
    except OSError as e:
        raise ConfigError(f"project file not readable: {path}") from e
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ConfigError("project file is writable by group or others")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ConfigError("project file is not valid JSON") from e
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ConfigError(f"project file schema must be {SCHEMA}")

    def abs_path(key, default):
        value = os.path.expanduser(data.get(key, default))
        if not os.path.isabs(value):
            raise ConfigError(f"{key} must be absolute")
        return Path(value)

    state_dir = abs_path("state_dir", "~/Library/Application Support/jorah-ios-runner")
    handoff_dir = abs_path("handoff_dir", "/Users/Shared/jorah-handoff")
    search = data.get("path", DEFAULT_PATH)
    if not isinstance(search, list) or not all(isinstance(p, str) and os.path.isabs(p) for p in search):
        raise ConfigError("path must be a list of absolute folders")
    developer_dir = data.get("developer_dir")
    if developer_dir is not None and not (isinstance(developer_dir, str) and os.path.isabs(developer_dir)):
        raise ConfigError("developer_dir must be absolute")
    timeouts = dict(DEFAULT_TIMEOUTS)
    for key, value in (data.get("timeouts") or {}).items():
        if key not in DEFAULT_TIMEOUTS or not isinstance(value, (int, float)) or value <= 0:
            raise ConfigError(f"bad timeout: {key}")
        timeouts[key] = value
    max_log = data.get("max_log_bytes", 8 * 1024 * 1024)
    keep = data.get("keep_runs", 100)
    if not isinstance(max_log, int) or max_log < 4096:
        raise ConfigError("max_log_bytes must be at least 4096")
    if not isinstance(keep, int) or keep < 1:
        raise ConfigError("keep_runs must be at least 1")

    projects = {}
    for name, p in (data.get("projects") or {}).items():
        _match(PROJECT_RE, name, "project name")
        if not isinstance(p, dict):
            raise ConfigError(f"project {name} must be an object")
        if bool(p.get("workspace")) == bool(p.get("project")):
            raise ConfigError(f"project {name} needs exactly one of workspace or project")
        root = p.get("path")
        if not isinstance(root, str) or not os.path.isabs(os.path.expanduser(root)):
            raise ConfigError(f"project {name} path must be absolute")
        prepare = p.get("prepare", [])
        if not isinstance(prepare, list) or any(step not in PREPARE_STEPS for step in prepare):
            raise ConfigError(f"project {name} prepare must be chosen from {sorted(PREPARE_STEPS)}")
        team = p.get("team_id")
        if team is not None:
            _match(TEAM_RE, team, f"project {name} team_id")
        projects[name] = Project(
            name=name,
            path=Path(os.path.expanduser(root)),
            workspace=_relative(p["workspace"], "workspace") if p.get("workspace") else None,
            project=_relative(p["project"], "project") if p.get("project") else None,
            scheme=_match(SCHEME_RE, p.get("scheme"), f"project {name} scheme"),
            configuration=_match(CONFIGURATION_RE, p.get("configuration", "Debug"), f"project {name} configuration"),
            bundle_id=_match(BUNDLE_ID_RE, p.get("bundle_id"), f"project {name} bundle_id"),
            prepare=list(prepare),
            team_id=team,
        )

    devices = {}
    for alias, d in (data.get("devices") or {}).items():
        _match(DEVICE_RE, alias, "device alias")
        udid = d.get("udid") if isinstance(d, dict) else None
        devices[alias] = _match(UDID_RE, udid, f"device {alias} udid")

    return Config(state_dir, handoff_dir, list(search), developer_dir, max_log, keep, timeouts, projects, devices)


# --- argument checks --------------------------------------------------------


def check_project(config: Config, name: str) -> Project:
    if not PROJECT_RE.match(name or ""):
        raise Refused("project name is not allowed")
    if name not in config.projects:
        raise Refused(f"project {name} is not on the allowlist")
    return config.projects[name]


def check_branch(branch: str) -> str:
    if branch == "main":
        return branch
    if branch.startswith("jorah/"):
        task = branch[len("jorah/"):]
        if TASK_RE.match(task) and ".." not in task and not task.endswith((".", ".lock")):
            return branch
    raise Refused("branch must be main or jorah/<task>")


def check_device(config: Config, alias: str) -> str:
    if not DEVICE_RE.match(alias or ""):
        raise Refused("device name is not allowed")
    if alias not in config.devices:
        raise Refused(f"device {alias} is not on the allowlist")
    return config.devices[alias]


def check_run_id(run_id: str) -> str:
    if not RUN_ID_RE.match(run_id or ""):
        raise Refused("run id is not valid")
    return run_id


# --- logs -------------------------------------------------------------------


class CappedLog:
    """Keeps the head of the log up to its share of the cap and the most recent
    tail, and drops the middle. Errors from xcodebuild come at the end."""

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

    def write(self, data: bytes):
        with self.lock:
            room = self.head_cap - self.written
            if room > 0:
                part = data[:room]
                self.handle.write(part)
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
            if self.dropped:
                self.handle.write(f"\n[... {self.dropped} bytes dropped by the log cap ...]\n".encode())
            self.handle.write(bytes(self.tail))
            self.handle.close()


# --- runs -------------------------------------------------------------------


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z-" + secrets.token_hex(4)


def write_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.chmod(tmp, 0o640)
    os.replace(tmp, path)


class Lock:
    """One run at a time per project. flock is released if the runner dies."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.handle = open(self.path, "a")
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            raise
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


@dataclass
class StepResult:
    name: str
    exit_code: int | None
    duration_s: float
    timed_out: bool = False
    error: str | None = None

    @property
    def ok(self):
        return self.exit_code == 0 and not self.timed_out and self.error is None


class Run:
    def __init__(self, config: Config, verb: str, project: Project, extra: dict):
        self.config = config
        self.verb = verb
        self.project = project
        self.run_id = new_run_id()
        self.dir = config.state_dir / "runs" / self.run_id
        self.dir.mkdir(parents=True, mode=0o750)
        self.log_path = self.dir / "run.log"
        self.log = CappedLog(self.log_path, config.max_log_bytes)
        self.started = time.monotonic()
        self.steps: list[StepResult] = []
        self.env = {
            "PATH": ":".join(config.path),
            "HOME": os.environ.get("HOME", "/var/empty"),
            "LANG": "en_US.UTF-8",
            "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
            "CI": "1",
        }
        if config.developer_dir:
            self.env["DEVELOPER_DIR"] = config.developer_dir
        self.result = {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "verb": verb,
            "project": project.name,
            "commit_sha": None,
            "tree_clean": None,
            "exit_code": None,
            "outcome": "running",
            "tier": "unknown",
            "tiers": {},
            "started_at": now_iso(),
            "finished_at": None,
            "duration_s": None,
            "artifact_path": None,
            "log_path": str(self.log_path),
            "steps": [],
            "error": None,
            **extra,
        }
        write_json(self.dir / "result.json", self.result)

    def step(self, name, argv, cwd, timeout_key, capture=False):
        """Runs one argument array. Output goes to the capped log, and is also
        returned when capture is set (for short git queries)."""
        timeout = self.config.timeouts[timeout_key]
        self.log.note(f"\n=== {name}: {json.dumps(argv)} (cwd {cwd}, timeout {timeout}s) ===\n")
        start = time.monotonic()
        captured = bytearray()
        try:
            proc = subprocess.Popen(
                argv, cwd=str(cwd), env=self.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, shell=False,
            )
        except OSError as e:
            res = StepResult(name, None, round(time.monotonic() - start, 3), error=f"could not start {argv[0]}: {e.strerror}")
            self.log.note(res.error + "\n")
            self.steps.append(res)
            return res, b""

        def pump():
            for chunk in iter(lambda: proc.stdout.read1(65536), b""):
                self.log.write(chunk)
                if capture and len(captured) < 1 << 20:
                    captured.extend(chunk)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc)
            code = None
        reader.join(timeout=5)
        res = StepResult(name, code, round(time.monotonic() - start, 3), timed_out=timed_out)
        if timed_out:
            res.error = f"timed out after {timeout}s"
            self.log.note(f"\n[{name} {res.error}; process group killed]\n")
        self.steps.append(res)
        return res, bytes(captured)

    def finish(self, outcome, tier, tiers, artifact=None, error=None):
        last = self.steps[-1] if self.steps else None
        self.result.update(
            exit_code=last.exit_code if last else None,
            outcome=outcome,
            tier=tier,
            tiers=tiers,
            artifact_path=str(artifact) if artifact else None,
            finished_at=now_iso(),
            duration_s=round(time.monotonic() - self.started, 3),
            steps=[s.__dict__ for s in self.steps],
            error=error,
        )
        self.log.close()
        write_json(self.dir / "result.json", self.result)
        prune_runs(self.config)
        return self.result


def _kill_group(proc):
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def prune_runs(config: Config):
    """Rotation: keeps the newest keep_runs run folders. Handoff artifacts are
    never touched."""
    runs = config.state_dir / "runs"
    names = sorted(n for n in os.listdir(runs) if RUN_ID_RE.match(n))
    for name in names[: max(0, len(names) - config.keep_runs)]:
        shutil.rmtree(runs / name, ignore_errors=True)


# --- verbs ------------------------------------------------------------------


def record_commit(run: Run):
    res, out = run.step("rev-parse", ["git", "-C", str(run.project.path), "rev-parse", "HEAD"], run.project.path, "git", capture=True)
    sha = out.decode(errors="replace").strip()
    run.result["commit_sha"] = sha if res.ok and re.fullmatch(r"[0-9a-f]{40,64}", sha) else None
    res, out = run.step("status", ["git", "-C", str(run.project.path), "status", "--porcelain"], run.project.path, "git", capture=True)
    run.result["tree_clean"] = (out.strip() == b"") if res.ok else None
    # These two are bookkeeping, not the verb's own steps.
    run.steps = [s for s in run.steps if s.name not in ("rev-parse", "status")]


def failed(run: Run, tier_name: str, error=None, extra_tiers=None):
    last = run.steps[-1] if run.steps else None
    outcome = "timeout" if last and last.timed_out else "failed"
    tiers = {tier_name: "unknown", **(extra_tiers or {})}
    return run.finish(outcome, "unknown", tiers, error=error or (last.error if last else None) or f"{last.name} exited {last.exit_code}")


def verb_sync(run: Run, branch: str):
    root = run.project.path
    git = ["git", "-C", str(root)]
    res, out = run.step("check-clean", git + ["status", "--porcelain"], root, "git", capture=True)
    if not res.ok:
        return failed(run, "sync")
    if out.strip():
        record_commit(run)
        return run.finish("refused", "unknown", {"sync": "unknown"}, error="working tree is dirty; the runner never resets or stashes")
    steps = [
        ("fetch", git + ["fetch", "--prune", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}"]),
    ]
    for name, argv in steps:
        res, _ = run.step(name, argv, root, "git")
        if not res.ok:
            return failed(run, "sync")
    res, _ = run.step("has-local", git + ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root, "git")
    if res.ok:
        argv = [git + ["switch", "--", branch], git + ["merge", "--ff-only", f"refs/remotes/origin/{branch}"]]
    else:
        run.steps.pop()  # a missing local branch is expected, not a failure
        argv = [git + ["switch", "--create", branch, "--track", f"refs/remotes/origin/{branch}"]]
    for i, a in enumerate(argv):
        res, _ = run.step(f"switch-{i}", a, root, "git")
        if not res.ok:
            return failed(run, "sync")
    record_commit(run)
    return run.finish("ok", "none", {"sync": "proved"})


def run_prepare(run: Run) -> bool:
    for name in run.project.prepare:
        argv, where = PREPARE_STEPS[name]
        cwd = run.project.path if where == "root" else run.project.xcode_dir()
        res, _ = run.step(f"prepare:{name}", list(argv), cwd, "prepare")
        if not res.ok:
            return False
    return True


def xcodebuild_base(run: Run, destination: str, derived: Path):
    p = run.project
    return ["xcodebuild", *p.container_args(), "-scheme", p.scheme, "-configuration", p.configuration,
            "-destination", destination, "-derivedDataPath", str(derived)]


def find_app(products: Path, bundle_id: str) -> Path | None:
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


def derived_dir(run: Run, kind: str) -> Path:
    path = run.config.state_dir / "derived" / run.project.name / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def verb_build_sim(run: Run):
    record_commit(run)
    if not run_prepare(run):
        return failed(run, "build")
    derived = derived_dir(run, "sim")
    res, _ = run.step("xcodebuild", xcodebuild_base(run, "generic/platform=iOS Simulator", derived)
                      + ["build", "CODE_SIGNING_ALLOWED=NO"], run.project.path, "build")
    if not res.ok:
        return failed(run, "build")
    app = find_app(derived / "Build" / "Products" / f"{run.project.configuration}-iphonesimulator", run.project.bundle_id)
    if not app:
        return failed(run, "build", error="xcodebuild exited 0 but no .app with the expected bundle ID was found")
    return run.finish("ok", "build", {"build": "proved"}, artifact=app)


def check_development_signature(run: Run, app: Path) -> str | None:
    """Returns None when the app is signed by an Apple Development identity,
    else the reason it isn't proven."""
    res, out = run.step("codesign", ["codesign", "--display", "--verbose=2", str(app)], app.parent, "codesign", capture=True)
    if not res.ok:
        return "codesign could not read the signature"
    authorities = [line.split("=", 1)[1] for line in out.decode(errors="replace").splitlines() if line.startswith("Authority=")]
    if not authorities:
        return "the app is not signed"
    if not authorities[0].startswith(("Apple Development:", "iPhone Developer:")):
        return f"signed by {authorities[0].split(':')[0]}, not a Development certificate"
    return None


def verb_build_device(run: Run):
    record_commit(run)
    if not run_prepare(run):
        return failed(run, "build")
    derived = derived_dir(run, "device")
    argv = xcodebuild_base(run, "generic/platform=iOS", derived) + ["build"]
    if run.project.team_id:
        argv.append(f"DEVELOPMENT_TEAM={run.project.team_id}")
    res, _ = run.step("xcodebuild", argv, run.project.path, "build")
    if not res.ok:
        return failed(run, "build")
    app = find_app(derived / "Build" / "Products" / f"{run.project.configuration}-iphoneos", run.project.bundle_id)
    if not app:
        return failed(run, "build", error="xcodebuild exited 0 but no .app with the expected bundle ID was found")
    why = check_development_signature(run, app)
    if why:
        return failed(run, "build", error=why)
    return run.finish("ok", "build", {"build": "proved"}, artifact=app)


def verb_install_device(run: Run, udid: str, launch: bool):
    record_commit(run)
    derived = run.config.state_dir / "derived" / run.project.name / "device"
    app = find_app(derived / "Build" / "Products" / f"{run.project.configuration}-iphoneos", run.project.bundle_id)
    extra = {"launch": "unknown"} if launch else {}
    if not app:
        return run.finish("failed", "unknown", {"install": "unknown", **extra},
                          error="no device build found; run build-device first")
    run.result["artifact_path"] = str(app)
    res, _ = run.step("install", ["xcrun", "devicectl", "device", "install", "app", "--device", udid, str(app)],
                      run.project.path, "install")
    if not res.ok:
        return failed(run, "install", extra_tiers=extra)
    if not launch:
        return run.finish("ok", "install", {"install": "proved"}, artifact=app)
    res, _ = run.step("launch", ["xcrun", "devicectl", "device", "process", "launch", "--device", udid,
                                 run.project.bundle_id], run.project.path, "launch")
    if not res.ok:
        last = run.steps[-1]
        return run.finish("timeout" if last.timed_out else "failed", "install",
                          {"install": "proved", "launch": "unknown"}, artifact=app,
                          error=last.error or f"launch exited {last.exit_code}")
    return run.finish("ok", "launch", {"install": "proved", "launch": "proved"}, artifact=app)


EXPORT_OPTIONS = {
    "method": "debugging",  # Development signing; Xcode's new name for "development"
    "destination": "export",  # never upload
    "signingStyle": "automatic",
    "compileBitcode": False,
    "uploadSymbols": False,
    "manageAppVersionAndBuildNumber": False,
}


def verb_archive(run: Run):
    record_commit(run)
    if not run_prepare(run):
        return failed(run, "build")
    archive = run.dir / f"{run.project.name}.xcarchive"
    derived = derived_dir(run, "archive")
    argv = xcodebuild_base(run, "generic/platform=iOS", derived) + ["-archivePath", str(archive), "archive"]
    if run.project.team_id:
        argv.append(f"DEVELOPMENT_TEAM={run.project.team_id}")
    res, _ = run.step("archive", argv, run.project.path, "archive")
    if not res.ok:
        return failed(run, "build")
    options = run.dir / "ExportOptions.plist"
    export_options = dict(EXPORT_OPTIONS)
    if run.project.team_id:
        export_options["teamID"] = run.project.team_id
    with open(options, "wb") as f:
        plistlib.dump(export_options, f)
    handoff = run.config.handoff_dir / run.run_id
    try:
        run.config.handoff_dir.mkdir(parents=True, exist_ok=True)
        handoff.mkdir(mode=0o755)
    except OSError as e:
        return failed(run, "build", error=f"cannot create the handoff folder: {e.strerror}")
    res, _ = run.step("export", ["xcodebuild", "-exportArchive", "-archivePath", str(archive),
                                 "-exportPath", str(handoff), "-exportOptionsPlist", str(options)],
                      run.project.path, "export")
    if not res.ok:
        return failed(run, "build")
    ipas = sorted(handoff.glob("*.ipa"))
    if len(ipas) != 1 or not zipfile.is_zipfile(ipas[0]):
        return failed(run, "build", error="export exited 0 but did not leave exactly one valid .ipa")
    return run.finish("ok", "build", {"build": "proved", "archive": "proved"}, artifact=ipas[0])


def verb_devices(config: Config):
    """Allowlisted devices only, with whether devicectl sees each. Other
    connected devices are counted, not named."""
    env = {"PATH": ":".join(config.path), "HOME": os.environ.get("HOME", "/var/empty")}
    if config.developer_dir:
        env["DEVELOPER_DIR"] = config.developer_dir
    tmp = config.state_dir / f"devices-{secrets.token_hex(4)}.json"
    seen: set[str] | None = None
    try:
        proc = subprocess.run(["xcrun", "devicectl", "list", "devices", "--json-output", str(tmp)],
                              env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=config.timeouts["devices"], shell=False)
        if proc.returncode == 0:
            data = json.loads(tmp.read_text())
            seen = set()
            for d in data.get("result", {}).get("devices", []):
                seen.add(str(d.get("identifier", "")).upper())
                seen.add(str(d.get("hardwareProperties", {}).get("udid", "")).upper())
    except (OSError, ValueError, subprocess.TimeoutExpired, AttributeError):
        seen = None
    finally:
        tmp.unlink(missing_ok=True)
    simulators = None
    try:
        proc = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"], env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=config.timeouts["devices"], shell=False)
        if proc.returncode == 0:
            simulators = sum(len(v) for v in json.loads(proc.stdout).get("devices", {}).values())
    except (OSError, ValueError, subprocess.TimeoutExpired, AttributeError):
        simulators = None
    devices = []
    for alias, udid in sorted(config.devices.items()):
        connected = "unknown" if seen is None else (udid.upper() in seen)
        devices.append({"device": alias, "connected": connected})
    return {"schema": SCHEMA, "verb": "devices", "outcome": "ok" if seen is not None else "failed",
            "devices": devices, "simulators_available": simulators if simulators is not None else "unknown"}


# --- entry point -----------------------------------------------------------


class _ArgError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """argparse that refuses instead of exiting, so the caller always gets JSON."""

    def error(self, message):
        raise _ArgError(message)


def parser():
    p = _Parser(prog="jorah-ios-runner", allow_abbrev=False, add_help=False,
                description="Fixed-verb iOS build runner. Arguments are names, never commands.")
    sub = p.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    s = sub.add_parser("sync", allow_abbrev=False, add_help=False)
    s.add_argument("project")
    s.add_argument("branch")
    for verb in ("build-sim", "build-device", "archive"):
        sub.add_parser(verb, allow_abbrev=False, add_help=False).add_argument("project")
    s = sub.add_parser("install-device", allow_abbrev=False, add_help=False)
    s.add_argument("project")
    s.add_argument("device")
    s.add_argument("--launch", action="store_true")
    for verb in ("status", "log"):
        sub.add_parser(verb, allow_abbrev=False, add_help=False).add_argument("run_id")
    sub.add_parser("devices", allow_abbrev=False, add_help=False)
    return p


def parse(argv):
    return parser().parse_args(argv)


def config_path():
    return Path(os.environ.get("JORAH_IOS_RUNNER_CONFIG",
                               os.path.expanduser("~/.config/jorah-ios-runner/projects.json")))


def emit(obj, code):
    print(json.dumps(obj, sort_keys=True))
    return code


def refusal(reason, verb=None):
    return {"schema": SCHEMA, "verb": verb, "outcome": "refused", "tier": "unknown", "error": reason}


def exit_for(result):
    return {"ok": EXIT_OK, "refused": EXIT_REFUSED, "busy": EXIT_BUSY, "timeout": EXIT_TIMEOUT}.get(result["outcome"], EXIT_FAILED)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = parse(argv)
    except _ArgError as e:
        return emit(refusal(f"bad arguments: {e}"), EXIT_REFUSED)
    try:
        config = load_config(config_path())
    except ConfigError as e:
        return emit(refusal(f"config: {e}", args.verb), EXIT_REFUSED)
    config.state_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
    (config.state_dir / "runs").mkdir(exist_ok=True, mode=0o750)
    (config.state_dir / "locks").mkdir(exist_ok=True, mode=0o750)

    try:
        if args.verb in ("status", "log"):
            run_id = check_run_id(args.run_id)
            folder = config.state_dir / "runs" / run_id
            if not folder.is_dir():
                return emit(refusal("no such run", args.verb), EXIT_REFUSED)
            if args.verb == "status":
                sys.stdout.write((folder / "result.json").read_text())
                return EXIT_OK
            with open(folder / "run.log", "rb") as f:
                sys.stdout.buffer.write(f.read(config.max_log_bytes + 4096))
            return EXIT_OK
        if args.verb == "devices":
            result = verb_devices(config)
            return emit(result, EXIT_OK if result["outcome"] == "ok" else EXIT_FAILED)

        project = check_project(config, args.project)
        extra = {}
        if args.verb == "sync":
            extra["branch"] = check_branch(args.branch)
        udid = None
        if args.verb == "install-device":
            udid = check_device(config, args.device)
            extra["device"] = args.device
            extra["launch_requested"] = bool(args.launch)
    except Refused as e:
        return emit(refusal(str(e), args.verb), EXIT_REFUSED)

    try:
        with Lock(config.state_dir / "locks" / f"{project.name}.lock"):
            run = Run(config, args.verb, project, extra)
            try:
                if args.verb == "sync":
                    result = verb_sync(run, extra["branch"])
                elif args.verb == "build-sim":
                    result = verb_build_sim(run)
                elif args.verb == "build-device":
                    result = verb_build_device(run)
                elif args.verb == "install-device":
                    result = verb_install_device(run, udid, args.launch)
                else:
                    result = verb_archive(run)
            except Exception as e:  # a runner bug still leaves an honest result
                result = run.finish("failed", "unknown", {}, error=f"runner error: {type(e).__name__}")
    except BlockingIOError:
        return emit({**refusal(f"another run holds the lock for {project.name}", args.verb), "outcome": "busy"}, EXIT_BUSY)
    return emit(result, exit_for(result))


if __name__ == "__main__":
    sys.exit(main())
