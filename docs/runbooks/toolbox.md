# Jorah's engineering tools and toolbox

Adam asked on 2026-11-17 that Jorah be able to use Fusion 360, a Cura slicer for his printer, a PCB
tool, coding environments and web research, and preferably install and learn new tools himself.
He approved this plan the same day. The decision is recorded in `docs/adr/0004-toolbox-installs-and-licences.md`.

**State, 2026-11-18:** source and tests only. Nothing is installed on the PC yet; each step
below waits for Adam's yes.

Checked off the PC [measured 2026-11-18, in fresh `ubuntu:24.04` containers on the Mac; amd64
under emulation for KiCad]:

- **`install-kicad.sh`:** the dry run, then the install. The key matched the pin and the candidate
  was `10.0.8~ubuntu24.04.1`. It installed 261 packages, about 241 MB to download and 1322 MB
  installed. On the PC it will be fewer, since the bench already brought many of the libraries.
- **The `kicad` smoke steps** on `deploy/kicad/smoke/board.kicad_pcb`, as an unprivileged user:
  - `kicad-cli version` printed `10.0.8`;
  - DRC found 0 violations and 0 unconnected items;
  - 25 Gerber files and `board.drl`;
  - `board.step` starting `ISO-10303-21;`;
  - the `R` symbol as SVG.
- **The installer's AppImage step:** an ELF followed by a zstd squashfs unpacked with
  `unsquashfs` 4.6.1 at the offset the code computed.

Not checked: anything on the PC, inside Claude Code's sandbox, or through the Gateway.

## What Jorah has, by job

| Job | What | How |
|---|---|---|
| **CAD** | build123d (robotics bench, installed) | Parts in code. Adam gets STEP, which Fusion 360 opens, plus STL for printing and SVG or DXF drawings |
| **Fusion 360** | Not driven | Fusion runs only on Windows or macOS, needs Adam's Autodesk sign-in, and has no headless or Linux mode. Driving it would put a Windows desktop and Adam's account in Jorah's reach. Autodesk's cloud Fusion Automation API needs a developer account and paid tokens; not now. If Adam edits a part in Fusion, he exports STEP and Jorah reads it |
| **PCB** | KiCad 10.0.8 from KiCad's PPA (`scripts/pc/install-kicad.sh`) | `kicad-cli`: ERC, DRC, Gerbers and drill files for a board house, BOM, netlists, PDF and SVG, the board as STEP. Schematics as code (SKiDL from PyPI) a run installs when it needs it |
| **Slicer** | Not installed: Adam's test | Jorah picks one for Adam's printer and installs it through the toolbox. Cura (its AppImage carries CuraEngine and the printer definitions), PrusaSlicer and OrcaSlicer are all AppImages |
| **Coding** | Python 3.12, Node 26 with npm 11.20, gcc and cmake, git; the robotics bench for robots | npm and PyPI packages go into the project. The 7-day rule is now enforced in runs (`npm_config_min_release_age=7`, `PIP_UPLOADED_PRIOR_TO=P7D` for pip 26.1 and newer, `UV_EXCLUDE_NEWER="7 days"`). Go, Java, uv and the like come through the toolbox |
| **Web research** | WebSearch and WebFetch in runs with `web: true`; web search in chat | Unchanged. Downloading files such as datasheets or vendor STEP models into a project isn't possible from the sandbox; that is its own decision later |

## How Jorah adds a tool

```
Jorah: toolbox_propose, or a run writes ~/work/.toolbox/requests/<name>.json
   |   (contract jorah-tool-v1, docs/contracts/jorah-tool-v1.md; checked by the plugin or the runner)
   v
/var/lib/jorah-toolbox/proposals/<id>.json           toolbox_list shows it waiting for a card
   |
   |   Adam: yes -> toolbox_install(card fields) -> guard card: id, name, version, source,
   |   sha256, licence, released, size -> Allow
   v
/var/lib/jorah-toolbox/approved/<id>.json            written only by the plugin, after the card
   |   jorah-toolbox.path starts jorah-toolbox.service (user jorah-toolbox, no root)
   v
download over https -> GitHub's date and digest (release assets) -> SHA-256 -> unpack without running
   -> /opt/jorah-toolbox/tools/<name>/<version>, wrappers in /opt/jorah-toolbox/bin, installed.json
   -> /var/lib/jorah-toolbox/results/<id>.json
   |   the project runner's next tick (at most 15 minutes)
   v
smoke test in bubblewrap (no network, empty home) -> /var/lib/jorah-toolbox/tested/<name>.json
   v
learning run: Claude Code in ~/work/.toolbox (project sandbox, web on, 30 min, 80 turns)
   -> notes/<name>.md, examples/<name>/, committed by the runner
   v
every project run's brief lists the tool, its smoke result and its notes
```

**Ubuntu packages** (`kind: "apt"`): after the card the installer only writes `needs-root`, and
Adam runs one command as root (step 6 below). It installs only from Ubuntu's own archive.

