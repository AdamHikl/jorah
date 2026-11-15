# Proactive layer (phone-layer plan, step C)

Jorah's proactive layer: what Jorah may tell Adam without being asked, and the code that holds it back. Built 2026-11-15 on Adam's "Yes, build A–C". The rules come from `docs/plan/01-vision-and-ux.md` §11, `06-connectors.md` §3.3 and C6, and `p5-plan.md` §4 and §12. The phone service it reads is `docs/contracts/jorah-phone-v1.md` (steps A and B, another session).

## Where it stands

| Tier | State |
|---|---|
| Source | Done: `plugins/jorah-proactive`, the guard's proactive rules, `config/proactive/`, `config/pc/proactive.patch.json5`, `scripts/pc/install-proactive.sh` |
| Unit tests | Pass: 35 in `plugins/jorah-proactive/test/`, 10 new in `plugins/jorah-guard/test/proactive.test.js` (the guard's 55 earlier tests still pass), in `just unit` |
| `jorah-dev` spike | **Not run.** Three OpenClaw facts below are read from source and docs, not seen running |
| Install on the PC | Not done. Nothing copied to `/opt/jorah`, no config applied |
| Types on, automations | None. No schedule exists, and no message has been sent |
| Adam's acceptance on the iPhone and in Telegram | Not done |

**Default: silent.** With the patch as written, every type is off, so `proactive_notify` answers "off" and the tick has nothing to send. Each type goes on separately, after Adam reads its preview card. Each automation has its own yes.

**Wait for two things before installing:** the P5 log review (due about 2026-11-20), because nothing private connects before the P5 gate passes, and the phone service from steps A and B, without which the phone fields say "unavailable" and every P2 item goes to the digest.

## What each piece does

### C1: `today_picture`

One object written by code: Adam's local date, time and weekday (Europe/Bratislava), whether it is a school day (weekdays only: holidays aren't known yet), what the phone service's `GET /today` says, open loops due today or overdue, quiet hours and how many pushes are left. `calendar` and `school` say `not_connected`. Health is replaced with `status: "off"` unless `includeHealth` is on (Adam's decision H). If the phone service can't be reached, its part is `{status: "unavailable", reason}`. Nothing unknown is ever 0. The only network use in the whole plugin is `http://127.0.0.1:43212`, with the read token from `/home/jorah/.config/jorah-phone/read-token` (mode 600, read on every call). Answers are checked against `packages/contracts/phone/*.schema.json`. Weather is left to Jorah's own web search in the brief.

### C2: open loops

| Tool | What it does | Guard |
|---|---|---|
| `loop_propose(kind, who, what, due?)` | `kind`: `waiting_on_me` (someone is waiting on Adam) or `i_promised` (Adam promised to do it). `who` at most 60 characters, `what` at most 100, one line each, `due` `YYYY-MM-DD`. Stores exactly these fields, or refuses: it never trims or rewrites, so the card shows what is saved | **Always a card** with the exact fields, Allow once or Deny, even in Adam's own clean chat |
| `loops_list(status?)` | Open by default; `done`, `dropped` or `all` | Read |
| `loop_done(id)`, `loop_drop(id)` | Close a loop. Closed loops go after 30 days | Free in a clean chat; a card after outside text or by voice |

The store is the plugin's own (`/home/jorah/.jorah-proactive/loops.json`), not Jorah's memory: folder 700, files 600, written atomically. A file that can't be read is left as it is and every tool that needs it says "unavailable".

### C3: restraint in code

Every proactive item goes through `proactive_notify(type, class, text?, matters_until?, source_at?, actionable?)`. Code decides: push, the digest, or nothing. It never sends: a push goes to an outbox that only the tick automation drains.

| Class | Examples | What code does |
|---|---|---|
| P0 safety | (no type yet) | Always pushed, even in quiet hours, no budget |
| P1 decision with a deadline | `job_blocked` | Pushed, except in quiet hours: then the digest |
| P2 useful now | `home_loops`, `left_home_loops`, `job_finished` | The five checks below, then pushed; any failure: the digest |
| P3 everything else | `learned` | The digest only |
| digest | `morning_brief`, `evening_wrap` | Pushed outside quiet hours, once a day |

The model can lower a class, never raise it: the type's class in `config/proactive/types.json` is the ceiling.

**The five checks for P2**, each recorded with its data:

1. Matters in the next few hours: `matters_until` is in the future and at most 12 hours away.
2. Adam can act on it now: `actionable` is true.
3. Fresh: `source_at` is at most 30 minutes old.
4. Budget: at most 5 P2 pushes a day. The 3 spoken a day are counted but unused: nothing is spoken before M10.
5. Not busy and outside quiet hours: the phone's Focus is off or `personal`, and it isn't quiet hours. **If the phone service can't be reached, this fails**, so the item goes to the digest. Presence isn't measured (there is no `jorah-presence` yet), and the record says so.

