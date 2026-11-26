# ADR 0011: May typing in the paired Mac HUD count as Adam's own clean chat?

**Status:** proposed on 2026-11-22 (issue #22, part 2). Decided by Adam on 2026-11-26: option B,
on a weaker anchor than the device id (a waived gate, below). Built on `claude/hud-drive`.

**Question:** jorah-guard treated typing in the Mac HUD (`webchat`) like voice: every guarded call
gets a card, even in a chat that has read nothing from outside (`plugins/jorah-guard/lib/policy.js`,
`typedByOwner` and `sessionState`). Telegram typing with Adam's sender id is "clean" until the chat
reads outside text. Should the paired HUD's typing be clean too?

## Decision, 2026-11-26

Adam asked for Jorah to work more on its own, "like jarvis", without confirming each step. Asked
"How far should HUD typing in your main conversation count as you?", Adam chose "Same as Telegram
(Recommended)". That option read: "HUD typing counts as your clean chat, like Telegram. Background
jobs, project records, memory notes in your words and one-off reminders run without a card. About
16 of the last 21 HUD cards go away. Cards stay for tool installs, project access changes, anything
after Jorah reads outside text, and anything leaving the PC. Lines Claude Code types in drive mode
get a visible marker and keep their cards."

**What counts as Adam's typing.** A `webchat` turn counts when all of these hold
(`typedByOwner` and `hudKind` in `plugins/jorah-guard/lib/policy.js`, `before_agent_run` in
`index.js`):

- `senderIsOwner` is `true`.
- The guard saw the run start in `before_agent_run`, and saw the line as sent in
  `before_prompt_build` for the same run id (see below). A tool call from a run it never saw, a
  turn without a run id, or a `webchat` run without that line keeps its card.
- The run isn't a heartbeat, cron job or event: its `trigger` is `user` (or absent). In the PC's
  guard log every `webchat` row so far has `trigger: "user"`; heartbeats run in their own
  `…:heartbeat` sessions with no channel.
- Its run id isn't one the Gateway's HTTP APIs give: `chatcmpl_…` (Chat Completions) or `resp_…`
  (Responses). The Gateway makes these ids itself from a random UUID (`openai-http-*.mjs` and
  `openresponses-http-*.mjs` in the 2026.11.6 dist), so a caller of those APIs can't choose a
  HUD-looking id. jorah-voice and jorah-phone use Chat Completions, so they never count, even if
  their spoken marker were lost.
- Neither `[Spoken turn.` nor `[Typed by Claude Code` is in the first 200 characters of the line as
  sent, of the prompt `before_agent_run` gets, or of the typed text in either (OpenClaw may put a
  timestamp or a metadata block first).
- The plugin setting `hudTypingIsAdam` isn't `false` (default: on).
- The run is in the main agent's `agent:main:main` (`cleanSessionKeys`). A "+" chat in the HUD, or
  a run OpenClaw starts itself on `webchat` (a skill review), isn't Adam's typing, not even for
  memory notes in their words (fix of 2026-11-26, after the first live test).
- The session isn't a child: not an OpenClaw subagent (`…:subagent:…`) and not one the guard saw
  spawned. OpenClaw copies the parent's owner flag and channel onto a subagent run, so without this
  a brief Jorah wrote would count as Adam's words. This holds for Telegram too.

The chat is no longer clean once it reads outside text, exactly like Telegram. The guard's log
shows these turns as `from: "hud-typed"`. OpenClaw 2026.11.6 puts no requester on
`before_agent_run` and none on most tool calls (only `tool_search` had one in the live log), so the
guard rebuilds the run's requester from the context's channel and the event's sender and hands it
to that run's tool calls by run id (`agentRunRequester`, `rememberRun`). Plugin commands are unchanged (ADR 0012):
`/jorah-careful off` and `/jorah-freeze` still answer only on Telegram.

**The line as sent, not the composed prompt (fix of 2026-11-26, after the third drive test).** For
Claude CLI runs OpenClaw 2026.11.6 hands `before_agent_run` the prompt it built for the hooks:
`${prependContext}\n\n${prompt}\n\n${appendContext}` (`promptForHooks` in the CLI runner).
memory-core's standing intents and active memory come before the line; runtime context, delivery
guidance and part of the system prompt come after it. In the live test a drive line's marker sat
past the first 200 characters, so the guard logged it `from: "hud-typed"` (its write still got a
card because the chat had read outside text), and Adam's "own words" included the appended text.
`before_prompt_build` runs earlier with the line as sent and the same run id (skipped only for side
questions and control operations; prompt-build hooks are allowed unless
`hooks.allowPromptInjection` is `false`). The guard keeps that line by run id, uses it for the
markers and for Adam's words, and takes it once. The guard's handler returns nothing, so it never
changes the prompt. If a future OpenClaw stops calling `before_prompt_build` for HUD turns, every
HUD turn keeps its card again (safe side); re-check after each upgrade with a drive line and a
typed line.

**Drive mode** (ADR 0012) puts `[Typed by Claude Code in HUD drive mode.]` in front of every line it
types, so those turns keep every card, and the card says Claude Code typed it. It may send only a
short list of commands unmarked, and nothing while a run is active (so a drive line can't join a
run Adam typed).

### Waived gate: the device-id anchor

The 2026-11-22 recommendation made B and C wait until OpenClaw passes the sending device's id to
hooks. OpenClaw 2026.11.6 still doesn't. Adam accepted the weaker anchor above on 2026-11-26 by
choosing "Same as Telegram". This is a waived gate, written here: B is built without the device id.
After every OpenClaw upgrade, re-check whether the device id reaches `before_agent_run` (search the
dist for `approvalReviewerDeviceId` in `buildAgentHookContext`); once it does, pin the HUD's device
id and keep the run-id rule as a second check.

### Risks accepted

- **Other paired devices count too.** The Control UI in a browser, or any device paired with
  `operator.write`, sends turns that look the same to a hook and now counts as Adam. List and revoke
  devices with `openclaw --profile jorah devices list` and `devices revoke` (ADR 0007).
- **Credential holders.** Whoever holds the Gateway token or a paired device's key can open a
  WebSocket and type as Adam. That credential already gives operator access to the Gateway, so this
  widens little, but it now skips some cards.
- **Someone at Adam's unlocked Mac** can type in the HUD as them, as they could in Telegram there.
- **Voice joining a typed run.** If a spoken turn is steered into a run Adam typed while it is still
  going, its tool calls carry the typed run's id. Narrow: the voice clients start their own runs,
  and the spoken words don't become Adam's words for memory notes.

### Undo

Set `hudTypingIsAdam: false` in the jorah-guard plugin config (a config change: Adam's yes first)
and recycle the Gateway: every HUD turn gets its card again. Or redeploy the previous guard files
from the backup made at deploy time.

## Why the guard couldn't tell (2026-11-22)

- The hook context for a HUD turn carries `requester.channel: "webchat"`, `senderIsOwner: true`, and
  no sender id (P5.4 and 2026-11-22 notes in `policy.js`).
- The same shape comes from the Control UI in a browser, and from any Chat Completions caller that
  holds the Gateway token: such a caller can name any channel in `x-openclaw-message-channel` but
  never a sender id. So "webchat with no sender id" proves only that the caller holds some Gateway
  credential, not that Adam typed it in the HUD.
- The Gateway does know which paired device sent a turn: it names that device as the card's
  reviewer (`ApprovalReviewerDeviceId`, ADR 0007, source read). OpenClaw 2026.10.9 does **not**
  pass that device id to plugin hooks (`before_agent_run`, `before_tool_call`): the spike below
  found it only in the host's internal run context, which the hook context is filtered from.

## Options

| | What | Gains | Costs and risks |
|---|---|---|---|
| A | Keep it as now | Nothing new to trust | Cards on every guarded HUD action, even in a clean chat |
| B | Clean when the turn comes from the HUD's own paired device id, pinned in the guard's config | HUD typing works like Telegram: memory saves in Adam's words, `project_start`, `supply_save` and small records need no card in a clean chat | Needs a device id the Gateway sets and the model can't, in the hook context. A stolen HUD device token (Mac login Keychain) then acts as Adam typing. Anyone at Adam's unlocked Mac can type as them, as they could in Telegram on that Mac |
| C | B, but only for the small classes (`memoryWrite` in Adam's words, `localWrite`) | Most of the friction gone | Spawns, schedules, pushes and `confirmAlways` keep their cards from the HUD; two rules to explain |

A stolen device token is about as strong as a stolen Telegram session on the same Mac. The
difference is that Telegram also checks the sender id on its own servers, while the HUD's token is
checked only by the Gateway. Revoking it is `openclaw --profile jorah devices revoke` (ADR 0007).

## Recommendation, 2026-11-22 (superseded by the decision above)

A, on OpenClaw 2026.10.9 (updated after the spike of 2026-11-22). C stays the target, but it is
not buildable: the one field that would tell the HUD apart, the paired device's id, is verified by
the Gateway and can't be forged, yet never reaches a plugin hook. Everything a hook does see
(`channel`, `senderId`, `senderIsOwner`, `accountId`) a Chat Completions caller or the Control UI
can produce or match, so the guard must keep treating HUD typing like voice.

C becomes buildable only once OpenClaw puts the sending device's id (`client.connect.device.id`,
the value it already uses as `ApprovalReviewerDeviceId`) into the hook's `requester` or agent
context. That is an upstream change; re-check it after every OpenClaw upgrade (search the dist for
`approvalReviewerDeviceId` in `buildToolContext` and `buildAgentHookContext`).

## What deciding needs

1. ~~A spike: which fields differ between the three callers, and whether any is set only by the
   Gateway.~~ Done 2026-11-22 by source read (below): none that a hook can see.
2. ~~Adam's yes to an option, in writing, here.~~ Done 2026-11-26: B on the weaker anchor.
3. If C, once OpenClaw exposes the device id: the sketch at the end of the spike section.

## Spike, 2026-11-22

Source read of OpenClaw 2026.10.9 (`/opt/homebrew/lib/node_modules/openclaw/dist` on the Mac, the
version Jorah runs, README). No Gateway was run: the source settles the question, so the
scratch run the spike allowed wasn't needed. Evidence and file list:
`docs/evidence/adr11-hud-spike-2026-11-22/README.md`.

**Is there a Gateway-only device id?** Yes, but only inside the host.

- At `connect`, the Gateway checks the device block: the id must be derived from the public key,
  the signature must cover the Gateway's nonce and be fresh (`message-handler-*.mjs`,
  `deriveDeviceIdFromPublicKey`, `device-id-mismatch`, `device-nonce-mismatch`) [verified: source
  read]. A caller can't claim another device's id without its private key.
- For each `chat.send`, `resolveChatSendCallerContext` (`gateway-client-identity-*.mjs`) copies
  `client.connect.device.id` into `ApprovalReviewerDeviceId`, then into the run's
  `approvalReviewerDeviceId` (`get-reply-*.mjs`, `reply-tool-authority-*.mjs`) and the internal
  tool context (`agent-tools-*.mjs`, `builtin-openclaw-*.mjs`) [verified: source read]. It is used
  to route plugin approval cards to that device (`agent-tools.before-tool-call-*.mjs`).

**Does a hook see it?** No.

- `before_tool_call`: the host builds the plugin's context with `buildToolContext`
  (`agent-tools.before-tool-call-*.mjs`), which copies only `toolName`, `toolKind`,
  `toolInputKind`, `agentId`, `sessionKey`, `sessionId`, `runId`, `abortSignal`, `trace`,
  `toolCallId`, `channelId` and `requester`. `requester` is built in `agent-tools-*.mjs` and
  `host-capability-*.mjs` from `channel`, `accountId`, `senderId`, `senderIsOwner`, `roleIds`
  only [verified: source read].
- `before_agent_run`: the event carries `prompt`, `messages`, `systemPrompt`, `channelId`,
  `accountId`, `senderId`, `senderIsOwner`; the context comes from `buildAgentHookContext`
  (`hook-context-*.mjs`), which has no device field [verified: source read].
- The public types agree: no hook context or event type in the plugin SDK
  (`config-contracts-*.d.ts`, `src/plugins/hook-*.types`) has any device field, and
  `PluginHookToolRequesterContext` lists exactly the five fields above [verified: source read].

**What each caller looks like to a hook:**

| Caller | `channel` | `senderId` | `senderIsOwner` | Device id |
|---|---|---|---|---|
| HUD, `chat.send` over WS (`client.id: "gateway-client"`, paired device) | `webchat` (`INTERNAL_MESSAGE_CHANNEL`, `message-channel-constants-*.mjs`) [verified: source read] | the source sets `SenderId` to the client's self-declared `client.id` for non-operator-UI clients; the P5.4 observation saw none. Either way it is caller-chosen | owner when the client is an operator with the right scope | verified at connect, **not passed to hooks** |
| Control UI, `chat.send` over WS (`client.id: "openclaw-control-ui"`, pairs as its own browser device) | `webchat` | none (`isOperatorUiClient` drops it) | owner when it's an admin operator | its own, verified, **not passed to hooks** |
| Chat Completions, `POST /v1/chat/completions` | from `x-openclaw-message-channel`, default `webchat` (`openai-http-*.mjs`) | none | true when the shared secret grants `operator.admin` (`resolveOpenAiCompatibleHttpSenderIsOwner`) | none (HTTP has no device block) |

So a Gateway-token holder can reproduce every field the HUD's turns show a hook. The device id
would tell all three apart (the HUD and the Control UI have different paired ids, HTTP has none),
which is why C would work if OpenClaw exposed it.

**If OpenClaw exposes it later (sketch, not built; Adam decides first):**

- Field: the sending device's id in `ctx.requester` (or the agent context), set from
  `client.connect.device.id`. Accept it only if the plugin SDK type documents it as host-set.
- Pinned: the HUD's device id in `jorah-guard`'s plugin config (`hudDeviceIds`), not the
  permission matrix, written on Adam's yes after pairing; revoking the device
  (`openclaw --profile jorah devices revoke`) means removing it there too.
- Rule: clean only when `channel` is `webchat`, `senderIsOwner` is true and the device id is
  pinned; then only `memoryWrite` in Adam's words and `localWrite` (option C).
- Tests in `plugins/jorah-guard`: the pinned id in a clean chat passes those two classes without a
  card; a different device id, no device id, a Chat Completions shape with
  `x-openclaw-message-channel: webchat`, and the Control UI shape all keep the card; spawns,
  schedules, pushes and `confirmAlways` keep the card even with the pinned id; a tainted chat
  keeps the card.

## Related

ADR 0005 (native HUD), ADR 0007 (HUD answers cards), ADR 0010 (voice confirms cards, being built
in its own session on `feat/voice-confirm`). ADR 0012 (drive mode): a command line Adam arms in the HUD sends through
the HUD's device; building option B or C needs ADR 0012's condition first.
