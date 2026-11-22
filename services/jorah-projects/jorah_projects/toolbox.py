"""Jorah's toolbox, the runner's side (docs/runbooks/toolbox.md).

The installer (services/jorah-toolbox, user jorah-toolbox) puts approved tools in /opt/jorah-toolbox.
The runner does the rest, as jorah, outside the sandbox:

- **Requests from runs.** A run that needs a tool writes `~/work/.toolbox/requests/<name>.json`
  (contract jorah-tool-v1). After the run, the runner checks each one and turns the good ones into
  proposals in /var/lib/jorah-toolbox/proposals/, where Jorah sees them (toolbox_list) and Adam
  approves them on a card (toolbox_install). Bad ones move to requests/bad/ with the reason beside
  them, so the next run can fix them. For a GitHub release asset the runner asks GitHub's API for
  the release itself and takes the hash, the date and the size from it (`github_get`); a request
  waits in place while GitHub can't be asked.
- **Smoke test.** Every newly installed tool's smoke command runs once in bubblewrap: no network,
  the system read-only, the home folder empty except the tool's own state folder. The record goes
  to /var/lib/jorah-toolbox/tested/<name>.json. This is the runner's measurement, not a run's word.
- **Learning run.** After a tool passes, one short Claude Code run in ~/work/.toolbox (a local git
  repo with no remote) tries the tool on its purpose and writes Jorah's notes,
  notes/<name>.md. Every project run's brief lists the tools and their notes.
- **Notes are committed** by the runner after every run, so each change is in the history.

`~/work/.toolbox` sits in ~/work, which runs may write; its name starts with a dot, which no
project name can.
"""

import importlib.util
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from . import fsio
from .gitsafe import GitError, Repo, UnsafeRepo, init_local

NOTE_FILE = re.compile(r"^[a-z][a-z0-9-]{1,39}\.md$")
MAX_OUTPUT = 4000


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_contract(settings):
    path = Path(settings.toolbox_contract) / "toolcheck.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("jorah_toolcheck", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 - a broken contract means no requests are taken
        return None
    return module


def available(settings):
    """True when the toolbox is installed: its registry folder and state folder exist."""
    return Path(settings.toolbox_dir).is_dir() and Path(settings.toolbox_var).is_dir()


def installed(settings):
    """{name: entry} from /opt/jorah-toolbox/installed.json, or {} if there's none or it's damaged."""
    path = Path(settings.toolbox_dir) / "installed.json"
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > (4 << 20):
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tools = data.get("tools") if isinstance(data, dict) else None
    if not isinstance(tools, dict):
        return {}
    return {n: t for n, t in tools.items() if isinstance(t, dict) and isinstance(n, str) and NOTE_FILE.match(f"{n}.md")}


def tested(settings, name):
    path = Path(settings.toolbox_var) / "tested" / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_tested(settings, name, record):
    folder = Path(settings.toolbox_var) / "tested"
    folder.mkdir(exist_ok=True)
    path = folder / f"{name}.json"
    tmp = folder / f".{name}.json.tmp"
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def work_dir(settings):
    return Path(settings.work_root) / ".toolbox"


# ---- writing where runs can write -------------------------------------------------------------------
# ~/work/.toolbox is run-writable: a run could leave a link where the runner is about to write or
# move a file, to make the runner (outside the sandbox) write elsewhere. So folders are made real
# (a link in their place is removed) and files are created fresh, never written through a link.

def real_dir(path):
    """`path` as a real folder: a link or a file in its place is removed first."""
    path = Path(path)
    if os.path.islink(path) or (os.path.lexists(path) and not path.is_dir()):
        os.unlink(path)
    path.mkdir(exist_ok=True)
    return path


def fresh_file(path, text):
    """Write `text` to a new file at `path`, replacing whatever entry was there, never following a link."""
    if os.path.lexists(path):
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _plain_tree(path):
    """True if `path` and every folder above it up to work_root are real folders, not links."""
    path = Path(path)
    return path.is_dir() and not any(os.path.islink(p) for p in (path, path.parent))


# ---- the notes repo --------------------------------------------------------------------------------