**What a tool gets:**
- read access to its own folder;
- write access to `~/sandbox/.cache/jorah-toolbox/<name>`;
- the environment its wrapper sets (`env` in the request);
- no network in runs.

Runs can read `/opt/jorah-toolbox` and `/var/lib/jorah-toolbox` but write neither.

**Files:**

| Path | Owner | What |
|---|---|---|
| `/opt/jorah-toolbox/installed.json`, `tools/`, `bin/` | jorah-toolbox | What is installed. Runs read it, never write it |
| `/var/lib/jorah-toolbox/proposals/` | jorah | Proposals from runs (the runner) and from chat (the plugin) |
| `/var/lib/jorah-toolbox/approved/` | jorah:jorah-toolbox, 2770 | Approvals, only after a card |
| `/var/lib/jorah-toolbox/results/`, `downloads/` | jorah-toolbox | The installer's results; downloads in progress; things that weren't approvals, set aside under `downloads/stray/` |
| `/var/lib/jorah-toolbox/tested/` | jorah | The runner's smoke tests and learning runs |
| `/var/lib/jorah-toolbox/apt/<name>.txt` | root | What `toolbox-apt.sh` added, kept for removal |
| `~/work/.toolbox/` | jorah | Jorah's notes repo: `notes/`, `examples/`, `requests/` (local git, no remote) |
| `~/.jorah-projects/_toolbox/runs/` | jorah | Learning-run records |

## Adam's steps

Run each in a Terminal attached to no agent. Nothing here needs a password or a key.

**0. The reviewed files on the PC** (the install session does this, as for every install). Copy
`main`'s versions of exactly the paths below into `/opt/jorah`, root-owned. Then compare each
file's SHA-256 with `main`'s, check that nothing is group- or world-writable
(`find /opt/jorah -perm /022` lists nothing new), and run `sync`. No write to `/opt/jorah` counts
as done until it has been followed by `sync` (the rule since the empty-files incident of
2026-11-16, `docs/runbooks/jorah-on-pc.md`).

```
packages/contracts/toolbox services/jorah-toolbox services/jorah-projects plugins/jorah-projects
plugins/jorah-guard config/permission-matrix.json deploy/jorah-toolbox.service deploy/jorah-toolbox.path
deploy/jorah-projects.service deploy/jorah-firewall.nft deploy/kicad scripts/pc/install-toolbox.sh
scripts/pc/toolbox-apt.sh scripts/pc/install-kicad.sh scripts/pc/setup-project-permissions.sh
scripts/pc/bench-smoke.sh docs/contracts/jorah-tool-v1.md workspace/AGENTS.md
```

**1. KiCad, dry run, then install** (as root):

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-kicad.sh --dry-run
```

Expected:
- `PPA key: FDA854F61C4D0D9572BB95E5245D5502FAD7A805 (matches the pin)`;
- `kicad candidate: 10.0.8~ubuntu24.04.1`;
- the number of packages and their download and installed sizes;
- the kicad packages at `10.0.8~ubuntu24.04.1`;
- no `UNEXPECTED from the PPA` line;
- `Dry run: nothing written ...`.

If the PPA answers 503, run it again later (exit 8).

Then the same command without `--dry-run`. Expected:
- `newly installed by this script (kept for --undo): N packages`;
- the `INSTALLED.txt` lines;
- as jorah, `kicad-cli version` prints `10.0.8`.

**2. KiCad smoke test**, offline and direct, then inside Claude Code's sandbox (as jorah):

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/bench-smoke.sh --part kicad
```

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/bench-smoke.sh --part kicad --via-claude
```

Expected, both times:
- `offline: yes`;
- `kicad PASS ... 10.0.8: 26 Gerber and drill files, board.step ... bytes, DRC 0 violations, 0 unconnected`
  (the container's figures);
- `RESULT: PASS`.

The smoke board has two 0603 resistors joined by one track, generated by
`deploy/kicad/smoke/make_board.py` with KiCad 10.0.8's own `pcbnew` module.

**3. Toolbox, dry run** (as root):

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-toolbox.sh --dry-run
```

Expected:
- `firewall file: valid (nft -c)`;
- a diff that adds only the `skuid 1103` lines;
- `Dry run successful` for main's tool list;
- the `Would:` lines;
- `Dry run only: nothing written.`

It stops early if the permission list has no toolbox rules, if `unsquashfs` or `bwrap` is missing,
or if uid 1103 is taken.

**4. Toolbox, install**, in two parts.

The system part leaves the live Gateway alone, so it can run while another session holds the
Gateway. It needs only the non-Gateway files in `/opt/jorah`:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-toolbox.sh --no-gateway
```

The Gateway part comes once no other session is on the live Gateway, and once `plugins/jorah-projects`,
`plugins/jorah-guard` and `config/permission-matrix.json` from this commit are in `/opt/jorah`. It
restarts the Gateway, so keep it clear of `jorah-gateway-recycle.timer`'s 02:20, 08:20, 14:20 and
20:20. Run `--dry-run` first, as with every step:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-toolbox.sh --gateway-only
```

