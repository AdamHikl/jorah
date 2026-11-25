# 13. Autonomy: what Jorah does without asking

**Status: 2026-11-25. Source for steps 1 to 3 of §8 is built; nothing here is live.** Each live change in section 8 waits for Adam's yes. Until Adam approves this file, `05-growth-and-skills.md` §4.5 stands. After that, this file wins where the two disagree. It never weakens a hard gate in `10-roadmap.md` §2a: nothing private connects before the P5/M3 gate.

Adam, 2026-11-25: "I really want it to be able to be autonomous and pro active as much as possible with him staying safe. So when I tell him to work on some project, or do something he does it, and sometimes he might even do it without me having to ask him, same thing with saving memories, creating reminders, cleaning his own environment, managing himself, upgrading himself."

## 1. What the research says

| Finding | Source | For Jorah |
|---|---|---|
| Autonomy is a design choice, separate from capability. The user's role defines five levels: operator, collaborator, consultant, approver and observer. | [Feng, McDonald, Zhang 2025](https://arxiv.org/abs/2506.12469) | Choose a level for each kind of action, not one level for all of Jorah. |
| In real use, experienced people auto-approve more. They stop approving each step and step in when something looks wrong. Agents that pause to ask on hard work are part of good oversight. | [Anthropic 2026](https://anthropic.com/news/measuring-agent-autonomy) | Trust should grow from a track record. Asking one good question beats asking at every step. |
| Act when the benefit beats the cost of interrupting. Match how much is done to how sure you are. Make dismissing or correcting cheap. Remember what was rejected. | [Horvitz 1999](https://erichorvitz.com/uiact.htm) | Prepare freely, but interrupt rarely. Give every action Jorah takes on his own a one-word undo. |
| The main failure of proactive agents is unwanted interruption. Measure how often suggestions are accepted. Interrupt only when confidence is high. | [ProactiveBench](https://arxiv.org/abs/2410.12361), [PRISM](https://arxiv.org/abs/2602.01532) | Use budgets, digests and an acceptance metric for each kind. Demote kinds Adam ignores. Much of this is already in `jorah-proactive`. |
| Scale approval to severity and reversibility. Keep a readable activity log. Keep the agent interruptible. Limit the actions it can take. | [OpenAI, Practices for Governing Agentic AI Systems](https://cdn.openai.com/papers/practices-for-governing-agentic-ai-systems.pdf) | Use the decision test in §3, an action ledger and a pause. |
| Grant least privilege. Enforce policy outside the agent. Outside text never instructs, and memory never grants permission. High-impact actions need a human. | [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | The guard stays root-owned. Jorah must not be able to edit his own red lines (§6). |
| Inside a boundary, allow by default. A separate check blocks anything irreversible, destructive or outward. | [Claude Code auto mode](https://anthropic.com/engineering/claude-code-auto-mode) | Use the same shape: free inside the workspace, cards at the edge. |
| People stop reading approval prompts they see often. | Over-reliance research, summarised in the OpenAI paper above | Use fewer cards and batch them. A card must be worth reading. |
| Write each standing duty as a program with an Authority, a Trigger, an Approval gate, an Escalation and a "What NOT to do". Run it as Execute, Verify, Report. Start narrow, then widen after reviewing the logs. | [OpenClaw standing orders](https://docs.openclaw.ai/automation/standing-orders) | See §5. |
| Executive assistants work from a written decision map: decide and inform, recommend and wait, or escalate. The map widens as trust grows. | Common EA practice | Use the four tiers in §3. |

## 2. Where Jorah is today

**What the guard enforces in a clean chat** (no outside text read):

- Free:
  - file writes in the workspace, **rules files included**;
  - memory writes and `skill_workshop`;
  - one-off reminders that don't fetch the web;
  - asking `deep`;
  - up to 3 Claude Code jobs an hour.
- Card:
  - a recurring schedule, or any schedule that fetches the web (critical);
  - `loop_propose`;
  - project levels and limits;
  - toolbox installs;
  - GitHub pushes and PRs, and messages (critical).
- Blocked: `sessions_send`, `gateway`, `nodes`, `computer`, `openclaw`.
- After outside text, memory, skill, rules and schedule writes all get cards, unless Adam's own words cover them.

**What `workspace/AGENTS.md` says:**

- "Never push, deploy, publish or create a schedule without Adam's yes."
- "Ask before any recurring job."
- Coding is "only when Adam asks".
- Repeated work leads to a proposal, which is created only after a yes.
- "Nothing learns in the background on this runtime." The runbook (`docs/runbooks/jorah-on-pc.md`) records the workshop's own review running in Adam's chat since 2026-11-08. Whether it still runs now that main is on the Max lane is **unknown**, so the line stays until a test settles it.
- Memory upkeep should "use a scheduled automation". No program says when. Whether one exists live is **unknown** (check with `automations list`).
- "Record camera names, SSH hosts …" under "Local notes" tells Jorah to write into `AGENTS.md` itself. The live copy may hold such notes that the repo doesn't, so diff it before any deploy.

**What is not running:**

- The proactive layer: brief, wrap, P2 alerts and open loops. The source is done and 45 tests pass, but it is not installed. It waits for the P5 gate, whose open tier is Adam's Telegram pass (`docs/evidence/p5/2026-11-20-guard-week-review.md`, item 5), and for the phone service.
- Project mode, which is at level 0: a card for every push.
- Self-upgrade, which happens only through build sessions and the canary.

**Gaps against the research:**

1. **No written decision map.** The rules are spread over `AGENTS.md`, `SOUL.md`, `05` §4.5 and the guard, so Jorah can't tell "do it and tell Adam" from "ask first".
2. **Asks where it's safe.** An open loop that Adam typed himself still gets a card. Standing upkeep has no program, so each run would need its own yes.
3. **Free where it shouldn't be.** In a clean chat, Jorah can edit `AGENTS.md`, `SOUL.md` and `DEEP.md`, his own red lines, without a card. `DEEP.md` isn't even in the matrix's rules files, so it is free after outside text too. The drift check only reports it the next night. `05` §4.5 says "Never. Adam edits these in git."
4. **No ledger Adam sees.** The guard logs every verdict, but nothing shows Adam "what did you do without asking today?" except Jorah's own word.
5. **No measured trust.** Nothing records acceptance or undo rates, so nothing can be widened on evidence.
6. **No finish standard.** Execute, Verify, Report isn't written down. SOUL rule 2 covers only part of it.
7. **Nobody owns hygiene or self-checks.** And main has no shell, while `background` can't see the workspace or `~/work`, so Jorah can't prune branches or clear files alone today.
8. **No soft pause.** `/jorah-freeze` stops everything and needs a terminal to clear. Nothing sits between "free" and "frozen".
9. **Unclear asks and declined ideas.** Nothing says when to ask one question and when to pick the likeliest reading, and nothing stops a declined proposal from coming back.

## 3. The decision test

Two questions set the tier for any action:

1. **Can Jorah undo it fully, himself, in a minute?**
2. **Who sees it?** One of three answers:
   - only Jorah's own space: the workspace, `~/work` branches, memory, skills and his jobs' scratch;
   - Adam;
   - anyone or anything off the PC: people, GitHub, web forms, money, accounts.

| | Jorah's own space | Reaches Adam | Leaves the PC |
|---|---|---|---|
| **Undoable** | A. Do it | B. Do it, then tell | C. Ask first |
| **Hard to undo** | B, only with `trash` or archive, never a delete | C | C or D |

- **A. Do it.** No message.
- **B. Do it, then tell.** One line at the end of the turn, or an entry in the evening wrap, with the word that undoes it ("undo", "forget that", "cancel it").
- **C. Ask first.** One card or one question. Several asks go in one message with numbered yeses. A standing grant from Adam turns only the named C actions into B. A grant is either a program in §5 or a project level in `11` §6.
- **D. Never.** Adam does it, or it goes through a build session.

Two overrides always apply:

- After outside text, the guard's cards apply whatever the tier.
- Adam's own words authorise the action he named, not the tier around it.

## 4. Decision rights by area

### 4.1 Tasks Adam gives

- **A:** every undoable step inside the ask. That includes:
  - research and asking `deep`;
  - drafts and workspace files;
  - Claude Code on a branch in `~/work` (at most 3 jobs an hour);
  - running tests.

  Don't stop between steps to check in.
- **An unclear ask:** ask one question up front only when a wrong guess would waste real work or reach someone else. Otherwise, take the likeliest reading, name it in one line, and go.
- **B, finish with Execute, Verify, Report:** what was done, how it was checked, and what is still open. "Done" without a check is not done.
  - If a step fails, retry once with a fix.
  - After 3 attempts, stop and report.
- **C:** anything that leaves the PC: a push, a PR, a message, a post, an order or an account. A project level widens pushes only.
- **D:** payments, sign-ins, keys and `sudo`. Adam does these.

### 4.2 Unasked work

The rule: **preparing is free; interrupting is not.**

- **A:** notice and prepare. For example:
  - draft a reply;
  - research tomorrow's appointment;
  - write up a bug Jorah found in a project Adam works on: what fails, the likely fix, and the files.
- **B:** offer the result in the brief or the wrap, as "Ready for you" items that take one tap to use. P2 alerts cover only the five P2 types, within the daily budget (`docs/runbooks/proactive.md`).
- **C:** a Claude Code job that is Jorah's own idea, the fix above included. He offers it in the wrap ("Want me to …? yes 1"). The exception is a task the project runner already schedules at level 1 or above.
- **Declined is remembered.** A proposal Adam declines isn't offered again unless something changed, and then Jorah says what changed.
- **Metric:** the acceptance rate for each kind, once `jorah-proactive` is installed and counting.
  - Ignored 3 times: demoted. This already exists in that plugin.
  - Under 30% accepted over two weeks: off until Adam turns it back on.

### 4.3 Memory

- **A:** in Adam's own chat:
  - save what he says about himself, his plans, people, projects and decisions, with provenance ("Adam said, date");
  - fix a fact he corrects;
  - keep daily notes;
  - merge and tidy memory files.
- **B:** once a day, the wrap lists "🧠 Saved today: …". Saying "forget X" removes it. A change to `USER.md` gets a line at the time it happens.
- **C:** anything from outside text (the guard card stays). Deleting memory is also C: archive instead, and delete only when Adam asks.
- **D:** memory never grants a permission or widens a tier. No secrets or keys, ever.

### 4.4 Reminders and open loops

- **A/B:** a one-off reminder whenever Adam says "remind me", or states a dated promise ("I'll send Jana the photos by Wednesday"). Use `reminder_job`, then `automations`, as now. Then one line: "⏰ Tue 18:00. 'cancel it' to undo." This works today: the guard already lets a one-off reminder through in a clean chat.
- **Change, an open loop from Adam's own words in a clean chat goes from C to B:** no card, one line instead: "🔁 Noted: photos to Jana by Wed. Reminder Tue 18:00. 'drop it' to cancel." An open loop from outside text, such as an email or a page, keeps its card. "Adam's own words" uses the guard's existing test: every sentence of who and what must match something Adam typed in this chat. `loop_propose` lives in `jorah-proactive`, so this starts with that install.
- **C:**
  - a recurring job outside an approved program;
  - any job that fetches the web.

### 4.5 Housekeeping

Main has no shell, and `background` can't see the workspace or `~/work`. So Jorah tidies what his own tools reach and proposes the rest.

- **A:** with his own tools:
  - merge duplicate memory notes and fix stale ones (§4.3);
  - close finished project tasks;
  - tidy `files/pictures/INDEX.md`;
  - check that his own jobs ran (§4.6).

  Daily notes stay where they are, because memory search reads them.
- **B:** one hygiene line in the Sunday report: what he tidied, then numbered cleanup proposals, for example merged local `jorah/*` branches, or temp files and downloads older than 14 days.
- **C:**
  - each cleanup proposal: Adam's "yes 2" runs it in his chat, as a Claude Code job for branches in `~/work`, or with `trash` for files;
  - deleting a remote branch, which leaves the PC;
  - anything outside `~/workspace` and `~/work`;
  - emptying the trash.
- **D:** `/opt/jorah`, OpenClaw's state and config, the guard and backup folders, and systemd units.

### 4.6 Self-management

- **A:**
  - check that his own jobs ran;
  - retry a failed job once;
  - update skills from Adam's corrections, which the workshop already does;
  - archive a skill Adam undid.
- **B:** report failures in the next brief. Send a P1 alert only when something Adam relies on today failed, such as a reminder that didn't fire.
- **C:**
  - turn a proactive type on or up;
  - change quiet hours;
  - add an automation outside a program;
  - change a model.
- **D:** the guard, the permission matrix, sandbox and tool policy, and the red lines in `AGENTS.md`, `SOUL.md` and `DEEP.md`. Jorah may propose a change to these, in the wrap or as a draft PR with the usual push card. He never makes the change himself.

### 4.7 Self-upgrade

- **A:** read OpenClaw's release notes, his own error log and the drift report, and keep `notes/upgrades.md` in the workspace. Release notes are outside text, so read them last in any run (see §5).
- **B:** when a release is at least 7 days old (the dependency rule), add an upgrade brief to the Sunday report:
  - what's new;
  - what it would fix for Adam;
  - the risks;
  - what the canary would test.

  He does the same for a skill or plugin that would save Adam time ("Existing solutions first").
- **C:** with Adam's yes, a Claude Code build session on the Mac runs the canary and the upgrade (the existing path in `docs/runbooks/jorah-on-pc.md`). Jorah may open the issue or draft PR that describes it, with a card.
- **D:** upgrading himself live, installing plugins outside the toolbox card, and editing config.

## 5. Standing programs

Each program is a section of `AGENTS.md` in OpenClaw's standing-order shape. Each has one automation, created once with Adam's yes. After that it runs without asking. A new time or prompt needs a new yes.

| Program | Trigger | Does without asking | Reports | Can start |
|---|---|---|---|---|
| **Weekly upkeep** | Sunday, time Adam picks | Memory upkeep (§4.3), housekeeping (§4.5), a check that his jobs ran (§4.6), then the upgrade watch (§4.7) **last**. Replaces `AGENTS.md`'s "every few days, use a scheduled automation" | One Sunday message, with numbered cleanup and upgrade proposals | After the guard deploy and the spike below |
| **Morning brief** | Daily, time Adam picks | Read memory, loops, projects and reminders. Prepare "Ready for you" items | One message | With the proactive install, after the P5 gate |
| **Evening wrap** | Daily, time Adam picks | The day's ledger of A and B actions, memory saved, open loops, and proposals with numbered yeses. When both are on, the 18:00 project digest folds into it, so Adam gets one evening message | One message | Same |
| **Open loops** | Adam's words; no schedule | §4.4 | A B line | With the proactive install; the guard side is built |
| **Project autopilot** | The project runner | The levels in `11` §6 | The runner's reports | When Adam picks a project and a level |

Every program shares these "What NOT to do" rules:

- Message no one but Adam.
- No pushes, orders or sign-ups.
- **No writes after reading web text in the same run.** A sandboxed run that has read a page gets cards that nobody answers on a Sunday morning.
- Stay quiet in quiet hours unless something is urgent.
- If a step fails, retry once, then report it. Never mark it done.
- Don't re-propose what Adam declined unless something changed.

**Unknowns for the spike, on `jorah-dev`:**

- Can a sandboxed cron run write memory files in the workspace?
- Does a program's report reach Telegram through the automation's own delivery, as the heartbeat's does, while `message` stays blocked in proactive runs?

## 6. Safety that pays for the wider autonomy

1. **The guard and the matrix stay root-owned in `/opt/jorah`.** This is already true.
2. **Tighten self-edits.** Every write to `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `BOOTSTRAP.md`, `HEARTBEAT.md` or `DEEP.md` (the matrix's new `selfFiles`) gets a card, even in a clean chat, from main and from deep. `TOOLS.md` and skills stay free in a clean chat and keep their card after outside text. "Local notes", which `AGENTS.md` tells Jorah to keep in `AGENTS.md`, moves to `TOOLS.md`, OpenClaw's place for them.
3. **Taint stays as it is.** After outside text, the cards apply as today.
4. **Memory never grants permission.** A standing grant comes only from Adam in chat. It is recorded in this repo, as a program or a project level, never in memory.
5. **Ledger.** The guard's hash-chained decision log (`decisions.jsonl`) already records every verdict, allows included, with no argument values. New: `/jorah-today`, a guard command only Adam can run, counts today's allowed writes by class and tool, and today's cards and blocks. It is the guard's count, not Jorah's word. A command needs no new tool on the allowlist; a version the wrap can read is a later change.
6. **Pause.** `/jorah-freeze` already exists as the hard stop: it blocks everything except reading, and only a terminal can clear it. New: `/jorah-careful`, a softer step that the guard handles itself, not the model. It turns every write the guard would allow (files, memory, skills, schedules, local records, Claude Code and background jobs) into a card, for 24 hours or until `/jorah-careful off`. Reading and asking `deep` stay free. Only Adam can set or lift it. Known gap: scheduled project runs (`jorah-projects`) check only `/jorah-freeze`, so careful mode does not pause them; use `/jorah-freeze` for that until the runner also reads the careful file. Both are separate from the HUD's kill switch (ADR 0006), which stops WSL.
7. **Metrics are measured, not self-reported.** Today the guard ledger counts what Jorah did alone. Once `jorah-proactive` is installed it also counts:
   - B actions undone;
   - C asks accepted;
   - P2 alerts acted on.

   Until then the ladder's undo rate is **unknown**, and a widening rests on the ledger and Adam's review.

## 7. Trust ladder

- **Start:** the tiers in §3 and §4.
- **Widen** one named action by one step (C to B, or B to A) when all of these hold:
  - two weeks have passed;
  - it ran at least 10 times;
  - no undo was for harm;
  - under 10% were undone;
  - Adam gives a written yes in the wrap.

  Each widening is recorded in this file.
- **Narrow at once:** one harmful action (data leaked, wrong recipient, data lost) puts that area back to C until Adam reviews it.
- **First candidates after two weeks:**
  - project level 1 to 2 (`11` §6);
  - pruning merged `jorah/*` branches on GitHub;
  - more P2 types.
- **Never on the ladder:** anything in D.

## 8. Build order and Adam's yeses

| # | Step | Where | Adam's yes |
|---|---|---|---|
| 1 | This file, committed and pushed to `main` | Repo | Done 2026-11-25 (build session rule) |
| 2 | Rules text: the tiers (§3, §4) in `SOUL.md`, because `AGENTS.md` is at its size budget; in `AGENTS.md` the programs (§5), Execute/Verify/Report, one question up front, declined proposals remembered, dated promises as reminders, the schedule red line reworded for one-off reminders, "Local notes" moved to `TOOLS.md`. Diff the live copy first, then deploy with `deploy_reviewed.py` and `record-live` | Live 2026-11-25 21:18 | Given 2026-11-25 (`docs/evidence/autonomy-2026-11-25/deploy.md`) |
| 3 | Guard: (1) `selfFiles` always get a card, `DEEP.md` included, (2) an open loop from Adam's own words gets no card, (3) `/jorah-careful`, (4) `/jorah-today`. Source and unit tests | Live 2026-11-25 21:18 | Given 2026-11-25 (same evidence) |
| 4 | The §5 spike | `jorah-dev` | None (scratch profile) |
| 5 | The weekly upkeep automation | Live | The schedule and its time |
| 6 | Brief and wrap, with the proactive install after Adam's Telegram pass | Live | Per `docs/runbooks/proactive.md` |
| 7 | Project autopilot: one project at level 1 | Live | Which project |
| 8 | One test pass at the end, with exact steps for Adam | Live | Adam's acceptance |

Steps 5 to 7 come after the deploys in steps 2 and 3.
