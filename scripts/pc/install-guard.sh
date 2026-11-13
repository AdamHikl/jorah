#!/usr/bin/env bash
# P5.5: installs plugins/jorah-guard on live Jorah, enforcing. Run as root, in a Terminal attached
# to no agent, after /opt/jorah holds the reviewed commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-guard.sh
# Links the plugin from root-owned /opt/jorah, adds it to the live plugins.allow (as it is now),
# applies config/pc/guard.patch.json5, restarts the Gateway and shows what loaded.
#   --dry-run  Validates the change against the live config and writes nothing.
#   --undo     Removes the plugin and restores the config from before. The decision log stays.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
STATE=/home/jorah/.jorah-guard
LOG=/home/jorah/.openclaw-jorah/logs

restart() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "${1:-}" = "--undo" ]; then
  "${OC[@]}" plugins uninstall jorah-guard --force --keep-files || true
  cp "$CFG.pre-guard" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"
  restart
  echo "Guard removed; config restored from $CFG.pre-guard. Its log stays in $STATE."
  exit 0
fi

for f in /opt/jorah/plugins/jorah-guard/index.js /opt/jorah/config/permission-matrix.json /opt/jorah/config/pc/guard.patch.json5; do
  [ -f "$f" ] || { echo "Missing $f: copy the reviewed commit to /opt/jorah first."; exit 1; }
  [ "$(stat -c %U "$f")" = root ] || { echo "$f isn't root-owned."; exit 1; }
done

# plugins.allow as it is now, plus jorah-guard: a JSON5 patch in a root-only temp file.
ALLOW=$("${OC[@]}" config get plugins.allow 2>/dev/null)
TMP=$(mktemp /tmp/guard-allow.XXXXXX.json5); trap 'rm -f "$TMP"' EXIT
python3 - "$ALLOW" "$TMP" <<'P'
import json, sys
allow = json.loads(sys.argv[1])
if not isinstance(allow, list) or not allow:
    sys.exit("plugins.allow isn't a list; stopping")
if "jorah-guard" not in allow:
    allow.append("jorah-guard")
open(sys.argv[2], "w").write(json.dumps({"plugins": {"allow": allow}}))
P
chmod 644 "$TMP"

if [ "${1:-}" = "--dry-run" ]; then
  "${OC[@]}" config patch --file "$TMP" --dry-run
  "${OC[@]}" config patch --file /opt/jorah/config/pc/guard.patch.json5 --dry-run
  echo "Dry run only: nothing written. plugins.allow would be: $(python3 -c 'import json,sys; print(", ".join(json.load(open(sys.argv[1]))["plugins"]["allow"]))' "$TMP")"
  exit 0
fi

[ -f "$CFG.pre-guard" ] || cp -p "$CFG" "$CFG.pre-guard"
install -d -o jorah -g jorah -m 700 "$STATE"
"${OC[@]}" plugins install --link /opt/jorah/plugins/jorah-guard --force --accept-capabilities
"${OC[@]}" config patch --file "$TMP"
"${OC[@]}" config patch --file /opt/jorah/config/pc/guard.patch.json5
restart
journalctl -u openclaw-gateway --since "-3 min" --no-pager 2>/dev/null | grep -o "jorah-guard: .*" | tail -1 || true
grep -rho "jorah-guard: [^\"]*" "$LOG" 2>/dev/null | tail -1 || true
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. Config backup: $CFG.pre-guard. Decision log: $STATE/decisions.jsonl. Undo: the same command with --undo."
