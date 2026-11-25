# Projects: Adam's notes, runs after answers, fewer setup questions

Built 2026-11-24 on `claude/project-notes`, after the jorah-arm start (2026-11-23) took about twenty
asks from Adam. Three fixes:

| Fix | Where | What |
|---|---|---|
| `project_note` | `plugins/jorah-projects` (`index.js`, `lib/intake.js`, `lib/runner.js`) | Adam's words for a project that answer no one question (a printer he has, "use the camera", "I approve the parts list") are appended verbatim to the runner's `inbox/intake.md`, under `## Note from Adam, <time>, via <telegram\|voice\|app>`. The runner already copies a changed intake into the project and tells the run; the run brief (`brief.md` step 3) says to read new notes first and act on them. At most 4,000 characters a note; the intake stays under 200 KB. |
| Level 0 runs itself | same plugin | `project_answer`, `project_task_result` and `project_note` file a run-now request for a level-0 project, unless one is already waiting, the project is paused, or Jorah passes `run: false` (all but the last of a batch). Levels 1 and 2 keep their schedule. The reply's `run` says what happened. |
| Fewer setup questions | `services/jorah-projects/brief-setup.md`, `templates/project/CHARTER.md` | At most two founder questions at setup, only money and safety. "Cheapest first, I have parts" is a budget. Time, openness, dates and legal get safe defaults marked "Default, Adam can change it". |
| Guard | `config/permission-matrix.json` | `project_note` is `localWrite`: free in Adam's clean chat, a card ("Jorah wants to pass your words to a project") after outside text or by voice, like an answer. |
| Rules | `workspace/AGENTS.md`, "Running Projects" | When to use `project_note`, `run: false` in a batch, "a run is starting" instead of "at its next run", and the shorter setup questions. |

Contract: `docs/contracts/jorah-project-v1.md`, `intake.md` and setup runs. The runner code is
unchanged apart from the line in `brief()` that points a run at new notes.

## Deploy (the deploy session, on Adam's yes for each step)

Run from the main checkout with `HEAD` at the commit on `origin/main` that holds this change.

```bash
cd ~/Documents/jorah && git pull --ff-only && git log -1 --oneline
```

```bash
PC=(ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root --)
```

### 0. Preflight (read only)

```bash
python3 scripts/pc/deploy_reviewed.py baseline
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
"${OC[@]}" health 2>&1 | tail -1
"${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow
systemctl is-active jorah-projects.service
test -f /home/jorah/.jorah-guard/FROZEN && echo FROZEN || echo "not frozen"
EOF
```

Expected: no drift under `plugins/jorah-guard`, `plugins/jorah-projects`, `services/jorah-projects`,
`templates/project`, `config/permission-matrix.json` or `/home/jorah/workspace/AGENTS.md`; health
ok; main's list has `project_answer` and no `project_note`; the runner `inactive`; not frozen.

### 1. Backups

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
CFG=/home/jorah/.openclaw-jorah/openclaw.json
B=/root/opt-jorah-pre-notes-$(date +%F).tgz
tar -czf "$B" -C /opt/jorah plugins/jorah-guard plugins/jorah-projects services/jorah-projects templates/project config/permission-matrix.json
[ -f "$CFG.pre-notes" ] || cp -p "$CFG" "$CFG.pre-notes"
cp -p /home/jorah/workspace/AGENTS.md /home/jorah/workspace/AGENTS.md.pre-notes
echo "$B: $(tar -tzf "$B" | wc -l) entries"
EOF
```

### 2. Code, runner, briefs, template and the permission list

Only while `jorah-projects.service` is `inactive` (a tick imports the runner as it goes).

```bash
"${PC[@]}" systemctl is-active jorah-projects.service
python3 scripts/pc/deploy_reviewed.py deploy plugins/jorah-guard plugins/jorah-projects services/jorah-projects templates/project config/permission-matrix.json
```

Expected: `inactive`, then `deployed N file(s)`, all recorded. The runner picks the new briefs up at
its next tick; the Gateway runs the old plugin until step 5.

### 3. Plugin consent and main's tool list

```bash
"${PC[@]}" bash -s <<'EOF'
runuser -u jorah -- /usr/local/bin/openclaw --profile jorah plugins enable jorah-projects --accept-capabilities 2>&1 | tail -3
EOF
```

Main's list, built from the live one plus `project_note` (dry run first):

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
T=$(mktemp -d /tmp/notes-tools.XXXXXX); chmod 755 "$T"
LIVE=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow)
python3 -I - "$LIVE" "$T/p.json5" <<'P'
import json, sys
lst = json.loads(sys.argv[1])
if not isinstance(lst, list) or not lst: sys.exit("main's tool list isn't a list; stopping")
if "project_note" not in lst: lst.append("project_note")
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(sys.argv[2], "w"))
print(f"main's list would be ({len(lst)}): " + ", ".join(lst))
P
chmod 644 "$T/p.json5"
"${OC[@]}" config patch --file "$T/p.json5" --dry-run
echo "patch file: $T/p.json5"
EOF
```

