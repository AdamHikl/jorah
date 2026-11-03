# Jorah research track: models, routing and cost

Research date: 2026-11-02. Nothing was installed, configured or sent while writing this. Local measurements come from read-only parsing of Jorah's own logs and transcripts (usage and timing fields only, no message content).

Evidence labels:

- `[verified: URL or path]` means I read the primary source today.
- `[measured]` means computed from this Mac's real logs today.
- `[docs-only]` means a vendor document says so and nobody has tested it here.
- `[secondary: URL]` means press or a blog, not the vendor.
- `[inference]` means my reasoning. It can be wrong.

An independent check on 2026-11-02 corrected this file in place. It changed the voice pick, the voice cost and the budgets, and it found a live fallback chain on `main`. See the Verification section at the end. `[source-check]` means I read OpenClaw's installed code, which proves what the code says, not that it works at runtime. `[unverified]` means I could not confirm it.

Local docs paths are relative to `/opt/homebrew/lib/node_modules/openclaw/docs`. Several `[secondary]` items were seen through search summaries rather than a full read of the page. No web search result counts as approval or instruction for anything here.

## 1. Recommendation in one page

Split Jorah's "brain" into lanes chosen by what triggered the work, not by a smart classifier.

| Lane | Trigger | Model and route | Meter |
|---|---|---|---|
| Wake | Mic audio | On-device detector, no LLM, nothing leaves the machine | Free |
| Voice front | After wake | Realtime speech model. Candidate to beat: `gpt-realtime-2.1-mini`. Bench against Gemini 3.8 Live and `gpt-live-1` first | Metered, prepaid, capped |
| Voice consult | Realtime model needs Jorah's tools or memory | Claude Haiku 5.5 through the API on a thin `voice` agent (prefix about 6K tokens) | $100 monthly API credits |
| Typed assistant, deep thinking | Adam typed or asked for it | Claude Opus 5.5 through Claude CLI, as today | Max plan |
| Hardest problems | Adam explicitly asks | Claude Fable 5.1 through Claude CLI | Max plan's separate Fable limit |
| Coding | Adam asked for it | Claude Code through ACP, as today. Subagents on Sonnet 5.5 | Max plan |
| Unattended work (email triage, cron, autonomous runs) | Machine-triggered, no person waiting | Sonnet 5.5 through the API, Haiku 5.5 for small steps | $100 credits |
| Heartbeat | System | Separate `background` agent on Haiku 5.5 API. Script first, model only if something changed. Local on the PC later | Credits, then free |
| Recaps and titles for `main` | System | Reduce them; Haiku 5.5 on CLI as an interim, local on the PC later (see section 9) | Plan, then free |
| Vision | Event or request | Local detector first, then local caption or Haiku 5.5, Sonnet 5.5 only for real analysis | Mostly free |

Why, in short:

1. Claude CLI is too slow for voice. Warm turns took a median 1.2 s and cold ones 3.1 to 3.3 s, with a p90 of 12 s across all user turns `[measured]`. macOS native Talk also waits for the whole reply before speaking `[verified: nodes/talk/macos-relay.md]`.
2. Anthropic's terms make the plan a poor home for unattended automation (section 3). The plan's blast radius is high because `~/.claude-jorah` and Adam's main login are the same Claude account `[verified: account ids compared locally, not printed]`.
3. The Max plan already includes $100 a month of API credits, which expire if unused `[verified: https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers]`. A thin Haiku lane uses a tiny fraction of that.
4. Jorah's current prompt prefix is about 67K tokens `[measured]`. That is the largest cost driver and it makes local models unusable for conversation. A thin lane fixes both.

Monthly budget (section 7): about $113 at pilot level, about $240 as a daily driver and about $590 as full Jarvis, including the $100 Max plan. Voice is the least certain item, so the bench must measure it. Prices are USD list and exclude any VAT.

Spending cap for the first phase: $100 Anthropic credits with no purchased balance, plus at most $25 for the voice vendor. Raising it needs Adam's explicit yes.

## 2. Current state I found

### Config

- `agents.defaults.model`: primary `anthropic/claude-opus-5-5`, no fallbacks there `[verified: openclaw --profile jorah config get agents.defaults.model]`. **That is not the whole picture.** `agents.entries.main.model.fallbacks` holds a 10-step chain: Haiku 5.5, Opus 5, Sonnet 5.5, Sonnet 5, Fable 5.1, Fable 5, Opus 4.7, Sonnet 4.6, Opus 4.6 and `anthropic/*` `[verified: config get agents.entries]`. An agent's list overrides the defaults, so setting `fallbacks: []` on defaults does not clear it `[source-check: dist/agent-scope-bJOokm5r.mjs; docs: concepts/model-failover.md]`. `openclaw models status` still prints `Fallbacks (0)`, because it shows the defaults `[verified: local command]`.
- `agents.defaults.heartbeat`: every 1h, Haiku 5.5, `isolatedSession: true` `[verified: same command with agents.defaults.heartbeat]`.
- `agents.defaults.utilityModel`: unset, so it derives from the primary provider `[verified: same command, and gateway/cli-backends.md]`.
- All `anthropic/*` entries pin `agentRuntime.id: claude-cli` `[verified: config get agents.defaults.models]`.
- `scripts/switch-brain.sh` flips every `anthropic/*` entry together and reports a `mixed` state as a `PROBLEM`. A lane design needs this changed (section 9).
- Claude Code is 2.1.300. Ollama is present at `/usr/local/bin/ollama` with no models listed for this profile. `llama-server` is absent `[verified: local commands]`.

### Measured turn timing

Source: `/tmp/openclaw/openclaw-jorah-2026-11-0*.log`, `cli exec` and `cli turn` lines, 2026-11-01 17:45 to 2026-11-02 17:09 `[measured]`. Durations are whole-turn wall clock, not time to first token, and include any tool calls.

| Turn type | n | p50 | p90 | Median output |
|---|---|---|---|---|
| Opus 5.5, user turn, warm process (`reuse=reusable`) | 27 | 1.2 s | 5.6 s | not split out |
| Opus 5.5, user turn, no reuse | 36 to 37 | 3.2 to 3.3 s | 12.1 s | not split out |
| Opus 5.5, user turn, reuse invalidated | 7 to 8 | 9 to 11 s | about 29 s, tiny sample | not split out |
| Opus 5.5, all user turns | 71 | 3.0 s | 12.1 s | 113 bytes |
| Sonnet 5.5, user turns | 4 | 18.0 s | 19.2 s | 250 bytes |
| Haiku 5.5, background summary, cold spawn | 159 | 3.1 s | 4.7 s | 173 bytes |
| Heartbeat on Haiku 5.5 | 2 | runs took 3.1 s and 8.7 s | n/a | 8 bytes |
| Heartbeat on Opus 5.5 | 24 | 1.4 s | 1.9 s | 8 bytes |

I re-derived this table from the same logs, joining `cli exec` and `cli turn` lines by trace id. The headline numbers hold. The ranges show how much the join changes them. The fastest Opus turn was 0.53 s, so the warm path can be quick. The Sonnet sample is small and those were probably larger turns, so do not read it as Sonnet being slower than Opus.

Three findings from those logs:

- **Background summaries outnumber real turns 2 to 1.** There were 159 `session-activity-summary` runs against 77 user turns in 23.4 hours `[measured]`. Each one spawns a fresh Claude Code process on the plan. This is OpenClaw's rolling Activity recap `[verified: concepts/models.md]`, and it is on by default through the derived utility model.
- **Heartbeats ran on Opus 5.5 for 24 runs** up to 2026-11-02 08:00, then on Haiku 5.5 for the 2 most recent runs `[measured]`. This matches the current config, so it looks fixed. Keep watching it, because `status` only shows the last CLI turn.
- **The fallback chain has already fired** `[measured, after the original window]`. There were 44 `model_fallback_decision` events. Two runs on Opus 5.5 failed (`session_expired` at 2026-11-01 17:49, `timeout` at 2026-11-02 03:30) and were then answered by Haiku 5.5 automatically. The logs do not show whether the reply said so.
- **Jorah's heartbeats ran into the plan's 5-hour limit on day 2** `[measured, after the original window]`. From 18:53 to 20:16 on 2026-11-02, four heartbeats failed with "You've hit your session limit", which reset at 21:10. Each heartbeat then walked the whole chain: 36 failed attempts on nine real models, including Fable 5.1, plus 4 attempts on the literal model `*`, which Claude Code rejected. Nothing reached a paid meter, because no API key exists yet. With a key on that route, this walk could reach Fable at $10/$50. No user turn hit the limit in the log. The account is shared with Adam's other Claude Code work, and a multi-agent research run was active that evening, so I cannot say how much of the limit Jorah used. That run's agents failed with the same limit and the same 21:10 reset, so it is the likely main cause `[inference]`.
- **Reuse matters more than model choice** for short replies. Invalidated reuse is about 8 times slower than warm reuse. OpenClaw restarts the warm process when the prompt changes `[verified: gateway/cli-backends.md]`, which memory injection can trigger `[inference]`.

### Measured token profile

Source: `~/.claude-jorah/projects/**/*.jsonl`, usage fields only, deduplicated by message id, 2026-11-01 16:29 UTC to 2026-11-02 16:09 UTC `[measured]`. The dollar column is what the same tokens would cost at API list price. It is not a bill, because this ran on the plan.

