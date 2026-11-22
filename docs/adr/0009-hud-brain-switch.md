# ADR 0009: the HUD switches Jorah between the Max plan and the API key

**Decision:** the Mac HUD gets a button that shows what Jorah bills, the Max plan or Jorah's Console key, and switches between the two. Adam asked for it on 2026-11-21: "switch jorah to api now, also make it possible for me to switch between the max plan and the api back and forth inside the jorah hud".

Until now each switch was a build session applying `config/pc/api-lane.patch.json5` or `max-lane.patch.json5` by hand (`docs/runbooks/jorah-on-pc.md`, 2026-11-06 and 2026-11-16).

## How it works

The switch works like the kill switch (ADR 0006): the HUD runs a fixed script on the Mac, which uses the setup SSH key to run a fixed script on the PC.

| Piece | What |
|---|---|
| `scripts/pc/brain-lane.sh` (PC, in `/opt/jorah`, run as `jorah`) | `status [--probe]`, `api` or `max`. A switch takes a lock, checks its preconditions, backs up `openclaw.json` to `~/.openclaw-jorah/backups/brain-lane/` (newest 20 kept), runs a dry run, applies the lane's patch (hot reload, no restart), sets or clears main's and deep's own key order, validates, runs the secrets audit (API lane only) and reads everything back. The last line is always `LANE: api`, `max`, `mixed` or `unknown` |
| `scripts/pc/jorah-brain.sh` (Mac) | Checks that the `jorah` distro is running, then runs the PC script over SSH. A stopped distro is left alone, because `wsl -d jorah` would start it, and the Gateway with it |
| HUD | A `BILLS` button in the top bar shows the lane last read on the PC. It opens a sheet that explains both lanes and has one switch button for each |

## What each lane changes

| | Max plan | API key |
|---|---|---|
| main (chat, voice, the iPhone), heartbeats, Dreaming, utility model | `claude-cli`, Jorah's Claude login (Adam's own Max account) | Embedded runtime, `anthropic:jorah-store` |
| deep | `claude-cli` | Embedded runtime |
| `auth.order.anthropic` | `[]` | `["anthropic:jorah-store"]` |
| main's and deep's own key order | Cleared. OpenClaw treats an explicit order as authoritative for `claude-cli` | `anthropic:jorah-store` |
| background | Key, embedded runtime: its shell needs the Podman sandbox | The same |
| Claude Code coding jobs (ACP) | Max | Max |

`api-lane.patch.json5` now also pins deep back to the embedded runtime. Before this change, a switch to the key would have left deep on Max.

## Rules

| Rule | How |
|---|---|
| Only a click switches | Each switch button calls the switch. Neither is the default button or has a shortcut. Voice, chat and Jorah have no path to it: the script runs on the Mac, from the app |
| The PC is the truth | The lane comes from the PC script's last line, with the time it was read. It is read when the HUD starts (unless Jorah is paused from this Mac), when the sheet opens, and after each switch. A failed read shows `UNKNOWN`, never a lane |
| Fixed words only | The app passes `status`, `status --probe`, `api` or `max`. Both scripts refuse anything else |
| No secret moves | The key stays in the secret store. Neither script reads or prints it or `openclaw.json` |
| A half-done switch is visible | `MIXED` in red, and both switch buttons stay enabled. Both switches are safe to repeat |
| Proof on request | "Run a test turn" sends one message to main in a throwaway session (deleted and forgotten afterwards) and shows which route it took: `runner: cli` is Max; `embedded` with a `profile` credential is the key |

## Limits

- **It rides on the setup key,** like the kill switch. When setup access closes (`close-setup-access.ps1 -EndSetup`), the button shows `UNKNOWN` and the switches fail at SSH. The follow-up in ADR 0006, a dedicated key with a forced command, should cover `brain-lane.sh` too.
- **Money:** on the API key, Jorah's Console workspace is capped at $80 a month. When the credit runs out Jorah stops answering, with nothing to fall back to. On the Max plan, Jorah shares Adam's 5-hour and weekly limits. The sheet says both.
- **A reply already running** may finish on the old lane. Whether OpenClaw 2026.10.9 moves a running turn on hot reload has not been checked.
- **The main chat** may keep its old route until a new session (`/new` or the 04:00 reset), as noted at the 2026-11-07 and 2026-11-16 switches. The test turn runs in a new session, so it does not show this.
- **Memory leak:** heartbeats on `claude-cli` leak agentmemory processes (runbook, 2026-11-17). On the API key that stops. The 6-hourly Gateway restart covers it on both lanes.

## Tests

- `scripts/pc/tests/test_brain_lane.py`: the PC script against a fake `openclaw`. It covers status on each lane, a single setting off making the lane mixed, an unreadable config making it unknown, a switch both ways, a missing key profile and a failed dry run each changing nothing, a failure after the patch showing mixed, backup pruning, and refusing other words.
- `clients/mac-hud/Tests/HUDCoreTests/BrainLaneTests.swift`: reading the lane and the test turn from the output.
- Live: the switch to the key on 2026-11-21 was applied by hand, before the script existed, and proved with test turns on main and deep. The script's `status` and a repeat `api` were then run on the PC (runbook). The HUD's buttons, and `max` through the script, are Adam's test.

## Undo

Remove the button and sheet, and delete `brain-lane.sh` from `/opt/jorah` (`deploy_reviewed.py forget`). The lane stays where it was last set.
