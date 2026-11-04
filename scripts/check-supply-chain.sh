#!/usr/bin/env bash
# Enforces the repo's dependency defaults (docs/plan/09-engineering-and-ops.md 4.4).
set -euo pipefail

cd "$(dirname "$0")/.."

failed=0
require() {
  if ! grep -qE "^$2\$" "$1" 2>/dev/null; then
    echo "MISSING in $1: $2" >&2
    failed=1
  fi
}

require .npmrc 'min-release-age=7'
require .npmrc 'ignore-scripts=true'
require uv.toml 'exclude-newer = "7 days"'

# GitHub Actions must be pinned to a full commit SHA.
if [ -d .github/workflows ]; then
  unpinned="$(grep -rhE '^[[:space:]-]*uses:' .github/workflows | grep -vE '@[0-9a-f]{40}([[:space:]]|$)' || true)"
  if [ -n "$unpinned" ]; then
    echo "Actions not pinned to a full SHA:" >&2
    printf '%s\n' "$unpinned" >&2
    failed=1
  fi
fi

[ "$failed" -eq 0 ] && echo "supply-chain defaults in place"
exit "$failed"
