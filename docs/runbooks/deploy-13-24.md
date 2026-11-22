# Deploy the #13–#24 batch to live Jorah

Status, 2026-11-22: **written, not run.** Nothing in it has been copied to the PC, applied or
restarted. It deploys the batch built on `claude/issues-13-24`:

- #13: deep's finds reach the reply.
- #15: long found links, and a read-only browser for `deep`.
- #18: one audit chain for two writers, and the guard report.
- #14: `project_set_capabilities`.
- #16: `project_preview` and design routing.
- #17: the runner's vendor fetcher.
- #19: Level 2's standing push grant, which stays OFF.
- #20: toolbox apt parity and the GitHub cache.
- #21: the runner's model and effort settings.

#22 (ADR 0011) and #23–#24 deploy nothing.

The steps follow `CLAUDE.md`. Only one session touches the live Gateway. Reviewed files go through
`scripts/pc/deploy_reviewed.py`, and nothing is applied without Adam's yes. **Each numbered step
needs its own yes, typed in the deploy session.** Step 9 is Adam's own.

## Who runs what

| Step | Who | Why |
|---|---|---|
| 0, 1 | the deploy session, on Adam's yes | read-only checks, then backups as root over the setup SSH key |
| 2–8 | the deploy session, on Adam's yes for each step | file deploys, config patches, plugin consent, Gateway restarts |
| 9 | **Adam, in a Terminal attached to no agent** (optional) | an apt install as root (`poppler-utils`, for PDF text) |
| A–D | **Adam, in Telegram** | acceptance |

No step needs `sudo` on the Mac. Nobody enters or reads a secret, and nobody reads
`openclaw.json`: `config get` is used only for non-secret paths.

## Shell setup (the deploy session, on the Mac)

Run everything from the main checkout, with `HEAD` on `origin/main` at the commit that holds the
batch. `deploy_reviewed.py` refuses any other `HEAD`.

```bash
cd ~/Documents/jorah && git pull --ff-only && git log -1 --oneline
```

```bash
PC=(ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root --)
```

Scripts go to the PC on stdin (`"${PC[@]}" bash -s <<'EOF' … EOF`), so Windows' quoting never
touches them. Inside them:

- `OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)`
- `CFG=/home/jorah/.openclaw-jorah/openclaw.json`

`CFG` is only ever copied, never printed.

## 0. Preflight (read only)

```bash
python3 scripts/pc/deploy_reviewed.py baseline
```

Expected: no path under `plugins/jorah-guard`, `plugins/jorah-projects`, `plugins/jorah-github`,
`services/jorah-projects`, `packages/contracts/project`, `config/permission-matrix.json`,
`scripts/pc/guard-report.py`, `/home/jorah/workspace/AGENTS.md` or
`/home/jorah/workspace-deep/AGENTS.md` in its unmatched (drift) list. A path there was changed on
the PC by hand: stop and show Adam the diff.

```bash
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
"${OC[@]}" health 2>&1 | tail -1
systemctl is-active jorah-projects.service jorah-projects.timer jorah-projects.path
"${OC[@]}" config get plugins.entries.jorah-github.config.standingGrant 2>&1 | tail -1
"${OC[@]}" config get agents.entries.deep.tools.sandbox.tools.alsoAllow
"${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow
command -v pdftotext || echo "pdftotext: not installed"
test -f /home/jorah/.jorah-guard/FROZEN && echo FROZEN || echo "not frozen"
EOF
```

Expected:

- health is ok;
- `jorah-projects.service` is `inactive` (no tick running), the timer and the path are `active`;
- `standingGrant` is not set (a "not found" or empty answer, never `true`);
- deep's list has no `browser`;
- main's list has the four `toolbox_*` names and neither `project_set_capabilities` nor
  `project_preview`;
- not frozen.

Keep both lists: steps 3 and 4 build from them. A tick in progress: wait until the service is
`inactive` before step 4.

## 1. Backups

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
CFG=/home/jorah/.openclaw-jorah/openclaw.json
B=/root/opt-jorah-pre-13-24-$(date +%F).tgz
tar -czf "$B" -C /opt/jorah plugins/jorah-guard plugins/jorah-projects plugins/jorah-github \
  services/jorah-projects packages/contracts/project config/permission-matrix.json scripts/pc/guard-report.py
