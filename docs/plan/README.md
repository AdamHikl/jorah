# Jorah master plan

**Jorah** is Adam's personal real-time assistant: it hears "Jorah" or "Hey Jorah", talks back like Jarvis, sees through a camera, reads mail and calendar with permission, does long jobs on its own and remembers how, and eventually moves a robot arm and a tracked base. It runs on OpenClaw, on this Mac first and always-on on the PC later. It is also a learning project and a possible business.

**Status, 2026-11-03: planning, with the order changed to PC first** (`10-roadmap.md` section 2a). Only M0-A is done: the first commit and gitleaks. OpenClaw 2026.10.9 runs in a terminal with Telegram working. Nothing in this plan has been built, installed or tried on a device. Every claim here is a source, docs or read-only check unless it says otherwise, and every hour, date and euro total is my judgment.

## The plan on one page

**Keep OpenClaw** as brain, memory and control plane, use its official Mac and iPhone apps, and add only thin pieces where it has gaps [track: `02-architecture.md`, `07-apps-and-devices.md`].

**The order, PC first, so Jorah works without the MacBook:**

| Stage | Milestones | What Adam gets |
|---|---|---|
| Lock the door | P0 (M0) | No shell as Adam, API exit tested |
| Move out | P1 (M7), P2 (M9) | **Telegram Jorah with the Mac closed,** surviving reboots, rescue bot on the Pi |
| Talk | P3 (M20), P4 (M10) | **Local voice through iPhone and AirPods,** then "Hey Jorah" in the room on the Pi. No private data yet |
| Connect safely | P5 (M3), M4, M6 | Bridge and hard gate, web answers, read-only mail and calendar, a morning brief, then writes with a tap |
| Grow | M11, M12, M14 | Gets its own tools, edits a YouTube video, designs a part, remembers and improves |
| Body | M5, M8, M13, M15 to M17 | Sim, safety bench, arm by hand, then pick by voice with a spoken stop. The stock gripper is not fingers |
| Beyond | M18 to M25 | Watch mode, iOS builds and Fusion, learned skills, messages, tracked base. Mac-only parts work only while the Mac is awake |
| Extras, each with a trigger | M26+ | **Fingers (M26),** robot senses, Wear OS, glasses, own app, drone logs, always-on sight, logged-in browsing. **Not in the hours or money below** |

**Size, estimated before PC first, and hours aren't a constraint for Adam:** about 715 hours through M25. **Money:** about €2,050 to €5,820 of new money, plus unknown PC parts, a lawyer consultation and any API lane for `main`, on top of Max. About €890 one-off in the frugal case to an arm that works by voice. **You can stop after any milestone** and keep something that works.

**Three rules run through everything:** a failed security gate stops what is behind it. Every install, config change, schedule, service, account and purchase is previewed and needs Adam's yes. Evidence tiers stay separate: source, install, launch, signed-in device acceptance.

## Documents

| File | What it holds | Read it when |
|---|---|---|
| `README.md` | This page | First |
| **`10-roadmap.md`** | **The master plan: every milestone, session, step, gate, acceptance test and purchase** | Every session |
| `01-vision-and-ux.md` | What it should feel like: persona, states, stop words, approvals, dialogues, wireframes | UX work, M1, M2 |
| `02-architecture.md` | Components, data flows, topology, migration, routing, budgets | M1, M7, M9 |
| `03-security-and-privacy.md` | Threat model, permission matrix, exec lockdown, tests SEC-T1 to T40, gates, legal, incident runbook | Before any gate |
| `04-voice-and-vision.md` | Voice stages, `jorah-talk`, spikes, bench, wake word, camera modes | M1, M2, M6, M10, M18, M20 |
| `05-growth-and-skills.md` | The Lab, capability loop, trust ladder, memory, evals, video and CAD | M3, M4, M11, M12, M14 |
| `06-connectors.md` | Every data connector in order, with scopes and tests | M3, M4, M6, M22 |
| `07-apps-and-devices.md` | Mac and iPhone setup, app tests, room ear, when to build our own | M1, M2, M10 |
| `08-robotics.md` | Parts lists, wiring, firmware, safety, arm and base stages, drones last | M5, M8, M13 to M17, M21, M23 to M25 |
| `09-engineering-and-ops.md` | Repo, secrets, upgrades, services, tests, backups, session rules, budget | M0, every session |
| `research/` | 13 research tracks and 5 gap studies with sources | When a claim needs checking |

