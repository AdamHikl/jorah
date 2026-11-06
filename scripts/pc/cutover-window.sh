#!/usr/bin/env bash
# Adam's part of the cutover window, docs/runbooks/cutover.md steps 8, 9 and 10, in one run.
# Run it as jorah, in a Terminal attached to no agent, after rotating the Telegram token (step 2):
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     wsl -d jorah -u jorah -- bash -l /opt/jorah/scripts/pc/cutover-window.sh
# It never prints a token. The patch applies only after Adam types y at its dry run.
# Safe to run again: a step already done is skipped.
set -euo pipefail

PATCH=/home/jorah/cutover/pc.json5
VOICE_TOKEN=/home/jorah/.config/jorah-voice/gateway-token
CONFIG=/home/jorah/.openclaw-jorah/openclaw.json
export CLAUDE_CONFIG_DIR=/home/jorah/.claude-jorah
oc() { openclaw --profile jorah "$@"; }
say() { printf '\n== %s\n' "$*"; }

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
[ -t 0 ] || { echo "Run this in an interactive terminal (ssh -t)."; exit 3; }
[ -f "$PATCH" ] || { echo "$PATCH is missing. Ask Claude to prepare it."; exit 3; }
if systemctl is-active --quiet openclaw-gateway || systemctl is-active --quiet jorah-gateway; then
  echo "A Gateway is already running. Stopping here."; exit 3
fi

has_entry() { oc secrets store list 2>/dev/null | grep -q "$1"; }

say "Step 8: secrets into the store"
if has_entry OPENCLAW_GATEWAY_TOKEN; then
  echo "OPENCLAW_GATEWAY_TOKEN already stored, kept."
else
  # A new Gateway token. jorah-voice gets the same value in its own file, mode 600.
  umask 077
  G=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
  printf '%s' "$G" | oc secrets store set OPENCLAW_GATEWAY_TOKEN --kind secret --value-file -
  printf '%s' "$G" > "$VOICE_TOKEN"; chmod 600 "$VOICE_TOKEN"
  unset G
fi
if has_entry TELEGRAM_BOT_TOKEN; then
  echo "TELEGRAM_BOT_TOKEN already stored, kept."
else
  read -rs -p 'New Telegram token from BotFather (hidden): ' T; echo
  [ -n "$T" ] || { echo "Empty token. Stopping."; exit 3; }
  printf '%s' "$T" | oc secrets store set TELEGRAM_BOT_TOKEN --kind secret --value-file -
  unset T
fi
oc secrets store list
[ -s "$VOICE_TOKEN" ] && ls -l "$VOICE_TOKEN" || echo "Voice token file missing: see cutover.md step 11, Voice."

say "Step 9: the PC patch"
if [ "$(grep -c /Users/ "$CONFIG" || true)" = 0 ] && [ "$(oc config get gateway.port 2>/dev/null)" = 43181 ]; then
  echo "Already applied, skipped."
else
  oc config patch --file "$PATCH" --dry-run
  read -r -p 'Apply this patch? [y/N] ' A
  [ "$A" = y ] || { echo "Not applied. Stopping."; exit 3; }
  oc config patch --file "$PATCH"
  oc config validate
  echo "Mac paths left in the config: $(grep -c /Users/ "$CONFIG" || true) (expected 0)"
fi
if oc models auth list 2>/dev/null | grep -q llama-cpp; then
  oc models auth logout llama-cpp:default --yes
fi
oc secrets audit --check || echo "Secrets audit not clean: tell Claude before going on."

say "Step 10: sign in to Claude, as Jorah"
echo "If a setup prompt offers a llama.cpp chat model, answer No."
claude auth login
oc models auth login --provider anthropic --method cli --set-default

say "Done. Tell Claude: \"window script done\". Claude starts the Gateway and checks it."
