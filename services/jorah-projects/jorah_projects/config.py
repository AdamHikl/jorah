"""The runner's settings and the project registry (plan 11, sections 3.4 and 4).

Paths default to the PC's. Tests build a Settings with their own folders. The registry is
`/home/jorah/.config/jorah-projects/projects.json`, mode 600, one entry per project; each entry is
checked against `project-config.schema.json` from the contract and against the hard limits below,
which no registry value can loosen.
"""

import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from . import contract

HOME = Path("/home/jorah")
REPO_ROOT = Path(__file__).resolve().parents[3]

PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")  # the contract's registry key form
REPO = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
BRANCH = re.compile(r"^jorah/[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")
SLOT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
STATE_DIR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")

# Hard ranges, the same as the contract's project-config schema, checked here again so no schema
# edit alone can loosen them (PM-T6, runaway use).
LIMIT_RANGES = {"runsPerDay": (0, 8), "minutesPerRun": (5, 120), "maxTurns": (1, 500)}
DEFAULT_LIMITS = {"runsPerDay": 3, "minutesPerRun": 45, "maxTurns": 200}
BENCHES = {"robotics"}


class ConfigError(ValueError):
    pass


@dataclass
class Settings:
    """Where things are. One per runner process."""

    registry: Path = HOME / ".config/jorah-projects/projects.json"
    runner_file: Path = HOME / ".config/jorah-projects/runner.json"
    state_root: Path = HOME / ".jorah-projects"
    work_root: Path = HOME / "work"
    mirror_dir: Path = HOME / ".jorah-github/mirrors"
    freeze_file: Path = HOME / ".jorah-guard/FROZEN"
    claude_bin: Path = Path("/opt/jorah-tools/claude-code/2.1.300/claude")
    claude_config_dir: Path = HOME / ".claude-jorah"
    sandbox_dir: Path = HOME / "sandbox"
    bench_env: dict = field(default_factory=lambda: {"robotics": Path("/opt/jorah-bench/env.sh")})
    contracts: Path = REPO_ROOT / "packages/contracts/project"
    brief_template: Path = Path(__file__).resolve().parents[1] / "brief.md"
    setup_brief_template: Path = Path(__file__).resolve().parents[1] / "brief-setup.md"
    templates: Path = REPO_ROOT / "templates/project"  # copied into a new project's folder by its setup run
    gitleaks_bin: str = "/usr/local/bin/gitleaks"
    gitleaks_config: Path = Path(__file__).resolve().parents[1] / "gitleaks.toml"
    sync_cmd: list = field(default_factory=lambda: ["/usr/bin/node", str(REPO_ROOT / "plugins/jorah-github/bin/jorah-github-sync.mjs")])
    git_bin: str = "/usr/bin/git"
    timezone: str = "Europe/Bratislava"
    github_app_id: str = ""
    github_owner: str = ""
    model: str = "claude-opus-5-5"
    effort: str = "high"
    min_free_bytes: int = 5 * 1024**3
    kill_grace_seconds: int = 30
    default_backoff_minutes: int = 60
    weekly_ceiling: float = 0.85
    default_hold_hours: int = 48
    require_root_owned_bench: bool = True

    def project_state(self, name):
        return Path(self.state_root) / name

    @property
    def project_settings_file(self):
        return Path(self.claude_config_dir) / "project-settings.json"

    @property
    def project_settings_web_file(self):
        return Path(self.claude_config_dir) / "project-settings-web.json"


RUNNER_KEYS = {"githubAppId": "github_app_id", "githubOwner": "github_owner", "timezone": "timezone",
               "claude": "claude_bin", "gitleaks": "gitleaks_bin", "templates": "templates"}
PATH_KEYS = {"claude_bin", "templates"}


def load_runner_file(settings):
    """Overlay /home/jorah/.config/jorah-projects/runner.json (written by install-projects.sh)."""
    path = Path(settings.runner_file)
    if not path.exists():
        return settings
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("runner.json must hold an object")
    for key, value in data.items():
        if key not in RUNNER_KEYS or not isinstance(value, str):
            raise ConfigError(f"runner.json: unknown or non-text key {key[:40]}")
        attr = RUNNER_KEYS[key]
        setattr(settings, attr, Path(value) if attr in PATH_KEYS else value)
    if settings.github_app_id and not settings.github_app_id.isdigit():
        raise ConfigError("runner.json: githubAppId must be a number")
    if settings.github_owner and not re.match(r"^[A-Za-z0-9-]+$", settings.github_owner):
        raise ConfigError("runner.json: githubOwner must be a GitHub account name")
    return settings


@dataclass
class Project:
    name: str
    repo: str | None  # None: local only, no GitHub repo yet
    work_dir: Path
    branch: str
    state_dir: str
    level: int
    schedule: list
    limits: dict
    web: bool
    bench: str | None
    paused: bool


