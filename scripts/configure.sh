#!/usr/bin/env bash
# Sets up Jorah's non-secret OpenClaw config on a NEW profile.
# Not safe to re-run: on an existing profile it refuses, because re-applying would
# undo later changes. --diff prints what would change as a `config patch --dry-run`
# and writes nothing, so a change can be previewed and applied on Adam's yes.
# Secrets (Anthropic API key, Telegram bot token) are added separately.
#
# JORAH_PROFILE picks the profile, for tests on a scratch profile.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PINNED_VERSION="2026.10.9"
PROFILE="${JORAH_PROFILE:-jorah}"
export JORAH_PROFILE="$PROFILE"

oc() { openclaw --profile "$PROFILE" "$@"; }

MODE="apply"
case "${1:-}" in
  "") ;;
  --diff) MODE="diff" ;;
  *)
    echo "Usage: $0 [--diff]" >&2
    exit 2
    ;;
esac

if ! command -v openclaw >/dev/null; then
  if [ "$MODE" = "diff" ]; then
    echo "openclaw is not installed, so there is nothing to compare." >&2
    exit 1
  fi
  # A private prefix is upgraded through its own procedure (09 section 5), never from here.
  NPM_PREFIX="$(npm config get prefix)"
  case "$NPM_PREFIX" in
    "$HOME"/*)
      echo "Refusing npm install -g: the prefix is private ($NPM_PREFIX)." >&2
      echo "Install or upgrade it by docs/plan/09-engineering-and-ops.md section 5." >&2
      exit 1
      ;;
  esac
  echo "Installing openclaw@${PINNED_VERSION}" >&2
  npm install -g "openclaw@${PINNED_VERSION}" --allow-scripts=openclaw
fi

CONFIG_FILE="$(oc config file)"
CONFIG_FILE="${CONFIG_FILE/#\~/$HOME}"

# Claude Code as the only ACP coding harness, loopback only, Jorah's own Claude Code
# config and login. The bridge skips user settings unless that variable is set.
PATCH="$(mktemp)"
trap 'rm -f "$PATCH"' EXIT
cat >"$PATCH" <<EOF
{
  acp: { enabled: true, backend: "acpx", defaultAgent: "claude", allowedAgents: ["claude"] },
  gateway: { bind: "loopback" },
  env: { vars: { CLAUDE_CONFIG_DIR: "$HOME/.claude-jorah", ACPX_CLAUDE_INCLUDE_USER_SETTINGS: "1" } },
  plugins: {
    entries: {
      acpx: {
        enabled: true,
        config: {
          probeAgent: "claude",
          cwd: "$REPO/sandbox",
          nonInteractivePermissions: "deny",
          timeoutSeconds: 1800,
        },
      },
    },
  },
}
EOF

if [ "$MODE" = "diff" ]; then
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "Profile $PROFILE has no config yet. Run $0 without --diff." >&2
    exit 1
  fi
  echo "== Base config, dry run. Nothing is written."
  oc config patch --file "$PATCH" --dry-run
  echo "== Memory config, dry run. Nothing is written."
  oc config patch --file "$REPO/config/memory.patch.json5" --dry-run
  exit 0
fi

if [ -f "$CONFIG_FILE" ]; then
  echo "Refusing: profile $PROFILE already exists ($CONFIG_FILE)." >&2
  echo "Re-applying would undo later changes. Run $0 --diff to preview." >&2
  exit 1
fi

mkdir -p "$REPO/sandbox"
oc setup --baseline --workspace "$REPO/workspace"

oc plugins list 2>/dev/null | grep -q "acpx" || oc plugins install @openclaw/acpx
mkdir -p "$HOME/.claude-jorah"
chmod 700 "$HOME/.claude-jorah"
oc config patch --file "$PATCH"

# What delegated Claude Code may do.
"$REPO/scripts/setup-permissions.sh"

# Memory stack (local embeddings, Active Memory, Memory Wiki)
oc plugins list 2>/dev/null | grep -q "llama-cpp" || oc plugins install @openclaw/llama-cpp-provider
oc config patch --file "$REPO/config/memory.patch.json5"

"$REPO/scripts/setup-learning.sh"
"$REPO/scripts/setup-continuity.sh"

oc config validate
echo "Done. Next, log Jorah's Claude Code in and route the brain through it:" >&2
echo "  CLAUDE_CONFIG_DIR=\$HOME/.claude-jorah claude auth login" >&2
echo "  CLAUDE_CONFIG_DIR=\$HOME/.claude-jorah openclaw --profile $PROFILE models auth login --provider anthropic --method cli --set-default" >&2
echo "Then block any saved API key: ./scripts/switch-brain.sh cli" >&2
echo "Then add Telegram: openclaw --profile $PROFILE channels add" >&2
echo "Then download the embedding model: openclaw --profile $PROFILE models auth login --provider llama-cpp --method local" >&2
