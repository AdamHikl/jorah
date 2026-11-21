#!/usr/bin/env bash
# Runs on the Mac. Pauses Jorah on the PC to free its GPU, memory and CPU, and brings it back.
#
#   jorah-power.sh pause [--no-backup]   save, stop Jorah's services, stop the distro, stop Ollama
#   jorah-power.sh resume                start the distro again and wait for the Gateway
#   jorah-power.sh status                say what is running
#
# It uses the setup SSH key, so it stops working once setup access is closed
# (scripts/pc/close-setup-access.ps1 -EndSetup). See docs/adr/0006-hud-kill-switch.md.
#
# Pause only stops the `jorah` distro, not other WSL distros. Ollama is not part of Jorah:
# pause ends its Windows processes, and resume does not start it again.
#
# The PowerShell snippets are in single quotes on purpose: their $variables belong to PowerShell.
# shellcheck disable=SC2016
set -euo pipefail

PC_HOST="${JORAH_PC_HOST:-adamh@100.115.240.14}"
PC_KEY="${JORAH_PC_KEY:-$HOME/.ssh/jorah-pc-setup}"
UNITS="openclaw-gateway.service jorah-voice.service jorah-voice-qwen.service jorah-agentmemory.service"

say() { printf '%s\n' "$*"; }
die() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }

pc() {
    ssh -i "$PC_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 "$PC_HOST" "$@"
}

# Windows' shell drops inner quotes, so PowerShell gets its script base64-encoded.
win() {
    local encoded
    encoded="$(printf '%s' "\$ProgressPreference='SilentlyContinue'; $1" | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')"
    pc "powershell -NoProfile -NonInteractive -EncodedCommand $encoded"
}

in_distro() {
    # shellcheck disable=SC2029 # the arguments are meant to expand here
    pc "wsl -d jorah -u root -- $*"
}

# Prints "running" or "stopped". wsl.exe prints UTF-16, so the NULs are removed first.
distro_state() {
    win 'if (((wsl.exe -l -q --running) -replace "`0","") -contains "jorah") { "running" } else { "stopped" }' | tr -d '\r'
}

report_windows() {
    win '
$left = @(Get-Process -Name "ollama*" -ErrorAction SilentlyContinue).Count
"Ollama processes: $left"
$task = Get-ScheduledTask -TaskName "Jorah WSL" -ErrorAction SilentlyContinue
if ($task) { "Keep-alive task: $($task.State)" } else { "Keep-alive task: unknown (not found)" }
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) { "GPU memory used, total: " + (nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader) } else { "GPU memory: unknown (no nvidia-smi)" }
' | tr -d '\r'
}

pause() {
    local backup=1
    [ "${1:-}" = "--no-backup" ] && backup=0

    say "1/5 Reaching the PC"
    pc "echo ok" >/dev/null || die "can't reach the PC over SSH"

    if [ "$(distro_state)" = "running" ]; then
        if [ "$backup" = 1 ]; then
            say "2/5 Saving: verified backup (this can take a few minutes)"
            in_distro "systemctl start jorah-backup.service" \
                || die "the backup failed, so nothing was stopped. Check: journalctl -u jorah-backup.service"
            say "    backup done"
        else
            say "2/5 Saving: backup skipped, as asked"
        fi

        say "3/5 Stopping Jorah's services cleanly"
        in_distro "systemctl stop $UNITS" || die "a service did not stop, so the distro was left running"
        in_distro "sync" || true
    else
        say "2/5 The distro is already stopped: nothing to save"
        say "3/5 The distro is already stopped: no services to stop"
    fi

    say "4/5 Stopping the distro, its keep-alive task, and Ollama"
    win '
$ErrorActionPreference = "Stop"
Disable-ScheduledTask -TaskName "Jorah WSL" | Out-Null
Stop-ScheduledTask -TaskName "Jorah WSL"
wsl.exe --terminate jorah | Out-Null
Get-Process -Name "ollama*" -ErrorAction SilentlyContinue | Stop-Process -Force
' >/dev/null || die "the Windows step failed. Run: jorah-power.sh status"

    say "5/5 Checking"
    local state
    state="$(distro_state)"
    say "Distro: $state"
    report_windows
    [ "$state" = "stopped" ] || die "the distro is still running"
    say "PAUSED"
}

resume() {
    say "1/3 Reaching the PC"
    pc "echo ok" >/dev/null || die "can't reach the PC over SSH"

    say "2/3 Starting the distro and its keep-alive task"
    win '
$ErrorActionPreference = "Stop"
Enable-ScheduledTask -TaskName "Jorah WSL" | Out-Null
Start-ScheduledTask -TaskName "Jorah WSL"
' >/dev/null || die "could not start the keep-alive task"

    say "3/3 Waiting for the Gateway (up to 4 minutes)"
    local tries=0
    until [ "$(in_distro "systemctl is-active openclaw-gateway.service" 2>/dev/null | tr -d '\r')" = "active" ]; do
        tries=$((tries + 1))
        [ "$tries" -lt 48 ] || die "the Gateway is not active after 4 minutes. Run: jorah-power.sh status"
        sleep 5
    done
    status
    say "Ollama was not started: start it yourself if you want it."
    say "RESUMED"
}

status() {
    local state unit active
    state="$(distro_state)"
    say "Distro: $state"
    if [ "$state" = "running" ]; then
        for unit in $UNITS; do
            active="$(in_distro "systemctl is-active $unit" 2>/dev/null | tr -d '\r' || true)"
            say "$unit: ${active:-unknown}"
        done
    fi
    report_windows
}

case "${1:-}" in
    pause) shift; pause "$@" ;;
    resume) resume ;;
    status) status ;;
    *) die "usage: jorah-power.sh pause [--no-backup] | resume | status" ;;
esac
