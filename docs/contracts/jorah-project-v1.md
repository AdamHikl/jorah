# jorah-project v1: a project's folder

The files a project keeps in its own repo so Jorah can run it: the charter, the backlog, founder
questions, tasks for Adam's hands, decisions and a run log. The runner (`services/jorah-projects`),
the plugin (`plugins/jorah-projects`) and Claude Code's project runs all read and write them, and
the runner refuses a run's changes that don't pass. Written 2026-11-16 for
`docs/plan/11-project-mode.md` (section 3, which this page details).

The machine-readable parts are in `packages/contracts/project/`: four JSON Schemas, a checker
(`projectcheck.py`) for the rules a schema can't say, good and bad examples, and their tests (in
`just unit`). Where this page and a schema differ, the schema wins. Templates for every file are in
`templates/project/`.

Nothing here has run on the PC yet. Source and unit tests only.

## Shape

```
<repo>/
  project/                  stateDir in the registry; project when left out
    CHARTER.md              Adam's. Runs never edit it
    backlog.yaml            Jorah's. Schema: backlog.schema.json
    questions.yaml          Jorah asks, Adam answers. Schema: questions.schema.json
    adam-tasks.yaml         Jorah writes, Adam reports. Schema: adam-tasks.schema.json
    DECISIONS.md            Both. Append-only
    log/YYYY-MM-DD.md       Runner and Jorah. Append-only, one file a day
    research/               Jorah. Notes with sources, dates and unverified
    field-data/             Runner only. A-xxxx-<n>.<ext>, from Adam's results
```

`log/`, `research/` and `field-data/` may each hold a `README.md` (the templates do).

## Who writes what

| Field or file | Written by | Enforced by |
|---|---|---|
| `CHARTER.md` | Adam (by hand, or the runner from an answered charter question) | Runner reverts a run's change and marks the run `state-rejected` |
| `questions[].answer` | **Runner only**, from `inbox/answers.jsonl` or the default at `decide_by` | Runner compares `founder_fields()` before and after a run; any change by the run is reverted |
| `tasks[].result`, `field-data/` | **Runner only**, from `inbox/results/` | The same |
| Everything else in the YAML files | Jorah's runs | Schemas and the checker |
| `DECISIONS.md`, `log/` | Runs append; the runner appends founder input | Append-only by rule (not yet checked in code) |

## Format

- **YAML, narrowed.** Read with PyYAML's safe loader, plus: dates stay text (`2026-11-16` is the
  string, checked by the schema's `format: date`); duplicate keys, anchors and aliases are refused;
  a file over 2 MB is refused. Python tags fail as they would in any safe loader.
- **Quote text with `, ` or `: ` in flow style.** In `{ key: A, text: ..., consequence: ... }` and
  `[ ... ]`, an unquoted comma ends the value: `consequence: Small robot, low price` silently turns
  `low price` into a field, which the schema then refuses. Quote it, or use block style. The
  templates use block style in their comments for this reason.
- **Ids:** `T-0001` backlog items, `Q-0001` questions, `A-0001` Adam tasks: the letter, a hyphen and
  exactly 4 digits. Never reused, even when an item is dropped or a question withdrawn.
- **Dates** `YYYY-MM-DD`, real calendar dates. **Times** (`answer.at`, `result.at`) ISO 8601 with an
  offset, written by the runner.
- **Every state file** starts with `version: 1`. Unknown fields fail everywhere.
- **Checker messages** name the file, the place and the rule, never the value, so they can go into
  run records and the digest.

## `backlog.yaml`

```yaml
version: 1
items:
  - id: T-0001
    title: Size the drive motors for 250 kg on a 10% slope   # 1-200 characters
    track: eng                # eng | biz | research | ops | adam
    status: ready             # ready | doing | blocked | done | dropped
    priority: 2               # 1 (highest) to 5
    depends_on: [T-0003]      # optional, [] when left out
    blocked_on: null          # optional: Q-xxxx, A-xxxx or null
    acceptance: Torque and power per wheel with the inputs listed, two motor candidates with prices
    evidence: []              # optional: paths, commit SHAs or URLs; required when done
    # note: ...             # optional text; required when dropped (the reason)
    created: 2026-11-16
    updated: 2026-11-16
  - id: T-0004
    title: Tap flow at the dock
    track: adam
    adam_task: A-0001         # required on track adam, refused on the others
    ...
```

