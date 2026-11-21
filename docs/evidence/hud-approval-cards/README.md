# HUD approval cards (ADR 0007)

Evidence for the Mac HUD answering Jorah's plugin approval cards. 2026-11-21, OpenClaw 2026.10.9.

## The failure that started it (live, 08:13)

Adam typed "yes" in the HUD to install uv (toolbox proposal `tb-cf6866267c`). The Gateway logged `plugin approval gateway request failed; blocking tool call: GatewayClientRequestError: missing scope: operator.approvals`, and Jorah got "Plugin approval required (gateway unavailable)". The HUD device held `operator.read` and `operator.write`. Cause, from source: a turn's `plugin.approval.request` keeps only the scopes of the client that started the turn (ADR 0007).

## Tiers

| Tier | State |
|---|---|
| Source | Card panel, live scope upgrade, `plugin-approvals` capability, ADR 0007 |
| Unit tests | `swift test --package-path clients/mac-hud`: 10 passed (parsing, plain text, offered decisions, 1.5 s hold, expiry) |
| Scratch Gateway, protocol | `scripts/pc/hud-approvals-scratch.sh`, output in `scratch-run-2026-11-21.txt`. T1 to T5 passed. A Node probe that signs in like the HUD, not the Swift app itself |
| Layout | `demo-card.png`: `JORAH_HUD_DEMO=1`, made-up card, buttons off |
| Install | `just mac-hud-install` on Adam's Mac, 2026-11-21 11:27, relaunched |
| Live scope grant | Adam clicked "Ask for card access"; request `8fbfc9e6` checked in `devices list` ("Jorah HUD" from the Mac's Tailscale address, asking for approvals, read, write) and approved at Adam's request in chat. `devices list` then showed the HUD with `operator.read, operator.write, operator.approvals` |
| Adam's uv test | Open |

## Scratch results

| Test | Result |
|---|---|
| T1 read+write device lists cards | Refused: `missing scope: operator.approvals` |
| T2a reconnect with old device token asking for +approvals | Refused: `AUTH_SCOPE_MISMATCH`, no pending request filed |
| T2b `device.scopes.requestUpgrade` on the live link | Pending repair request for read, write, approvals; nothing widened while pending; after approval `waitUpgrade` returned `approved` and a new device token; reconnect has `operator.approvals` |
| T3 card delivery | Needs the `plugin-approvals` capability as well as the scope; without it every card closed at once as "no approval route" |
| T3 answers | `allow-always` on an `allow-once`/`deny` card refused; `allow-once` accepted |
| T4 first answer wins | Second answer: "approval already resolved". After another connection answered first, the HUD's answer was refused and the HUD got `plugin.approval.resolved` with the card's id |
| T5 list shape | Rows `{ approvalKind, createdAtMs, expiresAtMs, id, request }`; the Gateway turns U+202E into a visible `\u{202E}` before the HUD sees it; Markdown stays literal |

Not covered on scratch: a real guarded turn (needs a model) and which Telegram or voice cards a non-admin HUD sees. The CLI's `gateway call` uses least-privilege scopes, so it could not see cards other devices asked for.

The scratch profile turns `gateway.nodes.pairing.autoApproveLocal` off, because OpenClaw otherwise approves loopback pairings and scope upgrades silently, which the HUD (through Tailscale Serve) never gets. On the first run, before that, the probe's pairing was approved with no request.
