#!/usr/bin/env bash
# Installs Jorah's toolbox on live Jorah (docs/runbooks/toolbox.md). Run as root, in a Terminal
# attached to no agent, after /opt/jorah holds the reviewed commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-toolbox.sh --dry-run
#
# What it does:
#   1. user jorah-toolbox (uid 1103): no login, no home, no sudo. The installer runs as it.
#   2. /opt/jorah-toolbox (jorah-toolbox, 755; read-only to everyone else, tools go here) and
#      /var/lib/jorah-toolbox: proposals/ and tested/ (jorah), approved/ (2770 jorah:jorah-toolbox,
#      written only by the jorah-projects plugin after Adam's card), results/ and downloads/
#      (jorah-toolbox).
#   3. the firewall: deploy/jorah-firewall.nft (adds uid 1103: DNS and public HTTPS only) to
#      /etc/nftables.conf, the old one kept as /etc/nftables.conf.pre-toolbox.
#   4. jorah-toolbox.service and jorah-toolbox.path; the path unit enabled and started. The updated
#      jorah-projects.service (write access to proposals/ and tested/), reloaded.
#   5. as jorah: scripts/pc/setup-project-permissions.sh (toolbox readable, not writable, in runs;
#      the 7-day limit for npm, pip and uv).
#   6. the four toolbox_* tools added to main's live tool list; the Gateway restarted so the updated
#      jorah-projects plugin (same link, /opt/jorah/plugins/jorah-projects) loads them.
# Nothing is installed in the toolbox itself: tools come only from Adam's cards.
#
#   --dry-run   checks the files, the users and the firewall file (nft -c), shows the firewall diff
#               and validates the tool-list patch against the live config. Writes nothing.
#   --no-gateway    steps 1 to 5 only: nothing in the live Gateway changes (when another session
#                   holds it). Needs only the system files in $SRC, not the plugin or the guard's list.
#   --gateway-only  step 6 only, once steps 1 to 5 are done and the plugin and the guard's list from
#                   this commit are in $SRC.
#   --undo      stops and removes the units, restores the firewall and main's tool list from the
#               backups, restarts the Gateway. /opt/jorah-toolbox, /var/lib/jorah-toolbox and the
#               user stay (they hold what was installed); the runbook says how to remove them.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
# openclaw runs as jorah and spawns workers in the current folder: from /root (unreadable to jorah)
# `config validate` fails with "spawn ... EACCES" [measured 2026-11-18].
cd /
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
SRC=/opt/jorah
OPT=/opt/jorah-toolbox
VAR=/var/lib/jorah-toolbox
UIDN=1103
DRY=0; SYSTEM=1; GATEWAY=1; UNDO=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --no-gateway) GATEWAY=0 ;;
    --gateway-only) SYSTEM=0 ;;
    --undo) UNDO=1 ;;
    *) echo "Unknown option: $arg"; exit 2 ;;
  esac
done
[ "$SYSTEM" = 1 ] || [ "$GATEWAY" = 1 ] || { echo "--no-gateway and --gateway-only together leave nothing to do."; exit 2; }
TOOLS=(toolbox_list toolbox_propose toolbox_install toolbox_remove)

# Load the firewall file without restarting nftables.service: openclaw-gateway.service has
# Requires=nftables.service, so `systemctl restart nftables` restarts the Gateway too (it did,
# 2026-11-18 11:27). nft -f replaces the ruleset (the file starts with flush ruleset); then
# jorah-firewall-ports puts the live ephemeral port range back.
load_firewall() {
  nft -f /etc/nftables.conf
  systemctl restart jorah-firewall-ports.service
}

