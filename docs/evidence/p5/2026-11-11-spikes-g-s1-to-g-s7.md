# P5.2: spikes G-S1 to G-S7 on `jorah-dev` (2026-11-11, 20:50-21:40)

All on the scratch profile `jorah-dev`. The live Jorah was not touched: its Gateway, config and store were only read, to confirm they were unchanged.

## Setup [measured]

- **Mirror** (`config/pc/dev/mirror.patch.json5`, dry run 30 updates, applied; backup `openclaw.json.pre-p5-mirror`): `main` on Haiku 5.5, `sandbox.mode: non-main`, the live tool list minus GitHub and agentmemory; `background` (Sonnet) and `deep` (Opus) added with `agents add` in `~/scratch-dev/workspace-*`, rules files from the repo, both sandboxed in Podman; all three on `anthropic:jorah-store` (`config/pc/dev/key-ref.plan.json`). `browser.evaluateEnabled: false`, session reset and Workshop as live.
- **Left out on purpose:** Telegram (the block and its stored bot token removed; the live store still has its own), `jorah-voice-provider` (it would reach the live voice service), ACP and `acpx`, `jorah-github`, agentmemory, an approvals route. Each comes back in P5.4 with a stand-in where needed.
- **Gateway token:** a fresh random token for `jorah-dev` only, in `~/.config/jorah-dev/gateway-token` (mode 600), never printed, so a voice-style client can call it as `jorah-voice` calls the live one.
- **Start and stop:** `scripts/pc/dev-gateway.sh start|stop|status` (loopback 43186, channels and cron off). Left stopped.
- **Observation plugin:** `plugins/jorah-guard-spike`, linked on `jorah-dev` only. It never blocks; it records context fields, tool names, parameter keys and result shapes, never values or sender ids. Two `before_tool_call` handlers at priority 100 and -100.

Seven turns: typed through the CLI (`agent`), voice-style through Chat Completions exactly as `services/jorah-voice/jorah_voice/brain.py` sends them (bearer token, `x-openclaw-session-key`, the voice system note), and Control-UI-style through the Gateway's `chat.send`. They covered web search and fetch, hand-offs to `deep` and `background`, a `MEMORY.md` edit, a reminder and a learned skill. 74 hook records, then 2 more for `chat.send`.

## Results

### G-S1: can the guard tell who is speaking? Partly [measured]

| Turn | `ctx.sessionKey` | `ctx.requester` |
|---|---|---|
| Typed, CLI `agent` | `agent:main:main` | `senderIsOwner: true`, no channel |
| **Voice-style, Chat Completions, shared Gateway token** | `agent:main:main` or the key the client sends | **`channel: "webchat"`, `senderIsOwner: true`, no sender id** |
| Control-UI-style `chat.send` (CLI device) | `agent:main:main` | `channel: "webchat"`, a sender id, `senderIsOwner: false` |
| `background` child | `agent:background:subagent:<uuid>` | `senderIsOwner: false`, or missing on Code Mode exec |
| Telegram | not testable on `jorah-dev` | `channel: "telegram"` expected [docs-only]; confirmed on live in P5.6 |

- `ctx.messageProvider` and `ctx.channelId` were never set; `requester` is the only source. `after_tool_call` carries no requester.
- **Voice is distinguishable from Telegram and the CLI, but only weakly from the Control UI:** both say `webchat`; they differ only in sender id and owner flag, which is fingerprinting, not a contract. The voice service also counts as the owner, because it uses the shared Gateway token.
- **Consequence for 4.3:** the guard needs a marker the voice service controls and the model can't. Next test, in P5.3: whether Chat Completions' `user` field reaches `requester.senderId` (then `jorah-voice` sends a fixed one), or `jorah-voice` gets its own device token. Until one of those passes, the guard treats every `webchat` turn as voice, so a Control UI turn that writes would also need a confirmation. Voice stays in the shared chat either way.
- **No parent link in the context:** a child's context has no parent session key. The `sessions_spawn` result carries `details.childSessionKey`, so the guard maps child to parent from it; a child it can't map is treated as having read outside text.

