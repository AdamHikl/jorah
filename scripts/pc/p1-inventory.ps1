# Jorah P1.0: read-only inventory of the PC. Changes nothing and reads no file contents.
# Paste this whole file into PowerShell. Run as Administrator to fill in the encryption and TPM lines.
# The result goes on the clipboard and to Desktop\jorah-inventory.txt. Anything it can't read says "unknown".

$out = New-Object System.Collections.Generic.List[string]
function Say($text) { $out.Add([string]$text) }
function Section($name) { Say ""; Say "== $name" }
function Try-Value($label, [scriptblock]$probe) {
  try {
    $value = & $probe 2>$null
    if ($null -eq $value -or "$value" -eq "") { Say "${label}: unknown" } else { Say "${label}: $(($value | Out-String).Trim())" }
  } catch { Say "${label}: unknown" }
}
function Tool-Version($name, $flag = "--version") {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if (-not $cmd) { Say "${name}: absent"; return }
  try { $v = (& $name $flag 2>&1 | Select-Object -First 1); Say "${name}: $v" } catch { Say "${name}: present, version unknown" }
}
function Hide-Home($path) { ([string]$path).Replace($env:USERPROFILE, "~") }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Say "Jorah PC inventory, P1.0"
Say "Ran as Administrator: $isAdmin"

Section "Windows"
Try-Value "Edition" { (Get-CimInstance Win32_OperatingSystem).Caption }
Try-Value "Build" { (Get-CimInstance Win32_OperatingSystem).BuildNumber }
Try-Value "Uptime hours" { [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1) }

Section "Hardware"
Try-Value "CPU" { (Get-CimInstance Win32_Processor | Select-Object -First 1).Name }
Try-Value "RAM GB" { [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1) }
Try-Value "C: free GB" { [math]::Round((Get-PSDrive C).Free / 1GB, 1) }
Try-Value "C: total GB" { [math]::Round(((Get-PSDrive C).Free + (Get-PSDrive C).Used) / 1GB, 1) }
Try-Value "GPU from nvidia-smi" { nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader }
Try-Value "Network adapters up" { Get-NetAdapter | Where-Object Status -eq "Up" | ForEach-Object { "$($_.InterfaceDescription), $($_.PhysicalMediaType), $($_.LinkSpeed)" } }

Section "Encryption and TPM"
if ($isAdmin) {
  Try-Value "TPM present and ready" { $t = Get-Tpm; "present=$($t.TpmPresent) ready=$($t.TpmReady)" }
  Try-Value "C: protection" { $b = Get-BitLockerVolume -MountPoint "C:"; "method=$($b.EncryptionMethod) status=$($b.ProtectionStatus) encrypted=$($b.EncryptionPercentage)%" }
} else {
  Say "TPM and C: protection: unknown, not run as Administrator"
}
Try-Value "Device encryption blocked by policy" { (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\BitLocker" -Name PreventDeviceEncryption -ErrorAction Stop).PreventDeviceEncryption }

Section "WSL"
Try-Value "wsl version" { (wsl --version) -replace "`0", "" | Where-Object { $_ -match "\S" } | Select-Object -First 2 }
Try-Value "wsl distros" { (wsl -l -v) -replace "`0", "" | Where-Object { $_ -match "\S" } }
Try-Value ".wslconfig exists" { Test-Path "$env:USERPROFILE\.wslconfig" }
Try-Value "Virtualization on" { (Get-CimInstance Win32_ComputerSystem).HypervisorPresent }

Section "Tools"
foreach ($tool in "git", "gh", "node", "npm", "python", "py", "uv", "docker", "tailscale", "openclaw", "claude", "ollama", "ffmpeg", "ssh") {
  if ($tool -eq "ssh") { Tool-Version $tool "-V" } else { Tool-Version $tool }
}

Section "Services matching Jorah's concerns"
$pattern = "openclaw|merlin|clawd|claude|ollama|docker|tailscale|sshd|ssh-agent|wsl|node"
Try-Value "Services" { Get-Service | Where-Object { $_.Name -match $pattern -or $_.DisplayName -match $pattern } | ForEach-Object { "$($_.Name), $($_.Status), $($_.StartType)" } }

Section "Scheduled tasks outside Microsoft's folder"
Try-Value "Tasks" { Get-ScheduledTask | Where-Object { $_.TaskPath -notlike "\Microsoft*" } | ForEach-Object { "$($_.TaskPath)$($_.TaskName), $($_.State)" } }

Section "Listening TCP ports, with the owning process name"
Try-Value "Ports" {
  Get-NetTCPConnection -State Listen | Sort-Object LocalPort -Unique | ForEach-Object {
    $proc = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    "$($_.LocalAddress):$($_.LocalPort) $proc"
  }
}

Section "Leftovers, by path only. No file was opened"
$skip = @("AppData", "node_modules", ".git", ".venv", "site-packages", "__pycache__")
$match = "merlin|openclaw|^\.clawd$|^certs$|\.key$|\.pem$|\.pfx$|^\.env$|^\.env\.|^id_rsa$|^id_ed25519$"
$clock = [Diagnostics.Stopwatch]::StartNew()
$queue = New-Object System.Collections.Queue
$queue.Enqueue(@($env:USERPROFILE, 0))
$hits = New-Object System.Collections.Generic.List[string]
while ($queue.Count -gt 0 -and $clock.Elapsed.TotalSeconds -lt 60) {
  $item = $queue.Dequeue()
  try { $entries = ([IO.DirectoryInfo]$item[0]).EnumerateFileSystemInfos() } catch { continue }
  try {
    foreach ($entry in $entries) {
      if ($entry.Name -match $match -and $hits.Count -lt 150) { $hits.Add((Hide-Home $entry.FullName)) }
      $isDir = $entry.Attributes -band [IO.FileAttributes]::Directory
      $isLink = $entry.Attributes -band [IO.FileAttributes]::ReparsePoint
      if ($isDir -and -not $isLink -and $skip -notcontains $entry.Name -and $item[1] -lt 5) { $queue.Enqueue(@($entry.FullName, ($item[1] + 1))) }
    }
  } catch { continue }
}
Say "Search covered everything to depth 5: $($queue.Count -eq 0). AppData and dependency folders skipped."
if ($hits.Count) { $hits | ForEach-Object { Say $_ } } else { Say "No matches" }
Try-Value "Top-level folders on C:" { Get-ChildItem C:\ -Directory -Force | Where-Object { $_.Name -notmatch '^\$|^(Windows|Program Files|Program Files \(x86\)|ProgramData|Users|PerfLogs|Recovery|System Volume Information|Documents and Settings|Config\.Msi|MSOCache)$' } | ForEach-Object { $_.Name } }

$report = $out -join "`r`n"
$file = Join-Path ([Environment]::GetFolderPath("Desktop")) "jorah-inventory.txt"
$report | Set-Content -Path $file -Encoding UTF8
try { $report | Set-Clipboard; $copied = "It is on the clipboard." } catch { $copied = "Copy it from that file." }
Write-Host $report
Write-Host ""
Write-Host "Saved to $file. $copied Nothing on this PC was changed apart from that file."
