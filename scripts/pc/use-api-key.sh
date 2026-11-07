#!/usr/bin/env bash
# Move every Jorah agent from the Max login to the Anthropic API key (config/pc/api-lane.patch.json5).
# Run it as jorah, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     wsl -d jorah -u jorah -- bash -l /opt/jorah/scripts/pc/use-api-key.sh
# It never prints the key. The key goes into the secret store, never into an auth profile as plain text:
# main and background get the profile anthropic:jorah-store, which only references it
# (config/pc/api-key-ref.plan.json). The patch applies only after Adam types y at its dry run.
# Safe to run again: a key already stored is kept.
set -euo pipefail

ID=ANTHROPIC_API_KEY_JORAH
PROFILE=anthropic:jorah-store
PLAN=/opt/jorah/config/pc/api-key-ref.plan.json
PATCH=/opt/jorah/config/pc/api-lane.patch.json5
oc() { openclaw --profile jorah "$@"; }
say() { printf '\n== %s\n' "$*"; }

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
[ -t 0 ] || { echo "Run this in an interactive terminal (ssh -t)."; exit 3; }
for f in "$PLAN" "$PATCH"; do [ -f "$f" ] || { echo "$f is missing. Ask Claude to copy it."; exit 3; }; done

say "1. The API key, into the secret store as $ID"
if oc secrets store list 2>/dev/null | grep -q "$ID"; then
  echo "$ID already stored, kept."
else
  read -rs -p "Paste Jorah's Console key (hidden): " K; echo
  [ -n "$K" ] || { echo "Empty key. Stopping."; exit 3; }
  printf '%s' "$K" | oc secrets store set "$ID" --kind secret --value-file -
  unset K
fi

say "2. Profiles that reference it, for main and background"
oc secrets apply --from "$PLAN" --dry-run
oc secrets apply --from "$PLAN"
for a in main background; do oc models auth order set --provider anthropic --agent "$a" "$PROFILE"; done

say "3. Every model onto the key"
oc config patch --file "$PATCH" --dry-run
read -r -p 'Apply this patch? [y/N] ' A
[ "$A" = y ] || { echo "Not applied. Jorah stays on the Max login."; exit 3; }
oc config patch --file "$PATCH"
oc config validate

say "4. Checks"
oc secrets audit --check && echo "Audit clean." || echo "The audit flagged something. Tell Claude, without pasting the key."
oc models auth list --agent main