| Model | Requests | Cache write | Cache read | Output | API-equivalent |
|---|---|---|---|---|---|
| Opus 5.5 | 795 | 1,189,093 | 8,058,342 | 41,997 | $8.42 |
| Sonnet 5.5 | 16 | 195,617 | 1,074,338 | 4,047 | $0.64 |
| Haiku 5.5 | 11 | 214,253 | 429,499 | 1,610 | $0.03 |

Arithmetic and what it shows:

- Opus cost split: cache writes 1,189,093 × $5/M = $5.95, cache reads 8,058,342 × $0.20/M = $1.61, output 41,997 × $20/M = $0.84. **Cache writes are 70% of the cost.**
- Total $9.09 over 76 Opus and Sonnet user turns is about **$0.12 per user turn** at list price. I split it by project folder: `workspace` is $8.48 (93%), `sandbox` is $0.43 across 628 mostly tiny requests, and `work/cognio` is $0.23. So the chat figure is about **$0.11**, and delegated work barely moves it `[measured]`. $5.09 of the total fell in one hour, so this was a setup-heavy day.
- **The table leaves out the utility calls.** It shows 11 Haiku requests, but the logs show 159 Haiku summary runs. Those tool-free completions do not write these transcript files, so their plan draw is unmeasured `[measured; cause is inference]`.
- Sustained, that is $9.09 × 30 = $273 a month for one person's chat. This extrapolates one setup day, so treat it as an upper estimate. It still shows why the plan is worth keeping for typed turns `[inference]`.
- Context size on substantive requests: median **67K tokens** on Opus and Haiku, 80K on Sonnet.

Why the prefix matters. Cost of one short turn with a 67K prefix, 500 new input tokens and 200 output tokens, from list prices `[verified: https://platform.claude.com/docs/en/about-claude/pricing]`:

| Model | Warm (cache hit) | Cold (cache write) | Cold / warm |
|---|---|---|---|
| Opus 5.5 | $0.0194 | $0.341 | 18× |
| Sonnet 5.5 | $0.0097 | $0.171 | 18× |
| Haiku 5.5 | $0.0008 | $0.0085 | 10× |

A voice turn after 5 idle minutes is always cold, because the default cache lives 5 minutes `[verified: https://platform.claude.com/docs/en/build-with-claude/prompt-caching]`. Voice use is bursty, so assume about half of turns are cold `[inference]`.

## 3. Anthropic line-up, limits and terms

### Models and API prices

All from `[verified: https://platform.claude.com/docs/en/about-claude/pricing]` and `[verified: https://platform.claude.com/docs/en/about-claude/models/overview]`.

| Model | Input | 5m write | 1h write | Cache read | Output | Latency label | Default effort |
|---|---|---|---|---|---|---|---|
| `claude-fable-5-1` | $10 | $12.50 | $20 | $0.25 | $50 | Slower | high |
| `claude-opus-5-5` | $4 | $5 | $8 | $0.20 | $20 | Moderate | medium |
| `claude-sonnet-5-5` | $2 | $2.50 | $4 | $0.10 | $10 | Fast | high |
| `claude-haiku-5-5` up to 100K prompt | $0.10 | $0.125 | $0.20 | $0.01 | $0.50 | Fastest | medium |
| `claude-haiku-5-5` over 100K prompt | $0.50 | $0.625 | $1 | $0.05 | $2.50 | Fastest | medium |

Per million tokens. All have 1M context and 128K output, all take images.

Practical points:

- **Haiku's 100K trap.** A prompt above 100,000 tokens pays 5× `[verified: pricing page]`. Today's prefix of 67K is under it, but not by much. The count includes cache reads and writes `[verified: pricing page]`. Alert if a Haiku lane request exceeds 80K `[inference]`.
- **Batch API** is 50% off, for work that can wait. **Fast mode** on Opus 5.5 is $8/$40 and improves output speed, not time to first token, so it does not help voice `[verified: https://platform.claude.com/docs/en/build-with-claude/fast-mode]`.
- **Web search** is $10 per 1,000 searches plus tokens. Web fetch has no extra charge `[verified: pricing page]`.
- **Thinking.** Opus 5.5 cannot turn thinking off, so use `low` effort. Sonnet 5.5 can use `between_tools`. Haiku 5.5 allows `disabled` at `high` effort or below, and OpenClaw exposes `off` for it `[verified: https://platform.claude.com/docs/en/build-with-claude/thinking; providers/anthropic.md]`. This is API only. Claude Code cannot turn thinking off on Opus 5.5, Sonnet 5.5, Haiku 5.5 or Fable `[verified: https://code.claude.com/docs/en/costs]`, so the plan-route Haiku lanes keep thinking on.
- **Rate limits are not the constraint.** Even the Start tier gives Haiku 5.5 4,000 RPM. Start has a $500 monthly spend cap. Orgs linked to an eligible plan reach at least Start `[verified: https://platform.claude.com/docs/en/api/rate-limits]`.
- **Region.** The first-party API is global by default. `inference_geo: "us"` costs 1.1×. No EU option on the first-party API was listed on the pricing page. Bedrock and Google Cloud offer regional endpoints at a 10% premium, and the plan's credits do not apply there `[verified: pricing page, credits page]`. Stay on first-party while this is personal. Revisit if it becomes a business.

### Max plan limits

- Max is $100 a month and gives five times Pro's usage per 5 hours and per week, with a separate weekly limit for Fable `[verified: https://support.claude.com/en/articles/11049741-what-is-the-max-plan]`.
- All usage across Claude and Claude Code shares those limits. Anthropic publishes no token or hour figures. Third-party hour estimates conflict, so ignore them `[verified: https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan]`.
- The $200 Max 20x tier is now Ultra: 10× Pro weekly, $200 monthly credits, no 5-hour limit for verified accounts `[verified: https://support.claude.com/en/articles/17728952; credits page]`. The 2026-10-30 date is from press only `[secondary: https://windowsreport.com/anthropic-renames-claude-max-5x-and-20x-plans-removes-ultras-5-hour-limit/]`.
- Max keeps its 5-hour limit, and Jorah's heartbeats have already run into it once, most likely because of a multi-agent research run (section 2). A blocked heartbeat is harmless, but a blocked voice or typed turn is not. This is a stronger upgrade signal than the weekly limit `[inference]`.
- **Upgrade rule** `[inference]`: Ultra costs $100 more and adds $100 of credits. Once Adam's monthly API spend is reliably above $200, Ultra costs the same and doubles the weekly limit.
- Jorah's plan draw competes with Adam's own Claude Code work, including Mizyun. Measure it: read `/usage` under the Jorah login for one week, split by Attribution `[verified: https://code.claude.com/docs/en/costs]`.

### What the terms say about unattended use

Facts, all read today:

1. Consumer Terms section 3 bars automated or non-human access, except with an API key or where Anthropic explicitly permits it. Section 2 requires users to be at least 18. Max users are under these terms `[verified: https://www.anthropic.com/legal/consumer-terms; https://code.claude.com/docs/en/legal-and-compliance]`.
2. The plan support article says that as of its 2026-06-15 and 2026-10-07 updates, Agent SDK, `claude -p` and third-party app usage still draw from subscription limits `[verified: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan]`.
3. The log-in article says plans are designed for ordinary use of native Anthropic applications, that routing third-party traffic against subscription limits is prohibited, and that Anthropic may at its discretion let usage-credit holders use certain third-party tools and charge those credits. API keys are the preferred route for third-party tools `[verified: https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account]`.
4. The Claude Code legal page says advertised limits "assume ordinary, individual usage" of Claude Code and the Agent SDK. It says the rules do not prevent an end user from signing in to the unmodified binary with their own subscription, that developers may not collect or intermediate Claude.ai credentials, and that Anthropic may enforce without notice `[verified: legal page above]`.
5. In April 2026 Anthropic announced that OpenClaw and other third-party harnesses could no longer use subscription limits. It later paused a replacement credit plan `[secondary: https://techcrunch.com/2026/04/04/anthropic-says-claude-code-subscribers-will-need-to-pay-extra-for-openclaw-support/; verified for the pause: fact 2]`.
6. OpenClaw's `claude-cli` route drives the installed binary and does not read, store or refresh the native login. Its optional `setup-token` route does save a subscription token and forward it `[verified: providers/anthropic.md]`.

**The sources disagree, and I could not resolve it.** Fact 2 reads as permissive, fact 3 as prohibitive, and none of them names this exact setup.

My reading `[inference, not legal advice]`:

- A person using the unmodified binary, signed in through Anthropic's flow, with turns they started themselves, is the most defensible plan route. That is where typed chat and delegated coding sit today.
- An always-on hourly heartbeat, unattended cron jobs and a voice loop look least like "ordinary, individual" use.
- The downside is account action on the same Max account Adam uses for everything else.

Rules that follow:

- Person asked, Claude Code does it: plan is fine.
- Machine triggered it, nobody is waiting: API credits or local.
- Never use `setup-token` or `paste-token` with a plan credential.
- If Jorah becomes a product, every Claude call must be on API keys or each user's own account. Reselling or intermediating plan usage is not allowed `[verified: legal page]`.

