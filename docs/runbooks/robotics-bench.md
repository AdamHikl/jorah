# Robotics bench: ROS 2, Gazebo, PlatformIO and code CAD on the PC

Section 7 of `docs/plan/11-project-mode.md`: the tools project runs need to build robot software,
simulate it, build firmware and make CAD, installed once on the `jorah` distro and used offline
inside Claude Code's sandbox. First user: `tree-watering-robot`.

**State, 2026-11-17: installed on the PC** by the install session [measured, reported by it]:
`INSTALL EXIT 0`, every command found as jorah. First smoke test (direct, own network namespace,
offline): `pio` and `cad` passed; `colcon` failed on the smoke package's maintainer e-mail
(catkin_pkg wants a dotted domain), and `gz` exited 0 but the robot didn't move, because the wheel
joints were `continuous`, which Gazebo's DART physics builds as fixed. Both fixed in the smoke assets
(and the test now fails when the robot doesn't drive); **the rerun is open**. Also open: the smoke
test inside Claude Code's sandbox (S3) and a first project run with `bench: robotics`. S4 answered
(plan section 14).

## What gets installed

| Part | Version | Source | Where |
|---|---|---|---|
| ROS 2 Jazzy `ros-base` | 0.11.0, built 2026-10-06 | ROS snapshot repository, sync of 2026-10-05 | `/opt/ros/jazzy` |
| Nav2 (navigation2's 31 packages, without `nav2_rviz_plugins`) | 1.3.13 | same | `/opt/ros/jazzy` |
| `robot_localization` | 3.8.3 | same | `/opt/ros/jazzy` |
| `ros_gz`: `ros_gz_sim`, `ros_gz_bridge`, `ros_gz_interfaces` (without `ros_gz_sim_demos`) | 1.0.24 | same | `/opt/ros/jazzy` |
| Gazebo Harmonic (gz-sim 8, through ROS's `gz_sim_vendor` 0.0.13 and the other `gz_*_vendor` packages), run server-only | gz-sim 8.15 | same | `/opt/ros/jazzy/opt/gz_*_vendor` |
| `colcon` (`python3-colcon-common-extensions`), `rosdep` | colcon-core 0.21.3, rosdep 0.27.0 | same | system Python |
| `build-essential`, `python3-venv`, `libgl1` and every dependency apt pulls in | as Ubuntu 24.04 has them | Ubuntu archive | system |
| PlatformIO Core | 6.2.0 (2026-09-05) and 22 dependencies, hashes pinned | PyPI | `/opt/jorah-bench/pio/venv` |
| Platform Espressif 32 | 8.0.0 (2026-10-19), Arduino-ESP32 3.3.12 | PlatformIO registry, during install only | `/opt/jorah-bench/pio/core` |
| Platform Raspberry Pi RP2040 | 1.20.0 (2026-06-25), Arduino on mbed 4.6.0 | same | same |
| Toolchains and frameworks for boards `esp32dev`, `seeed_xiao_esp32s3`, `pico` | pinned in `deploy/jorah-bench/smoke/pio/platformio.ini` | same | same |
| build123d | 0.13.0 (2026-09-21) and 57 dependencies, hashes pinned; OpenCascade from `cadquery-ocp-novtk` 8.0.1.1.0 | PyPI | `/opt/jorah-bench/py/venv` |
| rosdep database | rosdistro tag `jazzy/2026-10-05` | GitHub raw (rosdistro) | `/opt/jorah-bench/ros-home` |
| `env.sh`, `bin/` (`pio`, `platformio`, `cad-python`), smoke assets, `INSTALLED.txt` | this repo | `deploy/jorah-bench/` | `/opt/jorah-bench` |

All of `/opt/jorah-bench` is root-owned and read-only to `jorah`; so is `/opt/ros`. Pins live in
`deploy/jorah-bench/versions.env`, `requirements-pio.txt`, `requirements-cad.txt` and
`smoke/pio/platformio.ini`.

**KiCad, update 2026-11-17:** KiCad 10.0.8 now has its own install, `scripts/pc/install-kicad.sh`
(KiCad's PPA, pinned), and a `kicad` part in `bench-smoke.sh`; see `docs/runbooks/toolbox.md`. The
paragraph below is the earlier decision, kept for the record.

**Not installed: KiCad CLI.** Decision: not now. Noble has no CLI-only package: `kicad-cli` comes
in the full `kicad` package, which pulls wxWidgets and the GUI stack, and noble's own is KiCad 7.0
(two majors behind; files saved by newer KiCad don't open in it). The current release needs the
KiCad PPA, a third signing key for a GUI program. The robot has no schematic yet; when one is due,
it becomes an Adam task with the PPA's fingerprint and size, and runs do wiring diagrams and BOMs
as text until then.

## Decisions and why

- **Snapshot, not the live ROS repository.** `packages.ros.org` keeps only the latest sync, so a pin
  breaks at the next sync, and it would bring packages younger than 7 days. `snapshots.ros.org` keeps
  each sync frozen for at least six months (http://wiki.ros.org/SnapshotRepository). The sync of
  2026-10-05 was published 2026-10-12. Moving on means changing `ROS_SNAPSHOT` in `versions.env` and
  rerunning the install. The snapshot gets no security fixes, which is why moving on now and then
  matters.
- **No OSRF apt repository.** ROS Jazzy ships Gazebo Harmonic as its own `gz_*_vendor` packages, which
  `ros_gz` is built against. One repository and one key fewer.
- **No RViz or GUI tools.** Nothing on the distro has a display. Gazebo's vendor packages still pull
  Qt libraries; they're never started.
- **build123d in its own venv** (`cad-python`), not on the system Python: it needs numpy 2, and ROS
  Jazzy's Python packages are built against Ubuntu's numpy 1.26.
- **PlatformIO's core can't be read-only** [measured 2026-11-16 on the Mac, PlatformIO 6.2.0, offline
  through a dead proxy]: `PLATFORMIO_CORE_DIR` on a read-only folder fails with
  `HomeDirPermissionsError` (it writes `appstate.json` and locks `.cache/` there), and read-only
  `PLATFORMIO_PLATFORMS_DIR`/`_PACKAGES_DIR` fail too, because `pio run` takes `platforms.lock` in
  their *parent* folder even when nothing needs installing. What works: a per-user core in
  `~/sandbox/.cache/jorah-bench/platformio` whose `platforms` and `packages` are symlinks to the
  read-only copies. The build passed offline with nothing written to the read-only copy or to `HOME`.
  `env.sh` sets this up.
- **Gazebo writes to `HOME`** (gz-sim 8 source): `~/.gz/sim/log/<time>/server_console.log` on every
  start, and a copy of `server.config` in `~/.gz/sim/8/`. Gazebo has no variable for its home folder.
  `env.sh` points `GZ_SIM_SERVER_CONFIG_PATH` at the installed config, and when `HOME` isn't writable
  (inside the sandbox) moves `HOME` to `~/sandbox/.cache/jorah-bench/home`.
- **`env.sh` works in two passes.** The project runner (`services/jorah-projects`,
  `bench_environment`) sources it once outside the sandbox, keeps the exported variables and resets
  `HOME`. So `env.sh` also exports `BASH_ENV` pointing at itself: every bash Claude Code starts in the
  sandbox sources it again and takes a short pass that only fixes `HOME` and `TMPDIR` for where it
  runs [tested in a container with the runner's capture-then-reset sequence].

## Signing keys

Fingerprints computed from the key files the official install pages name, 2026-11-16:

| Repository | Key | Fingerprint | Used here |
|---|---|---|---|
| `snapshots.ros.org` | "ROS Snapshot builder", from the keyserver as http://wiki.ros.org/SnapshotRepository says; the copy is `deploy/jorah-bench/keys/ros-snapshots.asc` | `4B63 CF8F DE49 746E 98FA 01DD AD19 BAB3 CBF1 25EA` | **Yes.** It signs the 2026-10-05 snapshot's InRelease. Its latest self-signature (2025-08-27) sets expiry to **2027-05-31**: check for a renewed key before then |
| `packages.ros.org` (live) | "Open Robotics", `https://raw.githubusercontent.com/ros/rosdistro/master/ros.key`, the key docs.ros.org's Jazzy page installs through `ros2-apt-source` | `C1CF 6E31 E6BA DE88 68B1 72B4 F42E D6FB AB17 C654` | No (recorded). Signs today's live InRelease; expires 2030-06-01 |
| `packages.osrfoundation.org` (Gazebo) | "OSRF Repository", `https://packages.osrfoundation.org/gazebo.gpg`, named by gazebosim.org/docs/harmonic/install_ubuntu | `D248 6D2D D83D B692 72AF E988 6717 0598 AF24 9743` | No (recorded) |

The install checks the snapshot key file's fingerprint against `versions.env` and stops on a mismatch.
The snapshot server's only working scheme is plain http (its https certificate doesn't match the
name); apt checks the signature and every package's hash, so that's the integrity check.

## Pins, the 7-day rule and exceptions

- ROS: the snapshot is the pin (published 2026-10-12).
- PyPI: every package of both trees pinned with its wheel's SHA-256, each wheel uploaded on or before
  2026-11-09 (dates in the lock files). Two held back: `numpy` 2.5.4 (2.5.5 was a day old) and
  `bd_materials` 0.2.5 (0.2.6 was three days old). Installed with `--require-hashes --no-deps
  --only-binary :all:`.
- PlatformIO: `framework-arduinoespressif32 ~4.30312.0` would resolve to a build released on
  2026-11-16, so `smoke/pio/platformio.ini` pins `4.30312.261024` (2026-10-24) and the other
  toolchains. After fetching, the install asks the registry for each package's release date
  (`deploy/jorah-bench/pio-age-check.py`) and stops if any is under 7 days or unknown.
- **Exception (written):** Ubuntu's own archive packages (compilers, Qt, Boost and the other
  dependencies apt pulls in) install as the Ubuntu 24.04 archive has them, including security
  updates, as for the rest of the distro. They aren't pinned by date.
- **Licences:** every PyPI package is in `config/licenses.tsv`. Five licences outside the allowlist
  (chardet's LGPL, OpenCascade's LGPL inside the OCP wheel, PSF-2.0, Unlicense, MIT-CMU) are accepted
  for personal use in `docs/adr/0003-robotics-bench-licences.md`, for the bench's packages only.
- **Note:** rosdep's `distribution_cache` for Jazzy comes from `repo.ros2.org` as it is on install
  day; the rule files are pinned to the tag. It only maps dependency names.

## Disk

Measured at the install of 2026-11-17 (`/opt/jorah-bench/INSTALLED.txt`):

| Part | Size |
|---|---|
| apt: ROS from the snapshot and Ubuntu dependencies, 1051 packages | 2524 MB |
| `/opt/jorah-bench/pio`: PlatformIO and 14 platform packages (ESP32 and RP2040 toolchains, frameworks) | 5.2 GB |
| `/opt/jorah-bench/py`: build123d venv | 998 MB |
| Per-user caches (`~/sandbox/.cache/jorah-bench`, builds, logs) | grows with use |

About 8.7 GB in all, inside the plan's guess of 6 to 10 GB. PlatformIO is larger than the 3 GB
estimate because the ESP32 platform needs both Xtensa and RISC-V toolchains and their debuggers.

## Adam's steps

Each in a Terminal attached to no agent. Nothing here needs a password or a key.

**0. Reviewed files on the PC** (the install session does this, as for every install: copy, then
SHA-256 against `main`):

```bash
git archive main scripts/pc/install-robotics-bench.sh scripts/pc/bench-smoke.sh deploy/jorah-bench | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- tar -x -C /opt/jorah"
```

**1. Dry run** (writes nothing; reads apt indexes into a temporary folder, then removes it):

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-robotics-bench.sh --dry-run
```

Expected: `Ubuntu 24.04... amd64, python 3.12.x`, free space and memory, the snapshot
key line with the fingerprint from "Signing keys" and "(matches the pin)", `PyPI pins: 23 for PlatformIO, 58 for
build123d`, then "packages apt would newly install: N" with the download and installed size, the
versions of `ros-jazzy-ros-base` (0.11.0-1noble.20261006...), `ros-jazzy-gz-sim-vendor` and friends,
no `UNEXPECTED: ros-jazzy-rviz...` line, and "Dry run: nothing written". It stops early, with a
reason, if another ROS apt source is configured or a pin doesn't match.

**2. Install** (as root; the network is used here and never again by the bench):

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-robotics-bench.sh
```

Expected, in order: `== 1. Checks` as in the dry run; apt installs; "newly installed by this script
(kept for --undo): N packages"; PlatformIO builds `esp32dev`, `xiao_esp32s3` and `pico` with
`[SUCCESS]` for each (a line "Tool Manager: Error: Please read
https://bit.ly/package-manager-ioerror" appeared once at the install of 2026-11-17 and all three boards
still built and passed the age check; harmless so far); "Python packages added by PlatformIO outside the hashed lock: none" (if it names
any, say so: they were installed without hashes); one line per PlatformIO package with `ok` and its
release date, ending "0 failing the 7-day rule or unknown"; `build123d 0.13.0`; rosdep "updated
cache" (after a warning that it runs as root, which is intended: the database is root-owned); the `INSTALLED.txt` record with versions and disk use; and as jorah every command found:
`ros2`, `colcon`, `rosdep`, `gz`, `pio`, `cad-python`. Time: mostly downloads, roughly 3 to 4 GB.
If the age check stops it (exit 7), nothing after step 5 ran: tell the build session which package.

**3. Smoke test, direct** (as jorah, in its own network namespace, so offline):

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/bench-smoke.sh
```

Expected: `network namespace: own`, `offline: yes`, then four lines `colcon PASS`, `gz PASS 60 simulated s
(60000 steps of 1 ms) ... the robot is at x=11 to 12 m`, with `gz-transport ... yes`, `pio PASS esp32dev firmware.bin ... bytes`, `cad PASS
box.step ... bytes, volume_mm3=...`, the info lines, and `RESULT: PASS`. Exit 0. The summary stays
in `~/sandbox/bench-smoke/<time>-<pid>/summary.txt`. First run: the ESP32 build takes a minute or
two; Gazebo's 60 simulated seconds should take well under a minute of wall time.

**4. Smoke test inside Claude Code's sandbox (spike S3).** As jorah, after WS2's
`setup-project-permissions.sh` has written `~/.claude-jorah/project-settings.json`. The script starts
Claude Code headless the way the runner does (`env.sh` sourced outside with `PATH=/usr/bin:/bin`,
`HOME` reset, the project-run settings, Opus 5.5 at high effort, in `~/work/bench-check`) and has it
run the smoke test with its Bash tool, inside its sandbox. Uses a few turns of the Max plan:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/bench-smoke.sh --via-claude
```

Expected: the same four PASS lines and `RESULT: PASS`, with `home writable before env.sh: no`,
`network namespace: inherited` or `own`, and `offline: yes`. The info lines answer S3: whether a ROS 2
node starts in the sandbox, whether gz-transport works between processes there (odometry messages,
robot at about x = 11 to 12 m), and whether `/dev/shm` is writable and `/dev/dri` absent. If Claude
Code asks for approval or the sandbox refuses a path, that is a finding: copy the lines.

**5. Memory next to voice (spike S4).** Run step 3 again while `jorah-voice` and `jorah-voice-qwen`
are active (the summary prints their state), ideally during a voice turn. Expected: "lowest during
it" stays above 2 GB available. Record both figures and gz's peak RSS in plan section 14.

**6. Record** the results of steps 2 to 5 in `docs/evidence/robotics-bench/` (no private content),
fill S3 and S4 in plan section 14, and update the State line above.

## Using the bench in a project

For runs and the brief (`services/jorah-projects/brief.md`); a project gets it with `"bench": "robotics"`:

- Source `/opt/jorah-bench/env.sh` (the runner already does, and `BASH_ENV` repeats it per command).
- ROS: `colcon build` in the project's workspace; `rosdep keys`/`rosdep check` work; `rosdep install`
  can't (no root): a missing system package is an Adam task.
- Gazebo: always `gz sim -s` (server only), `-r --iterations N` for a fixed run, worlds without
  camera, depth or lidar sensors that need rendering (no GPU in the sandbox). A camera in simulation
  is a later decision. Wheel and other unlimited joints: `type="revolute"` with limits
  ±1.79769e+308, never `continuous`, which this Gazebo's DART physics turns into a fixed joint with
  only a log line [measured 2026-11-17]. Check a simulation by its result (the robot's odometry),
  not by `gz sim` exiting 0.
- PlatformIO: use exactly `platform = platformio/espressif32@8.0.0` (boards `esp32dev`,
  `seeed_xiao_esp32s3`) or `platformio/raspberrypi@1.20.0` (board `pico`), framework `arduino`, and
  copy the `platform_packages` lines from `/opt/jorah-bench/smoke/pio/platformio.ini`. Anything else
  needs a download the sandbox refuses. Flashing is Adam's, by hand (`08-robotics.md` hard rules).
- CAD: `cad-python script.py` (build123d; STEP and STL export). Not `python3`.
- A new tool goes through Jorah's toolbox (`docs/runbooks/toolbox.md`): a request, Adam's card, the
  installer. A new PlatformIO platform or board, or anything needing root beyond Ubuntu's own
  packages, is still an Adam task done by a build session that adds it to this install.

## For the runner (WS2) and the install session

- `setup-project-permissions.sh` already lets the sandbox read `/opt/jorah-bench`; `/opt/ros` is
  readable because only the home folder is denied. Writes go to `~/sandbox/.cache/jorah-bench`,
  inside the allowed `~/sandbox`. No new network domains.
- The runner evaluates `env.sh` with `PATH=/usr/bin:/bin` and uses the result as the run's PATH.
  `env.sh` keeps `/usr/local/bin` on it for that reason.
- The runner drops `HOME` from what `env.sh` exports; `BASH_ENV` (exported by `env.sh`) is what puts
  the `HOME` fix back inside the sandbox. If a later Claude Code doesn't pass `BASH_ENV` through to
  its shell, Gazebo will print errors about `~/.gz` and fall back; the smoke test in step 4 shows it.
- `jorah-projects.service` runs with `ProtectHome=tmpfs` and binds `~/sandbox`: the cache folder is
  inside it, so nothing more is needed there.

## Undo

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-robotics-bench.sh --undo --dry-run
```

Shows what goes: `/opt/jorah-bench` and its size, the snapshot apt source and key, and the apt
packages this install newly installed (recorded in `/opt/jorah-bench/apt-added.txt`; packages that
were there before stay). If something else now depends on them, it names those and `--undo` stops.
Then the same without `--dry-run`, and type `yes`. Expected: "Undo done"; `dpkg -l 'ros-jazzy-*'`
lists nothing. The per-user cache stays; as jorah, `rm -rf ~/sandbox/.cache/jorah-bench
~/sandbox/bench-smoke` removes it.

## Troubleshooting

- `pio run` tries to download: the project asks for a platform, board or package version that isn't
  installed. Use the pinned ones above.
- `HomeDirPermissionsError` from PlatformIO: `PLATFORMIO_CORE_DIR` points at `/opt`; source `env.sh`.
- `ImportError` for `build123d` or numpy: `python3` was used instead of `cad-python`.
- Gazebo exits at once with a plugin error: the world uses a system that isn't in the vendor
  packages; `gz sim -s -v 4 world.sdf` names it.
