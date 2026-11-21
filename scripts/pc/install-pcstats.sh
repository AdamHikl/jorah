#!/usr/bin/env bash
# Runs on the Mac. Installs the PC stats reader for the HUD's PC panel on Windows, over the setup
# SSH key, the way jorah-power.sh reaches the PC. See docs/adr/0008-hud-pc-stats.md.
#
#   install-pcstats.sh --dry-run   say what would change and check the PC. Writes nothing (default)
#   install-pcstats.sh --install   install or update, start, and check from the PC and from this Mac
#   install-pcstats.sh --status    tasks, listener, Serve route and one reading
#   install-pcstats.sh --undo      remove the Serve route, both tasks and the folder
#
# What --install changes on Windows:
#   C:\ProgramData\Jorah\pcstats\pcstats.ps1   from git HEAD, SHA-256 checked; only admins can write
#   task "Jorah PC Stats"   powershell -File pcstats.ps1, answers 127.0.0.1:43230
#   task "Jorah Core Temp"  starts the Core Temp already installed, so the CPU temperature is readable
#   Both tasks: user adamh, at boot with nobody signed in (S4U), highest privileges, again every
#   5 minutes if they stopped (IgnoreNew), no time limit.
#   Tailscale Serve https :43231 -> http://127.0.0.1:43230, tailnet only.
# Nothing in the jorah distro changes: its firewall keeps the jorah user away from both ports.
#
# The PowerShell snippets are in single quotes on purpose: their $variables belong to PowerShell.
# shellcheck disable=SC2016
set -euo pipefail

PC_HOST="${JORAH_PC_HOST:-adamh@100.115.240.14}"
PC_KEY="${JORAH_PC_KEY:-$HOME/.ssh/jorah-pc-setup}"
SERVE_URL="${JORAH_PCSTATS_URL:-https://rocket.tail1574a5.ts.net:43231/v1/stats}"
SOURCE="scripts/pc/pcstats.ps1"
tmp=""

say() { printf '%s\n' "$*"; }
die() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }

ssh_opts=(-i "$PC_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10)
# shellcheck disable=SC2029 # the command is meant to expand here
pc() { ssh "${ssh_opts[@]}" "$PC_HOST" "$@"; }

# Windows' shell drops inner quotes, so PowerShell gets its script base64-encoded.
win() {
    local encoded
    encoded="$(printf '%s' "\$ProgressPreference='SilentlyContinue'; $1" | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')"
    pc "powershell -NoProfile -NonInteractive -EncodedCommand $encoded" | tr -d '\r'
}

COMMON='
$Dir = "C:\ProgramData\Jorah\pcstats"
$CoreTemp = "C:\Program Files\Core Temp\Core Temp.exe"
function Show-Task($name) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $t) { return "${name}: not installed" }
    $reps = ($t.Triggers | ForEach-Object { if ($_.Repetition.Interval) { "every $($_.Repetition.Interval)" } else { "at boot" } }) -join ", "
    "${name}: $($t.State), $($t.Principal.UserId) $($t.Principal.LogonType) $($t.Principal.RunLevel), $reps, $($t.Settings.MultipleInstances)"
}
function Show-Reading {
    try {
        $j = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 http://127.0.0.1:43230/v1/stats).Content | ConvertFrom-Json
        "Reading at $($j.at): CPU $($j.cpu.percent)%, CPU temperature $(if ($null -ne $j.cpu.temperatureC) { "$($j.cpu.temperatureC) C ($($j.cpu.temperatureSource))" } else { "unknown" }), GPU $(if ($j.gpu) { "$($j.gpu.percent)% $($j.gpu.temperatureC) C" } else { "unknown" }), disks $(($j.disks | ForEach-Object { "$($_.drives -join "") $($_.temperatureC) C" }) -join ", ")"
        foreach ($p in $j.unknown.PSObject.Properties) { "  unknown $($p.Name): $($p.Value)" }
    } catch { "Reading: none on 127.0.0.1:43230 ($($_.Exception.Message))" }
}
'

source_blob() {
    git rev-parse --verify -q "HEAD:$SOURCE" >/dev/null || die "$SOURCE is not in HEAD"
    git fetch -q origin main || die "can't fetch origin/main"
    git merge-base --is-ancestor HEAD origin/main || die "HEAD is not on origin/main. Install from a checkout of main"
}

dry_run() {
    say "Dry run: nothing changes."
    pc "echo ok" >/dev/null || die "can't reach the PC over SSH"
    git rev-parse --verify -q "HEAD:$SOURCE" >/dev/null || die "$SOURCE is not in HEAD"
    say "Would copy $SOURCE at $(git rev-parse --short HEAD) (SHA-256 $(git show "HEAD:$SOURCE" | shasum -a 256 | cut -c1-16)...) to C:\\ProgramData\\Jorah\\pcstats\\pcstats.ps1"
    say "Would register tasks \"Jorah PC Stats\" and \"Jorah Core Temp\" (adamh, S4U, highest, boot + every 5 min, IgnoreNew)"
    say "Would add Serve https :43231 -> http://127.0.0.1:43230 (tailnet only)"
    say "Now on the PC:"
    win "$COMMON"'
"Core Temp: " + $(if (Test-Path $CoreTemp) { (Get-Item $CoreTemp).VersionInfo.FileVersion } else { "NOT FOUND" })
"nvidia-smi: " + $(if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "found" } else { "not found" })
"Folder: " + $(if (Test-Path $Dir) { "exists" } else { "absent" })
Show-Task "Jorah PC Stats"
Show-Task "Jorah Core Temp"
$used = @(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 43230, 43231 } | ForEach-Object { "$($_.LocalAddress):$($_.LocalPort) $($_.State) pid $($_.OwningProcess)" })
"Ports 43230/43231 in use: " + $(if ($used.Count) { $used -join ", " } else { "none" })
"Serve routes: " + ((tailscale serve status 2>&1 | Select-String "^https") -join "; ")
'
}

