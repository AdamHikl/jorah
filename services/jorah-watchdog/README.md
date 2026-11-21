# jorah-watchdog

Tells Adam on Telegram when Jorah's Gateway, the project runner or the Gateway's cron scheduler is
down. Jorah's own messages go
through the Gateway, so a down Gateway can't report itself. This sends with its own bot, straight to
Telegram's Bot API: the "rescue bot" of `docs/plan/02-architecture.md`, on the PC for now.

What it does, every 5 minutes (`deploy/jorah-watchdog.timer`, as the system user `jorah-watchdog`):

| Check | Down means | Alert after |
|---|---|---|
| Gateway | the unit isn't active, or `/readyz` on loopback doesn't say ready | 10 minutes |
| Project runner | its timer isn't active, or its last tick ended other than `success` (the runner exits non-zero only when it is broken itself, not when a project run fails) | 20 minutes |
| Cron (`cronwatch.py`, root, read-only, `jorah-cron-watch.service`, run just before each check) | the Gateway's journal since its current start has "[cron] failed to start", "Cron maintenance failed" or "Cron receipt authority is unavailable" and no heartbeat finished after it; or no heartbeat receipt for 2.5 hours while the Gateway has been up longer. A missing, stale (15 min) or unreadable report counts as down; "pending" (Gateway stopped, or up less than 2.5 hours) keeps what it had | 10 minutes |

- **Alerts:** one alert per outage, a reminder every 6 hours while it lasts, and "Back: …" when it's over.
- **Unreadable checks:** a check it can't read counts as down.
- **Gaps:** if no check ran for 30 minutes (the PC or WSL was off or asleep), it says so at the next check. While the PC is off nothing can be sent; that needs a watcher off the PC.
- **Retries:** a message that fails to send is retried at the next check.
- **Restarts:** the 6-hourly restart (`jorah-gateway-recycle`) takes under a minute, so it never alerts. The cron check says "pending" across it, so a cron alert neither repeats nor clears with a restart.

**Nightly, 03:40** (`deploy/jorah-daily-watch.timer`, `watchdog.py daily`; installed by
`scripts/pc/install-daily-watch.sh`):

| Check | Tells Adam | Unknown after |
|---|---|---|
| Advisory watch (`advisories.py`, as `jorah-watchdog`) | each OpenClaw advisory, from the repository's own list, whose `openclaw` or `@openclaw/*` range covers what is installed: id, severity, summary, fixed versions, link. Once per advisory | a day without a good read of the list or the installed version |
| Drift check (`drift.py`, root, no network, `jorah-drift.service`) | reviewed files changed, missing, or new in `/opt/jorah`, against the manifest of the last deploy from main. Once per distinct finding, and when it clears | a day without a fresh report |

"Unknown" is said once, never as "no advisories" or "no drift". The manifest is kept by
`scripts/pc/deploy_reviewed.py`, which every build session uses to deploy (see the runbook, "Advisory
watch, drift check and install policy").

**Setup** (`scripts/pc/install-watchdog.sh`, then Adam):
1. In Telegram, @BotFather → `/newbot`, any name, for example "Jorah watchdog". Keep the token to paste.
2. In a Terminal attached to no agent: `scripts/pc/store-watchdog-token.sh` (see its header). It prints the bot's name, never the token.
3. Send `/start` to the new bot.
4. `install-watchdog.sh --test` sends a test message.

**Where things are:**
- the token: `/etc/jorah-watchdog/telegram.token` (root:jorah-watchdog 640);
- the chat id and the Gateway port: `/etc/jorah-watchdog/watchdog.conf`;
- the state: `/var/lib/jorah-watchdog/state.json` and `daily.json`, readable with `watchdog.py status`;
- the cron watch's report: `/var/lib/jorah-cron-watch/report.json` (`cronwatch.py show`); installed by `scripts/pc/install-cron-watch.sh`;
- the manifest and the drift report: `/var/lib/jorah-drift/` (root-owned; `drift.py show`);
- the log: `journalctl -u jorah-watchdog -u jorah-cron-watch -u jorah-daily-watch -u jorah-drift`.

The token never appears in a log or the state.