**Quiet hours:** the proposal 22:30 to 07:30, until Adam sets them. OpenClaw's own quiet hours drop notices rather than queue them, so the plugin keeps its own: P1 items wait in the digest, P2 items go to the digest, briefs are dropped (the next one carries it). When the phone reports the alarm stopped or a wake, that morning's quiet hours end then (`awakeEndsQuiet`).

**The digest:** P3 lines, P2 lines that failed a check, P1 lines held over the night, and lines the tick couldn't deliver within their window (20 minutes for P2). `digest_list` reads it; a brief or wrap-up sent through `proactive_notify` clears what it carried.

**Lines on Telegram:** the brief, the wrap-up and the two loop types are written by code with counts and times only, never a name or a loop's text (Telegram isn't end to end, `06` §3.3). For example: "Morning brief: 2 open loops due today, 1 overdue. Woke 06:42. 3 digest items. Detail in the Jorah app." The other types carry Jorah's own line: one line, at most 300 characters, no links or web addresses.

**Learning from reactions:**

- **"Stop telling me this":** `proactive_feedback(reaction: "stop")` stops the type at once, removes what was queued, and stays until Adam undoes it. `proactive_resume` undoes it, always with a card, and can't turn on a type that is off in the settings.
- **Ignored 3 times:** a P2 push with no `proactive_feedback` within 3 hours counts as ignored, and so does "dismissed". After 3 in a row the type is demoted to the digest, and the digest asks once: "Say 'keep telling me …' to undo." "Acted" resets the count.
- **"Why did you tell me?":** `proactive_why(record)` returns the record: type, class, decision, the reason, each check with its data, and the line. Without a record it lists the types (with their preview cards), what is stopped or demoted, quiet hours, today's pushes and the latest decisions.

### C4: triggers

Three automations, written but not created. Each needs Adam's yes, and Adam runs each command (`automations add` needs `operator.admin`).

| Automation | Runs | Model? | Delivers |
|---|---|---|---|
| **Proactive tick** | Every 2 minutes: `config/proactive/tick.script.js` calls `proactive_tick`, which reads new phone events since its cursor, turns the kinds Adam turned on into P2 candidates through C3, and hands back queued lines | **No.** A script payload | Its `notify` through OpenClaw's announce, to Adam's Telegram chat |
| **Morning brief** | Condition script `brief-due.trigger.js` every 5 minutes from 05:00 to 09:55; the agent turn runs once, when `proactive_due` says so (alarm stopped on a school day, else 07:30, never after 10:00) | Yes, once a day | Nothing itself (`--no-deliver`). It writes the detail as its reply, which stays in its session ("detail in the app"), and calls `proactive_notify`; the tick delivers the code-written line |
| **Evening wrap-up** | At a time Adam picks | Yes, once a day | The same as the brief |

**Phone events that become candidates**, only for types Adam turned on and only when open loops are due today or overdue: `arrive` at `home` (`home_loops`), and `leave` from `home` before noon (`left_home_loops`). Events older than 30 minutes are skipped. The first tick starts the cursor at "now", so old events never replay. `alarm_stopped` is read through `/today` by the brief's condition, not as an event.

### The guard: how it tells proactive runs apart

**Spike, 2026-11-15, read from OpenClaw 2026.10.9's source and docs, not yet seen running:**

- `before_agent_run` gets `ctx.trigger` (`user`, `heartbeat`, `cron`, `event`, `manual` and more), `ctx.runId` and `ctx.jobId` [source: `buildEmbeddedAgentHookContext` in `dist/helpers-*.mjs`; `resolveReplyRunTrigger` in `dist/reply-turn-kind-*.mjs`; `trigger: "cron"` in `dist/server-cron-*.mjs`].
- `before_tool_call` gets `ctx.runId` and `ctx.sessionKey` but **no trigger and no job id** [types: `PluginHookToolContext` in `dist/config-contracts-*.d.ts`; docs: `plugins/hooks/prompt-and-session.md`].
- Isolated cron runs use `agent:<id>:cron:<jobId>` [docs: `automation/cron-jobs/payloads.md`]; webhook turns `hook:…` [source: `dist/external-content-source-*.mjs`]. **A heartbeat runs in `agent:main:main`, Adam's own chat's key** [docs: `gateway/heartbeat.md`], so the key alone can't tell them apart.
- Cron script payloads run headless, call the agent's tools as async globals, and their returned `notify` goes out through the job's announce [docs: `automation/cron-jobs/payloads.md` "Script payloads"; `tools/code-mode/guest-api.md`].

