#!/usr/bin/env bash
# Installs Jorah's Google readers on live Jorah (docs/runbooks/google.md). Run as root, in a Terminal
# attached to no agent, after /opt/jorah holds the reviewed commit, and only after the P5 gate passes:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-google.sh binary --dry-run
# Stages, each on its own yes:
#   binary   gog v0.48.0 (released 2026-11-05) for linux/amd64 into /opt/jorah-tools/gog-0.48.0,
#            root-owned, checked against the SHA-256 pinned below (from the release's checksums.txt,
#            read 2026-11-15). /opt/jorah-tools/gog/gog points at it. Nothing in OpenClaw changes.
#   plugin   The jorah-google plugin, its four tools on main's tool list, config/pc/google.patch.json5,
#            a Gateway restart. Needs Adam's grant first (scripts/pc/google-grant.sh), or the tools
#            answer "not set up".
#   undo     Removes the plugin and restores the config from before the plugin stage. The binary and
#            the grant stay: google-grant.sh remove deletes the token, and Google's page revokes it.
# Add --dry-run after a stage to check it and see what it would do; nothing is written.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
CFG=/home/jorah/.openclaw-jorah/openclaw.json
SRC=/opt/jorah
VERSION=0.48.0
TARBALL="gogcli_${VERSION}_linux_amd64.tar.gz"
URL="https://github.com/openclaw/gogcli/releases/download/v${VERSION}/${TARBALL}"
SHA256=8809d2f4fe95a0299b1a2a5c6bc912c4aba4b90a7b5e2c1f5cf11b9945a50004
DEST=/opt/jorah-tools/gog-${VERSION}
TOOLS=(calendar_read mail_read mail_open contact_search)
STAGE="${1:-}"
DRY="${2:-}"
case "$STAGE" in binary|plugin|undo) ;; *) sed -n 2,18p "$0"; exit 2 ;; esac
[ -z "$DRY" ] || [ "$DRY" = --dry-run ] || { echo "Unknown option $DRY"; exit 2; }

restart_gateway() {
  systemctl restart openclaw-gateway
  for _ in $(seq 1 45); do "${OC[@]}" health >/dev/null 2>&1 && break; sleep 2; done
  "${OC[@]}" health 2>&1 | tail -1
}

if [ "$STAGE" = binary ]; then
  if [ "$DRY" = --dry-run ]; then
    [ -x "$DEST/gog" ] && echo "Installed already: $("$DEST/gog" --version 2>&1 | head -1)"
    echo "Would download $URL as root, check SHA-256 $SHA256, install the gog binary to $DEST (root-owned, 755)"
    echo "and point /opt/jorah-tools/gog at it. Dry run only: nothing written."
    exit 0
  fi
  TMP=$(mktemp -d /tmp/gog.XXXXXX); trap 'rm -rf "$TMP"' EXIT
  curl -fsSL --proto '=https' --max-time 120 -o "$TMP/$TARBALL" "$URL"
  echo "$SHA256  $TMP/$TARBALL" | sha256sum -c - || { echo "Checksum mismatch: stopping, nothing installed."; exit 1; }
  mkdir "$TMP/x" && tar -xzf "$TMP/$TARBALL" -C "$TMP/x" --no-same-owner
  BIN=$(find "$TMP/x" -type f -name gog -perm -u+x | head -1)
  [ -n "$BIN" ] || { echo "No gog binary in the archive: stopping."; exit 1; }
  install -d -o root -g root -m 755 /opt/jorah-tools "$DEST"
  install -o root -g root -m 755 "$BIN" "$DEST/gog"
  ln -sfn "$DEST" /opt/jorah-tools/gog
  echo "gog: $(runuser -u jorah -- /opt/jorah-tools/gog/gog --version 2>&1 | head -1) at /opt/jorah-tools/gog/gog"
  echo "Next: Adam's grant (google-grant.sh client, then grant), then this script's plugin stage after the P5 gate."
  exit 0
fi

if [ "$STAGE" = undo ]; then
  [ "$DRY" = --dry-run ] && { echo "Would uninstall the jorah-google plugin and restore $CFG.pre-google if it exists."; exit 0; }
  "${OC[@]}" plugins uninstall jorah-google --force --keep-files 2>/dev/null || true
  if [ -f "$CFG.pre-google" ]; then
    cp "$CFG.pre-google" "$CFG"; chown jorah:jorah "$CFG"; chmod 600 "$CFG"
    restart_gateway
    echo "Config restored from $CFG.pre-google."
  fi
  echo "Google readers off. The gog binary and the grant stay (google-grant.sh remove deletes the token)."
  exit 0
fi

# plugin stage
for f in plugins/jorah-google/index.js plugins/jorah-google/lib/gog.js plugins/jorah-google/lib/map.js \
         plugins/jorah-google/openclaw.plugin.json config/pc/google.patch.json5 config/permission-matrix.json; do
  [ -f "$SRC/$f" ] || { echo "Missing $SRC/$f: copy the reviewed commit to $SRC first."; exit 1; }
  [ "$(stat -c %U "$SRC/$f")" = root ] || { echo "$SRC/$f isn't root-owned."; exit 1; }
done
[ -x /opt/jorah-tools/gog/gog ] || { echo "gog isn't installed: run the binary stage first."; exit 1; }
grep -q '"calendar_read"' "$SRC/config/permission-matrix.json" || { echo "The guard's permission list in $SRC doesn't know the Google tools yet."; exit 1; }
[ -f /home/jorah/.config/jorah-google/keyring-password ] || echo "Note: no grant yet (google-grant.sh). The tools will answer \"not set up\" until there is one."

TMP=$(mktemp -d /tmp/google.XXXXXX); trap 'rm -rf "$TMP"' EXIT
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
for t in tools:
    if t not in lst:
        lst.append(t)
if "jorah-google" not in allow:
    allow.append("jorah-google")
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(f"{out}/main-tools.json5", "w"))
json.dump({"plugins": {"allow": allow}}, open(f"{out}/allow.json5", "w"))
P
chmod 644 "$TMP"/*.json5

if [ "$DRY" = --dry-run ]; then
  "${OC[@]}" config patch --file "$TMP/allow.json5" --dry-run
  "${OC[@]}" config patch --file "$TMP/main-tools.json5" --dry-run
  "${OC[@]}" config patch --file "$SRC/config/pc/google.patch.json5" --dry-run
  echo "Would link plugins/jorah-google, apply the three patches above and restart the Gateway."
  echo "Main's tools would be: $(python3 -I -c 'import json,sys; print(", ".join(json.load(open(sys.argv[1]))["agents"]["entries"]["main"]["tools"]["sandbox"]["tools"]["alsoAllow"]))' "$TMP/main-tools.json5")"
  echo "Dry run only: nothing written."
  exit 0
fi

[ -f "$CFG.pre-google" ] || cp -p "$CFG" "$CFG.pre-google"
"${OC[@]}" plugins install --link "$SRC/plugins/jorah-google" --force --accept-capabilities
"${OC[@]}" config patch --file "$TMP/allow.json5"
"${OC[@]}" config patch --file "$TMP/main-tools.json5"
"${OC[@]}" config patch --file "$SRC/config/pc/google.patch.json5"
restart_gateway
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-" || true
"${OC[@]}" security audit 2>&1 | grep -E "^Summary" || true
echo "Done. Config backup: $CFG.pre-google. Undo: the same command with undo."
