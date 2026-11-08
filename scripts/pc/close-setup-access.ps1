# Jorah P1.2: close the setup access to Windows. Adam runs this, in PowerShell as Administrator,
# on the PC itself (not over SSH: step 2 stops the SSH server you'd be using).
#
#   .\close-setup-access.ps1              Password login off. Key login keeps working.
#   .\close-setup-access.ps1 -EndSetup    Also removes the jorah-pc-setup key and stops sshd,
#                                         so setup agents can't reach Windows until Adam reopens it.
#
# Reopen later: Set-Service sshd -StartupType Manual; Start-Service sshd, and put the key back
# in C:\ProgramData\ssh\administrators_authorized_keys from the backup this script prints.
param([switch]$EndSetup)
$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Run PowerShell as Administrator." }

$config = "C:\ProgramData\ssh\sshd_config"
$keys = "C:\ProgramData\ssh\administrators_authorized_keys"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

# 1. Password and keyboard-interactive login off.
Copy-Item $config "$config.pre-close-$stamp"
$lines = Get-Content $config
foreach ($setting in "PasswordAuthentication", "KbdInteractiveAuthentication") {
  $found = $false
  $lines = $lines | ForEach-Object {
    if ($_ -match "^\s*#?\s*$setting\b") { $found = $true; "$setting no" } else { $_ }
  }
  # A Match block at the end would swallow an appended line, so new settings go first.
  if (-not $found) { $lines = @("$setting no") + $lines }
}
Set-Content -Path $config -Value $lines -Encoding ascii
& "C:\Windows\System32\OpenSSH\sshd.exe" -t
if ($LASTEXITCODE -ne 0) {
  Copy-Item "$config.pre-close-$stamp" $config -Force
  throw "sshd rejected the new config, so the old one is back. Nothing changed."
}
Restart-Service sshd
Write-Host "Password login: off. Backup: $config.pre-close-$stamp"

# 2. Optional: end setup access entirely.
if ($EndSetup) {
  if (Test-Path $keys) {
    Copy-Item $keys "$keys.pre-close-$stamp"
    $kept = Get-Content $keys | Where-Object { $_ -notmatch "\bjorah-pc-setup\s*$" }
    Set-Content -Path $keys -Value $kept -Encoding ascii
    Write-Host "Removed the jorah-pc-setup key. Backup: $keys.pre-close-$stamp"
  }
  Stop-Service sshd
  Set-Service sshd -StartupType Disabled
  Write-Host "sshd: stopped and disabled."
}

Write-Host ""
Write-Host "Check from the Mac:"
Write-Host "  ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password adamh@100.115.240.14"
Write-Host "Expected: 'Permission denied (publickey)' now, or 'Connection refused' after -EndSetup."
