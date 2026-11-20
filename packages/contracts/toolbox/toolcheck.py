"""Contract jorah-tool-v1: Jorah's request to install one tool in the toolbox.

Described in docs/contracts/jorah-tool-v1.md. The same rules are checked in three places, each of
which refuses what fails them: the project runner (requests a run writes), the jorah-projects
plugin (proposals from chat, and again before the card's approval is written; a JavaScript copy
of these rules, tested against the same examples), and the installer (again, as user
jorah-toolbox, just before installing).

Python 3 standard library only. `check(manifest, today)` returns a list of problems, empty when the
manifest is good. `digest(manifest)` is the SHA-256 of its canonical JSON, which names a proposal.

GitHub release assets: a request whose `url` is one may leave out `sha256`, `released` and
`download_mb`. Whoever turns the request into a proposal (the plugin, the runner) asks GitHub's API
for the release (`github_asset`), and `apply_github` fills them in from GitHub's answer, or refuses
the request when Jorah's own values differ. No network here: the callers fetch.

Sizes are limits the installer enforces, not claims. Any archive may leave out `installed_mb`:
`fill_sizes` sets it to a ceiling from the download size and the archive's compression
(`unpack_factor`). A non-GitHub archive may leave out `download_mb` too: the installer then caps the
download at UNSTATED_DOWNLOAD_MB and sets the unpacked ceiling from the bytes it got.
"""

import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote, unquote, urlsplit

