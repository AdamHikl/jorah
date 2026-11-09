#!/usr/bin/env bash
# Lets Jorah start Claude Code sessions (ACP through the acpx plugin) for coding jobs.
# Adam runs it as root, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-claude-acp.sh
#
# 1. Installs the Claude ACP adapter root-owned in /opt/jorah-tools, so Jorah can't change it, at
#    the version acpx 2026.10.9 asks for (^0.76.0 = 0.76.0, released 2026-09-09), with every
#    dependency as published on or before 2026-11-02 (7-day rule). It bundles Claude Code through
#    the Agent SDK 0.3.257. Without this, acpx would fetch the adapter with npx, unpinned.
# 2. Applies config/pc/acp.patch.json5: ACP on, acpx pointed at that copy.
#    Only Adam's own conversation (agent:main:main, outside the sandbox) can start a session:
#    OpenClaw refuses ACP from sandboxed sessions, which are cron, heartbeat, background and deep.
#    Each session runs in Claude Code's own sandbox (~/.claude-jorah/settings.json): no network for
#    commands, home unreadable except ~/work and ~/sandbox, no push, signed in to Adam's Max plan.
#
#   --undo   ACP off again (learning-guard.patch.json5). The installed copy stays.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }

OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
DIR=/opt/jorah-tools/claude-agent-acp
CFG=/home/jorah/.openclaw-jorah/openclaw.json

if [ "${1:-}" = "--undo" ]; then
  "${OC[@]}" config patch --file /opt/jorah/config/pc/learning-guard.patch.json5
  "${OC[@]}" config get acp.enabled
  exit 0
fi

echo "== 1. Adapter, pinned, root-owned"
mkdir -p "$DIR"
cd "$DIR"
[ -f package.json ] || echo '{"name":"jorah-claude-agent-acp","private":true}' > package.json
npm install --no-audit --no-fund --omit=dev --ignore-scripts --save-exact \
  --before=2026-11-02 @agentclientprotocol/claude-agent-acp@0.76.0
chown -R root:root /opt/jorah-tools
chmod -R go-w /opt/jorah-tools
BIN="$DIR/node_modules/.bin/claude-agent-acp"
[ -x "$BIN" ] || { echo "Adapter binary missing: $BIN"; exit 4; }
echo "  adapter: $(node -p "require('$DIR/node_modules/@agentclientprotocol/claude-agent-acp/package.json').version")"
echo "  agent sdk: $(node -p "require('$DIR/node_modules/@anthropic-ai/claude-agent-sdk/package.json').version")"
if [ -d "$DIR/node_modules/@anthropic-ai/claude-agent-sdk-linux-x64" ]; then
  echo "  Claude Code binary for linux-x64: present"
else
  echo "  Claude Code binary for linux-x64: MISSING"
fi

echo "== 2. Config"
[ -f "$CFG.pre-acp" ] || cp -p "$CFG" "$CFG.pre-acp"
"${OC[@]}" config patch --file /opt/jorah/config/pc/acp.patch.json5 --dry-run
"${OC[@]}" config patch --file /opt/jorah/config/pc/acp.patch.json5
echo "  acp.enabled: $("${OC[@]}" config get acp.enabled 2>/dev/null)"
echo "  claude command: $("${OC[@]}" config get plugins.entries.acpx.config.agents.claude.command 2>/dev/null)"
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. Config backup: $CFG.pre-acp. Undo: the same command with --undo."