If two documents disagree on order, dates, hours or purchases, `10-roadmap.md` wins. Its section 13 lists stale rows elsewhere, and session M0-F fixes them.

## Decisions only Adam can make

One answer per question, deduplicated across all documents, ordered by what blocks most. **My recommendation is a recommendation.** Nothing here is legal advice. Write answers to `~/.jorah-private/answers.md`, outside the repo, so age, household and school answers never reach git, and for later rows, in the issue that needs them.

**Decisions 1 to 19 are answered, privately.** The ones that change the plan's path are recorded in `10-roadmap.md` section 2a. Where an answer differs from the recommendations below, section 2a wins. Decisions 20 onward are still open, and 21 and 23 are reshaped by section 2a.

**These numbers are canonical.** Other files keep their own labels: `04` and roadmap D1 is 21 here, `07` D18 and question 16 are also 21, `06` D1 is 30 here, `07` D1 is the app choice covered by 14, `08` Q3 is in 38. When recording an answer, use the number here.

### Now: blocks M0

| # | Question | Blocks | My recommendation |
|---|---|---|---|
| 1 | **Are you 18 or older? Answer first, before any more use of the current setup.** Claude's consumer terms and Gemini's API terms require 18+. OpenAI's minimum is unread. Max is already paid and already runs Jorah | All paid keys, orders, drone exams, and Jorah's current Max use | If no, pause Jorah's existing Max use as well as new keys, and involve a parent or guardian. I offer no workaround |
| 2 | Assistant first or arm first? | Everything after M8 | Assistant first |
| 3 | Accept stage 0: no shell on `main`, no cron or gateway tools, **and no web on `main` until M3**? | M0. If no, M1 does not start (`10` M0 table) | Yes. It closes the largest known gap |
| 4 | **The Max risk, unresolved.** Read by the research track, for you to read yourself [track: `research/brain.md`, terms facts 1 to 5]: consumer terms bar automated access without an API key or explicit permission. The log-in article says routing third-party traffic against subscription limits is prohibited. In April 2026 Anthropic announced that OpenClaw and other third-party harnesses could no longer use subscription limits [secondary]. The legal page does allow a person signing in to the unmodified binary with their own plan, says limits assume "ordinary, individual usage", and says Anthropic may enforce without notice. `~/.claude-jorah` is the same account as Mizyun and Cognio. **Really on Max today:** typed turns, heartbeat, utility calls, delegated coding, Dreaming probably | The brain | **Ask Anthropic in writing before M3.** M0: heartbeat paused, Dreaming paused (`10` 0.13a). M1: heartbeat on the API. M2b: voice-started `ask_main` and `start_job` on the API. **M3: Jorah's Gateway on the API unless Anthropic confirms,** with Max kept for your own Claude Code sessions. Utility calls stay with `main` until then, an accepted exception. **Cost is not modelled:** step 0.18 measures it, at about $0.12 a typed Opus turn at the 67K prefix, with the $100 credits first. A separate Anthropic account for Jorah only if the terms allow it |
| 5 | Link a Console org to Max? It cannot be changed without contacting support | API lane, M0-D. If no: SEC-T21 not run, no tested exit, no `voice` on the API (`10` M0 table) | Yes, no payment method, $100 limit |
| 6 | Check the training setting and usage credits on that account | Before Jorah reads anything of others | Training off, credits off or capped |
| 7 | Pause the hourly heartbeat? It draws on Max around the clock, and when the shared 5-hour limit ran out on day 2 (most likely from the multi-agent plan research), each heartbeat retried through the whole model chain | M0 | Yes, right after the MANGO-42 check |
| 8 | Create the daily learning review job? | M0 | **Not now.** `/learn` by hand, and Jorah saves corrections in the same turn. Revisit at M14 |
| 9 | Run the Gateway as a service now, under your own user? | M0 | **No.** First service at M1, under user `jorah`. Foreground until then |
| 10 | Private GitHub repo plus a bundle, or bundle only? The notes describe current weaknesses | First push. If bundle only: no CI, no PRs, local branches and a merge you review | Private repo plus bundle |