Rules beyond the schema:

| Rule | Message |
|---|---|
| Ids unique | `id T-0001 is used twice` |
| `depends_on` names existing items, not itself, and has no cycle | `depends on T-0009, which isn't in the backlog`, `depends on itself`, `dependency cycle T-0001 -> T-0002 -> T-0001` |
| `blocked_on` names an existing question or task (when that file is present) | `blocked on Q-0099, which doesn't exist` |
| `status: blocked` names what it waits for | `is blocked but names no blocked_on and no depends_on` |
| `status: done` has evidence | `is done without evidence` |
| `status: dropped` has a reason in `note` | `is dropped without a reason in note` |
| `track: adam` mirrors an existing Adam task, and only that track has `adam_task` | `track adam needs adam_task`, `mirrors A-0042, which doesn't exist`, `adam_task is only for track adam` |
| `updated` is not before `created` | `updated is before created` |

`note` and `adam_task` are never `null`: leave them out, or give a value.

## `questions.yaml`

```yaml
version: 1
questions:
  - id: Q-0001
    asked: 2026-11-16
    question: Who is the first customer?                    # 1-400
    why_it_matters: Sets the robot's size, price target and who we interview first
    options:                                                 # 2 to 6
      - key: A                                               # A to F
        text: Private garden owners
        consequence: Small robot, low price, many sales
      - key: B
        text: Landscaping firms
        consequence: Fewer buyers, pay for saved labour
    recommendation: B         # an option key, or null when it's purely Adam's call
    default_if_silent: null   # an option key, or null to wait
    decide_by: 2026-11-20     # or null; required when there is a default
    status: open              # open | answered | defaulted | withdrawn
    answer: null              # runner only, see below
```

All ten fields are required on every question (`null` where allowed). `answer`, when set:

```yaml
answer: { key: B, note: "Saturdays only", by: adam, via: telegram, at: "2026-11-17T19:02:00+01:00" }
```

| Field | Values |
|---|---|
| `key` | An option key, or `null` when Adam answered in words only (then `note` is required) |
| `note` | Adam's words beyond the key, or `null` |
| `by` | `adam`, or `default` when the runner applied `default_if_silent` at `decide_by` |
| `via` | `telegram`, `voice`, `phone`, `chat`, or `default` (exactly when `by` is `default`) |
| `at` | When the runner recorded it, with an offset |

**Defaults** apply only to cheap, reversible choices. Anything about money, direction, safety, the
law or anything public has `default_if_silent: null` and waits. The checker can't tell a choice's
nature, so this rule is the brief's and the reviewer's, not the schema's.

Rules beyond the schema:

| Rule | Message |
|---|---|
| Ids unique; option keys unique within a question | `id Q-0001 is used twice`, `option keys repeat` |
| `recommendation`, `default_if_silent` and `answer.key` are option keys | `recommendation isn't one of the option keys` |
| A default has a `decide_by`; `decide_by` is not before `asked` | `a default needs decide_by`, `decide_by is before asked` |
| `open` and `withdrawn` have no answer; `answered` and `defaulted` have one | `an open question has no answer`, `an answered question needs answer` |
| `answered` is `by: adam`; `defaulted` is `by: default` with the default's key | `an answered question is answered by adam`, `a defaulted question's answer is the default, by default` |
| An answer has a key or a note | `answer needs a key or a note` |

## `adam-tasks.yaml`

```yaml
version: 1
tasks:
  - id: A-0001
    title: Time the tap's flow
    why: Sets the dock's fill time and whether a buffer tank is needed
    when: Any day, 10 minutes          # when and how long, in words
    steps:                             # 1 to 30
      - Fill a 10 L bucket from the tap the dock will use
      - Time it with a phone stopwatch
      - Repeat twice
    materials: [10 L bucket, phone]    # optional
    send_back: The three times in seconds, and a photo of the tap
    status: open                       # open | done | skipped
    result: null                       # runner only