def _private_file(path):
    info = os.stat(path)
    if stat.S_ISLNK(os.lstat(path).st_mode) or not stat.S_ISREG(info.st_mode):
        raise ConfigError(f"{path} isn't a plain file")
    if info.st_mode & 0o077:
        raise ConfigError(f"{path} must be mode 600 (readable by jorah only)")
    if info.st_uid != os.getuid():
        raise ConfigError(f"{path} isn't owned by the runner's user")


def parse_entry(settings, name, entry, pc=None):
    """One registry entry. `pc` is the contract checker; without it only the hard checks run."""
    if not PROJECT_NAME.match(name):
        raise ConfigError(f"project name {name[:40]!r} isn't allowed")
    if not isinstance(entry, dict):
        raise ConfigError(f"{name}: entry must be an object")
    repo = entry.get("repo")
    local_only = "repo" in entry and repo is None
    if pc is not None:
        problems = contract.entry_problems(pc, name, entry)
        if local_only:
            # `repo: null` is a local-only project (no GitHub repo yet). Kept here as well as in the
            # contract, so the runner doesn't depend on which schema version is installed.
            problems = [p for p in problems if not p.startswith("$.repo")]
        if problems:
            raise ConfigError(f"{name}: doesn't match the contract ({problems[0]})")
    if not local_only and (not isinstance(repo, str) or not REPO.match(repo)):
        raise ConfigError(f"{name}: repo must be owner/name, or null for a local-only project")
    if not local_only and settings.github_owner and repo.split("/")[0].lower() != settings.github_owner.lower():
        raise ConfigError(f"{name}: {repo} isn't {settings.github_owner}'s")
    work_root = Path(os.path.realpath(settings.work_root))
    work_dir = Path(entry.get("workDir") or (Path(settings.work_root) / name))
    if not work_dir.is_absolute() or work_dir.parent != Path(settings.work_root):
        raise ConfigError(f"{name}: workDir must be a folder directly under {settings.work_root}")
    if work_dir.exists() and Path(os.path.realpath(work_dir)).parent != work_root:
        raise ConfigError(f"{name}: workDir resolves outside {settings.work_root}")
    branch = entry.get("branch", "jorah/line")
    if not isinstance(branch, str) or not BRANCH.match(branch) or ".." in branch or branch.endswith(".lock"):
        raise ConfigError(f"{name}: branch must be jorah/<name>")
    state_dir = entry.get("stateDir", "project")
    if not isinstance(state_dir, str) or not STATE_DIR.match(state_dir) or ".." in state_dir.split("/") or state_dir.startswith(".git"):
        raise ConfigError(f"{name}: stateDir must be a plain relative folder")
    level = entry.get("level", 0)
    if not isinstance(level, int) or isinstance(level, bool) or level not in (0, 1, 2):
        raise ConfigError(f"{name}: level must be 0, 1 or 2")
    schedule = entry.get("schedule", [])
    if not isinstance(schedule, list) or not all(isinstance(s, str) and SLOT.match(s) for s in schedule) or len(schedule) > 24:
        raise ConfigError(f"{name}: schedule must be a list of HH:MM")
    limits = dict(DEFAULT_LIMITS)
    raw_limits = entry.get("limits", {})
    if not isinstance(raw_limits, dict):
        raise ConfigError(f"{name}: limits must be an object")
    for key, value in raw_limits.items():
        if key not in LIMIT_RANGES:
            raise ConfigError(f"{name}: unknown limit {key[:40]}")
        low, high = LIMIT_RANGES[key]
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ConfigError(f"{name}: {key} must be a whole number from {low} to {high}")
        limits[key] = value
    web = entry.get("web", False)
    bench = entry.get("bench")
    paused = entry.get("paused", False)
    if not isinstance(web, bool) or not isinstance(paused, bool):
        raise ConfigError(f"{name}: web and paused must be true or false")
    if bench is not None and bench not in BENCHES:
        raise ConfigError(f"{name}: bench must be one of {sorted(BENCHES)} or null")
    return Project(name=name, repo=repo, work_dir=work_dir, branch=branch, state_dir=state_dir, level=level,
                   schedule=sorted(set(schedule)), limits=limits, web=web, bench=bench, paused=paused)


def load_registry(settings, pc=None, check_mode=True):
    """{name: Project or ConfigError}. A bad entry doesn't stop the others; a bad file stops all."""
    path = Path(settings.registry)
    if not path.exists():
        return {}
    if check_mode:
        _private_file(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ConfigError(f"{path.name} isn't valid JSON: {error}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must hold an object of projects")
    projects = {}
    for name, entry in data.items():
        try:
            projects[name] = parse_entry(settings, name, entry, pc)
        except ConfigError as error:
            projects[name] = error
    return projects
