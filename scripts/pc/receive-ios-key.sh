#!/usr/bin/env bash
# Receives the iOS runner's shared HMAC key on the PC (contract jorah-ios/1, "Key"), as base64 on
# stdin, from the Mac. Adam runs it from the Mac, in a Terminal attached to no agent
# (docs/runbooks/ios-builds.md, step A10):
#   sudo base64 -i /Users/jorah-build/.config/jorah-ios/runner.key | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/receive-ios-key.sh
# Writes /home/jorah/.config/jorah-ios/runner.key, mode 600, only if it decodes to exactly 32 bytes,
# then prints its SHA-256 (not secret) to compare with the Mac's. Never prints the key.
# Base64 because the hop through Windows OpenSSH and wsl.exe is safe for text, not proven for bytes.
set -euo pipefail
[ "$(id -un)" = "jorah" ] || { echo "Run this as jorah."; exit 3; }
umask 077
dir="$HOME/.config/jorah-ios"
mkdir -p "$dir"
chmod 700 "$dir"
tmp="$(mktemp "$dir/.runner.key.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
tr -d '\r\n ' | base64 -d > "$tmp" || { echo "Stopped: the input was not base64."; exit 1; }
size="$(stat -c %s "$tmp")"
[ "$size" = "32" ] || { echo "Stopped: got $size bytes, want 32. Nothing written."; exit 1; }
chmod 600 "$tmp"
mv -f "$tmp" "$dir/runner.key"
trap - EXIT
echo "Written $dir/runner.key (600). SHA-256:"
sha256sum "$dir/runner.key" | cut -d' ' -f1
