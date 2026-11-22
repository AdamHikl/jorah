# jorah-guard: review of the first week on live (P5.5)

Date: 2026-11-20. Scheduled, read-only run by Claude Code from the Mac. Nothing was changed on the PC, in the config or in `main`.

**Tier reached: a log review.** It is not signed-in device acceptance. Adam's own Telegram use of the guard (a card, `/jorah-status`, `/jorah-freeze`) is still unseen.

## How it was checked

- `scripts/pc/guard-report.py --days 8`, run as `jorah` on the PC: exit 0.
- Two extra read-only passes over the same log, printing only line numbers, times, tool names, verdicts, sender classes and session-key shapes. They were needed to explain the broken chain and the sender classes. No arguments, addresses, message text or sender ids were printed.
- Health: the command in the task failed as written (`'grep' is not recognized`: Windows took the `|` before WSL did). The same two commands were sent on standard input to `bash -ls` instead.

## Numbers

- 112 decisions, 2026-11-13 17:36 to 2026-11-20 07:47 UTC. Allow 108, block 4.
- Per day: 4, 22, 2, 2, 22, 24, 33, 3.
- Cards shown: 0. Links removed from Telegram replies: 0. Freezes: 0. Resets seen: 0. Guard errors: 0. Tools blocked as not in the permission list: 0.
- Frozen now: no. Chats marked as having read outside text, by first source: `toolbox_list` 2, `web_fetch` 1.
- Gateway: `active`. `jorah-guard`: listed, enabled, loaded from `/opt/jorah`.

## a. Hash chain: broken, by a second writer, not by an edit

The report says "BROKEN at line 85". What the log shows:

- **No line was edited:** every one of the 112 lines still matches its own hash.
- **No line that another line points at is missing.** Only line 1 starts from `genesis`.
- **The chain forks at line 83.** Two lines name line 83 as their predecessor. From there two writers each kept their own chain and their lines interleave, which gives 4 mismatches (lines 85, 91, 93, 108).
  - Writer 1 (the Gateway): 91 lines, the whole week.
  - Writer 2: 21 lines, 2026-11-19 15:45 to 16:33 UTC (16:45 to 17:33 CET), in `agent:main:main` (8) and `agent:main:voice-probe` (13). All have no requester and trigger `user`.
- **Cause, as far as the log shows:** a second process loaded the guard and wrote to the same file. `AuditLog` reads the last hash once at start and then trusts its own copy, so two processes always fork the chain.
- **Not known:** what the second process was. A build session's command-line turns on 2026-11-19 would fit (the URL-laundering and toolbox work was that day), but the log can't say. A deleted last line of either branch would also not show.

Writer 2's 8 rows in `agent:main:main`, Adam's own chat key, at 15:45 UTC: `read`, `toolbox_list`, `web_fetch` blocked, `web_search`, `web_fetch` allowed, `web_fetch` blocked, `exec` blocked, `web_search`. That looks like a test of the URL rule. If no session ran it, it needs a closer look.

## b. Who asked: no real Telegram turn is in the log

| Class | Channel | Rows | What they are |
|---|---|---|---|
| none | - | 83 | 58 heartbeat runs (`deep` 41, `main` 17), 21 from the second writer, 4 from named check sessions (`pm-check`, `errands-check`) |
| voice | webchat | 21 | all in `agent:main:voice-probe` and its memory helpers |
| adam-typed | - | 4 | the install's own test session, 2026-11-13 |
| other | telegram | 4 | heartbeat runs of `background` (3) and `deep` (1) |

