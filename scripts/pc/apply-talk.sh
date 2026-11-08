#!/usr/bin/env bash
# Applies the 2026-11-08 build to live Jorah. Adam runs it as root, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/apply-talk.sh
#
# 1. Firewall: Jorah reaches the public internet on web ports only (deploy/jorah-firewall.nft).
# 2. Talk: links plugins/jorah-voice-provider (declares one realtime voice provider, jorah-local),
#    accepts that, and applies config/pc/talk.patch.json5 (9 updates, dry run passed 2026-11-08).
# 3. Hook probe for roadmap step 2.1, test only: links plugins/jorah-hook-probe.
# Then restarts the Gateway once and shows what loaded.
#
#   --remove-hook-probe   After the test: unlinks the probe and puts the plugin list back.
#   --undo                Talk off and the probe gone: plugin list as before, talk.realtime unset.
#                         The firewall stays; the old file is in git history.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }

OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json

restart_gateway() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 30); do
    "${OC[@]}" health >/dev/null 2>&1 && break
    sleep 2
  done
  "${OC[@]}" health 2>&1 | tail -3
}

case "${1:-}" in
  --remove-hook-probe)
    "${OC[@]}" plugins uninstall jorah-hook-probe --force --keep-files
    "${OC[@]}" config patch --file /opt/jorah/config/pc/talk.patch.json5
    restart_gateway
    "${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
    exit 0
    ;;
  --undo)
    "${OC[@]}" plugins uninstall jorah-hook-probe --force --keep-files || true
    "${OC[@]}" plugins uninstall jorah-voice-provider --force --keep-files || true
    cp "$CFG.pre-talk" "$CFG"
    chown jorah:jorah "$CFG"; chmod 600 "$CFG"
    restart_gateway
    exit 0
    ;;
  "") ;;
  *) echo "Unknown option: $1"; exit 2 ;;
esac

echo "== 1. Firewall"
cp /opt/jorah/deploy/jorah-firewall.nft /etc/nftables.conf
nft -f /etc/nftables.conf
runuser -u jorah -- curl -s -o /dev/null -w "  https to Telegram: %{http_code} (any number means it got through)\n" --max-time 8 https://api.telegram.org/ || echo "  https to Telegram: FAILED"
if runuser -u jorah -- timeout 6 bash -c 'echo > /dev/tcp/smtp.gmail.com/587' 2>/dev/null; then
  echo "  mail port 587: OPEN, which is wrong"
else
  echo "  mail port 587: refused, as intended"
fi

echo "== 2. Talk plugin and config"
[ -f "$CFG.pre-talk" ] || cp -p "$CFG" "$CFG.pre-talk"
"${OC[@]}" plugins install --link /opt/jorah/plugins/jorah-voice-provider --force --accept-capabilities
"${OC[@]}" config patch --file /opt/jorah/config/pc/talk.patch.json5

echo "== 3. Hook probe (test only)"
"${OC[@]}" plugins install --link /opt/jorah/plugins/jorah-hook-probe --force --accept-capabilities
"${OC[@]}" config patch --file /opt/jorah/config/pc/hook-probe.patch.json5

echo "== Restart"
restart_gateway
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || echo "  jorah plugins: not listed"
echo "  talk.realtime.provider: $("${OC[@]}" config get talk.realtime.provider 2>/dev/null || echo unset)"
"${OC[@]}" security audit 2>&1 | grep -iE "critical|warn" | head -3 || true
echo "Done. Backup of the config before this run: $CFG.pre-talk"
