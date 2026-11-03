#!/usr/bin/env bash
# Applies Jorah's non-secret OpenClaw config to the "jorah" profile.
# Safe to re-run. Secrets (Anthropic API key, Telegram bot token) are added
# separately with `openclaw --profile jorah configure`.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PINNED_VERSION="2026.10.9"

oc() { openclaw --profile jorah "$@"; }

if ! command -v openclaw >/dev/null; then
  echo "Installing openclaw@${PINNED_VERSION}" >&2
  npm install -g "openclaw@${PINNED_VERSION}" --allow-scripts=openclaw
fi

mkdir -p "$REPO/sandbox"

if [ ! -f "$HOME/.openclaw-jorah/openclaw.json" ]; then
  oc setup --baseline --workspace "$REPO/workspace"
fi

# Claude Code as the only ACP coding harness
oc plugins list 2>/dev/null | grep -q "acpx" || oc plugins install @openclaw/acpx
oc config set plugins.entries.acpx.enabled true
oc config set acp.enabled true
oc config set acp.backend acpx
oc config set acp.defaultAgent claude
oc config set acp.allowedAgents '["claude"]' --strict-json
oc config set plugins.entries.acpx.config.probeAgent claude
oc config set plugins.entries.acpx.config.cwd "$REPO/sandbox"
oc config set plugins.entries.acpx.config.nonInteractivePermissions deny
oc config set plugins.entries.acpx.config.timeoutSeconds 1800

oc config set gateway.bind loopback

# Jorah gets its own Claude Code config and login, separate from ~/.claude
mkdir -p "$HOME/.claude-jorah"
chmod 700 "$HOME/.claude-jorah"
oc config set env.vars.CLAUDE_CONFIG_DIR "$HOME/.claude-jorah"

# What delegated Claude Code may do. The bridge skips user settings unless this variable is set.
oc config set env.vars.ACPX_CLAUDE_INCLUDE_USER_SETTINGS '"1"' --strict-json
"$REPO/scripts/setup-permissions.sh"

# Memory stack (local embeddings, Active Memory, Memory Wiki)
oc plugins list 2>/dev/null | grep -q "llama-cpp" || oc plugins install @openclaw/llama-cpp-provider
oc config patch --file "$REPO/config/memory.patch.json5"

"$REPO/scripts/setup-learning.sh"
"$REPO/scripts/setup-continuity.sh"

oc config validate
echo "Done. Next, log Jorah's Claude Code in and route the brain through it:" >&2
echo "  CLAUDE_CONFIG_DIR=\$HOME/.claude-jorah claude auth login" >&2
echo "  CLAUDE_CONFIG_DIR=\$HOME/.claude-jorah openclaw --profile jorah models auth login --provider anthropic --method cli --set-default" >&2
echo "Then block any saved API key: ./scripts/switch-brain.sh cli" >&2
echo "Then add Telegram: openclaw --profile jorah channels add" >&2
echo "Then download the embedding model: openclaw --profile jorah models auth login --provider llama-cpp --method local" >&2
