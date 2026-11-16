# jorah-projects: the project runner

Runs Claude Code headless on a project's backlog, on a schedule or on "run now", outside OpenClaw
(which refuses ACP from sandboxed sessions). Plan: `docs/plan/11-project-mode.md`, section 4.
Status: **source and unit tests only.** Nothing is installed; the install is plan section 12.

## One tick

`jorah-projects tick` (systemd: `deploy/jorah-projects.{service,timer,path}`), for each project in
`/home/jorah/.config/jorah-projects/projects.json`:

1. **Requests** in `~/.jorah-projects/<project>/requests/`: run-now, pause, resume.
2. **Trigger**: a run-now request, or (level 1 and up) a schedule slot that's due and not more than
   3 hours late. Nothing due: done, no record.
3. **Checks**, each a skipped record if it fails: paused (registry or runner), `/jorah-freeze` (the
   guard's `~/.jorah-guard/FROZEN`, read only; a guard folder it can't see counts as frozen), runs
   a day, usage-limit backoff, the weekly limit at 85% or more, 5 GB free, the contract
   (`packages/contracts/project/projectcheck.py` and its schemas), the Claude Code binary, the
   settings file, the work clone.
4. **Lock** `~/.jorah-projects/<project>/lock` (flock). Busy: the trigger waits.
5. **Sync** with `plugins/jorah-github/bin/jorah-github-sync.mjs` (read-only token, into the
   plugin's mirror), fetch the mirror into the work repo, create `jorah/line` from the default
   branch the first time, then **merge** the default branch in (never rebase). A conflict is left
   for the run as its first task; if the run doesn't finish it, the merge is undone.
6. **Intake**: `inbox/answers.jsonl` and `inbox/results/` into `questions.yaml`, `adam-tasks.yaml`
   and `field-data/`, committed as "Founder input from Telegram". Due defaults, after a 48-hour
   hold. The only writer of `answer` and `result`.
7. **Brief** from `brief.md`, then **Claude Code**: the pinned binary, `CLAUDE_CONFIG_DIR` the Max
   login, `-p` stream-json, `claude-opus-5-5`, effort high, `--max-turns`, `--setting-sources ""`
   with the project-run settings file, no MCP servers, the bench's `env.sh` if `bench` is set, and
   a wall-clock kill at `minutesPerRun`.
8. **Checks**: uncommitted work committed; state files that fail the contract (schemas and
   cross-file rules) put back; the charter,
   `answer`, `result` and the statuses that go with them put back (Adam's own changes on GitHub's
   default branch are accepted through the merge); gitleaks with `--redact` and the runner's own
   config on everything since the last clean scan. A finding, or a scan that can't run, pauses the
   project and sets `pushBlocked`.
9. **Record** `runs/<id>.json` and **report** `outbox/<id>.json`, then unlock.

## Safety, briefly

- The work repo is untrusted. Its `.git/config` must hold only allow-listed keys (no hooks,
  fsmonitor, filters, includes, ssh command), and every git the runner or gitleaks starts runs
  with pinned config. Files are read and written with no symlink anywhere in the path.
- The runner never pushes. A push goes through `jorah-github`'s card and must respect
  `pushBlocked`.
- Records hold ids, statuses, SHAs, file names and commit subjects; never prompts, file contents
  or secrets.

## Runner state (shared with the plugin `jorah-projects`)

`~/.jorah-projects/` (700, files 600): `usage.json` (global backoff and last usage seen),
`requests.signal` (the plugin touches it after writing a request; the path unit watches it), and
per project `state.json`, `runs/`, `outbox/`, `inbox/answers.jsonl`, `inbox/applied.json`,
`inbox/results/`, `requests/`, `lock`. Formats: the WS2 hand-over note in the session notes, and
the code (`runner.py`, `intake.py`).

- Answer: one line `{"v":1,"id":<uuid4>,"question":"Q-0001","key":"B"|null,"note":…,"by":"adam","via":"telegram","at":…}`.
- Result: `inbox/results/<uuid4>.json` `{"v":1,"id","task":"A-0001","text","files":[names in inbox/results/files/],"at"}`.
- Request: `requests/<name>.json` `{"v":1,"id","type":"run-now"|"pause"|"resume","by","at"}`.

## Tests

`python3 -m unittest discover -s services/jorah-projects/tests` (in `just unit`): a stand-in
`claude` that edits and commits, a local bare repo as GitHub, a stand-in sync command, and the
real sync CLI against a stand-in GitHub API. Needs git, PyYAML, node and gitleaks; no network or
model. State is checked with WS1's contract checker, `packages/contracts/project/projectcheck.py`,
the same one the runner imports at run time.