```

`result`, when set: `{ text, files, at }`. `text` is Adam's words or `null`; `files` lists paths
`field-data/A-0001-<n>.<ext>` (letters, digits, `_` and `-` before the extension); `at` has an
offset.

Rules beyond the schema:

| Rule | Message |
|---|---|
| Ids unique | `id A-0001 is used twice` |
| `open` has no result; `done` has one; `skipped` may carry one (Adam's reason) | `an open task has no result`, `a done task needs result` |
| A result has text or files | `result needs text or files` |
| Files are named for their own task and exist in `field-data/` | `result file isn't named for this task`, `result file field-data/A-0001-1.jpg is missing` |

Every Adam task is mirrored in the backlog by an item with `track: adam` and `adam_task: A-xxxx`, so
the backlog shows everything in one list. The checker checks the mirror's target exists; it doesn't
require a mirror for every task.

## `CHARTER.md`, `DECISIONS.md`, `log/`

Markdown, so not schema-checked beyond existing (`CHARTER.md` and `DECISIONS.md` must exist) and
the log's file names (`log/YYYY-MM-DD.md`, real dates, plus an optional `README.md`). Their formats
are in the templates:

- **Charter:** mission, founder's intent, non-goals, constraints (money, time, safety, legal,
  openness), success by date, decision rights, budget. A section not yet settled says
  `Open: Q-xxxx`.
- **Decisions:** one entry per decision, newest last: who, decision, why, evidence, how reversible,
  what it replaces.
- **Log:** one section per run: did, found, tier reached (written, built, tested in simulation,
  tested on hardware), new ids, problems, next.

## Registry entry (`project-config.schema.json`)

One entry per project in `/home/jorah/.config/jorah-projects/projects.json` (mode 600), keyed by a
name matching `^[a-z0-9][a-z0-9-]{0,62}$`:

| Field | Required | Values |
|---|---|---|
| `repo` | yes | `owner/name` |
| `workDir` | yes | Absolute path, no `.`, `..` or `//` parts. The runner also keeps it under its work root |
| `branch` | yes | Under `jorah/`, the only branches the GitHub App may write |
| `stateDir` | no (`project`) | Relative path, no `.` or `..` parts, not under `.git` |
| `level` | yes | 0 supervised, 1 scheduled, 2 standing grant (plan section 6) |
| `schedule` | yes | Up to 8 distinct `HH:MM` times in the PC's local time; `[]` means run-now only |
| `limits` | yes | `runsPerDay` 0-8, `minutesPerRun` 5-120, `maxTurns` 1-500 |
| `web` | no (`false`) | WebSearch and WebFetch in runs |
| `bench` | no (`null`) | `robotics` or `null` |
| `paused` | yes | boolean |

## Using the checker

```bash
python3 packages/contracts/project/projectcheck.py ~/work/tree-watering-robot/project
python3 packages/contracts/project/projectcheck.py --registry ~/.config/jorah-projects/projects.json
```

Exit 0 when valid, 1 with one problem per line, 2 on bad usage. Needs Python 3 and PyYAML (on
the Mac, on GitHub's Ubuntu runners, and `python3-yaml` on Ubuntu 24.04). From Python:

| Function | Returns |
|---|---|
| `check_project(dir)` | Every problem in a project folder, `[]` when valid |
| `check_registry(obj)` | Problems in a parsed `projects.json` |
| `load_yaml(path)`, `load_yaml_text(text)` | Parsed YAML, narrowed as above; raises `LoadError` |
| `check_file(kind, data)` | Schema problems of one parsed file (`backlog`, `questions`, `adam-tasks`) |
| `check_backlog`, `check_questions`, `check_adam_tasks` | The rules beyond the schema, for one parsed file |
| `founder_fields(questions, tasks)` | `{id: answer or result}`, for the runner's before-and-after comparison (PM-T2) |

## Changes

- **v1, 2026-11-16.** First version. Compared with the plan's first draft of section 3: backlog items
  gained `adam_task` (the mirror link) and `note` (the drop reason); `depends_on`, `blocked_on` and
  `evidence` became optional with empty defaults; `answer.by` may be `default`; `via` is an enum;
  the plan's flow-style example had unquoted commas, now quoted. Plan section 3 was updated in the
  same commit.