[ -f "$CFG.pre-13-24" ] || cp -p "$CFG" "$CFG.pre-13-24"
for w in workspace workspace-deep; do cp -p /home/jorah/$w/AGENTS.md /home/jorah/$w/AGENTS.md.pre-13-24; done
echo "$B: $(tar -tzf "$B" | wc -l) entries"; ls -l "$CFG.pre-13-24" /home/jorah/workspace*/AGENTS.md.pre-13-24 | awk '{print $1, $3, $NF}'
EOF
```

Expected:

- one `.tgz` line with a few hundred entries;
- `openclaw.json.pre-13-24` at `-rw-------`, owner `jorah`;
- two `AGENTS.md.pre-13-24` files.

Undo: nothing to undo. The backups are what the later undos use.

## 2. The guard (#13, #15, #18)

```bash
python3 scripts/pc/deploy_reviewed.py deploy plugins/jorah-guard config/permission-matrix.json scripts/pc/guard-report.py
```

Expected: `deployed N file(s) from <commit>`, and every file recorded. The Gateway still runs the
old guard until it restarts.

Restart now, so that the new guard is the one running before `deep` gets a browser in step 3. The
old guard's rules let a browser click. `jorah-gateway-recycle.service` waits until Jorah is idle
(no turn, cron run or voice call), for up to an hour, so start it without blocking:

```bash
"${PC[@]}" bash -s <<'EOF'
systemctl start --no-block jorah-gateway-recycle.service
EOF
```

```bash
"${PC[@]}" bash -s <<'EOF'
journalctl -u jorah-gateway-recycle.service -n 5 --no-pager
runuser -u jorah -- /usr/local/bin/openclaw --profile jorah health 2>&1 | tail -1
journalctl -u openclaw-gateway --since "-10 min" --no-pager | grep -o "jorah-guard: [^\"]*" | tail -3
EOF
```

Expected:

- the recycle service ends in success;
- health is ok;
- `jorah-guard: matrix loaded; state ok`;
- no guard warning or error.

Undo:

```bash
"${PC[@]}" bash -s <<'EOF'
tar -xzf /root/opt-jorah-pre-13-24-<date>.tgz -C /opt/jorah plugins/jorah-guard config/permission-matrix.json scripts/pc/guard-report.py && sync
systemctl start --no-block jorah-gateway-recycle.service
EOF
```

Then run `deploy_reviewed.py baseline --write`, so the drift check matches.

## 3. deep's read-only browser (`config/pc/deep-browser.patch.json5`)

Only after step 2's log line. Build the patch from deep's live list plus `browser`, the way
`install-errands.sh` does. Never apply the file's placeholder.

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
T=$(mktemp -d /tmp/deep-browser.XXXXXX); chmod 755 "$T"
LIVE=$("${OC[@]}" config get agents.entries.deep.tools.sandbox.tools.alsoAllow)
python3 -I - "$LIVE" "$T/p.json5" <<'P'
import json, sys
lst = json.loads(sys.argv[1])
if not isinstance(lst, list) or not lst: sys.exit("deep's tool list isn't a list; stopping")
if "browser" not in lst: lst.append("browser")
json.dump({"agents": {"entries": {"deep": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(sys.argv[2], "w"))
print("deep's list would be: " + ", ".join(lst))
P
chmod 644 "$T/p.json5"
"${OC[@]}" config patch --file "$T/p.json5" --dry-run
echo "patch file: $T/p.json5"
EOF
```

Expected:

- deep's list is the step-0 list with `browser` at the end;
- `Dry run successful` with one update, `agents.entries.deep.tools.sandbox.tools.alsoAllow`.

Show Adam that list. On his yes, run the apply and check it:

```bash
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
"${OC[@]}" config patch --file <patch file from above>
"${OC[@]}" sandbox explain --agent deep 2>&1 | grep -i browser
"${OC[@]}" security audit 2>&1 | grep -E "^Summary"
EOF
```

Expected:

- the patch applies by hot reload;
- `sandbox explain` lists `browser` for deep;
- the audit summary shows 0 critical.

Undo: the same build without `browser` (`lst.remove("browser")`), dry run, then apply.

## 4. jorah-projects, the runner and main's tool list (#14, #16, #17, #20, #21)

