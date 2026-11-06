#!/usr/bin/env bash
# Move every Jorah agent from the Max login to the Anthropic API key (config/pc/api-lane.patch.json5).
# Run it as jorah, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     wsl -d jorah -u jorah -- bash -l /opt/jorah/scripts/pc/use-api-key.sh
# It never prints the key. The patch applies only after Adam types y at its dry run.
# Safe to run again: a key already stored is kept.
set -euo pipefail

PATCH=/opt/jorah/config/pc/api-lane.patch.json5
PROFILE=anthropic:jorah
oc() { openclaw --profile jorah "$@"; }
say() { printf '\n== %s\n' "$*"; }

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
[ -t 0 ] || { echo "Run this in an interactive terminal (ssh -t)."; exit 3; }
[ -f "$PATCH" ] || { echo "$PATCH is missing. Ask Claude to copy it."; exit 3; }

say "1. The API key, into main's store as $PROFILE"
if oc models auth list --agent main 2>/dev/null | grep -q "$PROFILE"; then
  echo "$PROFILE already stored, kept."
else
  echo "Paste Jorah's Console key at the prompt. It doesn't echo."
  oc models auth paste-api-key --provider anthropic --agent main --profile-id "$PROFILE"
fi
oc models auth order set --provider anthropic --agent main "$PROFILE"
oc models auth order set --provider anthropic --agent background "$PROFILE" \
  || echo "background order not set: it falls back to the global order the patch sets."

say "2. Every model onto the key"
oc config patch --file "$PATCH" --dry-run
read -r -p 'Apply this patch? [y/N] ' A
[ "$A" = y ] || { echo "Not applied. Jorah stays on the Max login."; exit 3; }
oc config patch --file "$PATCH"
oc config validate

say "3. Checks"
oc secrets audit --check || echo "The audit flagged something. Tell Claude, without pasting the key."
oc models auth list --agent main
echo
echo "Done. Send Jorah a message in Telegram. If the reply still comes from the Max login"
echo "(Claude's usage page moves, the Console's doesn't), tell Claude."
