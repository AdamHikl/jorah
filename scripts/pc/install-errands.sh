#!/usr/bin/env bash
# Installs Jorah's errands plugin on live Jorah (docs/runbooks/errands.md). Run as root, in a Terminal
# attached to no agent, after /opt/jorah holds the reviewed commit (jorah-guard's permission list
# from that same commit, since the guard blocks tools it doesn't list):
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-errands.sh --dry-run
# What it does: the state folder /home/jorah/.jorah-errands (mode 700); links plugins/jorah-errands;
# adds its six tools to main's live tool list, price_compare to deep's, and the plugin to
# plugins.allow; applies config/pc/errands.patch.json5; restarts the Gateway (the guard reads its
# permission list at start). It creates no automation, and doesn't copy AGENTS.md (runbook step 2).
#   --dry-run  checks files and validates the config changes against the live config; writes nothing.
#   --undo     removes the plugin and restores the config from before. The state folder stays.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
SRC=/opt/jorah
STATE=/home/jorah/.jorah-errands
MODE="${1:-}"
case "$MODE" in ""|--dry-run|--undo) ;; *) sed -n 2,13p "$0"; exit 2 ;; esac
TOOLS=(reminder_job price_compare supply_list supply_plan supply_save supply_forget)
DEEP_TOOLS=(price_compare)

restart() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "$MODE" = --undo ]; then
  "${OC[@]}" plugins uninstall jorah-errands --force --keep-files || true
  [ -f "$CFG.pre-errands" ] && { cp "$CFG.pre-errands" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"; }
  restart
  echo "Errands off; config restored from $CFG.pre-errands. $STATE stays (it may hold private details: delete it by hand if Adam asks)."
  echo "Restock reminders already set stay in automations: list them and remove the jorah:restock:* ones if wanted."
  exit 0
fi

for f in plugins/jorah-errands/index.js plugins/jorah-errands/openclaw.plugin.json plugins/jorah-errands/package.json \
         plugins/jorah-errands/lib/dates.js plugins/jorah-errands/lib/reminder.js plugins/jorah-errands/lib/supplies.js \
         plugins/jorah-errands/lib/prices.js plugins/jorah-errands/lib/store.js \
         config/pc/errands.patch.json5 config/permission-matrix.json; do
  [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the reviewed commit to $SRC first."; exit 1; }
  [ "$(stat -c %U "$SRC/$f")" = root ] || { echo "$SRC/$f isn't root-owned."; exit 1; }
done
grep -q '"supply_forget"' "$SRC/config/permission-matrix.json" || { echo "The permission list has no errands rules: copy this commit's config/permission-matrix.json first."; exit 1; }

# main's and deep's live tool lists plus the new tools, and plugins.allow plus jorah-errands, as patches.
TMP=$(mktemp -d /tmp/errands.XXXXXX); trap 'rm -rf "$TMP"' EXIT
chmod 755 "$TMP"
MAIN=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow 2>/dev/null || echo null)
DEEP=$("${OC[@]}" config get agents.entries.deep.tools.sandbox.tools.alsoAllow 2>/dev/null || echo null)
ALLOW=$("${OC[@]}" config get plugins.allow 2>/dev/null || echo null)
python3 -I - "$MAIN" "$DEEP" "$ALLOW" "$TMP" "${TOOLS[*]}" "${DEEP_TOOLS[*]}" <<'P'
import json, sys
main, deep, allow, out = json.loads(sys.argv[1]), json.loads(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4]
tools, deep_tools = sys.argv[5].split(), sys.argv[6].split()
for name, lst in (("main", main), ("deep", deep)):
    if not isinstance(lst, list) or not lst:
        sys.exit(f"{name}'s tool list (tools.sandbox.tools.alsoAllow) isn't a list; stopping")
if not isinstance(allow, list) or not allow:
    sys.exit("plugins.allow isn't a list; stopping")
main += [t for t in tools if t not in main]
deep += [t for t in deep_tools if t not in deep]
if "jorah-errands" not in allow:
    allow.append("jorah-errands")
entry = lambda lst: {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}
json.dump({"agents": {"entries": {"main": entry(main), "deep": entry(deep)}}}, open(f"{out}/tools.json5", "w"))
json.dump({"plugins": {"allow": allow}}, open(f"{out}/allow.json5", "w"))
P
chmod 644 "$TMP"/*.json5

if [ "$MODE" = --dry-run ]; then
  "${OC[@]}" config patch --file "$TMP/allow.json5" --dry-run
  "${OC[@]}" config patch --file "$TMP/tools.json5" --dry-run
  "${OC[@]}" config patch --file "$SRC/config/pc/errands.patch.json5" --dry-run
  python3 -I -c 'import json,sys; e=json.load(open(sys.argv[1]))["agents"]["entries"]; [print(f"{a} tools would be: " + ", ".join(e[a]["tools"]["sandbox"]["tools"]["alsoAllow"])) for a in ("main","deep")]' "$TMP/tools.json5"
  echo "Would create $STATE (mode 700, owner jorah), link plugins/jorah-errands, apply the three patches above and restart the Gateway."
  echo "No automation is created. Dry run only: nothing written."
  exit 0
fi

[ -f "$CFG.pre-errands" ] || cp -p "$CFG" "$CFG.pre-errands"
install -d -o jorah -g jorah -m 700 "$STATE"
"${OC[@]}" plugins install --link "$SRC/plugins/jorah-errands" --force --accept-capabilities
"${OC[@]}" config patch --file "$TMP/allow.json5"
"${OC[@]}" config patch --file "$TMP/tools.json5"
"${OC[@]}" config patch --file "$SRC/config/pc/errands.patch.json5"
restart
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. Config backup: $CFG.pre-errands. Undo: the same command with --undo."
