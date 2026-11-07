#!/usr/bin/env bash
# Move Jorah's API key from plain text in the auth database into the secret store.
# Run it as jorah, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     wsl -d jorah -u jorah -- bash -l /opt/jorah/scripts/pc/store-api-key.sh
# It never prints the key. The mapping applies only after Adam confirms it in OpenClaw's helper.
set -euo pipefail

ID=ANTHROPIC_API_KEY_JORAH
oc() { openclaw --profile jorah "$@"; }
say() { printf '\n== %s\n' "$*"; }

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
[ -t 0 ] || { echo "Run this in an interactive terminal (ssh -t)."; exit 3; }

say "1. The key into the secret store as $ID"
if oc secrets store list 2>/dev/null | grep -q "$ID"; then
  echo "$ID already stored, kept."
else
  read -rs -p 'Paste the same API key you entered before (hidden): ' K; echo
  [ -n "$K" ] || { echo "Empty key. Stopping."; exit 3; }
  printf '%s' "$K" | oc secrets store set "$ID" --kind secret --value-file -
  unset K
fi
oc secrets store list

say "2. Point the profile anthropic:jorah at the stored key"
cat <<EOF
In OpenClaw's helper:
  - pick the credential for auth profile anthropic:jorah (its key field),
  - source: store, provider: default, id: $ID,
  - let preflight run, then answer yes to apply and yes to the one-way confirmation.
EOF
oc secrets configure --skip-provider-setup --agent main

say "3. Checks"
oc secrets reload || true
oc secrets audit --check && echo "Audit clean." || echo "Audit still has findings. Tell Claude, without pasting the key."
oc models auth list --agent main
