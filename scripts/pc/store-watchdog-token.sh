#!/usr/bin/env bash
# Adam runs this to store the watchdog bot's token. Use a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/store-watchdog-token.sh"
# It reads the token without showing it, checks its shape, stores it for the user jorah-watchdog only
# (root:jorah-watchdog, mode 640), and asks Telegram which bot it belongs to. It prints the bot's
# name, never the token. Needs install-watchdog.sh to have run first.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
ETC=/etc/jorah-watchdog
id jorah-watchdog >/dev/null 2>&1 && [ -d "$ETC" ] || { echo "Run install-watchdog.sh first."; exit 4; }
read -rsp "Paste the bot token from BotFather (it won't show): " token; echo
[[ "$token" =~ ^[0-9]{5,}:[A-Za-z0-9_-]{30,}$ ]] || { echo "That doesn't look like a bot token. Nothing saved."; exit 5; }
umask 027
printf '%s\n' "$token" > "$ETC/telegram.token.new"
unset token
chown root:jorah-watchdog "$ETC/telegram.token.new"
chmod 640 "$ETC/telegram.token.new"
mv "$ETC/telegram.token.new" "$ETC/telegram.token"
sync
echo "  saved: $ETC/telegram.token (root:jorah-watchdog, mode 640)"
/usr/bin/python3 -I - "$ETC/telegram.token" <<'PY'
import json, sys, urllib.request, urllib.error
token = open(sys.argv[1]).read().strip()
try:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=20) as r:
        me = json.load(r)["result"]
    print(f"  Telegram says this is @{me.get('username')} ({me.get('first_name')}).")
    print("  Now open that bot in Telegram and send it /start, so it may message you.")
except urllib.error.HTTPError as e:
    print(f"  Telegram refused the token (HTTP {e.code}). Check it and run this again.")
except (OSError, ValueError, KeyError) as e:
    print(f"  Couldn't ask Telegram ({type(e).__name__}). The token is saved; try --test later.")
PY