Only when `jorah-projects.service` is `inactive`. A tick imports the runner as it goes, so a deploy
during a tick could mix old and new code. The briefs (`services/jorah-projects/brief*.md`) go with
the runner in this step, not in step 6. They are files the runner reads from its own folder in
`/opt/jorah`, not live workspace rules. `deploy` copies them, and `record-live` doesn't apply to
them. Shipping them with the code that acts on them keeps a run from getting the vendor-request
rule before the runner fetches vendor files.

```bash
"${PC[@]}" bash -s <<'EOF'
systemctl is-active jorah-projects.service
EOF
python3 scripts/pc/deploy_reviewed.py deploy plugins/jorah-projects services/jorah-projects packages/contracts/project
```

Expected:

- `inactive`;
- `deployed N file(s)`, with all of them recorded.

The runner takes the new code at its next tick. Its units didn't change, so no `daemon-reload` is
needed (step 8 checks it).

**Plugin consent.** The plugin declares two new tools, so OpenClaw asks for capability consent
again (as on 2026-11-18). On Adam's yes:

```bash
"${PC[@]}" bash -s <<'EOF'
runuser -u jorah -- /usr/local/bin/openclaw --profile jorah plugins enable jorah-projects --accept-capabilities 2>&1 | tail -3
EOF
```

**Main's tool list** (`config/pc/projects-tools.patch.json5` explains why). Build it from the live
list plus the two new names:

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
T=$(mktemp -d /tmp/projects-tools.XXXXXX); chmod 755 "$T"
LIVE=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow)
python3 -I - "$LIVE" "$T/p.json5" <<'P'
import json, sys
lst = json.loads(sys.argv[1])
if not isinstance(lst, list) or not lst: sys.exit("main's tool list isn't a list; stopping")
new = ["project_set_capabilities", "project_preview"]
lst += [t for t in new if t not in lst]
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(sys.argv[2], "w"))
print(f"main's list would be ({len(lst)}): " + ", ".join(lst))
P
chmod 644 "$T/p.json5"
"${OC[@]}" config patch --file "$T/p.json5" --dry-run
echo "patch file: $T/p.json5"
EOF
```

Expected:

- main's list is step 0's list plus the two names, so the count goes up by exactly 2;
- `Dry run successful` with one update.

On Adam's yes, apply it:

```bash
"${PC[@]}" bash -s <<'EOF'
runuser -u jorah -- /usr/local/bin/openclaw --profile jorah config patch --file <patch file from above>
EOF
```

The old plugin, still loaded until step 7, doesn't register the two names, so the window in between
is harmless.

Do not set `benches` in the plugin's live config. The plugin's default `["robotics"]` is the
runner's `BENCHES` and the contract's enum. A name the runner doesn't know would make
`project_set_capabilities` write a registry entry the runner refuses.

Undo:

```bash
"${PC[@]}" bash -s <<'EOF'
tar -xzf /root/opt-jorah-pre-13-24-<date>.tgz -C /opt/jorah plugins/jorah-projects services/jorah-projects packages/contracts/project
rm -f /opt/jorah/plugins/jorah-projects/lib/ghcache.js /opt/jorah/plugins/jorah-projects/lib/preview.js \
  /opt/jorah/services/jorah-projects/jorah_projects/vendor.py /opt/jorah/services/jorah-projects/tests/test_vendor.py \
  /opt/jorah/packages/contracts/project/examples/bad/project-config.effort-unknown.json \
  /opt/jorah/packages/contracts/project/examples/bad/project-config.model-unknown.json
