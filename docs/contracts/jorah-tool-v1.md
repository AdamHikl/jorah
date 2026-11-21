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
| `released` | all | yes, except for a GitHub release asset | `YYYY-MM-DD`, at least 7 days before today (Adam's rule). For a GitHub release asset, leave it out: GitHub's `published_at` (UTC) fills it in. For `apt`, the date of the candidate version in Ubuntu's archive |
| `sandbox` | all | yes | Exactly `{"network": []}`. Toolbox tools run offline inside the project sandbox. A tool that needs the network while it runs is a build-session decision |
| `smoke` | all | yes | A command line, 1 to 20 arguments. The first is one of the tool's `commands` (archive) or a command name (apt). The runner runs it offline after the install |
| `smoke_expect` | all | no | Text the smoke command's output must contain |
| `url` | archive | yes | `https`, a public host, at most 150 characters, so the card shows it in full |
| `sha256` | archive | yes, except for a GitHub release asset | 64 lower-case hex digits. For a GitHub release asset, leave it out: GitHub's digest of the asset fills it in. Otherwise the publisher's own checksum, not computed by Jorah from a download |
| `format` | archive | yes | `tar` (any compression), `zip`, `appimage` (type 2, squashfs) or `file` (a single binary) |
| `strip` | archive | no | 0 to 3 leading folders to drop, for `tar` and `zip` only. `commands` paths start below them |
| `download_mb` | all | no | Whole megabytes (MiB), 1 to 4096. No fractions anywhere, so Python and JavaScript hash the request alike. For a GitHub release asset, leave it out: the asset's size, rounded up, fills it in. Elsewhere give it only when the publisher states it; without it the installer measures the download and stops past 1024 MB (see "Sizes") |
| `installed_mb` | all | no | Whole megabytes, 1 to 16384; for an archive, at least `download_mb`. For an archive, leave it out: a ceiling is set from the download size (see "Sizes"). Never Jorah's estimate |
| `commands` | archive | yes | 1 to 12 entries of `{name: path inside the tool}`, the path as it is after `strip`: an archive holding `uv-x86_64-unknown-linux-gnu/uv` with `strip: 1` has the path `uv`. An `appimage` is unpacked, so its paths are inside the image: usually its `AppRun` launcher, which sets up the environment (`AppRun <program>` starts another program from its `usr/bin`), never the AppImage's file name. Names: `a-z`, digits, `. _ + -`. Paths: plain parts only (letters, digits, `. _ + @ -`), with no `..`. Each becomes a wrapper in `/opt/jorah-toolbox/bin`. A `file` tool has exactly one |
| `env` | archive | no | At most 12 variables the wrapper sets, such as a tool's data folder. The only `$` allowed is `${TOOL}` (the tool's folder) and `${STATE}` (its writable state folder, `~/sandbox/.cache/jorah-toolbox/<name>`). No backquote, double quote, backslash or newline. `PATH`, `HOME`, `LD_*`, `BASH_ENV` and similar can't be set |
| `packages` | apt | yes | 1 to 20 Ubuntu package names, at most 134 characters together |

## GitHub release assets

A `url` of the form `https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>` is a GitHub
release asset. Jorah gives the version and that URL, and no hash, date or size. Whoever
turns the request into a proposal asks GitHub's API itself, in code, with no sign-in:
`GET https://api.github.com/repos/<owner>/<repo>/releases/tags/<tag>`. That is the plugin for
`toolbox_propose`, and the project runner for requests a run writes. Then
`toolcheck.apply_github` (and its JavaScript copy):

- refuses a draft, a pre-release, an asset the release doesn't have, and an asset that isn't fully
  uploaded;
- fills in `released` from `published_at`, `sha256` from the asset's `digest` (`sha256:<hex>`) and
  `download_mb` from its `size`, where the request leaves them out;
- refuses the request where Jorah's own value differs from GitHub's. For `download_mb`, that means
  more than 3 MB or a quarter off, or too small for the installer's cap;
- for an older release with no digest on GitHub, needs `sha256` in the request: the publisher's own
  checksum, as for other hosts.

Then `check` runs on the filled-in request, so the 7-day rule uses GitHub's date. The proposal is
the filled-in request, so its id and Adam's card cover GitHub's values. Beside it, the proposal
file keeps what GitHub said:

```json
"github": {"tag": "0.13.8", "asset": "uv-x86_64-unknown-linux-gnu.tar.gz",
           "publishedAt": "2026-11-12T17:03:07Z", "assetBytes": 16855069,
           "digest": "sha256:5acfd917...", "immutable": true,
           "filled": ["released", "sha256", "download_mb", "installed_mb"], "checkedAt": "..."}
```

