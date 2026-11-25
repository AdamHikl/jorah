# Task results after a restart, and expired cards: PC deploy, 2026-11-25

Adam, after Jorah's A-0001 filing failed with "there's no recent attachment in this chat" and then
"Plugin approval unavailable (no approval route)": "Yes, build both", then "Deploy and restart".
Commit `b3a58a0`.

Causes, read only: the 18:50 Gateway restart emptied jorah-projects' in-memory attachment tracker,
so `project_task_result` with `files: "last"` found nothing; card 45 (`operator_approvals`) then
expired unanswered after 5 minutes, and OpenClaw 2026.11.6 words an in-process timeout
(decision `null`) as "no approval route".

| Step | Result |
|---|---|
| Preflight | live `index.js`, `lib/media.js`, `lib/pictures.js` and workspace `AGENTS.md` matched `b3a58a0~1` byte for byte (sha256) |
| Backup | `/root/opt-jorah-pre-task-result-last-2026-11-25.tgz` (the three plugin files); `/home/jorah/workspace/AGENTS.md.pre-task-result-last` |
| Files | `deploy plugins/jorah-projects/index.js plugins/jorah-projects/lib/media.js plugins/jorah-projects/lib/pictures.js`: 3 deployed and recorded from `b3a58a0` |
| Rules | `workspace/AGENTS.md` copied live (sha256 matches `HEAD`), `record-live` recorded 1 file |
| Restart | recycle 20:25:14 CET, idle on try 1, Gateway active 20:25:20, ready after 20 s; HTTP server listening with 16 plugins; `jorah-guard: matrix loaded; state ok` |
| Checks | health: event loop ok, agents main, background, deep; jorah-projects `loadFailedCount=0`, `registerFailedCount=0`; deployed `index.js` has `RESULT_INBOUND_MS`; live `AGENTS.md` has "A card nobody answered" |

Not new: health's delivery-queue warning (1 dead-lettered entry, 3 days old) was there before.

What changed: `project_task_result` with `files: "last"` falls back to the newest photos in the
inbound media folders from the last 24 hours when the tracker is empty after a restart, or when
those photos are newer than the tracked attachment; the usual root, type and size checks still
apply. AGENTS.md tells Jorah that this failure after the 5-minute wait means the card expired
unanswered, not a missing route.

Undo: restore the `.tgz` into `/opt/jorah` and `AGENTS.md.pre-task-result-last` over the live
`AGENTS.md`, recycle the Gateway, then `deploy_reviewed.py baseline --write`.

Tiers: source, tests (70/70), PC deploy and Gateway restart. Open: Adam's acceptance in the HUD.