sync
EOF
```

Then:

1. Run `deploy_reviewed.py forget` for those six paths, then `baseline --write`.
2. Build main's list without the two names, dry run it, then apply it.
3. Restart the Gateway (step 7).

## 5. jorah-github, with the grant off (#19)

```bash
python3 scripts/pc/deploy_reviewed.py deploy plugins/jorah-github
```

Expected: `deployed N file(s)`, recorded. The runner's sync command
(`plugins/jorah-github/bin/jorah-github-sync.mjs`) imports `github.js`, so it uses the new file at
once. The Gateway uses it after step 7.

The manifest's `configSchema` now lists `standingGrant`, `guardStateDir`, `selfRepos`,
`projectsRegistry` and `projectsStateDir`. That makes them settable, not set. **Set none of them.**
The grant turns on only after Adam's written yes, which waits for the P5 guard review and a week at
level 1 without incident. That is a separate change with its own preview. Its tools are the same
five, so no new consent is needed.

Check that the grant is still off:

```bash
"${PC[@]}" bash -s <<'EOF'
runuser -u jorah -- /usr/local/bin/openclaw --profile jorah config get plugins.entries.jorah-github.config.standingGrant 2>&1 | tail -1
EOF
```

Expected: not set (never `true`).

Undo:

```bash
"${PC[@]}" bash -s <<'EOF'
tar -xzf /root/opt-jorah-pre-13-24-<date>.tgz -C /opt/jorah plugins/jorah-github
rm -f /opt/jorah/plugins/jorah-github/test/grant.test.js
sync
EOF
```

Then `deploy_reviewed.py forget plugins/jorah-github/test/grant.test.js`, `baseline --write`, and a
restart.

## 6. Workspace rules

These are main's and deep's live `AGENTS.md`. Step 4 shipped the briefs.

Step 0's drift check proved that each live copy matches a version on `main`. Copy the new versions
in. `tee` keeps the live file's owner and mode.

```bash
git show HEAD:workspace/AGENTS.md | "${PC[@]}" tee /home/jorah/workspace/AGENTS.md >/dev/null
git show HEAD:workspace-deep/AGENTS.md | "${PC[@]}" tee /home/jorah/workspace-deep/AGENTS.md >/dev/null
python3 scripts/pc/deploy_reviewed.py record-live workspace/AGENTS.md=/home/jorah/workspace/AGENTS.md workspace-deep/AGENTS.md=/home/jorah/workspace-deep/AGENTS.md
```

Expected: both recorded. `record-live` refuses a file whose SHA-256 differs from git.

Jorah reads the new rules from his next turn. They name `project_preview` and
`project_set_capabilities`, which work only after step 7, so go on to step 7 straight away.

Undo, for each of the two workspaces:

```bash
"${PC[@]}" cp -p /home/jorah/workspace/AGENTS.md.pre-13-24 /home/jorah/workspace/AGENTS.md
```

Then `deploy_reviewed.py baseline --write`.

## 7. Gateway restart

This loads the new jorah-projects and jorah-github code with the new consent. The guard is already
running from step 2.

```bash
"${PC[@]}" bash -s <<'EOF'
systemctl start --no-block jorah-gateway-recycle.service
EOF
```

When the recycle service has finished:

```bash
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
journalctl -u jorah-gateway-recycle.service -n 5 --no-pager
"${OC[@]}" health 2>&1 | tail -1
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-(guard|projects|github)"
journalctl -u openclaw-gateway --since "-10 min" --no-pager | grep -oE "jorah-(guard|projects|github): [^\"]*" | tail -5
"${OC[@]}" sandbox explain --agent main 2>&1 | grep -E "project_(set_capabilities|preview)"
"${OC[@]}" security audit 2>&1 | grep -E "^Summary"
EOF
```

Expected:

- the recycle service succeeded and health is ok;
- the three plugins are loaded, with no "requires capability consent";
- `jorah-guard: matrix loaded; state ok`, and no plugin error;
- main's sandbox shows both new tools;
- the audit summary shows 0 critical.

Undo: undo steps 4–6 as written there, then restart again.

## 8. The runner

The runner is a oneshot, started by `jorah-projects.timer` every 15 minutes and by
`jorah-projects.path` on a run-now request. There is no daemon to reload, and its units are
unchanged. Check that the new code loads and reads the registry, without starting a run:

```bash
"${PC[@]}" bash -s <<'EOF'
systemctl is-active jorah-projects.timer jorah-projects.path
runuser -u jorah -- /usr/bin/python3 -I /opt/jorah/services/jorah-projects/bin/jorah-projects status | head -40
systemctl list-timers jorah-projects.timer --no-pager | head -3
EOF
```

Expected:

- `active active`;
- `status` prints JSON with the registry's projects, the schemas found, not frozen, and no backoff;
- the next timer run is within 15 minutes.

A `ConfigError` here means the registry or `runner.json` no longer validates. That is a stop: undo
step 4.

`runner.json` needs no change. `weeklySoft`, `tightModel`, `tightEffort` and `usageBackoffMinutes`
(#21) are optional and off by default.

## 9. Optional, Adam's step: PDF text for vendor files

Without `pdftotext`, a fetched datasheet lands but its text is "unknown" (no `<name>.txt` next to
it). Ubuntu's `poppler-utils` puts it in `/usr/bin`, which the runner's unit can read. It's an apt
install as root, so Adam runs it in a Terminal attached to no agent:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- apt-get install --no-install-recommends poppler-utils
```