- **The report's warning "Telegram counted as Adam typing: 0 of 4" is a false alarm.** Those 4 rows are heartbeat runs whose reply channel is Telegram. None is a message from Adam.
- **The real question is still open.** No tool call from a turn Adam typed in Telegram was logged all week. So whether Telegram turns carry a sender id and count as `adam-typed` is **unknown**, not failed. `typedByOwner` needs no rethink on this evidence.
- Whether Adam used Telegram at all this week, the guard's log can't say: it records tool calls, not messages.
- Named check sessions run from the command line logged as `none`, not `adam-typed` as the install test did. That is the safe direction (not treated as Adam's clean chat), but the two paths differ and nobody has written down why.

## c. Tools not in the permission list

None blocked. 19 tool names were seen and all are in the matrix. `jorah-ios`'s tools didn't appear. Nothing to add.

## d. Cards

None shown, so nothing to judge as noise or as right. No turn reached a rule that asks: the week was heartbeat reads, probe turns and checks.

One thing to watch: `toolbox_list` marks a chat as having read outside text, and it was the first source for 2 of the 3 marked chats. The second writer's turns call `toolbox_list`, `project_list` and `supply_list` together at the start of a turn. If Jorah does that routinely, a chat is marked from its first turn, and "nothing changes until a chat reads outside text" stops being true in daily use. Seen 5 times in all, so this is a pattern to confirm, not a measured rate.

## e. Blocks, errors, freezes, removed links

4 blocks, all expected:

- 1 `tool_call`: "private or local address". The install's own test.
- 2 `web_fetch`: address not in the message or an earlier result, after outside text. Second writer, `agent:main:main`.
- 1 `exec`: "main has no shell; background does shell work". Same turn.

No guard errors, freezes or removed links. Heartbeat runs of `deep` used `exec` 9 times, allowed: `deep` has a sandboxed shell, as the matrix says.

## f. Still loaded, Gateway healthy

Yes: `openclaw-gateway` is `active` and `jorah-guard` is listed as enabled. This is a service and plugin-list check only, not a full health or audit run.

## What worked

- The guard stayed loaded for the week with no errors and no unknown tools.
- It refused what it should: a local address, two addresses nobody gave, and a shell call from `main`.
- Heartbeat runs and voice-probe turns were never treated as Adam's clean chat.

## What got in the way

- The hash chain can't prove the log is whole, because a second process forked it.
- The week has no Telegram turn from Adam and no card, so the two things P5.5 most wanted to see are still unseen.
- The report misreads heartbeat rows as Telegram turns, and lumps heartbeat, checks and the second writer into "none".
- The health command in the review task doesn't run as written.

## Proposed fixes (each needs Adam's yes; none applied)

1. **Find the second writer.** Ask the sessions that worked on 2026-11-19 which one ran turns in `agent:main:main` and `agent:main:voice-probe` between 16:45 and 17:33 CET, and record the answer here. Changes nothing on the PC.
2. **Make the log safe for two writers.** In `plugins/jorah-guard/lib/audit.js`, take a file lock and re-read the last line's hash before each append, so a second process extends the chain instead of forking it. Source and tests first; the deploy to `/opt/jorah` and the Gateway restart are a separate yes.
3. **Teach the report to tell a fork from an edit.** `scripts/pc/guard-report.py` would say "forked by a second writer at line N, no line edited" or "line N edited or missing", and keep the existing log as it is (not rewritten).
4. **Fix the report's "who asked".** Count heartbeat and cron runs as their own class, and count a row as Telegram only when the turn was started by a user. The "0 of 4" alarm goes away and a real missing sender id would stand out.
5. **Adam's acceptance pass in Telegram** (the open tier). In Jorah's Telegram chat:
   - Send `/jorah-status`. Expected: "Frozen: no", "This chat hasn't read outside text", "Permission list: loaded".
   - Ask Jorah to search the web for anything, then send `/jorah-status`. Expected: "This chat has read outside text: web_search results".
   - Ask Jorah, in his own wording, to save a note about what he found. Expected: a card with the exact text.
   - Then Claude re-runs the report. Expected: Telegram rows classed `adam-typed`. If they say `other`, `typedByOwner` needs the rethink.
6. **Decide whether `toolbox_list` should mark a chat.** First measure how often Jorah calls it at the start of a turn. If it is routine, either mark only when the list holds run-written proposals, or stop Jorah listing it unasked (`workspace/AGENTS.md`). Either is a change to `config/permission-matrix.json` or to Jorah's rules.
7. **Fix the health command in the review task and the runbook,** so the pipe reaches WSL (send the commands on standard input to `bash -ls`). A change to the stored scheduled task and to `docs/runbooks/jorah-on-pc.md`.
8. **Write down why command-line check sessions log as `none`** while the install test logged `adam-typed`, in the runbook's P5.5 section. Documentation only, after a look at how each was started.

## Tiers

- Source, tests: not touched in this run.
- Install, launch: service active and plugin enabled, checked 2026-11-20.
- Log review: done, this file.
- Signed-in device acceptance (Adam, Telegram): **open**, fix 5.

## Status, 2026-11-22

Adam said yes to building the source fixes. All of them are **source and unit tests only**. Nothing is deployed to `/opt/jorah`, the Gateway hasn't been restarted, and the tests haven't run yet: a coordinating session runs them once before the push.

| Fix | State | Where |
|---|---|---|
| 1. Find the second writer | Open: no session has answered yet | - |
| 2. Log safe for two writers | Built: `AuditLog` takes a lock and re-reads the last hash before each append | `f6c7ad9` on `claude/issues-13-24` (#18) |
| 3. Report tells a fork from an edit | Built | `f6c7ad9`, `scripts/pc/guard-report.py` |
| 4. Report's "who asked" | Built: heartbeat and cron rows have their own class | `f6c7ad9`, `scripts/pc/guard-report.py` |
| 5. Adam's Telegram pass | Open (Adam), after a deploy | Runbook P5.5 says how to read `none` |
| 6. `toolbox_list` and the mark | Built: the default view doesn't mark the chat, view `full` does | `26e8ae5` on `claude/guard-review-fixes-6-8-b027f8` |
| 7. Health command | Fixed in the runbook | `2c2a12d`, `docs/runbooks/jorah-on-pc.md` P5.5 |
| 8. Why CLI checks log as `none` | Written down in the runbook | `2c2a12d`, same section |

**Fix 6: what was chosen and why.** The chat is marked only when the result can hold text a run, a tool or a page wrote, as the fix asked. But it is decided from the call, not from the result:
- **Why not decide from the result.** In OpenClaw, `after_tool_call` only observes: its handlers run alongside each other, a failed or timed-out one is skipped, and `result` is optional (`plugins/hooks/tool-policy.md`). A mark set there could come after the model had read the text, or not come at all. That would break the guard's rule that a chat is marked before outside text arrives (p5-plan 4.1).
- **What was built.** `toolbox_list` moved from `taintRead` to a new class, `viewRead`. A call with no arguments, or exactly `{view: "installed"}`, is a plain read. The plugin then returns only installed tools' names, versions, kinds and command names, whether the smoke test passed and whether notes are written, plus counts. Each value is checked against the toolbox's strict shapes and dropped if it doesn't match. Any other argument (`view: "full"`: proposals, smoke output, errors, root commands) marks the chat before the call, as before.
- **As a second line:** if a clean-view result comes back without `view: "installed"` (an older plugin, an error, no result), the guard marks the chat afterwards and logs `late-mark`. That can only add a mark, never remove one.
- **Jorah's rules** (`workspace/AGENTS.md`) now say to use `view: "full"` only when a count shows something is waiting, or for a root command.
- **The fallback** (keep the mark and stop Jorah listing unasked) wasn't needed.

**Also built, from the same pass:** links in Telegram replies that pass the reply rule now go out without `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_eid` and `_ga`. The parameters are only cut out. The link is checked as it was found, so cutting can't make an unseen link pass. This is `b651667`, logged as `tidy`.

**Still open:**
- the tests (one run before the push);
- a deploy of `plugins/jorah-guard`, `plugins/jorah-projects`, `config/permission-matrix.json` and the rules file, together and on Adam's yes;
- fix 1;
- fix 5, Adam's signed-in pass in Telegram.
