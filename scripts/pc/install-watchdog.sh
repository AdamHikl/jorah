#!/usr/bin/env bash
# Installs the watchdog that tells Adam on Telegram when the Gateway or the project runner is down
# (services/jorah-watchdog/watchdog.py; Adam's yes, 2026-11-18). Run as root after /opt/jorah holds
# the reviewed commit:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-watchdog.sh --dry-run"
#
#   (no option)  Makes the system user jorah-watchdog and /etc/jorah-watchdog, writes watchdog.conf (the
#                chat id from channels.telegram.allowFrom and the Gateway's port; neither is printed),
#                installs the service and the timer and enables the timer. Without the bot token it
#                watches and logs but can't send: Adam stores the token with store-watchdog-token.sh.
#   --dry-run    Checks everything and prints what it would do. Writes nothing.
#   --test       Sends one test message through the bot.
#   --undo       Stops and removes the units. Keeps the user, /etc/jorah-watchdog and the token.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-install}"
case "$MODE" in install|--dry-run|--test|--undo) ;; *) sed -n 2,14p "$0"; exit 2 ;; esac
SRC=/opt/jorah
ETC=/etc/jorah-watchdog
UNITS=(jorah-watchdog.service jorah-watchdog.timer)
PY=(/usr/bin/python3 -I "$SRC/services/jorah-watchdog/watchdog.py")
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)

if [ "$MODE" = --undo ]; then
  systemctl disable --now jorah-watchdog.timer 2>/dev/null || true
  for u in "${UNITS[@]}"; do rm -f "/etc/systemd/system/$u"; done
  systemctl daemon-reload
  echo "Removed the watchdog's units. Kept: the user jorah-watchdog, $ETC and the token."
  exit 0
fi

if [ "$MODE" = --test ]; then
  exec runuser -u jorah-watchdog -- "${PY[@]}" test
fi

fail=0
for f in services/jorah-watchdog/watchdog.py "${UNITS[@]/#/deploy/}"; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done
chat="$(cd /tmp && "${OC[@]}" config get channels.telegram.allowFrom --json 2>/dev/null | /usr/bin/python3 -I -c '
import json, sys
v = json.load(sys.stdin)
print(v[0] if isinstance(v, list) and len(v) == 1 else "")' 2>/dev/null || true)"
[[ "$chat" =~ ^[0-9]+$ ]] || { echo "Expected exactly one numeric channels.telegram.allowFrom entry."; fail=1; }
port="$(cd /tmp && "${OC[@]}" config get gateway.port 2>/dev/null | tail -1 || true)"
[[ "$port" =~ ^[0-9]+$ ]] || { echo "Couldn't read gateway.port."; fail=1; }
[ "$fail" = 0 ] || exit 1
token=no; [ -s "$ETC/telegram.token" ] && token=yes

if [ "$MODE" = --dry-run ]; then
  id jorah-watchdog >/dev/null 2>&1 && echo "user jorah-watchdog exists" || echo "would: make the system user jorah-watchdog"
  echo "would: write $ETC/watchdog.conf (chat id from allowFrom, Gateway port $port), root:jorah-watchdog 640"
  echo "would: install ${UNITS[*]} and enable jorah-watchdog.timer (every 5 minutes)"
  echo "bot token stored: $token"
  exit 0
fi

id jorah-watchdog >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent \
  --shell /usr/sbin/nologin jorah-watchdog
install -d -m 750 -o root -g jorah-watchdog "$ETC"
umask 027
printf '{"chat_id": "%s", "gateway_port": %s}\n' "$chat" "$port" > "$ETC/watchdog.conf.new"
chown root:jorah-watchdog "$ETC/watchdog.conf.new"
chmod 640 "$ETC/watchdog.conf.new"
mv "$ETC/watchdog.conf.new" "$ETC/watchdog.conf"
for u in "${UNITS[@]}"; do install -m 644 -o root -g root "$SRC/deploy/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now jorah-watchdog.timer
systemctl start jorah-watchdog.service || true
sync
journalctl -u jorah-watchdog.service -n 3 --no-pager -o cat
echo "bot token stored: $token"
[ "$token" = yes ] || echo "Next: Adam stores the token with store-watchdog-token.sh, sends /start to the bot, then: install-watchdog.sh --test"