README = """# Jorah's toolbox notes

What Jorah learned about each tool in his toolbox (/opt/jorah-toolbox) and the system tools (KiCad).
A local repo with no remote: the project runner commits every change after a run.

- `notes/<tool>.md`: what the tool is for, commands that worked, profiles and settings, pitfalls.
- `examples/<tool>/`: small working examples (each file under 5 MB).
- `requests/<tool>.json`: a request for a new tool (contract jorah-tool-v1,
  /opt/jorah/docs/contracts/jorah-tool-v1.md). Leave installed_mb out: a limit is set from the download
  size. For a GitHub release asset, also leave sha256, released and download_mb out: the runner reads
  them from GitHub. Elsewhere give download_mb only if the publisher states it; the installer measures
  it otherwise. The runner takes it after the run; Adam approves it on a card.
  Refused requests move to `requests/bad/` with the reason in a `.why.txt` beside them.
"""


def ensure_repo(settings, home):
    """The notes repo, made on first use. Returns a Repo, or None if it can't be used safely."""
    path = work_dir(settings)
    if not os.path.lexists(path):
        repo = init_local(path, home=home, git=settings.git_bin, message="Start Jorah's toolbox notes")
        for sub in ("notes", "examples", "requests"):
            (path / sub).mkdir()
        (path / "README.md").write_text(README, encoding="utf-8")
        (path / ".gitignore").write_text("/requests/\n", encoding="utf-8")
        (path / "notes" / ".keep").write_text("", encoding="utf-8")
        repo.commit_all("Notes folder layout")
        return repo
    if os.path.islink(path) or not path.is_dir():
        return None
    if not os.path.lexists(path / ".git"):
        # A run made the folder before the runner did: make it a repo in place, files and all.
        tmp = path.parent / ".toolbox-init"
        shutil.rmtree(tmp, ignore_errors=True)
        init_local(tmp, home=home, git=settings.git_bin, message="Start Jorah's toolbox notes")
        os.rename(tmp / ".git", path / ".git")
        shutil.rmtree(tmp, ignore_errors=True)
        if not os.path.lexists(path / ".gitignore"):
            fresh_file(path / ".gitignore", "/requests/\n")
    repo = Repo(path, home=home, git=settings.git_bin)
    try:
        repo.check_config()
    except UnsafeRepo:
        return None
    for sub in ("notes", "examples", "requests"):
        target = path / sub
        if not os.path.lexists(target):
            target.mkdir()
    return repo


def commit_notes(settings, home, message):
    """Commit what runs changed in the notes repo. Returns {"commit", "files"} or {"error"}."""
    try:
        repo = ensure_repo(settings, home)
        if repo is None:
            return {"error": "~/work/.toolbox isn't a safe git repo; not committed"}
        if repo.current_branch() != "main":
            return {"error": f"~/work/.toolbox is on {repo.current_branch() or 'a detached HEAD'}, not main; not committed"}
        start = repo.head()
        sha = repo.commit_all(message)
        if sha is None:
            return {"commit": None, "files": []}
        files = [f for c in repo.commits_since(start) for f in c["files"]]
        return {"commit": sha[:12], "files": sorted(set(files))[:50]}
    except (GitError, UnsafeRepo, OSError, subprocess.SubprocessError) as error:
        return {"error": f"notes not committed: {str(error)[:160]}"}


# ---- GitHub's record of a release ------------------------------------------------------------------
# One GET to api.github.com per GitHub-hosted request, unauthenticated (60 an hour per address),
# backed by an on-disk cache (TTL 6h, If-None-Match 304s, and 7-day stale fallback on rate limit).

GITHUB_TIMEOUT = 20
GITHUB_MAX_BYTES = 4 << 20
GITHUB_CACHE_FILE = "github-cache.json"
GITHUB_CACHE_TTL_SECONDS = 6 * 3600
GITHUB_CACHE_MAX_STALE_SECONDS = 7 * 86400
GITHUB_CACHE_MAX_ENTRIES = 64
_MAX_CACHE_FILE_BYTES = 8 << 20


class GitHubLookupError(Exception):
    """`final`: the request itself is wrong (no such release). Otherwise GitHub can't be asked now."""

    def __init__(self, reason, final=False):
        super().__init__(reason)
        self.final = final


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://api.github.com/"):
            raise GitHubLookupError("GitHub's API redirected away from api.github.com")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsOnly, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def _parse_iso_utc(value):
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clean_etag(value):
    if isinstance(value, str) and 0 < len(value) <= 512 and "\r" not in value and "\n" not in value:
        return value
    return None


