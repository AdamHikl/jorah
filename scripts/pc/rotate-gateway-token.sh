#!/usr/bin/env bash
# Replace the Gateway token, for a lost phone or a leaked token (docs/runbooks/lost-phone.md).
# Run it as jorah, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     wsl -d jorah -u jorah -- bash -l /opt/jorah/scripts/pc/rotate-gateway-token.sh
# It never prints the token. jorah-voice gets the same new value in its own file (mode 600).
# The Gateway restart needs root, so the last step prints the command for Adam to run.
# Every client that used the old token (browser, mac-ear's Keychain entry) needs the new one.
set -euo pipefail

VOICE_TOKEN=/home/jorah/.config/jorah-voice/gateway-token
oc() { openclaw --profile jorah "$@"; }

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
[ -t 0 ] || { echo "Run this in an interactive terminal (ssh -t)."; exit 3; }
read -r -p 'Replace the Gateway token now? Every client must then use the new one. [y/N] ' A
[ "$A" = y ] || { echo "Nothing changed."; exit 3; }

umask 077
G=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
printf '%s' "$G" | oc secrets store set OPENCLAW_GATEWAY_TOKEN --kind secret --value-file -
printf '%s' "$G" > "$VOICE_TOKEN"; chmod 600 "$VOICE_TOKEN"
unset G
oc secrets audit --check && echo "Audit clean."

cat <<'EOF'

Token replaced in the store and in jorah-voice's file. Apply it with a restart, as root:
  wsl -d jorah -u root -- systemctl restart openclaw-gateway jorah-voice
Then: the browser and mac-ear need the new token (`openclaw --profile jorah gateway auth-token --show`
in a Terminal attached to no agent, then update mac-ear's Keychain entry).
EOF
