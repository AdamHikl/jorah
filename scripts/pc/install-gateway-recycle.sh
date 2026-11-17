#!/usr/bin/env bash
# Installs the 6-hourly Gateway restart (Adam's choice of 2026-11-17; see scripts/pc/gateway-recycle.sh).
# Run as root after /opt/jorah holds the reviewed commit:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-gateway-recycle.sh --dry-run"
#
#   (no option)  Checks the files, installs the service and the timer, enables the timer.
#   --dry-run    Checks the files, runs the restart script's own dry run, writes nothing.
#   --undo       Stops and disables the timer and removes both units.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-install}"
case "$MODE" in install|--dry-run|--undo) ;; *) sed -n 2,8p "$0"; exit 2 ;; esac
SRC=/opt/jorah
UNITS=(jorah-gateway-recycle.service jorah-gateway-recycle.timer)

if [ "$MODE" = --undo ]; then
  systemctl disable --now jorah-gateway-recycle.timer 2>/dev/null || true
  for u in "${UNITS[@]}"; do rm -f "/etc/systemd/system/$u"; done
  systemctl daemon-reload
  echo "Removed the Gateway restart timer. The leak returns to about 290 MB an hour."
  exit 0
fi

fail=0
for f in scripts/pc/gateway-recycle.sh "${UNITS[@]/#/deploy/}"; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done
[ -x "$SRC/scripts/pc/gateway-recycle.sh" ] || { echo "NOT EXECUTABLE: $SRC/scripts/pc/gateway-recycle.sh"; fail=1; }
command -v ss >/dev/null || { echo "MISSING: ss"; fail=1; }
command -v curl >/dev/null || { echo "MISSING: curl"; fail=1; }
[ "$fail" = 0 ] || exit 1

if [ "$MODE" = --dry-run ]; then
  "$SRC/scripts/pc/gateway-recycle.sh" --dry-run
  echo "would install ${UNITS[*]} and enable jorah-gateway-recycle.timer (02:20, 08:20, 14:20, 20:20)"
  exit 0
fi

for u in "${UNITS[@]}"; do install -m 644 -o root -g root "$SRC/deploy/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now jorah-gateway-recycle.timer
sync
systemctl list-timers jorah-gateway-recycle.timer --no-pager | head -3
