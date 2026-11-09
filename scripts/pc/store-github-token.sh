#!/usr/bin/env bash
# Stores Jorah's GitHub token for plugins/jorah-github. Adam runs it as jorah, in a Terminal
# attached to no agent, and pastes the token at the hidden prompt:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/store-github-token.sh
# Then checks it with GitHub and prints the account name and scopes, never the token.
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
dir=/home/jorah/.config/jorah-github
mkdir -p "$dir" && chmod 700 "$dir"
read -rsp "Paste Jorah's GitHub token (hidden), then Enter: " token; echo
[ "${#token}" -ge 20 ] || { echo "That doesn't look like a token. Nothing saved."; exit 4; }
umask 077
printf '%s' "$token" > "$dir/token"
chmod 600 "$dir/token"
headers="$(curl -sS -D - -o /dev/null -H "Authorization: Bearer $token" https://api.github.com/user)"
unset token
echo "$headers" | grep -iE "^HTTP/|^x-oauth-scopes:" | sed 's/^/  /'
login="$(curl -sS -H "Authorization: Bearer $(cat "$dir/token")" https://api.github.com/user | python3 -c 'import json,sys; print(json.load(sys.stdin).get("login","unknown"))')"
echo "  account: $login"
echo "Saved to $dir/token (mode 600)."
