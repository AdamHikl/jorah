#!/usr/bin/env bash
# Commits a snapshot of what Jorah has learned to a local-only git repo, so you
# can see how it changed over time and roll back. The repo has no remote and is
# never pushed: it holds personal memory.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATE="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-jorah}"
BRAIN="${JORAH_BRAIN_DIR:-$HOME/.jorah-brain}"

if [ ! -d "$BRAIN/.git" ]; then
  mkdir -p "$BRAIN"
  chmod 700 "$BRAIN"
  git -C "$BRAIN" init -q -b main
fi

copy() { # copy <source> <name>: mirrors a file or folder if it exists, drops it if it's gone
  if [ -e "$1" ]; then
    rsync -a --delete --exclude '.dreams/' --exclude '.git/' "$1" "$BRAIN/$2"
  else
    rm -rf "${BRAIN:?}/$2"
  fi
}

copy "$REPO/workspace/USER.md" USER.md
copy "$REPO/workspace/MEMORY.md" MEMORY.md
copy "$REPO/workspace/DREAMS.md" DREAMS.md
copy "$REPO/workspace/memory/" memory/
copy "$STATE/wiki/main/" wiki/
copy "$STATE/agents/main/agent/workshop-skills/" learned-skills/

git -C "$BRAIN" add -A
if git -C "$BRAIN" diff --cached --quiet; then
  echo "No changes since the last snapshot."
else
  git -C "$BRAIN" commit -q -m "Snapshot $(date '+%Y-%m-%d %H:%M')"
  git -C "$BRAIN" log --oneline -1
fi