CONTRACT = "jorah-tool-v1"
MIN_AGE_DAYS = 7  # Adam's rule: a release is at least 7 days old before it's installed
KINDS = ("archive", "apt")
FORMATS = ("tar", "zip", "appimage", "file")
MAX_DOWNLOAD_MB = 4096
MAX_INSTALLED_MB = 16384
MAX_URL = 150  # the card shows the source in full: guard lines are cut at 160 characters
MAX_LICENCE = 60
MAX_BYTES = 64 * 1024  # a request or proposal file over this is refused unread
UNSTATED_DOWNLOAD_MB = 1024  # the download cap when a non-GitHub request gives no download_mb
SIZE_FLOOR_MB = 64  # the smallest unpacked ceiling filled in for a compressed archive

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
ARCHIVE = {"url": True, "sha256": True, "format": True, "download_mb": False, "installed_mb": False, "commands": True,
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


def check(m, today=None, *, filled_later=()):
    """Problems with manifest `m` (a dict from JSON). `today` (a date) is for the 7-day rule.
    `filled_later`: required fields that may be missing because a lookup fills them in (see
    `check_request`)."""
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
        if required and key not in m and key not in filled_later:
            problems.append(f"{key}: missing" + (MISSING_HINT if key in GITHUB_FILLS else ""))
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

    released = m.get("released", "2000-01-01")
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
        if "sha256" in m and (not isinstance(m["sha256"], str) or not SHA256.match(m["sha256"])):
            problems.append("sha256: 64 lower-case hex digits, from the publisher's checksum")
        if m["format"] not in FORMATS:
            problems.append(f"format: must be one of {', '.join(FORMATS)}")
        given = [_number(problems, m, key, high) for key, high in (("download_mb", MAX_DOWNLOAD_MB), ("installed_mb", MAX_INSTALLED_MB))
                 if key in m]
        if len(given) == 2 and None not in given and given[1] < given[0]:
            problems.append(f"installed_mb: less than the {given[0]} MB download; leave installed_mb out and a limit "
                            "is set from the download size")
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


# ---- GitHub release assets ---------------------------------------------------------------------
# The same pattern as the installer's (services/jorah-toolbox/jorah_toolbox/fetch.py), which asks
# GitHub again at install.

GITHUB_ASSET = re.compile(r"^https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})/releases/download/([^/?#]{1,100})/([^/?#]{1,200})$")
GITHUB_API = "https://api.github.com"
GITHUB_FILLS = ("sha256", "released", "download_mb")
GITHUB_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
ASSET_NAME = re.compile(r"^[A-Za-z0-9._+-]{1,120}$")
MISSING_HINT = " (filled in from GitHub only when url is a GitHub release asset)"
MIB = 1048576


def github_asset(url):
    """For a GitHub release asset URL: {"owner", "repo", "tag", "asset", "path"}, where `path` is the
    API path of the release (append it to GITHUB_API). None for any other URL."""
    match = GITHUB_ASSET.match(url) if isinstance(url, str) else None
    if not match or match.group(2) in (".", ".."):
        return None
    owner, repo = match.group(1), match.group(2)
    tag, asset = unquote(match.group(3)), unquote(match.group(4))
    return {"owner": owner, "repo": repo, "tag": tag, "asset": asset,
            "path": f"/repos/{owner}/{repo}/releases/tags/{quote(tag, safe='')}",
            "list": f"/repos/{owner}/{repo}/releases?per_page=10"}


def check_request(m, today=None):
    """`check` for a request as Jorah writes it: for a GitHub release asset, the fields GitHub
    fills in may be missing. Run `check` again on what `apply_github` returns."""
    url = m.get("url") if isinstance(m, dict) and m.get("kind") == "archive" else None
    return check(m, today, filled_later=GITHUB_FILLS if github_asset(url) else ())


def download_cap(download_mb):
    """The most bytes the installer downloads for `download_mb` (jorah_toolbox/install.py)."""
    return int(download_mb * 1.1 * MIB) + 5 * MIB


def apply_github(m, release):
    """Fill in and check a GitHub release asset request against GitHub's answer for its release
    (the parsed JSON of GET /repos/<owner>/<repo>/releases/tags/<tag>).

    Returns (manifest, record, problems). `manifest` is a copy of `m` with `sha256`, `released`
    and `download_mb` filled in where Jorah left them out. `record` is what GitHub said, kept beside
    the proposal: {"tag", "asset", "publishedAt", "assetBytes", "digest", "immutable", "filled"}.
    A problem means the request is refused: Jorah's value differs from GitHub's, or GitHub's
    release can't be installed (a draft, a pre-release, no such asset, no digest and none given)."""
    where = github_asset(m.get("url"))
    if where is None:
        return m, None, ["url: isn't a GitHub release asset URL"]
    tag, name = where["tag"], where["asset"]
    if not isinstance(release, dict):
        return m, None, ["GitHub's answer isn't a release"]
    problems = []
    out = dict(m)
    record = {"tag": tag, "asset": name, "publishedAt": None, "assetBytes": None, "digest": None,
              "immutable": release.get("immutable") if isinstance(release.get("immutable"), bool) else None, "filled": []}
    if release.get("draft"):
        problems.append(f"url: GitHub marks release {tag} a draft")
    if release.get("prerelease"):
        problems.append(f"url: GitHub marks {tag} a pre-release; pick a full release")

    published = release.get("published_at")
    day = None
    if isinstance(published, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", published):
        try:
            day = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
        except ValueError:
            day = None
    if day is None:
        problems.append(f"released: GitHub gives no publication date for {tag}")
    else:
        record["publishedAt"] = published
        if "released" not in m:
            out["released"] = day
            record["filled"].append("released")
        elif m["released"] != day:
            problems.append(f"released: GitHub says {tag} was published {day} (UTC), not {m['released']}; "
                            "leave released out and it is filled in")

    assets = [a for a in release.get("assets") or [] if isinstance(a, dict)]
    found = next((a for a in assets if a.get("name") == name), None)
    if found is None:
        names = [a["name"] for a in assets if isinstance(a.get("name"), str) and ASSET_NAME.match(a["name"])][:8]
        problems.append(f"url: release {tag} has no asset named {name[:80]}" + (f"; its assets include {', '.join(names)}" if names else ""))
        return out, record, problems
    if found.get("state") not in (None, "uploaded"):
        problems.append(f"url: GitHub says {name[:80]} isn't fully uploaded")

    digest_match = GITHUB_DIGEST.match(found["digest"]) if isinstance(found.get("digest"), str) else None
    if digest_match:
        record["digest"] = found["digest"]
        hexdigest = digest_match.group(1)
        if "sha256" not in m:
            out["sha256"] = hexdigest
            record["filled"].append("sha256")
        elif m["sha256"] != hexdigest:
            problems.append(f"sha256: GitHub's digest for {name[:80]} is {hexdigest[:16]}..., not {str(m['sha256'])[:16]}...; "
                            "leave sha256 out and it is filled in")
    elif "sha256" not in m:
        problems.append("sha256: GitHub holds no digest for this asset (an older release): give the publisher's own checksum")

    size = found.get("size")
    if isinstance(size, int) and not isinstance(size, bool) and size > 0:
        record["assetBytes"] = size
        need = max(1, math.ceil(size / MIB))
        given = m.get("download_mb")
        if given is None:
            out["download_mb"] = need
            record["filled"].append("download_mb")
        elif isinstance(given, int) and not isinstance(given, bool) and (size > download_cap(given) or abs(given - size / MIB) > max(3, size / MIB / 4)):
            problems.append(f"download_mb: GitHub says {name[:80]} is {size} bytes; use {need}, or leave download_mb out")
    return out, record, problems


# ---- sizes -------------------------------------------------------------------------------------
# How many times its download an archive may grow when unpacked. Measured 2026-11-20 on 14 real
# Linux releases (docs/contracts/jorah-tool-v1.md, "Sizes"): zip at most 2.3x, AppImage 3.2x,
# gzip tar 3.5x, xz tar 12.8x (helix: its grammars compress well). Each factor leaves room above
# the largest seen; the installer also allows 25% and 50 MB over the ceiling.

def unpack_factor(fmt, url):
    if fmt == "file":
        return 1
    if fmt == "zip":
        return 4
    if fmt == "appimage":
        return 6
    path = url.split("#")[0].split("?")[0].lower() if isinstance(url, str) else ""
    return 6 if path.endswith((".tar.gz", ".tgz")) else 16


def installed_ceiling(fmt, url, download_mb):
    """The unpacked ceiling, in whole MB, for an archive of `download_mb`."""
    factor = unpack_factor(fmt, url)
    mb = download_mb * factor
    return min(MAX_INSTALLED_MB, mb if factor == 1 else max(SIZE_FLOOR_MB, mb))


def fill_sizes(m):
    """(manifest, filled): for an archive with a download size and no `installed_mb`, a copy with
    `installed_mb` set to `installed_ceiling`. Run after `apply_github`, before `check`."""
    if not isinstance(m, dict) or m.get("kind") != "archive" or "installed_mb" in m:
        return m, []
    download_mb = m.get("download_mb")
    if not isinstance(download_mb, int) or isinstance(download_mb, bool) or not 1 <= download_mb <= MAX_DOWNLOAD_MB:
        return m, []
    return {**m, "installed_mb": installed_ceiling(m.get("format"), m.get("url"), download_mb)}, ["installed_mb"]


TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_~-]{0,59}$")


def _published_day(release):
    published = release.get("published_at")
    if not isinstance(published, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", published):
        return None
    try:
        return datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        return None


def older_release(releases, where, today):
    """From GitHub's list of releases (GET <where["list"]>), the newest full release published at
    least MIN_AGE_DAYS before `today`: {"tag", "released", "url"}, `url` being its asset named like
    the request's (the tag or version swapped in), or None when it has none. None if there is no
    such release."""
    limit = today - timedelta(days=MIN_AGE_DAYS)
    best = None
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag, day = release.get("tag_name"), _published_day(release)
        if not isinstance(tag, str) or not TAG.match(tag) or day is None or day > limit:
            continue
        if best is None or release["published_at"] > best[0]["published_at"]:
            best = (release, tag, day)
    if best is None:
        return None
    release, tag, day = best
    names = {a.get("name") for a in release.get("assets") or [] if isinstance(a, dict)}
    old, new = where["tag"], tag
    tries = [where["asset"].replace(old, new), where["asset"].replace(old.lstrip("vV"), new.lstrip("vV")) if old.lstrip("vV") else None]
    found = next((n for n in tries if n and n in names and ASSET_NAME.match(n)), None)
    url = (f"https://github.com/{where['owner']}/{where['repo']}/releases/download/{quote(tag, safe='')}/{quote(found, safe='')}"
           if found else None)
    return {"tag": tag, "released": day.isoformat(), "url": url}


def digest(m):
    """SHA-256 of the canonical JSON of manifest `m` (sorted keys, no spaces, UTF-8)."""
    return hashlib.sha256(json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def proposal_id(m):
    return "tb-" + digest(m)[:10]


def source_text(m):
    """What the card's `source` line says: the URL, or the Ubuntu packages."""
    return m["url"] if m.get("kind") == "archive" else "Ubuntu archive: " + " ".join(m.get("packages") or [])


def size_text(m):
    """The card's size line. For an archive both numbers are limits the installer enforces."""
    download, installed = m.get("download_mb"), m.get("installed_mb")
    if m.get("kind") != "archive":
        if download is None and installed is None:
            return "not given (apt shows it before installing)"
        fmt = lambda v: "?" if v is None else f"{v:g}"  # noqa: E731
        return f"{fmt(download)} MB download, {fmt(installed)} MB installed"
    if download is None:
        first = f"up to {UNSTATED_DOWNLOAD_MB} MB download (measured at install)"
        if installed is not None:
            return f"{first}, up to {installed} MB installed"
        factor = unpack_factor(m.get("format"), m.get("url"))
        return f"{first}, installed " + (f"up to {factor}x it, min {SIZE_FLOOR_MB} MB" if factor > 1 else "the same")
    if installed is None:
        installed = installed_ceiling(m.get("format"), m.get("url"), download)
    return f"{download} MB download, up to {installed} MB installed"


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
