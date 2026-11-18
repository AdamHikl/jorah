# jorah-watchdog

Tells Adam on Telegram when Jorah's Gateway or the project runner is down. Jorah's own messages go
through the Gateway, so a down Gateway can't report itself. This sends with its own bot, straight to
Telegram's Bot API: the "rescue bot" of `docs/plan/02-architecture.md`, on the PC for now.

What it does, every 5 minutes (`deploy/jorah-watchdog.timer`, as the system user `jorah-watchdog`):

| Check | Down means | Alert after |
|---|---|---|
| Gateway | the unit isn't active, or `/readyz` on loopback doesn't say ready | 10 minutes |
| Project runner | its timer isn't active, or its last tick ended other than `success` (the runner exits non-zero only when it is broken itself, not when a project run fails) | 20 minutes |

- **Alerts:** one alert per outage, a reminder every 6 hours while it lasts, and "Back: …" when it's over.
- **Unreadable checks:** a check it can't read counts as down.
- **Gaps:** if no check ran for 30 minutes (the PC or WSL was off or asleep), it says so at the next check. While the PC is off nothing can be sent; that needs a watcher off the PC.
- **Retries:** a message that fails to send is retried at the next check.
- **Restarts:** the 6-hourly restart (`jorah-gateway-recycle`) takes under a minute, so it never alerts.

**Setup** (`scripts/pc/install-watchdog.sh`, then Adam):
1. In Telegram, @BotFather → `/newbot`, any name, for example "Jorah watchdog". Keep the token to paste.
2. In a Terminal attached to no agent: `scripts/pc/store-watchdog-token.sh` (see its header). It prints the bot's name, never the token.
3. Send `/start` to the new bot.
4. `install-watchdog.sh --test` sends a test message.

**Where things are:**
- the token: `/etc/jorah-watchdog/telegram.token` (root:jorah-watchdog 640);
- the chat id and the Gateway port: `/etc/jorah-watchdog/watchdog.conf`;
- the state: `/var/lib/jorah-watchdog/state.json`, readable with `watchdog.py status`;
- the log: `journalctl -u jorah-watchdog`.

The token never appears in a log or the state.
