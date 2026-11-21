#!/usr/bin/env bash
# Installs the cron watch (services/jorah-watchdog/cronwatch.py): before each watchdog run, every 5
# minutes, a read-only check of whether the live Gateway's cron scheduler still runs jobs; the
# watchdog tells Adam when it doesn't. Needs install-watchdog.sh done first (user, conf, token). Run
# as root after /opt/jorah holds the reviewed commit:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-cron-watch.sh --dry-run"
#
#   --dry-run   Checks files and units, shows how the watchdog's unit changes, runs the check once in
#               a throwaway unit with the service's own sandbox (it prints the report and writes
#               nothing), then the watchdog's check with --dry-run on that report. Sends nothing,
#               installs nothing.
#   (no option) Installs jorah-cron-watch.service and the new jorah-watchdog.service, which pulls the
#               check in before each run, then runs the check once. Doesn't restart the Gateway.
#   --run       Runs the check once now and prints the report.
#   --undo      Removes jorah-cron-watch.service, so the watchdog stops watching cron. Keeps the
#               report; the watchdog's unit keeps a Wants= that systemd ignores while the unit is gone.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-install}"
case "$MODE" in install|--dry-run|--run|--undo) ;; *) sed -n 2,18p "$0"; exit 2 ;; esac
SRC=/opt/jorah
UNITS=(jorah-cron-watch.service jorah-watchdog.service)
CW=(/usr/bin/python3 -I "$SRC/services/jorah-watchdog/cronwatch.py")
WD=(/usr/bin/python3 -I "$SRC/services/jorah-watchdog/watchdog.py")

if [ "$MODE" = --undo ]; then
  rm -f /etc/systemd/system/jorah-cron-watch.service
  systemctl daemon-reload
  echo "Removed jorah-cron-watch.service. Kept /var/lib/jorah-cron-watch."
  exit 0
fi

if [ "$MODE" = --run ]; then
  systemctl start jorah-cron-watch.service || true
  journalctl -u jorah-cron-watch.service --since -10min --no-pager -o cat | tail -5
  "${CW[@]}" show
  exit 0
fi

fail=0
for f in services/jorah-watchdog/cronwatch.py services/jorah-watchdog/watchdog.py "${UNITS[@]/#/deploy/}"; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done
id jorah-watchdog >/dev/null 2>&1 || { echo "No user jorah-watchdog: run install-watchdog.sh first."; fail=1; }
[ -f /etc/jorah-watchdog/watchdog.conf ] || { echo "No /etc/jorah-watchdog/watchdog.conf: run install-watchdog.sh first."; fail=1; }
[ "$fail" = 0 ] || exit 1

if [ "$MODE" = --dry-run ]; then
  T=$(mktemp -d)
  trap 'rm -rf "$T"' EXIT
  chmod 755 "$T"
  cp "${UNITS[@]/#/$SRC/deploy/}" "$T/"
  systemd-analyze verify "${UNITS[@]/#/$T/}" 2>&1 | grep -v -i "is not a valid path\|unit file was not found" || echo "units verify clean"
  echo "--- how jorah-watchdog.service changes:"
  diff -u /etc/systemd/system/jorah-watchdog.service "$SRC/deploy/jorah-watchdog.service" || true
  # The service's own sandbox, from its unit file, for one run that prints the report.
  mapfile -t PROPS < <(sed -n '/^\[Service\]/,$p' "$SRC/deploy/jorah-cron-watch.service" \
    | grep -E '^(UMask|PrivateNetwork|CapabilityBoundingSet|NoNewPrivileges|ProtectSystem|ProtectHome|PrivateTmp|PrivateDevices|InaccessiblePaths|RestrictAddressFamilies|SystemCallFilter)=' \
    | sed 's/^/--property=/')
  echo "--- the check, in a throwaway unit with ${#PROPS[@]} sandbox settings:"
  systemd-run --quiet --pipe --wait --collect "${PROPS[@]}" "${CW[@]}" check --report - > "$T/cron.json"
  cat "$T/cron.json"
  install -d -m 700 -o jorah-watchdog "$T/wd"
  install -m 644 "$T/cron.json" "$T/wd/cron.json"
  echo "--- the watchdog's check on that report, as jorah-watchdog, dry run:"
  runuser -u jorah-watchdog -- "${WD[@]}" check --dry-run --cron-report "$T/wd/cron.json"
  echo "would: install ${UNITS[*]} (the watchdog's timer stays as it is: every 5 minutes)"
  exit 0
fi

for u in "${UNITS[@]}"; do install -m 644 -o root -g root "$SRC/deploy/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl start jorah-cron-watch.service || true
sync
journalctl -u jorah-cron-watch.service -n 3 --no-pager -o cat
echo "Installed. The next watchdog run (every 5 minutes) checks cron first; --run shows the report."
