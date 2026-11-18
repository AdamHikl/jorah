"""Contract jorah-tool-v1: Jorah's request to install one tool in the toolbox.

Described in docs/contracts/jorah-tool-v1.md. The same rules are checked in three places, each of
which refuses what fails them: the project runner (requests a run writes), the jorah-projects
plugin (proposals from chat, and again before the card's approval is written; a JavaScript copy
of these rules, tested against the same examples), and the installer (again, as user
jorah-toolbox, just before installing).

Python 3 standard library only. `check(manifest, today)` returns a list of problems, empty when the
manifest is good. `digest(manifest)` is the SHA-256 of its canonical JSON, which names a proposal.
"""

import hashlib
import json
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

CONTRACT = "jorah-tool-v1"
MIN_AGE_DAYS = 7  # Adam's rule: a release is at least 7 days old before it's installed
KINDS = ("archive", "apt")
FORMATS = ("tar", "zip", "appimage", "file")
MAX_DOWNLOAD_MB = 4096
MAX_INSTALLED_MB = 16384
MAX_URL = 150  # the card shows the source in full: guard lines are cut at 160 characters
MAX_LICENCE = 60
MAX_BYTES = 64 * 1024  # a request or proposal file over this is refused unread

NAME = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_~-]{0,29}$")
COMMAND = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,39}$")
PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
PACKAGE = re.compile(r"^[a-z0-9][a-z0-9+.-]{1,62}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ENV_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
PLACEHOLDER = re.compile(r"\$\{(TOOL|STATE)\}")
# Variables a tool's wrapper may not set: they would change how the shell, the loader or Python
# behave for everything the tool starts, or move its writes out of its own cache.
FORBIDDEN_ENV = {"PATH", "HOME", "SHELL", "ENV", "BASH_ENV", "IFS", "PS4", "PROMPT_COMMAND", "LD_PRELOAD", "LD_AUDIT",
                 "PYTHONSTARTUP", "PYTHONHOME", "NODE_OPTIONS", "GIT_SSH", "GIT_SSH_COMMAND", "GIT_EXEC_PATH",
                 "JORAH_TOOLBOX_STATE", "TMPDIR", "XDG_RUNTIME_DIR", "CLAUDE_CONFIG_DIR"}

COMMON = {
    "contract": True, "name": True, "title": True, "version": True, "kind": True, "purpose": True, "homepage": True,
    "licence": True, "licence_source": True, "released": True, "release_page": True, "sandbox": True, "smoke": True,
    "for_project": False, "smoke_expect": False,
}
ARCHIVE = {"url": True, "sha256": True, "format": True, "download_mb": True, "installed_mb": True, "commands": True,
           "strip": False, "env": False}
APT = {"packages": True, "download_mb": False, "installed_mb": False}


def _text(problems, m, key, low, high, *, one_line=True):
    value = m.get(key)
    if not isinstance(value, str) or not low <= len(value.strip()) <= high or value != value.strip():
        problems.append(f"{key}: must be text of {low} to {high} characters, without spaces at the ends")
        return None
    if one_line and ("\n" in value or "\r" in value):
        problems.append(f"{key}: must be one line")
    if any(ord(c) < 32 and c not in "\n\t" for c in value) or "\x7f" in value:
        problems.append(f"{key}: has control characters")
    return value


def _https(problems, key, value, high):
    if not isinstance(value, str) or not 12 <= len(value) <= high:
        problems.append(f"{key}: must be an https URL of at most {high} characters")
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        problems.append(f"{key}: isn't a URL")
        return None
    host = parts.hostname or ""
    if parts.scheme != "https" or not host or parts.username or parts.password or parts.port not in (None, 443):
        problems.append(f"{key}: must be https, on the default port, with no user or password")
        return None
    if re.match(r"^[0-9.]+$", host) or ":" in host or "." not in host or host.endswith((".local", ".internal", ".localhost", ".lan")):
        problems.append(f"{key}: must name a public host, not an address")
    if any(c.isspace() for c in value) or "\\" in value:
        problems.append(f"{key}: has spaces or backslashes")
    return value


def _number(problems, m, key, high):
    # Whole megabytes: no floats anywhere in a manifest, so Python and JavaScript hash it alike.
    value = m.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= high:
        problems.append(f"{key}: must be a whole number of megabytes from 1 to {high}")
        return None
    return value


RELPART = re.compile(r"^[A-Za-z0-9_+@-][A-Za-z0-9._+@-]{0,99}$")


def _relpath(value):
    """A path inside the tool: plain parts only (it is written into a shell wrapper)."""
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        return False
    return all(RELPART.match(p) and p not in (".", "..") for p in value.split("/"))


def check(m, today=None):
    """Problems with manifest `m` (a dict from JSON). `today` (a date) is for the 7-day rule."""
    today = today or date.today()
    if not isinstance(m, dict):
        return ["the request must be a JSON object"]
    problems = []
    kind = m.get("kind")
    if kind not in KINDS:
        problems.append(f"kind: must be one of {', '.join(KINDS)}")
        fields = dict(COMMON)
    else:
        fields = {**COMMON, **(ARCHIVE if kind == "archive" else APT)}
    for key in m:
        if key not in fields:
            problems.append(f"{str(key)[:40]}: unknown field")
    for key, required in fields.items():
        if required and key not in m:
            problems.append(f"{key}: missing")
    if problems:
        return problems

    if m["contract"] != CONTRACT:
        problems.append(f"contract: must be {CONTRACT}")
    if not isinstance(m["name"], str) or not NAME.match(m["name"]):
        problems.append("name: lower-case letters, digits and dashes, 2 to 40, starting with a letter")
    _text(problems, m, "title", 1, 80)
    if not isinstance(m["version"], str) or not VERSION.match(m["version"]):
        problems.append("version: letters, digits and . + _ ~ -, at most 30, starting with a letter or digit")
    _text(problems, m, "purpose", 10, 600, one_line=False)
    _https(problems, "homepage", m["homepage"], 300)
    _https(problems, "release_page", m["release_page"], 300)
    _text(problems, m, "licence", 2, MAX_LICENCE)
    _text(problems, m, "licence_source", 2, 300)

    released = m["released"]
    if not isinstance(released, str) or not DAY.match(released):
        problems.append("released: must be a date, YYYY-MM-DD")
    else:
        try:
            day = date.fromisoformat(released)
        except ValueError:
            problems.append("released: isn't a real date")
        else:
            if day > today - timedelta(days=MIN_AGE_DAYS):
                problems.append(f"released: {released} is less than {MIN_AGE_DAYS} days ago; wait until "
                                f"{(day + timedelta(days=MIN_AGE_DAYS)).isoformat()} or pick an older release")

    project = m.get("for_project")
    if project is not None and (not isinstance(project, str) or not PROJECT.match(project)):
        problems.append("for_project: a project's name, or null")

    sandbox = m["sandbox"]
    if not isinstance(sandbox, dict) or set(sandbox) != {"network"} or sandbox.get("network") != []:
        problems.append('sandbox: must be {"network": []}: toolbox tools run offline inside the project sandbox; '
                        "a tool that needs the network while it runs is a build-session decision")

    if kind == "archive":
        _https(problems, "url", m["url"], MAX_URL)
        if not isinstance(m["sha256"], str) or not SHA256.match(m["sha256"]):
            problems.append("sha256: 64 lower-case hex digits, from the publisher's checksum")
        if m["format"] not in FORMATS:
            problems.append(f"format: must be one of {', '.join(FORMATS)}")
        _number(problems, m, "download_mb", MAX_DOWNLOAD_MB)
        _number(problems, m, "installed_mb", MAX_INSTALLED_MB)
        strip = m.get("strip", 0)
        if not isinstance(strip, int) or isinstance(strip, bool) or not 0 <= strip <= 3:
            problems.append("strip: a whole number from 0 to 3")
        elif strip and m["format"] not in ("tar", "zip"):
            problems.append("strip: only for tar and zip")
        commands = m["commands"]
        if not isinstance(commands, dict) or not 1 <= len(commands) <= 12:
            problems.append("commands: an object of 1 to 12 command names and paths inside the tool")
            commands = {}
        for cmd, path in commands.items():
            if not COMMAND.match(cmd):
                problems.append(f"commands: {cmd[:40]!r} isn't a plain command name")
            if not _relpath(path):
                problems.append(f"commands.{cmd[:40]}: must be a relative path inside the tool: letters, digits and . _ + @ -, no .. or empty parts")
        if m["format"] == "file" and len(commands) != 1:
            problems.append("commands: a single-file tool has exactly one command")
        env = m.get("env", {})
        if not isinstance(env, dict) or len(env) > 12:
            problems.append("env: an object of at most 12 variables")
            env = {}
        for key, value in env.items():
            if not ENV_KEY.match(key) or key in FORBIDDEN_ENV or key.startswith(("LD_", "BASH_FUNC", "DYLD_")):
                problems.append(f"env: {key[:40]} can't be set")
                continue
            rest = PLACEHOLDER.sub("", value) if isinstance(value, str) else None
            if rest is None or len(value) > 300 or any(c in rest for c in '$`"\\\n\r') or any(ord(c) < 32 for c in value):
                problems.append(f"env.{key}: text of at most 300 characters; only ${{TOOL}} and ${{STATE}} may be used, "
                                "and no $, backquote, double quote, backslash or newline otherwise")
        smoke_names = set(commands)
    else:
        packages = m["packages"]
        if not isinstance(packages, list) or not 1 <= len(packages) <= 20 or not all(isinstance(p, str) and PACKAGE.match(p) for p in packages):
            problems.append("packages: 1 to 20 Ubuntu package names")
        elif len(set(packages)) != len(packages):
            problems.append("packages: a name is listed twice")
        elif len(" ".join(packages)) > MAX_URL - 16:
            problems.append(f"packages: at most {MAX_URL - 16} characters in all (the card shows them in full)")
        for key in ("download_mb", "installed_mb"):
            if key in m:
                _number(problems, m, key, MAX_INSTALLED_MB)
        smoke_names = None

    smoke = m["smoke"]
    if not isinstance(smoke, list) or not 1 <= len(smoke) <= 20 or not all(isinstance(a, str) and 0 < len(a) <= 300 for a in smoke):
        problems.append("smoke: a command line as a list of 1 to 20 arguments")
    elif any(any(ord(c) < 32 for c in a) for a in smoke):
        problems.append("smoke: arguments can't have control characters")
    elif smoke_names is not None and smoke[0] not in smoke_names:
        problems.append("smoke: must start with one of the tool's commands")
    elif smoke_names is None and not COMMAND.match(smoke[0]):
        problems.append("smoke: must start with a plain command name")
    if "smoke_expect" in m:
        _text(problems, m, "smoke_expect", 1, 200)
    return problems


def digest(m):
    """SHA-256 of the canonical JSON of manifest `m` (sorted keys, no spaces, UTF-8)."""
    return hashlib.sha256(json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def proposal_id(m):
    return "tb-" + digest(m)[:10]


def source_text(m):
    """What the card's `source` line says: the URL, or the Ubuntu packages."""
    return m["url"] if m.get("kind") == "archive" else "Ubuntu archive: " + " ".join(m.get("packages") or [])


def size_text(m):
    if m.get("download_mb") is None and m.get("installed_mb") is None:
        return "not given (apt shows it before installing)"
    fmt = lambda v: "?" if v is None else f"{v:g}"  # noqa: E731
    return f"{fmt(m.get('download_mb'))} MB download, {fmt(m.get('installed_mb'))} MB installed"


def card_fields(m, proposal):
    """The exact fields toolbox_install takes and the card shows. The plugin builds the same."""
    return {
        "id": proposal,
        "name": m["name"],
        "version": m["version"],
        "source": source_text(m),
        "sha256": m["sha256"][:16] if m.get("kind") == "archive" else "none (Ubuntu's signed archive)",
        "licence": m["licence"],
        "released": m["released"],
        "size": size_text(m),
    }


def load_file(path):
    """A request or proposal file's manifest, read with a size cap. Raises ValueError."""
    with open(path, "rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"over {MAX_BYTES // 1024} KB")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"isn't JSON: {str(error)[:80]}") from None


if __name__ == "__main__":  # python3 -I toolcheck.py request.json: prints problems, exits 1 if any
    import sys

    try:
        found = check(load_file(sys.argv[1]))
    except (OSError, ValueError, IndexError) as error:
        found = [str(error)]
    for line in found:
        print(line)
    sys.exit(1 if found else 0)
