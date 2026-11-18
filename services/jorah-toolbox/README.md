# jorah-toolbox: the installer for Jorah's toolbox

Installs tools Adam approved on a card into `/opt/jorah-toolbox`, as the system user `jorah-toolbox`.
It never runs as root and never runs what it downloads. The design, Adam's steps and the test are
in `docs/runbooks/toolbox.md`. The request format is `docs/contracts/jorah-tool-v1.md`, and the
decision is ADR 0004.

- `jorah_toolbox/install.py`: the queue. For each approval it:
  1. checks it again against the contract;
  2. for GitHub release assets, checks the date and digest GitHub holds;
  3. downloads the file and checks its SHA-256;
  4. unpacks it, then writes the wrappers and `installed.json`.

  An apt request only becomes `needs-root`; `record-apt` and `forget-apt` are called by
  `scripts/pc/toolbox-apt.sh` after Adam's root command.
- `jorah_toolbox/fetch.py`: https only, redirects too, size-capped, and GitHub's release record.
- `jorah_toolbox/unpack.py`:
  - tar with Python's `data` filter;
  - zip by hand, with no links;
  - AppImage (type 2) with `unsquashfs -o <offset>`;
  - a single file.

  Afterwards setuid and others' write bits are cleared, and special files are refused.
- `bin/jorah-toolbox`: `run-queue`, `status`, `check FILE`, `record-apt ID`, `forget-apt NAME`.
  Run it with `python3 -I`.

Standard library only; Python 3.12 (Ubuntu 24.04). The tests use a stand-in network and need no
root, network or unsquashfs: `python3 -m unittest discover -s services/jorah-toolbox/tests`.
The AppImage step was also checked with the real `unsquashfs` 4.6.1 in an Ubuntu 24.04 container
on 2026-11-17: an ELF followed by a zstd squashfs unpacked at the offset the code computed.

The runner's side (smoke test, learning run, notes, requests from runs) is
`services/jorah-projects/jorah_projects/toolbox.py`. The plugin's side (`toolbox_list`,
`toolbox_propose`, `toolbox_install`, `toolbox_remove`) is `plugins/jorah-projects/lib/toolbox.js`.