**What the guard does now:** it remembers each run's trigger from `before_agent_run` by run id. A tool call is from a proactive run when:

- its run's trigger is `cron` or `heartbeat`, or
- its session key is a `cron:`, `hook:` or `proactive:` session, or
- it descends from one, or
- it is a `main` run with no requester and no known trigger, so it can't be shown to be Adam's.

In those runs `message` is blocked, to Adam or anyone, also through the search wrapper: "scheduled and background runs tell Adam things only through proactive_notify". Adam's own runs keep today's rules. The decision log gains a `trigger` field.

New classes in `config/permission-matrix.json`:

| Class | Tools | Rule |
|---|---|---|
| `read` | `today_picture`, `loops_list`, `proactive_why`, `digest_list`, `proactive_due` | Allow |
| `proactiveSend` | `proactive_notify`, `proactive_feedback` | Allow, also after outside text: code decides, and it only queues. Frozen blocks it |
| `localWrite` | `loop_done`, `loop_drop` | Allow in a clean chat, a card after outside text |
| `confirmAlways` | `loop_propose`, `proactive_resume` | Always a card with the exact fields |
| `cronOnly` | `proactive_tick` | Only in a `cron:` session; elsewhere the lines would be lost |

**Paths outside any tool call, which the guard can't see:**

- A heartbeat's own reply text and `heartbeat_respond` with `notify: true` are delivered by OpenClaw.
- A cron job with `--announce` delivers the model's final reply.

The closures:

- The brief and wrap-up use `--no-deliver`.
- The tick is code only.
- The heartbeat is decision 5 below.
- `event` runs (a background command's result coming back to the chat where Adam started it) count as Adam's own.

## Steps for Adam

Each numbered step needs its own yes. Commands with `openclaw` run as `jorah` on the PC, in a Terminal attached to no agent.

**Before step 1, check:**

- The P5 log review has passed.
- The phone service (steps A and B) is installed.
- No other session has a live change open.

1. **Claude copies the reviewed commit to root-owned `/opt/jorah`:**
   - `plugins/jorah-proactive`;
   - `plugins/jorah-guard` (the proactive rules);
   - `config/permission-matrix.json`;
   - `config/proactive/`;
   - `config/pc/proactive.patch.json5`;
   - `scripts/pc/install-proactive.sh`.

   It checks each file's SHA-256 against `main`. The guard's new rules take effect at the next Gateway restart, which step 3 does.
2. **Dry run** (Claude or Adam, as root):
   ```bash
   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-proactive.sh --dry-run
   ```
   Expected:
   - three "Dry run successful" lines;
   - main's tool list ending with the twelve new tools;
   - "No proactive type is turned on and no automation is created".
3. **Install** (Adam, as root): the same command without `--dry-run`. Expected:
   - the Gateway restarts;
   - the log says `jorah-proactive: 12 tools; types on: none` and `jorah-guard: matrix loaded; state ok`;
   - health ok;
   - audit 0 critical;
   - the backup `openclaw.json.pre-proactive`.

   Undo: the same command with `--undo`.
4. **First check, in Telegram:**
   - "What's on today?" Expected: a short answer from `today_picture`, with the date, open loops (none yet), the phone (or "unavailable" if the phone service isn't installed), and calendar and school "not connected". No zeros for unknowns.
   - "I promised Jana I'd send the photos by Wednesday." Expected: a card "Jorah wants to note an open loop" with `kind: i_promised`, `who: Jana`, `what: …`, `due: 2026-11-18`. **Allow once** saves it as L1; **Deny** saves nothing. Check with "what are my open loops?".
   - "What would you tell me unasked?" Expected: the seven types with their cards, all off.
   - "/jorah-status". Expected: as before; nothing new is frozen.
5. **Turn one type on** (one yes per type, after reading its card from step 4). Dry run first, then the same command without `--dry-run`:
   ```bash
   openclaw --profile jorah config set plugins.entries.jorah-proactive.config.enabledTypes '["morning_brief"]' --strict-json --dry-run
   ```
   This is the whole list: to add a second type, list both. Expected: the plugin reloads and the log says `types on: morning_brief`. Undo: the same command with `[]`.
6. **Automations** (each one its own yes). First put Adam's Telegram chat id in a shell variable, so it never sits in a file:
   ```bash
   ID=$(openclaw --profile jorah config get channels.telegram.allowFrom | python3 -I -c 'import json,sys; print(json.load(sys.stdin)[0])')
   ```
   a. **Proactive tick**, every 2 minutes, no model:
   ```bash
   openclaw --profile jorah automations add --every 2m --name "Proactive tick" --agent main --session isolated --script /opt/jorah/config/proactive/tick.script.js --script-timeout-seconds 30 --script-tool-budget 2 --tools proactive_tick --announce --channel telegram --to "$ID"
   ```
   b. **Morning brief**, condition every 5 minutes from 05:00, agent turn once a day:
   ```bash
   openclaw --profile jorah automations add --cron "*/5 5-9 * * *" --tz Europe/Bratislava --name "Morning brief" --agent main --session isolated --message "$(cat /opt/jorah/config/proactive/morning-brief.prompt.md)" --trigger-script /opt/jorah/config/proactive/brief-due.trigger.js --tools today_picture,loops_list,digest_list,web_search,proactive_notify,proactive_due --no-deliver --timeout-seconds 300 --fallbacks ""
   ```
   c. **Evening wrap-up**, at the time Adam picks (21:00 is a placeholder):
   ```bash
   openclaw --profile jorah automations add --cron "0 21 * * *" --tz Europe/Bratislava --name "Evening wrap-up" --agent main --session isolated --message "$(cat /opt/jorah/config/proactive/evening-wrap.prompt.md)" --tools today_picture,loops_list,digest_list,proactive_notify --no-deliver --timeout-seconds 300 --fallbacks ""
   ```
   Expected for each: `openclaw --profile jorah automations list` shows it, and `automations runs <id>` shows `ok` runs. While nothing is queued, the tick sends nothing. Turn one off with `automations disable <id>`, or remove it with `automations rm <id>`.

   **If `automations add` rejects a flag** (for example `--script` with `--every`, or `--trigger-script` with `--message`), stop and tell Claude: the flags come from `--help` at 2026.10.9, not from a run.
7. **Test pass** (after the brief and the tick are on):
   - **School-day morning:** stop the alarm. Expected within 5 to 7 minutes: one Telegram line "Morning brief: … Detail in the Jorah app.", counts and times only. The run's session in the Jorah app holds the detail.
   - **Saturday:** expected at 07:30 to 07:37, not before.
   - **"Why did you tell me that?"** Expected: the rule ("a digest Adam turned on"), the record id, quiet hours and the time.
   - **"Stop the morning brief."** Expected: "stopped"; the next morning, nothing. Then "keep telling me the morning brief" brings a card; Allow once restores it.
   - **Phone service stopped** before the brief: the brief still comes at 07:30, and the detail says the phone is unavailable, never zeros.

## Decisions still open

| # | Question | Proposal |
|---|---|---|
| 1 | Quiet hours | 22:30 to 07:30. Should the alarm (or a wake) end them early? Proposed: yes |
| 2 | D9: brief time and channel | On "alarm stopped" on a school day (Monday to Friday; holidays unknown until the school is connected), else 07:30, never after 10:00. A Telegram line with counts and times, detail in the app |
| 3 | Evening wrap-up | A time, or none. 21:00 is a placeholder |
| 4 | Which types first | `morning_brief` first. `01` §11 picks `job_finished` and `job_blocked` at M6 |
| 5 | Heartbeat alerts | Today the hourly heartbeat can still alert through its own reply, outside `proactive_notify`. Moving them under these rules means heartbeat `target: "none"`, which also hides OpenClaw's own heartbeat failure notices. Keep as is, or move? |
| 6 | Brief model | main's default, or `--model` Haiku for the brief and wrap-up |
| 7 | Loop kinds | `waiting_on_me` and `i_promised`, as asked. Add "waiting on others" (things others owe Adam)? |
| 8 | Busy Focus modes | Everything except no Focus and `personal` counts as busy for P2 |

## Honest limits

- Presence isn't measured. Busy comes from the phone's Focus only, and an unreachable phone means "busy unknown", so P2 goes to the digest.
- Nothing is spoken: there is no speaking path before M10.
- Lines in Jorah's own words (`job_finished`, `job_blocked`, `learned`) are checked for length, one line and links. Code can't tell whether one holds a name or a private detail. The loop and brief lines are written by code and can't.
- "Delivered" means handed to OpenClaw's announce. A delivery that then fails shows in the tick's run history, not in the record.
- "Ignored" means Jorah recorded no reaction within 3 hours. If Jorah forgets to record one, a type gets demoted, which errs toward quiet.
- The tick runs about 720 times a day, all without a model.
- The plugin has its own copy of the small schema checker that `plugins/jorah-phone` also has (on its branch). Sharing one is a follow-up, once both are on `main`.
