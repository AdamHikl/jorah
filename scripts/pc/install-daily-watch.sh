#!/usr/bin/env bash
# Installs the nightly advisory watch and drift check (services/jorah-watchdog/advisories.py and
# drift.py), sent through the watchdog's own bot. Needs install-watchdog.sh done first (user, conf,
# token). Run as root after /opt/jorah holds the reviewed commit:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-daily-watch.sh --dry-run"
#
#   --dry-run   Checks files and units, checks that `openclaw --version` (as jorah, from /) agrees
#               with the package.json the watch reads, runs the drift check into a scratch report,
#               then the daily run with --dry-run as jorah-watchdog (it reads GitHub's list and
#               prints what it would send). Sends nothing, installs nothing.
#   (no option) Installs jorah-drift.service, jorah-daily-watch.service and .timer (03:40 nightly)
#               and enables the timer. Doesn't run it: --run does.
#   --run       Runs it once now: drift check, then the daily run, which sends what is due.
#   --undo      Stops and removes the three units. Keeps the state and the manifest.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-install}"
case "$MODE" in install|--dry-run|--run|--undo) ;; *) sed -n 2,17p "$0"; exit 2 ;; esac
SRC=/opt/jorah
UNITS=(jorah-drift.service jorah-daily-watch.service jorah-daily-watch.timer)
WD=(/usr/bin/python3 -I "$SRC/services/jorah-watchdog/watchdog.py")
DRIFT=(/usr/bin/python3 -I "$SRC/services/jorah-watchdog/drift.py")

if [ "$MODE" = --undo ]; then
  systemctl disable --now jorah-daily-watch.timer 2>/dev/null || true
  for u in "${UNITS[@]}"; do rm -f "/etc/systemd/system/$u"; done
  systemctl daemon-reload
  echo "Removed the daily watch units. Kept /var/lib/jorah-drift and /var/lib/jorah-watchdog/daily.json."
  exit 0
fi

if [ "$MODE" = --run ]; then
  systemctl start jorah-daily-watch.service || true
  journalctl -u jorah-drift.service -u jorah-daily-watch.service --since -10min --no-pager -o cat | tail -15
  exit 0
fi

fail=0
for f in services/jorah-watchdog/watchdog.py services/jorah-watchdog/advisories.py services/jorah-watchdog/drift.py \
         "${UNITS[@]/#/deploy/}"; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done
id jorah-watchdog >/dev/null 2>&1 || { echo "No user jorah-watchdog: run install-watchdog.sh first."; fail=1; }
[ -f /etc/jorah-watchdog/watchdog.conf ] || { echo "No /etc/jorah-watchdog/watchdog.conf: run install-watchdog.sh first."; fail=1; }
[ "$fail" = 0 ] || exit 1

cli="$(cd / && runuser -u jorah -- /usr/local/bin/openclaw --version 2>/dev/null | awk '{print $2}')"
pkg="$(/usr/bin/python3 -I -c 'import json;print(json.load(open("/opt/node/lib/node_modules/openclaw/package.json"))["version"])')"
echo "openclaw --version: $cli; package.json the watch reads: $pkg"
[ -n "$cli" ] && [ "$cli" = "$pkg" ] || { echo "They differ: the watch would check the wrong version. Stopping."; exit 1; }

if [ "$MODE" = --dry-run ]; then
  T=$(mktemp -d)
  trap 'rm -rf "$T"' EXIT
  chmod 755 "$T"
  cp "${UNITS[@]/#/$SRC/deploy/}" "$T/"
  systemd-analyze verify "${UNITS[@]/#/$T/}" 2>&1 | grep -v -i "is not a valid path\|unit file was not found" || echo "units verify clean"
  if [ -f /var/lib/jorah-drift/manifest.json ]; then
    "${DRIFT[@]}" check --report "$T/report.json"
  else
    echo "No manifest yet: the drift check would report 'unknown' until deploy_reviewed.py baseline --write."
  fi
  install -d -m 700 -o jorah-watchdog "$T/wd"
  [ -f "$T/report.json" ] && install -m 644 "$T/report.json" "$T/wd/report.json"
  runuser -u jorah-watchdog -- "${WD[@]}" daily --dry-run --daily-state "$T/wd/daily.json" --drift-report "$T/wd/report.json"
  echo "would: install ${UNITS[*]} and enable jorah-daily-watch.timer (03:40 nightly)"
  exit 0
fi

for u in "${UNITS[@]}"; do install -m 644 -o root -g root "$SRC/deploy/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now jorah-daily-watch.timer
sync
systemctl list-timers jorah-daily-watch.timer --no-pager | head -3
echo "Installed. Run it once now with --run."
