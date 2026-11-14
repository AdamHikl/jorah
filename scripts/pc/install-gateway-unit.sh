#!/usr/bin/env bash
# Installs deploy/openclaw-gateway.service from /opt/jorah over the live unit. Run as root, in a
# Terminal attached to no agent, after /opt/jorah holds the reviewed commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-gateway-unit.sh
# It reloads systemd but doesn't restart the Gateway: the change applies at the next start.
#   --dry-run  Shows the diff and checks the new unit. Writes nothing.
#   --undo     Restores the unit from before and reloads systemd.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
SRC=/opt/jorah/deploy/openclaw-gateway.service
DST=/etc/systemd/system/openclaw-gateway.service
BAK=$DST.pre-podman-warmup

if [ "${1:-}" = "--undo" ]; then
  [ -f "$BAK" ] || { echo "No backup at $BAK."; exit 1; }
  cp "$BAK" "$DST"; chmod 644 "$DST"
  systemctl daemon-reload
  echo "Unit restored from $BAK. It applies at the next Gateway start."
  exit 0
fi

[ -f "$SRC" ] || { echo "Missing $SRC: copy the reviewed commit to /opt/jorah first."; exit 1; }
[ "$(stat -c %U "$SRC")" = root ] || { echo "$SRC isn't root-owned."; exit 1; }

diff -u "$DST" "$SRC" && { echo "Live unit already matches $SRC."; exit 0; } || true
# systemd-analyze wants the unit's own name, so check a copy in a temp folder.
TMPD=$(mktemp -d); trap 'rm -rf "$TMPD"' EXIT
cp "$SRC" "$TMPD/openclaw-gateway.service"
systemd-analyze verify "$TMPD/openclaw-gateway.service"
echo "Unit check passed."
[ "${1:-}" = "--dry-run" ] && { echo "Dry run: nothing written."; exit 0; }

[ -f "$BAK" ] || cp "$DST" "$BAK"
cp "$SRC" "$DST"; chmod 644 "$DST"
systemctl daemon-reload
echo "Installed. Backup: $BAK. The Gateway keeps running; the change applies at its next start."
systemctl show -p ExecStartPre openclaw-gateway | cut -c1-200