install() {
    source_blob
    local sha
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    git show "HEAD:$SOURCE" >"$tmp/pcstats.ps1"
    sha="$(shasum -a 256 "$tmp/pcstats.ps1" | cut -d' ' -f1)"

    say "1/6 Reaching the PC"
    pc "echo ok" >/dev/null || die "can't reach the PC over SSH"

    say "2/6 Folder, writable by admins only; stopping the reader if it runs"
    win "$COMMON"'
$ErrorActionPreference = "Stop"
if (-not (Test-Path $CoreTemp)) { throw "Core Temp is not at $CoreTemp" }
if (Get-ScheduledTask -TaskName "Jorah PC Stats" -ErrorAction SilentlyContinue) { Stop-ScheduledTask -TaskName "Jorah PC Stats" }
New-Item -ItemType Directory -Force $Dir | Out-Null
icacls $Dir /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-32-545:(OI)(CI)RX" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls failed" }
"    folder ready"
' || die "the folder step failed"

    say "3/6 Copying pcstats.ps1 ($(git rev-parse --short HEAD)) and checking its SHA-256"
    scp -q "${ssh_opts[@]}" "$tmp/pcstats.ps1" "$PC_HOST:C:/ProgramData/Jorah/pcstats/pcstats.ps1.new" || die "copy failed"
    win "$COMMON"'
$ErrorActionPreference = "Stop"
$got = (Get-FileHash "$Dir\pcstats.ps1.new" -Algorithm SHA256).Hash.ToLower()
if ($got -ne "'"$sha"'") { Remove-Item "$Dir\pcstats.ps1.new"; throw "SHA-256 mismatch: $got" }
Move-Item -Force "$Dir\pcstats.ps1.new" "$Dir\pcstats.ps1"
"    SHA-256 matches git"
' || die "the copy did not match git, so nothing was installed"

    say "4/6 Registering the two tasks"
    win "$COMMON"'
$ErrorActionPreference = "Stop"
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
function Triggers { @((New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5))) }
$stats = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Dir\pcstats.ps1`""
$core = New-ScheduledTaskAction -Execute $CoreTemp -WorkingDirectory (Split-Path $CoreTemp)
Register-ScheduledTask -TaskName "Jorah PC Stats" -Description "Jorah HUD: read-only PC stats on 127.0.0.1:43230 (docs/adr/0008-hud-pc-stats.md)" `
    -Action $stats -Trigger (Triggers) -Principal $principal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName "Jorah Core Temp" -Description "Jorah HUD: runs Core Temp with nobody signed in, for the CPU temperature (docs/adr/0008-hud-pc-stats.md)" `
    -Action $core -Trigger (Triggers) -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName "Jorah Core Temp"
Start-ScheduledTask -TaskName "Jorah PC Stats"
Show-Task "Jorah PC Stats"
Show-Task "Jorah Core Temp"
' || die "registering the tasks failed"

    say "5/6 Serve route :43231, tailnet only"
    pc "tailscale serve --bg --yes --https=43231 http://127.0.0.1:43230" >/dev/null || die "tailscale serve failed"
    local route
    route="$(win '(tailscale serve status 2>&1 | Select-String "43231") -join " "')"
    say "    $route"
    case "$route" in
        *"tailnet only"*) ;;
        *) die "the :43231 route is not marked tailnet only. Undo with --undo" ;;
    esac

    say "6/6 Checking, on the PC and from this Mac"
    sleep 12
    win "$COMMON"'Show-Reading'
    local code
    code="$(curl -s -o "$tmp/reading.json" -w '%{http_code}' --max-time 20 "$SERVE_URL" || true)"
    [ "$code" = "200" ] || die "from this Mac, $SERVE_URL answered ${code:-nothing}"
    say "From this Mac: 200, $(wc -c <"$tmp/reading.json" | tr -d ' ') bytes"
    say "INSTALLED"
}

status() {
    win "$COMMON"'
Show-Task "Jorah PC Stats"
Show-Task "Jorah Core Temp"
"Core Temp running: " + [bool](Get-Process -Name "Core Temp" -ErrorAction SilentlyContinue)
"Serve: " + ((tailscale serve status 2>&1 | Select-String "43231") -join " ")
Show-Reading
if (Test-Path "$Dir\pcstats.log") { "Log, last lines:"; Get-Content "$Dir\pcstats.log" -Tail 5 }
'
}

undo() {
    say "Removing the Serve route, both tasks and the folder"
    pc "tailscale serve --https=43231 off" >/dev/null 2>&1 || say "    no Serve route on :43231"
    win "$COMMON"'
foreach ($name in "Jorah PC Stats", "Jorah Core Temp") {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $name
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        "    removed task $name"
    }
}
if (Test-Path $Dir) { Remove-Item -Recurse -Force $Dir; "    removed $Dir" }
$parent = Split-Path $Dir
if ((Test-Path $parent) -and -not (Get-ChildItem $parent -Force)) { Remove-Item $parent; "    removed empty $parent" }
"Core Temp still running: " + [bool](Get-Process -Name "Core Temp" -ErrorAction SilentlyContinue)
'
    say "UNDONE"
}

case "${1:---dry-run}" in
    --dry-run) dry_run ;;
    --install) install ;;
    --status) status ;;
    --undo) undo ;;
    *) die "usage: install-pcstats.sh [--dry-run | --install | --status | --undo]" ;;
esac
