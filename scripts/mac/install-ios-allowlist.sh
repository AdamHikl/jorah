#!/bin/bash
# Installs the runner allowlist (docs/runbooks/ios-builds.md, step A9). Adam runs it; no agent does.
#   scripts/mac/install-ios-allowlist.sh --dry-run <UDID>   # preview, no sudo
#   sudo scripts/mac/install-ios-allowlist.sh <UDID>        # preview, then asks
# Source: services/ios-runner/ios-projects.json, the entries that were built and tested (the only
# copy). Adds the iPhone as `adam-iphone` with the given UDID (from `xcrun devicectl list devices`),
# then installs it as /Library/Application Support/Jorah/ios-projects.json, root:wheel 0644.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO/services/ios-runner/ios-projects.json"
DEST="/Library/Application Support/Jorah/ios-projects.json"
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi
[ "$#" = "1" ] || { sed -n '2,7p' "$0"; exit 2; }
UDID="$1"

die() { echo "Stopped: $*" >&2; exit 1; }
[ "$DRY_RUN" = "1" ] || [ "$(id -u)" = "0" ] || die "run it with sudo (or --dry-run to preview)."
[ -d "$(dirname "$DEST")" ] || die "$(dirname "$DEST") is missing: run scripts/mac/setup-jorah-build.sh first."

tmp="$(mktemp -t ios-projects)"
trap 'rm -f "$tmp"' EXIT
/usr/bin/python3 -I "$REPO/scripts/mac/ios_allowlist.py" "$SRC" "$UDID" > "$tmp"

echo "Source: $SRC"
echo "Adds:   devices.adam-iphone = $UDID"
if [ -e "$DEST" ]; then
  echo "Changes against the installed $DEST:"
  diff -u "$DEST" "$tmp" && echo "  (none)"
else
  echo "Installs $DEST (new), root:wheel 0644."
fi
[ "$DRY_RUN" = "1" ] && { echo "Dry run: nothing changed."; exit 0; }

read -r -p "Type yes to install exactly this: " answer
[ "$answer" = "yes" ] || die "not installed."
install -o root -g wheel -m 0644 "$tmp" "$DEST"
stat -f '%Su:%Sg %Sp %N' "$DEST"
echo "The runner reads it when it starts. If it is already running, restart it as jorah-build:"
echo "  launchctl kickstart -k gui/\$(id -u)/com.jorah.ios-runner"
