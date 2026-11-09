#!/usr/bin/env bash
# Installs plugins/jorah-github on live Jorah. Adam runs it as root, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-github.sh
# Links the plugin from root-owned /opt/jorah (declares tools github_push_branch, github_open_pr),
# applies config/pc/github.patch.json5, restarts the Gateway and shows what loaded.
#   --undo   Removes the plugin and restores the config from before.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json

restart() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 30); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "${1:-}" = "--undo" ]; then
  "${OC[@]}" plugins uninstall jorah-github --force --keep-files || true
  cp "$CFG.pre-github" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"
  restart; exit 0
fi

[ -f /home/jorah/.config/jorah-github/app.pem ] || echo "Note: the App's key isn't on the PC yet (scripts/github/move-app-key.sh)."
[ -f "$CFG.pre-github" ] || cp -p "$CFG" "$CFG.pre-github"
"${OC[@]}" plugins install --link /opt/jorah/plugins/jorah-github --force --accept-capabilities
"${OC[@]}" config patch --file /opt/jorah/config/pc/github.patch.json5
restart
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. Config backup: $CFG.pre-github. Undo: the same command with --undo."
