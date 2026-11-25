# deep as an extension of main: PC deploy, 2026-11-25

Adam: "deep should act as an extension of main, so I want it to be able to access the same files
and have the same permissions", "just make it so that the main agent can elevate the issue to opus
and he then tries to solve it", "build it", then "Apply and restart". Commits `5dad85c` (the change)
and `9f2d73e` (the drift check may record `DEEP.md`).

| Step | Result |
|---|---|
| Preflight | `deploy_reviewed.py baseline`: 0 drift, 0 unrecorded; not frozen. Live deep: workspace `/home/jorah/workspace-deep`, 8-tool `tools.allow`, 16-entry deny, codeMode false, sandbox off, no `bootstrapMaxChars` (main: 40000) |
| Backups | `openclaw.json.pre-deep-extension`; `/root/opt-jorah-pre-deep-extension-2026-11-25.tgz` (guard and matrix, 23 entries); `/home/jorah/workspace/AGENTS.md.pre-deep-extension` (34,784 bytes) |
| Dry run | `config/pc/deep-consult.patch.json5` at `5dad85c`: `Dry run successful: 4 update(s)` |
| Files | `deploy plugins/jorah-guard config/permission-matrix.json`: 20 files deployed and recorded; `deploy services/jorah-watchdog/drift.py`: 1 file; `workspace/AGENTS.md` (35,479 bytes) and `workspace/DEEP.md` (4,974 bytes) copied, `record-live` 2 files from `9f2d73e`. The first `record-live` was refused ("not a path the manifest may hold: DEEP.md") and recorded nothing, hence `9f2d73e` |
| Apply | `config unset agents.entries.deep.tools.allow`: removed; patch: `Applied 4 config update(s)`. `config get`: workspace `/home/jorah/workspace`, `bootstrapMaxChars` 40000, `tools.allow` unset, deny `image_generate, video_generate, music_generate, message, exec, process, sessions_spawn, sessions_send, sessions_yield, subagents`, codeMode false, sandbox off |
| Restart | recycle finished 12:54:32 CET, `Deactivated successfully`; `jorah-guard: matrix loaded; state ok` at 12:54:19 |
| Checks | event loop ok; jorah-guard and jorah-projects enabled; deployed `policy.js` and matrix have `extensionAgents`; `sandbox explain --agent deep`: mode off, host workspace `/home/jorah/workspace`; audit `0 critical · 5 warn · 2 info` (same as before) |

Undo: copy `openclaw.json.pre-deep-extension` back (owner `jorah`, mode 600), restore the `.tgz`
into `/opt/jorah` and `AGENTS.md.pre-deep-extension`, remove `/home/jorah/workspace/DEEP.md`,
recycle the Gateway, then `deploy_reviewed.py baseline --write`.

Tiers: source, tests, PC deploy and Gateway restart. Open: Adam's acceptance in a fresh `/new`
(runbook `docs/runbooks/project-notes.md`, "deep as an extension of main"), including whether a
card raised in deep's session reaches Adam (if not, it times out and the write is denied).
