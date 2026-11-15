#!/usr/bin/env bash
# Installs jorah-phone on live Jorah (docs/runbooks/phone.md, docs/contracts/jorah-phone-v1.md). Run
# as root, in a Terminal attached to no agent, after /opt/jorah holds the reviewed commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-phone.sh service --dry-run
# Stages, each on its own yes:
#   service     Ask Jorah (step A): folders, the firewall line for 43212, the unit, started with
#               phone events and health off. Nothing in OpenClaw changes. The phone's token and
#               the Tailscale Serve route are separate steps (runbook).
#   plugin      Phone events (step B), only after the P5 gate passes: phone events on, a read token
#               for the plugin (written to a file, never shown), the jorah-phone plugin, phone_today
#               on main's tool list, a Gateway restart. Health stays off.
#   health-on   Adam's decision H is the daily upload: the service takes health uploads and the
#               plugin passes health fields to Jorah. health-off turns just that off again.
#   undo        Stops the service, removes the plugin, restores the config from before the plugin
#               stage. Folders, tokens, /etc/jorah/phone.env and the firewall line stay.
# Add --dry-run after a stage to check it and see what it would do; nothing is written.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
SRC=/opt/jorah
ENVF=/etc/jorah/phone.env
READ_TOKEN=/home/jorah/.config/jorah-phone/read-token
TOKEN_TOOL=(runuser -u jorah -- /usr/bin/python3 -I "$SRC/services/jorah-phone/bin/jorah-phone-token")
STAGE="${1:-}"
DRY="${2:-}"
case "$STAGE" in service|plugin|health-on|health-off|undo) ;; *) sed -n 2,19p "$0"; exit 2 ;; esac
[ -z "$DRY" ] || [ "$DRY" = --dry-run ] || { echo "Unknown option $DRY"; exit 2; }

restart_gateway() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

healthz() {
  for _ in $(seq 1 10); do
    /usr/bin/python3 -I -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:43212/healthz", timeout=3).read().decode())' 2>/dev/null && return 0
    sleep 1
  done
  echo "jorah-phone doesn't answer on 127.0.0.1:43212: journalctl -u jorah-phone -n 30"; return 1
}

need_files() {
  local f
  for f in "$@"; do
    [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the reviewed commit to $SRC first."; exit 1; }
    [ "$(stat -c %U "$SRC/$f")" = root ] || { echo "$SRC/$f isn't root-owned."; exit 1; }
  done
}

# Current switch values, so changing one keeps the other.
switch() {
  local v=""
  [ -f "$ENVF" ] && v=$(sed -n "s/^$1=\(on\|off\)\$/\1/p" "$ENVF" | tail -1)
  echo "${v:-off}"
}
set_switches() {
  install -d -o root -g root -m 755 /etc/jorah
  printf 'JORAH_PHONE_INGEST=%s\nJORAH_PHONE_HEALTH=%s\n' "$1" "$2" > "$ENVF"
  chown root:root "$ENVF"; chmod 644 "$ENVF"
  echo "switches: phone events $1, health $2 ($ENVF)"
}

plugin_installed() { "${OC[@]}" plugins list 2>/dev/null | grep -q 'jorah-phone'; }

if [ "$STAGE" = undo ]; then
  [ "$DRY" = --dry-run ] && { echo "Would stop and disable jorah-phone, uninstall the jorah-phone plugin and restore $CFG.pre-phone if it exists."; exit 0; }
  systemctl disable --now jorah-phone 2>/dev/null || true
  plugin_installed && "${OC[@]}" plugins uninstall jorah-phone --force --keep-files || true
  if [ -f "$CFG.pre-phone" ]; then
    cp "$CFG.pre-phone" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"
    restart_gateway
    echo "Config restored from $CFG.pre-phone."
  fi
  echo "jorah-phone off. Folders, tokens, $ENVF and the firewall line stay. The Serve route is removed from the Mac:"
  echo "  ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \"tailscale serve --https=43213 off\""
  exit 0
fi

need_files services/jorah-phone/bin/jorah-phone services/jorah-phone/bin/jorah-phone-token \
  services/jorah-phone/jorah_phone/server.py services/jorah-phone/jorah_phone/ask.py services/jorah-phone/jorah_phone/store.py \
  services/jorah-phone/jorah_phone/schema.py services/jorah-phone/jorah_phone/tokens.py services/jorah-phone/jorah_phone/compute.py \
  packages/contracts/phone/today.schema.json deploy/jorah-phone.service deploy/jorah-firewall.nft

if [ "$STAGE" = service ]; then
  /usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "/usr/bin/python3 is older than 3.10"; exit 1; }
  [ -f /home/jorah/.config/jorah-voice/gateway-token ] || { echo "The Gateway token file jorah-voice uses is missing; jorah-phone reads the same one."; exit 1; }
  if [ "$DRY" = --dry-run ]; then
    nft -c -f "$SRC/deploy/jorah-firewall.nft" && echo "firewall file: valid (nft -c)"
    diff <(grep -v '^\s*#' /etc/nftables.conf) <(grep -v '^\s*#' "$SRC/deploy/jorah-firewall.nft") || true
    echo "Would create ~/.config/jorah-phone and ~/.local/share/jorah-phone (mode 700, jorah), load the firewall above"
    echo "(keeping /etc/nftables.conf.pre-phone), write $ENVF (phone events off, health off) unless it exists,"
    echo "install and start jorah-phone.service on 127.0.0.1:43212. Nothing in OpenClaw changes. Dry run only: nothing written."
    exit 0
  fi
  runuser -u jorah -- mkdir -p -m 700 /home/jorah/.config/jorah-phone /home/jorah/.local/share/jorah-phone
  chmod 700 /home/jorah/.config/jorah-phone /home/jorah/.local/share/jorah-phone
  [ -f /etc/nftables.conf.pre-phone ] || cp -p /etc/nftables.conf /etc/nftables.conf.pre-phone
  cp "$SRC/deploy/jorah-firewall.nft" /etc/nftables.conf
  systemctl restart nftables
  echo "firewall: jorah may reach 127.0.0.1:43212 ($(nft list chain inet jorah_out output | grep -c 43212) rule); undo: cp /etc/nftables.conf.pre-phone /etc/nftables.conf && systemctl restart nftables"
  [ -f "$ENVF" ] || set_switches off off
  install -m 644 "$SRC/deploy/jorah-phone.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now jorah-phone
  systemctl restart jorah-phone
  healthz
  journalctl -u jorah-phone -n 3 --no-pager | tail -1
  echo "Done. Next (runbook \"Ask Jorah\"): the phone's token, made by Adam, then the Serve route on :43213."
  exit 0
