# Jorah PC stats: a read-only reader of the PC's load, for the Mac HUD's PC panel.
#
# Runs on Windows in Windows PowerShell 5.1, which ships with Windows: nothing to download.
# scripts/pc/install-pcstats.sh installs it as the task "Jorah PC Stats". See
# docs/adr/0008-hud-pc-stats.md and docs/contracts/jorah-pcstats-v1.md.
#
#   pcstats.ps1          answer GET /v1/stats on 127.0.0.1:43230 (Tailscale Serve :43231 in front)
#   pcstats.ps1 -Once    print one reading as JSON and exit. Changes nothing
#
# It answers one fixed request, reads nothing from a request but its first line, and never
# runs anything a request names. A reading that fails is null with a short reason under
# "unknown", never 0. The rates (CPU, network, disk) are averages since the previous request.
param([switch]$Once, [int]$Port = 43230)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Invariant = [Globalization.CultureInfo]::InvariantCulture
$LogPath = if ($PSScriptRoot) { Join-Path $PSScriptRoot 'pcstats.log' } else { $null }

function Write-Log([string]$text) {
    if ($Once -or -not $LogPath) { return }
    try {
        if ((Test-Path $LogPath) -and (Get-Item $LogPath).Length -gt 512KB) {
            Move-Item -Force $LogPath "$LogPath.old"
        }
        $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss', $Invariant)
        Add-Content -Path $LogPath -Value "$stamp $text" -Encoding UTF8
    } catch { }
}

