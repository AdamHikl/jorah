#!/usr/bin/env bash
# Pre-push guard: refuses a push to main unless Adam set JORAH_ALLOW_MAIN=1.
# Stops mistakes, not `--no-verify` (docs/plan/09-engineering-and-ops.md 4.3).
# Git passes one "<local ref> <local sha> <remote ref> <remote sha>" line per ref.
set -euo pipefail

while read -r _local_ref _local_sha remote_ref _remote_sha; do
  if [ "$remote_ref" = "refs/heads/main" ] && [ "${JORAH_ALLOW_MAIN:-}" != "1" ]; then
    echo "REFUSED: push to main. Open a PR, or Adam sets JORAH_ALLOW_MAIN=1." >&2
    exit 1
  fi
done
