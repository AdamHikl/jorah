# Errands: shopping research, things Adam buys again, exact reminders

Adam, 2026-11-17: Jorah should fully handle "I need new contact lenses, I use <product>, <powers>, find me the best website to buy from, cost and shipping, monthly or weekly?", remember the details the next time he says "I need my lenses", work out from what he buys when he'll run out, and remind him about a month before. Then: "make sure that it is not only for lens shopping but for any other similar questions and we can use the work we do here in other features."

So the pieces are general. Lenses are the first use.

| Piece | Where | What it does |
|---|---|---|
| `reminder_job` | `plugins/jorah-errands` | The exact `automations` call for **any** one-shot reminder: a date, "in 3 days", "in 20 minutes", "a month before 14 May". Code does the date, weekday, daylight saving and UTC. Jorah's rules now use it for every reminder, not only restocking |
| `price_compare` | same | Per unit, per month at Adam's rate of use, and a period's total with shipping and the free-shipping threshold, for any shopping comparison. Unknown prices and shipping stay unknown |
| `supply_list`, `supply_plan`, `supply_save`, `supply_forget` | same | A private record of anything Adam buys again (lenses, vitamins, filters, coffee, a yearly renewal), with run-out and reorder dates worked out in code |
| Shopping rules | `workspace/AGENTS.md`, "Shopping and Things Adam Buys Again" | Main hands comparisons to `deep`, keeps health details out of briefs and searches, passes prices on with shop, link and date, never orders |
| Research rules | `workspace-deep/AGENTS.md`, "Shopping research" | Shops that deliver to Slovakia, each page read the same day, sums through `price_compare`, product facts from the maker's page, a fitting or prescription said plainly |
| Guard rules | `config/permission-matrix.json`, `errands` | The four reads are free; `supply_save` is free in Adam's clean typed chat and a card after outside text or by voice; `supply_forget` is always a card |

`lib/dates.js`, `lib/reminder.js` and `lib/prices.js` don't depend on OpenClaw or on supplies, so a later feature (a warranty or passport reminder, a subscription renewal, the calendar at M4) can reuse them as they are.

## How the dates work

A supply has one or more **lines**, each with its own stock: one per eye when the powers differ, one line for most things. Each line has a pack size (`perPack`, e.g. 6 lenses) and a rate (`use`, e.g. 1 lens per 30 days; 250 g per 7 days).

- A **purchase** adds its days of use, from the later of the day it was bought and the day that line would have run out. Partial days round down.
- A **count** ("I have 2 left") starts again from that day. The unit in use isn't counted, so the date errs early.
- The supply runs out on the **earliest line's** date. A line with no purchase or count is **unknown**, never zero, and is named as missing.
- The reminder is `leadDays` before that, at 09:00 in Bratislava. Automatic lead: a third of the last purchase's cover, at most 30 days. Six months of lenses gives 30 days, as Adam asked; 4 weeks of coffee gives 9. Inside the lead, the tool says **due now** and sets nothing.