Expected: apt lists `poppler-utils` and the libraries it needs, shows the download size and asks
Y/n. If apt says it can't find the package, run the same command with `apt-get update` in place of
the install, then the install again. After it, `command -v pdftotext` prints
`/usr/bin/pdftotext`.

Undo:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- apt-get remove poppler-utils
```

## Acceptance, in Telegram (Adam)

Open your own chat with Jorah and send `/new` first, so the chat starts clean.

B and C use one new test project, and its runs use Claude usage: up to 45 minutes each at the
default limits. To stop it at any point, send `Pause camera-mount`.

### A. Shop links from deep (#13, #15)

Send:

`Find me a 50mm f/1.8 lens for Sony E-mount in Slovak shops: price delivered to Slovakia, and the link for each.`

Expected:

- Jorah says he's asking `deep`;
- the reply lists at least two shops, each with a euro price, shipping and a clickable link to the
  product page on the shop's own site;
- no link is replaced by a "Not opened" or "link removed" note;
- a price `deep` couldn't read shows as unknown, not as a number.

Failure means #13 isn't live (go back to step 2's log line), or the shop needed the browser and
step 3 didn't apply.

### B. `project_set_capabilities` raises a card (#14, #16)

Send:

`Start a new project: design a small desk mount for a Raspberry Pi 5 with a Camera Module 3. Budget 30 euros, nothing public, call it camera-mount.`

Expected:

- Jorah starts `camera-mount` (local only) and asks no more than two questions, or none;
- he says a card is coming;
- a Telegram card: **"Jorah wants to change a project's web or bench access"**, with the exact
  change (web research on, bench `robotics`).

Tap **Allow**. Then send `Status of camera-mount`. Expected: web on, bench robotics.

A card that never comes means the tool isn't in main's list or the consent is missing (steps 4 and
7).

### C. A vendor PDF lands in `project/vendor/` (#17)

Send `Run camera-mount now`. The first run is the setup run. When Jorah reports it finished, send
`Run camera-mount now` again.

Expected, after that run:

- `What did camera-mount's last run do?` includes a line like
  `vendor file: camera-module-3-....pdf (pdf, N KB, unverified) from https://datasheets.raspberrypi.com/...`;
- on the PC (the deploy session, read only), the PDF is there with `MANIFEST.json`, and a `.txt`
  beside it if step 9 ran:

```bash
"${PC[@]}" ls -l /home/jorah/work/camera-mount/project/vendor/
```

If the run asked for nothing, the digest has no vendor line. That is a run's choice, not a
failure. A line under "refused" with a reason is the fetcher working. A run that asked and got
nothing back, with no reason given, is a failure: copy the digest to the build session.

### D. `project_preview` sends a PNG (#16)

After a run that rendered something (the brief has hardware runs put PNGs in `renders/`), send:

`Show me camera-mount's latest renders.`

Expected:

- Jorah lists the images;
- up to four arrive in Telegram as pictures, each with what the run's log says it shows.

If there are none yet, Jorah says so: no picture and no description. If he lists files but no
picture arrives, check on the PC:

```bash
"${PC[@]}" ls -l /home/jorah/workspace/media/outbound/previews/camera-mount/
```

If the files are there, the `MEDIA:` path isn't delivered from the workspace outbox. That is an
OpenClaw media question for the build session, and it is not deployed yet: check
`$(npm root -g)/openclaw/docs` on the PC for `MEDIA:` and local paths.

### Afterwards

`camera-mount` stays a local-only project at level 0, which runs only when asked. Keep it as the
test bench, or send `Pause camera-mount`. Removing it from the registry is a separate step that
needs Adam's word.

## Tiers

- Reached once this runbook has run: source and tests (the merging session's `just check`),
  install (steps 2–8), and launch (step 7's log lines, step 8's `status`).
- Signed-in device acceptance (A–D) is a separate tier, and only Adam's Telegram results count for
  it.
