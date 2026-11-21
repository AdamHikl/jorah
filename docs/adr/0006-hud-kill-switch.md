# ADR 0006: the HUD's kill switch pauses Jorah on the PC over the setup SSH key

**Decision:** the Mac HUD gets a kill switch that pauses Jorah on the PC, to free the GPU, memory and CPU for other work, and a resume. Adam asked for it on 2026-11-10: "save the current environment and everything in jorah, and then just stop the wsl and ollama".

The switch runs `scripts/pc/jorah-power.sh` on the Mac. `just mac-hud` copies that script into the app. The same script works from a Terminal.

## What pause does, in order

| Step | Action | If it fails |
|---|---|---|
| 1 | Reach the PC over SSH | Stop. Nothing changed |
| 2 | Save: `systemctl start jorah-backup.service`, the same verified backup the 04:30 timer makes | Stop. Nothing is stopped |
| 3 | `systemctl stop` the Gateway, `jorah-voice`, `jorah-voice-qwen` and `jorah-agentmemory` | Stop. The distro stays up |
| 4 | Disable and stop the Windows task "Jorah WSL", `wsl --terminate jorah`, end Windows processes named `ollama*` | Reported. Check with `status` |
| 5 | Check that the distro is stopped, and print the task state, Ollama process count and GPU memory | Reported as failed |

Resume enables and starts the "Jorah WSL" task, waits up to 4 minutes for the Gateway unit to be active, and prints each unit's state. The enabled units start by themselves with the distro.

## Why these choices

- **The task must be disabled.** It restarts the distro every 5 minutes, so a plain `wsl --terminate` would not hold (`docs/runbooks/jorah-on-pc.md`).
- **Save means a verified backup plus a clean stop.** OpenClaw's state is on disk in `~/.openclaw-jorah`. Live SQLite files are never copied (`docs/plan/09-engineering-and-ops.md`), so the existing backup service is the safe snapshot. Whether OpenClaw keeps anything only in memory is unknown: the units get their normal stop, with the Gateway's 60 seconds.
- **Only the `jorah` distro is stopped,** not `wsl --shutdown`, because Adam's other work may itself run in WSL.
- **Ollama is not part of Jorah.** The repo only records that it listens on Windows' loopback. Pause ends its processes. Resume does not start it, because how it starts on that PC is not recorded.

## What this adds to the HUD's power, and its limits

ADR 0005 keeps the HUD's Gateway access to `operator.read` and `operator.write`. The kill switch is a second, separate power: it runs `ssh` with Adam's setup key, which is a Windows administrator key.

| Limit | How |
|---|---|
| The app holds no key | It starts `/bin/bash` with the script, and `ssh` reads `~/.ssh/jorah-pc-setup` as it does in Terminal |
| Nothing runs without Adam | Each pause or resume needs the button and a confirmation that lists the steps. Voice cannot trigger it |
| The script is fixed | The app passes only `pause`, `pause --no-backup`, `resume` or `status` |
| It ends with setup access | `close-setup-access.ps1 -EndSetup` removes the key and stops `sshd`. The switch then fails at step 1 |

## Known gaps

- Not yet run against the PC. The first real pause and resume are Adam's test.
- A run, an approval or a scheduled job in flight is cut off. The HUD warns about runs it can see.
- Telegram messages sent while paused may all be answered at once on resume.
- While paused the iPhone, `mac-ear` and the HUD show disconnected. The Tailscale Serve routes stay and return errors.
- "Paused" in the HUD is what this Mac did, not a live reading. "Check what is running" asks the PC.

## Follow-up, before setup access closes

A dedicated SSH key on the PC with a forced command that can only pause, resume or report status, so the switch outlives the setup key and no longer rides on an administrator key. That is a change on the PC and needs its own yes.