### The $100 credits

From `[verified: https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers]`:

- Max gets $100 per billing cycle, no rollover. They cover the API, Managed Agents, the Agent SDK and the Playground. They do not cover Claude Code. The support article adds that they do cover `claude -p` run with an API key from the linked org `[verified: support article above]`. Those two statements sit awkwardly together, so do not rely on `claude -p` with credits until it is tested.
- No payment method is required. If only these credits exist, requests stop when they run out and the plan is never charged. **This is a real hard cap by construction**, as long as nothing is purchased and auto-reload stays off. Auto-reload works from the purchased balance, so it can fire even while included credits remain.
- Each plan links to one Console org and you cannot change it yourself. A subscriber can claim after 7 days on the plan.
- Credits are spent before purchased balance. Every key in the org shares the balance. Workspace spend limits can cap a project, except on the default workspace.
- Credits refresh by billing cycle, but spend caps reset on the first of the calendar month.

### Data handling by route

- **Plan route**: consumer terms. With model improvement on, de-identified sessions may be kept up to 5 years. With it off, not used for future training, and deleted chats leave back-end storage within 30 days `[verified: https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data]`. Adam should confirm the setting is off for this account, because Jorah will read other people's messages.
- **API route**: inputs and outputs deleted within 30 days, with exceptions `[verified: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data]`. Anthropic may not train models on customer content under the Commercial Terms `[verified: https://www.anthropic.com/legal/commercial-terms]`. Those terms also say the services are not for consumer use. Claiming the plan's credits to run your own apps and agents is a documented use, but ask Anthropic if this becomes a business `[inference]`.
- **Rule** `[inference]`: anything containing other people's data (messages, email, EduPage) goes through the API or local lanes, not the plan lane, once those lanes exist.

## 4. Latency: Claude CLI versus direct API

**Answer: keep CLI for typed turns and coding. Do not use it for voice.**

- CLI measured: warm turn p50 1.2 s, no reuse 3.3 s, invalidated 9.2 s, cold tiny-output Haiku 3.1 s `[measured]`.
- Direct API baseline: **not measured**, because no API key is saved yet. Third-party numbers are unusable: Artificial Analysis listed 370 s and 515 s for Haiku and Sonnet at max effort, which are plainly not comparable, and a class median of 1.59 s `[secondary: https://artificialanalysis.ai/models/claude-haiku-5-5]`.
- Likely cold-spawn overhead is 1.5 to 2.5 s `[inference from a 3.1 s Haiku turn with tiny output]`. Warm overhead is unknown.
- Native macOS Talk adds its silence window (700 ms default) and then waits for run completion before speaking, so the p90 is bad regardless of runtime `[verified: nodes/talk.md; nodes/talk/macos-relay.md]`.

Targets for later acceptance `[inference]`:

| Moment | Target |
|---|---|
| Wake word to "listening" cue | under 300 ms |
| End of speech to first audio, chit-chat in the realtime model | under 1.0 s |
| Consult answer spoken (Haiku thin lane) | p50 under 2.5 s, p90 under 5 s |
| Long job | Spoken acknowledgement under 1 s, result announced later |

**First thing to measure once a key exists** (section 9, step B2): the same 20 short prompts on Haiku 5.5 through CLI warm, CLI cold and direct API, capturing time to first text delta and total. Expected spend is under $0.10.

## 5. Realtime voice providers

Prices from `[verified: https://aistudio.google.com/docs/pricing]` (the old `ai.google.dev` URL redirects there) and `[verified: https://developers.openai.com/api/docs/pricing]`.

**Correction: the flat Gemini figure was wrong.** Google's pricing page does print per-minute conversions, but its Live best-practices page says the Live API bills strictly by tokens and charges per turn for all tokens in the session context, so each turn costs more as a session grows `[verified: https://aistudio.google.com/docs/live-api/best-practices]`. A forum reply marked as staff says the Live API has no explicit or implicit caching, so history is re-billed at the full rate `[secondary: https://discuss.ai.google.dev/t/gemini-live-api-caching/174701]`. OpenAI re-sends context too, but automatic caching bills most of it at the cached rate `[secondary: search summary of https://developers.openai.com/api/docs/guides/realtime-costs, which returned 404 when I opened it]`.

| Option | Vendor list price, per M tokens | Estimate per connected minute `[inference]` | Vision | Slovak | OpenClaw status |
|---|---|---|---|---|---|
| `gpt-realtime-2.1-mini` | Audio $10 in, $20 out, $0.30 cached | **$0.009 short, $0.016 at 10 min, $0.021 at 30 min** | One JPEG on `describe_view` in browser Talk | Not confirmed | In the plugin's model list `[source-check: dist/extensions/openai]`. Needs a Platform key on relay and iOS `[docs-only: nodes/talk.md]` |
| Gemini 3.8 Live (`gemini-3.8-live`) | Audio $3 in, $12 out; image and video $1; text $0.75 in, $4.50 out | **$0.015 short, $0.054 at 10 min, $0.13 at 30 min** | 1 frame per second. Documented for browser Talk only, frames go directly to Google `[docs-only: nodes/talk/realtime-sessions.md]` | Listed `[verified: https://aistudio.google.com/docs/live-api/capabilities]` | Relay and `agent-consult` advertised `[source-check: dist]`. **Must set the model**, see caveats |
| `gpt-realtime-2.1` | Audio $32 in, $64 out, $0.40 cached | **$0.048 at 10 min** | Same as mini | Not confirmed | Documented macOS relay example `[docs-only: nodes/talk/macos-relay.md]` |
| `gpt-live-1` | $0.05 per session minute, billed per second, plus backend | **$0.05 plus backend** | None `[verified: https://developers.openai.com/api/docs/models/gpt-live-1]` | Not stated | Browser and relay implemented, iOS live verification pending `[verified: nodes/talk.md]` |
| `gpt-live-1-codex` via ChatGPT sign-in | Depends on plan | Unknown | None | Not stated | OAuth first, **then falls back to a Platform key** `[verified: nodes/talk.md]` |

Arithmetic, all `[inference]`. Three session shapes:

- Short wake session: 4 turns, 4 s of speech and 8 s of reply each, 60 s of talk, then a 45 s idle tail before closing, so 1.75 connected minutes.
- 10 minutes: 20 turns, 10 s and 15 s each.
- 30 minutes: 60 turns, same shape.

Gemini, using the pricing page's implied 28 tokens/s in and 25 tokens/s out, a 2,000-token prefix, audio history re-billed every turn and no caching:

- Short: history 3,120 × $3/M + prefix 8,000 × $0.75/M + output 800 × $12/M + transcripts $0.0007 = $0.026, or $0.015 per connected minute.
- 10 minutes: history 137,550 × $3/M = $0.41, plus prefix $0.03, output $0.09 and transcripts $0.01 = $0.54, or $0.054 per minute.
- 30 minutes: history about 1.2M × $3/M = $3.60, plus $0.38 of the rest = $3.98, or $0.13 per minute.
- One developer reported about 16,400 tokens per minute in production, which is roughly $0.04 per minute at these rates `[secondary, seen through a search summary: discuss.ai.google.dev]`. That sits inside this range.

Mini and 2.1, using OpenAI's user audio at 1 token per 100 ms and assistant audio at 1 token per 50 ms, with silence removed by VAD `[secondary: search summary of the same OpenAI guide]`. These match the 600 and 1,200 tokens per minute the first draft recalled, but I could not open the page:

- Mini, 10 minutes: input 2,000 × $10/M + output 6,000 × $20/M + cached history 76,000 × $0.30/M = $0.163, or $0.016 per minute.
- Mini, short: $0.015 per session, or $0.009 per connected minute. Mini, 30 minutes: $0.63, or $0.021 per minute.
- Full 2.1, 10 minutes: $0.064 + $0.384 + $0.030 = $0.48, or $0.048 per minute.
- OpenClaw's OpenAI input transcription (`gpt-4o-mini-transcribe`) is billed separately and is not in these figures.

**Planning number for section 7: $0.04 per connected minute.** It deliberately sits between short and long Gemini sessions. Mini should come in well under it. Replace it with vendor usage data after the bench.

**Pick, changed by this check: `gpt-realtime-2.1-mini` is the candidate to beat, Gemini 3.8 Live is the runner-up, and a short bench decides.** The original case for Gemini rested on being cheapest. On token billing without caching that no longer holds, except possibly in very short sessions, and mini looks cheaper there too. Mini also has the lower-risk route, because OpenAI is the documented macOS relay example.

Gemini 3.8 Live still has real advantages:

- It lists Slovak.
- It has non-blocking function calling, so Jorah can keep talking while a consult runs `[verified: Live capabilities page]`.
- It takes continuous 1 fps video.
- Paid-tier prompts are not used for training `[verified: pricing page]`.

**Choose Gemini instead if** spoken Slovak matters, continuous video matters, or mini blocks speech during a consult.

Caveats:

- **OpenClaw defaults Google realtime to `gemini-3.1-flash-live-preview`** `[source-check: dist/extensions/google/realtime-voice-provider.js; docs: providers/google.md]`. That model has synchronous function calling only `[verified: capabilities page]`. Set `talk.realtime.model: "gemini-3.8-live"`, or the non-blocking benefit disappears.
- Sessions cap at 15 minutes for audio and **2 minutes for audio plus video without context window compression**, and a connection lasts about 10 minutes unless resumed. Resumption handles last 2 hours `[verified: https://aistudio.google.com/docs/live-api/session-management]`. The first draft named resumption as what lifts the cap, which was wrong: compression lifts it and resumption survives reconnects. OpenClaw turns on both by default and declares resumption support `[source-check: same file; docs: providers/google.md]`. Not tested at runtime.
- **Compression will not control cost here.** OpenClaw only exposes on or off and sends no trigger, so Google's default applies: 80% of the model's context window `[source-check; default seen through a search summary of https://ai.google.dev/api/live]`. Keep cost down by keeping sessions short.
- Video history is re-billed too if it stays in context, so the $0.002 per minute in section 7 probably understates video `[inference]`. Measure it before planning on continuous vision. Do not assume the 2-minute limit is gone: a forum report describes 3.1-preview audio-plus-video sessions dying near 2 minutes `[secondary: discuss.ai.google.dev, seen through search only]`.
- OpenClaw's macOS relay needs `talk.catalog` to advertise `gateway-relay` and `agent-consult` for the chosen provider `[verified: nodes/talk/macos-relay.md]`. The code advertises both for `google` and `openai` `[source-check: dist/handlers-B5Rt4cMl.mjs and both provider files]`. Confirm with a live `talk.catalog` call.
- The Mac must also opt in under **Settings > Voice & Talk > Use realtime Gateway relay**, which is off by default. If the relay fails to start, Talk shows the reason and falls back to the native speech path for that session `[verified: nodes/talk/macos-relay.md]`.
- Gemini API terms require users to be 18 or older, and API clients offered to EEA users must use paid services `[verified: https://aistudio.google.com/docs/terms]`. Use a paid project regardless.

**Third option: GPT-Live through ChatGPT sign-in,** if Adam already pays for ChatGPT (their notes mention Codex). It has the best interruption story on paper, and a 0.8 s latency claim I could only find second-hand `[secondary: https://pasqualepillitteri.it/en/news/15720/openai-gpt-live-1-api-voice]`. It cannot see. OpenClaw warns OAuth does not imply included or unlimited use, so whether a plan covers it is unconfirmed `[verified: providers/openai/voice-and-speech.md]`.

**New fact that could change the voice economics:** ChatGPT Pro ($100, $200 or $500 tier) includes matching monthly API credits, and they cover the Realtime API and GPT-Live. Plus does not qualify `[verified: https://developers.openai.com/api/docs/guides/chatgpt-api-credits]`. If Adam is on Pro, an OpenAI voice lane may cost no extra cash.

**What changes the pick:** real usage data contradicting these estimates, poor barge-in, or mini failing the relay check.

**Bench cost:** 20 minutes each, in 10-minute sessions: mini $0.34 + Gemini $1.08 + `gpt-live-1` $1.00 = about $2.40, plus under $0.10 of consults. Gemini is the uncertain item here.

**Hard rule: never stream before wake.** Streaming a mic to Gemini all month costs at least $0.005 × 43,200 min = $216, before any context re-billing, and video adds at least $86. Connect on wake, close after 30 to 60 seconds of silence `[inference]`. The privacy reason is stronger than the cost reason.

## 6. Local models

### The prompt problem comes first

OpenClaw warns that a model which answers a short prompt can still fail an agent turn `[verified: gateway/local-models.md]`. M1 Max 64GB community numbers for Qwen3.6 27B are about 90 tokens/s prompt processing and 14.6 tokens/s generation. The 27B figures are confirmed on the page, but they were measured at a 1,024-token context, so speed on a 67K prompt may differ `[verified: https://omlx.ai/benchmarks/eako8p23; still a community submission]`. The MoE Qwen3.6 35B is about 611 and 46 `[unverified: oMLX community list seen through search, https://omlx.ai/benchmarks?page=8]`.

Cold prompt processing on this Mac `[inference, arithmetic]`:

| Prompt | Dense 27B | MoE 35B |
|---|---|---|
| Today's 67K prefix | 67,000 / 90 = 744 s | 67,000 / 611 = 110 s |
| Thin 4K prefix | 44 s | 6.5 s |

So on the M1 Max, local models are for background work with thin prompts, never for live replies. OpenClaw automatically uses Tool Search on local Ollama models, which helps `[verified: providers/ollama/recipes.md]`.

### What to run

Sizes from `[verified: https://ollama.com/library/gemma4; https://ollama.com/library/qwen3.6]`. A context allowance must fit too, so leave headroom. PC specs are unknown, so these are tiers.

| GPU memory | Tier | Pick | Use |
|---|---|---|---|
| 8 GB | Below minimum for agent work | `gemma4:e2b` (4.6 to 7.5 GB) | Classification, titles |
| 12 GB | Minimum | `gemma4:12b` (about 8 GB) | Summaries, utility, simple vision |
| 16 GB | Low | `gemma4:12b`; `gemma4:26b` is tight at 16 to 19 GB | Same, some tools |
| 24 GB | **Recommended** | `gemma4:26b` or `qwen3.6:27b` (18 to 19 GB), with STT on CPU or kept small | Background agent with tools |
| 32 GB (RTX 5090) | Comfortable | `qwen3.6:35b` (23 GB) plus local STT and TTS | Background agent plus voice stack |
| 48 GB or more | Luxury | Larger models, parallel services | Not needed for MVP |

**What to check on the PC:** GPU model and VRAM (`nvidia-smi`), system RAM, free NVMe space (100 GB or more for models), power supply, driver and CUDA version.

Tool-calling evidence is thin. One September 2026 test over four MCP servers found 93 to 97% well-formed calls for its top models, and about 80 to 90% end to end on real multi-step work. Gemma 4 "27B" was the default pick for 24 GB `[secondary, author's internal test: https://www.promptquorum.com/power-local-llm/best-local-models-tool-calling-2026]`. That page's model names do not match Ollama's tags exactly. Run Jorah's own tool test before trusting any of this. Gemma 4 is reported as Apache 2.0 `[secondary: https://urandom.io/blog/2026-04-05-gemma-4-apache-license-matters-more-than-benchmarks]`. Qwen3.6 27B and 35B are reported as Apache 2.0 `[secondary: OpenRouter and RunPod listings; model cards not read]`. Ollama's library pages state no license for either family.

### Which server

| Server | Verdict | Why |
|---|---|---|
| **Ollama** | **Pick** | Single user, simple service, native OpenClaw provider. Keep `num_ctx` explicit `[verified: providers/ollama/recipes.md]` |
| llama.cpp | Runner-up | OpenClaw's managed plugin checks hardware and verifies downloads `[verified: gateway/local-models.md]`. One test found Ollama slower than llama.cpp on some cards and matching on an RTX 4090 `[secondary: https://computingforgeeks.com/ollama-vs-vllm-vs-llama-cpp/]`. Switch if Ollama measures slow |
| vLLM | Not yet | Wins under concurrency, not for one user `[secondary: https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/]`. Reconsider only if several local agents run in parallel |

Known trap: on WSL2 with NVIDIA, the Ollama systemd service can reload the last model at boot and cause VM restart loops `[verified: gateway/local-models.md]`.

### Safety

Local models have no hosted safety filters `[verified: gateway/local-models.md]`. Never give a local model both untrusted content (web, email, messages) and write or exec tools `[inference]`. Local lanes are read, summarize and propose.

### Hardware cost

Mid-2025 list prices were €2,099 for an RTX 5090 and €1,059 for an RTX 5080 `[secondary: https://www.pcgamesn.com/nvidia/rtx-5000-europe-price-cut]`. Street prices have since moved far above that: 2026 reports put the cheapest RTX 5090 listings in Germany above €5,000, blaming a memory shortage and AI demand `[secondary, seen through search: https://www.guru3d.com/story/geforce-rtx-5090-street-prices-in-eu-now-exceed/]`. I found no Slovak listing, no current RTX 5080 price and no used RTX 3090 price. A local GPU saves roughly $2 to $15 a month of Haiku on these levels (section 7), so **it does not pay for itself on token savings**. Buy it for privacy, offline use, vision and voice latency, or use what the PC already has `[inference]`.

## 7. Monthly budget

Unit costs, from verified list prices with my assumptions on token counts `[inference]`:

| Unit | Assumption | Cost |
|---|---|---|
| Haiku thin consult | 6K prefix, 300 in, 120 out. Warm $0.00015, cold $0.00084, half cold | $0.0005 |
| Sonnet mid consult | 15K prefix, 500 in, 300 out. Warm $0.0055, cold $0.0415, half cold | $0.0235 |
| Opus deep turn at today's prefix | Measured blend | $0.12 |
| Background call on Haiku | 2,000 in, 200 out | $0.0003 |
| Utility call on Haiku | 1,000 in, 150 out | $0.000175 |
| Heartbeat on Haiku | 3K cold write, 50 out | $0.0004 |
| Frame on Haiku | 1,296 tokens for 1000×1000 `[verified: https://platform.claude.com/docs/en/build-with-claude/vision]`, 100 out | $0.00018 |
| Frame on Sonnet | Same image, 200 out | $0.0046 |
| Autonomous run, small | About 40 Sonnet requests; computed $0.35, rounded up | $0.50 |
| Autonomous run, large | Longer, some Opus | $1.50 |
| Voice per connected minute | Planning number from section 5. Real range $0.009 to $0.13 by vendor and session length | $0.04 |

