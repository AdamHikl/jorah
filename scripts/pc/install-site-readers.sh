#!/usr/bin/env bash
# Installs the site readers on live Jorah (docs/runbooks/site-readers.md). Run as root, in a Terminal
# attached to no agent, after /opt/jorah holds the reviewed commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-site-readers.sh --dry-run
# What it does, in order:
#   1. users jorah-sites (uid 1101, the site browsers) and jorah-proxy (uid 1102, the site proxy);
#   2. /etc/jorah/sites.private.json (root-owned; empty, so no site is set up yet);
#   3. the firewall with the two users' rules (deploy/jorah-firewall.nft);
#   4. jorah-site-proxy.service, and the jorah-site-browser@.service template (started per site by site.sh);
#   5. the reader-site agent, its stored-key profile, the jorah-sites plugin, site_read and sites_list
#      on main's live tool list, and config/pc/site-reader.patch.json5; then a Gateway restart.
# Adding a site afterwards: site.sh set-host / add / signin (no rerun of this script).
#   --dry-run  checks files and validates the config changes against the live config; writes nothing.
#   --undo     stops the site browsers and the proxy, removes the plugin, restores the config from
#              before. Users, firewall rules and signed-in profiles stay (site.sh remove --wipe clears one).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
SRC=/opt/jorah
WS=/home/jorah/workspace-site-reader
MODE="${1:-}"

restart() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "$MODE" = --undo ]; then
  for u in $(systemctl list-units --plain --no-legend 'jorah-site-browser@*' | awk '{print $1}'); do systemctl disable --now "$u" || true; done
  systemctl disable --now jorah-site-proxy || true
  "${OC[@]}" plugins uninstall jorah-sites --force --keep-files || true
  [ -f "$CFG.pre-sites" ] && { cp "$CFG.pre-sites" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"; }
  restart
  echo "Site readers off; config restored from $CFG.pre-sites. Users, firewall rules and /var/lib/jorah-sites stay."
  exit 0
fi

for f in plugins/jorah-sites/index.js plugins/jorah-guard/lib/sites.js config/sites/edupage.json config/pc/site-reader.patch.json5 \
         config/pc/site-reader-key.plan.json services/jorah-site-proxy/proxy.mjs scripts/pc/site-browser.sh scripts/pc/site.sh \
         deploy/jorah-site-proxy.service deploy/jorah-site-browser@.service deploy/jorah-firewall.nft workspace-site-reader/AGENTS.md; do
  [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the reviewed commit to $SRC first."; exit 1; }
  [ "$(stat -c %U "$SRC/$f")" = root ] || { echo "$SRC/$f isn't root-owned."; exit 1; }
done
command -v node >/dev/null || { echo "node is missing"; exit 1; }
[ -x /usr/bin/google-chrome-stable ] || { echo "Chrome is missing at /usr/bin/google-chrome-stable"; exit 1; }

# A user must be either absent or exactly the expected id.
check_user() {
  local name=$1 uid=$2 have
  if have=$(id -u "$name" 2>/dev/null); then
    [ "$have" = "$uid" ] || { echo "$name exists with uid $have, not $uid: stopping."; exit 1; }
  elif getent passwd "$uid" >/dev/null; then
    echo "uid $uid is taken by $(getent passwd "$uid" | cut -d: -f1): stopping."; exit 1
  fi
}
check_user jorah-sites 1101
check_user jorah-proxy 1102

# main's live tool list plus site_read and sites_list, as a JSON5 patch in a root-only temp file.
TMP=$(mktemp -d /tmp/site-readers.XXXXXX); trap 'rm -rf "$TMP"' EXIT
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
for t in ("site_read", "sites_list"):
    if t not in lst:
        lst.append(t)
if "jorah-sites" not in allow:
    allow.append("jorah-sites")
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(f"{out}/main-tools.json5", "w"))
json.dump({"plugins": {"allow": allow}}, open(f"{out}/allow.json5", "w"))
P
chmod 644 "$TMP"/*.json5

if [ "$MODE" = --dry-run ]; then
  "${OC[@]}" config patch --file "$TMP/allow.json5" --dry-run
  "${OC[@]}" config patch --file "$TMP/main-tools.json5" --dry-run
  "${OC[@]}" config patch --file "$SRC/config/pc/site-reader.patch.json5" --dry-run
  "${OC[@]}" agents list 2>&1 | grep -q reader-site && echo "reader-site exists already." || echo "Would add the agent reader-site (workspace $WS)."
  echo "Would create users jorah-sites (1101) and jorah-proxy (1102) unless present, /etc/jorah/sites.private.json if missing,"
  echo "copy deploy/jorah-firewall.nft to /etc/nftables.conf and reload it, install and start jorah-site-proxy.service,"
  echo "install jorah-site-browser@.service, link plugins/jorah-sites, apply the three patches above and restart the Gateway."
  echo "Main's tools would be: $(python3 -I -c 'import json,sys; print(", ".join(json.load(open(sys.argv[1]))["agents"]["entries"]["main"]["tools"]["sandbox"]["tools"]["alsoAllow"]))' "$TMP/main-tools.json5")"
  echo "Dry run only: nothing written."
  exit 0
fi

[ -f "$CFG.pre-sites" ] || cp -p "$CFG" "$CFG.pre-sites"

# 1. Users, no login, no home.
id jorah-sites >/dev/null 2>&1 || useradd --system --uid 1101 --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin jorah-sites
id jorah-proxy >/dev/null 2>&1 || useradd --system --uid 1102 --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin jorah-proxy

# 2. The private file: root-owned, readable by the guard (jorah), the proxy and the browsers.
install -d -o root -g root -m 755 /etc/jorah
[ -f /etc/jorah/sites.private.json ] || printf '{ "version": 1, "sites": {} }\n' > /etc/jorah/sites.private.json
chown root:root /etc/jorah/sites.private.json; chmod 644 /etc/jorah/sites.private.json
install -d -o jorah-sites -g jorah-sites -m 700 /var/lib/jorah-sites

# 3. Firewall.
cp "$SRC/deploy/jorah-firewall.nft" /etc/nftables.conf
systemctl restart nftables
nft list chain inet jorah_out output | grep -cE 'skuid (1101|1102)' | xargs -I{} echo "firewall: {} site-reader rules loaded"

# 4. Services.
install -m 644 "$SRC/deploy/jorah-site-proxy.service" "$SRC/deploy/jorah-site-browser@.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now jorah-site-proxy
sleep 1; systemctl is-active jorah-site-proxy

# 5. OpenClaw: the agent, its key, the plugin, main's tools, the patch.
install -d -o jorah -g jorah -m 755 "$WS"
install -o jorah -g jorah -m 644 "$SRC"/workspace-site-reader/*.md "$WS/"
"${OC[@]}" agents list 2>&1 | grep -q reader-site || "${OC[@]}" agents add reader-site --workspace "$WS" --non-interactive
"${OC[@]}" secrets apply --from "$SRC/config/pc/site-reader-key.plan.json"
"${OC[@]}" plugins install --link "$SRC/plugins/jorah-sites" --force --accept-capabilities
"${OC[@]}" config patch --file "$TMP/allow.json5"
"${OC[@]}" config patch --file "$TMP/main-tools.json5"
"${OC[@]}" config patch --file "$SRC/config/pc/site-reader.patch.json5"
restart
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" models auth list --agent reader-site 2>&1 | tail -3 || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. No site is set up yet: site.sh set-host edupage <school>.edupage.org, then site.sh add edupage, then site.sh signin edupage."
echo "Config backup: $CFG.pre-sites. Undo: the same command with --undo."
