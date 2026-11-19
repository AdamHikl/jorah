#!/usr/bin/python3 -I
"""Jorah's `security.installPolicy` command: block every skill or plugin install not on Adam's list.

OpenClaw runs this on every skill and plugin install or update, after staging the source and before
the install goes on (tools/skills-config.md, "Operator Install Policy", OpenClaw 2026.10.9): ClawHub,
uploaded, Git and local skills, skill dependency installers, and plugin install and update sources,
from the CLI, the Gateway and the agent's own install tool. It reads one JSON request on stdin and
must print one JSON decision. A block, a crash, bad JSON or a timeout all stop the install, and
neither `--force` nor acknowledging a warning gets past a block.

Rules:
- allow only a request matching an entry in the allowlist, /etc/jorah/install-allowlist.json,
  which must be a regular file owned by root and writable by nobody else;
- block everything else, and block everything when the allowlist is missing, unreadable, unsafe or
  malformed.

An entry names fields that must all equal the request's:
  {"targetType": "plugin", "targetName": "jorah-foo", "sourceKind": "local-path",
   "mode": "install", "requestedSpecifier": "...", "sourcePath": "...", "note": "why, and Adam's yes"}
`targetType` and `targetName` are required; the rest narrow it further. `note` is shown on allow.

Installed root-owned at /usr/local/lib/jorah/install-policy by scripts/pc/install-install-policy.sh.
Not covered by OpenClaw's policy at all: skills Jorah writes with `skill_workshop`, which are files
in `<state>/agents/<id>/agent/workshop-skills`, not installs.
"""

import json
import os
import stat
import sys

ALLOWLIST = "/etc/jorah/install-allowlist.json"
MATCH_FIELDS = ("targetType", "targetName", "sourceKind", "mode", "requestedSpecifier", "sourcePath")


def request_fields(request):
    source = request.get("source") if isinstance(request.get("source"), dict) else {}
    req = request.get("request") if isinstance(request.get("request"), dict) else {}
    return {"targetType": request.get("targetType"), "targetName": request.get("targetName"),
            "sourceKind": source.get("kind"), "mode": req.get("mode"),
            "requestedSpecifier": req.get("requestedSpecifier"), "sourcePath": request.get("sourcePath")}


def load_allowlist(path, check_owner=True):
    """The entries, or raises ValueError saying why the list can't be trusted."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return []
    except OSError as error:
        raise ValueError(f"can't read the allowlist ({type(error).__name__})") from None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("the allowlist isn't a regular file")
    if check_owner and (info.st_uid != 0 or info.st_mode & 0o022):
        raise ValueError("the allowlist isn't root-owned and writable only by root")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        raise ValueError("the allowlist isn't valid JSON") from None
    entries = data.get("allow") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError('the allowlist has no "allow" list')
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("targetType") or not entry.get("targetName"):
            raise ValueError("an allowlist entry lacks targetType or targetName")
        unknown = set(entry) - set(MATCH_FIELDS) - {"note"}
        if unknown:
            raise ValueError(f"an allowlist entry has unknown fields: {', '.join(sorted(unknown))}")
    return entries


def decide(request, allowlist_path=ALLOWLIST, check_owner=True):
    if not isinstance(request, dict) or request.get("protocolVersion") != 1:
        return block("unexpected request (protocolVersion isn't 1)")
    fields = request_fields(request)
    what = f"{fields['targetType']} {fields['targetName']!r} ({fields['sourceKind'] or 'unknown source'})"
    try:
        entries = load_allowlist(allowlist_path, check_owner)
    except ValueError as error:
        return block(f"Jorah's install policy blocks {what}: {error}.")
    for entry in entries:
        if all(entry[key] == fields[key] for key in MATCH_FIELDS if key in entry):
            note = entry.get("note")
            return {"protocolVersion": 1, "decision": "allow",
                    "reason": f"on Jorah's install allowlist{': ' + note if note else ''}"}
    return block(f"Jorah's install policy blocks {what}: not on {allowlist_path}. "
                 f"Adam adds an entry there to allow it.")


def block(reason):
    return {"protocolVersion": 1, "decision": "block", "reason": reason[:1000]}


def main():
    try:
        request = json.loads(sys.stdin.read(1024 * 1024))
    except ValueError:
        request = None
    sys.stdout.write(json.dumps(decide(request)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