`immutable` is GitHub's flag for a release whose assets and tag can't be changed after
publication, or `null` when GitHub doesn't say. It is recorded, not required.

When GitHub can't be asked (the network, or the unauthenticated limit of 60 lookups an hour from
the PC's address), `toolbox_propose` answers `unavailable` with the reason and the time the limit
resets, and a run's request stays in `requests/` until the runner's next turn. GitHub answering 404
(no such published release) is a refusal. Nothing falls back to Jorah's word.

At install, the installer asks GitHub again and checks the date, the flags and the digest, then
the download's own SHA-256 against the proposal.

## Sizes

Publishers rarely state how big a tool is once unpacked, so Jorah never estimates it. Both sizes
are limits the installer enforces, and the card says so ("up to").

- **`installed_mb`:** for an archive with a download size and no `installed_mb`,
  `toolcheck.fill_sizes` (and its JavaScript copy) sets it to the download size times
  `unpack_factor`, at least 64 MB for compressed formats, at most 16384. Both languages fill it in
  before the proposal id is computed, so the id and the card cover it. Jorah may still give his
  own `installed_mb`: it is kept as the limit and refused if it's below `download_mb`.
- **`download_mb` elsewhere than GitHub:** nothing asks the host before Adam's card. A request to a
  host Jorah chose would bypass the guard's URL checks, and a proposal is a read. Without it the
  card says `up to 1024 MB download (measured at install), installed up to <n>x it, min 64 MB`.
  The installer checks there's room for a 1024 MB download, caps the download there, and sets the
  unpacked ceiling from the bytes that came (`installedLimitMb` in its result).
- **At install:** the download stops past `download_mb` x 1.1 + 5 MB, and the unpacked tool is
  refused past `installed_mb` x 1.25 + 50 MB. Free disk must hold `installed_mb` x 1.25 plus the
  20 GB reserve.

`unpack_factor` comes from 14 real Linux releases, measured on 2026-11-20 (download MB, then
unpacked MB, regular files only):

| Format, compression | Factor | Measured |
|---|---|---|
| `file` | 1 | the file is the tool |
| `zip` | 4 | Deno 40 to 92 (2.3x), Godot 74 to 140 (1.9x) |
| `appimage` | 6 | Neovim 11 to 35 (3.2x), OrcaSlicer 2.3.1 109 to 270 (2.5x) |
| `tar`, URL ending `.tar.gz` or `.tgz` | 6 | uv 16 to 37 (2.3x), gh 14 to 40 (2.8x), Neovim 11 to 34 (3.2x), Go 67 to 233 (3.5x), arduino-cli 2.0x, ripgrep 2.6x |
| `tar`, any other ending (`.tar.xz`, `.tar.zst`, `.tar.bz2`, `.tar`) | 16 | typst 17 to 53 (3.2x), Zig 55 to 357 (6.5x), Node 33 to 214 (6.6x), helix 16 to 202 (12.8x: its grammars) |

A tool that unpacks past its ceiling is refused with its unpacked size. Jorah can then propose it
again with `installed_mb` set to that size, which Adam sees on the new card.

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
  - `size`: for an archive, `<download> MB download, up to <installed> MB installed`, or the
    "measured at install" line above when there's no download size. For apt,
    `<download> MB download, <installed> MB installed`, or `not given (apt shows it before installing)`

  The plugin refuses a request whose card would be cut. The guard cuts lines at 160 characters
  and a card at 500.

## Examples

These are in `packages/contracts/toolbox/examples/`:

- `good/`: `uv` (a tarball), `orca-slicer` (an AppImage), `java` (Ubuntu packages) and `zig` (a
  tarball from ziglang.org with no sizes given). `uv`'s hash and date are GitHub's for uv 0.9.18,
  and `zig`'s are ziglang.org's for 0.17.1. The others are illustrative, and the all-zero hashes
  aren't real.
- `github/`: a request for uv 0.13.8 as Jorah now writes it (no hash, date or sizes), and
  GitHub's answer for that release, trimmed. `expected.json`'s `github` part says what both
  languages must fill in (`installed_mb` included), the resulting digest and card size, and the
  cases that must be refused. `sizes` lists ceilings and card size lines both must compute alike.
- `bad/`: one example per rule. `expected.json` names the reason each must fail for, and the
  digests both languages must compute.

## What a request can't do

- Run anything at install. The installer unpacks and copies only, and AppImages are unpacked with
  `unsquashfs`.
- Need root, a new apt repository or signing key, network access while it runs, or a service. All
  of those are a build session's job, on Adam's yes.
- Install from a release younger than 7 days. For a GitHub release asset, the date is GitHub's,
  both when proposing and again at install.