Expected:
- from the system part:
  - `firewall: 7 rules for jorah-toolbox loaded`;
  - `active` for the path unit;
  - the four `wrote ... project-settings*.json` lines;
  - a status with `"tools": {}`;
- from the Gateway part:
  - the Gateway's health line;
  - `jorah-projects` in the plugin list.

Then copy `workspace/AGENTS.md` to the live workspace (backup `AGENTS.md.pre-toolbox`), as at the
projects install.

**5. End-to-end check, in Telegram** (it costs one short learning run on the Max plan):

> Jorah, add uv to your toolbox: it's the Python package manager. Show me the card.

Expected:
1. Jorah finds uv's latest release that is at least 7 days old on GitHub. He says its version, the
   licence (Apache-2.0 OR MIT), about 20 MB, and that it runs offline, then sends a card titled
   "Jorah wants to install a tool (runs offline, read-only to him)" with id, name, version, source,
   sha256, licence, released and size.
2. Tap Allow. Within a minute, `toolbox_list` (ask "what's in your toolbox?") shows uv installed.
3. Within 15 minutes it shows the smoke test passed. Within about 45 minutes the learning run is
   done and `~/work/.toolbox/notes/uv.md` exists.

If anything fails, `toolbox_list` says why. Copy that line to the build session.

**6. Ubuntu packages** (only when Jorah asks for one, for example Java for an autorouter). After
the card, Jorah shows the command. From the Mac:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/toolbox-apt.sh tb-xxxxxxxxxx --dry-run
```

Then the same without `--dry-run`. On the PC itself the command is the same, without the
`ssh ... adamh@100.115.240.14` part, in Windows Terminal.

Expected:
- `Request tb-...: tool <name>, Ubuntu packages: ...`;
- the packages apt would install and their size;
- the question `Type yes to install them`.

It stops (exit 5) if any package would come from somewhere other than Ubuntu's own archive.
Afterwards, `toolbox_list` shows the tool installed.

## Adam's test: slicing for his printer

After steps 1 to 5. In Telegram, typed:

> Jorah, my 3D printer is a <make and model>. Set up slicing so you can make print files for my projects.

What should happen:

1. Jorah says which slicer he picked for that printer and why. It runs headless on Linux and has
   a profile for the printer; Cura, PrusaSlicer or OrcaSlicer are the likely ones. He gives the
   version, licence (these three are AGPL or LGPL), size, and that it runs offline.
2. A card with the fields above. The source is the slicer's own GitHub release, and the release
   is at least 7 days old. Tap Allow.
3. If the slicer's smoke test shows a missing system library, Jorah proposes the Ubuntu package (a
   second card) and shows the root command for step 6.
4. Within about an hour Jorah reports from `toolbox_list` and his notes:
   - the printer profile he used and where it is (`~/work/.toolbox/examples/<slicer>/`);
   - a test slice of a small part, with the estimated print time and filament;
   - the exact command he will use for project parts.
5. To check it yourself, ask him to put the test G-code and profile into the robot project, so
   they reach GitHub with the next push card. Then open the G-code in Cura on the Mac, or print the
   test cube.

What counts as "set up correctly":
- the profile names your printer (build volume, nozzle, firmware flavour);
- the G-code starts with that printer's start code;
- the print time is plausible;
- the notes say how to slice the next part, and what wasn't checked.

If he claims a slice without a file to show, that is the failure the test looks for.

## Undo

- **Toolbox:**
  - `install-toolbox.sh --undo` (as root) removes the units and restores the firewall and main's
    tool list. `/opt/jorah-toolbox`, `/var/lib/jorah-toolbox` and the user stay.
  - To remove those too, run `rm -rf /opt/jorah-toolbox /var/lib/jorah-toolbox && userdel jorah-toolbox`,
    after removing any apt tools with `toolbox-apt.sh --remove <name>`.
  - To remove one tool: `toolbox_remove` (a card).
- **KiCad:** `install-kicad.sh --undo --dry-run`, then `--undo` and type yes.
- **Settings:** `setup-project-permissions.sh` from the commit before rewrites the project-run
  settings without the toolbox.

## Troubleshooting

- `toolbox_list` says the toolbox isn't installed: step 4 hasn't run.
- A result says `GitHub says the release was published ..., less than 7 days ago`: pick an older
  release, or wait.
- `the download's SHA-256 is ...`: the hash in the request isn't the file's. Jorah took it from the
  wrong asset, or the file changed.
- `command X: Y isn't a file inside the tool`: the path in `commands` is wrong. The installer
  removed what it had unpacked.
- The smoke test failed with a missing `lib*.so`: the tool needs an Ubuntu package (step 6).
- Notes don't get committed: `~/work/.toolbox` must stay a plain git repo on `main` with no extra
  git config. The runner's record names the problem.
