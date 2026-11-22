# ADR 0010: Adam confirms approval cards by voice, and each card goes where he asked

**Status:** decided by Adam on 2026-11-22, being built. Nothing in it is deployed.

**Decision:** `jorah-voice` checks the speaker on the PC (plan 12, section 3) and may answer a pending approval card when Adam's voice says yes. A card shows only on the surface Adam asked from. Adam asked for it on 2026-11-22: "make it that the confirm cards can be confirmed through voice saying yes or confirm or similar", and "if I ask it through hud, go only to hud, if through voice, go to hud and by voice, if telegram then only telegram, if the openclaw ios app then only there".

## Adam's decisions, 2026-11-22

| # | Decision | Changes |
|---|---|---|
| D1 | Build the speaker check for confirmations and card routing now. Guest mode (plan 12, decisions V1 to V5) later | Plan 12, section 13: only the VI-A half, without guest routing. Until guest mode exists, an unknown voice is treated as today for talking, and can never confirm |
| D2 | **A permanent spoken phrase or PIN, set up in the HUD, replaces the 4-digit code per card** for actions that leave the PC (pushes, pull requests, recurring or web-fetching schedules). Adam: "a pincode or phrase that stays permanent, so that I can use it fully handsfree" | Replaces the code rule in `p5-plan.md` 4.3 (2026-11-11). Accepted weakness: anyone who hears or records Adam saying it once has his voice and the phrase. Kept limits: a confirmation answers one card, only within 20 s of Jorah asking, and the phrase never reaches the model, the transcript or a log |
| D3 | A short or unsure "yes" gets a natural request to say it again, in varied wording, never a robotic "say it a bit longer" | `p5-plan.md` 4.3 and plan 12 3.6: the confirming answer must be at least 1.5 s of speech and score as Adam |
| D4 | The OpenClaw iOS app keeps its admin pairing, so it can still list every pending card | Accepted |
| D5 | Antigravity (Gemini 4 Hydrogen High) writes the code, Claude reviews it. Deploys, downloads and PC changes stay with Claude and wait for Adam's yes | `antigravity-delegate`: Adam's explicit say-so for the security parts |

## How a voice confirmation works

1. A guarded tool in a voice turn raises a card. The guard writes the question; the model doesn't word it.
2. `jorah-voice` sees the card is from its own voice turn, shows it on the HUD over the voice connection, and speaks the guard's question.
3. Adam answers within 20 s. The turn is handled on the PC and is never sent to the Gateway:
   - "no", "cancel", "don't": the card is denied;
   - "yes, go ahead", "yes, confirm" and similar: allowed only if the speaker check scores **Adam** on at least 1.5 s of speech, and, when the card leaves the PC, the turn also contains Adam's phrase;
   - anything else, unsure, or too short: a natural "say it again", and after two tries "tap it in the HUD instead".
4. Three wrong phrases in a row turn voice confirmation off until Adam answers a card by tap.
5. A tap on the HUD card always works, and the first answer anywhere wins (the Gateway's rule).

## The phrase

- Set, changed or removed in the HUD (it goes to the PC over the voice connection, which runs over Tailscale with the voice token).
- Stored on the PC only as a salted, slow hash (scrypt) of its normalised words, in `jorah-voice`'s private folder, mode 600. Parakeet's transcript is normalised the same way and compared with the hash.
- Never spoken by Jorah, never shown back, never logged, never sent to the Gateway.

## Routing

See "Card routes" (filled in after the source research and the scratch test). Target:

| Asked from | Card shows |
|---|---|
| HUD typing (`webchat`, the HUD's device) | HUD only |
| Voice (`voice`) | HUD and spoken |
| Telegram | Telegram only |
| OpenClaw iOS app | The app (which, as admin, also lists the others: D4) |

## The voice service's Gateway connection holds admin (Adam's yes, 2026-11-22)

A card raised in a Chat Completions turn, which is how every spoken turn reaches the Gateway, is visible only to `operator.admin` connections (`isApprovalRecordVisibleToClient`; measured on live at 13:42:36: `Plugin approval unavailable (no approval route)` with the HUD and an approvals-only connection online). So `jorah-voice`'s approvals connection asks for `operator.admin` as well. The shared Gateway token it already holds allows admin, so no secret gains power; the connection sees every pending card, and `session.py` acts only on cards from its own voice turn (same session key, a `webchat` or `voice` turn source, created while that turn ran). It never sends `allow-always`.

## Re-check

When guest mode is built, when OpenClaw changes approval routing, and after the first month of use: how often a confirmation was refused, and whether any unknown voice ever confirmed.
