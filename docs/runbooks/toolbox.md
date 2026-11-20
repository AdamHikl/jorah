# Jorah's engineering tools and toolbox

Adam asked on 2026-11-17 that Jorah be able to use Fusion 360, a Cura slicer for his printer, a PCB
tool, coding environments and web research, and preferably install and learn new tools himself.
He approved this plan the same day. The decision is recorded in `docs/adr/0004-toolbox-installs-and-licences.md`.

**State, 2026-11-20:** installed on the PC: KiCad 10.0.8, the toolbox (empty), and the four tools
for main. See "Install record". Since 2026-11-20, GitHub release assets are looked up in code (see
"GitHub lookup"), and sizes are limits set in code, not Jorah's estimates (see "Sizes in code").
Open: deploying "Sizes in code", the end-to-end check (step 5) and Adam's slicer test.

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
   |   GitHub release asset: the plugin or the runner asks api.github.com for the release and fills
   |   in sha256, released and download_mb from GitHub's answer (Jorah gives version + URL only);
   |   installed_mb is set as a limit from the download size (fill_sizes); no other host is asked
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

**5. End-to-end check, in Telegram** (it costs one short learning run on the Max plan). Use a chat
that has already searched the web, as the 2026-11-19 test did: ask him something that needs a
web search first, or say it in the same chat as one.

> Jorah, add uv to your toolbox: it's the Python package manager. Show me the card.

Expected:
1. Jorah picks uv's latest release on GitHub and proposes it with only the version and the asset
   URL. He doesn't look for a checksum page and doesn't ask you to paste anything. If his first
   pick is under 7 days old, `toolbox_propose` refuses it and names the newest release old enough;
   he proposes that one. On 2026-11-19 that is **0.13.8** (0.13.9 came out on 2026-11-17).
2. He says its version, the licence (Apache-2.0 OR MIT), 17 MB download and up to 102 MB
   installed, that it runs offline, and that the hash and date are GitHub's own record of the
   release, which GitHub marks immutable. He doesn't ask you for a size or offer to measure one.
   Then a card titled "Jorah wants to install a tool (runs offline, read-only to him)" with:
   - `source: https://github.com/astral-sh/uv/releases/download/0.13.8/uv-x86_64-unknown-linux-gnu.tar.gz`;
   - `sha256: 5acfd9177cfecf0b` (the first 16 digits of GitHub's digest);
   - `released: 2026-11-12`;
   - `size: 17 MB download, up to 102 MB installed`;
   - id, name `uv`, version `0.13.8`, licence.
3. Tap Allow. Within a minute, `toolbox_list` (ask "what's in your toolbox?") shows uv installed.
4. Within 15 minutes it shows the smoke test passed. Within about 45 minutes the learning run is
   done and `~/work/.toolbox/notes/uv.md` exists.

If anything fails, `toolbox_list` says why. Copy that line to the build session. If Jorah says
GitHub's hourly limit is used up, ask again after the time he gives.

**5b. A tool from another host**, in the same chat:

> Jorah, add Zig 0.17.1 from ziglang.org to your toolbox. Show me the card.

Expected: he takes the SHA-256 and the release date from ziglang.org's own download page, gives no
sizes, and proposes it without asking you for anything. The card shows
`source: https://ziglang.org/download/0.17.1/zig-x86_64-linux-0.17.1.tar.xz`,
`sha256: 3581863e3cbcfd0f`, `released: 2026-11-02` and
`size: up to 1024 MB download (measured at install), installed up to 16x it, min 64 MB`. If he
gives `download_mb` because the page states it (55), the size reads
`55 MB download, up to 880 MB installed`. Tap Allow only if you want Zig. Otherwise say no; the
proposal stays inert. After an Allow, the result's `installedLimitMb` is the ceiling set from the
bytes that came.

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
2. A card with the fields above. The source is the slicer's own GitHub release asset (the x86_64
   Linux AppImage), the release is at least 7 days old, and the hash and date come from GitHub's
   record of it, as for uv. Jorah doesn't hunt for a checksum file; slicers often publish none. If
   GitHub holds no digest for that release (an old one), Jorah says so and needs the publisher's
   own checksum; pick a newer release instead if there is one. The size reads
   `<n> MB download, up to <6n> MB installed` for an AppImage: a limit, not his estimate. Tap Allow.
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

## Install record, 2026-11-18

