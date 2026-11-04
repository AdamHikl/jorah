#!/usr/bin/env bash
# Writes ~/.claude-jorah/settings.json: what delegated Claude Code (ACP) may do.
# Safe to re-run. Only touches Jorah's Claude Code config, never ~/.claude.
#
# - File tools: reads stop at the working directory; writes stay in sandbox/ and ~/work.
# - Bash: runs in the macOS sandbox with writes confined to sandbox/, ~/work and Claude Code's
#   temp folder, no home directory reads except sandbox/ and ~/work, no network. Fails closed
#   if it can't start.
# - WebFetch and WebSearch run outside the sandbox, so they are denied by rule.
# - Text deny rules are only a second line. The sandbox is what holds.
#
# JORAH_PACKAGE_NETWORK=1 also opens the npm and PyPI registries to sandboxed commands.
# pip's default macOS trust store can't reach trustd in the sandbox, so it uses its own CA bundle.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SANDBOX="$REPO/sandbox"
PROJECTS="$HOME/work"
CONFIG_DIR="$HOME/.claude-jorah"
SETTINGS="$CONFIG_DIR/settings.json"
USER_ID="$(id -u)"

mkdir -p "$SANDBOX" "$PROJECTS" "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# A spawn with no explicit cwd inherits the agent's workspace, not the acpx default. These
# keep Jorah's memory and identity files out of reach; the brain uses OpenClaw's own tools.
WORKSPACE="$REPO/workspace"

# Second line for a task spawned with its working directory outside sandbox/.
SECRET_DIRS=(.ssh .aws .gnupg .claude .claude-jorah .openclaw .openclaw-jorah .jorah-brain .acpx
  .codex .gemini .copilot .config .docker .kube .supabase .pulumi .amplify .mcp-auth
  .cognio-recovery Library/Keychains)
SECRET_FILES=(.claude.json .netrc .npmrc .git-credentials .zsh_history .bash_history)

read_denies=""
for dir in "${SECRET_DIRS[@]}"; do
  read_denies+="      \"Read(/$HOME/$dir/**)\","$'\n'
done
for file in "${SECRET_FILES[@]}"; do
  read_denies+="      \"Read(/$HOME/$file)\","$'\n'
done

if [ "${JORAH_PACKAGE_NETWORK:-}" = "1" ]; then
  allowed_domains='"registry.npmjs.org", "pypi.org", "files.pythonhosted.org"'
  cache_env=",
    \"npm_config_cache\": \"$SANDBOX/.cache/npm\",
    \"PIP_CACHE_DIR\": \"$SANDBOX/.cache/pip\",
    \"PIP_USE_DEPRECATED\": \"legacy-certs\""
else
  allowed_domains=''
  cache_env=''
fi

# CLAUDE_CODE_TMPDIR moves Claude Code's own session files into sandbox/, so the
# /tmp/claude-<uid>/-* denies can fence off other Claude Code sessions' scratch files.
# The xcrun cache stays readable because /usr/bin/git and other Xcode shims need it.
umask 077
cat > "$SETTINGS" <<EOF
{
  "disableClaudeAiConnectors": true,
  "env": {
    "CLAUDE_CODE_TMPDIR": "$SANDBOX/.tmp",
    "GOMODCACHE": "$PROJECTS/.cache/go/mod",
    "GOCACHE": "$PROJECTS/.cache/go/build",
    "GOTOOLCHAIN": "local",
    "GOFLAGS": "-modcacherw"$cache_env
  },
  "permissions": {
    "blockReadsOutsideWorkingDirectories": true,
    "additionalDirectories": ["$SANDBOX", "$PROJECTS"],
    "allow": [
      "Edit(/$SANDBOX/**)",
      "Edit(/$PROJECTS/**)",
      "Bash(rm *)",
      "Bash(rmdir *)"
    ],
    "deny": [
      "Read(/$WORKSPACE/**)",
      "Edit(/$WORKSPACE/**)",
      "WebFetch",
      "WebSearch",
$read_denies      "Bash(git push *)",
      "Bash(rm -rf *)",
      "Bash(rm -fr *)",
      "Bash(sudo *)",
      "Bash(git reset --hard *)",
      "Bash(git clean *)",
      "Bash(security *)",
      "Agent",
      "Workflow",
      "EnterWorktree",
      "ExitWorktree",
      "CronCreate",
      "CronDelete",
      "ScheduleWakeup",
      "RemoteTrigger",
      "PushNotification",
      "ListAgents",
      "SendMessage",
      "DesignSync"
    ]
  },
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false,
    "filesystem": {
      "denyRead": [
        "$HOME",
        "/tmp/claude-$USER_ID/-*",
        "/private/tmp/claude-$USER_ID/-*",
        "/var/folders",
        "/private/var/folders"
      ],
      "allowRead": [
        "$SANDBOX",
        "$PROJECTS",
        "/var/folders/*/*/T/xcrun_db*",
        "/private/var/folders/*/*/T/xcrun_db*"
      ],
      "denyWrite": [
        "$WORKSPACE",
        "/tmp/claude-$USER_ID/-*",
        "/private/tmp/claude-$USER_ID/-*"
      ]
    },
    "credentials": {
      "envVars": [
        { "name": "ANTHROPIC_API_KEY", "mode": "deny" },
        { "name": "ANTHROPIC_AUTH_TOKEN", "mode": "deny" },
        { "name": "CLAUDE_CODE_OAUTH_TOKEN", "mode": "deny" },
        { "name": "CLAUDE_CODE_MESSAGING_TOKEN", "mode": "deny" },
        { "name": "OPENCLAW_GATEWAY_TOKEN", "mode": "deny" },
        { "name": "OPENCLAW_GATEWAY_PASSWORD", "mode": "deny" },
        { "name": "TELEGRAM_BOT_TOKEN", "mode": "deny" },
        { "name": "GITHUB_TOKEN", "mode": "deny" },
        { "name": "GH_TOKEN", "mode": "deny" }
      ]
    },
    "network": {
      "allowedDomains": [$allowed_domains],
      "strictAllowlist": true
    }
  }
}
EOF
chmod 600 "$SETTINGS"
