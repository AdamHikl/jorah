#!/usr/bin/env bash
# Adam's Google read-only grant for Jorah's Google readers (docs/runbooks/google.md). Run as jorah, in
# a Terminal attached to no agent. Nothing secret is ever printed or put on a command line.
#
#   client   Receives the OAuth client file (Google Cloud Console, Desktop app) as base64 on stdin,
#            from the Mac, checks it is an "installed" client, and keeps it mode 600:
#              base64 -i ~/Downloads/client_secret_*.json | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/google-grant.sh client
#   grant    Interactive (ssh -t): makes the file keyring's password if there is none (random, mode
#            600, never shown), stores the client in gog, then asks Google for read-only Calendar,
#            Gmail and Contacts on the address you type. gog prints a link: open it in your own
#            browser, allow, then paste the address the browser ends on back here. Sets the alias
#            "adam" and deletes the client file.
#              ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/google-grant.sh grant
#   status   What is granted: accounts and scopes, as gog reports them.
#   remove   Deletes the stored token from the PC. Revoke it at Google too (runbook).
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
GOG=/opt/jorah-tools/gog/gog
CFG="$HOME/.config/jorah-google"
export GOG_HOME="$HOME/.local/share/jorah-google/gog" GOG_KEYRING_BACKEND=file GOG_READONLY=1
umask 077
mkdir -p "$CFG" "$GOG_HOME"
chmod 700 "$CFG" "$GOG_HOME" "$(dirname "$GOG_HOME")"
password() {
  [ -f "$CFG/keyring-password" ] || { head -c 32 /dev/urandom | base64 | tr -d '\n/+=' | head -c 40 > "$CFG/keyring-password"; chmod 600 "$CFG/keyring-password"; }
  GOG_KEYRING_PASSWORD="$(cat "$CFG/keyring-password")"; export GOG_KEYRING_PASSWORD
}
need_gog() { [ -x "$GOG" ] || { echo "gog isn't installed: run install-google.sh binary first."; exit 1; }; }

case "${1:-}" in
  client)
    tmp="$(mktemp "$CFG/.client.XXXXXX")"; trap 'rm -f "$tmp"' EXIT
    tr -d '\r\n ' | base64 -d > "$tmp" || { echo "Stopped: the input was not base64."; exit 1; }
    python3 -I - "$tmp" <<'P' || { echo "Stopped: not a Desktop-app OAuth client file. Nothing kept."; exit 1; }
import json, sys
d = json.load(open(sys.argv[1]))
c = d.get("installed")
assert isinstance(c, dict) and c.get("client_id") and c.get("client_secret")
P
    chmod 600 "$tmp"; mv -f "$tmp" "$CFG/client.json"; trap - EXIT
    echo "Kept $CFG/client.json (600). Next: google-grant.sh grant, with ssh -t."
    ;;
  grant)
    need_gog
    [ -t 0 ] || { echo "Run this in an interactive terminal (ssh -t)."; exit 3; }
    [ -f "$CFG/client.json" ] || { echo "No client file: run google-grant.sh client first."; exit 1; }
    password
    "$GOG" auth keyring file
    "$GOG" auth credentials set "$CFG/client.json"
    read -r -p "Your Google address (read-only access is asked for): " ACCOUNT
    [[ "$ACCOUNT" =~ ^[^[:space:]@]+@[^[:space:]@]+$ ]] || { echo "That isn't an address."; exit 1; }
    "$GOG" auth add "$ACCOUNT" --readonly --services calendar,gmail,contacts --manual
    "$GOG" auth alias set adam "$ACCOUNT"
    rm -f "$CFG/client.json"
    echo "Done. The client file is deleted. Check the scopes with: google-grant.sh status"
    ;;
  status)
    need_gog; password
    "$GOG" --json auth list
    ;;
  remove)
    need_gog; password
    read -r -p "Your Google address, to delete its token from the PC: " ACCOUNT
    read -r -p "Delete the stored Google token for it? [y/N] " A
    [ "$A" = y ] || { echo "Nothing changed."; exit 0; }
    "$GOG" auth remove "$ACCOUNT" || true
    "$GOG" auth alias unset adam || true
    echo "Removed here. Also revoke it at myaccount.google.com → Security → Third-party connections."
    ;;
  *) sed -n 2,20p "$0"; exit 2 ;;
esac
