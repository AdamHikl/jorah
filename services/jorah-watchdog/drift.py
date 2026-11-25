#!/usr/bin/env python3
"""Nightly drift check: are the reviewed files on the PC still the ones last deployed from main?

Why (docs/plan/research/openclaw-security-landscape.md, recommendation 10): Jorah's rules files and
the reviewed code in /opt/jorah can be changed by paths the guard doesn't see, such as Dreaming, a
Claude Code job or a mistake by hand. A hash baseline catches that the next night.

The manifest (/var/lib/jorah-drift/manifest.json, root-owned) maps each deployed file to the SHA-256
of its content in git and the commit it came from. Only `record` writes it, and only after checking
that each file on disk has exactly the hash git gives (scripts/pc/deploy_reviewed.py computes the
hashes on the Mac from the commit, so the manifest never just trusts what is on the PC).

  check    (root, no network; jorah-drift.service) Hash every file in the manifest, list files in
           /opt/jorah that aren't in it, write the report for the watchdog to send. The report also
           lists the versions of OpenClaw's npm-installed plugins for the advisory watch.
  record   (root) Read {"commit": ..., "files": {path: {"sha256": ..., "source": ...}}} on stdin,
           check each file on disk matches, then merge the entries into the manifest.
  forget   (root) Remove the named paths from the manifest (a file deleted from main).
  hashes   (root) Print {path: sha256} for the named files, or every file under named folders, for
           the baseline in deploy_reviewed.py. Secret names print as "refused", never hashed.
  show     Print the report.

Never reads files that hold secrets: it hashes only manifest paths, which come from git (secrets are
never committed), and refuses the name patterns in SECRET_NAMES even then. In the live workspaces
only AGENTS.md, SOUL.md, IDENTITY.md and DEEP.md may be recorded: never USER.md, MEMORY.md or memory/. Files not in the manifest
are listed by name and never opened.
"""

import argparse
import fnmatch
import glob
import hashlib
import json
import os
import sys
import time
from pathlib import Path

MANIFEST = "/var/lib/jorah-drift/manifest.json"
REPORT = "/var/lib/jorah-drift/report.json"
TREE = "/opt/jorah"
# Live files that may be recorded besides /opt/jorah: the agents' reviewed rules files.
LIVE_ALLOWED = ("/home/jorah/workspace/", "/home/jorah/workspace-deep/", "/home/jorah/workspace-background/")
# DEEP.md since 2026-11-25: deep's rules, in main's workspace.
LIVE_NAMES = ("AGENTS.md", "SOUL.md", "IDENTITY.md", "DEEP.md")
SECRET_NAMES = ("openclaw.json", "*.token", "*.key", "*.pem", ".env", ".env.*", "*credentials*",
                "id_rsa*", "id_ed25519*")
MAX_LISTED = 20
# OpenClaw's npm-installed plugins for live Jorah (acpx, duckduckgo), in jorah's private home where
# the watchdog's user can't look. Only name and version are read from each package.json, for the
# advisory watch.
PACKAGE_GLOB = "/home/jorah/.openclaw-jorah/npm/projects/*/node_modules/@openclaw/*/package.json"


def log(line):
    print(line, flush=True)


def secret_name(path):
    name = os.path.basename(path)
    return any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_NAMES)


def allowed_path(path, tree=TREE, live_allowed=LIVE_ALLOWED):
    """A path the manifest may hold: under the tree, or one of the agents' rules files."""
    path = os.path.normpath(path)
    if not os.path.isabs(path) or secret_name(path):
        return False
    if path.startswith(tree.rstrip("/") + "/"):
        return True
    return any(path.startswith(prefix) for prefix in live_allowed) and os.path.basename(path) in LIVE_NAMES \
        and os.path.dirname(path) + "/" in live_allowed


def sha256_file(path):
    """The file's SHA-256, or None when it's missing, not a regular file or a symlink."""
    try:
        if os.path.islink(path) or not os.path.isfile(path):
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def tree_files(tree):
    """Every regular file under the tree, by path only. Nothing is opened."""
    out = []
    for root, dirs, files in os.walk(tree):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for name in files:
            if name.endswith(".pyc"):
                continue
            out.append(os.path.join(root, name))
    return out


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data, mode=0o644):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    os.chmod(tmp, mode)
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    tmp.replace(path)


def packages(pattern=PACKAGE_GLOB):
    """{"@openclaw/<name>": [versions]} of the plugin packages OpenClaw installed from npm."""
    found = {}
    for path in glob.glob(pattern):
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        name, version = data.get("name"), data.get("version")
        if isinstance(name, str) and name.startswith("@openclaw/") and isinstance(version, str):
            found.setdefault(name, set()).add(version)
    return {name: sorted(versions) for name, versions in sorted(found.items())}


