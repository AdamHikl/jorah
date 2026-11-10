#!/usr/bin/env bash
# Applies config/pc/approvals.patch.json5 with Adam's Telegram chat ID filled in from Jorah's own
# config (channels.telegram.allowFrom), so the ID stays out of the repo. Run as jorah.
#   bash /opt/jorah/scripts/pc/apply-approvals.sh            dry run
#   bash /opt/jorah/scripts/pc/apply-approvals.sh --apply    apply, with a config backup
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
OC=(/usr/local/bin/openclaw --profile jorah)
id="$("${OC[@]}" config get channels.telegram.allowFrom --json | python3 -c 'import json,sys; v=json.load(sys.stdin); print(v[0] if isinstance(v,list) and len(v)==1 else "")')"
[[ "$id" =~ ^[0-9]+$ ]] || { echo "Expected exactly one numeric Telegram allowFrom entry."; exit 4; }
mkdir -p "$HOME/.cache/jorah" && chmod 700 "$HOME/.cache/jorah"
patch="$(mktemp "$HOME/.cache/jorah/approvals.XXXXXX.json5")"
trap 'rm -f "$patch"' EXIT
sed "s/TELEGRAM_CHAT_ID/$id/" /opt/jorah/config/pc/approvals.patch.json5 > "$patch"
if [ "${1:-}" = "--apply" ]; then
  cp -p "$HOME/.openclaw-jorah/openclaw.json" "$HOME/.openclaw-jorah/openclaw.json.pre-approvals"
  "${OC[@]}" config patch --file "$patch"
  "${OC[@]}" config get approvals.plugin --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("approvals.plugin:", d["enabled"], d["mode"], d["agentFilter"], [t["channel"] for t in d["targets"]])'
else
  "${OC[@]}" config patch --file "$patch" --dry-run
fi