On Adam's yes, typed in this session ("Yes, all three steps"), after the go-ahead the session that
started this one relayed from him ("go ahead on both"). Every write was followed by `sync`.

1. **Files [measured]:**
   - copied into `/opt/jorah`: 69 files from `main` at `ab57563`, the non-Gateway part only;
   - SHA-256 of all 69 matched `main`;
   - root-owned, nothing group- or world-writable;
   - the 11 files they replaced are backed up in `/root/opt-jorah-pre-toolbox-2026-11-18.tgz`;
   - each of those 11 differed from `main` only by the toolbox commit.

   Held back while the errands session had the live Gateway: `plugins/jorah-projects`,
   `plugins/jorah-guard`, `config/permission-matrix.json` and `workspace/AGENTS.md`.
2. **KiCad [measured]:**
   - dry run: the key matched the pin; 63 packages, about 140 MB to download, 893 MB installed;
   - install: `INSTALL EXIT 0` at 10:27 UTC, and as jorah `kicad-cli version` printed `10.0.8`;
   - smoke test, direct and offline, in its own network namespace: `kicad PASS ... 26 Gerber and
     drill files, board.step 8841 bytes, DRC 0 violations, 0 unconnected`;
   - the same inside Claude Code's sandbox (`--via-claude`): PASS, with `/dev/dri` absent;
   - log: `/root/install-kicad-2026-11-18.log`.
3. **Toolbox system part (`--no-gateway`) [measured]:**
   - the dry run's firewall diff added only the 7 `skuid 1103` lines;
   - install: `INSTALL EXIT 0`, user `jorah-toolbox` (uid 1103; `useradd` warned that uid 1103 is
     above SYS_UID_MAX, as for 1101 and 1102);
   - owners and modes as in the table above;
   - `jorah-toolbox.path` active, 7 firewall rules loaded;
   - the four project-run settings files rewritten, and the toolbox status `"tools": {}`;
   - log: `/root/install-toolbox-2026-11-18.log`.
4. **Incident: the live Gateway restarted at 11:27:44 CET**, during the errands session's hold on
   it.
   - Cause: the script ran `systemctl restart nftables`, and `openclaw-gateway.service` has
     `Requires=nftables.service`, so systemd restarted the Gateway with it.
   - It was back at 11:27:46 (`NRestarts=0`), and `openclaw health` answered.
   - The ephemeral port set matched the live range again.
   - Reported to the starting session at once.
   - Fixed in the script: `nft -f /etc/nftables.conf` then `systemctl restart
     jorah-firewall-ports`, which leaves the Gateway alone.
   - `scripts/pc/install-site-readers.sh` and `scripts/pc/install-phone.sh` still use
     `systemctl restart nftables`, so they restart the Gateway the same way. Not changed here.

5. **The Gateway part**, on Adam's yes typed in this session ("Yes, do it"), after the errands
   session handed the Gateway back at 10:30.
   - **Files [measured]:**
     - copied: `plugins/jorah-projects`, `plugins/jorah-guard` and `config/permission-matrix.json`
       from `main` at `3daa30e`, plus `workspace/AGENTS.md` into the live workspace;
     - 32 SHA-256 matched;
     - each differed from what was live only by the toolbox commit: the guard's own code is
       unchanged, and errands' lines are kept;
     - backups: `/root/opt-jorah-pre-toolbox-gw-2026-11-18.tgz` and `AGENTS.md.pre-toolbox`.
   - **Dry run:** `--gateway-only --dry-run` gave "Dry run successful: 1 update(s)".
   - **At 11:49:**
     - the apply added the four `toolbox_*` tools to main's list (37 entries), applied by hot
       reload;
     - `config validate` then failed with `spawn /opt/node/bin/node EACCES` and stopped the
       script before the restart;
     - the failure was false: the script ran from `/root`, which jorah can't read, and from `/`
       the config is valid.
   - **Consent:** the plugin list warned that `jorah-projects` "requires capability consent",
     because it declares four new tools. On Adam's yes ("Accept and restart"),
     `plugins enable jorah-projects --accept-capabilities` recorded the accepted tools.
   - **Restart at 11:52:24 [measured]:**
     - listening at 11:52:44 with 16 plugins, including `jorah-projects`, `jorah-guard`
       ("matrix loaded; state ok") and `jorah-errands`;
     - config valid, no plugin warnings, no errors in the log afterwards;
     - security audit 0 critical, 4 warnings, as before.
   - **Fixed in the script:** it runs from `/`, and accepts the plugin's capabilities before
     restarting.

