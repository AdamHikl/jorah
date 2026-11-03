# Jorah

A personal "Jarvis": one central agent you talk to, which sees, listens, speaks and acts through a fleet of devices.

- **Gateway / organizer:** [OpenClaw](https://docs.openclaw.ai) (pinned `2026.10.9`), profile `jorah` (state in `~/.openclaw-jorah`).
- **Brain model:** Claude through Jorah's own Claude Code login (`~/.claude-jorah`), separate from `~/.claude`. A manual switch moves it to an API key and back: see `docs/switch-brain.md`.
- **Specialist:** Claude Code, launched by Jorah through ACP (`@openclaw/acpx`), using the same login.
- **First channel:** Telegram.
- **Later:** phone/Mac device nodes, smart glasses, robots as nodes or MCP servers.

## Layout

| Path | What |
|---|---|
| `workspace/` | Jorah's workspace: `AGENTS.md` (rules, Claude Code delegation), `SOUL.md`, `USER.md`, `IDENTITY.md`, `skills/` |
| `workspace/memory/`, `MEMORY.md`, `USER.md`, `DREAMS.md` | Jorah's private memory (git-ignored) |
| `sandbox/` | Scratch folder for delegated Claude Code tasks (git-ignored) |
| `~/work/<repo>` | Jorah's own clones of real projects, separate from `~/Documents` (see Working on projects) |
| `config/memory.patch.json5` | Memory stack config |
| `scripts/configure.sh` | Re-applies the non-secret OpenClaw config (use on the always-on device) |
| `scripts/setup-permissions.sh` | Writes `~/.claude-jorah/settings.json`: what delegated Claude Code may do |
| `scripts/setup-continuity.sh` | Links transcripts so chats survive, sets the hourly Haiku heartbeat |
| `scripts/setup-learning.sh` | Checks learning setup; creates the daily review only with `--create-review-job` |
| `config/learning-review.prompt.md` | Prompt for the optional daily learning review |
| `scripts/switch-brain.sh` | Switches the brain between the Claude login and an API key (`cli`, `api`, `status`) |
| `docs/switch-brain.md` | Runbook for that switch |
| `scripts/snapshot-brain.sh` | Commits what Jorah has learned to `~/.jorah-brain`, a local-only git repo with no remote |

## Memory

| Human memory | Jorah's layer | Where it lives |
|---|---|---|
| Working | Current session; saved to disk before compaction | Session |
| Episodic | Daily notes, indexed transcripts, Active Memory (`escalate`) | `workspace/memory/` |
| Semantic | `USER.md`, `MEMORY.md`, Memory Wiki (`bridge`) | `workspace/`, `~/.openclaw-jorah/wiki/main` |
| Associative | Hybrid search with local EmbeddingGemma, recency decay | Agent SQLite index |
| Consolidation | Dreaming (nightly); review in `DREAMS.md` | `workspace/` |
| Procedural | Skill Workshop, saved in the same turn on the CLI login; say "undo" to revert | `~/.openclaw-jorah/agents/main/agent/workshop-skills` |
| Prospective | Standing intents, scheduled tasks | Agent SQLite, cron |

On the Claude CLI runtime, background self-learning reviews don't run. Jorah saves corrections in the same turn through `skill_workshop`, following `workspace/AGENTS.md`. An optional daily review is created by `scripts/setup-learning.sh --create-review-job`. Download the embedding model once per machine:

```bash
openclaw --profile jorah models auth login --provider llama-cpp --method local
```

## Set up on a machine

Requires Node 24.22.1+ (24.x) or 26.12.1+.

```bash
./scripts/configure.sh
CLAUDE_CONFIG_DIR=$HOME/.claude-jorah claude auth login
CLAUDE_CONFIG_DIR=$HOME/.claude-jorah openclaw --profile jorah models auth login --provider anthropic --method cli --set-default
openclaw --profile jorah channels add   # Telegram bot token
CLAUDE_CONFIG_DIR=$HOME/.claude-jorah ACPX_CLAUDE_INCLUDE_USER_SETTINGS=1 openclaw --profile jorah gateway run < /dev/null    # foreground, with no prompts
openclaw --profile jorah doctor
```

`< /dev/null` matters: with a terminal attached, a denied Claude Code action waits for `y/N` in that terminal instead of being refused.

Then message the bot on Telegram and approve the pairing request:

```bash
openclaw --profile jorah pairing list
openclaw --profile jorah pairing approve <code>
```

Check Claude Code delegation from chat with `/acp doctor`, then `/acp spawn claude`.

## Conversation continuity

`scripts/setup-continuity.sh` (safe to re-run; `configure.sh` calls it) does two things:

- Links `~/.claude/projects/<workspace key>` to `~/.claude-jorah/projects/<workspace key>`. OpenClaw 2026.10.9 only looks for Claude transcripts under `~/.claude`, so without the link Jorah loses the conversation when its Claude process exits.
- Sets `agents.defaults.heartbeat` to hourly, `anthropic/claude-haiku-5-5`, `isolatedSession: true`, so heartbeats run in `agent:main:main:heartbeat` and leave the main chat alone.

Side effect of the link: `claude --resume` run from `workspace/` under your own `~/.claude` lists Jorah's transcripts.

## Working on projects

Jorah works in its own clones under `~/work`, never in `~/Documents`. The two copies sync only through GitHub.

- **Clones:** full clones, not worktrees, so `.env` files and untracked work stay out. Pushing is disabled on each clone with `git remote set-url --push origin no-push://local-only`.
- **Branches:** `jorah/<task>`, local only for now. You review and push them yourself.
- **Dependencies:** install them from outside the sandbox, because delegated tasks have no network. Go uses the shared cache in `~/work/.cache/go`.
- **Pushing later:** this needs a bot account with access only to chosen repos, and `main` protected on GitHub. For `robo-sk/cognio` the repo owner has to set that up.

## Safety defaults

- Gateway binds to loopback only; reach it remotely through Tailscale, never the public internet.
- Only `claude` is an allowed ACP agent.
- Delegated Claude Code runs in the macOS sandbox (`scripts/setup-permissions.sh`). Commands can write only in `sandbox/`, `~/work` and Claude Code's temp folder, can't read the rest of the home directory, and have no network. It fails closed if the sandbox can't start.
- It can run tests and create venvs there. Installing packages needs `JORAH_PACKAGE_NETWORK=1 ./scripts/setup-permissions.sh`, which opens only the npm and PyPI registries; install scripts then run, and anything in those folders could be sent to those hosts.
- File tools can't read outside the working folder, and secret folders and `workspace/` are denied outright. `Bash` deny rules are simple text matches, so treat the sandbox as the real boundary.
- claude.ai connectors, subagents, worktrees, schedules and peer messaging are off for delegated tasks.
- Always pass `cwd` when spawning: a spawn without it starts in `workspace/`, not `sandbox/`.
- Not covered: Jorah's own `exec` tool, and any other folder Jorah explicitly passes as `cwd`.
- The brain never moves to the API on its own. On the login route a saved API key is blocked (`auth.order.anthropic: []` and no provider key reference). Never put a key in an environment variable: delegated Claude Code inherits the gateway's environment and would bill the API.
- `nonInteractivePermissions=deny`: Claude Code actions that would need a permission prompt are denied rather than auto-approved. Raising `permissionMode` to `approve-all` lets it write and run commands unattended; that is a deliberate choice, not a default.
- No community (ClawHub) skills unless read first.
- Upgrade OpenClaw deliberately: bump `PINNED_VERSION` in `scripts/configure.sh`, back up with `openclaw --profile jorah backup`, then `openclaw --profile jorah doctor --fix`.