restart() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "$UNDO" = 1 ]; then
  systemctl disable --now jorah-toolbox.path 2>/dev/null || true
  rm -f /etc/systemd/system/jorah-toolbox.service /etc/systemd/system/jorah-toolbox.path
  systemctl daemon-reload
  if [ -f /etc/nftables.conf.pre-toolbox ]; then cp /etc/nftables.conf.pre-toolbox /etc/nftables.conf; load_firewall; fi
  if [ "$GATEWAY" = 1 ] && [ -f "$CFG.pre-toolbox" ]; then
    cp "$CFG.pre-toolbox" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"; restart
  fi
  sync
  echo "Toolbox off: units removed, firewall and main's tool list restored. $OPT, $VAR and user jorah-toolbox stay."
  exit 0
fi

# ---- checks ---------------------------------------------------------------------------------------
need=()
[ "$SYSTEM" = 1 ] && need+=(services/jorah-toolbox/bin/jorah-toolbox services/jorah-toolbox/jorah_toolbox/install.py
  packages/contracts/toolbox/toolcheck.py deploy/jorah-toolbox.service deploy/jorah-toolbox.path deploy/jorah-projects.service
  deploy/jorah-firewall.nft scripts/pc/setup-project-permissions.sh scripts/pc/toolbox-apt.sh
  services/jorah-projects/jorah_projects/toolbox.py)
[ "$GATEWAY" = 1 ] && need+=(plugins/jorah-projects/lib/toolbox.js plugins/jorah-projects/index.js config/permission-matrix.json)
for f in "${need[@]}"; do
  [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the reviewed commit to $SRC first."; exit 1; }
  [ "$(stat -c %U "$SRC/$f")" = root ] || { echo "$SRC/$f isn't root-owned."; exit 1; }
done
if [ "$GATEWAY" = 1 ]; then
  grep -q '"toolbox_install"' "$SRC/config/permission-matrix.json" || { echo "The permission list has no toolbox rules: install jorah-guard's list from this commit first."; exit 1; }
fi
if [ "$SYSTEM" = 0 ]; then
  if ! { [ -f "$OPT/installed.json" ] && systemctl is-active --quiet jorah-toolbox.path; }; then
    echo "The toolbox's system part isn't installed: run with --no-gateway first."; exit 1
  fi
else
  for bin in unsquashfs bwrap python3 nft; do command -v "$bin" >/dev/null || { echo "$bin is missing."; exit 1; }; done
  if have=$(id -u jorah-toolbox 2>/dev/null); then
    [ "$have" = "$UIDN" ] || { echo "jorah-toolbox exists with uid $have, not $UIDN: stopping."; exit 1; }
  elif getent passwd "$UIDN" >/dev/null; then
    echo "uid $UIDN is taken by $(getent passwd "$UIDN" | cut -d: -f1): stopping."; exit 1
  fi
  nft -c -f "$SRC/deploy/jorah-firewall.nft" && echo "firewall file: valid (nft -c)"
  echo "firewall change against the live /etc/nftables.conf (comments left out):"
  diff <(grep -v '^\s*#' /etc/nftables.conf) <(grep -v '^\s*#' "$SRC/deploy/jorah-firewall.nft") | sed 's/^/  /' || true
fi

TMP=""
if [ "$GATEWAY" = 1 ]; then
  TMP=$(mktemp -d /tmp/toolbox.XXXXXX); trap 'rm -rf "$TMP"' EXIT
  chmod 755 "$TMP"
  LIST=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow 2>/dev/null || echo null)
  python3 -I - "$LIST" "$TMP" "${TOOLS[@]}" <<'P'
import json, sys
lst, out, tools = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3:]
if not isinstance(lst, list) or not lst:
    sys.exit("main's tool list (tools.sandbox.tools.alsoAllow) isn't a list; stopping")
if "project_list" not in lst:
    sys.exit("main's tool list has no project_* tools: install project mode first")
