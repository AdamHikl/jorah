#!/usr/bin/env bash
# Receives the jorah-bot GitHub App's private key on stdin and stores it for plugins/jorah-github.
# Called by scripts/github/move-app-key.sh on the Mac; prints only a fingerprint, never the key.
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
dir=/home/jorah/.config/jorah-github
mkdir -p "$dir" && chmod 700 "$dir"
umask 077
tmp="$(mktemp "$dir/.incoming.XXXXXX")"
cat > "$tmp"
if ! grep -q "BEGIN RSA PRIVATE KEY\|BEGIN PRIVATE KEY" "$tmp" || ! openssl pkey -in "$tmp" -noout 2>/dev/null; then
  rm -f "$tmp"; echo "That wasn't a private key. Nothing saved."; exit 4
fi
mv "$tmp" "$dir/app.pem"
chmod 600 "$dir/app.pem"
echo "  saved: $dir/app.pem (mode 600)"
echo "  public key fingerprint: $(openssl pkey -in "$dir/app.pem" -pubout -outform DER 2>/dev/null | openssl dgst -sha256 -binary | base64)"
