# OpenClaw upgrade 2026.10.9 → 2026.11.5: findings and plan (2026-11-22, source tier only)

Build session sad-chaum-abf56e. Nothing installed or changed on the PC. All PC reads were read-only.

## 1. Root cause of the 16:57:48 deep hand-back failure [measured, live log + filesystem]

Live log, 2026-11-22 (UTC 15:57:48 = 16:57:48 CET):
- `claude-cli transcript check v4 miss (sessionId-deterministic path, grace 250ms): sessionId=effa46d1-… expectedPath=/home/jorah/.claude/projects/-home-jorah-workspace/effa46d1-….jsonl fileExists=false`
- then the announce run `announce:v1:agent:deep:subagent:…` on main fails `cli_live_session_changed`, `CLI session cleared after failed reused turn … reason=session_expired`, `Subagent announce give up (permanent_failure)`, and 7 s later the recovery turn fails `SESSION_DELIVERY_GENERATION_UNAVAILABLE` (dead-lettered). The answer still reached the chat through recovery.
- The transcript exists: `/home/jorah/.claude-jorah/projects/-home-jorah-workspace/effa46d1-….jsonl` (288 KB, written 16:57).
- `~/.claude/projects/` on the PC holds only `-opt-node-lib-node-modules-openclaw`. **The link `~/.claude/projects/-home-jorah-workspace → ~/.claude-jorah/projects/-home-jorah-workspace` that README "Conversation continuity" / `scripts/setup-continuity.sh` describe does not exist on the PC.** The cutover restored state but never ran that step (and the script derives the key from `$REPO/workspace`, which on the PC is `/opt/jorah/workspace`, not `/home/jorah/workspace`, so it would make the wrong link there).
- Since 2026-11-16 (Max lane): 280 probe misses, all for `-home-jorah-workspace`; 2 `cli_live_session_changed`; 1 announce give-up.
- Gateway env: `CLAUDE_CONFIG_DIR=/home/jorah/.claude-jorah` (unit file), so Claude writes there, while 10.9's probe looks only under `$HOME/.claude` (`claude-cli-project-dir.ts`).
- Mechanism (matches upstream issue #166130 / #145309): a missed probe makes `prepare` pin `requiredClaudeLiveSessionGeneration`; the announce run needs a new process (`reuse=reusable-drift:system-prompt`), the registry refuses the changed generation → `cli_live_session_changed`.
- Main did not call `sessions_yield` in that turn (spawn, then `end_turn`), so the 11.5 yield fix (#179486) is not what this needs.

## 2. Which release fixes it [verified: GitHub source at tags]

`src/agents/command/claude-cli-project-dir.ts`:
- v2026.10.9 and **v2026.10.33**: `$HOME/.claude/projects` only. **10.33, the target of the 2026-11-19 plan, does not fix this.**
- v2026.11.5 and v2026.11.6: new `resolveClaudeCliProjectsDir()` uses `CLAUDE_CONFIG_DIR` when no explicit home is passed. Release note 11.5: "Fixes stopped Claude CLI sessions failing to resume or import history when transcripts are in a custom configuration directory".

## 3. Releases and the 7-day rule [verified: GitHub releases API]

| Version | Published (UTC) | 7 days old (CET) | Notes |
|---|---|---|---|
| 2026.11.4 | 11-16 04:17 | 11-23 05:17 | no CONFIG_DIR fix (release branch, like 10.33) |
| 2026.11.5 | 11-17 10:47 | **11-24 11:47** | fix present; 15,606 commits ahead of 10.9 |
| 2026.10.33 | 11-18 04:15 | 11-25 05:15 | extended-stable; no CONFIG_DIR fix |
| 2026.11.6 | 11-19 17:26 | **11-26 18:26** | 11.5 + 406 commits, patch release |
| 2026.11.10-beta.1 | 11-19 | — | beta, not a candidate |

Advisories: only GHSA-pw3x-g8v8-fvj2 since 11-10; 11.5 and 11.6 are outside its ranges.

11.6 adds, relevant to Jorah: Claude CLI fails clearly when the OpenClaw MCP server doesn't connect (#176154); resume survives a tool-loading-hint change (abb3431); queued Telegram replies incl. subagent completions no longer abort (#189457); a batch of subagent-result delivery fixes (#200005, #200279, #200760, 3d2ebc2, 8bd36aa, 1d09030, #200516); exec-approval security fixes (#187884, #190024, 266a72e, 58997e1).

Open upstream, affects 11.5 and 11.6: #202518, claude-cli run never closes after `sessions_spawn` + `sessions_yield` in long sessions. Jorah's main doesn't yield today (deep's allow list has `sessions_yield`). Keep main off `sessions_yield`.

## 4. Changelog read 10.9 → 11.5 (+11.6), what touches Jorah

Earlier record (runbook, 2026-11-19) covers 10.10, 11.1–11.4, 10.33. New here, from 11.5 (21,387 lines, grepped by topic, not read line by line) and 11.6:

**Hook shapes** [verified: `src/plugins/hook-types.ts` and split files at v2026.10.9 vs v2026.11.5]
- `before_tool_call` event, `after_tool_call` event, tool context, `message_sending` event/result, `message_received`, `before_agent_run`, `before_reset`: unchanged except additive fields (`trigger?` on tool context, `images?` on before_agent_run). `PluginHookBeforeToolCallResult` (`params`, `block`, `blockReason`, `requireApproval{…}`) unchanged.
- Timeouts now explicit: `before_tool_call` 15 s and **fails closed**; `message_sending` 15 s and **fails open** (a hung guard would let a message out unstripped). The guard is fast; note only.
- 11.5: plugin `before_tool_call` inputs that "share memory with the host" are rejected (isolation). Test on canary.
- 11.5: after-tool hook result edits can affect later display: treat results read-only. jorah-guard only reads them (check on canary).

**Tool Search** [verified]: `src/plugins/tool-hook-matcher.ts` identical in 10.33 and 11.5 (`tool_call` → `dispatch_action`). The guard's 2026-11-20 wrapper fix (`plugins/jorah-guard/lib/wrapper.js`) targets that. New in 11.5: **managed Claude CLI turns load OpenClaw tool definitions through Tool Search by default** ("Definitions load as needed by default"), so main/deep on Max will call wrapped tools; the guard must see the inner name. `tools.gatewayPolicy` (deployment-wide allowlist) is new, not needed.

**Plugin SDK** (11.5): 13 top-level SDK methods removed, `api.on("deactivate")` alias removed, SDK contract change without compat window (`setActiveEmbeddedRun`, `chatAbortControllers`…). Jorah plugins use only `registerTool`, `on` (before_tool_call, after_tool_call, before_agent_run, before_reset, message_received, message_sending), `registerCommand`, `registerRealtimeVoiceProvider`, `runtime.subagent.{run,waitForRun,getSessionMessages,deleteSession}` (jorah-sites), `pluginConfig`, `logger`; no SDK imports. None is in the removed list; confirm by loading all plugins on the canary. `package.json` `compat`/`build` fields say 10.9; bump after.

**claude-cli**: CONFIG_DIR transcript fix (above); yield/child-handoff fix #179486; completed CLI turns no longer left "active"; subagent result no longer lost/mistaken for the user; MCP settings edits after launch prep don't affect the attempt; native Claude Code tools under `on-miss`/`always` approval now prompt instead of being denied.

**Sandbox**: bundled default images moved to Debian 13. Jorah pins its own `openclaw-sandbox:bookworm-slim` (`stage0.patch.json5`), so no forced change; check on canary. Default `pidsLimit` 1024 for Podman containers.

**Security-relevant defaults that change** (each needs a decision):
- **Host `apply_patch` may edit outside the workspace by default** (11.5). Main runs `runtime: direct`. Propose restoring the workspace restriction (exact key from 11.5 docs `tools/apply-patch`, checked on canary).
- **User-installed plugins show native UI in the Control UI by default, unsandboxed, with the viewer's permissions** (11.5). All jorah-* plugins are user-installed. Propose `gateway.controlUi.experimental.customPlugins: false`.
- Plugin install by bare package name goes to ClawHub (11.5); local `--link` installs are unaffected; `configure.sh`'s `@openclaw/acpx` would need `npm:` (configure.sh isn't re-run).

**Pairing / scopes** (HUD holds operator.admin, ADR 0007): 11.5 moves client identities, pairing tokens and local socket credentials out of the shared Gateway DB, keeping existing ones. "A client issued new credentials between an upgrade and automatic rollback needs to pair again." So a rollback to 10.9 may need HUD/iPhone re-pairing. HUD's `plugin.approval.list` and `/new` to be checked on canary.

**Cron**: `HEARTBEAT_OK` alone no longer silences a cron reply (no Jorah file uses it); jobs scheduled into an existing conversation can't manage other automations or wait for a child; default jobs may pause until an interactive `doctor --fix` if the default partition can't be identified.

**Telegram** (11.6): subagent completion replies no longer abort when an earlier turn ends.

## 5. Plan

0. **Now, on live 10.9 (needs Adam's yes):** `ln -s /home/jorah/.claude-jorah/projects/-home-jorah-workspace /home/jorah/.claude/projects/-home-jorah-workspace` as `jorah`. No restart, no config. Undo: `rm` the link. Expected: no more `transcript check v4 miss`, and a deep consult hands back. Fixes the bug two days before any upgrade is eligible; harmless after 11.5.
1. **Target (Adam's choice):** 11.5 (canary from 11-24 11:47) or 11.6 (from 11-26 18:26, more subagent/CLI and exec-approval fixes). Either replaces 10.33. The 10.33 exception of 2026-11-19 lapses; neither needs an exception.
2. **Canary on jorah-dev:** restore jorah-dev from `~/backups/jorah-dev-pre-1033-20261119T1805.tar.gz` (10.9 state, like live); install in a scratch prefix with `--min-release-age=7`; `doctor --fix`; list every package under 7 days old (doctor's plugin installer ignores the rule); guard tests + `just check`; check dist for hook shapes, Tool Search names, apply_patch and customPlugins keys; claude-cli main turn → deep consult hand-back with `CLAUDE_CONFIG_DIR` set and **no** link (proves 11.5's fix); planted unseen URL blocked; `dispatch_action` allowed call passes; audit. Restore jorah-dev after.
3. **Preview live upgrade → Adam's yes.** Back up state + `openclaw.json`; stop Gateway (never two); install; `doctor --fix`; start; `/readyz` ready before any config change; the existing post-upgrade checklist.
4. **After:** Adam's Telegram test; guard "matrix loaded; state ok"; `brain-lane.sh status` → `LANE: max`; deep hand-back from main; record in `config/versions.env` (create it) and the runbook.