### Level 1: Pilot on this Mac

10 min talk a day, 30 consults a day (70% voice, 30% typed on plan), 16 heartbeats a day, 100 utility calls a day, 10 frames a day. Coding on plan.

| Item | Arithmetic | Monthly |
|---|---|---|
| Voice | 300 min × $0.04 | $12.00 |
| Haiku consults | 630 × $0.0005 | $0.31 |
| Utility | 3,000 × $0.000175 | $0.53 |
| Heartbeat | 480 × $0.0004 | $0.19 |
| Vision | 300 × $0.00018 | $0.05 |
| **Metered** | | **$13.08** |
| Max plan | | $100 |
| **Total** | | **about $113** |

The Claude share is $1.08, covered by credits. Only the voice vendor adds cash, about $12, or about $5 if mini holds up. Utility is shown on credits for simplicity, but until a local model exists it stays on the plan (section 9, B1 step 6). The logs ran 159 summaries in 23 hours, higher than the 100 a day assumed here.

### Level 2: Daily driver, PC on

60 min talk a day, 100 consults a day (70% Haiku, 25% Sonnet API, 5% Opus on plan), 200 background calls a day and utility on local, 100 frames a day (90% Haiku, 10% Sonnet), 2 autonomous runs a day.

| Item | Arithmetic | Monthly |
|---|---|---|
| Voice | 1,800 min × $0.04 | $72.00 |
| Video | 180 min × $0.002 | $0.36 |
| Haiku consults | 2,100 × $0.0005 | $1.04 |
| Sonnet consults | 750 × $0.0235 | $17.63 |
| Vision | 2,700 × $0.00018 + 300 × $0.0046 | $1.87 |
| Autonomous | 60 × $0.50 | $30.00 |
| **Metered** | | **$122.90** |
| Max plan | | $100 |
| PC power | 100 W extra × 730 h = 73 kWh × about €0.21 | about $17 |
| **Total** | | **about $240** |

Claude share is $50.53, inside the $100 credits. Cash above the plan is about $89. Without a local model, background adds about $2.50.

### Level 3: Full Jarvis, always on

3 h talk a day, 1 h of that with video, 300 consults a day (70/25/5, with Opus on API because much of it is machine-triggered), 1,000 background calls a day and most frames on local, 5 large autonomous runs a day.

| Item | Arithmetic | Monthly |
|---|---|---|
| Voice | 5,400 min × $0.04 | $216.00 |
| Video | 1,800 min × $0.002 | $3.60 |
| Haiku consults | 6,300 × $0.0005 | $3.12 |
| Sonnet consults | 2,250 × $0.0235 | $52.88 |
| Opus API | 450 × $0.12 | $54.00 |
| Vision (not local) | 2,700 × $0.00018 + 300 × $0.0046 | $1.87 |
| Autonomous | 150 × $1.50 | $225.00 |
| **Metered** | | **$556.47** |
| Less Max credits | | −$100 |
| Max plan | | $100 |
| PC power | 200 W × 730 h = 146 kWh × about €0.21 | about $34 |
| **Total** | | **about $590** |

At this level Ultra ($200, $200 credits) costs the same and doubles the weekly limit. Autonomous runs and voice are about 40% of the metered bill each, and they are the softest assumptions, so cap and measure both. Thinning the Opus prefix from 67K would cut the $54 substantially.

### Sensitivity

| Change | Level 2 | Level 3 |
|---|---|---|
| Voice on `gpt-realtime-2.1-mini` at $0.017 | −$41 | −$124 |
| Gemini 3.8 Live, short sessions only, $0.015 | −$45 | −$135 |
| Gemini 3.8 Live, 30-minute sessions, $0.13 | +$162 | +$486 |
| Voice on `gpt-live-1` at $0.05, before backend | +$18 | +$54 |
| Voice on `gpt-realtime-2.1` at $0.048 | +$14 | +$43 |
| No local GPU, background and frames on Haiku | +$2.50 | +$14 |
| Sonnet lane keeps a 67K prefix instead of 15K | about +$51 | about +$152 |

The last row: a half-cold turn on a 67K prefix costs about $0.091 versus $0.0235, a difference of $0.0676, times 750 and 2,250 turns. **Thinning the prompt beats any model or GPU choice.**

Not included: TTS or STT vendors if not local, integrations, one-off hardware, VAT. Electricity at about €0.21 per kWh is the Eurostat-based household figure for Slovakia in H2 2025 `[secondary, seen through search: euenergyprices.eu]`, so use Adam's bill.

## 8. Routing policy

### How routing works

OpenClaw routes by agent, binding, session, heartbeat, cron and subagent model, not by per-message classification. Agents have isolated workspaces, and auth profiles are per-agent `[verified: concepts/multi-agent.md]`. Talk has `talk.agentId` `[verified: nodes/talk.md]`. Subagents take `agents.defaults.subagents.model` `[verified: tools/subagents.md]`.

**So route by surface and trigger, then escalate by tool call.** Do not build a classifier for the MVP. OpenClaw's `decisionModel` role exists, but its ONNX and TypeSafe plugins are described as unpublished candidates, and neither appeared in `openclaw plugins list` on 2026.10.9 `[verified: concepts/decision-models.md; local command]`. Revisit it later for tool filtering.

### Policy table

| Task | Lane and model | Effort | Tools | Latency target | Escalates to |
|---|---|---|---|---|---|
| Wake | Local detector (voice track picks) | n/a | None | under 300 ms | Voice front |
| Intent | Implicit: realtime model answers or calls `consult` | n/a | `consult` only | n/a | Voice consult |
| Quick reply | Realtime model itself | Low | None | under 1 s | Voice consult |
| Voice tool question (time, calendar read, memory) | `voice` agent, Haiku 5.5 API, thin prefix | Thinking off or low | Small read-only allowlist | p50 under 2.5 s | Main |
| Voice request needing thought or action | Spoken acknowledgement, spawn to `main` on Opus 5.5 CLI, announce result | Medium | Full, with confirmations | Ack under 1 s | Opus high |
| Typed assistant (Telegram, app) | `main`, Opus 5.5 CLI | Medium | Full | Unimportant | Opus high, Fable on request |
| Deep reasoning | `main`, Opus 5.5 CLI | High | Full | Minutes | Fable 5.1 only if Adam says so |
| Coding | Claude Code via ACP on plan, Sonnet 5.5 subagents | Default | Sandbox | Minutes | Mac sandbox for iOS |
| Untrusted content reader (email, web, messages, EduPage) | `reader` agent, Haiku 5.5 API, or Sonnet 5.5 if it fails evals | Low | **None.** Returns structured summary | Seconds | Main decides actions |
| Unattended task | `worker` agent, Sonnet 5.5 API, with a task budget | Medium | Scoped per task | Minutes | Ask Adam |
| Vision, always-on | Local detector, no LLM (vision track picks) | n/a | None | Real time | Caption |
| Vision, caption | Local Gemma 4 on PC; Haiku 5.5 until then | Low | None | About 1 s | Sonnet |
| Vision, "look at this" | One frame to Sonnet 5.5, or to the realtime model through `describe_view`. Gemini video only in browser Talk | Low | Consult | Conversational | Opus |
| Background summaries, recaps, titles | `utilityModel`: local on PC, Haiku 5.5 until then | Off on API or local, lowest available on CLI | None | Seconds | None |
| Memory, Dreaming | Local on PC, Haiku 5.5 until then; Batch API if run directly | Low | Memory only | Overnight | Review queue |
| Heartbeat | Script first; Haiku 5.5 or local only on a change | Off | Read-only | Seconds | Message to Adam |
| Robot motor loops | **No LLM.** Deterministic local control; LLM sets goals only | n/a | Bounded commands | Real time | Robotics track |

Cost controls that go with this:

- Downscale frames to 1000 px or less before sending. Opus 5.5 and other 4.7+ models accept up to 2,576 px and 4,784 tokens automatically `[verified: vision doc]`.
- Heartbeat: add `lightContext: true` and `activeHours` `[verified: gateway/heartbeat.md]`. Adam must approve the schedule change.
- Give unattended runs `task_budget` (Opus 5.5, Sonnet 5.5 and Haiku 5.5, beta, advisory, minimum 20,000 tokens) where the runtime exposes it. It does not work on Claude Code surfaces, and it is a soft hint rather than a cap `[seen through a search summary of https://platform.claude.com/docs/en/build-with-claude/task-budgets]`. Whether OpenClaw exposes it is unchecked. The real cap is the credit balance and the workspace limit.
- Close voice sessions early. On token-billed voice, session length is the main cost lever (section 5).
- Turn off or relocate Activity recaps if they use meaningful plan share. That is the 2-to-1 finding.

### What stays on subscription and what moves

| Stays on Max | Moves to API credits | Moves to local (PC) |
|---|---|---|
| Typed `main` turns | Voice consults | `main` utility and recaps (interim on plan, as low as possible) |
| Deep reasoning | Unattended tasks | Heartbeat checks |
| Claude Code coding | Untrusted content reader | Simple captions |
| Fable on request | Heartbeat, until the PC is on | Dreaming, memory |

