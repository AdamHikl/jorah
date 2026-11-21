# jorah-pcstats v1: the PC's load for the HUD

The interface between `scripts/pc/pcstats.ps1` on Windows and the Mac HUD's PC panel
(`clients/mac-hud/Sources/HUDCore/PCStats.swift`). Written 2026-11-21 with ADR 0008.

```
Mac HUD ──tailnet, HTTPS──> Windows: tailscale serve :43231 ──> 127.0.0.1:43230 (pcstats.ps1, task "Jorah PC Stats")
                                                                  ├─ performance counters: CPU, memory, network, disks
                                                                  ├─ nvidia-smi: GPU
                                                                  ├─ Get-StorageReliabilityCounter: disk temperatures, once a minute
                                                                  └─ Core Temp's shared memory: CPU temperature
```

## Request

`GET /v1/stats`, no query, no body, no auth. Anything else: `404` for another `GET` path,
`405` for another method. One request at a time; the answer is cached for one second.

## Response

`200`, `application/json`. Every number may be `null`; a `null` section or value has its reason in
`unknown`. Readers must show a `null` as unknown, never as 0. A real 0 (an idle GPU) is `0`.

```json
{
  "schema": "jorah-pcstats/1",
  "at": "2026-11-21T14:16:43.492Z",
  "cpu": { "name": "Intel(R) Core(TM) i7-14700K", "percent": 5, "temperatureC": null, "temperatureSource": null },
  "memory": { "usedBytes": 17297235968, "totalBytes": 34107396096 },
  "gpu": { "name": "NVIDIA GeForce RTX 5070", "percent": 0, "memoryUsedBytes": 6136266752,
           "memoryTotalBytes": 12820938752, "temperatureC": 49, "powerW": 1.9, "fanPercent": 0 },
  "network": { "downBytesPerSec": 1629, "upBytesPerSec": 621, "adapters": ["Wi-Fi"] },
  "disks": [
    { "drives": ["C:"], "model": "ADATA LEGEND 800", "kind": "ssd", "usedBytes": 689329963008,
      "totalBytes": 999036022784, "readBytesPerSec": 144884, "writeBytesPerSec": 3204045,
      "busyPercent": 0.7, "temperatureC": 48, "temperatureAt": "2026-11-21T14:15:45.170Z" }
  ],
  "unknown": { "cpu.temperatureC": "Core Temp is not running" }
}
```

| Field | Source | Notes |
|---|---|---|
| `cpu.percent` | `Processor Information(_Total)\% Processor Utility` | What Task Manager shows; capped at 100 |
| `cpu.temperatureC` | Core Temp, hottest core | `temperatureSource` says so |
| `memory.usedBytes` | total minus `Memory\Available Bytes` | |
| `gpu.*` | `nvidia-smi --query-gpu=...` | `memory*Bytes` from MiB |
| `network.*` | `Network Interface(*)\Bytes Received/sec`, `Bytes Sent/sec` | Summed over physical adapters that are up |
| `disks[].busyPercent` | 100 minus `PhysicalDisk(*)\% Idle Time` | Task Manager's "active time" |
| `disks[].kind` | `Get-PhysicalDisk` | `ssd`, `hdd`, or `null` when Windows does not say |
| `disks[].temperatureC` | SMART, `Get-StorageReliabilityCounter` | Read once a minute; `temperatureAt` is when |

Rates (`percent`, `*PerSec`, `busyPercent`) are averages since the previous request, or over
0.7 s after more than 10 s without one.

## Versions

A change that removes or renames a field is `jorah-pcstats/2`. The HUD refuses a schema it does not
know and says which one it got.
