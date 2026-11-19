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
| `strip` | archive | no | 0 to 3 leading folders to drop, for `tar` and `zip` only |
| `download_mb`, `installed_mb` | archive: yes (`download_mb` not for a GitHub release asset); apt: no | | Whole megabytes (MiB), from 1 to 4096 and 16384. No fractions anywhere, so Python and JavaScript hash the request alike. For a GitHub release asset, `download_mb` is the asset's size, rounded up, when left out |
| `commands` | archive | yes | 1 to 12 entries of `{name: path inside the tool}`. Names: `a-z`, digits, `. _ + -`. Paths: plain parts only (letters, digits, `. _ + @ -`), with no `..`. Each becomes a wrapper in `/opt/jorah-toolbox/bin`. A `file` tool has exactly one |
| `env` | archive | no | At most 12 variables the wrapper sets, such as a tool's data folder. The only `$` allowed is `${TOOL}` (the tool's folder) and `${STATE}` (its writable state folder, `~/sandbox/.cache/jorah-toolbox/<name>`). No backquote, double quote, backslash or newline. `PATH`, `HOME`, `LD_*`, `BASH_ENV` and similar can't be set |
| `packages` | apt | yes | 1 to 20 Ubuntu package names, at most 134 characters together |

## GitHub release assets

A `url` of the form `https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>` is a GitHub
release asset. Jorah gives the version and that URL, and no hash, date or download size. Whoever
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
           "filled": ["released", "sha256", "download_mb"], "checkedAt": "..."}
```

`immutable` is GitHub's flag for a release whose assets and tag can't be changed after
publication, or `null` when GitHub doesn't say. It is recorded, not required.

When GitHub can't be asked (the network, or the unauthenticated limit of 60 lookups an hour from
the PC's address), `toolbox_propose` answers `unavailable` with the reason and the time the limit
resets, and a run's request stays in `requests/` until the runner's next turn. GitHub answering 404
(no such published release) is a refusal. Nothing falls back to Jorah's word.

At install, the installer asks GitHub again and checks the date, the flags and the digest, then
the download's own SHA-256 against the proposal.

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

- `good/`: `uv` (a tarball), `orca-slicer` (an AppImage) and `java` (Ubuntu packages). `uv`'s
  hash and date are GitHub's for uv 0.9.18. The others are illustrative, and the all-zero hashes
  aren't real.
- `github/`: a request for uv 0.13.8 as Jorah now writes it (no hash, date or download size), and
  GitHub's answer for that release, trimmed. `expected.json`'s `github` part says what both
  languages must fill in, the resulting digest, and the cases that must be refused.
- `bad/`: one example per rule. `expected.json` names the reason each must fail for, and the
  digests both languages must compute.

## What a request can't do

- Run anything at install. The installer unpacks and copies only, and AppImages are unpacked with
  `unsquashfs`.
- Need root, a new apt repository or signing key, network access while it runs, or a service. All
  of those are a build session's job, on Adam's yes.
- Install from a release younger than 7 days. For a GitHub release asset, the date is GitHub's,
  both when proposing and again at install.