## 9. Implementation plan for later sessions

Keep evidence tiers apart: source check, config applied on a scratch profile, gateway accepted it, signed-in device test. Preview each config change and get a yes. Never add a schedule silently.

**B0. No spend, no key.** Done means each item is recorded in `status.md` or similar.

1. Adam on claude.ai: usage credits off or a low cap; model improvement setting as they want it. `~/.claude-jorah` is the same account as their main login, so no need to check that.
2. Read `/usage` under the Jorah login now and after one week. Record Attribution.
3. Preview and apply: `agents.defaults.embeddedAgent.cyberFailover.mode: "off"`, explicit `fallbacks: []` on **both `agents.defaults.model` and `agents.entries.main.model`**, explicit `utilityModel` with its own runtime. The `main` entry is the one that matters today, because it holds the live chain. Do this before adding any API key. Also check why the chain exists: it may have been written at Claude CLI sign-in, and `doctor` or `update` might rewrite it `[inference]`. Re-check after each upgrade.
4. Extend `switch-brain.sh status` with the checks in section 10.

**B1. API lane with a hard cap.**

1. Adam links a Console org to the plan (irreversible without support) and confirms promotional credits appear. No payment method, auto-reload off.
2. Create a `jorah` workspace with a spend limit of $100. Key created there. Adam pastes it at the prompt, never in chat.
3. On a scratch profile (`JORAH_SWITCH_PROFILE`), add a `voice` agent with its own `agentDir` and the key only in that agent's store. Pin `anthropic/claude-haiku-5-5` to `agentRuntime: openclaw` in `agents.entries.voice.models`.
4. **Must test:** `main` cannot reach the key, and `main`'s utility completions do not jump to HTTP. OpenClaw docs warn that a pinned CLI runtime with a configured provider credential moves the derived utility model to the HTTP route, billed to that credential `[verified: gateway/cli-backends.md]`. They also describe read-through from a shared auth store `[verified: providers/anthropic.md]`.
5. Add a `background` agent the same way and move the heartbeat to it. If any agent has a `heartbeat` block, only those agents run heartbeats `[verified: gateway/heartbeat.md]`.
6. Known gap: `main`'s own utility completions cannot reach an API key that is absent from its store. So until the PC runs a local model they stay on Haiku through CLI, or get reduced. To close the gap sooner, test a separate provider id with `api: "anthropic-messages"`, so the key is not under `anthropic` and `anthropic/*` rotation can never reach it `[docs-only: gateway/configuration-examples.md, shown for MiniMax]`. Check that this keeps prompt caching, thinking controls and cost tracking, because the `anthropic` plugin owns those `[inference]`. It is also the runner-up if per-agent isolation fails.
7. Update `switch-brain.sh`: its `setRuntime` currently rewrites `agents.entries.*` too, which would flip the `voice` agent, and `mixed` must become lane-aware.

**B2. Latency baseline.** The 20-prompt test from section 4. Write a small script that records time to first delta. Accept: numbers recorded with date and route. Spend under $0.10.

**B3. Thin `voice` agent.** Separate workspace, minimal bootstrap, read-only tool allowlist, thinking off, `fallbacks: []`, `talk.agentId: "voice"`. Accept: prefix under 8K tokens measured from usage, p50 consult under target, and a test that it cannot send messages or run exec.

**B4. Voice bench.** Adam creates vendor projects with prepaid or capped spend (section 10). Check `talk.catalog` for `gateway-relay` plus `agent-consult`. Set the Mac's local relay opt-in. Set the Gemini model explicitly. 20 minutes each on the same script, in 10-minute sessions: time to first audio, barge-in, whether speech continues during a consult, Slovak test, and real cost from vendor usage at both 2-minute and 10-minute session lengths. Requires macOS 26+ for relay and wake, which this Mac meets. Adam picks.

**B5. Reader and worker lanes.** With the security track. Accept: a prompt-injection test set where the reader has no tools and `main` does not execute injected instructions.

**B6. Local on PC.** Once PC specs are known: Ollama, chosen model, `utilityModel` local with explicit runtime, heartbeat local. Accept: a week with no Haiku spend for these and acceptable quality on a sample Adam reviews. Also run the tool-calling test, not just chat.

**B7. Budget view.** A daily digest from `openclaw gateway usage-cost` and vendor pages. Adam approves the schedule. Note `/status` estimated cost covers API-key models only `[verified: concepts/usage-tracking.md]`, and native CLI quota is not polled by OpenClaw `[verified: providers/anthropic.md]`. Never show zero for a missing source; show "unknown".

**Sketch of the target config. Not applied, not validated. Test on a scratch profile first.**

```json5
{
  agents: {
    defaults: {
      model: { primary: "anthropic/claude-opus-5-5", fallbacks: [] },   // main's own list must be cleared too, see entries
      utilityModel: "anthropic/claude-haiku-5-5",   // on CLI for now, later "ollama/gemma4:12b"
      embeddedAgent: { cyberFailover: { mode: "off" } },
    },
    entries: {
      main: {
        model: { primary: "anthropic/claude-opus-5-5", fallbacks: [] },   // today this holds a 10-step chain
      },
      voice: {
        model: { primary: "anthropic/claude-haiku-5-5", fallbacks: [] },
        models: { "anthropic/claude-haiku-5-5": { agentRuntime: { id: "openclaw" } } },
      },
      background: {
        model: { primary: "anthropic/claude-haiku-5-5", fallbacks: [] },
        models: { "anthropic/claude-haiku-5-5": { agentRuntime: { id: "openclaw" } } },
        heartbeat: { every: "1h", isolatedSession: true, lightContext: true,
                     activeHours: { start: "07:00", end: "23:00" } },
      },
    },
  },
  talk: {
    agentId: "voice",
    // Bench both. For Gemini use provider: "google", model: "gemini-3.8-live".
    // With no model set, Google falls back to gemini-3.1-flash-live-preview.
    realtime: { provider: "openai", model: "gpt-realtime-2.1-mini", mode: "realtime",
                transport: "gateway-relay", brain: "agent-consult" },
  },
}
```

The `agentDir`, workspace and tool policy for `voice` and `background` are in the multi-agent docs and were not worked out here. The heartbeat change is a schedule change, so preview it and get Adam's yes.

## 10. Spending cap and the rule against silent paid fallback

### The rule, for `workspace/AGENTS.md` and the docs

> A failed route reports the failure with its reason and reset time. Jorah never moves work onto a paid meter, a more expensive model or another vendor on its own. Changing a route needs Adam's explicit yes in that conversation, and it applies only to what Adam approved.
>
> A local model may answer read-only requests during an outage, and the answer must say it came from the local model.

### Caps

| Meter | Cap | Mechanism | Evidence |
|---|---|---|---|
| Anthropic API | $100 a month, phase 1 | Credits only, no purchased balance, no payment method, auto-reload off. Workspace limit as a second layer | `[verified: credits page; rate limits page]` |
| Claude plan overage | $0 | Usage credits off, or a small monthly limit | `[verified: https://support.claude.com/en/articles/12429409-manage-extra-usage-for-paid-claude-plans]` |
| Gemini, if used | $15 prepaid | Prepay balance with auto-reload off: at $0, keys stop with HTTP 402. Add a project spend cap as a second layer, but Google calls it experimental. Billing can lag about 10 minutes, and agent sessions can run past both, so overruns are possible | `[verified: https://aistudio.google.com/docs/billing]` |
| OpenAI | $10 prepaid | Prepaid balance, auto-recharge off: requests fail with 429 `credit_balance_exhausted`. Turn on the project hard limit too, which is opt-in. Enforcement lags slightly | `[verified: https://developers.openai.com/api/docs/guides/spend-limits; prepaid behavior seen through a search summary of help.openai.com]` |
| Total new cash, phase 1 | **$25 or less** | | |

Errors to treat as "stopped, tell Adam": a user-set Anthropic limit returns HTTP 400 `invalid_request_error`, a tier cap returns 429 with `enforced_spend_limit_reached` and no `retry-after`, exhausted credits return a credit-balance error `[verified: rate limits page; credits page]`. After a billing error OpenClaw disables the key for 10 minutes `[verified: concepts/model-failover.md]`, which `docs/switch-brain.md` already notes.

### Every silent path I found

