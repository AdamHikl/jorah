# ADR 0007: the Mac HUD answers Jorah's approval cards

**Decision:** the Mac HUD (`clients/mac-hud/`) may hold `operator.approvals` and answer plugin approval cards with Allow once or Deny. Adam asked for it on 2026-11-21: "I want to be able to fully use jorah without telegram, so make a UI in the jorah hud for confirming cards", and said yes to this plan in the build session the same day.

This replaces one row of ADR 0005 (the HUD "does not ask for `operator.approvals`"). The rest of ADR 0005 stands.

## Why the HUD needs the scope even to ask

On 2026-11-21 at 08:13 Adam typed "yes" in the HUD to install uv. The guard's `confirmAlways` card for `toolbox_install` never appeared anywhere: the Gateway logged `missing scope: operator.approvals` and Jorah was told "Plugin approval required (gateway unavailable)".

OpenClaw 2026.10.9 sends a tool call's `plugin.approval.request` with the authority of the client that started the turn. `resolveInProcessGatewaySyntheticScopes` (`dist/server-plugin-in-process-dispatch-*.mjs`) keeps only the scopes that client holds, and the HUD held `operator.read` and `operator.write` [verified: source read, not run]. Telegram and voice turns run with full scopes, so their cards worked. Without `operator.approvals`, any guarded tool started from the HUD fails, so the HUD cannot be used on its own.

## What the HUD does with the scope

| Rule | How |
|---|---|
| Is a route for cards | The HUD advertises the `plugin-approvals` client capability. The Gateway sends a plugin card only to clients with both that capability and `operator.approvals` (`canDeliverApprovals`). A card with no route is closed at once as "no approval route" (scratch T3) |
| Shows only what the Gateway lists | `plugin.approval.list` after linking, on `plugin.approval.requested` and `.resolved` events, and every 15 seconds. The list is the truth. A failed list shows "cards unknown", never "none" |
| Plain text only | Title, description and every field the request carries, drawn with `Text(verbatim:)`. Control and format characters (bidi overrides, zero-width) are removed, long values clipped (`HUDCore/Approvals.swift`, unit tested) |
| Allow once and Deny only | `allow-always` is never offered or sent, even when a card allows it. The Gateway also refuses any decision the card did not offer |
| Only a deliberate click | The only caller of `plugin.approval.resolve` is the card's button action. No keyboard shortcut, not the default button, not focusable, disabled for 1.5 seconds after a card appears and after it expires. Voice, chat text and anything Jorah writes have no path to it |
| Time left | A countdown from the card's `expiresAtMs`. An expired card can't be answered and drops off at the next list |
| Telegram unchanged | `approvals.plugin` still forwards every main card to Telegram. The first answer anywhere wins (the Gateway's rule), and the other surface drops the card on `plugin.approval.resolved` |
| Fails closed, visibly | Not linked: "cards unknown, answer in Telegram". Linked without the scope: "this HUD can't answer cards" and an "Ask for card access" button |

## Which cards the HUD sees

Without `operator.admin`, the Gateway shows a client only cards it requested or that name it as reviewer (`isApprovalRecordVisibleToClient`). Only the agent runtime can name a reviewer (`bindApprovalReviewerDeviceIds`), and a chat turn names the device that sent it (`ApprovalReviewerDeviceId` = the client's device id, `gateway-client-identity-*.mjs`) [verified: source read]. So the HUD sees the cards of turns started from the HUD. Whether it also sees cards from Telegram or voice turns is unknown until the live test: Telegram keeps getting all of them either way.

## How the scope is granted

Adam's yes on the PC, as for any pairing change. "Ask for card access" in the HUD calls `device.scopes.requestUpgrade` over the live link with the current scopes plus `operator.approvals`. The Gateway files a pending request, shown in `openclaw --profile jorah devices list` as a repair of "Jorah HUD", and nothing widens before Adam runs `openclaw --profile jorah devices approve <requestId>` himself. `device.scopes.waitUpgrade` then hands the waiting HUD a new device token, which it keeps in the Keychain and reconnects with (scratch T2b).

A reconnect that just asks for broader scopes with the old device token does not work: the Gateway refuses it with `AUTH_SCOPE_MISMATCH` and files nothing (scratch T2a). A fresh pairing has a third choice in the sheet, "answer approval cards".

## What it adds, and the limits

| Risk | Limit |
|---|---|
| A stolen HUD device token can approve cards the HUD can see | It lives in the Mac's login Keychain. Revoke with `openclaw --profile jorah devices revoke`. The Mac's Control UI and the iPhone already hold this scope with admin |
| HUD-started turns now carry `operator.approvals` | The `gateway` and `openclaw` tools stay denied to every agent (`config/pc/deny-openclaw.patch.json5`), so no agent tool can call `plugin.approval.resolve`. The requesting connection is never a route for its own card, but on the scratch Gateway a second connection of the same device could answer it (T4), so the deny list is what keeps Jorah from answering. Not yet tested with a live turn |
| Loopback clients get scope upgrades silently by default | OpenClaw approves pairings and scope upgrades from loopback without asking (`gateway.nodes.pairing.autoApproveLocal`, unset on `jorah`, so on). The HUD comes in through Tailscale Serve, which does not get this. A process on the PC that can reach loopback can already read the Gateway token, so this adds nothing for the HUD, but the scratch test turns it off |
| Voice approving (gate 9) | Unchanged: voice runs through `jorah-voice`, never this button |
| RISK-T3 | Still not phone-only until SEC-T20. The HUD is a Mac app on Adam's unlocked Mac, which `03` 5.x allows for RISK-T3 |

## Tests

Unit: `swift test --package-path clients/mac-hud` (parsing, plain text, offered decisions, hold, expiry).

Scratch Gateway (`jorah-hud-test` profile, loopback, channels and cron off, local auto-approval off), `scripts/pc/hud-approvals-scratch.sh`, results in `docs/evidence/hud-approval-cards/`:

1. T1: a paired device with only read and write is refused `plugin.approval.list` (`missing scope: operator.approvals`). Passed.
2. T2a: the same device reconnecting with its device token and `+operator.approvals` is refused (`AUTH_SCOPE_MISMATCH`). T2b: `device.scopes.requestUpgrade` files a pending repair request, nothing widens while it waits, approval returns a new token through `waitUpgrade`, and the reconnect has `operator.approvals`. Passed.
3. T3: with the capability, a card is delivered and listed; `allow-always` on an `allow-once`/`deny` card is refused; `allow-once` resolves it. Passed.
4. T4: a second answer gets "approval already resolved"; when another connection answers first, the HUD's answer is refused and the HUD gets `plugin.approval.resolved` naming the card. Passed.
5. T5: list rows are `{ approvalKind, createdAtMs, expiresAtMs, id, request }`, which `HUDCore` parses. The Gateway already writes control characters such as U+202E as visible escapes. Passed.

Not covered on scratch: a real guarded turn (needs a model), and cards from Telegram or voice turns. The live test covers the first.

Live, Adam, 2026-11-21: passed. Two `toolbox_install` cards were allowed in the HUD and installed: uv 0.13.8 (`tb-9f96fe897d`, 13:44) and ripgrep (`tb-da7bd38a1b`, 13:57). Cards from Telegram or voice turns in the HUD are still untested (`docs/evidence/hud-approval-cards/`).

## Re-check

Before the HUD is shared or published, and if OpenClaw changes how turn authority reaches `plugin.approval.request`.