**Still open:**
- the end-to-end check (step 5): one Telegram message from Adam, and a card;
- Adam's slicer test.

## GitHub lookup, 2026-11-19

On 2026-11-19 Adam's step 5 stalled: `toolbox_propose` needed `sha256` and `released` from Jorah.
In a chat that had read web results, `jorah-guard` (rightly) wouldn't open the release URL Jorah
had built, and GitHub's API answer for a release (about 96 KB for uv 0.13.8) is longer than
`web_fetch`'s 20,000-character cut. Adam had to paste a link.

Since then, for a GitHub release asset, code reads the release from GitHub's API
(`docs/contracts/jorah-tool-v1.md`, "GitHub release assets"):

- `toolbox_propose` in `plugins/jorah-projects` (in the Gateway, as jorah), with Node's `fetch`;
- the runner, for requests a run writes (`services/jorah-projects`, as jorah, with `urllib`). A
  request waits in `requests/` while GitHub can't be asked.

The rules are in `toolcheck.py` (`github_asset`, `check_request`, `apply_github`,
`older_release`) and their JavaScript copy, tested against the same examples
(`packages/contracts/toolbox/examples/github/`). The installer is unchanged: it asks GitHub again
at install and checks the download.

**Network [measured 2026-11-19, 17:45 CET]:**
- the Gateway runs as `jorah` (uid 1000), and the live `jorah_out` chain lets uid 1000 reach public
  TCP 443;
- as jorah on the PC, `curl` and Node's `fetch` both got HTTP 200 from
  `https://api.github.com/rate_limit`.

The project runner's unit allows `AF_INET`, and its runs already reach the network, but no lookup
from inside the unit has been measured.

**The hourly limit is shared.** GitHub allows 60 unauthenticated API requests an hour per public
address. The PC and the Mac share one: at 17:46 both had 2 left, used by build sessions' own
lookups. A test right after a busy build session can hit the limit; Jorah then says until when.
If that keeps happening, a follow-up could sign the lookups with the jorah-github App's
installation token (5,000 an hour). That is a build-session decision, because the token is a
secret.

**Deployed 2026-11-20, on Adam's yes typed in the build session ("Yes deploy it")**, with the
coordinating session's go for the live Gateway:

1. **Backup:** `/root/opt-jorah-pre-gh-lookup-2026-11-20.tgz` (77 entries): the four paths below
   and the live `AGENTS.md`. Before it, all 65 files still matched `main` at `17e2da3`.
2. **The non-Gateway part, 14:27 [measured]:**
   - `scripts/pc/deploy_reviewed.py deploy packages/contracts/toolbox services/jorah-projects
     docs/contracts/jorah-tool-v1.md` from `22ad9a1`: 50 files deployed and recorded;
   - nothing group- or world-writable;
   - as jorah, the deployed runner loads the contract, with `apply_github` and `check_request`.
3. **The Gateway part, 14:35 [measured]:**
   - `deploy_reviewed.py deploy plugins/jorah-projects`: 16 files recorded;
   - the live `AGENTS.md` copied, after a check that it was still `main` at `17e2da3`: SHA-256
     `7ba0dd0a…` equals `main`'s, `jorah:jorah 644`, backup `AGENTS.md.pre-gh-lookup`, recorded
     with `record-live`;
   - `/readyz` ready, then `systemctl start jorah-gateway-recycle.service`. The Gateway started at
     14:35:35 ("ready after 25 s", `NRestarts` 0);
   - `/readyz` at 14:36:29: `ready` true, `coreReady` true, `failing` [];
   - the plugin list shows `jorah-projects` enabled, with no consent warning (the tool names didn't
     change);
   - the log shows "http server listening (16 plugins: ... jorah-projects ...)", no line from
     `jorah-projects`, and the same warnings as at the 14:20 start.

