# ADR 0004: Jorah installs his own tools, on Adam's card

**Decision:** Adam approved the plan on 2026-11-17 ("Yes, build it"). Jorah may propose tools for
his toolbox. Each install needs Adam's yes on a card that shows exactly what installs. The tool is
installed by fixed code that never has root. Adam's yes on that card also accepts the tool's
licence for personal use. As in ADR 0003, licences are checked again before anything built with
the tool is published or sold.

## Context

Adam asked for engineering tools (CAD, a slicer for his printer, PCB, coding, research), and
preferably for Jorah to install and learn tools himself. The repo's rules still hold:

- Adam says yes to every install.
- Dependencies wait 7 days.
- Licences are checked.
- Adam does every `sudo` prompt.
- Project runs stay offline apart from npm and PyPI.

## What the decision covers

| Kind | Who acts | Root | Where it goes |
|---|---|---|---|
| A release archive, a single binary or an AppImage | Card, then the installer (user `jorah-toolbox`) | Never | `/opt/jorah-toolbox` |
| Ubuntu packages from Ubuntu's own archive | Card, then **Adam runs one root command** (`scripts/pc/toolbox-apt.sh <id>`). It refuses any package from another origin | Adam's | The system |
| A new apt repository or signing key, network access for runs, a service, anything else needing root | A build session, on Adam's yes, as for KiCad (`scripts/pc/install-kicad.sh`) | Adam's | As reviewed |
| npm and PyPI packages inside a project | The run itself. The sandbox already allows both registries, and the settings enforce the 7-day rule (`npm_config_min_release_age=7`, `PIP_UPLOADED_PRIOR_TO=P7D` for pip 26.1 and newer, `UV_EXCLUDE_NEWER="7 days"`) | Never | The project's own folder |

## Why this is safe enough

**The card shows exactly what installs.** It shows the id, name, version, source, the first 16
digits of the SHA-256, the licence, the release date and the sizes. `toolbox_install` takes those
fields, the plugin refuses them unless they equal the stored proposal, and the installer checks
the proposal's hash again. A proposal edited after Adam saw it has a different id and is refused.

**The installer trusts the source's record over Jorah's word.**
- It refuses a file whose SHA-256 differs.
- For a GitHub release asset, it reads the release's publication date and GitHub's own digest of
  the asset from GitHub's API, and refuses a release under 7 days old, a draft or pre-release, or
  a digest that differs.
- For other hosts, the record says the date is the request's own.

**Nothing downloaded runs during the install.** tar and zip are unpacked by Python with the `data`
filter: no absolute paths, no links out, no devices, no setuid. AppImages are unpacked by
`unsquashfs` at the squashfs offset, and setuid and write bits are cleared. Code from the download
first runs in the runner's smoke test, under bubblewrap with no network and an empty home folder,
then in the project sandbox.

**The installer's user can do little.** `jorah-toolbox` has no login, no home and no sudo. It can't
read Jorah's home or secrets. Its firewall rule allows DNS and public HTTPS only. Its systemd unit
is strict (`ProtectSystem=strict`, `ProtectHome=yes`, no capabilities, `MemoryDenyWriteExecute`).

**Runs can read the toolbox but never write it.** `/opt/jorah-toolbox` is owned by `jorah-toolbox`,
and the project-run settings deny writes to it. Only the plugin, outside the sandbox, writes the
installer's queue.

## Licences

The card shows each tool's licence, and the proposal records where it is stated. Adam's yes
accepts the licence for using the tool locally. A tool's licence doesn't reach what Jorah makes with
it: a slicer's AGPL doesn't apply to G-code, and KiCad's GPL doesn't apply to a board.

`proprietary: <name>` licences need a closer look, and Jorah says so when he proposes one. Before
anything built with toolbox tools is published, sold or redistributed, the licences of those tools
and of anything they bundle are checked again, as in ADR 0003.

## KiCad

KiCad 10.0.8 comes from KiCad's official PPA, a new apt source with its own key. It is a
build-session install (`scripts/pc/install-kicad.sh`), pinned in `deploy/kicad/versions.env`.

- KiCad itself is GPL-3.0-or-later [from memory, not checked this session: check before
  redistributing anything of KiCad's].
- Its libraries (symbols, footprints, 3D models) are CC-BY-SA 4.0. For designs made with them, the
  copyright holder waives the share-alike article, so a board's files don't have to be CC-BY-SA.
  Redistributing the libraries themselves does fall under CC-BY-SA [from
  kicad.org/libraries/license, read 2026-11-17].

## What it costs

- Every new tool adds trust in its publisher. Adam weighs that on the card.
- The 7-day rule protects only against releases pulled within a week. A slow-burn compromise isn't
  caught.
- A tool's own runtime can't reach the network in a run, so a tool that needs downloads while it
  works (Rust's crates, for example) isn't covered here. It needs a build-session decision about
  the sandbox's network.
