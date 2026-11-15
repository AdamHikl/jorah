#!/usr/bin/env bash
# Sets up the site readers on the jorah-dev scratch profile only (docs/runbooks/site-readers.md,
# stage C). Run as jorah, after /opt/jorah holds the commit and install-site-readers.sh --system-only
# has run. Never touches the live profile. From the Mac:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/site-readers-dev-setup.sh --dry-run"
#   --dry-run  copies nothing, validates the config changes against jorah-dev's config.
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
OC=(/usr/local/bin/openclaw --profile jorah-dev)
SRC=/opt/jorah
DEV=/home/jorah/scratch-dev
WS=$DEV/workspace-site-reader
MODE="${1:-}"

for f in plugins/jorah-sites/index.js plugins/jorah-guard/lib/sites.js config/pc/dev/site-readers.patch.json5 tests/sites/fakeschool.json; do
  [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the commit to $SRC first."; exit 1; }
done
id jorah-sites >/dev/null 2>&1 || { echo "No jorah-sites user: run install-site-readers.sh --system-only (root) first."; exit 1; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
LIST=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow 2>/dev/null || echo null)
python3 -I - "$LIST" "$TMP/main-tools.json5" <<'P'
import json, sys
lst = json.loads(sys.argv[1])
if lst is None:
    lst = []
if not isinstance(lst, list):
    sys.exit("jorah-dev main's tool list isn't a list; stopping")
for t in ("site_read", "sites_list"):
    if t not in lst:
        lst.append(t)
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(sys.argv[2], "w"))
P

if [ "$MODE" = --dry-run ]; then
  "${OC[@]}" config patch --file "$SRC/config/pc/dev/site-readers.patch.json5" --dry-run
  "${OC[@]}" config patch --file "$TMP/main-tools.json5" --dry-run
  "${OC[@]}" agents list 2>&1 | grep -q reader-site && echo "reader-site exists on jorah-dev." || echo "Would add reader-site to jorah-dev (workspace $WS)."
  echo "Would copy jorah-guard, jorah-sites and the permission list to $DEV/p5, the reader's rules to $WS, and restart jorah-dev."
  echo "Dry run only: nothing written."
  exit 0
fi

# Scratch copies of the plugins and the permission list, as config/pc/dev/guard.patch.json5 expects.
mkdir -p "$DEV/p5/plugins" "$DEV/p5/config" "$WS"
rm -rf "$DEV/p5/plugins/jorah-guard.new" "$DEV/p5/plugins/jorah-sites.new"
cp -r "$SRC/plugins/jorah-guard" "$DEV/p5/plugins/jorah-guard.new"
cp -r "$SRC/plugins/jorah-sites" "$DEV/p5/plugins/jorah-sites.new"
rm -rf "$DEV/p5/plugins/jorah-guard" "$DEV/p5/plugins/jorah-sites"
mv "$DEV/p5/plugins/jorah-guard.new" "$DEV/p5/plugins/jorah-guard"
mv "$DEV/p5/plugins/jorah-sites.new" "$DEV/p5/plugins/jorah-sites"
cp "$SRC/config/permission-matrix.json" "$DEV/p5/config/permission-matrix.json"
cp "$SRC"/workspace-site-reader/*.md "$WS/"

"${OC[@]}" agents list 2>&1 | grep -q reader-site || "${OC[@]}" agents add reader-site --workspace "$WS" --non-interactive
"${OC[@]}" secrets apply --from "$SRC/config/pc/site-reader-key.plan.json"
"${OC[@]}" config patch --file "$SRC/config/pc/dev/site-readers.patch.json5"
"${OC[@]}" config patch --file "$TMP/main-tools.json5"
bash "$SRC/scripts/pc/dev-gateway.sh" stop || true
bash "$SRC/scripts/pc/dev-gateway.sh" start
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
echo "jorah-dev ready. Stage C (root): python3 $SRC/scripts/pc/site-readers-dev-test.py --runs 3"