### Next: blocks M1 and sets the plan's size

| # | Question | Blocks | My recommendation |
|---|---|---|---|
| 11 | Who lives at or visits this home? Children or pets? Do cameras see a window, street or shared hallway? | Guest mode, consent, arm storage, **whether the lawyer comes before M2b** | Answer before M1. Tell anyone at home about the mic. A recorded yes from each regular member, a parent's decision for children, before M2b and M10 |
| 12 | **PC:** run the check in `research/topology.md` section 15. Windows edition, GPU, RAM, disk. Daily or gaming machine? Where does it sit? | Largest cost unknown, €0 against €1,500+ | Check now, buy nothing |
| 13 | Does the MacBook stay docked at home, or travel daily? | M9, M19, iMessage | Tell me. Daily travel means pricing a Mac mini later |
| 14 | Approve `chmod 700` on your home, the `jorah` user, the LaunchAgent, OpenClaw.app with Mic and Speech, the narrow node exception? | M1 | Yes to all. Computer Control off. **The app gets a node role only if SEC-T15b passes.** Key-only Remote Login is not needed at M1, and comes up at M7 step 7.0 |
| 15 | How do you pronounce Jorah? English only until M20? | Wake tests, provider pick | JOR-uh, `en-US`, English first |
| 16 | Persona, wit and pronoun. Is "stop" for speech and "cancel that" for work acceptable? | M1, M2 | Dry brief colleague, wit about 1 in 20, "it", yes |
| 17 | Which iPhone and iOS (app needs 26.2+)? Own a headset, AirPods, Watch, Android phone, spare device? | M1, M2, M30 | Check Settings |
| 18 | How many of the 10 to 15 hours a week are really free, given Mizyun, Cognio and school? Personal first, with business gates at M4 and M17? | All dates | Measure in M0 and M1. Personal first, at most 10% of hours on business |
| 19 | Monthly cash ceiling, and voice budget? Max does not cover voice | M2a | $25 prepaid (OpenAI $10, Gemini $15), raised only after a real bill. Later €155 including Max before tax |

### M2: voice and phone

| # | Question | My recommendation |
|---|---|---|
| 20 | Read OpenAI's Services Agreement, DPA, sub-processors and enterprise privacy page before prepaying. They returned 403 to research | Do it, 10 minutes, list in `research/gap-private-data-through-realtime-providers.md` section 9. Stop if the age rule blocks you |
| 21 | **D1:** build `jorah-talk` on the Mac at M2b, or no daily realtime until about August 2027? **Declining saves no total hours:** the work moves to M3 and M10, daily realtime comes about 5 months later, M4 to M9 about 2 to 4 weeks earlier, M10 onward unchanged | Build it, after the bench numbers |
| 22 | Widen the `jorah-talk` token to `operator.write` after SEC-T37? Without it, the ear answers only from public notes | Yes if T37 passes, per token. Decide separately for the room ear at M10 |
| 23 | **The phone does not meet gate 4,** having no idle close. Accept a recorded waiver for deliberate sessions, with a hard cap, or native Talk only? Audio keeps going to the provider if a session is forgotten, up to the relay's 30 minutes, at school or in public, and bystanders are recorded | The waiver if the cap can be set and tested, background Talk off, read one week's bill. **If it cannot be set, native Talk only** |
| 24 | Hosted push relay, Limited phone access, Telegram job notices with neutral text? Vocal Shortcut "Hey Jorah"? | Yes to each if its APP test passes. Vocal Shortcuts off at school |
| 25 | Which voice? Unknown speaker: ignore, or public questions only? | Stock calm voice by ear, never imitating the film character. Public questions only |
| 26 | Do you have a ChatGPT plan? Do you use Siri on the Mac? Which Apple team signs the wrappers? | Skip ChatGPT unless Pro is already paid. If you use Siri, Jorah leaves quick Mac tasks to it. Separate team from Mizyun if a business is likely |
| 27 | Is Action Button plus Face ID enough away from home? This most decides any own app | Try for two weeks with the A7 log |

### M3 to M6: safe connections