function Round1($value) { if ($null -eq $value) { $null } else { [math]::Round([double]$value, 1) } }
function Clamp100($value) { [math]::Max(0.0, [math]::Min(100.0, [double]$value)) }
function IsoTime([datetime]$when) { $when.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", $Invariant) }

# --- Counters, made once. A rate counter's NextValue() is the average since its previous call.

function New-Counter([string]$category, [string]$name, [string]$instance) {
    $counter = New-Object System.Diagnostics.PerformanceCounter($category, $name, $instance, $true)
    [void]$counter.NextValue()
    $counter
}

$Static = @{ cpuName = $null; memoryTotal = $null }
try { $Static.cpuName = ((Get-CimInstance Win32_Processor | Select-Object -First 1).Name).Trim() } catch { }
try { $Static.memoryTotal = [int64](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory } catch { }

$Counters = @{ cpu = $null; memoryAvailable = $null; net = @(); disks = @()
              netAt = [datetime]::MinValue; diskAt = [datetime]::MinValue; ratesAt = [datetime]::MinValue }

try { $Counters.cpu = New-Counter 'Processor Information' '% Processor Utility' '_Total' }
catch { try { $Counters.cpu = New-Counter 'Processor' '% Processor Time' '_Total' } catch { } }
try { $Counters.memoryAvailable = New-Object System.Diagnostics.PerformanceCounter('Memory', 'Available Bytes', '', $true) } catch { }

# Physical adapters that are up. Counter instance names write ( ) # / \ as [ ] _ _ _.
function Update-NetCounters {
    if (((Get-Date) - $Counters.netAt).TotalSeconds -lt 30) { return }
    $Counters.netAt = Get-Date
    $list = @()
    try {
        $known = (New-Object System.Diagnostics.PerformanceCounterCategory 'Network Interface').GetInstanceNames()
        foreach ($adapter in @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up')) {
            $instance = $adapter.InterfaceDescription.Replace('(', '[').Replace(')', ']').Replace('#', '_').Replace('/', '_').Replace('\', '_')
            if ($known -notcontains $instance) { continue }
            $old = @($Counters.net | Where-Object { $_.instance -eq $instance })
            if ($old.Count -gt 0) { $list += $old[0]; continue }
            $list += @{
                name = $adapter.Name
                instance = $instance
                down = New-Counter 'Network Interface' 'Bytes Received/sec' $instance
                up = New-Counter 'Network Interface' 'Bytes Sent/sec' $instance
            }
        }
    } catch { }
    $Counters.net = $list
}

# One entry per physical disk. Instance names are "<disk number> <letters>", e.g. "1 C:".
function Update-DiskCounters {
    if (((Get-Date) - $Counters.diskAt).TotalSeconds -lt 300) { return }
    $Counters.diskAt = Get-Date
    $list = @()
    try {
        $physical = @{}
        foreach ($disk in @(Get-PhysicalDisk)) { $physical[[string]$disk.DeviceId] = $disk }
        $known = (New-Object System.Diagnostics.PerformanceCounterCategory 'PhysicalDisk').GetInstanceNames()
        foreach ($instance in ($known | Where-Object { $_ -ne '_Total' } | Sort-Object)) {
            $parts = $instance -split ' '
            $number = $parts[0]
            $letters = @($parts | Select-Object -Skip 1 | Where-Object { $_ -match '^[A-Z]:$' })
            if ($letters.Count -eq 0) { continue }
            $kind = $null; $model = $null
            if ($physical.ContainsKey($number)) {
                $disk = $physical[$number]
                $model = ([string]$disk.FriendlyName).Trim()
                if ([string]$disk.MediaType -eq 'SSD' -or [string]$disk.BusType -eq 'NVMe') { $kind = 'ssd' }
                elseif ([string]$disk.MediaType -eq 'HDD') { $kind = 'hdd' }
            }
            $list += @{
                number = $number; drives = $letters; model = $model; kind = $kind
                idle = New-Counter 'PhysicalDisk' '% Idle Time' $instance
                read = New-Counter 'PhysicalDisk' 'Disk Read Bytes/sec' $instance
                write = New-Counter 'PhysicalDisk' 'Disk Write Bytes/sec' $instance
            }
        }
    } catch { }
    $Counters.disks = @($list | Sort-Object { $_.drives[0] })
}

# --- Disk temperatures: SMART through Get-StorageReliabilityCounter, which needs an elevated
# token and takes over a second, so it runs beside the server, once a minute at most.

$DiskTemps = @{ values = @{}; at = $null; error = 'not read yet'; job = $null; startedAt = $null; runspace = $null }

$DiskTempScript = {
    Get-PhysicalDisk | Get-StorageReliabilityCounter |
        ForEach-Object { [pscustomobject]@{ id = [string]$_.DeviceId; temperature = $_.Temperature } }
}

function Update-DiskTemps([switch]$Wait) {
    $job = $DiskTemps.job
    if ($null -ne $job) {
        if ($Wait) { [void]$job.handle.AsyncWaitHandle.WaitOne(15000) }
        if ($job.handle.IsCompleted) {
            try {
                $values = @{}
                foreach ($row in $job.ps.EndInvoke($job.handle)) {
                    if ($null -ne $row.temperature -and $row.temperature -gt 0 -and $row.temperature -lt 120) {
                        $values[$row.id] = [double]$row.temperature
                    }
                }
                $DiskTemps.values = $values
                $DiskTemps.at = Get-Date
                $DiskTemps.error = if ($values.Count -eq 0) { 'the disks report no temperature' } else { $null }
            } catch {
                $DiskTemps.error = 'reading SMART failed (needs an elevated task)'
            } finally {
                $job.ps.Dispose()
                $DiskTemps.job = $null
            }
        } elseif (((Get-Date) - $DiskTemps.startedAt).TotalSeconds -gt 30) {
            try { $job.ps.Stop(); $job.ps.Dispose(); $DiskTemps.runspace.Dispose() } catch { }
            $DiskTemps.runspace = $null
            $DiskTemps.job = $null
            $DiskTemps.error = 'reading SMART timed out'
        }
        return
    }
    if ($null -ne $DiskTemps.at -and ((Get-Date) - $DiskTemps.at).TotalSeconds -lt 60) { return }
    # One runspace for the life of the reader, so the Storage module loads once.
    if ($null -eq $DiskTemps.runspace -or $DiskTemps.runspace.RunspaceStateInfo.State -ne 'Opened') {
        $DiskTemps.runspace = [runspacefactory]::CreateRunspace()
        $DiskTemps.runspace.Open()
    }
    $ps = [powershell]::Create()
    $ps.Runspace = $DiskTemps.runspace
    [void]$ps.AddScript($DiskTempScript)
    $DiskTemps.job = @{ ps = $ps; handle = $ps.BeginInvoke() }
    $DiskTemps.startedAt = Get-Date
    if ($Wait) { Update-DiskTemps -Wait }
}

# --- CPU temperature from Core Temp's shared memory (CORE_TEMP_SHARED_DATA, Core Temp 1.x):
# uiLoad[256] @0, uiTjMax[128] @1024, uiCoreCnt @1536, uiCPUCnt @1540, fTemp[256] @1544,
# ucFahrenheit @2684, ucDeltaToTjMax @2685. Core Temp has to be running in the same session.

function Read-CoreTemp {
    if (-not (Get-Process -Name 'Core Temp' -ErrorAction SilentlyContinue)) {
        return @{ error = 'Core Temp is not running' }
    }
    $map = $null; $view = $null
    try {
        $map = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('CoreTempMappingObject',
            [System.IO.MemoryMappedFiles.MemoryMappedFileRights]::Read)
        $view = $map.CreateViewAccessor(0, 2686, [System.IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
        $cores = [int]$view.ReadUInt32(1536)
        $cpus = [int]$view.ReadUInt32(1540)
        if ($cores -lt 1 -or $cpus -lt 1 -or ($cores * $cpus) -gt 256) {
            return @{ error = 'Core Temp shares no core count yet' }
        }
        $fahrenheit = $view.ReadByte(2684) -eq 1
        $toTjMax = $view.ReadByte(2685) -eq 1
        $temps = @()
        for ($cpu = 0; $cpu -lt $cpus; $cpu++) {
            $tjMax = [double]$view.ReadUInt32(1024 + 4 * $cpu)
            for ($core = 0; $core -lt $cores; $core++) {
                $t = [double]$view.ReadSingle(1544 + 4 * ($cpu * $cores + $core))
                if ($toTjMax) { $t = $tjMax - $t }
                if ($fahrenheit) { $t = ($t - 32) * 5 / 9 }
                if ($t -gt 5 -and $t -lt 125) { $temps += $t }
            }
        }
        if ($temps.Count -eq 0) { return @{ error = 'Core Temp shares no plausible temperature' } }
        return @{ hottest = ($temps | Measure-Object -Maximum).Maximum; cores = $temps.Count }
    } catch {
        return @{ error = 'Core Temp is running but shares no readings in this session' }
    } finally {
        if ($view) { $view.Dispose() }
        if ($map) { $map.Dispose() }
    }
}

# --- GPU through nvidia-smi (about 70 ms).

$NvidiaSmi = (Get-Command nvidia-smi -ErrorAction SilentlyContinue).Source

function ParseNumber([string]$text) {
    $text = $text.Trim()
    if ($text -eq '' -or $text -match 'N/A|Not Supported|Unknown|Error') { return $null }
    $value = 0.0
    if ([double]::TryParse($text, [Globalization.NumberStyles]::Float, $Invariant, [ref]$value)) { return $value }
    return $null
}

function Read-Gpu {
    if (-not $NvidiaSmi) { return @{ error = 'nvidia-smi is not installed' } }
    # Windows PowerShell turns any stderr line of a native command into a terminating error under Stop.
    $ErrorActionPreference = 'Continue'
    try {
        # All of the output, then the first line: stopping the pipeline early would end nvidia-smi.
        $lines = @(& $NvidiaSmi '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed' '--format=csv,noheader,nounits' 2>$null)
        if ($LASTEXITCODE -ne 0 -or $lines.Count -eq 0) { return @{ error = "nvidia-smi failed (exit $LASTEXITCODE)" } }
        $line = [string]$lines[0]
        $f = $line -split ','
        if ($f.Count -lt 7) { return @{ error = 'nvidia-smi gave an unexpected line' } }
        $used = ParseNumber $f[2]; $total = ParseNumber $f[3]
        return @{ value = [ordered]@{
            name = $f[0].Trim()
            percent = ParseNumber $f[1]
            memoryUsedBytes = if ($null -ne $used) { [int64]($used * 1MB) } else { $null }
            memoryTotalBytes = if ($null -ne $total) { [int64]($total * 1MB) } else { $null }
            temperatureC = ParseNumber $f[4]
            powerW = Round1 (ParseNumber $f[5])
            fanPercent = ParseNumber $f[6]
        } }
    } catch {
        return @{ error = 'nvidia-smi failed' }
    }
}

# --- One reading.

function Read-Rates([scriptblock]$reader) {
    try { & $reader } catch { $null }
}

function Get-Stats {
    $unknown = [ordered]@{}
    Update-NetCounters
    Update-DiskCounters
    Update-DiskTemps -Wait:$Once

    # A rate read long after the last one is a long average: read once to restart, then again.
    if (((Get-Date) - $Counters.ratesAt).TotalSeconds -gt 10) {
        foreach ($c in @($Counters.cpu) + @($Counters.net | ForEach-Object { $_.down; $_.up }) +
                 @($Counters.disks | ForEach-Object { $_.idle; $_.read; $_.write })) {
            if ($null -ne $c) { try { [void]$c.NextValue() } catch { } }
        }
        Start-Sleep -Milliseconds 700
    }
    $Counters.ratesAt = Get-Date

    # CPU
    $cpuPercent = $null
    if ($Counters.cpu) { $cpuPercent = Read-Rates { Round1 (Clamp100 $Counters.cpu.NextValue()) } }
    if ($null -eq $cpuPercent) { $unknown['cpu.percent'] = 'the CPU counter is missing' }
    $coreTemp = Read-CoreTemp
    $cpuTemp = $null; $cpuTempSource = $null
    if ($coreTemp.ContainsKey('hottest')) {
        $cpuTemp = Round1 $coreTemp.hottest
        $cpuTempSource = "Core Temp, hottest of $($coreTemp.cores) cores"
    } else {
        $unknown['cpu.temperatureC'] = $coreTemp.error
    }

    # Memory
    $memory = $null
    try {
        if ($null -eq $Static.memoryTotal -or $null -eq $Counters.memoryAvailable) { throw 'missing' }
        $available = [int64]$Counters.memoryAvailable.RawValue
        $memory = [ordered]@{ usedBytes = [int64]($Static.memoryTotal - $available); totalBytes = $Static.memoryTotal }
    } catch { $unknown['memory'] = 'the memory counter is missing' }

    # GPU
    $gpuRead = Read-Gpu
    $gpu = $null
    if ($gpuRead.ContainsKey('value')) { $gpu = $gpuRead.value } else { $unknown['gpu'] = $gpuRead.error }

    # Network: every physical adapter that is up, summed.
    $network = $null
    if ($Counters.net.Count -gt 0) {
        try {
            $down = 0.0; $up = 0.0
            foreach ($n in $Counters.net) { $down += $n.down.NextValue(); $up += $n.up.NextValue() }
            $network = [ordered]@{
                downBytesPerSec = [math]::Round($down); upBytesPerSec = [math]::Round($up)
                adapters = [object[]]@($Counters.net | ForEach-Object { $_.name })
            }
        } catch { $unknown['network'] = 'reading the adapter counters failed' }
    } else { $unknown['network'] = 'no physical network adapter is up' }

    # Disks
    $disks = @()
    foreach ($d in $Counters.disks) {
        $used = $null; $total = $null
        try {
            $total = [int64]0; $free = [int64]0
            foreach ($letter in $d.drives) {
                $info = New-Object System.IO.DriveInfo($letter)
                if ($info.IsReady) { $total += $info.TotalSize; $free += $info.TotalFreeSpace }
            }
            if ($total -gt 0) { $used = $total - $free } else { $total = $null }
        } catch { $total = $null }
        $busy = Read-Rates { Round1 (Clamp100 (100 - $d.idle.NextValue())) }
        $read = Read-Rates { [math]::Round($d.read.NextValue()) }
        $write = Read-Rates { [math]::Round($d.write.NextValue()) }
        $temp = $null; $tempAt = $null
        if ($DiskTemps.values.ContainsKey($d.number)) {
            $temp = $DiskTemps.values[$d.number]; $tempAt = IsoTime $DiskTemps.at
        } else {
            $unknown["disks.$($d.drives -join '').temperatureC"] = if ($DiskTemps.error) { $DiskTemps.error } else { 'this disk reports no temperature' }
        }
        $disks += [ordered]@{
            drives = [object[]]$d.drives; model = $d.model; kind = $d.kind
            usedBytes = $used; totalBytes = $total
            readBytesPerSec = $read; writeBytesPerSec = $write; busyPercent = $busy
            temperatureC = $temp; temperatureAt = $tempAt
        }
    }
    if ($disks.Count -eq 0) { $unknown['disks'] = 'no disk counters' }

    [ordered]@{
        schema = 'jorah-pcstats/1'
        at = IsoTime (Get-Date)
        cpu = [ordered]@{ name = $Static.cpuName; percent = $cpuPercent; temperatureC = $cpuTemp; temperatureSource = $cpuTempSource }
        memory = $memory
        gpu = $gpu
        network = $network
        disks = [object[]]$disks
        unknown = $unknown
    }
}

if ($Once) {
    ConvertTo-Json -InputObject (Get-Stats) -Depth 6
    return
}

# --- The server: one request at a time, one fixed answer.

function Send-Response($stream, [int]$code, [string]$reason, [string]$body) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($body)
    $head = "HTTP/1.1 $code $reason`r`nContent-Type: application/json; charset=utf-8`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`nConnection: close`r`n`r`n"
    $headBytes = [Text.Encoding]::ASCII.GetBytes($head)
    $stream.Write($headBytes, 0, $headBytes.Length)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()
}

$Cache = @{ json = $null; at = [datetime]::MinValue }

function Serve-Client($client) {
    $client.ReceiveTimeout = 3000
    $client.SendTimeout = 3000
    $stream = $client.GetStream()
    $buffer = New-Object byte[] 8192
    $count = 0
    $head = ''
    while ($count -lt $buffer.Length) {
        $read = $stream.Read($buffer, $count, $buffer.Length - $count)
        if ($read -le 0) { break }
        $count += $read
        $head = [Text.Encoding]::ASCII.GetString($buffer, 0, $count)
        if ($head.Contains("`r`n`r`n")) { break }
    }
    $first = ($head -split "`r`n", 2)[0]
    if ($first -ceq 'GET /v1/stats HTTP/1.1' -or $first -ceq 'GET /v1/stats HTTP/1.0') {
        if (((Get-Date) - $Cache.at).TotalSeconds -ge 1) {
            $Cache.json = ConvertTo-Json -InputObject (Get-Stats) -Depth 6 -Compress
            $Cache.at = Get-Date
        }
        Send-Response $stream 200 'OK' $Cache.json
    } elseif ($first -cmatch '^GET ') {
        Send-Response $stream 404 'Not Found' '{"error":"only GET /v1/stats"}'
    } else {
        Send-Response $stream 405 'Method Not Allowed' '{"error":"only GET /v1/stats"}'
    }
}

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
$listener.Server.ExclusiveAddressUse = $true
try {
    $listener.Start()
} catch {
    Write-Log "FAILED: could not listen on 127.0.0.1:$Port ($($_.Exception.Message))"
    exit 1
}
Write-Log "listening on 127.0.0.1:$Port"
while ($true) {
    $client = $listener.AcceptTcpClient()
    try { Serve-Client $client }
    catch { Write-Log "request failed: $($_.Exception.Message)" }
    finally { $client.Close() }
}