def _gh_cache_read(path):
    path = Path(path)
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_CACHE_FILE_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("entries"), dict):
        return {}
    out = {}
    for url, raw in data["entries"].items():
        if not isinstance(url, str) or not url or not isinstance(raw, dict):
            continue
        if _parse_iso_utc(raw.get("fetchedAt")) is None or "body" not in raw:
            continue
        out[url] = {"etag": _clean_etag(raw.get("etag")), "body": raw["body"], "fetchedAt": raw["fetchedAt"]}
    return out


def _gh_cache_set(path, url, etag, body, fetched_at, max_entries=GITHUB_CACHE_MAX_ENTRIES):
    entries = _gh_cache_read(path)
    entries[url] = {"etag": _clean_etag(etag), "body": body, "fetchedAt": fetched_at}
    if len(entries) > max_entries:
        ordered = sorted(
            entries.items(),
            key=lambda kv: _parse_iso_utc(kv[1].get("fetchedAt")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        entries = dict(ordered[:max_entries])
    fsio.write_private_json(path, {"v": 1, "entries": entries})


def github_get(url, opener=None, *, cache_path=None, now=None,
               ttl_seconds=GITHUB_CACHE_TTL_SECONDS, max_stale_seconds=GITHUB_CACHE_MAX_STALE_SECONDS):
    """GitHub's API answer at `url` (https://api.github.com/...), parsed. Raises GitHubLookupError."""
    opener = opener or _OPENER
    if not url.startswith("https://api.github.com/"):
        raise GitHubLookupError("only api.github.com", final=True)
    current = now() if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    entry = _gh_cache_read(cache_path).get(url) if cache_path else None
    age_s = None
    if entry is not None:
        fetched_dt = _parse_iso_utc(entry["fetchedAt"])
        if fetched_dt is not None:
            age_s = (current - fetched_dt).total_seconds()
            if 0 <= age_s < ttl_seconds:
                return entry["body"]

    req_headers = {"Accept": "application/vnd.github+json", "User-Agent": "jorah-toolbox/1",
                   "X-GitHub-Api-Version": "2022-11-28"}
    if entry is not None and entry.get("etag"):
        req_headers["If-None-Match"] = entry["etag"]
    request = urllib.request.Request(url, headers=req_headers)
    try:
        with opener.open(request, timeout=GITHUB_TIMEOUT) as response:
            data = response.read(GITHUB_MAX_BYTES + 1)
            resp_etag = response.headers.get("ETag") if response.headers else None
    except urllib.error.HTTPError as error:
        err_headers = error.headers or {}
        if error.code == 304 and entry is not None:
            new_etag = err_headers.get("ETag") or entry.get("etag")
            if cache_path:
                try:
                    _gh_cache_set(cache_path, url, new_etag, entry["body"], current.isoformat())
                except OSError:
                    pass
            return entry["body"]
        if error.code == 404:
            raise GitHubLookupError("GitHub has no published release for this URL (drafts aren't visible): check the owner, repo and tag",
                                    final=True) from None
        if error.code in (403, 429) and (err_headers.get("x-ratelimit-remaining") == "0" or err_headers.get("retry-after")):
            if entry is not None and age_s is not None and 0 <= age_s < max_stale_seconds:
                return entry["body"]
            reset = err_headers.get("x-ratelimit-reset")
            until = (datetime.fromtimestamp(int(reset), timezone.utc).strftime("%H:%M UTC") if reset and reset.isdigit()
                     else f"in {err_headers.get('retry-after') or 60} seconds")
            raise GitHubLookupError(f"GitHub's API limit for this machine (60 lookups an hour, no sign-in) is used up until {until}") from None
        raise GitHubLookupError(f"GitHub's API answered {error.code}") from None
    except GitHubLookupError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise GitHubLookupError(f"GitHub's API didn't answer: {type(error).__name__}") from None
    if len(data) > GITHUB_MAX_BYTES:
        raise GitHubLookupError("GitHub's answer is over 4 MB")
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise GitHubLookupError("GitHub's answer isn't JSON") from None
    if cache_path:
        try:
            _gh_cache_set(cache_path, url, resp_etag, parsed, current.isoformat())
        except OSError:
            pass
    return parsed


# ---- Ubuntu packages: Launchpad's publishing record and the package's own copyright file ------

LAUNCHPAD = "https://api.launchpad.net/1.0"
UBUNTU_CHANGELOGS = "https://changelogs.ubuntu.com/changelogs/pool"
UBUNTU_FILLS = ("version", "released", "release_page", "homepage", "licence", "licence_source")
UBUNTU_ALLOWED_HOSTS = ("api.launchpad.net", "changelogs.ubuntu.com")
SERIES = re.compile(r"^[a-z]{3,20}$")
COMPONENT = re.compile(r"^(main|restricted|universe|multiverse)$")
DEB_VERSION = re.compile(r"^(?:\d+:)?[A-Za-z0-9][A-Za-z0-9.+~-]{0,79}$")
SOURCE = re.compile(r"^[a-z0-9][a-z0-9+.-]{1,62}$")
MAX_LICENCE = 60


class UbuntuLookupError(Exception):
    pass


class _UbuntuHttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname not in UBUNTU_ALLOWED_HOSTS:
            raise UbuntuLookupError("Ubuntu lookup redirected to an unexpected host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_UBUNTU_OPENER = urllib.request.build_opener(_UbuntuHttpsOnly, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def is_series(value):
    return isinstance(value, str) and bool(SERIES.match(value))


def no_epoch(version):
    return re.sub(r"^\d+:", "", str(version))


def launchpad_binaries(series, pkg):
    arch = f"{LAUNCHPAD}/ubuntu/{series}/amd64"
    return (
        f"{LAUNCHPAD}/ubuntu/+archive/primary?ws.op=getPublishedBinaries"
        f"&binary_name={quote(pkg, safe='')}&exact_match=true"
        f"&distro_arch_series={quote(arch, safe='')}&status=Published"
    )


def newest_binary(answer, pkg):
    """The newest published version of one binary package from Launchpad's answer, or None."""
    raw_entries = answer.get("entries") if isinstance(answer, dict) and isinstance(answer.get("entries"), list) else []
    entries = []
    for e in raw_entries:
        if not isinstance(e, dict):
            continue
        if (e.get("binary_package_name") == pkg and e.get("status") == "Published"
                and isinstance(e.get("binary_package_version"), str) and DEB_VERSION.match(e["binary_package_version"])
                and isinstance(e.get("source_package_name"), str) and SOURCE.match(e["source_package_name"])
                and isinstance(e.get("source_package_version"), str) and DEB_VERSION.match(e["source_package_version"])
                and isinstance(e.get("component_name"), str) and COMPONENT.match(e["component_name"])):
            dt = _parse_iso_utc(e.get("date_published"))
            if dt is not None:
                entries.append((dt, e))
    if not entries:
        return None
    entries.sort(key=lambda item: item[0], reverse=True)
    dt, e = entries[0]
    pocket = e.get("pocket")
    return {
        "name": pkg,
        "version": e["binary_package_version"],
        "published": dt.isoformat().replace("+00:00", "Z"),
        "pocket": "" if pocket is None else str(pocket),
        "component": e["component_name"],
        "source": e["source_package_name"],
        "sourceVersion": e["source_package_version"],
    }


def copyright_url(b):
    prefix = b["source"][:4] if b["source"].startswith("lib") else b["source"][0]
    return f"{UBUNTU_CHANGELOGS}/{b['component']}/{prefix}/{b['source']}/{b['source']}_{no_epoch(b['sourceVersion'])}/copyright"


def _has_control(text):
    return any((ord(c) < 32 and c not in "\n\t") or c == "\x7f" for c in text)


def dep5_licence(text):
    """The licence of a machine-readable (DEP-5) copyright file's 'Files: *' paragraph, or None."""
    if not isinstance(text, str) or not re.search(r"^Format:\s*https?://\S*copyright-format", text, re.MULTILINE):
        return None
    for para in re.split(r"\n\s*\n", text.replace("\r", "")):
        if not re.search(r"^Files:\s*\*\s*$", para, re.MULTILINE):
            continue
        match = re.search(r"^License:[ \t]*(\S[^\n]*)$", para, re.MULTILINE)
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        if _has_control(value):
            return None
        return f"{value[:MAX_LICENCE - 1]}…" if len(value) > MAX_LICENCE else value
    return None


def _ubuntu_fetch(url, max_bytes, opener=None):
    opener = opener or _UBUNTU_OPENER
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in UBUNTU_ALLOWED_HOSTS:
        raise UbuntuLookupError("unexpected Ubuntu lookup host")
    request = urllib.request.Request(url, headers={"User-Agent": "jorah-toolbox/1", "Accept": "application/json, text/plain"})
    try:
        with opener.open(request, timeout=GITHUB_TIMEOUT) as response:
            cl = response.headers.get("Content-Length") if response.headers else None
            if cl and cl.isdigit() and int(cl) > max_bytes:
                return 200, None
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        return error.code, None
    if len(data) > max_bytes:
        return 200, None
    if parts.hostname == "api.launchpad.net":
        return 200, data.decode("utf-8")
    return 200, data.decode("utf-8", errors="replace")


def ubuntu_record(series, packages, fetch=None):
    """Ubuntu's record for an apt request: {'ok': True, 'found': ..., 'copyright': ...} or {'ok': False, 'reason': ...}.
    One Launchpad lookup per package (at most 8), then the first package's copyright file."""
    if not is_series(series):
        return {"ok": False, "reason": f"invalid Ubuntu series {str(series)[:20]}"}
    fetch_fn = fetch or _ubuntu_fetch
    found = []
    for pkg in list(packages)[:8]:
        try:
            status, text = fetch_fn(launchpad_binaries(series, pkg), GITHUB_MAX_BYTES)
        except Exception as error:  # noqa: BLE001 - network/fetch errors become clear unknown reason
            return {"ok": False, "reason": f"Launchpad (Ubuntu's archive) didn't answer ({type(error).__name__}); try again in a few minutes"}
        if status != 200:
            return {"ok": False, "reason": f"Launchpad answered {status} for {pkg}; try again later"}
        if text is None:
            return {"ok": False, "reason": f"Launchpad's answer for {pkg} is over 4 MB; try again later"}
        try:
            answer = json.loads(text)
        except (ValueError, TypeError):
            return {"ok": False, "reason": f"Launchpad's answer for {pkg} isn't JSON"}
        found.append(newest_binary(answer, pkg))
    copyright_info = None
    if found and found[0]:
        url = copyright_url(found[0])
        try:
            status, text = fetch_fn(url, 1 << 20)
            copyright_info = {"url": url, "text": text if status == 200 else None}
        except Exception:  # noqa: BLE001 - missing/unreadable copyright file isn't fatal
            copyright_info = {"url": url, "text": None}
    return {"ok": True, "found": found, "copyright": copyright_info}


def apply_ubuntu(m, series, found, copyright_info):
    """Fill in and check an apt request from Ubuntu's record: (manifest, record, problems)."""
    problems = []
    out = dict(m)
    record = {
        "series": series,
        "packages": [],
        "copyright": copyright_info.get("url") if isinstance(copyright_info, dict) else None,
        "filled": [],
    }
    packages = m.get("packages") or []
    for i, pkg in enumerate(packages):
        b = found[i] if i < len(found) else None
        if not b:
            problems.append(
                f"packages: Ubuntu {series} publishes no package named {str(pkg)[:63]} for amd64 "
                "(check the binary package's exact name)"
            )
        else:
            record["packages"].append({"name": b["name"], "version": b["version"], "pocket": b["pocket"], "published": b["published"]})
    if problems:
        return out, record, problems
    main = found[0]
    version = no_epoch(main["version"])
    if "version" not in m:
        out["version"] = version[:30]
        record["filled"].append("version")
    elif m["version"] != version and m["version"] != main["version"]:
        problems.append(
            f"version: Ubuntu {series} publishes {main['name']} {main['version']}, which apt installs; "
            "leave version out and it is filled in"
        )
    day = max(b["published"][:10] for b in found)
    if "released" not in m:
        out["released"] = day
        record["filled"].append("released")
    elif m["released"] != day:
        problems.append(
            f"released: Ubuntu published the newest of these packages on {day}, not {m['released']}; "
            "leave released out and it is filled in"
        )
    page = f"https://launchpad.net/ubuntu/+source/{main['source']}/{quote(main['sourceVersion'], safe='')}"
    for k in ("release_page", "homepage"):
        if k not in m:
            out[k] = page
            record["filled"].append(k)
    licence = dep5_licence(copyright_info.get("text") if isinstance(copyright_info, dict) else None)
    out["licence"] = licence or "see Ubuntu's copyright file"
    out["licence_source"] = (copyright_info.get("url") if isinstance(copyright_info, dict) and copyright_info.get("url")
                             else copyright_url(main))
    record["filled"].extend(["licence", "licence_source"])
    record["licenceFrom"] = "the package's copyright file" if licence else "not machine-readable; see the copyright file"
    return out, record, problems


def _check_apt_request(tc, manifest, today):
    stand_in = {
        "version": "0",
        "released": "2000-01-01",
        "release_page": "https://launchpad.net/",
        "homepage": "https://launchpad.net/",
        "licence": "stand-in",
        "licence_source": "stand-in",
    }
    probe = dict(manifest)
    for k in UBUNTU_FILLS:
        if k not in probe:
            probe[k] = stand_in[k]
    return tc.check(probe, today)


# ---- requests from runs ----------------------------------------------------------------------------

def collect_requests(settings, source, today, get=github_get, ubuntu_fetch=None):
    """Turn run-written requests into proposals. `source`: {"project", "run"}. `get`: GitHub's API,
    for release assets. Returns {"proposed": [{"id", "name", "version"}], "refused": [{"file", "why"}],
    "waiting": [{"file", "why"}]}; a waiting request stays in requests/ for the next run's turn."""
    out = {"proposed": [], "refused": [], "waiting": []}
    folder = work_dir(settings) / "requests"
    if not _plain_tree(folder):
        return out
    entries = sorted(p for p in folder.iterdir() if p.suffix == ".json")
    if not entries:
        return out
    tc = load_contract(settings)
    proposals = Path(settings.toolbox_var) / "proposals"
    if tc is None or not proposals.is_dir():
        out["refused"].append({"file": "*", "why": "the toolbox isn't installed, so requests wait"})
        return out
    raw_series = getattr(settings, "ubuntu_series", "noble")
    series = raw_series if is_series(raw_series) else "noble"
    cache_path = Path(settings.state_root) / GITHUB_CACHE_FILE
    for path in entries[:10]:
        name = path.name[:60]
        why = wait = github = ubuntu = None
        try:
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("isn't a plain file")
            manifest = tc.load_file(path)
            if isinstance(manifest, dict) and manifest.get("kind") == "apt":
                problems = _check_apt_request(tc, manifest, today)
            else:
                problems = tc.check_request(manifest, today)
            if problems:
                raise ValueError("; ".join(problems[:5]))
            where = tc.github_asset(manifest.get("url")) if manifest.get("kind") == "archive" else None
            if where:
                try:
                    url = tc.GITHUB_API + where["path"]
                    release = get(url, cache_path=cache_path) if get is github_get else get(url)
                except GitHubLookupError as error:
                    if error.final:
                        raise ValueError(f"url: {error}") from None
                    wait = str(error)
                else:
                    manifest, github, problems = tc.apply_github(manifest, release)
                    if problems:
                        raise ValueError("; ".join(problems[:5]))
                    github = {**github, "checkedAt": _now()}
            if not wait and manifest.get("kind") == "apt":
                got = ubuntu_record(series, manifest.get("packages") or [], fetch=ubuntu_fetch)
                if not got["ok"]:
                    raise ValueError(got["reason"])
                manifest, ubuntu, problems = apply_ubuntu(manifest, series, got["found"], got["copyright"])
                if problems:
                    raise ValueError("; ".join(problems[:5]))
                ubuntu = {**ubuntu, "checkedAt": _now()}
            if not wait:
                # The unpacked size is a limit set from the download size, never the run's estimate.
                manifest, filled = tc.fill_sizes(manifest)
                if github:
                    github["filled"] = github["filled"] + filled
                problems = tc.check(manifest, today)
                if problems:
                    raise ValueError("; ".join(problems[:5]))
        except (OSError, ValueError) as error:
            why = str(error)[:600]
        if wait and not why:
            out["waiting"].append({"file": name, "why": wait[:200]})
            continue
        if why:
            bad = real_dir(folder / "bad")
            if os.path.isdir(bad / name) and not os.path.islink(bad / name):
                shutil.rmtree(bad / name)
            if os.path.islink(path):
                os.unlink(path)
            else:
                os.replace(path, bad / name)  # replaces a link at the target, never follows it
            fresh_file(bad / f"{name}.why.txt", why + "\n")
            out["refused"].append({"file": name, "why": why[:200]})
            continue
        pid = tc.proposal_id(manifest)
        record = {"v": 1, "id": pid, "at": _now(), "from": {"via": "run", **source}, "manifest": manifest,
                  "digest": tc.digest(manifest), "card": tc.card_fields(manifest, pid)}
        if github:
            record["github"] = github
        if ubuntu:
            record["ubuntu"] = ubuntu
        target = proposals / f"{pid}.json"
        if not target.exists():
            tmp = proposals / f".{pid}.tmp"
            tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.chmod(tmp, 0o644)
            os.replace(tmp, target)
        done = real_dir(folder / "done")
        if os.path.isdir(done / name) and not os.path.islink(done / name):
            shutil.rmtree(done / name)
        os.replace(path, done / name)
        out["proposed"].append({"id": pid, "name": manifest["name"], "version": manifest["version"]})
    return out


# ---- the smoke test ---------------------------------------------------------------------------------

def smoke(settings, tool, *, run=subprocess.run, scratch_root=None):
    """Run the tool's smoke command offline in bubblewrap. Returns the tested record. Its home folder
    and its state folder are fresh, empty folders in the runner's own state (`scratch_root`), which
    runs can't reach, mounted where the tool expects them."""
    name = tool["name"]
    record = {"v": 1, "name": name, "id": tool.get("id"), "version": tool.get("version"), "at": _now(), "ok": False,
              "exit": None, "seconds": None, "expectFound": None, "output": "", "via": "bwrap", "error": None, "learn": None}
    argv = tool.get("smoke")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        record["error"] = "the tool has no smoke command"
        return record
    bwrap = settings.bwrap_bin
    if not Path(bwrap).is_file():
        record["error"] = f"bubblewrap isn't at {bwrap}"
        return record
    home = Path(settings.sandbox_dir).parent
    state = Path(settings.toolbox_state) / name
    root = Path(scratch_root or (Path(settings.state_root) / "_toolbox" / "smoke")) / name
    shutil.rmtree(root, ignore_errors=True)
    scratch, scratch_state = root / "home", root / "state"
    for p in (scratch, scratch_state):
        p.mkdir(parents=True, mode=0o700)
    cmd = [bwrap, "--die-with-parent", "--new-session", "--unshare-all",
           "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run",
           "--tmpfs", str(home.parent), "--bind", str(scratch), str(home), "--bind", str(scratch_state), str(state),
           "--chdir", str(home), "--clearenv",
           "--setenv", "HOME", str(home), "--setenv", "LANG", "C.UTF-8", "--setenv", "TMPDIR", "/tmp",
           "--setenv", "PATH", f"{Path(settings.toolbox_dir) / 'bin'}:/usr/local/bin:/usr/bin:/bin", "--", *argv]
    started = datetime.now(timezone.utc)
    try:
        done = run(cmd, capture_output=True, timeout=settings.smoke_seconds, check=False, stdin=subprocess.DEVNULL)
        record["exit"] = done.returncode
        text = (done.stdout or b"").decode("utf-8", "replace") + (done.stderr or b"").decode("utf-8", "replace")
    except subprocess.TimeoutExpired as error:
        record["error"] = f"timed out after {settings.smoke_seconds} s"
        text = ((error.stdout or b"") + (error.stderr or b"")).decode("utf-8", "replace") if isinstance(error.stdout, bytes) else ""
    except OSError as error:
        record["error"] = f"didn't start: {str(error)[:160]}"
        text = ""
    record["seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    record["output"] = text[-MAX_OUTPUT:]
    expect = tool.get("smokeExpect")
    if expect:
        record["expectFound"] = expect in text
    record["ok"] = record["error"] is None and record["exit"] == 0 and record["expectFound"] is not False
    shutil.rmtree(root, ignore_errors=True)
    return record


def due_smoke(settings):
    """Installed tools whose current install hasn't been smoke-tested yet."""
    out = []
    for name, tool in sorted(installed(settings).items()):
        done = tested(settings, name)
        if not done or done.get("id") != tool.get("id"):
            out.append(tool)
    return out


def due_learning(settings):
    """Installed tools that passed their smoke test and haven't had a learning run for this install."""
    out = []
    for name, tool in sorted(installed(settings).items()):
        done = tested(settings, name)
        if done and done.get("id") == tool.get("id") and done.get("ok") and not done.get("learn"):
            out.append((tool, done))
    return out


# ---- what runs are told -----------------------------------------------------------------------------

SYSTEM_TOOLS = (("kicad-cli", "/usr/bin/kicad-cli", "KiCad 10: ERC, DRC, Gerbers, drill, BOM, netlists, PDF/SVG, board STEP"),)


def brief_text(settings):
    """The toolbox paragraph of a project run's brief."""
    notes = work_dir(settings) / "notes"
    lines = []
    tools = installed(settings) if available(settings) else {}
    for name, tool in sorted(tools.items()):
        done = tested(settings, name) or {}
        state = ("passed its offline smoke test" if done.get("ok") and done.get("id") == tool.get("id")
                 else "smoke test failed or not run yet" if done else "smoke test not run yet")
        cmds = ", ".join(tool.get("commands") or []) or "on the system PATH"
        has_notes = (notes / f"{name}.md").is_file()
        lines.append(f"  - {name} {tool.get('version')} ({cmds}; {state}; notes: "
                     f"{'~/work/.toolbox/notes/' + name + '.md' if has_notes else 'none yet: write them when you first use it'})")
    for cmd, path, what in SYSTEM_TOOLS:
        if Path(path).is_file():
            has_notes = (notes / f"{cmd}.md").is_file()
            lines.append(f"  - {cmd}, {what} (system; notes: {'~/work/.toolbox/notes/' + cmd + '.md' if has_notes else 'none yet'})")
    have = "\n".join(lines) if lines else "  - none yet"
    return (
        "Tools beyond the project's own packages (read a tool's notes before you use it, and add what you learn: "
        "exact commands that worked, settings, pitfalls; commit in ~/work/.toolbox):\n" + have + "\n"
        "  To ask for a new tool, write ~/work/.toolbox/requests/<name>.json following "
        "/opt/jorah/docs/contracts/jorah-tool-v1.md; for a GitHub release asset give the version and its download URL and leave "
        "sha256, released and download_mb out: the runner reads them from GitHub's API. Never estimate installed_mb: leave it out and a "
        "limit is set from the download size. The runner proposes it and Adam approves it on a card. "
        "A request refused by the checks is in requests/bad/ with the reason. Packages from npm or PyPI need no request: "
        "install them into the project (uv, or pip 26.1 or newer, or npm), which take only releases at least 7 days old."
    )


def learn_brief(settings, template_path, tool, done, *, today, minutes, max_turns):
    from string import Template

    template = Template(Path(template_path).read_text(encoding="utf-8"))
    commands = ", ".join(tool.get("commands") or []) or "installed from Ubuntu's archive, on the system PATH"
    return template.substitute(
        name=tool["name"], title=_line(tool.get("title")), version=_line(tool.get("version")), commands=commands,
        tool_dir=tool.get("path") or "the system (Ubuntu packages: " + ", ".join(tool.get("packages") or []) + ")",
        licence=_line(tool.get("licence")), homepage=_line(tool.get("homepage")), purpose=str(tool.get("purpose") or "")[:600],
        for_project=tool.get("forProject") or "none named", smoke=" ".join(tool.get("smoke") or []),
        smoke_exit=done.get("exit"), smoke_seconds=done.get("seconds"), today=today, minutes=minutes, max_turns=max_turns,
    )


def _line(value):
    return re.sub(r"[\r\n]+", " ", str(value or ""))[:300]


def pseudo_project(settings, config):
    """The learning run's Project: ~/work/.toolbox, web on, the robotics bench if it's installed."""
    bench = "robotics" if Path(settings.bench_env.get("robotics", "")).is_file() else None
    return config.Project(name="toolbox", repo=None, work_dir=work_dir(settings), branch="main", state_dir="notes", level=0,
                          schedule=[], limits=dict(settings.learn_limits), web=True, bench=bench, paused=False)


def note_learned(settings, name, run_record):
    done = tested(settings, name)
    if not done:
        return
    done["learn"] = {"run": run_record["id"], "at": run_record["endedAt"], "outcome": run_record["outcome"],
                     "notes": (work_dir(settings) / "notes" / f"{name}.md").is_file()}
    write_tested(settings, name, done)


def private_json(path, data):
    fsio.write_private_json(path, data)
