# jorah-projects: the project runner

Runs Claude Code headless on a project's backlog, on a schedule or on "run now", outside OpenClaw
(which refuses ACP from sandboxed sessions). Plan: `docs/plan/11-project-mode.md`, sections 4
and 5.1.
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
   settings file. A work folder that exists but isn't a git repo is left alone (skipped).
4. **Lock** `~/.jorah-projects/<project>/lock` (flock). Busy: the trigger waits.
5. **Work folder**: a missing one is made, see "Starting a project".
   **Sync** with `plugins/jorah-github/bin/jorah-github-sync.mjs` (read-only token, into the
   plugin's mirror), fetch the mirror into the work repo, create `jorah/line` from the default
   branch the first time, then **merge** the default branch in (never rebase). A conflict is left
   for the run as its first task; if the run doesn't finish it, the merge is undone. A
   local-only project skips all of this: its line starts from local `main`.
6. **Setup** if the line has no charter, or the last setup didn't finish: see below.
   **Intake**: `inbox/intake.md` copied verbatim to `<stateDir>/intake.md` when it changed;
   `inbox/answers.jsonl` and `inbox/results/` into `questions.yaml`, `adam-tasks.yaml`
   and `field-data/`, committed as "Founder input from Telegram". Due defaults, after a 48-hour
   hold. The only writer of `answer` and `result`.
7. **Brief** from `brief.md` (`brief-setup.md` in a setup run), then **Claude Code**: the pinned binary, `CLAUDE_CONFIG_DIR` the Max
   login, `-p` stream-json, `claude-opus-5-5`, effort high, `--max-turns`, `--setting-sources ""`
   with the project-run settings file (`~/.claude-jorah/project-settings[-setup][-web].json`, from
   `scripts/pc/setup-project-permissions.sh`; the setup pair is used only in a setup run and is the
   same minus the deny on editing `CHARTER.md`; all four must exist or the run is skipped), no MCP servers, the bench's `env.sh` if `bench` is set, and
   a wall-clock kill at `minutesPerRun`.
8. **Checks**: uncommitted work committed; state files that fail the contract (schemas and
   cross-file rules) put back; the charter (except in a setup run), `intake.md`,
   `answer`, `result` and the statuses that go with them put back (Adam's own changes on GitHub's
   default branch are accepted through the merge); gitleaks with `--redact` and the runner's own
   config on everything since the last clean scan. A finding, or a scan that can't run, pauses the
   project and sets `pushBlocked`.
9. **Record** `runs/<id>.json` and **report** `outbox/<id>.json`, then unlock.

## Starting a project (plan 11 section 5.1)

Jorah sets a project up itself; no build session does it. The plugin's `project_start` writes the
registry entry and Adam's own words to `~/.jorah-projects/<name>/inbox/intake.md`, then asks for a
run.

- **Clone.** A missing work folder with `repo` set is cloned with `jorah-github-sync.mjs clone`
  (`github_clone`'s mirror-first flow: remote `github` reads the plugin's mirror, sandbox
  placeholders excluded). A failed clone is an error record and leaves no folder.
- **Local only.** `repo: null` means no GitHub repo yet. A missing work folder is made locally:
  `git init -b main` with no template (no sample hooks), the sandbox placeholders in
  `.git/info/exclude`, one empty commit "Start <name>". No sync, no merge, no network, nothing to
  push; `jorah/line` starts from local `main`; the digest says "local only".
- **Connecting later.** When `repo` is set on a project that ran local-only (`state.json`
  `localOnly`), the first sync merges `github/<default>` into the line once with
  `--allow-unrelated-histories` ("Connect jorah/line to github/main …"); a conflict is the run's
  first task, as for any merge. When the default branch is in the line, `state.json` gets
  `connected: {at, repo, defaultBranch, head}` and `localOnly: false`. Unrelated histories on any
  other project stop the run. Never a rebase or a force.
- **Setup run.** After sync and merge, a line with no `<stateDir>/CHARTER.md` (or `state.json`
  `setup: running|pending`) gets a setup run. The runner copies `templates/project/`
  (`/opt/jorah/templates/project`, or runner.json `templates`) into `<stateDir>/`, file by file and
  never over a file that's there, plus the intake, commits "Project folder from templates and
  founder input" as trusted, and sets `setup: running`. The brief is `brief-setup.md`: read the
  repo and the intake, draft the charter with "Open: Q-xxxx" where Adam must decide, seed
  questions, backlog and Adam tasks, no project work, check with `projectcheck.py`. Only a setup
  run may change `CHARTER.md`; `intake.md` stays protected. The run is judged after the usual
  checks: `setup: done` only if it ended `ok`, the five required files are there, the charter is
  no longer the template and every state file passes the contract. Otherwise `setup: pending`,
  the record's reason says why, and the next run is a setup run again.
- The run record has `workDir` (`cloned`, `created` or null), `setup` (`{status, copied, intake,
  why}` or null) and `founderInput` (`{sha256, copied}` or null). The outbox item has `setup`,
  `localOnly` and `notes`, e.g. "set up: charter draft and 4 questions ready" or "local only: no
  GitHub repo yet, so nothing is synced or pushed".

## Safety, briefly

- Claude Code's own sandbox, measured on the PC with `project-settings-web.json` (2026-11-17):
  `~/.ssh`, `~/.openclaw-jorah`, `~/workspace` and `~/.config/jorah-github` are hidden; a write to
  `~` lands on a masked layer and never reaches the real home; `~/work` is writable; example.com is
  refused and pypi.org is open. Its permission rules deny editing `intake.md` always and
  `CHARTER.md` outside setup runs (Edit rules only: Claude Code ignores `Write(path)` rules for
  files). These are the second line; the runner's checks after every run are the first.

- The work repo is untrusted. Its `.git/config` must hold only allow-listed keys (no hooks,
  fsmonitor, filters, includes, ssh command), and every git the runner or gitleaks starts runs
  with pinned config. Files are read and written with no symlink anywhere in the path.
- The runner never pushes. A push goes through `jorah-github`'s card, and `jorah-github` refuses
  any push or pull request from the project's folder while `pushBlocked` is set, or while the
  registry or `state.json` can't be read (`projectPushBlock` in `plugins/jorah-github/github.js`).
  Resuming the project clears it.
- Records hold ids, statuses, SHAs, file names and commit subjects; never prompts, file contents
  or secrets.

## Runner state (shared with the plugin `jorah-projects`)

`~/.jorah-projects/` (700, files 600): `usage.json` (global backoff and last usage seen),
`requests.signal` (the plugin touches it after writing a request; the path unit watches it), and
per project `state.json`, `runs/`, `outbox/`, `inbox/intake.md`, `inbox/answers.jsonl`, `inbox/applied.json`,
`inbox/results/`, `requests/`, `lock`. Formats: the WS2 hand-over note in the session notes, and
the code (`runner.py`, `intake.py`).

- Answer: one line `{"v":1,"id":<uuid4>,"question":"Q-0001","key":"B"|null,"note":…,"by":"adam","via":"telegram","at":…}`.
- Result: `inbox/results/<uuid4>.json` `{"v":1,"id","task":"A-0001","text","files":[names in inbox/results/files/],"at"}`.
- Request: `requests/<name>.json` `{"v":1,"id","type":"run-now"|"pause"|"resume","by","at"}`.

## Model, effort and quota step-down

All quota step-down settings are **off by default** (`weekly_soft` is `None`) until Adam picks values, so today's behaviour is unchanged unless configured.

- **Per-project `model` and `effort`** (optional in `projects.json`): `model` may be `opus`, `sonnet`, `haiku`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, or `null`; `effort` may be `low`, `medium`, `high`, `xhigh`, `max`, or `null`. Absent or `null` uses the runner defaults (`claude-opus-5-5`, `high`).
- **Soft step-down** (`Settings`: `weekly_soft`, `tight_model`, `tight_effort`; `runner.json`: `weeklySoft`, `tightModel`, `tightEffort`): defaults are `weekly_soft = None` (off), `tight_model = "claude-sonnet-5-5"`, `tight_effort = "medium"`. When `weekly_soft` is set and fresh seven-day utilization is at or above `weekly_soft` and below `weekly_ceiling` (`0.85`), the run goes ahead with `tight_model`/`tight_effort` (clamped so it is never stronger than the project's own setting) and records/logs `stepped down: weekly NN%`. At or above `weekly_ceiling` runs still skip; unknown or stale utilization keeps today's handling.
- **Usage-limit backoff** (`Settings`: `usage_backoff_minutes`, default `60`; `runner.json`: `usageBackoffMinutes`): minutes to back off after a usage-limit hit when no future `resetsAt` time is known. When `resetsAt` is known, the runner still waits until reset.
- **Billing:** `CLAUDE_CONFIG_DIR` stays Jorah's Max login; there is no API-key fallback.
- **Open decision:** capped API fallback for project runs: Adam's yes, a cap in euros, and which key.

## Tests

`python3 -m unittest discover -s services/jorah-projects/tests` (in `just unit`): a stand-in
`claude` that edits and commits, a local bare repo as GitHub, a stand-in sync command, and the
real sync and clone CLI against a stand-in GitHub API. `test_starting.py` covers setup runs, the
intake, clone, local-only init and connecting. Needs git, PyYAML, node and gitleaks; no network or
model. State is checked with WS1's contract checker, `packages/contracts/project/projectcheck.py`,
the same one the runner imports at run time.