### G-S2: can the guard collect URLs it has seen? Yes [measured]

`after_tool_call` carried results for `web_search` (5,494 to 9,620 characters, 6 to 10 URLs), `web_fetch` (4 URLs) and the `tool_call` wrapper. The wrapper fires `before_tool_call` first as `tool_call` (params `id`, `args`), then again under the real tool's name, so the guard sees both. Catalog tools also appear: `tool_search` (`query`), `tool_describe` (`id`). A failed search returned an error and 77 characters.

### G-S3: do the outbound hooks fire? Not for voice or CLI replies [measured]

`message_sending`, `reply_payload_sending` and `message_received` fired **zero** times across all seven turns. Chat Completions replies (voice), CLI turns and `chat.send` do not pass through them. Telegram delivery should [docs-only, confirmed on live in P5.6]. So the outbound URL filter covers Telegram only. A spoken reply carries no clickable link, so the gap is small, but the Control UI's chat isn't covered.

### G-S4: tool names and parameters for the matrix [measured]

| Action | Tool and parameters |
|---|---|
| Edit `MEMORY.md` | `read` (`path`), then `edit` (`path`, `edits`). No `derivedPaths` on `edit`, so the guard reads `path` |
| Reminder | `automations`, `action: "add"`, `job` |
| Learned skill | `skill_workshop`, `action: "create"`, `name`, `reason`, `content` |
| Hand-off | `sessions_spawn` (`agentId`, `mode: "run"`, `task`), then `sessions_yield` (`message`) |
| `background`'s shell | `exec` with `toolKind: "code_mode_exec"` (`title`, `code`, `command`), then `exec` (`command`, `yieldMs`) |
| Web | `web_search` (`query`, `count`), `web_fetch` (`url`, `extractMode`) |

### G-S5: two plugins' hooks in order? Yes [measured, docs]

Every call ran the priority 100 handler before the -100 one. The docs say a `block: true` is final and skips lower-priority handlers. So the guard at a high priority runs before `jorah-github`'s card.

### G-S6: can Dreaming exclude sessions that read outside text? No, but it is narrower than feared [docs-only]

`docs/concepts/dreaming.md`: before consolidation, `memory-core` drops candidates whose provenance is `untrusted` or `system`, and only interactive sessions are ingested; cron, heartbeat and sub-agent sessions are not. Exclusions exist only by hook source, channel or chat type (`memoryPolicy.excludeSessions`), not by taint. `memory forget --session` purges by session afterwards. So the open path is Jorah *itself* writing planted text into its notes or `MEMORY.md`, which is what the guard's write rule covers. Each rewrite of `MEMORY.md` is kept in plugin state, and `DREAMS.md` lists the changes, so a nightly review is possible.

### G-S7: can the Gateway run from a config Jorah's user can't change? No, not on 2026.10.9 [measured]

| Try | Result |
|---|---|
| Copy in a root-owned folder (`root:jorah`, file 640), `OPENCLAW_CONFIG_PATH` | `config file` resolves to it; the Gateway fails at `gateway-run-bootstrap` with no stated reason |
| Copy marked immutable (`chattr +i`) in a folder Jorah's user owns | Jorah's user can't write or rename it (`Operation not permitted`). The Gateway fails at the same step and writes nothing beside it |
| Control: the same custom path, writable | Starts and listens |

`config set` printed "No change" in the failed runs, because no Gateway was running. So the W3.8 primary route fails as tried. The plan's fallback stands: a small check under another account that hashes `openclaw.json` and the plugin folders against the approved set, and stops the Gateway on a mismatch. It is a schedule, so it needs Adam's yes. Why the Gateway needs to write at start is not known [inference: config-guard or plugin install records]. Cleaned up: both test folders removed, the immutable flag cleared first.

## Leftovers on `jorah-dev`

Test sessions, a `MEMORY.md` line ("test colour is teal"), a reminder and a learned skill `spike-test-skill`: all scratch, cleared before the attack runs in P5.4.
