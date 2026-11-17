#!/usr/bin/env bash
# Writes the Claude Code settings for project runs (docs/plan/11-project-mode.md, section 4.3), run
# as jorah. Four files in ~/.claude-jorah, never settings.json (that one is the coding jobs'):
#   project-settings.json            for projects with "web": false (WebFetch and WebSearch denied)
#   project-settings-web.json        for projects with "web": true  (both allowed; they run outside
#                                    the sandbox, so web text reaches the run: plan section 9, PM-T1)
#   project-settings-setup.json      the same two for a setup run (plan 11 section 5.1), which
#   project-settings-setup-web.json  drafts the charter: the same rules minus the CHARTER.md deny
# The runner passes one with --settings and --setting-sources "" so nothing else loads: not the
# coding jobs' settings.json, and not the work repo's own .claude/settings.json (hooks, rules).
#
# Same base as scripts/pc/setup-permissions.sh: the sandbox on and failing closed, no unsandboxed
# commands, the home folder unreadable except ~/sandbox, ~/work and the jorah-github mirrors, the
# same secret denies and credential env denies, npm and PyPI only. Differences:
#   - effort high (Adam, 2026-11-16), model claude-opus-5-5
#   - /opt/jorah-bench readable (the robotics bench; root-owned, the sandbox never writes it)
#   - hooks off, and a second-line deny on editing any project's CHARTER.md (not in a setup run),
#     its intake.md (never) and on history rewrites. Only Edit(path) rules: Claude Code matches
#     file permissions on Edit rules alone (a Write(path) rule only draws a warning), and an
#     Edit rule covers every editing tool. The runner's own checks stay the first line either way.
# Safe to re-run. JORAH_PACKAGE_NETWORK=0 closes the registries, as for coding jobs.
set -euo pipefail

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
for bin in bwrap socat python3; do command -v "$bin" >/dev/null || { echo "$bin is missing: Claude Code's sandbox needs it."; exit 3; }; done
CONFIG_DIR="$HOME/.claude-jorah"
mkdir -p "$HOME/sandbox" "$HOME/work" "$CONFIG_DIR" "$HOME/.jorah-github/mirrors"
chmod 700 "$CONFIG_DIR" "$HOME/sandbox" "$HOME/work" "$HOME/.jorah-github" "$HOME/.jorah-github/mirrors"

umask 077
HOME_DIR="$HOME" UID_NUM="$(id -u)" PACKAGES="${JORAH_PACKAGE_NETWORK:-1}" /usr/bin/python3 -I - "$CONFIG_DIR" <<'PY'
import json, os, sys

home = os.environ["HOME_DIR"]
uid = os.environ["UID_NUM"]
out_dir = sys.argv[1]
sandbox, work, mirrors, bench = f"{home}/sandbox", f"{home}/work", f"{home}/.jorah-github/mirrors", "/opt/jorah-bench"
workspace = f"{home}/workspace"
secret_dirs = [".ssh", ".aws", ".gnupg", ".claude", ".claude-jorah", ".openclaw", ".openclaw-jorah", ".jorah-brain", ".acpx",
               ".codex", ".gemini", ".copilot", ".config", ".docker", ".kube", ".supabase", ".pulumi", ".amplify", ".mcp-auth",
               ".local/share/keyrings", ".jorah-projects", ".jorah-guard", ".jorah-github"]
secret_files = [".claude.json", ".netrc", ".npmrc", ".git-credentials", ".zsh_history", ".bash_history"]
packages = os.environ["PACKAGES"] == "1"

env = {
    "CLAUDE_CODE_TMPDIR": f"{sandbox}/.tmp",
    "GOMODCACHE": f"{work}/.cache/go/mod",
    "GOCACHE": f"{work}/.cache/go/build",
    "GOTOOLCHAIN": "local",
    "GOFLAGS": "-modcacherw",
    "GIT_AUTHOR_NAME": "Jorah",
    "GIT_AUTHOR_EMAIL": "jorah@localhost",
    "GIT_COMMITTER_NAME": "Jorah",
    "GIT_COMMITTER_EMAIL": "jorah@localhost",
}
if packages:
    env.update(npm_config_cache=f"{sandbox}/.cache/npm", PIP_CACHE_DIR=f"{sandbox}/.cache/pip")

deny = [f"Read(/{workspace}/**)", f"Edit(/{workspace}/**)"]
# The mirrors stay readable to sandboxed git (allowRead below); the deny is for the file tools.
deny += [f"Read(/{home}/{d}/**)" for d in secret_dirs if d != ".jorah-github"]
deny += [f"Read(/{home}/{f})" for f in secret_files]
charter_deny = f"Edit(/{work}/*/project/CHARTER.md)"
deny += [
    f"Edit(/{work}/*/project/intake.md)",
    "Bash(git push *)", "Bash(git rebase *)", "Bash(git commit --amend *)", "Bash(git reset --hard *)",
    "Bash(git clean *)", "Bash(git filter-branch *)", "Bash(rm -rf *)", "Bash(rm -fr *)", "Bash(sudo *)",
    "Agent", "Workflow", "EnterWorktree", "ExitWorktree", "CronCreate", "CronDelete", "ScheduleWakeup", "RemoteTrigger",
    "PushNotification", "ListAgents", "SendMessage", "DesignSync",
]

def settings(web, setup):
    allow = [f"Edit(/{sandbox}/**)", f"Edit(/{work}/**)", "Bash(rm *)", "Bash(rmdir *)"]
    rules = list(deny) if setup else [charter_deny, *deny]
    if web:
        allow += ["WebSearch", "WebFetch"]
    else:
        rules += ["WebFetch", "WebSearch"]
    return {
        "disableClaudeAiConnectors": True,
        "disableAllHooks": True,
        "enableAllProjectMcpServers": False,
        "model": "claude-opus-5-5",
        "effortLevel": "high",
        "env": env,
        "permissions": {
            "blockReadsOutsideWorkingDirectories": True,
            "additionalDirectories": [sandbox, work, bench],
            "allow": allow,
            "deny": rules,
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "denyRead": [home, f"/tmp/claude-{uid}/-*"],
                "allowRead": [sandbox, work, mirrors, bench],
                "denyWrite": [workspace, bench, f"/tmp/claude-{uid}/-*"],
            },
            "credentials": {"envVars": [{"name": n, "mode": "deny"} for n in (
                "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_MESSAGING_TOKEN",
                "OPENCLAW_GATEWAY_TOKEN", "OPENCLAW_GATEWAY_PASSWORD", "TELEGRAM_BOT_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")]},
            "network": {
                "allowedDomains": ["registry.npmjs.org", "pypi.org", "files.pythonhosted.org"] if packages else [],
                "strictAllowlist": True,
            },
        },
    }

for name, web, setup in (("project-settings.json", False, False), ("project-settings-web.json", True, False),
                         ("project-settings-setup.json", False, True), ("project-settings-setup-web.json", True, True)):
    path = os.path.join(out_dir, name)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(settings(web, setup), handle, indent=2)
        handle.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    print(f"wrote {path} (web {'allowed' if web else 'denied'}, {'setup run: charter editable' if setup else 'charter denied'}, effort high)")
PY