Expected: step 0's list plus `project_note` (count up by exactly 1); `Dry run successful` with one
update. On Adam's yes, run `config patch --file <that patch file>` without `--dry-run`.

### 4. Workspace rules

```bash
git show HEAD:workspace/AGENTS.md | "${PC[@]}" tee /home/jorah/workspace/AGENTS.md >/dev/null
python3 scripts/pc/deploy_reviewed.py record-live workspace/AGENTS.md=/home/jorah/workspace/AGENTS.md
```

### 5. Gateway restart

```bash
"${PC[@]}" systemctl start --no-block jorah-gateway-recycle.service
```

When the recycle service has finished:

```bash
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
journalctl -u jorah-gateway-recycle.service -n 5 --no-pager
"${OC[@]}" health 2>&1 | tail -1
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-(guard|projects)"
"${OC[@]}" sandbox explain --agent main 2>&1 | grep -E "project_note"
"${OC[@]}" security audit 2>&1 | grep -E "^Summary"
EOF
```

Expected: recycle succeeded, health ok; both plugins loaded with no "requires capability consent";
main's sandbox shows `project_note`; 0 critical.

Undo: restore the `.tgz` into `/opt/jorah`, `openclaw.json.pre-notes` (owner `jorah`, mode 600) and
`AGENTS.md.pre-notes`, recycle the Gateway, then `deploy_reviewed.py baseline --write`. Notes
already written stay in each project's `intake.md`, which the old runner also reads.

## Acceptance (Adam, in Telegram or the HUD main chat, a fresh `/new`)

1. **A note.** "For jorah-arm: I have a Bambu printer, print the brackets." Expected: no card
   (clean chat); Jorah says it passed your words to the project and that a run is starting (level
   0). Within a few minutes `project_status` shows a run; its log mentions the printer.
2. **An answer starts a run.** Answer an open question ("Q-0003 B"). Expected: recorded, and "a run
   is starting", not "at its next run".
3. **A batch.** Answer two questions in one message. Expected: one run, not two.
4. **Setup asks less.** Start a small new project with a budget approach ("cheapest first, I have
   parts"). Expected: at most two questions in the first digest, none about time, dates, openness
   or legal; the charter shows those as defaults you can change.
5. **Card after outside text.** Ask for the project digest, then send a note. Expected: a card
   titled "Jorah wants to pass your words to a project" with your exact words.

jorah-arm is at level 0; any answers given since its last run wait in the inbox until a run. After
step 5, a note or `project_run_now` starts that run.

## Pictures and wrapped questions (2026-11-25, commit `954ca09`)

- `view_image` takes at most 5 pictures a call (jorah-guard). 14 at once broke claude-cli's 8 MB
  line limit and failed the turn. `AGENTS.md`, "Pictures Adam Sends": batches of 5, notes on each;
  `deep` can't see pictures, so "use Opus" gets Jorah's notes.
- The plugin's YAML reader reads strings wrapped over several lines, in every PyYAML style, and the
  runner writes each string on one line. jorah-arm's questions had shown as unknown.

Acceptance (fresh `/new` in the HUD main chat):

1. "What's the status of jorah-arm?" Expected: the questions are listed, Q-0005 (who may move the
   arm) open; no "unknown" for `questions.yaml`.
2. "Look at the 14 inventory photos I sent yesterday and list what's in each." Expected: Jorah works
   in batches of up to 5 and says how far it is; no "Run failed ... 8388608". If it tries more than 5
   in one call, the guard refuses that call and Jorah retries in batches.

Evidence: `docs/evidence/project-notes/yamlfix-2026-11-25.md`.

## Tiers

Source and tests (`just check`, 2026-11-24). PC deploy and Gateway restart on 2026-11-25
(`docs/evidence/project-notes/deploy-2026-11-25.md`). Pictures cap and wrapped YAML deployed the same day (`yamlfix-2026-11-25.md`). Not yet: the
acceptance above, both lists.
