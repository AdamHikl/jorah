#!/usr/bin/env bash
# Runs on the Mac. Switches Jorah between the Max plan and the API key, or says which is set.
#
#   jorah-brain.sh status [--probe]   which lane is set; --probe also runs one test turn
#   jorah-brain.sh api                every agent on Jorah's Console key
#   jorah-brain.sh max                main and deep on Jorah's Claude login (Adam's Max plan)
#
# It runs scripts/pc/brain-lane.sh in /opt/jorah on the PC, as jorah, over the setup SSH key,
# like jorah-power.sh. The Mac HUD runs it from its app bundle (docs/adr/0009-hud-brain-switch.md).
# The last line is always "LANE: api", "LANE: max", "LANE: mixed" or "LANE: unknown".
#
# The PowerShell snippet is in single quotes on purpose: its $variables belong to PowerShell.
# shellcheck disable=SC2016
set -euo pipefail

PC_HOST="${JORAH_PC_HOST:-adamh@100.115.240.14}"
PC_KEY="${JORAH_PC_KEY:-$HOME/.ssh/jorah-pc-setup}"
SCRIPT=/opt/jorah/scripts/pc/brain-lane.sh

say() { printf '%s\n' "$*"; }
unknown() { say "FAILED: $*"; say "LANE: unknown"; exit 1; }

pc() {
    ssh -i "$PC_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 "$PC_HOST" "$@"
}

# Windows' shell drops inner quotes, so PowerShell gets its script base64-encoded.
distro_state() {
    local encoded
    encoded="$(printf '%s' '$ProgressPreference="SilentlyContinue"; if (((wsl.exe -l -q --running) -replace "`0","") -contains "jorah") { "running" } else { "stopped" }' \
        | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')"
    pc "powershell -NoProfile -NonInteractive -EncodedCommand $encoded" | tr -d '\r'
}

case "${1:-} ${2:-}" in
    "status " | "status --probe" | "api " | "max ") ;;
    *) say "usage: jorah-brain.sh status [--probe] | api | max"; exit 3 ;;
esac

state="$(distro_state)" || unknown "can't reach the PC over SSH"
# `wsl -d jorah` would start a paused distro, and the Gateway with it, so a stopped one is left alone.
[ "$state" = running ] || unknown "Jorah's distro is $state on the PC. Resume it first."

# The arguments are fixed words, checked above.
# shellcheck disable=SC2029
pc "wsl -d jorah -u jorah -- bash -l $SCRIPT $*" | tr -d '\r'
