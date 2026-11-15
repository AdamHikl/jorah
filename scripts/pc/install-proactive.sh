#!/usr/bin/env bash
# Installs the proactive layer on live Jorah (docs/runbooks/proactive.md). Run as root, in a Terminal
# attached to no agent, after /opt/jorah holds the reviewed commit (and jorah-guard with the
# proactive rules is installed from that same commit):
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-proactive.sh --dry-run
# What it does: the state folder /home/jorah/.jorah-proactive (mode 700); links
# plugins/jorah-proactive; adds its twelve tools to main's live tool list and the plugin to
# plugins.allow; applies config/pc/proactive.patch.json5; restarts the Gateway.
# It turns no proactive type on and creates no automation: those are separate steps, each with a yes.
#   --dry-run  checks files and validates the config changes against the live config; writes nothing.
#   --undo     removes the plugin and restores the config from before. The state folder stays.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
SRC=/opt/jorah
STATE=/home/jorah/.jorah-proactive
MODE="${1:-}"
TOOLS=(today_picture loops_list loop_propose loop_done loop_drop proactive_notify proactive_feedback proactive_resume
       proactive_why digest_list proactive_due proactive_tick)

restart() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "$MODE" = --undo ]; then
  "${OC[@]}" plugins uninstall jorah-proactive --force --keep-files || true
  [ -f "$CFG.pre-proactive" ] && { cp "$CFG.pre-proactive" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"; }
  restart
  echo "Proactive layer off; config restored from $CFG.pre-proactive. $STATE stays. Remove the automations by hand (runbook)."
  exit 0
fi

for f in plugins/jorah-proactive/index.js plugins/jorah-proactive/openclaw.plugin.json config/proactive/types.json \
         config/proactive/tick.script.js config/proactive/brief-due.trigger.js config/proactive/morning-brief.prompt.md \
         config/proactive/evening-wrap.prompt.md config/pc/proactive.patch.json5 config/permission-matrix.json \
         packages/contracts/phone/today.schema.json packages/contracts/phone/events.schema.json; do
  [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the reviewed commit to $SRC first."; exit 1; }
  [ "$(stat -c %U "$SRC/$f")" = root ] || { echo "$SRC/$f isn't root-owned."; exit 1; }
done
grep -q '"proactive_tick"' "$SRC/config/permission-matrix.json" || { echo "The permission list has no proactive rules: install jorah-guard from this commit first."; exit 1; }

# main's live tool list plus the twelve tools, and plugins.allow plus jorah-proactive, as patches.
TMP=$(mktemp -d /tmp/proactive.XXXXXX); trap 'rm -rf "$TMP"' EXIT
chmod 755 "$TMP"
LIST=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow 2>/dev/null || echo null)
ALLOW=$("${OC[@]}" config get plugins.allow 2>/dev/null || echo null)
python3 -I - "$LIST" "$ALLOW" "$TMP" "${TOOLS[@]}" <<'P'
import json, sys
lst, allow, out, tools = json.loads(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3], sys.argv[4:]
if not isinstance(lst, list) or not lst:
    sys.exit("main's tool list (tools.sandbox.tools.alsoAllow) isn't a list; stopping")
if not isinstance(allow, list) or not allow:
    sys.exit("plugins.allow isn't a list; stopping")
lst += [t for t in tools if t not in lst]
if "jorah-proactive" not in allow:
    allow.append("jorah-proactive")
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(f"{out}/main-tools.json5", "w"))
json.dump({"plugins": {"allow": allow}}, open(f"{out}/allow.json5", "w"))
P
chmod 644 "$TMP"/*.json5

if [ "$MODE" = --dry-run ]; then
  "${OC[@]}" config patch --file "$TMP/allow.json5" --dry-run
  "${OC[@]}" config patch --file "$TMP/main-tools.json5" --dry-run
  "${OC[@]}" config patch --file "$SRC/config/pc/proactive.patch.json5" --dry-run
  echo "Would create $STATE (mode 700, owner jorah), link plugins/jorah-proactive, apply the three patches above and restart the Gateway."
  echo "Main's tools would be: $(python3 -I -c 'import json,sys; print(", ".join(json.load(open(sys.argv[1]))["agents"]["entries"]["main"]["tools"]["sandbox"]["tools"]["alsoAllow"]))' "$TMP/main-tools.json5")"
  echo "No proactive type is turned on and no automation is created. Dry run only: nothing written."
  exit 0
fi

[ -f "$CFG.pre-proactive" ] || cp -p "$CFG" "$CFG.pre-proactive"
install -d -o jorah -g jorah -m 700 "$STATE"
"${OC[@]}" plugins install --link "$SRC/plugins/jorah-proactive" --force --accept-capabilities
"${OC[@]}" config patch --file "$TMP/allow.json5"
"${OC[@]}" config patch --file "$TMP/main-tools.json5"
"${OC[@]}" config patch --file "$SRC/config/pc/proactive.patch.json5"
restart
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. Nothing is turned on yet: see the runbook for each type and each automation, one yes at a time."
echo "Config backup: $CFG.pre-proactive. Undo: the same command with --undo."
