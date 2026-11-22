# ADR 0011: May typing in the paired Mac HUD count as Adam's own clean chat?

**Status:** proposed on 2026-11-22 (issue #22, part 2). Not decided, not built. Adam decides.

**Question:** jorah-guard treats typing in the Mac HUD (`webchat`) like voice: every guarded call
gets a card, even in a chat that has read nothing from outside (`plugins/jorah-guard/lib/policy.js`,
`typedByOwner` and `sessionState`). Telegram typing with Adam's sender id is "clean" until the chat
reads outside text. Should the paired HUD's typing be clean too?

## Why the guard can't tell today

- The hook context for a HUD turn carries `requester.channel: "webchat"`, `senderIsOwner: true`, and
  no sender id (P5.4 and 2026-11-22 notes in `policy.js`).
- The same shape comes from the Control UI in a browser, and from any Chat Completions caller that
  holds the Gateway token: such a caller can name any channel in `x-openclaw-message-channel` but
  never a sender id. So "webchat with no sender id" proves only that the caller holds some Gateway
  credential, not that Adam typed it in the HUD.
- The Gateway does know which paired device sent a turn: it names that device as the card's
  reviewer (`ApprovalReviewerDeviceId`, ADR 0007, source read). Whether OpenClaw 2026.10.9 passes
  that device id to plugin hooks (`before_agent_run`, `before_tool_call`) is **unknown**. Nothing in
  the plugin docs says it does.

## Options

| | What | Gains | Costs and risks |
|---|---|---|---|
| A | Keep it as now | Nothing new to trust | Cards on every guarded HUD action, even in a clean chat |
| B | Clean when the turn comes from the HUD's own paired device id, pinned in the guard's config | HUD typing works like Telegram: memory saves in Adam's words, `project_start`, `supply_save` and small records need no card in a clean chat | Needs a device id the Gateway sets and the model can't, in the hook context. A stolen HUD device token (Mac login Keychain) then acts as Adam typing. Anyone at Adam's unlocked Mac can type as him, as they could in Telegram on that Mac |
| C | B, but only for the small classes (`memoryWrite` in Adam's words, `localWrite`) | Most of the friction gone | Spawns, schedules, pushes and `confirmAlways` keep their cards from the HUD; two rules to explain |

A stolen device token is about as strong as a stolen Telegram session on the same Mac. The
difference is that Telegram also checks the sender id on its own servers, while the HUD's token is
checked only by the Gateway. Revoking it is `openclaw --profile jorah devices revoke` (ADR 0007).

## Recommendation

C, if and only if a spike shows the Gateway hands plugin hooks the sending device's id for
`chat.send` turns, and that a Chat Completions caller or the Control UI can't produce the HUD's id.
Without that signal, A stays: the guard must not trust a channel name a caller can choose.

## What deciding needs

1. A spike on a scratch Gateway (never the live one): log the hook contexts of a HUD `chat.send`
   turn, a Control UI turn and a Chat Completions call with `x-openclaw-message-channel: webchat`.
   Record which fields differ and whether any is set only by the Gateway.
2. Adam's yes to an option, in writing, here.
3. If C: the HUD's device id pinned in `jorah-guard`'s config (not the permission matrix), a test
   that a forged channel or a different device stays tainted, and a re-check after every OpenClaw
   upgrade (the field could move).

## Related

ADR 0005 (native HUD), ADR 0007 (HUD answers cards), ADR 0010 (voice confirms cards, being built
in its own session on `feat/voice-confirm`).
