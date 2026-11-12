"""Builds the runner allowlist to install (issue 10, step A9): the committed entries in
services/ios-runner/ios-projects.json, the one source, plus the iPhone under `devices`.
The UDID never goes into the repo; it is added here, at install time.

  python3 -I ios_allowlist.py <source json> <udid>   -> merged JSON on stdout
"""

from __future__ import annotations

import json
import re
import sys

ALIAS = "adam-iphone"  # the alias the test pass (docs/runbooks/ios-test-pass.md, G3) uses
UDID_RE = re.compile(r"^[A-Fa-f0-9-]{8,64}$")  # as services/ios-runner/ios_runner/config.py


def merge(text: str, udid: str, alias: str = ALIAS) -> str:
    if not UDID_RE.match(udid or ""):
        raise ValueError("not a UDID: use the Identifier column of `xcrun devicectl list devices`")
    data = json.loads(text)
    if not isinstance(data, dict) or "projects" not in data:
        raise ValueError("source is not a runner allowlist")
    data["devices"] = {alias: {"udid": udid}}
    return json.dumps(data, indent=2) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.stderr.write(__doc__ or "")
        return 2
    try:
        with open(argv[0], encoding="utf-8") as f:
            sys.stdout.write(merge(f.read(), argv[1]))
    except (OSError, ValueError) as e:
        sys.stderr.write("Stopped: %s\n" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
