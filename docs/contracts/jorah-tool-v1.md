# Contract jorah-tool-v1: a request to install a tool in Jorah's toolbox

One JSON object asks for one tool. Jorah writes it, in a project or learning run as
`~/work/.toolbox/requests/<name>.json`, or from chat with `toolbox_propose`. Adam approves it on a
card. The installer then installs it (`docs/runbooks/toolbox.md`).

The checker is `packages/contracts/toolbox/toolcheck.py` (Python standard library only). Three
places run it, and each refuses what fails:

- the project runner, for requests a run writes;
- the `jorah-projects` plugin, through its JavaScript copy in `plugins/jorah-projects/lib/toolbox.js`,
  which is tested against the same examples;
- the installer, again, just before it installs.

To check a request yourself, run `python3 -I /opt/jorah/packages/contracts/toolbox/toolcheck.py
request.json`. It prints the problems and exits 1 if there are any.

## Fields

Unknown fields are refused. Text has no spaces at either end and no control characters.

| Field | Kind | Required | Rule |
|---|---|---|---|
| `contract` | all | yes | `"jorah-tool-v1"` |
| `name` | all | yes | `a-z`, digits, `-`; 2 to 40; starts with a letter. One tool per name |
| `title` | all | yes | One line, at most 80 |
| `version` | all | yes | Letters, digits, `. + _ ~ -`; at most 30 |
| `kind` | all | yes | `archive` (a download) or `apt` (Ubuntu packages) |
| `purpose` | all | yes | 10 to 600 characters: what Jorah will do with the tool. The learning run's task, and Adam reads it |
| `for_project` | all | no | The project it's first for, or `null` |
| `homepage`, `release_page` | all | yes | `https` URLs on public hosts |
| `licence` | all | yes | An SPDX expression where one exists, or `proprietary: <name>`. At most 60 |
| `licence_source` | all | yes | Where the licence is stated: a URL, or a path inside the download |
| `released` | all | yes | `YYYY-MM-DD`, at least 7 days before today (Adam's rule). For `apt`, the date of the candidate version in Ubuntu's archive |
| `sandbox` | all | yes | Exactly `{"network": []}`. Toolbox tools run offline inside the project sandbox. A tool that needs the network while it runs is a build-session decision |
| `smoke` | all | yes | A command line, 1 to 20 arguments. The first is one of the tool's `commands` (archive) or a command name (apt). The runner runs it offline after the install |
| `smoke_expect` | all | no | Text the smoke command's output must contain |
| `url` | archive | yes | `https`, a public host, at most 150 characters, so the card shows it in full |
| `sha256` | archive | yes | 64 lower-case hex digits, from the publisher's own checksum, not computed by Jorah from a download |
| `format` | archive | yes | `tar` (any compression), `zip`, `appimage` (type 2, squashfs) or `file` (a single binary) |
| `strip` | archive | no | 0 to 3 leading folders to drop, for `tar` and `zip` only |
| `download_mb`, `installed_mb` | archive: yes; apt: no | | Whole megabytes, from 1 to 4096 and 16384. No fractions anywhere, so Python and JavaScript hash the request alike |
| `commands` | archive | yes | 1 to 12 entries of `{name: path inside the tool}`. Names: `a-z`, digits, `. _ + -`. Paths: plain parts only (letters, digits, `. _ + @ -`), with no `..`. Each becomes a wrapper in `/opt/jorah-toolbox/bin`. A `file` tool has exactly one |
| `env` | archive | no | At most 12 variables the wrapper sets, such as a tool's data folder. The only `$` allowed is `${TOOL}` (the tool's folder) and `${STATE}` (its writable state folder, `~/sandbox/.cache/jorah-toolbox/<name>`). No backquote, double quote, backslash or newline. `PATH`, `HOME`, `LD_*`, `BASH_ENV` and similar can't be set |
| `packages` | apt | yes | 1 to 20 Ubuntu package names, at most 134 characters together |

## Names the tools use

- **Proposal id:** `tb-` and the first 10 hex digits of `digest(manifest)`. That is the SHA-256 of
  the request's canonical JSON: keys sorted, no spaces, UTF-8, non-ASCII kept (Python's
  `json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`). The same request
  always gets the same id, and any change gives a new one.
- **Card fields:** the ones `toolbox_install` takes and Adam's card shows:
  - `id`, `name`, `version`
  - `source`: the URL, or `Ubuntu archive: <packages>`
  - `sha256`: the first 16 hex digits, or `none (Ubuntu's signed archive)`
  - `licence`, `released`
  - `size`: `<download> MB download, <installed> MB installed`

  The plugin refuses a request whose card would be cut. The guard cuts lines at 160 characters
  and a card at 500.

## Examples

These are in `packages/contracts/toolbox/examples/`:

- `good/`: `uv` (a tarball), `orca-slicer` (an AppImage) and `java` (Ubuntu packages). Their
  values are illustrative, and the all-zero hashes aren't real.
- `bad/`: one example per rule. `expected.json` names the reason each must fail for, and the
  digests both languages must compute.

## What a request can't do

- Run anything at install. The installer unpacks and copies only, and AppImages are unpacked with
  `unsquashfs`.
- Need root, a new apt repository or signing key, network access while it runs, or a service. All
  of those are a build session's job, on Adam's yes.
- Install from a release younger than 7 days. For a GitHub release asset, the installer asks
  GitHub's API for the date itself and ignores the request's.
