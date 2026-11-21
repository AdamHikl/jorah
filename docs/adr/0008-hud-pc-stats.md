# ADR 0008: the HUD's PC panel reads the PC's load from a reader on Windows

**Decision:** the Mac HUD gets a PC panel with CPU, CPU temperature, RAM, GPU, VRAM, network and disk use. The numbers come from a read-only reader on Windows, `scripts/pc/pcstats.ps1`, through a tailnet-only Serve route. They do not go through the Gateway. Adam asked for it on 2026-11-21 ("add cpu usage, temperature, network usage, ram usage, gpu usage, vram usage, ssd usage of the pc to the jorah hud so that I can monitor it"), approved the plan below, and picked Core Temp for the CPU temperature ("Yes, try Core Temp").

## Why Windows, not the jorah distro

The distro can't see the PC as a whole, on purpose: `/etc/wsl.conf` turns interop and the Windows drive mounts off, and `deploy/jorah-firewall.nft` keeps the `jorah` user away from Windows' ports. Inside WSL, `/proc` shows only the distro's own CPU, memory and traffic, and its disk is a virtual one. Only `nvidia-smi` would be right from there. So the reader runs on Windows, where Task Manager's own counters are.

## Why not through the Gateway

- The panel keeps working while Jorah is paused by the kill switch (ADR 0006), which is when Adam most wants to see the GPU and memory free up.
- A Gateway route would need the Windows numbers carried into the distro, through a hole in the firewall or interop that this design avoids.

So this ADR replaces one line of ADR 0005, "The HUD shows only what the Gateway already sends an operator", for this panel only.

## What runs on Windows

| Piece | What | Why |
|---|---|---|
| `C:\ProgramData\Jorah\pcstats\pcstats.ps1` | Windows PowerShell 5.1, nothing downloaded. Answers only `GET /v1/stats` on `127.0.0.1:43230`, with one JSON reading. Reads nothing from a request but its first line | No new software. A fixed answer and no input leave little to attack |
| Folder ACL | Only SYSTEM and Administrators can write; Users can read | The task runs elevated, so its script must not be writable by others |
| Task "Jorah PC Stats" | `adamh`, S4U (at boot, nobody signed in), highest privileges, boot trigger plus every 5 minutes with `IgnoreNew`, no time limit | Same pattern as "Jorah WSL". Highest is needed only for disk temperatures (`Get-StorageReliabilityCounter`) |
| Task "Jorah Core Temp" | Starts `C:\Program Files\Core Temp\Core Temp.exe` (1.18.1, already installed by Adam) the same way | Windows reports no CPU temperature on this board (no ACPI thermal zones). Core Temp reads it with its own driver and shares it in memory, which the reader opens read-only. Both tasks run in session 0, so the reader can see Core Temp's shared memory |
| Serve route | `https://rocket.tail1574a5.ts.net:43231` to `http://127.0.0.1:43230`, tailnet only | HTTPS with the tailnet's certificate, like the Gateway and voice routes. 43230 and 43231 are clear of the distro's ports (`docs/runbooks/jorah-on-pc.md`, rule from 2026-11-08) |

Measured on 2026-11-21 with a 60-second run on a spare port: 0.9 s of CPU per minute while polled every 2 s (0.05% of the PC), 178 MB of memory, about 75 ms per answer, 3 s for the first answer after a pause.

## What the HUD does

- Polls every 2 seconds, only while the PC panel is on screen (COMMAND view) and the window is visible.
- A missing value says "unknown", with the reader's reason on hover. A reading older than 10 seconds is not shown at all: the panel says why it has none.
- The address is a setting (`hud.pcStatsURL`), like the voice address.

## Limits

| Limit | Detail |
|---|---|
| Any device on the tailnet can read these numbers | No token: they are load figures, hardware names and disk sizes, nothing from Jorah or Adam's files. The `jorah` user can't reach either port (firewall) |
| CPU temperature depends on Core Temp | If Core Temp does not start, or does not share its readings in session 0, the panel says "temp unknown" and why. Core Temp is closed-source freeware; it was already installed and in use on this PC |
| If Adam starts Core Temp himself while signed in | Core Temp's `SingleInstance=1` may refuse a second copy, or both run. Either way the reader keeps using the session-0 copy |
| Rates are averages since the previous request | With the HUD polling every 2 s, that is a 2-second average |
| Rides on the setup key for install | `install-pcstats.sh` uses `~/.ssh/jorah-pc-setup`, like the kill switch. Once installed, the panel does not need the key |

## Undo

`scripts/pc/install-pcstats.sh --undo` removes the Serve route, both tasks (which ends the Core Temp copy they started) and the folder.
