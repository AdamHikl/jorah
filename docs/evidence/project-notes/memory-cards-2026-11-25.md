# Fewer memory cards: PC deploy, 2026-11-25

Adam, about a HUD card "Jorah wants to save to memory": "can't we make a system that decides",
then "Build both fixes" ("Both fixes + check HUD"), then "Deploy and restart". Commit `0789012`.

| Step | Result |
|---|---|
| Preflight | `deploy_reviewed.py baseline`: 0 drift, 0 unrecorded |
| Backup | `/root/opt-jorah-pre-memory-cards-2026-11-25.tgz` (guard `index.js`, `lib/policy.js`, `lib/state.js`) |
| Files | `deploy plugins/jorah-guard/index.js plugins/jorah-guard/lib/policy.js plugins/jorah-guard/lib/state.js`: 3 deployed and recorded from `0789012` |
| Restart | recycle started 18:50:52 CET, idle on try 1, `Deactivated successfully` 18:50:55; `jorah-guard: matrix loaded; state ok` 18:51:06; HTTP server listening 18:51:09 |
| Checks | event loop ok; jorah-guard and jorah-projects enabled; deployed `policy.js` has `ownChatWords`, `state.js` has `taintedChildOf` |

What changed: a deep job asked from Adam's clean chat leaves main's chat clean until deep itself
reads outside text; a memory write that restates Adam's own typed messages in this session saves
without a card (`ownChatWords`). Neither applies to the HUD, which the guard still can't tell
from Siri.

HUD check, read only: HUD typing (WebSocket `chat.send`) and Siri (`/v1/chat/completions` from
jorah-phone) both reach the guard as `webchat` with no sender id and no account id (OpenClaw
2026.11.6 code; no stored turn in main's current session has a sender). Main's stored turns show
HUD-typed turns with input provenance `external_user` (23) and spoken turns with none (12 of 12);
9 unspoken turns also had none, source not established. Prompt hooks get it as
`ctx.inputProvenance`. Not used: trusting it needs Adam's yes and a logging pass first.

Undo: restore the `.tgz` into `/opt/jorah`, recycle the Gateway, then
`deploy_reviewed.py baseline --write`.

Tiers: source, tests, PC deploy and Gateway restart. Open: Adam's acceptance in Telegram.
