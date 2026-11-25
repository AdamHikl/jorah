# Autonomy charter steps 2 and 3: PC deploy, 2026-11-25

Adam: "if everything is build, then yes, deloy it", answering "Deploy the guard and rules text to
the PC and restart the Gateway?". Commit `1f8d161` (`docs/plan/13-autonomy.md` §8 steps 2 and 3).

| Step | Result |
|---|---|
| Preflight | live `permission-matrix.json`, guard `index.js`, `lib/policy.js`, `lib/state.js`, `openclaw.plugin.json`, `test/proactive.test.js` and workspace `AGENTS.md`, `SOUL.md` matched `f109e2a` (sha256). Live `test/guard.test.js` was from `5dad85c` (a later test-only change had not been deployed). `jorah-proactive` is not in `/opt/jorah` (not installed), so its `index.js` change was not deployed |
| Backup | `/root/opt-jorah-pre-autonomy-2026-11-25.tgz` (7 files, mode 600); `/home/jorah/workspace/AGENTS.md.pre-autonomy`, `SOUL.md.pre-autonomy` |
| Files | `deploy_reviewed.py deploy` of the matrix and 8 guard files (`lib/today.js` and `test/autonomy.test.js` new): 9 deployed and recorded from `1f8d161` |
| Rules | `workspace/AGENTS.md` and `SOUL.md` copied live (sha256 `b941186d…`, `ed542d57…` match `HEAD`); `record-live` recorded 2 files |
| Restart | `jorah-gateway-recycle.service` 21:18:07 CET, idle on try 1, ready after 20 s; HTTP server listening with 16 plugins; `jorah-guard: matrix loaded; state ok` |
| Checks | `plugins inspect jorah-guard`: loaded, commands `jorah-freeze`, `jorah-status`, `jorah-careful`, `jorah-today`. The deployed `summarizeDay` run on the live `decisions.jsonl` printed today's counts (5 file writes and 4 jobs done alone, 98 reads, 4 cards, 0 blocks). No `CAREFUL` file, so careful mode is off. Only error since the restart: `models.list unavailable during gateway startup` at 21:18:26, a client asking before the Gateway was ready |

Undo: as root, `tar -xzf /root/opt-jorah-pre-autonomy-2026-11-25.tgz -C /opt/jorah && rm
/opt/jorah/plugins/jorah-guard/lib/today.js /opt/jorah/plugins/jorah-guard/test/autonomy.test.js &&
sync`; copy the two `.pre-autonomy` files over the live ones; `systemctl start
jorah-gateway-recycle.service`; then `deploy_reviewed.py baseline --write`.

Tiers: source, tests (`just check`; guard 172/172), PC deploy and Gateway restart. Open: Adam's
signed-in test in Telegram (`/jorah-careful`, `/jorah-status`, a card in careful mode, an
`AGENTS.md` edit card, `/jorah-today`). The open-loop path waits for the `jorah-proactive` install.
