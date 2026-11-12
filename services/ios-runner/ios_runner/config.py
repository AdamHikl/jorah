"""The allowlist file (contract section 6). Owned by an admin, read-only to the
runner. Every field is checked when it loads; anything odd refuses to start."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

CONTRACT = "jorah-ios/1"

PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DEVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
REPO_RE = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
SCHEME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
UDID_RE = re.compile(r"^[A-Fa-f0-9-]{8,64}$")
TEAM_RE = re.compile(r"^[A-Z0-9]{10}$")
TARGET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,99}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")

# Environment names a project may never set: they change what runs or where.
ENV_FORBIDDEN = {"PATH", "HOME", "TMPDIR", "DEVELOPER_DIR", "SHELL", "ENV", "BASH_ENV", "NODE_OPTIONS",
                 "CI", "LANG", "USER", "LOGNAME", "PYTHONPATH", "PYTHONHOME", "RUBYOPT", "RUBYLIB"}
ENV_FORBIDDEN_PREFIXES = ("DYLD_", "LD_", "GIT_", "SSH_", "NPM_CONFIG_", "XCODE_", "DEVICECTL_", "JORAH_")
# The map is for non-secret values only. A name that looks like a secret is refused.
ENV_SECRET_WORDS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "PRIVATE", "CREDENTIAL", "API_KEY")

# The only prepare steps there are: (argv, default folder). "root" is the
# project folder, "xcode" the folder holding the workspace or project file.
PREPARE_STEPS = {
    "pnpm-install": (["pnpm", "install", "--frozen-lockfile"], "root"),
    "npm-ci": (["npm", "ci"], "root"),
    "pod-install": (["pod", "install"], "xcode"),
    "expo-prebuild": (["pnpm", "exec", "expo", "prebuild", "--platform", "ios", "--no-install", "--clean"], "root"),
    "expo-prebuild-npx": (["npx", "--no", "expo", "prebuild", "--platform", "ios", "--no-install", "--clean"], "root"),
}

DEFAULT_TIMEOUTS = {
    "git": 300,
    "prepare": 1800,
    "build": 2700,  # contract: build over 45 minutes is TIMEOUT
    "install": 300,  # contract: install over 5 minutes is TIMEOUT
    "launch": 120,
    "devices": 60,
    "codesign": 60,
    "simulator": 300,  # simctl: boot, shutdown, install, launch, screenshot, list
}

DEFAULT_PATH = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/opt/homebrew/bin"]
LOOPBACK = {"127.0.0.1", "::1"}


class ConfigError(Exception):
    """The allowlist file is missing, unsafe or malformed."""


@dataclass
class PrepareStep:
    step: str
    dir: Optional[str] = None  # relative to the project folder


@dataclass
class Signing:
    style: str = "manual"  # "manual" or "automatic"
    profiles: Dict[str, str] = field(default_factory=dict)  # target name -> profile name
    allow_provisioning_updates: bool = False


@dataclass
class Project:
    name: str
    repo: str
    path: Path
    scheme: str
    bundle_id: str
    workspace: Optional[str] = None
    project: Optional[str] = None
    team: Optional[str] = None
    prepare: List[PrepareStep] = field(default_factory=list)
    restore: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    env_file: Optional[Path] = None  # admin-owned KEY=VALUE file outside the clone, read per build
    signing: Signing = field(default_factory=Signing)

    def container_args(self) -> List[str]:
        if self.workspace:
            return ["-workspace", str(self.path / self.workspace)]
        return ["-project", str(self.path / self.project)]

    def xcode_dir(self) -> Path:
        return (self.path / (self.workspace or self.project)).parent


@dataclass
class Config:
    install_allowed: bool
    simulator_allowed: bool
    team: Optional[str]
    state_dir: Path
    handoff_dir: Path
    key_file: Path
    host: str
    port: int
    path: List[str]
    developer_dir: Optional[str]
    max_log_bytes: int
    keep_runs: int
    timeouts: Dict[str, float]
    projects: Dict[str, Project]
    devices: Dict[str, str]


def _relative(value, what):
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ConfigError(f"{what} must be a non-empty string")
    p = Path(value)
    if p.is_absolute() or ".." in p.parts or value.startswith("-") or "\n" in value:
        raise ConfigError(f"{what} must be a relative path inside the project")
    return value


def _match(regex, value, what):
    if not isinstance(value, str) or not regex.match(value):
        raise ConfigError(f"{what} is not allowed: {value!r}")
    return value


def _bool(value, what):
    if not isinstance(value, bool):
        raise ConfigError(f"{what} must be true or false")
    return value


def _keys(obj, allowed, what):
    if not isinstance(obj, dict):
        raise ConfigError(f"{what} must be an object")
    extra = set(obj) - set(allowed)
    if extra:
        raise ConfigError(f"{what} has unknown keys: {sorted(extra)}")


def _env(env, what):
    if env is None:
        return {}
    if not isinstance(env, dict):
        raise ConfigError(f"{what} must be an object")
    out = {}
    for name, value in env.items():
        _match(ENV_NAME_RE, name, f"{what} name")
        if name in ENV_FORBIDDEN or name.startswith(ENV_FORBIDDEN_PREFIXES):
            raise ConfigError(f"{what} may not set {name}")
        if any(word in name for word in ENV_SECRET_WORDS):
            raise ConfigError(f"{what} is for non-secret values; {name} looks like a secret")
        if not isinstance(value, str) or len(value) > 1024 or any(c in value for c in "\n\r\0"):
            raise ConfigError(f"{what} {name} must be a one-line string")
        out[name] = value
    return out


def read_env_file(path: Path, fixed: Dict[str, str]) -> Dict[str, str]:
    """A project's envFile: NAME=VALUE lines, '#' comments, for values Adam keeps
    out of git but that are not secrets, such as a publishable key that ships in
    the app. Same name rules as the env map. Refused if group or others can
    write it, if anyone but root or the runner's user owns it, or if it repeats
    a name from the env map. Error messages carry names, never values."""
    try:
        st = path.stat()
    except OSError:
        raise ConfigError("envFile is missing")
    if not stat.S_ISREG(st.st_mode) or st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ConfigError("envFile must be a regular file not writable by group or others")
    if st.st_uid not in (0, os.getuid()):
        raise ConfigError("envFile must be owned by root or the runner's user")
    if st.st_size > 16384:
        raise ConfigError("envFile is over 16 KiB")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ConfigError("envFile is not readable UTF-8")
    raw = {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if not sep:
            raise ConfigError(f"envFile line {number} is not NAME=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        name = name.strip()
        if name in raw or name in fixed:
            raise ConfigError(f"envFile sets {name} twice, or again after the env map")
        raw[name] = value
    return _env(raw, "envFile")


def _project(name, p, top_team):
    _keys(p, {"repo", "path", "workspace", "project", "scheme", "bundleId", "team", "prepare", "restore", "env",
              "envFile", "signing"}, f"project {name}")
    if bool(p.get("workspace")) == bool(p.get("project")):
        raise ConfigError(f"project {name} needs exactly one of workspace or project")
    root = p.get("path")
    if not isinstance(root, str) or not os.path.isabs(os.path.expanduser(root)):
        raise ConfigError(f"project {name} path must be absolute")
    prepare = []
    for item in p.get("prepare", []) or []:
        if isinstance(item, str):
            item = {"step": item}
        _keys(item, {"step", "dir"}, f"project {name} prepare step")
        if item.get("step") not in PREPARE_STEPS:
            raise ConfigError(f"project {name} prepare must be chosen from {sorted(PREPARE_STEPS)}")
        folder = _relative(item["dir"], f"project {name} prepare dir") if "dir" in item else None
        prepare.append(PrepareStep(item["step"], folder))
    restore = [_relative(r, f"project {name} restore") for r in (p.get("restore") or [])]
    team = p.get("team", top_team)
    if team is not None:
        _match(TEAM_RE, team, f"project {name} team")
    s = p.get("signing") or {}
    _keys(s, {"style", "profiles", "allowProvisioningUpdates"}, f"project {name} signing")
    style = s.get("style", "manual")
    if style not in ("manual", "automatic"):
        raise ConfigError(f"project {name} signing style must be manual or automatic")
    profiles = {}
    for target, profile in (s.get("profiles") or {}).items():
        _match(TARGET_RE, target, f"project {name} signing target")
        profiles[target] = _match(PROFILE_RE, profile, f"project {name} profile for {target}")
    signing = Signing(style, profiles, _bool(s.get("allowProvisioningUpdates", False),
                                             f"project {name} allowProvisioningUpdates"))
    env_file = p.get("envFile")
    if env_file is not None:
        if not isinstance(env_file, str) or not os.path.isabs(env_file) or "\n" in env_file:
            raise ConfigError(f"project {name} envFile must be an absolute path")
        env_file = Path(os.path.normpath(env_file))
        clone = Path(os.path.normpath(os.path.expanduser(root)))
        if env_file == clone or clone in env_file.parents:
            raise ConfigError(f"project {name} envFile must be outside the project's clone")
    return Project(
        name=name,
        repo=_match(REPO_RE, p.get("repo"), f"project {name} repo"),
        path=Path(os.path.expanduser(root)),
        workspace=_relative(p["workspace"], "workspace") if p.get("workspace") else None,
        project=_relative(p["project"], "project") if p.get("project") else None,
        scheme=_match(SCHEME_RE, p.get("scheme"), f"project {name} scheme"),
        bundle_id=_match(BUNDLE_ID_RE, p.get("bundleId"), f"project {name} bundleId"),
        team=team,
        prepare=prepare,
        restore=restore,
        env=_env(p.get("env"), f"project {name} env"),
        env_file=env_file,
        signing=signing,
    )


def load_config(path: Path) -> Config:
    try:
        st = path.stat()
    except OSError as e:
        raise ConfigError(f"allowlist not readable: {path}") from e
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ConfigError("allowlist is writable by group or others")
    if st.st_uid not in (0, os.getuid()):
        raise ConfigError("allowlist must be owned by root or the runner's user")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ConfigError("allowlist is not valid JSON") from e
    _keys(data, {"contract", "installAllowed", "simulatorAllowed", "team", "stateDir", "handoffDir", "keyFile", "listen", "path",
                 "developerDir", "maxLogBytes", "keepRuns", "timeouts", "projects", "devices"}, "allowlist")
    if data.get("contract") != CONTRACT:
        raise ConfigError(f"allowlist contract must be {CONTRACT}")

    def abs_path(key, default):
        value = os.path.expanduser(data.get(key, default))
        if not os.path.isabs(value):
            raise ConfigError(f"{key} must be absolute")
        return Path(value)

    team = data.get("team")
    if team is not None:
        _match(TEAM_RE, team, "team")
    listen = data.get("listen") or {}
    _keys(listen, {"host", "port"}, "listen")
    host = listen.get("host", "127.0.0.1")
    port = listen.get("port", 47820)
    if host not in LOOPBACK:
        raise ConfigError("listen host must be loopback (127.0.0.1 or ::1)")
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ConfigError("listen port must be 0 to 65535")
    search = data.get("path", DEFAULT_PATH)
    if not isinstance(search, list) or not all(isinstance(p, str) and os.path.isabs(p) for p in search):
        raise ConfigError("path must be a list of absolute folders")
    developer_dir = data.get("developerDir")
    if developer_dir is not None and not (isinstance(developer_dir, str) and os.path.isabs(developer_dir)):
        raise ConfigError("developerDir must be absolute")
    timeouts = dict(DEFAULT_TIMEOUTS)
    for key, value in (data.get("timeouts") or {}).items():
        if key not in DEFAULT_TIMEOUTS or isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ConfigError(f"bad timeout: {key}")
        timeouts[key] = value
    max_log = data.get("maxLogBytes", 64 * 1024 * 1024)
    keep = data.get("keepRuns", 200)
    if not isinstance(max_log, int) or max_log < 65536:
        raise ConfigError("maxLogBytes must be at least 65536")
    if not isinstance(keep, int) or keep < 1:
        raise ConfigError("keepRuns must be at least 1")

    projects = {}
    for name, p in (data.get("projects") or {}).items():
        _match(PROJECT_RE, name, "project name")
        projects[name] = _project(name, p, team)

    devices = {}
    for alias, d in (data.get("devices") or {}).items():
        _match(DEVICE_RE, alias, "device alias")
        _keys(d, {"udid"}, f"device {alias}")
        devices[alias] = _match(UDID_RE, d.get("udid"), f"device {alias} udid")

    return Config(
        install_allowed=_bool(data.get("installAllowed", False), "installAllowed"),
        simulator_allowed=_bool(data.get("simulatorAllowed", False), "simulatorAllowed"),
        team=team,
        state_dir=abs_path("stateDir", "~/Library/Application Support/jorah-ios-runner"),
        handoff_dir=abs_path("handoffDir", "/Users/Shared/jorah-handoff"),
        key_file=abs_path("keyFile", "~/.config/jorah-ios/runner.key"),
        host=host,
        port=port,
        path=list(search),
        developer_dir=developer_dir,
        max_log_bytes=max_log,
        keep_runs=keep,
        timeouts=timeouts,
        projects=projects,
        devices=devices,
    )