| # | Question | My recommendation |
|---|---|---|
| 28 | Sign in to Docker for `sbx`, telemetry off? Telegram group in the allowlist needed? | Yes. Remove any group not needed |
| 56 | **Which messengers do you really use?** Only Telegram and iMessage are planned, and personal WhatsApp never. Answer before M4 | Tell me. It decides whether M22 can ever be dropped |
| 29 | Learned instruction patches: at once with undo, or staged? Reject AGPL, FSL and non-commercial licences now? | At once for your typed corrections, staged for everything else. Flag for personal use, block on publishable paths |
| 30 | Which mailboxes, calendar and contacts do you use? Own Google account read-only, or a separate one? Separate Google account for Jorah's browser? | Tell me. Own account read-only for data, separate for browsing. **Read Google's terms on automated use first, an unclear result meaning off.** I did not read them either |
| 31 | May private text ever enter the realtime provider? May reader summaries reach `main` on the Max login? | No, and no by default. Allow a class only after the training check |
| 32 | Telegram detail: counts and times, one-line summaries, or full text? It is not end-to-end encrypted | Counts and times. School data neutral |
| 33 | **EduPage:** student, parent or teacher? Under 16, under 18? How do you log in? Does your login show Enable Webcal? Will you read the terms logged in, or ask the school? May it wait for a local model? | Teacher or staff means do not connect. Feed first, fetched directly, not through Google. **The wrapper stays off unless the terms clearly allow it or the school or aSc says yes in writing. Silence is no.** With no Webcal and no yes: alert emails or screenshots, or M4 passes without a timetable. Read Anthropic's minors' data rules, or school data stays local |
| 34 | Morning brief time and channel | 07:30, Telegram line, detail in the app. Nothing is scheduled without your yes |
| 35 | Should Jorah ever send as you? Personal WhatsApp? | Drafts only until M22. WhatsApp personal number never, hand forward instead. **Dropping M22 leaves "connect to messages" unmet beyond Telegram, and leaves no mail send** |
| 36 | U9: spoken yes alone for own low-stakes writes at the unlocked desk? | No. Tap, then read the diary |
| 37 | May home camera frames go through Max once training is off? Quiet hours, first proactive types? | API for voice Look, Max only for typed Look with you alone. 22:30 to 07:30. Job finished and blocked |

### M5 to M10: hardware and always-on

| # | Question | My recommendation |
|---|---|---|
| 38 | **At M5's exit, before B2:** still keen after the sim? Budget ceiling for the arm, about €720-875, up to €1,025 with options and OpenELAB? Dedicated Pi acceptable? Must the arm run on the ESP32 itself, or USB-hosted with an ESP32 safety layer? | Stage by test. Yes to the Pi. Safety layer. The ESP32-as-master path is in `10` section 10. The stock gripper is not fingers, and M26 is the fingers milestone |
| 39 | Which printer, nozzle, TPU? | Tell me. Check the SO-101 parts fit the bed |
| 40 | BitLocker TPM-only, or a pre-boot PIN? | TPM-only, so a power cut recovers |
| 41 | Offsite backup: Hetzner through restic, or a rotated disk? Where does the passphrase live? Tailnet Lock? | Hetzner, passphrase offline. Decide Lock at M9, knowing its limits |
| 42 | Firmware signing key: YubiKey or offline USB? | Offline, never reachable by Jorah |
| 43 | GPU, UPS: only from M7's data? | Yes. Token savings do not pay for a card |

### M11 and later