**Found while deploying, not caused by it:** the workspace `AGENTS.md` is 29,626 characters, and
OpenClaw injects at most 20,000 per file. For `AGENTS.md` it keeps the first 9,000, a digest of
short rule lines and the last 3,000. Of the toolbox section, Jorah gets steps 3 to 5 and the
"Never" line. Step 2's opening ("you need only the version and the asset's URL ... leave `sha256`,
`released` and `download_mb` out") falls outside, unless he reads the file. `toolbox_propose`'s
own description says the same, so the lookup doesn't depend on it. Most of the Projects section is
cut the same way. Fixing that is its own task: slim `AGENTS.md`, or raise
`agents.defaults.bootstrapMaxChars` (live config, on Adam's yes).
Done 2026-11-20 with both: `docs/runbooks/jorah-on-pc.md`, "AGENTS.md whole in Jorah's context".

**Open:** Adam's Telegram test (step 5), and the slicer test.

## Sizes in code, 2026-11-20

Adam's uv test after the GitHub lookup stopped at the card: `installed_mb` was required for every
archive, uv's pages don't state it, and Jorah rightly wouldn't estimate it. Adam: "yes, fix it,
also fix it for other things".

Every field Jorah supplies, and where it comes from now:

| Field | Now | Why |
|---|---|---|
| `installed_mb` | **code**: a ceiling, download size x a factor by format (contract "Sizes"), min 64 MB; the card says "up to" | The installer uses it only as a limit (disk check, unpack cap). The factor is from 14 real releases: 4x would have refused helix, Node and Zig, whose xz tarballs grow 6.5x to 12.8x |
| `download_mb`, GitHub asset | **code**: GitHub's asset size (since 2026-11-19) | |
| `download_mb`, other hosts | **installer**: optional; measured at download, capped at 1024 MB, card says "measured at install" | Asking the host at proposal time would send a request to a host Jorah chose before Adam's card, outside the guard's URL checks. The installer downloads after the card anyway |
| `commands` paths and `strip` | **still Jorah's**, but a wrong path now fails with the archive's executables listed (sanitized, at most 8) | Publishers rarely document the layout. Listing it would mean downloading before the card; the refusal costs one new card |
| `sha256`, other hosts | **publisher only**, unchanged | The hash is the trust anchor; nothing is weakened |
| `released`, other hosts | **publisher only**, unchanged | The 7-day rule rests on it, and no host but GitHub gives a date code can read before the card |
| `licence`, `licence_source` | **publisher only**, unchanged | GitHub's detected licence is a heuristic, and the card's licence is what Adam accepts |
| `format` | Jorah's, from the file name | The file name states it; a wrong one fails at unpack, before anything is placed |
| `smoke`, `smoke_expect`, `purpose`, `title`, `homepage`, `release_page`, `name`, `version` | Jorah's | His own words or the release page's; nothing to guess |
| apt `download_mb`, `installed_mb` | optional, unchanged | apt shows them at the root command |

Also fixed: main's `AGENTS.md` (step 3) and `toolbox_propose`'s description pointed Jorah at
`/opt/jorah/docs/contracts/jorah-tool-v1.md`. Main can't read it: `tools.fs.workspaceOnly` is
true and his sandbox mounts only `/home/jorah/workspace` (checked read-only on the PC,
2026-11-20). The description now lists every field. Project runs bind `/` read-only, so the
runner's pointers to the file stay.

Deploy (not yet done): `packages/contracts/toolbox`, `services/jorah-toolbox`,
`services/jorah-projects` and `docs/contracts` (no Gateway), then `plugins/jorah-projects` and the
live `AGENTS.md` (Gateway recycle). The plugin, runner and installer need the new `toolcheck.py`
together. A proposal written before the deploy and approved after it is refused ("the card's
fields don't match ... size"): Jorah proposes it again.

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
  wrong asset, or the file changed. For a GitHub asset the hash is GitHub's own digest, so this
  means the file GitHub served differs from GitHub's record: stop and tell the build session.
- `toolbox_propose` is `unavailable` with "GitHub's API limit for this machine ... is used up until
  HH:MM UTC": the PC's address used its 60 unauthenticated lookups for the hour. Ask again after
  that time. "GitHub's API didn't answer": the network or the firewall (see "GitHub lookup" below).
- `GitHub has no published release ...`: the tag in the URL is wrong, or the release is a draft.
- `command X: Y isn't a file inside the tool (strip N); executables in it: ...`: the path in
  `commands` or `strip` is wrong. The installer removed what it had unpacked; Jorah proposes again
  with one of the paths it names (a new card).
- `unpacked it is N MB, well over the M MB limit`: the tool grows more than its format's factor
  (see the contract's "Sizes"). Jorah proposes again with `installed_mb` set to N, which the new
  card shows.
- The smoke test failed with a missing `lib*.so`: the tool needs an Ubuntu package (step 6).
- Notes don't get committed: `~/work/.toolbox` must stay a plain git repo on `main` with no extra
  git config. The runner's record names the problem.
