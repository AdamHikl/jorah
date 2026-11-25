# deep looks at pictures: PC deploy, 2026-11-25

Adam's yes: "Yes, add it" (deep may use `view_image`), then "Apply and restart". Commit `f56592f`.

| Step | Result |
|---|---|
| Preflight | `deploy_reviewed.py baseline`: 0 drift, 0 unrecorded; runner `inactive`; not frozen |
| Files | `deploy plugins/jorah-guard config/permission-matrix.json`: 20 files deployed and recorded; `workspace/AGENTS.md` (34,784 bytes) and `workspace-deep/AGENTS.md` (4,471 bytes) copied and `record-live`d |
| Backup | `openclaw.json.pre-deep-pics` (copy with mode and owner kept) |
| Dry run | live `agents.entries.deep.tools.allow` had 7 tools; with `view_image`, 8; `Dry run successful: 1 update(s)` |
| Apply | `Applied 1 config update(s)`; `config get` shows the 8 tools ending in `view_image` |
| Restart | recycle started 11:45:16 CET, `Deactivated successfully`; Gateway started 11:45:20; `jorah-guard: matrix loaded; state ok` at 11:45:28 |
| Checks | event loop ok; jorah-guard and jorah-projects enabled, no consent warning; deployed `policy.js` has `consultPictureProblem`; audit `0 critical · 5 warn · 2 info` (same as before) |

Undo: copy `openclaw.json.pre-deep-pics` back (owner `jorah`, mode 600), deploy the previous
`plugins/jorah-guard`, matrix and both `AGENTS.md` files from `a857099`, recycle the Gateway.

Tiers: source, tests, PC deploy and Gateway restart. Open: Adam's acceptance in a fresh `/new`
(runbook `docs/runbooks/project-notes.md`, "deep looks at pictures").