| # | Question | My recommendation |
|---|---|---|
| 44 | Autonomy per job, one yes with a budget? Agent inside `sbx`: none, API, or Max? GROW-T4 tools per capability? | One yes per job. None, then API. Per capability |
| 45 | What footage, language, camera settings? May audio ever leave the machine? Music source? API upload? | Share one sample. No. Audio Library shelf. Not now |
| 46 | Which schedules? Evals on API at $25 per run? Real snippets as private eval cases? | Weekly digest at M14, each its own yes. Yes. Yes, per case, with consent for other voices |
| 47 | Rooms, arming timeout, faces, vision away from home? | No biometrics, 30 minutes, no vision at school |
| 48 | Fusion: personal or paid? At M19, or earlier? | Personal until a business gate. M19 unless code CAD disappoints |
| 49 | May home video go to the cloud for training? | Private repo for training only, with consent. Otherwise a PC GPU |
| 50 | Full Disk Access on one launcher for iMessage, which chats? | Decide at M22. Hand forwarding is fine |
| 51 | Base: lawn mower chassis if it still exists, UGV Beast or LeKiwi? Own VEX V5? | Decide at M21, per `08-robotics.md` Q8, Q9 |
| 52 | Publish video of other people, or take paying users, within a year? Open-source the safety core later? Is the robot a business line? | Any time, it changes the legal work. Write those parts as if public. Robot: no |
| 53 | Before anything public: EUIPO and USPTO searches on the name. Resolve Studio before the sale reportedly ends 20 Nov? | Run them yourself. Skip Resolve |
| 54 | **Accept that Jorah reads logs and drafts missions but never flies a drone or plane?** This narrows your goal | Yes: EASA bars autonomy in the open category [track: `03` 14]. Reopened only by legal review and a real need, with Adam-started reviewed missions as the runner-up (`08` 2) |
| 55 | Hands-free confirmation on the robot, a local "yes" in place of the per-goal tap? Gate 9 says no as written, and a TV can say yes | No. If you want it, it is decided at M17, with gate 9 rewritten and its conditions stated first |

## What to buy, by milestone

Each purchase is unlocked by a passed test. **Nothing needs buying before the end of M5, unless you have no spare encrypted disk or headset.** Prices are from research and mix with-VAT and without-VAT, and few Slovak shops were checked, so recheck at checkout. Details in `10-roadmap.md` section 9.

| Milestone | Item | About € | Only if |
|---|---|---|---|
| M0 | Encrypted backup SSD | 0-150 | No spare disk |
| M1 | Headset | Probably owned | None owned |
| End of M5 | R1 bench: XIAO ESP32-S3, adapter, one STS3215 servo, 12 V supply, E-stop, relay, key switch, INA226 | 125-170, to 285 with options | Sim passed, still keen. Servo takes about 3 weeks |
| M7 | Plug meter, dummy plug, cables. Windows Pro about €145 [unverified] if on Home | 20-205 | PC exists |
| End of M8 | SO-ARM101 Pro kit, 5 V supply, clamps, filament | 320-405 | Bench passed |
| M9 | GPU, UPS | 0-1,386 | M7 finds a real gap. Most likely waste in the plan |
| M10 | USB speakerphone and USB power switch | 148-158 | E1 and M9 passed |
| Midway M14 | Pi 5 4 GB, two cameras, powered USB hub | 215-245 | |
| M16 | Targets, small parts | 0-30 | |
| M17 | ReSpeaker XVF3800 | About 60 | |
| M18 | OBSBOT Tiny 2 Lite, easy returns | 199 | Watch really used |
| M21 | Training | 10-30 | |
| M23 | UGV Beast, second Pi, D500 LiDAR, cells, stop switch, radio kill, bumpers | 680-975 | M17 and M21 passed, and you re-decide |

**Running:** Max about €89 a month before tax, about €109 if 23% VAT applies. Voice €20-64 a month from M2a, modelled. PC power €12-22 a month from M9. Offsite about €4 a month if chosen. 1Password about €4 a month from M9, or €0 with `openclaw secrets store`. **Not modelled:** `main` on the API from M3. **Not in the totals:** a lawyer consultation, a few hundred euros [unverified], needed before M2b or M10.

## Top risks

