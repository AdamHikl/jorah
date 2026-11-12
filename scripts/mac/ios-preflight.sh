#!/bin/bash
# Read-only check of every Mac setup step for Jorah's iOS builds (issue 10).
# Safe to run any time, as adam or as jorah-build; no sudo, writes nothing, never reads a key.
#   scripts/mac/ios-preflight.sh
# Each line says done, missing, unknown or info, and the step in docs/runbooks/ios-builds.md
# ("Adam's steps") that fixes it. Some checks are only visible as jorah-build; as adam they
# show "unknown", never "done".
set -euo pipefail
exec /usr/bin/python3 -I "$(cd "$(dirname "$0")" && pwd)/ios_preflight.py" "$@"
