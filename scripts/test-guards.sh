#!/usr/bin/env bash
# Tests the commit and push guards with path lists and ref lines, no real commits.
set -euo pipefail

cd "$(dirname "$0")"

failed=0
refused() {
  if printf '%s\n' "$1" | ./guard-staged.sh --stdin >/dev/null 2>&1; then
    echo "NOT REFUSED: $1"
    failed=1
  fi
}
allowed() {
  if ! printf '%s\n' "$1" | ./guard-staged.sh --stdin >/dev/null 2>&1; then
    echo "WRONGLY REFUSED: $1"
    failed=1
  fi
}

for path in workspace/USER.md workspace/MEMORY.md workspace/DREAMS.md workspace/memory/2026-11-03.md \
  workspace-voice/USER.md docs/evidence/m0/answers.md docs/evidence/m0/mango-42.md state/x.sqlite \
  state/x.sqlite-wal fixtures/private/a.wav room.m4a; do
  refused "$path"
done
for path in workspace/AGENTS.md workspace/SOUL.md README.md fixtures/synthetic/tone.wav docs/evidence/m0/state.txt; do
  allowed "$path"
done

push() { printf 'refs/heads/x abc %s def\n' "$1" | ./guard-push.sh >/dev/null 2>&1; }
if push refs/heads/main; then
  echo "NOT REFUSED: push to main"
  failed=1
fi
if ! push refs/heads/feat/x; then
  echo "WRONGLY REFUSED: push to a branch"
  failed=1
fi
if ! printf 'refs/heads/x abc refs/heads/main def\n' | JORAH_ALLOW_MAIN=1 ./guard-push.sh >/dev/null 2>&1; then
  echo "WRONGLY REFUSED: push to main with JORAH_ALLOW_MAIN=1"
  failed=1
fi

[ "$failed" -eq 0 ] && echo "guards behave"
exit "$failed"