def check(manifest_path, tree=TREE, now=None):
    """The report: what changed, went missing or appeared outside a deploy. Never raises."""
    now = time.time() if now is None else now
    try:
        manifest = json.loads(Path(manifest_path).read_text())
        files = manifest["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("no files")
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"checked_at": now, "ok": False, "error": f"no usable manifest ({type(error).__name__})"}
    changed, missing, refused = [], [], []
    for path, entry in sorted(files.items()):
        if secret_name(path):
            refused.append(path)
            continue
        actual = sha256_file(path)
        if actual is None:
            missing.append(path)
        elif actual != entry.get("sha256"):
            changed.append({"path": path, "commit": entry.get("commit")})
    unrecorded = sorted(p for p in tree_files(tree) if p not in files)
    return {"checked_at": now, "ok": True, "files": len(files), "changed": changed, "missing": missing,
            "unrecorded": unrecorded, "refused": refused}


def record(manifest_path, payload, now=None, tree=TREE, live_allowed=LIVE_ALLOWED):
    """Merges verified entries. Returns (ok, lines). Writes nothing unless every file matches."""
    now = time.time() if now is None else now
    commit = str(payload.get("commit") or "")
    files = payload.get("files")
    if not commit or not isinstance(files, dict) or not files:
        return False, ["expected a commit and at least one file"]
    problems = []
    for path, entry in files.items():
        if not allowed_path(path, tree, live_allowed):
            problems.append(f"not a path the manifest may hold: {path}")
            continue
        actual = sha256_file(path)
        if actual != entry.get("sha256"):
            problems.append(f"differs from {commit[:12]}: {path}" if actual else f"missing: {path}")
    if problems:
        return False, problems
    manifest = load_json(manifest_path, {"files": {}})
    manifest.setdefault("files", {})
    for path, entry in files.items():
        manifest["files"][os.path.normpath(path)] = {"sha256": entry["sha256"], "commit": commit,
                                                     "source": entry.get("source"), "recorded_at": now}
    manifest["updated_at"] = now
    write_json(manifest_path, manifest)
    return True, [f"recorded {len(files)} file(s) from {commit[:12]}"]


def forget(manifest_path, paths, now=None):
    manifest = load_json(manifest_path, {"files": {}})
    gone = [p for p in paths if manifest.get("files", {}).pop(os.path.normpath(p), None) is not None]
    manifest["updated_at"] = time.time() if now is None else now
    write_json(manifest_path, manifest)
    return gone


def hashes(paths, tree=TREE, live_allowed=LIVE_ALLOWED):
    """{path: sha256, or "refused", or None when unreadable}. Only paths the manifest may hold are
    read: files under the tree and the agents' rules files, never a secret name, USER.md or memory."""
    out = {}
    for path in paths:
        targets = tree_files(path) if os.path.isdir(path) and not os.path.islink(path) else [path]
        for target in targets:
            ok = allowed_path(target, tree, live_allowed)
            out[target] = sha256_file(target) if ok else "refused"
    return out


def report_text(report):
    """What to tell Adam, or None when everything matches."""
    if not report.get("ok"):
        return None
    parts = []

    def listed(label, items):
        shown = items[:MAX_LISTED]
        more = f" and {len(items) - len(shown)} more" if len(items) > len(shown) else ""
        parts.append(f"{label}:\n" + "\n".join(f"- {item}" for item in shown) + more)

    if report["changed"]:
        listed("Changed since deployed", [f"{c['path']} (deployed from {str(c.get('commit'))[:7]})"
                                          for c in report["changed"]])
    if report["missing"]:
        listed("Missing", report["missing"])
    if report["unrecorded"]:
        listed("In /opt/jorah but never recorded by a deploy", report["unrecorded"])
    if not parts:
        return None
    return ("Jorah's drift check: reviewed files on the PC differ from what was last deployed from main.\n"
            + "\n".join(parts)
            + "\nIf a build session deployed without recording, it reruns scripts/pc/deploy_reviewed.py; "
              "otherwise find out who changed them.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="jorah-drift")
    parser.add_argument("command", choices=["check", "record", "forget", "hashes", "show"])
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--manifest", default=MANIFEST)
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--tree", default=TREE)
    args = parser.parse_args(argv)
    if args.command == "show":
        print(json.dumps(load_json(args.report, {}), indent=1))
        return 0
    if args.command == "check":
        report = check(args.manifest, args.tree)
        report["packages"] = packages()
        write_json(args.report, report)
        if report["ok"]:
            log(f"checked {report['files']} files: {len(report['changed'])} changed, {len(report['missing'])} "
                f"missing, {len(report['unrecorded'])} unrecorded")
        else:
            log(f"check failed: {report['error']}")
        return 0
    if args.command == "hashes":
        print(json.dumps(hashes(args.paths, args.tree), indent=0, sort_keys=True))
        return 0
    if args.command == "forget":
        log(f"forgot {len(forget(args.manifest, args.paths))} path(s)")
        return 0
    try:
        payload = json.loads(sys.stdin.read(16 * 1024 * 1024))
    except ValueError:
        log("stdin wasn't JSON")
        return 2
    ok, lines = record(args.manifest, payload, tree=args.tree)
    for line in lines:
        log(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