**Reminder jobs** are one-shot main-session system events (`sessionTarget: "main"`, `payload.kind: "systemEvent"`, `schedule.kind: "at"`, UTC). That's the heartbeat lane, which delivers to Adam's DM. Isolated and "current" jobs are bound to the chat that created them, and Adam's chat resets daily at 04:00, so one set months ahead could find its chat gone (OpenClaw docs: `automation/cron-jobs/payloads.md`, `delivery.md`). Each supply's reminder has the `declarationKey` `jorah:restock:<id>`. On OpenClaw 2026.10.9, `add` with an existing key updates that job (the cron service's add), so re-setting it after each purchase moves the one reminder instead of adding a second. Generic reminders get a key only when Jorah passes one (`jorah:reminder:<key>`).

**Guard:** a one-off reminder whose text doesn't mention the web is free in Adam's clean chat and a card after outside text, by the existing schedule rule. The texts the plugin writes avoid those words. Removing or changing a job by id would always be a card, which is why re-arming uses the key instead.

## Privacy

The record can hold health data (a lens prescription). It lives only in `/home/jorah/.jorah-errands/supplies.json` on the PC: folder mode 700, file 600, outside the workspace so file tools can't write it past the guard. Never in the repo, `docs/evidence`, test fixtures or shared agent memory. Tests use placeholder powers. The plugin logs only the supply's id and the kind of change. Reminder texts carry the product, never a line's spec. Main's rules keep health details out of `MEMORY.md`, `USER.md`, daily notes, agentmemory, `deep`'s briefs and every search query.

**Backup:** from 2026-11-17, `deploy/jorah-backup.service` also writes a daily `plugin-state-backup` tar (mode 600, kept 14 days, local only) that takes this folder along with the other plugin state. Installed on the PC 2026-11-17 (`docs/runbooks/jorah-on-pc.md`, "Daily backup"). Local only: a dead disk loses the PC and its backups together.

## Deploy, on Adam's yes

Only one session touches the live Gateway at a time. Tier reached before this: source and unit tests.

1. **Copy the commit to `/opt/jorah`,** from the Mac:

   ```bash
   git archive <commit> plugins/jorah-errands config/permission-matrix.json config/pc/errands.patch.json5 scripts/pc/install-errands.sh workspace/AGENTS.md workspace-deep/AGENTS.md | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- tar -x --no-same-owner -C /opt/jorah"
   ```

   Expected: the files are root-owned and their SHA-256 matches the commit. Run `sync` afterwards (files written just before a shutdown came back empty on 2026-11-17).
2. **Rules files:** on 2026-11-17 the live `/home/jorah/workspace/AGENTS.md` and `/home/jorah/workspace-deep/AGENTS.md` matched `main` before this change (SHA-256 starting `67c01cd6d3416477` and `cf47f249d5ba30cb`). If they still do, back each up as `AGENTS.md.pre-errands` and copy the new one in with the old one's owner and mode. If one differs, Jorah has edited it: merge by hand and show Adam the diff first. Rules load in new sessions.
3. **Dry run,** as root in a Terminal attached to no agent:

   ```bash
   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-errands.sh --dry-run
   ```

   Expected: three `Dry run successful` lines, main's tool list with the six new names at the end and nothing removed, and deep's list `group:web, price_compare`.
4. **Install:** the same command without `--dry-run`. It creates `/home/jorah/.jorah-errands` (700), links the plugin, applies the three patches and restarts the Gateway (the guard reads its permission list only at start). Expected: `jorah-errands` enabled in `plugins list`, health ok, audit `Summary` with 0 critical. Config backup: `openclaw.json.pre-errands`.

**Undo:** `install-errands.sh --undo` removes the plugin and restores the config. The state folder stays. Waiting `jorah:restock:*` reminders stay in automations until removed. The rules files come back from `AGENTS.md.pre-errands`.

**Deployed 2026-11-18 10:27 on Adam's yes ("Yes, deploy it")** [measured]:
- **Files:** `/opt/jorah` holds `plugins/jorah-errands`, `install-errands.sh` and both rules files as at `20ed521`, and `errands.patch.json5` as at `3febf59`. All 18 files match by SHA-256, root-owned. The old copies are in `/root/opt-jorah-pre-errands-2026-11-18.tgz`. `/opt/jorah` had no `workspace-deep` folder before.
- **Rules and the guard's list are `20ed521`'s, not `main`'s:** `main` already carried the toolbox commit `2402e98` (rules and guard entries for tools not installed yet), so only the errands lines went live. Live `workspace/AGENTS.md` is `7caf843c…`, `workspace-deep/AGENTS.md` `29bf7f7f…`, the guard's list `0012665f…`. Each old file is kept as `AGENTS.md.pre-errands`, and both matched `main` before the change.
- **Install:** the dry run matched the preview. Main's 27 tools plus the six; `deep`: `group:web, price_compare`; three patches validated. The plugin hot-loaded, then the Gateway restarted at 10:27:32: 16 plugins, "jorah-guard: matrix loaded; state ok", 0 errors in the log since, audit 0 critical and 4 warnings (as before). `/home/jorah/.jorah-errands` is mode 700. Config backup `openclaw.json.pre-errands`. The recycle timer was not touched (next run 14:20).
- **Test turns** in named sessions, read-only, nothing delivered:
  - main (Haiku, `claude-cli`): `reminder_job` gave "Thursday 15 April 2027 at 09:00", `2027-04-15T07:00:00.000Z`, target `main`; `supply_list` count 0.
  - `deep` (Opus, `claude-cli`): `price_compare` gave €4.9833 per lens, €9.97 a month and €59.80 for 180 days.
  - The guard allowed all three. Both sessions were then deleted and forgotten from memory search. `health`'s recent list still named main's.

**Not verified until Adam's test:**
- that a main-session reminder reaches Telegram while the heartbeat runs with `isolatedSession: true` (test 6);
- that Haiku follows the new rules with Adam's real requests (tests 1 to 5);
- a card from `supply_save` after outside text.

## Test in Telegram, after the deploy

Send `/new` first, so the chat starts clean and the first saves need no card.

1. **The request.** Send your lens message as you'd write it: product, both powers, "find me the best website to buy from, cost and shipping, monthly or weekly?".
   - Jorah saves the lenses (no card if he saves before asking Opus, a card if after), says he's asking Opus, and within a few minutes passes on `deep`'s answer: the best shop first; then per shop the pack, pack price, price per lens, per month for both eyes, shipping and the free-shipping threshold, the date checked and a link.
   - It says TOTAL30 is a monthly lens only, and that a 2-week lens is a different lens that needs an optician's fitting.
   - A price it couldn't read says unknown. Nothing is ordered.
2. **Recall.** Send `/new`, then "I need my lenses".
   - Jorah names the product and both powers without asking again, says no purchase is recorded yet, and asks when you last bought and how many you have, or offers to compare shops.
3. **A purchase.** Send "I ordered 1 box of 6 for each eye today from <shop>".
   - Jorah gives the run-out date, 180 days from today, and the reminder date, 30 days earlier at 09:00, with the weekday.
   - In the same chat as step 2 there are no cards. In the chat from step 1 there are two: "Jorah wants to update your supplies record" and "Jorah wants to create or change a schedule". Tap **Allow once** on each.
4. **No double reminder.** Send "I bought one more box per eye". Then "list my automations".
   - The run-out date moves 180 days later, and there is one "Restock: Contact lenses" job, not two.
5. **What-if.** Send "if I buy 2 boxes per eye next time, when will I run out?".
   - A date from `supply_plan`, and nothing saved.
6. **The reminder path, now.** Send "remind me in 2 minutes to check my lens order".
   - Jorah confirms the time. A message arrives in Telegram within about 3 minutes.
   - This is the same path the restock reminder takes months from now. If nothing arrives, tell Claude: `openclaw --profile jorah automations runs <id>` shows why.
7. **Any reminder.** Send "remind me a month before 14 May 2027 that my passport expires".
   - "Wednesday 14 April 2027 at 09:00".
8. **Any shopping question.** Send "where's the best place to buy Vitamin D3 2000 IU, 1 a day, cost per month with shipping?".
   - The same kind of answer as step 1, with per-month figures. Then "I bought 2 bottles of 90" gives a run-out date about 6 months away and a reminder 30 days before.
