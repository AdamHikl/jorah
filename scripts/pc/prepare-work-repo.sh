#!/usr/bin/env bash
# Prepares a clone in ~/work for Jorah's coding jobs. Run as jorah: prepare-work-repo.sh <project>
# - remote "github" reads the jorah-github plugin's mirror (git fetch github, no network or token)
# - hides the placeholder files Claude Code's sandbox mounts into the repo while a job runs
#   (.bashrc, .claude/..., .vscode and so on, /dev/null devices) from git status, in the repo's
#   local .git/info/exclude only, never in the project's own .gitignore
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
project="${1:-}"
[[ "$project" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "usage: $0 <project folder under ~/work>"; exit 2; }
repo="$HOME/work/$project"
[ -d "$repo/.git" ] || { echo "$repo is not a git clone"; exit 4; }
mirror="$HOME/.jorah-github/mirrors/$project.git"
git -C "$repo" remote get-url github >/dev/null 2>&1 || git -C "$repo" remote add github "$mirror"
git -C "$repo" remote set-url github "$mirror"
git -C "$repo" config remote.github.fetch "+refs/remotes/github/*:refs/remotes/github/*"
exclude="$repo/.git/info/exclude"
mkdir -p "$(dirname "$exclude")"
marker="# Claude Code sandbox placeholders (jorah prepare-work-repo.sh)"
if ! grep -qF "$marker" "$exclude" 2>/dev/null; then
  cat >> "$exclude" <<'PATTERNS'
# Claude Code sandbox placeholders (jorah prepare-work-repo.sh)
/.bash_profile
/.bashrc
/.profile
/.zprofile
/.zshrc
/.gitconfig
/.ripgreprc
/.mcp.json
/.idea
/.vscode
/.claude/agents
/.claude/commands
/.claude/hooks
/.claude/launch.json
/.claude/loop.md
/.claude/output-styles
PATTERNS
fi
echo "$project: remote github -> $mirror; placeholders hidden in .git/info/exclude"
