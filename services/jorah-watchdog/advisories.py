"""Daily check of OpenClaw's own security advisories against what runs on the PC.

Why: GHSA-pw3x-g8v8-fvj2 (2026-11-19) affected the live 2026.10.9 but wasn't in GitHub's global
advisory database, so `npm audit` stayed silent. OpenClaw's repository list
(https://api.github.com/repos/openclaw/openclaw/security-advisories) had it the same day.

How:
- Reads the repository's published advisories, most recently updated first, 100 a page, and stops at
  the first one it has already seen at that same update time. The first run reads all of them
  (about 723, 8 requests); later runs usually need one. Sorting by update rather than publication
  also catches an older advisory whose ranges were corrected. Unauthenticated limit: 60 an hour.
- Keeps every advisory's ranges for `openclaw` and `@openclaw/*`, and checks all of them against the
  installed versions each day, so an upgrade into an old advisory's range is caught too.
- Installed versions: `openclaw` from its package.json (what `openclaw --version` prints; the
  installer checks they agree), the `@openclaw/*` plugin packages bundled with it or installed next
  to it in /opt/node, and the npm-installed ones in Jorah's state folder, which the root drift check
  lists in its report (watchdog.py merges them; without a fresh list it's unknown).
- One message per advisory that affects what's running. A range it can't read counts as possibly
  affected and says so. A source it can't read is unknown, never "no advisories": after a day
  without a good read it says so once, and once more when it can read again.
"""

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/openclaw/openclaw/security-advisories"
PAGE = 100
MAX_PAGES = 30
UNKNOWN_AFTER = 26 * 3600
FLOOD = 5
OPENCLAW_ROOT = Path("/opt/node/lib/node_modules/openclaw")
NODE_MODULES = Path("/opt/node/lib/node_modules")


# --- versions and ranges ---------------------------------------------------------------------------