fi

systemctl is-active --quiet jorah-phone || { echo "jorah-phone isn't running: run the service stage first."; exit 1; }

if [ "$STAGE" = health-on ] || [ "$STAGE" = health-off ]; then
  want=${STAGE#health-}
  flag=$([ "$want" = on ] && echo true || echo false)
  if [ "$DRY" = --dry-run ]; then
    echo "Would set health $want in $ENVF (phone events stay $(switch JORAH_PHONE_INGEST)), restart jorah-phone,"
    plugin_installed && echo "and set plugins.entries.jorah-phone.config.includeHealth to $flag, then restart the Gateway." \
      || echo "and leave OpenClaw alone (the plugin isn't installed)."
    exit 0
  fi
  set_switches "$(switch JORAH_PHONE_INGEST)" "$want"
  systemctl restart jorah-phone
  healthz
  if plugin_installed; then
    TMP=$(mktemp -d /tmp/phone.XXXXXX); trap 'rm -rf "$TMP"' EXIT; chmod 755 "$TMP"
    printf '{ plugins: { entries: { "jorah-phone": { config: { includeHealth: %s } } } } }\n' "$flag" > "$TMP/health.json5"
    chmod 644 "$TMP/health.json5"
    "${OC[@]}" config patch --file "$TMP/health.json5"
    restart_gateway
  fi
  echo "Health $want."
  exit 0
fi

# plugin stage
need_files plugins/jorah-phone/index.js plugins/jorah-phone/openclaw.plugin.json plugins/jorah-phone/lib/schema.js config/pc/phone.patch.json5
TMP=$(mktemp -d /tmp/phone.XXXXXX); trap 'rm -rf "$TMP"' EXIT
chmod 755 "$TMP"
LIST=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow 2>/dev/null || echo null)
ALLOW=$("${OC[@]}" config get plugins.allow 2>/dev/null || echo null)
python3 -I - "$LIST" "$ALLOW" "$TMP" <<'P'
import json, sys
lst, allow, out = json.loads(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3]
if not isinstance(lst, list) or not lst:
    sys.exit("main's tool list (tools.sandbox.tools.alsoAllow) isn't a list; stopping")
if not isinstance(allow, list) or not allow:
    sys.exit("plugins.allow isn't a list; stopping")
if "phone_today" not in lst:
    lst.append("phone_today")
if "jorah-phone" not in allow:
    allow.append("jorah-phone")
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(f"{out}/main-tools.json5", "w"))
json.dump({"plugins": {"allow": allow}}, open(f"{out}/allow.json5", "w"))
P
chmod 644 "$TMP"/*.json5

if [ "$DRY" = --dry-run ]; then
  "${OC[@]}" config patch --file "$TMP/allow.json5" --dry-run
  "${OC[@]}" config patch --file "$TMP/main-tools.json5" --dry-run
  "${OC[@]}" config patch --file "$SRC/config/pc/phone.patch.json5" --dry-run
  echo "Would turn phone events on in $ENVF (health stays $(switch JORAH_PHONE_HEALTH)), make the plugin's read token in"
  echo "$READ_TOKEN unless it exists (never shown), link plugins/jorah-phone, apply the three patches above and restart the Gateway."
  echo "Main's tools would be: $(python3 -I -c 'import json,sys; print(", ".join(json.load(open(sys.argv[1]))["agents"]["entries"]["main"]["tools"]["sandbox"]["tools"]["alsoAllow"]))' "$TMP/main-tools.json5")"
  echo "Dry run only: nothing written."
  exit 0
fi

[ -f "$CFG.pre-phone" ] || cp -p "$CFG" "$CFG.pre-phone"
[ -f "$READ_TOKEN" ] || "${TOKEN_TOOL[@]}" new gateway --scopes read --to-file "$READ_TOKEN" --replace
set_switches on "$(switch JORAH_PHONE_HEALTH)"
systemctl restart jorah-phone
healthz
"${OC[@]}" plugins install --link "$SRC/plugins/jorah-phone" --force --accept-capabilities
"${OC[@]}" config patch --file "$TMP/allow.json5"
"${OC[@]}" config patch --file "$TMP/main-tools.json5"
"${OC[@]}" config patch --file "$SRC/config/pc/phone.patch.json5"
restart_gateway
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
# /today with the plugin's token, as the Gateway would ask: the status lines only.
runuser -u jorah -- /usr/bin/python3 -I - "$READ_TOKEN" <<'P'
import json, sys, urllib.request
token = open(sys.argv[1]).read().strip()
request = urllib.request.Request("http://127.0.0.1:43212/today", headers={"Authorization": f"Bearer {token}"})
body = json.load(urllib.request.urlopen(request, timeout=5))
print(f"/today answers: phone {body['phone']['status']}, health {body['health']['status']}")
P
echo "Done. Config backup: $CFG.pre-phone. Undo: the same command with undo."