| # | Risk | What the plan does | Where |
|---|---|---|---|
| 1 | **Today, Jorah's `exec` runs as Adam's macOS user.** Anything that reaches it reaches the home folder | Stage 0 in M0, own user in M1 | `03` 5.1, 5.2 |
| 2 | **The Max login carries the whole account, on a position the plan cannot defend.** A log-in article prohibits routing third-party traffic against plan limits, a reported April 2026 announcement names OpenClaw, it is the same account as Mizyun, and the shared 5-hour limit ran out on day 2, most likely from the multi-agent plan research rather than from Jorah | Heartbeat and Dreaming off the plan at M0, voice-started work on the API at M2b, Gateway on the API by M3 unless Anthropic confirms, tested exit in M0 | Decision 4, `research/brain.md` |
| 3 | **Prompt injection** through mail, web and messages reaching a tool | Reader and actor agents, taint, typed output, guard, no private data before M3's hard gate | `03` 7 |
| 4 | **The guard's foundation is untested.** If hooks do not fire on `claude-cli`, `main` loses all outward tools and costs rise | First task of M2a, with a fork table | `10` M2a, M3 |
| 5 | **The realtime provider hears everything once a session opens,** bystanders included, and one wake could keep a cloud mic open and billing. Slovak § 377 may reach this at home [inference, ask a lawyer] | Own client with idle close, `private_show`, boot closed until the lawyer answers, guest mode, named indicator, prepaid caps | `04`, `03` 9.4, 14, `research/gap-private-data-through-realtime-providers.md` |
| 6 | **Scope against time.** 715 hours is 20 months, with Mizyun, Cognio and school competing, and the estimates are judgment | Stop points, rescale after M2a, drop M20 first and M22 next, knowing M22 is the messages goal, stop if daily use has not started by M4 | `10` sections 3, 10 |
| 7 | **OpenClaw moves fast.** 17 stable releases in October, plugin APIs experimental, a thin fork needs the exact wire version | Exact pin, canary, regression suite, Hermes as named fallback on a trigger | `09` 5 |
| 8 | **The PC is unknown** and WSL2 has reported idle kills. Wake and mic under a no-login task are unproven | Nothing bought before M7. E1 in the first hour, 7-day soak, written fork | `10` M7, `02` 6.2 |
| 9 | **A moving arm can hurt someone** | Hardwired E-stop, firmware limits, watchdog, OS boundary test, tap per goal, spoken stop with no network | `08` 5, `03` 18 |
| 10 | **Other people's data and minors' data.** Family in the room, school records, EU law, EduPage terms | Consent, boot closed, teacher role means do not connect, EduPage wrapper off unless allowed in writing, school data off Google and voice, lawyer before M2b or M10 for bystanders, and before anything leaves the household | `03` 9, 14 |
| 13 | **Delegated workers and the Mac app share a trust domain with what they could reach.** Workers run Bash under the Gateway's user, and a node as Adam could be flipped from the `jorah` account | `denyRead` of home, WebFetch and WebSearch denied, wrapper refuses without settings, SEC-T9 on the real targets, SEC-T15b, no node as Adam | `03` 3.4, 15 |
| 11 | **`sbx` is unconfirmed on macOS 27,** and had a Critical CVE and reported hangs | Version floor 0.50.1, timeouts, go or no-go spike at M3, named fallbacks | `05` 3.6 |
| 12 | **"Jorah" may be a hard wake word,** near Laura, Nora, Jura and Torah | Measured in M1, trained with real negatives at M10 | `04` M1.10, M10.5 |

## Start here next session

**Adam, before the session, 10 minutes of attention:** answer decision 1 first. Then in Telegram, send `/new`, then `Test only, don't save this to memory: the codeword is MANGO-42. Reply noted.` Wait at least 1 hour 10 minutes with the Mac awake. Then send `What's the test codeword? Reply with only the codeword, or NONE if you don't have one. Don't search memory or files.` Note the reply. Put your answers in `~/.jorah-private/answers.md`, and paste only what the prompt below needs.

**Then open Claude Code in `/Users/adam/Documents/jorah` and paste this:**

```text
We are starting M0 of the Jorah plan. Read docs/plan/README.md, then in
docs/plan/10-roadmap.md read sections 2, 4 and the M0 milestone, then
docs/plan/09-engineering-and-ops.md sections 3.4 and 4.1.

First run the copy-paste block in roadmap section 2, save it to
docs/evidence/m0/state-YYYY-MM-DD.txt after checking it holds no secret, and tell
me anything that has changed. An unset path is a valid result. Never print secrets
or cat openclaw.json.

My MANGO-42 result: <reply, or "not run">
My answers to README decisions 1 to 10: <answers, kept out of the repo>

Do session M0-A only: steps 0.3 to 0.6, the first commit. Do not touch the live
Gateway. Preview each install and the exact staged file list, and wait for my yes
before installing, committing or pushing. Use they/them for me.

Finish with what changed, the evidence tier reached, the tiers still open, and the
exact steps for me. Then tell me which M0 session comes next and what you need from me.
```

**After M0-A:** M0-B and M0-C1 as PRs. Then M0-C2 with Adam present, then M0-D. M0-E and M0-F can run alongside, up to 2 sessions at once.