_VERSION = re.compile(r"^v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_CONSTRAINT = re.compile(r"^(>=|<=|>|<|=|==)?\s*(\S+)$")


def parse_version(text):
    """A comparable key for an npm-style version, or None when it isn't one.

    OpenClaw uses calendar versions (2026.10.33), sometimes with a pre-release (2026.11.1-beta.2).
    As in semver, a pre-release sorts before its release, and numeric parts compare as numbers.
    """
    match = _VERSION.match(str(text).strip())
    if not match:
        return None
    numbers = [int(n) for n in match.group(1).split(".")]
    numbers += [0] * (3 - len(numbers)) if len(numbers) < 3 else []
    pre = match.group(2)
    if pre is None:
        return (tuple(numbers), 1, ())
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (tuple(numbers), 0, parts)


def parse_range(text):
    """[(op, key)] for a range like '>= 2026.9.2, < 2026.10.33', or None when it can't be read."""
    if text is None or not str(text).strip():
        return None
    out = []
    for piece in str(text).split(","):
        match = _CONSTRAINT.match(piece.strip())
        if not match:
            return None
        key = parse_version(match.group(2))
        if key is None:
            return None
        out.append((match.group(1) or "=", key))
    return out


def in_range(version, range_text):
    """True or False, or None when either side can't be read (which the caller treats as unknown)."""
    key = parse_version(version)
    constraints = parse_range(range_text)
    if key is None or constraints is None:
        return None
    for op, bound in constraints:
        ok = {"<": key < bound, "<=": key <= bound, ">": key > bound, ">=": key >= bound,
              "=": key == bound, "==": key == bound}[op]
        if not ok:
            return False
    return True


# --- what is installed -----------------------------------------------------------------------------

def _package_version(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None, None
    return data.get("name"), data.get("version")


def installed_packages(openclaw_root=OPENCLAW_ROOT, node_modules=NODE_MODULES):
    """{package: version} for openclaw and the @openclaw/* packages beside or inside it.

    Raises OSError when openclaw itself can't be read: that is "unknown", not "nothing installed".
    """
    name, version = _package_version(Path(openclaw_root) / "package.json")
    if name != "openclaw" or not version:
        raise OSError(f"can't read openclaw's version from {openclaw_root}/package.json")
    found = {"openclaw": version}
    places = list((Path(openclaw_root) / "dist" / "extensions").glob("*/package.json"))
    places += list((Path(node_modules) / "@openclaw").glob("*/package.json"))
    for place in places:
        pname, pversion = _package_version(place)
        if pname and pname.startswith("@openclaw/") and pversion:
            found.setdefault(pname, pversion)
    return found


# --- the advisory list -----------------------------------------------------------------------------

def _relevant(name):
    return name == "openclaw" or str(name).startswith("@openclaw/")


def summarize(raw):
    """The few fields kept per advisory."""
    vulns = []
    for v in raw.get("vulnerabilities") or []:
        package = (v.get("package") or {}).get("name")
        if _relevant(package):
            vulns.append({"package": package, "range": v.get("vulnerable_version_range"),
                          "patched": v.get("patched_versions")})
    return {"id": raw.get("ghsa_id"), "severity": raw.get("severity"), "summary": raw.get("summary"),
            "url": raw.get("html_url"), "updated_at": raw.get("updated_at"),
            "published_at": raw.get("published_at"), "vulns": vulns}


def _next_link(header):
    for part in (header or "").split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match and match.group(1).startswith("https://api.github.com/"):
                return match.group(1)
    return None


def fetch(known, opener=urllib.request.urlopen, max_pages=MAX_PAGES):
    """Advisories updated since the last read, newest update first.

    `known` is {id: updated_at}. Stops at the first advisory already known at the same update time,
    or at the end of the list. Raises OSError (with a short reason) when the list can't be read
    completely, so a partial read is never taken as the whole truth.
    """
    url = f"{API}?state=published&sort=updated&direction=desc&per_page={PAGE}"
    out = []
    for _ in range(max_pages):
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jorah-advisory-watch"})
        try:
            with opener(request, timeout=30) as response:
                page = json.loads(response.read(8 * 1024 * 1024))
                link = response.headers.get("Link") if getattr(response, "headers", None) else None
        except urllib.error.HTTPError as error:
            raise OSError(f"GitHub answered {error.code}") from None
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise OSError(f"GitHub unreachable or unreadable ({type(error).__name__})") from None
        if not isinstance(page, list):
            raise OSError("GitHub's answer wasn't a list")
        for raw in page:
            if not isinstance(raw, dict) or not raw.get("ghsa_id"):
                raise OSError("an advisory without an id")
            if known.get(raw["ghsa_id"]) == raw.get("updated_at"):
                return out
            out.append(summarize(raw))
        url = _next_link(link)
        if not url or not page:
            return out
    raise OSError(f"more than {max_pages} pages; stopped")


# --- deciding what to say --------------------------------------------------------------------------

def affecting(advisory, installed):
    """[(package, version, range, verdict)] where verdict is True (affected) or None (can't tell).

    `installed` maps a package to a version or a list of versions (a plugin can sit on disk in more
    than one generation); each is checked."""
    hits = []
    for v in advisory.get("vulns", []):
        versions = installed.get(v["package"])
        for version in [versions] if isinstance(versions, str) else versions or []:
            verdict = in_range(version, v["range"])
            if verdict is not False:
                hits.append((v["package"], version, v["range"], verdict))
    return hits


def message(advisory, hits):
    patched = sorted({v["patched"] for v in advisory["vulns"] if v.get("patched")})
    running = ", ".join(sorted({f"{p} {ver}" for p, ver, _, _ in hits}))
    unsure = [r for _, _, r, verdict in hits if verdict is None]
    lines = [f"OpenClaw security advisory {advisory['id']} ({advisory.get('severity') or 'severity unknown'}) "
             f"affects what Jorah runs: {running}.",
             (advisory.get("summary") or "").strip(),
             f"Fixed in: {', '.join(patched) if patched else 'no fixed version listed'}.",
             advisory.get("url") or f"https://github.com/openclaw/openclaw/security/advisories/{advisory['id']}"]
    if unsure:
        lines.insert(1, f"(Couldn't read the range {unsure[0]!r}, so it may or may not apply. Check by hand.)")
    return "\n".join(line for line in lines if line)


def _versions(value):
    return value if isinstance(value, str) else "/".join(value or ["unknown"])


def step(state, now, read_list, read_installed):
    """One daily run. Returns [(kind, key, text)] to send; mark_sent records what went out."""
    due = []
    source = state.setdefault("source", {"last_ok": None, "problem": None, "since": None, "alerted": False})
    stored = state.setdefault("advisories", {})
    problem = None
    installed = None
    try:
        installed = read_installed()
    except OSError as error:
        problem = f"couldn't read the installed version ({error})"
    if problem is None:
        try:
            fresh = read_list({k: v.get("updated_at") for k, v in stored.items()})
        except OSError as error:
            problem = f"couldn't read OpenClaw's advisory list ({error})"
        else:
            for advisory in fresh:
                stored[advisory["id"]] = advisory
    if problem:
        if source["since"] is None:
            source["since"] = now
        source["problem"] = problem
        if not source["alerted"] and now - (source["last_ok"] or source["since"]) >= UNKNOWN_AFTER:
            last = source["last_ok"]
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last)) if last else "never"
            due.append(("unknown", None, f"Jorah's advisory watch: unknown. It {problem}; last good read: "
                                         f"{when}. So it can't say whether a new OpenClaw advisory affects Jorah."))
        return due
    if source["alerted"]:
        due.append(("readable", None, "Jorah's advisory watch can read OpenClaw's advisory list again."))
    source.update({"last_ok": now, "problem": None, "since": None})
    state["installed"] = installed
    notified = state.setdefault("notified", {})
    new = []
    for advisory in sorted(stored.values(), key=lambda a: a.get("published_at") or ""):
        if advisory["id"] in notified:
            continue
        hits = affecting(advisory, installed)
        if hits:
            new.append((advisory, hits))
    if len(new) > FLOOD:
        ids = ", ".join(a["id"] for a, _ in new)
        due.append(("many", [a["id"] for a, _ in new],
                    f"Jorah's advisory watch: {len(new)} OpenClaw advisories match what Jorah runs "
                    f"(openclaw {_versions(installed.get('openclaw'))}): {ids}. "
                    f"That many at once may mean a misread; check "
                    f"https://github.com/openclaw/openclaw/security/advisories"))
    else:
        for advisory, hits in new:
            due.append(("advisory", advisory["id"], message(advisory, hits)))
    return due


def mark_sent(state, kind, key, now):
    source = state.setdefault("source", {})
    if kind == "unknown":
        source["alerted"] = True
    elif kind == "readable":
        source["alerted"] = False
    elif kind == "advisory":
        state.setdefault("notified", {})[key] = now
    elif kind == "many":
        for ghsa in key:
            state.setdefault("notified", {})[ghsa] = now