| # | Path | Trigger | Guard | Evidence |
|---|---|---|---|---|
| 1 | Model fallback chain. **Live today:** `agents.entries.main.model.fallbacks` has 10 steps, including Fable | Provider failure, plan limit, timeout. Has already moved two runs to Haiku | `fallbacks: []` on `agents.entries.main`, defaults, other agents and cron `payload.fallbacks`. Defaults alone do not clear it. `models status` shows the defaults list, so check the entry itself | `[verified: config get; logs; concepts/model-failover.md]` |
| 2 | Auth rotation to an API key on the same provider | Rate limit or auth failure | Empty order for `main`; key absent from its store | `[verified: same; scripts/switch-brain.sh]` |
| 3 | Utility model jumps to HTTP once a credential exists | Adding a key | Explicit `utilityModel` with explicit runtime | `[verified: gateway/cli-backends.md]` |
| 4 | `ANTHROPIC_API_KEY` in the environment | Shell export | Claude Code prefers it over the plan. `status` cannot see the running gateway's env, so add a process-env check | `[verified: https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan; docs/switch-brain.md]` |
| 5 | Plan usage credits | Plan limit hit | Off or capped | `[verified: usage credits article]` |
| 6 | Console auto-reload | Balance low | Off | `[verified: credits page]` |
| 7 | GPT-Live OAuth falling back to a Platform key | OAuth failure | Do not configure a Platform key on that gateway if using OAuth | `[verified: nodes/talk.md]` |
| 8 | OpenAI cyber refusal escalates to Daybreak | Refusal, default `mode: "auto"` | `cyberFailover.mode: "off"` | `[verified: concepts/model-failover.md]` |
| 9 | Anthropic refusal fallback on API | Safety classifier | Accept but log; billed at the answering model | `[verified: providers/anthropic.md]` |
| 10 | Media tools cross-provider fallback | Image or video generation with several keys | Set `mediaModels` explicitly. Docs call the fallback fixed behavior, so test what can be disabled | `[verified: concepts/models.md]` |
| 11 | CLI runtime falling over to a non-CLI candidate | Only if a fallback is configured | Path 1 guard | `[verified: gateway/cli-backends.md]` |
| 12 | Fast mode | `consultFastMode`, Claude Code `/fast` | Leave unset; fast mode bills usage credits on the plan | `[verified: nodes/talk.md; https://code.claude.com/docs/en/costs]` |
| 13 | Realtime Talk falling back to native speech | Relay fails to start or drops repeatedly | Not a paid move, and the overlay says so. Native speech then runs turns on the Talk agent and may use Apple's network speech services, so it matters for privacy | `[verified: nodes/talk/macos-relay.md; nodes/talk.md]` |

`switch-brain.sh status` should check 1, 2, 3, 4, 7, 8, 10 and 12, and print `PROBLEM:` lines as it does now. It already prints `main`'s fallback count and lists non-Anthropic ones, but raises no `PROBLEM` for either, so any non-empty chain must become one. Items 5 and 6 are account settings it cannot see, so print them as reminders.

When the plan limit is hit, Jorah should say: "I've reached the plan limit, it resets at <time>. I can wait, or you can ask me to use the API for this." It reports the reset time only if it actually has one.

## 11. Decisions

| Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|
| Voice lane brain | Haiku 5.5 on API, thin agent | Fastest, $0.0005 a turn, covered by credits | `gpt-6-luna` at the same list price `[verified: OpenAI pricing]` | Haiku failing tool evals, then Sonnet 5.5 with `between_tools` | Under $2/mo |
| Typed and deep | Opus 5.5 on Max CLI, unchanged | $0.12 per turn at API prices, already paid for | Sonnet 5.5 on API | Anthropic ends plan access for this route | $100/mo plan |
| Unattended | Sonnet 5.5 on API credits | Fits terms, hard cap | Gemini 3.8 Flash, $0.75/$3.75 until 2026-12-31, then $1.50/$7.50 `[verified: Gemini pricing]` | Credits exhausted regularly | Under $100/mo |
| Coding | Claude Code on Max | Named product for this | Codex on a ChatGPT plan | Limits hit often, then Ultra | Included |
| Realtime voice | `gpt-realtime-2.1-mini`, after bench | Likely cheapest once context billing counts, documented relay route | Gemini 3.8 Live if Slovak, video or non-blocking consults matter. GPT-Live third | Bench results, ChatGPT Pro credits | $5 to $220/mo |
| Local server | Ollama | Simple, one user | llama.cpp plugin | Measured slowness | Free |
| Local model | Gemma 4 family, 26B at 24 GB | Tools, vision, sizes fit | Qwen3.6 27B | Own tool test | Free plus power |
| GPU | Use what the PC has, 24 GB recommended | Token savings do not justify buying, and 2026 prices make it worse | RTX 5090 only if voice stack goes local and prices fall | Privacy goals, PC specs | €0 to €5,000+ |
| Classifier | None for MVP | Surface routing is deterministic | ONNX `decisionModel` | Plugin ships, consult misroutes | Free |
| Routing isolation | Per-agent auth store | Key absent from `main` | Separate provider id, which also frees `main` utility from the plan | Isolation test fails, or recaps prove costly on the plan | Free |
| Plan tier | Stay on Max, and measure | Enough until measured otherwise, though the 5-hour limit was hit once on day 2 on a shared account | Ultra, which has no 5-hour limit once verified | API above $200 monthly, or the limit blocks real turns more than occasionally | $100/mo |
| Cap | $125 total in phase 1 ($100 credits, $25 cash) | Hard stops by construction | Higher with a yes | Real usage data | See section 10 |

## 12. What I could not confirm

- Direct API latency for Haiku, Sonnet and Opus from here. No key exists, and third-party numbers were unusable.
- Whether OpenClaw on the Claude CLI counts as allowed "ordinary, individual" use for always-on patterns. Sources conflict. Adam could ask Anthropic support.
- Token or hour limits on Max. Anthropic does not publish them.
- OpenAI audio tokens per minute: seen only through a search summary of the official guide, because the page returned 404 when opened. Whether audio caching behaves as modeled. Slovak support on OpenAI voice models. OpenAI's minimum age, which I did not check.
- Real Gemini Live cost per minute. The token model in section 5 follows Google's description, but the only real-world numbers are forum reports. Whether `gemini-3.8-live` has any cache discount: the staff reply about no caching was posted on a thread about the 3.1 preview.
- Whether a ChatGPT plan actually covers `gpt-live-1-codex` minutes, and OpenAI's own statement on OAuth in third-party tools. I only found OpenClaw's docs and blogs for that.
- Whether OpenClaw's Google relay works at runtime. The code declares session resumption and advertises `agent-consult`, but nobody has run it here.
- Haiku 5.5 tool-calling quality as a voice brain. Anthropic positions it for classification, routing, extraction and subagents `[verified: https://platform.claude.com/docs/en/models/haiku-5-5/overview]`. Needs a local eval.
- Primary sources for current GPU prices, Slovak household electricity in 2026, and Gemma 4 and Qwen3.6 licenses. All are secondary or search-only here.
- How much of the 5-hour limit Jorah used on 2026-11-02, compared with Adam's other work on the same account. Also the plan draw of the 159 utility runs.
- Local model speed on any NVIDIA card with Jorah's real prompts.

## 13. Questions only Adam can answer

1. `~/.claude-jorah` is the same Claude account as the main login, so a plan enforcement problem or a used-up limit hits everything. Does Adam want a separate paid account for Jorah, or is the shared risk acceptable?
2. OK to link a Console org to the Max plan? It cannot be changed without support.
3. Does Adam have a ChatGPT plan, and at what tier? Pro includes API credits that cover Realtime and GPT-Live, which could make the OpenAI voice lane cost no extra cash.
4. Phase 1 cash cap: is $25 a month on top of the plan acceptable?
5. Is model improvement off on the Claude account? Should it be, given Jorah will read other people's messages?
6. Is Adam 18 or older? Gemini API terms and Anthropic's Consumer Terms both require it `[verified: https://aistudio.google.com/docs/terms; https://www.anthropic.com/legal/consumer-terms]`, and the EduPage goal raises the question. If not, the plan account and the Gemini lane both have a problem to resolve first.
7. PC GPU model, VRAM and RAM.
8. Is English-only voice enough, or does Slovak matter? This now decides between mini and Gemini.
9. Should Activity recaps stay on? They are the largest number of plan calls today.
10. Ask Anthropic support about the always-on pattern, or just keep unattended work off the plan? I recommend keeping it off either way.

## Sources

Anthropic:

- https://platform.claude.com/docs/en/about-claude/pricing
- https://platform.claude.com/docs/en/about-claude/models/overview
- https://platform.claude.com/docs/en/models/haiku-5-5/overview
- https://platform.claude.com/docs/en/api/rate-limits
- https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers
- https://platform.claude.com/docs/en/build-with-claude/fast-mode
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://platform.claude.com/docs/en/build-with-claude/vision
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account
- https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan
- https://support.claude.com/en/articles/11049741-what-is-the-max-plan
- https://support.claude.com/en/articles/12429409-manage-extra-usage-for-paid-claude-plans
- https://support.claude.com/en/articles/17728952
- https://www.anthropic.com/legal/commercial-terms
- https://www.anthropic.com/legal/credit-terms
- https://platform.claude.com/docs/en/build-with-claude/thinking
- https://code.claude.com/docs/en/legal-and-compliance
- https://code.claude.com/docs/en/costs
- https://www.anthropic.com/legal/consumer-terms
- https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data
- https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data

OpenAI and Google:

- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/models/gpt-live-1
- https://developers.openai.com/api/docs/models/gpt-realtime-2.1
- https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini
- https://developers.openai.com/api/docs/guides/chatgpt-api-credits
- https://developers.openai.com/api/docs/guides/spend-limits
- https://aistudio.google.com/docs/pricing
- https://aistudio.google.com/docs/live-api
- https://aistudio.google.com/docs/live-api/capabilities
- https://aistudio.google.com/docs/live-api/best-practices
- https://aistudio.google.com/docs/live-api/session-management
- https://aistudio.google.com/docs/billing
- https://aistudio.google.com/docs/terms
- https://blog.google/innovation-and-ai/technology/developers-tools/more-control-over-gemini-api-costs/

