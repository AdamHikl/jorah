#!/usr/bin/env bash
# Pre-push guard: refuses a push to main without JORAH_ALLOW_MAIN=1, set by Claude Code build sessions (CLAUDE.md, 2026-11-07); Jorah never pushes main.
# Stops mistakes, not `--no-verify` (docs/plan/09-engineering-and-ops.md 4.3).
# Git passes one "<local ref> <local sha> <remote ref> <remote sha>" line per ref.
set -euo pipefail

while read -r _local_ref _local_sha remote_ref _remote_sha; do
  if [ "$remote_ref" = "refs/heads/main" ] && [ "${JORAH_ALLOW_MAIN:-}" != "1" ]; then
    echo "REFUSED: push to main. Set JORAH_ALLOW_MAIN=1 for a fast-forward from a build session." >&2
    exit 1
  fi
done
