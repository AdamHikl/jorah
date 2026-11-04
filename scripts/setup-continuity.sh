#!/usr/bin/env bash
# Keeps Jorah's Telegram conversation alive across Claude process exits and
# stops heartbeats disturbing it. Safe to re-run: a heartbeat already set stays as
# it is unless --set-heartbeat is passed, so a pause can't be undone by accident.
#
# 1. OpenClaw 2026.10.9 looks for Claude transcripts in $HOME/.claude/projects
#    and ignores CLAUDE_CONFIG_DIR, while the real ones are in
#    $HOME/.claude-jorah/projects. Without this link, the next turn after the
#    Claude process exits logs reason=missing-transcript and starts with no
#    context. One symlink for the workspace's project folder fixes the lookup.
# 2. A new profile gets heartbeats hourly on a cheap model in their own session.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_HOME="$HOME/.claude-jorah"
HEARTBEAT='{"every":"1h","model":"anthropic/claude-haiku-5-5","isolatedSession":true}'

SET_HEARTBEAT=""
case "${1:-}" in
  "") ;;
  --set-heartbeat) SET_HEARTBEAT=1 ;;
  *)
    echo "Usage: $0 [--set-heartbeat]" >&2
    exit 2
    ;;
esac

oc() { openclaw --profile "${JORAH_PROFILE:-jorah}" "$@"; }

mkdir -p "$REPO/workspace"

# Same project key OpenClaw and Claude Code derive: canonical path, every
# non-alphanumeric character replaced by "-". Paths over 200 characters get a
# hash suffix that the two do not share, so refuse those instead of guessing.
KEY="$(node -e '
  const fs = require("fs");
  const dir = fs.realpathSync.native(process.argv[1]).normalize("NFC");
  process.stdout.write(dir.replace(/[^a-zA-Z0-9]/g, "-"));
' "$REPO/workspace")"
if [ "${#KEY}" -gt 200 ]; then
  echo "Workspace path is too long for a plain project key: $REPO/workspace" >&2
  exit 1
fi

TARGET="$CLAUDE_HOME/projects/$KEY"
LINK="$HOME/.claude/projects/$KEY"

if [ -L "$LINK" ]; then
  if [ "$(readlink "$LINK")" != "$TARGET" ]; then
    echo "$LINK points to $(readlink "$LINK"), expected $TARGET. Left unchanged." >&2
    exit 1
  fi
  echo "Transcript link already in place: $LINK"
elif [ -e "$LINK" ]; then
  echo "$LINK already exists and is not a symlink. Left unchanged; move its contents out and re-run." >&2
  exit 1
else
  mkdir -p "$TARGET" "$(dirname "$LINK")"
  chmod 700 "$CLAUDE_HOME"
  ln -s "$TARGET" "$LINK"
  echo "Linked $LINK -> $TARGET"
fi

CURRENT="$(oc config get agents.defaults.heartbeat 2>/dev/null || true)"
if node -e '
  const [current, wanted] = process.argv.slice(1);
  const canon = (v) => { const o = JSON.parse(v); return JSON.stringify(Object.keys(o).sort().map((k) => [k, o[k]])); };
  try { process.exit(canon(current) === canon(wanted) ? 0 : 1); } catch { process.exit(1); }
' "$CURRENT" "$HEARTBEAT"; then
  echo "Heartbeat settings already applied"
elif [ -n "$CURRENT" ] && [ -z "$SET_HEARTBEAT" ]; then
  echo "Heartbeat already set, left alone. Pass --set-heartbeat to replace it."
else
  oc config set agents.defaults.heartbeat "$HEARTBEAT" --strict-json
fi