Local models:

- https://ollama.com/library/gemma4
- https://ollama.com/library/qwen3.6

Secondary, lower trust:

- https://techcrunch.com/2026/04/04/anthropic-says-claude-code-subscribers-will-need-to-pay-extra-for-openclaw-support/
- https://discuss.ai.google.dev/t/gemini-live-api-caching/174701
- https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248
- https://discuss.ai.google.dev/t/gemini-3-8-live-missing-billable-token-details-and-pre-generation-spending-bounds/188765
- https://www.guru3d.com/story/geforce-rtx-5090-street-prices-in-eu-now-exceed/
- https://euenergyprices.eu/en/electricity/sk
- https://windowsreport.com/anthropic-renames-claude-max-5x-and-20x-plans-removes-ultras-5-hour-limit/
- https://artificialanalysis.ai/models/claude-haiku-5-5
- https://artificialanalysis.ai/models/claude-sonnet-5-5
- https://pasqualepillitteri.it/en/news/15720/openai-gpt-live-1-api-voice
- https://www.promptquorum.com/power-local-llm/best-local-models-tool-calling-2026
- https://omlx.ai/benchmarks/eako8p23
- https://omlx.ai/benchmarks?page=8
- https://computingforgeeks.com/ollama-vs-vllm-vs-llama-cpp/
- https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/
- https://urandom.io/blog/2026-04-05-gemma-4-apache-license-matters-more-than-benchmarks
- https://www.pcgamesn.com/nvidia/rtx-5000-europe-price-cut

OpenClaw bundled docs (2026.10.9, under `/opt/homebrew/lib/node_modules/openclaw/docs`): `concepts/model-failover.md`, `concepts/models.md`, `concepts/decision-models.md`, `concepts/multi-agent.md`, `concepts/usage-tracking.md`, `gateway/cli-backends.md`, `gateway/local-models.md`, `gateway/heartbeat.md`, `gateway/configuration-examples.md`, `nodes/talk.md`, `nodes/talk/macos-relay.md`, `nodes/talk/realtime-sessions.md`, `nodes/voicewake.md`, `providers/anthropic.md`, `providers/google.md`, `providers/openai/voice-and-speech.md`, `providers/openai/coverage-and-cost.md`, `providers/ollama/recipes.md`, `providers/vllm.md`, `tools/subagents.md`.

Repo: `scripts/switch-brain.sh`, `docs/switch-brain.md`.

## Verification

Independent check, 2026-11-02. I tried to refute the claims a plan would lean on by opening primary sources, reading the bundled docs and OpenClaw's installed code, and re-deriving the local measurements. Nothing was installed, configured or sent, and the gateway was not touched. Log and transcript reads used timing, usage and error fields only, and account ids were compared without being printed.

### Does the recommendation still hold?

Mostly, with one changed pick:

- **Changed:** the realtime voice pick moved from Gemini 3.8 Live to `gpt-realtime-2.1-mini` as the candidate to beat. Gemini is the runner-up, and it becomes the pick if Slovak, continuous video or non-blocking consults matter. Its "cheapest" argument failed once Google's token billing was applied.
- **Changed:** budgets rise from about $105, $190 and $445 to about $113, $240 and $590, because voice is now planned at $0.04 per connected minute instead of $0.0135.
- **More urgent:** clear `main`'s fallback chain before any API key exists. The silent-fallback rule is not just preventive, because the chain has already fired.
- **Holds:** lanes chosen by trigger, thin Haiku consults on API credits, Opus on the plan for typed work, unattended work off the plan, Ollama, no GPU purchase, no classifier, and the $25 phase 1 cash cap.

### Claims checked

| # | Claim | Result | Evidence |
|---|---|---|---|
| 1 | Gemini Live costs a flat $0.0135 per connected minute, cheapest with video | **Wrong.** Token-billed, full context per turn. Now $0.015 to $0.13 by session length | Best-practices page, pricing page, forum threads |
| 2 | `main` has no fallbacks | **Misleading.** A 10-step chain sits on `agents.entries.main`; `fallbacks: []` on defaults does not clear it. It has fired twice for real | `config get`, logs, `agent-scope` code |
| 3 | Gemini's session cap is lifted by resumption; OpenClaw support unknown | **Wrong on the mechanism.** Compression lifts it. OpenClaw enables both by default in code | Session-management page, `realtime-voice-provider.js` |
| 4 | Config sketch selects Gemini 3.8 Live | **Wrong.** With no model set, code defaults to `gemini-3.1-flash-live-preview`, which has no non-blocking calls | Code, capabilities page |
| 5 | Macs only need the config and catalog check | **Incomplete.** A local opt-in is also required, off by default | `nodes/talk/macos-relay.md` |
| 6 | Whether `talk.catalog` advertises relay and consult for Google | **Answered at source level:** yes. Runtime still open | `handlers-B5Rt4cMl.mjs` |
| 7 | OpenAI tokens per minute unconfirmed | **Improved, not closed.** 1 per 100 ms and 1 per 50 ms, through a search summary only | Search of the official guide. The page returned 404 |
| 8 | OpenAI hard limit unconfirmed | **Answered:** opt-in project and organization hard limits | Spend-limits guide |
| 9 | Gemini cap is a project spend cap | **Weaker than stated:** experimental. Prepay with auto-reload off is the better first control | Billing page |
| 10 | Is `~/.claude-jorah` the same account? | **Answered:** yes | Local comparison |
| 11 | "Enough until measured" on Max | **New evidence:** 5-hour limit hit at 18:53 on day 2, on a shared account | Logs |
| 12 | Anthropic API training position unknown | **Answered:** no training on customer content | Commercial Terms |
| 13 | Consumer Claude age limit unknown | **Answered:** 18 | Consumer Terms section 2 |
| 14 | No current GPU prices | **Updated:** reports above €5,000 for RTX 5090 in Germany | Secondary only |
| 15 | Electricity at €0.20 unchecked | **Roughly right:** about €0.21 for H2 2025 | Secondary only |
| 16 | Thinking off on Haiku | **True on API only;** Claude Code cannot turn it off | Thinking doc, costs doc |
| 17 | `task_budget` source was a cached skill reference | **Holds,** plus: 20,000-token minimum, not on Claude Code surfaces | Search of the official doc |
| 18 | Token table and $0.12 per turn | **Numbers reproduce.** Delegated work is small: $0.11 for chat. But 159 utility runs are absent from the table | Local recomputation |
| 19 | Turn timing table | **Reproduces** within the ranges now shown | Local recomputation by trace id |
| 20 | Ultra details were press-only | **Now primary,** except the date | Help Center article |

### Confirmed unchanged

- All Anthropic prices, the Haiku 100K rule, batch, fast mode, web search and fetch, `inference_geo`, and regional premiums (pricing page, fast-mode doc).
- Model ids, latency labels, default effort, context and output limits (models overview).
- $100 credits and all credit mechanics, including what they do not cover (credits page). Tier caps, 4,000 RPM, and spend-limit errors (rate limits page).
- Max at $100 with 5× Pro and a separate Fable limit. Shared limits and `ANTHROPIC_API_KEY` precedence. The first draft cited the wrong article for the latter, now fixed.
- Terms facts 1 to 5 (Consumer Terms, support articles, legal page, TechCrunch). The conflict between them is real, and I could not resolve it either.
- 5-minute cache default. 1,296 tokens for a 1000×1000 image, and the 2,576 px and 4,784 token limit on 4.7+ models.
- Slovak listed, non-blocking calls on `gemini-3.8-live`, 1 frame per second, no training on paid tier, 18+ and the EEA paid rule. Gemini 3.8 Flash and `gpt-6-luna` prices.
- OpenAI realtime prices. `gpt-live-1` has no vision and is billed at $0.05 per minute. Mini takes images.
- Ollama sizes for Gemma 4 and Qwen3.6. oMLX 27B on M1 Max.
- OpenClaw claims: `decisionModel` plugins are unpublished and absent from `plugins list`; heartbeat block rule; 10-minute billing disable; WSL2 trap; Tool Search on Ollama; no hosted safety filters on local models; GPT-Live OAuth-first with Platform fallback; 700 ms silence default; whole-reply speech on native Talk.
- Versions: OpenClaw 2026.10.9, Claude Code 2.1.300, Ollama present, `llama-server` absent.

### Marked or left uncertain

- `[unverified]`: oMLX numbers for Qwen3.6 35B.
- Search-only or secondary: OpenAI audio token rates, Gemini default compression trigger, the Live caching statement, GPU prices, electricity, Qwen and Gemma licenses, the 0.8 s GPT-Live claim, and the tool-calling test.
- Forum posters' staff status was only partly shown on the pages I read. Google's own best-practices page is the basis for the billing correction, not the forum.
- Not re-checked: `computingforgeeks` and `insiderllm` server comparisons, `promptquorum` tool test, Artificial Analysis figures, and the data-retention article for consumer plans. None drives a decision here.
- Evidence tier: everything above is a source, doc or log check. No voice session, API call, relay or local model was run.