lst += [t for t in tools if t not in lst]
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(f"{out}/main-tools.json5", "w"))
P
  chmod 644 "$TMP"/*.json5
fi

if [ "$DRY" = 1 ]; then
  [ "$GATEWAY" = 1 ] && "${OC[@]}" config patch --file "$TMP/main-tools.json5" --dry-run
  if [ "$SYSTEM" = 1 ]; then
    echo "Would: create user jorah-toolbox ($UIDN) unless present; make $OPT and $VAR with the owners above;"
    echo "load the firewall file above (backup /etc/nftables.conf.pre-toolbox); install jorah-toolbox.service and .path,"
    echo "start the path unit; install the updated jorah-projects.service; rerun setup-project-permissions.sh as jorah."
  fi
  [ "$GATEWAY" = 1 ] && echo "Then add ${TOOLS[*]} to main's tools (backup $CFG.pre-toolbox) and restart the Gateway."
  echo "Dry run only: nothing written."
  exit 0
fi

if [ "$SYSTEM" = 1 ]; then
# ---- 1. user ----------------------------------------------------------------------------------------
id jorah-toolbox >/dev/null 2>&1 || useradd --system --uid "$UIDN" --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin jorah-toolbox

# ---- 2. folders -------------------------------------------------------------------------------------
install -d -o jorah-toolbox -g jorah-toolbox -m 755 "$OPT" "$OPT/bin" "$OPT/tools"
install -d -o jorah-toolbox -g jorah-toolbox -m 700 "$OPT/.staging"
install -d -o root -g root -m 755 "$VAR"
install -d -o jorah -g jorah -m 755 "$VAR/proposals" "$VAR/tested"
install -d -o jorah -g jorah-toolbox -m 2770 "$VAR/approved"
install -d -o jorah-toolbox -g jorah-toolbox -m 755 "$VAR/results"
install -d -o jorah-toolbox -g jorah-toolbox -m 700 "$VAR/downloads"
[ -f "$OPT/installed.json" ] || { printf '{\n  "v": 1,\n  "tools": {}\n}\n' > "$OPT/installed.json"; chown jorah-toolbox:jorah-toolbox "$OPT/installed.json"; chmod 644 "$OPT/installed.json"; }

# ---- 3. firewall ------------------------------------------------------------------------------------
[ -f /etc/nftables.conf.pre-toolbox ] || cp -p /etc/nftables.conf /etc/nftables.conf.pre-toolbox
cp "$SRC/deploy/jorah-firewall.nft" /etc/nftables.conf
load_firewall
echo "firewall: $(nft list chain inet jorah_out output | grep -c "skuid $UIDN") rules for jorah-toolbox loaded"

# ---- 4. units ---------------------------------------------------------------------------------------
install -m 644 "$SRC/deploy/jorah-toolbox.service" "$SRC/deploy/jorah-toolbox.path" "$SRC/deploy/jorah-projects.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now jorah-toolbox.path
systemctl is-active jorah-toolbox.path

# ---- 5. project-run settings ------------------------------------------------------------------------
runuser -u jorah -- env HOME=/home/jorah bash "$SRC/scripts/pc/setup-project-permissions.sh"
sync
fi

# ---- 6. Gateway: the four tools for main ------------------------------------------------------------
if [ "$GATEWAY" = 1 ]; then
  [ -f "$CFG.pre-toolbox" ] || cp -p "$CFG" "$CFG.pre-toolbox"
  "${OC[@]}" config patch --file "$TMP/main-tools.json5"
  "${OC[@]}" config validate 2>&1 | tail -1
  # The plugin now declares four more tools, so OpenClaw wants its capabilities accepted again;
  # without it the plugin may not load at the next start [measured 2026-11-18: "requires
  # capability consent"]. These are the four tools Adam approved.
  "${OC[@]}" plugins enable jorah-projects --accept-capabilities
  restart
  "${OC[@]}" plugins list 2>&1 | grep -E "jorah-projects" || true
fi
sync
echo "Done. Status as jorah-toolbox:"
runuser -u jorah-toolbox -- /usr/bin/python3 -I "$SRC/services/jorah-toolbox/bin/jorah-toolbox" status
echo "Undo: the same command with --undo."
