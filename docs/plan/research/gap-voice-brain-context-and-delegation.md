# Gap: one Jorah across `voice` and `main`

Date: 2026-11-02. Research only. No key, plugin, agent, config or gateway was touched, and nothing was run with real audio.

Labels: `[source: file]` read in OpenClaw 2026.10.9's shipped `dist/`, not run. `[docs-only: path]` the bundled docs say so, not run. `[verified: URL]` read directly this session. `[issue: #n]` an upstream report, read through `gh`; reports are other people's evidence, not mine. `[measured: brain.md]` another track's measurement on this Mac. `[track: file]` another track's finding, not re-checked. `[inference]` my reasoning. Bundled paths are relative to `/opt/homebrew/lib/node_modules/openclaw/`.

## Limits of this check

- **Evidence tier for the whole file: source and docs only.** There is no install, launch or device evidence here. Section 8 lists what would produce it.
- The shared web search budget ran out, so I used `gh` against the OpenClaw repo and opened known URLs only.
- **No roadmap file exists on disk** under `docs/plan/`, so I used the assignment's description of M2, M3 and section 14. M-numbers may need fitting to the final text.
- All latency for the Haiku API lane is an estimate. No API key exists yet, so nobody has measured it [track: brain.md].

## 1. Answer

**Pick: a separate `voice` agent plus a small typed plugin, `jorah-bridge`, with `main` as the only writer of memory and skills.** Facts move by two one-way paths: a digest from `main` to `voice`, and a reviewed inbox from `voice` to `main`.

- **Which agent answers a consult?** Always `voice` (Haiku 5.5 API, thin). It answers by itself only for time, timers, job status, note capture and a small public-class notes file. Everything needing Adam's memory, reasoning or action goes one hop to `main` through `ask_main`.
- **How does a job reach `main` and workers?** `ask_main` for answers, `start_job` for work. The plugin starts a turn on a dedicated `main` session (`agent:main:voice-bridge`, or `agent:main:voice-job-<id>`). `main` spawns workers as it does today.
- **How does the result get spoken in the same call?** Only by holding the consult's tool call open, because OpenClaw 2026.10.9 has no way to push text into a realtime call on the tool-call path (section 2, finding 5). So `ask_main` holds for up to 25 s and returns inline. Longer work becomes a job, Jorah says so aloud, and the result goes to the screen or Telegram, with spoken status on request.
- **Who writes the digest?** A plugin service calls a tool-free completion on the `background` agent (Haiku 5.5 API now, local on the PC later). It refreshes when `main`'s memory files change, not on a clock. Adam previews the first one and approves the automation.
- **What does it cost in latency?** Estimated p50 about 6 s and p90 about 16 s for voice to `main` and back, against about 3.8 s and 13 s if voice ran directly on `main`. A truthful acknowledgement still starts in under 1 s.

**This changes a promise.** "One thread" is false with a separate agent. The honest wording is **one Jorah, two transcripts, shared facts**. Section 4.6 says what Adam actually experiences.

## 2. What I found

1. **`sessions_send` needs a spoken "yes" on the pinned version.** `isMutatingToolCall` lists `sessions_send` and `sessions_spawn`, plus any tool whose name contains `send`, starts with `message_`, or ends in `_actions` [source: `dist/tool-mutation-BTW6eoAN.mjs`]. `requiresHighImpactVoiceConfirmation` applies to anything mutating except `write`, `edit`, `apply_patch` and the goal tools, and binds the yes to the exact arguments for 2 minutes [source: `dist/agent-tools.before-tool-call-CQkX3nOj.mjs`]. So send-only delegation, as `security.md` drew it, asks for a spoken yes on every ask, including read-only questions. Upstream confirms this for `sessions_spawn` on 2026.9.8 and reports it for `sessions_send` on 2026.10.9 [issue: #166156](https://github.com/openclaw/openclaw/issues/166156).

2. **That gate is about to disappear.** PR #159697 removed it from main on 2026-10-11 [verified: https://github.com/openclaw/openclaw/pull/159697]. Commit `f4f48684` is not an ancestor of tag `v2026.10.9` (compare: diverged) but is an ancestor of `v2026.10.10-beta.5` (compare: behind by 4,022) [verified: GitHub compare API]. The beta docs say Talk uses the same permissions as text and that saying "yes" does not grant anything [verified: `docs/nodes/talk/realtime-sessions.md` at `v2026.10.10-beta.5`]. So the design must hold both with and without the gate. No stable 2026.10.10 was listed when I checked.

3. **Send-only gives a reply and nothing else.** It grants no list, history, search, status, session control or watch [docs-only: `gateway/config-tools/sessions-and-subagents.md`, `concepts/session-state.md`]. A waited send returns the reply inline. If the wait expires, the reply arrives later as a new inter-session turn in the requester's session [docs-only: `concepts/session-tool.md`]. Nothing I read speaks such a turn into a call.

4. **Inter-session input is marked as not from the user** (`isUser=false`), and the docs warn that send-only does not stop a privileged target from acting or disclosing [docs-only: `concepts/session-tool.md`, `gateway/security/trust-model.md`]. The spoken gate binds only to the voice run. A `main` run started by `voice` is not voice-bound [source: `resolveClientVoiceRunBinding`, inference from the run id]. So the laundering risk is real whichever option is picked, and `main`'s own guard must carry it.

5. **There is no push into a call on the tool-call path.** The `talk.*` RPCs are `catalog`, `config`, `speak`, `client.*`, `session.create/appendAudio/cancelOutput/acknowledgeMark/submitToolResult/steer/close` and voice settings [source: `dist/handlers-B5Rt4cMl.mjs`]. `bridge.sendUserMessage` exists but is reached only by run control and forced consults. `submitToolResult` needs a pending provider call. A yielded consult returns "I started that work and will share the result when it is ready" and ends there on the tool-call path [source: `dist/realtime-session-harness-76VKE8_t.mjs`]. The one real later-speech path, `requesterFinal.append`, is wired only for GPT-Live native delegation after `sessions_yield` [source: `dist/realtime-quicksilver-delegation-controller-DJzRMSPy.mjs`, `dist/session-followup-completion-dNrbgyTC.mjs`]. `gpt-realtime-2.1-mini`, the current pick, does not use it.

6. **Holding the tool call open is a shipped path.** The relay submits a `working` result with `willContinue`, then a final result, for OpenAI GA and for Google models with async function calling [source: `submitRealtimeAgentConsultWorkingResponse` in `handlers-B5Rt4cMl.mjs`; `dist/extensions/openai/capability-catalog.js`; `dist/extensions/google/realtime-voice-provider.js`]. OpenAI's conversations guide does not describe late outputs at all, so how reliably the provider speaks a late one is unconfirmed [verified: https://developers.openai.com/api/docs/guides/realtime-conversations].

7. **A held consult blocks the next one.** Runs serialize on a session-key lane [docs-only: `concepts/queue.md`]. So while a consult waits on `main`, a second consult in that call queues. Run control still works: status and cancel act on the active run, but steering only lands at the next boundary, meaning after the tool returns [docs-only: `concepts/session-tool.md`, `nodes/talk/session-ownership.md`].

8. **Claude CLI turns do not appear to take same-turn steering.** The steering docs name the OpenClaw runtime and Codex, and say a runtime that cannot steer waits for the run to finish [docs-only: `concepts/queue-steering.md`]. A grep of the CLI executor found no steering hook [source: `dist/execute.runtime-DJQsoxvu.mjs`, grep only]. So "steer" against `main` on Opus means a follow-up turn, which then steers the worker.

9. **Memory and learning are per agent.** `memory_search` covers the selected agent's corpus, and shared Markdown belongs in `memory.search.extraPaths` [docs-only: `concepts/multi-agent.md`]. Learned skills belong to one agent [docs-only: `tools/skill-workshop.md`]. A live report shows Active Memory produces no log lines on Talk consults and that the voice model skips consults for memory questions even when told not to [issue: #183740](https://github.com/openclaw/openclaw/issues/183740).

10. **Today's Memory Wiki config would leak `main`'s memory to `voice`.** The jorah profile has `vaultMode: bridge`, `vault.scope: global`, and indexes the memory root, daily notes and dream reports [verified: `openclaw --profile jorah config get plugins.entries.memory-wiki.config`]. In global scope every agent shares that vault, and the wiki supplement reaches `memory_search` and `memory_get` [docs-only: `plugins/memory-wiki.md`]. Pages have no per-audience control. So `wiki_search`, or `memory_search` with a wiki corpus, on `voice` would read compiled private memory [inference from those docs, not run].

11. **Background learning would run on `voice`.** Reviews do not run on the Claude CLI runtime, but they do on the embedded runner [docs-only: `tools/self-learning.md`; track: current state]. A `voice` agent on the API would fork room-audio conversations into its own private skill store. Turns where tool policy hides `skill_workshop` do not count [docs-only: same], so denying that tool fixes it.

12. **What a user-installed plugin can do.** `api.runtime.gateway.request` is rejected for arbitrary external plugins [docs-only: `plugins/sdk-runtime/gateway-and-nodes.md`]. `api.runtime.subagent.run`, `waitForRun`, `getSessionMessages`, `complete` and `deleteSession` are available, and `run` dispatches the normal `agent` method to a session key checked only for locked or reserved ownership [source: `dist/server-plugins-CmWlaULD.mjs`, `dist/registry-runtime-session-ownership-ClnyynQF.mjs`]. Its synthetic client defaults to `operator.write`, not admin [source: `dist/server-plugin-in-process-dispatch-CHKjkAiH.mjs`], so `senderIsOwner` should be false and the owner-only tools (`nodes`, `computer`, `screen`, `terminal`, `conversations_*`, `sessions`, `openclaw`) should be withheld from that turn [source: `dist/dangerous-tools-7P77gGzs.mjs`, `dist/agent-turn-service-DndzLNDt.mjs`]. A good default, not yet run.

13. **Memory audience is a real risk for the bridge.** A root session with no durable chat type gets no audience, and a non-owner direct session gets `conversation`, not `owner-private` [source: `dist/memory-audience-B18hFdi8.mjs`]. Whether builtin `memory_search` then still sees `MEMORY.md` on a plugin-started `main` turn is **not confirmed**. If it does not, `ask_main` cannot remember, and that is a stop-the-line result (spike S2).

14. **Consults are costly on a large prompt.** Each consult can rewrite the prompt cache, dropping reads from about 123K to 11K tokens in one report, and voice consults were about 57% of that agent's model cost [issue: #179236](https://github.com/openclaw/openclaw/issues/179236). Consults also never apply `session.reset`, so a voice session can grow without limit [issue: #185942](https://github.com/openclaw/openclaw/issues/185942). Both favour a thin agent.

15. **Consult thinking defaults to high** on the embedded consult path when `talk.consultThinkingLevel` is unset [source: `consultRealtimeVoiceAgent`]. `brain.md`'s thin lane must set it.

## 3. The four options

| | A. Send-only with reply path | **B. Typed plugin tools (pick)** | C. Shared Memory Wiki | D. One agent with a guard |
|---|---|---|---|---|
| Shape | `voice` calls `sessions_send` to `main` and waits | `voice` calls `ask_main`, `start_job`, `job_*`, `note_for_main` | `voice` reads a shared vault, no call to `main` | `talk.agentId: main`, hook blocks risky tools on voice runs |
| Consult answered by | Haiku, then `main` | Haiku, then `main` | Haiku only | Opus on the plan |
| Result in same call | Inline if the wait holds; a late reply is lost to speech | Inline up to the cap; a job otherwise | Yes, but only for what is in the wiki | Yes, natively |
| Status, steer, cancel on `main`'s work | **None.** Send-only forbids them | Typed, via job records. Cancel needs spike S4 | Not applicable | Native on the run. Steer limited by finding 8 |
| 2026.10.9 spoken gate | **Blocks every ask** | Does not apply, by tool name [source] | Not applicable | Applies to risky tools |
| After 2026.10.10 | Works, still with no job control | Same as today | Same | Gate gone, so the hook is the only barrier |
| Facts `main` to `voice` | No | Digest and `ask_main` | Yes, too many: all of `main`'s compiled memory | Same memory |
| Corrections `voice` to `main` | Only as untyped text | Typed inbox, reviewed | `wiki_apply` from room audio, unreviewed | Direct write, from room audio |
| One thread | No | No, summaries instead | No | **Yes, if the same session key** |
| Room audio reaches the agent holding all memory and outward tools | Indirectly | Indirectly, through typed input and a tainted session | No | **Directly** |
| Bypass risk | Prompt-level trust in `main` | Plugin runs in-process, so it needs review | Page-level privacy absent | Single hook; hook firing on `claude-cli` is unproven |
| Plan or API draw | Plan on each ask | Plan on each ask, Haiku around it | API only | Plan on every consult, with a 67K prefix and the cache rewrite of finding 14 |
| Latency, memory question | About 6 s plus a yes | **About 6 s** | About 2.5 s, public facts only | About 3.8 s |
| Effort | Config only | 2 to 3 days | 1 day, then a privacy rebuild | 1 day plus guard tests |

**Why B.** A fails on control: M2 needs status, steer and cancel, and send-only forbids exactly those even once the gate goes. C cannot do work or take corrections safely and would hand `voice` everything. D is the honest runner-up: it is faster, simpler and the only true one-thread design, but it puts a TV's "Hey Jorah" directly into the agent that holds all memory and outward tools, and spends plan quota on a 67K prefix for every spoken question. Jorah already hit the 5-hour limit on day 2 [measured: brain.md].

**What would change the pick to D.** All of: the guard hook is proven to fire on `claude-cli` (`growth.md` S13), consult cost on the plan is tolerable on a week of real use, and Adam says one literal thread matters more than the extra barrier. Runner-up cost: about 1 day. Adam's call if they want it; I would not choose it first.

## 4. The design

### 4.1 Who answers what

| Request | Answered by | Route | Target |
|---|---|---|---|
| Greeting, repair, "what did you say" | Realtime model | No consult | Under 1 s |
| Time, timer, "is the job done?", "note that" | `voice` Haiku | Consult, one or two passes | p50 under 2.5 s [track: brain.md] |
| Curated public notes | `voice` Haiku | `memory_search` on its own corpus only | Same |
| Adam's memory, decisions, reasoning | `main` | `ask_main` | p50 about 6 s |
| Public web question | `reader-web` | `web_answer` (M3) | p50 about 6 to 9 s |
| Web question needing Adam's context | `main`, then `reader-web` | `ask_main` | p50 about 13 s |
| Anything taking work | `main` and workers | `start_job`, receipt spoken at once | Result on screen or Telegram |
| Private class: mail, calendar content, school | Reader lane, to a card | `private_show` [track: gap-private-data-through-realtime-providers.md] | Pointer spoken only |

Keep `realtime.consultRouting: provider-direct` as `voice.md` chose, but test it. Issue #183740 shows instructions alone do not stop guessing, so the wake-word test must score invented memory answers. If it finds any, flip to `force-agent-consult`.

### 4.2 Plugin tools on `voice`

| Tool | Does | Returns |
|---|---|---|
| `ask_main` | Starts a turn on `agent:main:voice-bridge`, waits up to 25 s | `{status: "answer", spoken}`, or `{status: "running", jobId}` when the cap is hit |
| `start_job` | Starts a turn on `agent:main:voice-job-<id>`, returns at once. Also posts a Telegram line with a Cancel action, so a job started by a TV is visible | `{jobId}` |
| `job_status` | Reads the job record and `waitForRun` state. No model call to invent progress | `{state, lastEventAt}` |
| `job_steer` | Sends a follow-up turn to the job's session | `{queued: true}` |
| `job_cancel` | Cancels, and reports `cancelled` only after the run reports a terminal state | `{state}` |
| `note_for_main` | Appends to the voice inbox with the exact quote and voice session id | `{noted: true}` |
| `web_answer` (M3) | Runs one `reader-web` turn, keeps typed fields only | `{answer, sources}`, capped |

Rules, enforced in the plugin rather than prompts:

- **Names stay clear of the classifier.** No tool name may contain `send`, start with `message_` or end in `_actions`, or the 2026.10.9 gate fires [source].
- **This avoids the spoken yes on purpose.** I am flagging that plainly. OpenClaw is removing that gate anyway, and `security.md` says a spoken yes is not authority. The protection moves to `main`'s guard below. The security track must sign this off.
- **`ask_main` returns only `spoken`.** The bridging turn has `extraSystemPrompt` telling `main` to answer in under about 60 words and to route private class to a card. From M4 the plugin also replaces `spoken` with a neutral pointer if that run touched a reader or connector tool, recorded through `after_tool_call` on the session key. This extends the sibling gap's "pointer only" rule to `main`'s replies, and its canary test must cover it. A memory entry with a third-party name is the hard case, and only the canary can prove it.
- **`cancel` propagates.** The tool's abort signal triggers the same cancel path as `job_cancel`.
- **Records survive restart as unknown.** After a Gateway restart a job is reported as "I lost track of that", never as done. In-flight reply observers do not survive [docs-only: `concepts/session-tool.md`].

### 4.3 Job started by voice: the sequence

```text
Adam: "Jorah, edit the raw video into a draft."
  realtime model -> openclaw_agent_consult          working result, "Let me check"   (under 1 s)
  voice (Haiku)  -> start_job {title, brief}        session agent:main:voice-job-7
  plugin         -> subagent.run(deliver: false)    non-owner turn, marked voice-origin
  voice          -> spoken: "Started. I'll message you when it's ready."

  main (Opus CLI) -> sessions_spawn builder or ACP  guard: tainted session
  main            -> sessions_yield                 main's turn ends; worker runs

Adam: "How's it going?"   consult -> job_status     state from records, spoken
Adam: "Make it 1080p."    consult -> job_steer      follow-up main turn, which steers the worker
Adam: "Never mind."       consult -> job_cancel     says cancelled only on a terminal state

Worker finishes -> main's successor turn -> plugin sees completion
  call open or not: Telegram or app card. Spoken on the next consult if the call is still open.
```

For `ask_main`, the same path applies but the consult stays open and the answer is spoken from the tool result. If 25 s passes, the plugin converts it to a job without cancelling `main`.

**Why 25 s.** `voice.md` said 15 s, but voice-to-`main` p90 is about 16 s, so a 15 s cap would convert one answer in ten. 25 s catches p90 at the price of a silent wait. Because finding 7 means a held consult blocks others, it must not grow further. Tune it on the bench [inference].

**Silence during a hold.** `voice.md`'s "one progress line per 8 s" cannot be built on V1: the built-in prompt says one acknowledgement, then wait [track: ux.md; issue: #165682](https://github.com/openclaw/openclaw/issues/165682). The overlay shows Thinking, and status works on request.

**Later in the call.** On the tool-call path a finished job cannot interrupt. If the call is still open, the first consult after completion gets a one-line note through a `before_prompt_build` hook. The fix for true push is V2's own realtime provider, since it owns the bridge [track: voice.md section 9], or an upstream RPC. If the bake-off picks GPT-Live instead, `requesterFinal` allows real later speech, and this section should be revisited.

### 4.4 Guard on `main`

Every session whose key starts with `agent:main:voice-` is tainted from birth, under `security.md`'s "taint follows the session" rule. The key is host-set by the plugin, so a model cannot change it.

| Action in that session | Result | `security.md` row |
|---|---|---|
| Memory reads and other read-only tools | Allowed; reader output treated as data | 2, 6 |
| `message` to Adam only | Allowed | 11 |
| Spawn listed workers | Allowed. Workers inherit no outward rights | Delegation |
| Write memory or skill | **T3 with diff**, or blocked | 4 |
| Anything outward, calendar, robot | **T2 or T3 on the phone**. Voice cannot approve | 12 to 14, 40 |
| Spend above the job budget | Blocked | `brain.md` section 10 |

Do not run voice work in `agent:main:main`. It would queue behind Telegram turns and taint Adam's primary session, so every later typed action would need a tap.

### 4.5 Facts and corrections, both ways

| Direction | What | Path | Latency | Writer |
|---|---|---|---|---|
| `main` to `voice`, always | Stable public-class facts | Digest in `voice`'s `USER.md`, read at call start [source: `resolveTalkRealtimeProviderInstructions`] | Next call | Plugin, from `background` |
| `main` to `voice`, on demand | Anything current | `ask_main` | About 6 s | None |
| Telegram fact to `voice` | "My dentist moved to Friday" typed to `main` | `main` saves it, the file change triggers a refresh, next call has it if public class. Active call uses `ask_main` | Under about 10 min | `main`, then plugin |
| Spoken correction, in this call | "Actually, it's Tuesday" | Stays in the voice session's context | Immediate | Provider and session |
| Spoken fact to `main` | "Remember that the arm uses M3 screws" | `note_for_main`, end-of-call card on the phone with the exact quote: Keep, Change, Forget. On Keep, `main` writes it | Tap | **`main` only** |
| Spoken procedure correction | "Always export at 1080p" | Same inbox, marked `procedure`. On Keep, `main` patches through `skill_workshop` in a clean turn | Tap | **`main` only** |
| Call record to `main` | What was said and decided | Plugin writes a `background` summary to `shared/voice-calls/<date>.md`, indexed for `main` only via per-agent `extraPaths`, so a typed "what did I ask you earlier?" finds it | At call end | Plugin |

**Why a tap for spoken facts.** Room audio is untrusted, and a TV should not be able to rewrite Jorah's beliefs. `security.md` row 4 already says tainted writes need T3. One batched card per call keeps this tolerable and fits Adam's rule to preview changes to data. The cost is friction: a spoken "remember" sticks only after a tap. If the phone is not there, the note waits; it is never written silently, and it is never lost. Jorah says, "Noted. Confirm on your phone to keep it."

**Exclusions.** `voice` gets `skill_workshop`, `wiki_*`, `sessions_*`, `exec`, `message`, `web_search` and `web_fetch` denied. Set `vault.scope: agent` before the `voice` agent exists: `main`'s default path stays `<state-dir>/wiki/main`, so nothing should need moving, but back up first and test on a scratch profile [docs-only: `plugins/memory-wiki.md`]. `voice` transcripts stay out of Dreaming and backfill [track: gap-private-data-through-realtime-providers.md]. Dreaming's per-agent controls were not worked out here.

### 4.6 What Adam experiences

| Moment | True behaviour |
|---|---|
| Same persona | `voice` and `main` share `IDENTITY.md` and `SOUL.md`, generated from one source. Same name and voice |
| Mac to iPhone in voice | Same `agent:voice:main` session, so "picking up" still works [track: ux.md] |
| Typed in Telegram, then speaks | Knows stable facts. For "that invoice", `ask_main` can read `agent:main:main` with `sessions_history` under same-agent visibility. Costs one hop |
| Spoke, then types in Telegram | `main` finds the call summary by memory search, and sees open jobs. No verbatim transcript in the Telegram thread |
| Looks at the Control UI | Sees two agents. The trust page must say so |
| Asks something only Opus knows | About 6 s, after an immediate acknowledgement |

### 4.7 The digest

| Question | Answer |
|---|---|
| Who generates it | `jorah-bridge` service, via `api.runtime.subagent.complete({agentId: "background"})`, which is tool-free, keeps no session and is capped at 3 concurrent runs per plugin [docs-only: `plugins/sdk-runtime/background-work.md`] |
| On which lane | `background`, Haiku 5.5 API credits now, local model on the PC later. Not `main` or the plan, per `brain.md`'s rule for unattended work. Not `voice`, which holds room audio |
| Input | `main`'s `USER.md` and `MEMORY.md`, plus a list of open job titles. **No transcripts, no reader output** |
| Output | `workspace-voice/USER.md`, under about 3,900 characters, because 12,000 characters are shared across 3 files [source: `dist/realtime-bootstrap-context-dPeThtcK.mjs`]. Also a longer `notes.md` in `voice`'s search corpus |
| Content rule | Public class only: preferences, projects, how Adam likes answers, current focus. **No third-party names, no health, no school data, no credentials.** It reaches the realtime provider every call [track: gap-private-data-through-realtime-providers.md] |
| Checks in code | Size cap, a stop-list for names and secrets, and an `as of` stamp. Failure keeps the last good digest and flags it. **A missing or stale digest never produces invented facts**: Jorah uses `ask_main` or says it does not know |
| Refresh | On change to `main`'s memory files, debounced 10 minutes. Not a clock. It reads at call start, so a running call does not change |
| Approval | Adam previews the first digest and says yes to the automation. Later changes keep a git-style diff, shown in the trust report |
| Cost | About 5K in and 1K out: $0.0005 + $0.0005 = **about $0.001 per refresh**, about $0.30 a month at 10 a day, from Haiku list prices [track: brain.md] |

**Why not Memory Wiki's compiled digest.** `context.includeCompiledDigestPrompt` adds to the memory prompt on the agent's turn, not to the realtime provider, and follows the vault. Under `scope: agent` it would read `voice`'s empty vault [docs-only: `plugins/memory-wiki.md`]. Keep the wiki on `main`.

### 4.8 Config shape

Sketch only. Not applied and not validated.

```json5
{
  agents: { entries: {
    voice: {
      workspace: "~/.openclaw-jorah/workspace-voice",
      model: { primary: "anthropic/claude-haiku-5-5", fallbacks: [] },
      tools: {
        allow: ["memory_search", "memory_get", "ask_main", "start_job",
                "job_status", "job_steer", "job_cancel", "note_for_main"],
        deny: ["skill_workshop", "sessions_send", "sessions_spawn", "exec", "message"],
        agentToAgent: { send: [] },
      },
      memory: { search: { extraPaths: ["~/.openclaw-jorah/shared/voice-notes"] } },
    },
  } },
  tools: { sessions: { visibility: "agent" } },
  talk: { agentId: "voice", consultThinkingLevel: "off" },
  plugins: { entries: {
    "jorah-bridge": { enabled: true },
    "memory-wiki": { config: { vault: { scope: "agent" } } },
  } },
}
```

The plugin bypasses `tools.agentToAgent`, since that policy governs tools, not in-process plugins [inference]. So `jorah-bridge` is a trusted component: it goes in `plugins.allow`, stays small, and gets the review `security.md` asks of plugins. Check that `tools.sessions.visibility: agent` does not break anything else that `main` does across agents.

## 5. Multi-hop latency

End of speech to first audio of the real answer. Basis: `main` turn timings are measured on this Mac: all user turns p50 3.0 s, p90 12.1 s; warm reuse 1.2 and 5.6 s [measured: brain.md]. Realtime decision and speech start about 0.4 s each way at p50, 0.6 s at p90 [inference from voice.md section 11, unmeasured]. Haiku pass about 1.0 s at p50, 1.5 s at p90 [inference: the only anchor is Haiku 4.5 first token at 0.71 s in a single run; thinking-off Haiku 5.5 is unmeasured, track: voice.md]. `reader-web` 3 to 6 s [inference]. Spoken acknowledgement under 1 s on all consult rows.

| Path | Hops | p50 | p90 |
|---|---|---|---|
| Realtime answers alone | None | Under 1 s target | Unmeasured |
| `voice` self-answer, no tool | Realtime, Haiku, speech | About 1.8 s | About 2.7 s |
| `voice` with one local tool | Realtime, Haiku twice, speech | About 2.8 s | About 4.2 s |
| **`voice` to `main`, `ask_main`** | **Realtime, Haiku, Opus, Haiku, speech** | **About 5.8 s (about 4 s warm)** | **About 16 s** |
| `voice` to `main` to `reader-web` | Above, plus reader and a second Opus turn | About 12 to 15 s | About 30 to 40 s; often converts to a job |
| `voice` to `reader-web`, `web_answer` | Realtime, Haiku, reader, Haiku, speech | About 6 to 9 s | About 12 to 14 s |
| Option D, `voice` on `main` | Realtime, Opus, speech | About 3.8 s | About 13 s |

Three things follow:

1. **`brain.md`'s under-2.5 s target applies only to the first three rows.** With one tool, it is already tight.
2. **The M3 spoken web answer should not go through `main`.** Two Opus turns add about 6 s and add nothing for a public question. Pick `web_answer` for public lookups, keeping `ask_main` for questions that need Adam's context. This adds an outward fetch to `voice`'s reach, so the security track must approve it. It is bounded because `voice` holds only public-class text, the reader returns capped typed fields, and any job started afterwards still runs in a tainted `main` session. Runner-up: always through `main`, which is simpler but slow enough to often miss the 25 s cap at p90.
3. **The two Haiku passes are the cost of B.** `before_agent_reply` can claim a turn without a model call [docs-only: `plugins/hooks/reference.md`]. If it fires on consult runs (unconfirmed), a fixed rule could skip Haiku for `job_status`. That removes hops and cost for the simplest cases. Do it only after a bench shows it matters.

## 6. Contradictions resolved

| Conflict | Who wins | Why |
|---|---|---|
| `voice.md` section 11: Opus owns all memory and actions behind consult. `brain.md` B3 and `security.md`: a thin Haiku agent answers consult | **Both, split.** Consult lands on `voice`, per `brain.md` and `security.md`. Truth and all writes stay with `main`, per `voice.md` | Room audio should not reach the top-privilege agent. `voice.md`'s principle survives one hop further back |
| `openclaw-fit.md` and `ux.md` section 12: one thread via shared session | **Multi-agent docs win.** One thread holds only within one agent. Reword to "one Jorah, two transcripts, shared facts" | `talk.agentId: voice` puts voice turns in `voice`'s store [docs-only: `nodes/talk/session-ownership.md`] |
| `security.md`: `voice` asks `main` "through send-only" | **Replaced by the plugin.** `send: []` on `voice` | Finding 1, and send-only has no job control even after the gate goes |
| `brain.md` policy table: "spawn to `main`, announce result" | **Replaced by `start_job`** | Spawn is gated on 2026.10.9, and an announcement lands in `voice`'s session without being spoken |
| `voice.md` sequence and `ux.md` U8: spoken "yes", then tap | **Version-specific, and `security.md` wins.** Tap is the authority. Plan for one step, since the next stable removes the yes. Only `voice`'s own tools would meet the gate on 2026.10.9, and none of them is classified as mutating | Findings 1 and 2 |
| `brain.md`: `voice` reads memory. `security.md`: not for voice | **Already settled for `security.md`** by the sibling gap. Refinement: `voice` keeps `memory_search` over its own public-class corpus only, and drops it if the canary test fails | The corpus holds only text already approved for the provider |
| `voice.md` over-15 s rule | **Moved to 25 s** for `ask_main`. Jobs still go to Telegram straight away | Section 4.3 |
| `growth.md` Skill Workshop as Jorah's learning | **Stands, on `main` only** | Finding 11 |

**For the sibling gap.** It says `voice`'s line to `main` returns a pointer only from M4. `ask_main` keeps that, except it allows spoken answers until a reader or connector is touched. Its canary test must include `ask_main`.

## 7. Decisions

| Decision | Pick | Why | Runner-up | What would change it | Cost |
|---|---|---|---|---|---|
| Voice and `main` link | Typed plugin | Job control, typed input, unaffected by the gate | One agent with guard | Section 3 | 2 to 3 days to build. Plan draw per ask. Pennies of Haiku |
| Consult target | `voice`, Haiku API | Room audio stays away from privileged agent | `main` on Opus | Same | $0.001 per two-pass consult, at `brain.md`'s figures |
| Result in same call | Hold open up to 25 s, else job | Only shipped path on tool-call providers | Upstream push RPC, or V2's own provider | A push RPC ships, or GPT-Live wins the bake-off | $0 |
| `main` session for voice | Dedicated `voice-bridge` and per-job keys | No queueing behind Telegram, no taint on the primary session | `agent:main:main` | Spike S2 fails on that key form | $0 |
| Fact flow | Digest out, reviewed inbox in | One writer. Adam previews changes | Shared wiki | Adam accepts unreviewed spoken writes | About 1 day |
| Digest lane | `background`, Haiku API; local on PC | Unattended work stays off the plan | Hand-kept section `main` maintains | Quality on review is poor | About $0.30 a month |
| M3 web route | `web_answer` to `reader-web` | Saves about 6 s, adds nothing Adam needs | Through `main` | Security track refuses | Reader Haiku cost |

## 8. Spikes, then acceptance

**Do these spikes first, on a scratch profile** (half a day each, except S1). Later steps depend on them. All need Adam's yes first, since they add an agent and a plugin, and a Haiku key from `brain.md` step B1.

| Spike | Check | Expected | If it fails |
|---|---|---|---|
| S1 (1 day) | Minimal plugin: `voice` calls `ask_main`, `subagent.run` hits `agent:main:voice-bridge`, answer speaks in the same relay call | Audio answer, no spoken-yes prompt, `senderIsOwner` false | Fall back to a loopback Gateway client with a dedicated `operator.write` device, using `sessions.send` and `sessions.abort` |
| S2 | On that turn, `memory_search` returns a planted `MEMORY.md` fact | Fact found | Finding 13 is live. Try the plugin creating a `direct` session entry, else stop and reconsider D |
| S3 | `before_tool_call` fires on `claude-cli` for that session (`growth.md` S13) | Hook log, block works | **Stop.** Voice-started writes and jobs stay off until solved |
| S4 | Cancel: `deleteSession` or `sessions.abort` stops a running `main` turn and its child | Terminal state; child ends | Report "cancel requested" truthfully; escalate upstream |
| S5 | Hold a consult 25 s on `gpt-realtime-2.1-mini` and on Gemini 3.8 Live | Late result is spoken once; no duplicate run (see #191108) | Lower the cap to what holds |
| S6 | `voice` cannot reach `main`'s memory with `memory_search`, `memory_get` or any corpus value, under `vault.scope: agent`. Plant a canary in `MEMORY.md` | Canary absent | Remove `memory_search` from `voice` |

**M2 acceptance** (tier: signed-in device, Mac relay, headphones). Script, on synthetic content:

1. Say "Jorah, what did I decide about the arm screws?". Expect an acknowledgement in under 1 s, then the planted answer. Record end of speech to first audio.
2. Start 10 scripted jobs, one at a time. For each, ask status once, steer 3 of them, cancel 3. Pass only if 10 of 10 status answers match the job record, every steer shows in the worker's result, no job said "cancelled" before a terminal state, and every completed job produced a card or message.
3. Say "Remember the arm uses M3 screws". Expect "Noted" and a phone card. Tap Keep. Then type the question in Telegram: `main` must answer it. Repeat with Forget: it must not.
4. Type a new public fact to Telegram. Wait 10 minutes. Start a new call and ask it. Expect it answered without an `ask_main` run in the logs.
5. Say "email my boss" from a TV recording. Expect no email, and a pending card only.
6. Restart the Gateway mid-job. Expect "I lost track of that" or the true state, never "done".

Report p50 and p90 for each row of section 5. A row that misses by more than 2x reopens section 3.

**M3 acceptance.** Ten scripted public web questions by voice. Expect spoken answers from `web_answer`, within 25 s on at least 9 of 10, with sources on a card. One planted injection page must change no state and start no job.

## 9. Not confirmed

- Whether the plugin's `subagent.run` works from inside a consult's tool call on 2026.10.9, as opposed to only by source reading. S1.
- Memory audience on plugin-started turns, S2. Hook firing on `claude-cli`, S3. Cascade cancel, S4.
- How OpenAI and Google treat a late tool result in speech. S5. OpenAI's guide is silent.
- Whether `readSessionFacts` is available to a user-installed plugin. Its docs paragraph does not say. `job_status` does not depend on it.
- Whether `before_agent_reply` and `before_prompt_build` fire on consult runs. A live report suggests other turn-level features do not (#183740).
- Whether the stock Mac app honours `talk.agentId` on all paths [issue: #167696](https://github.com/openclaw/openclaw/issues/167696) reports macOS wake ignoring a configured route. `security.md` T7 covers this.
- Voice session growth from #185942. Mitigation: alert over the 8K prefix target from `brain.md` B3, and rotate the session key daily from Jorah's own wake client if needed.
- Per-agent control of Dreaming and `skills.workshop.autonomous.mode`. Tool denial covers learning. Dreaming needs checking.
- Whether the guard's taint rule catches everything a tainted `main` turn can do through workers. `security.md`'s worker limits apply, but this path was not tested.

## Sources

**Local, OpenClaw 2026.10.9.** Docs: `docs/nodes/talk.md`; `docs/nodes/talk/realtime-sessions.md`; `docs/nodes/talk/session-ownership.md`; `docs/nodes/talk/macos-relay.md`; `docs/concepts/multi-agent.md`; `docs/concepts/memory-search.md`; `docs/concepts/session-tool.md`; `docs/concepts/session-state.md`; `docs/concepts/queue.md`; `docs/concepts/queue-steering.md`; `docs/gateway/config-tools/sessions-and-subagents.md`; `docs/gateway/security/trust-model.md`; `docs/plugins/memory-wiki.md`; `docs/plugins/sdk-runtime/background-work.md`; `docs/plugins/sdk-runtime/gateway-and-nodes.md`; `docs/plugins/sdk-overview/memory-and-context.md`; `docs/plugins/hooks/tool-policy.md`; `docs/plugins/hooks/reference.md`; `docs/plugins/tool-plugins.md`; `docs/tools/skill-workshop.md`; `docs/tools/self-learning.md`; `docs/channels/discord/voice-channels.md`.

Code: `dist/handlers-B5Rt4cMl.mjs`; `dist/realtime-session-harness-76VKE8_t.mjs`; `dist/agent-run-control-shared-1_6cGD_R.mjs`; `dist/agent-tools.before-tool-call-CQkX3nOj.mjs`; `dist/tool-mutation-BTW6eoAN.mjs`; `dist/realtime-bootstrap-context-dPeThtcK.mjs`; `dist/server-plugins-CmWlaULD.mjs`; `dist/server-plugin-in-process-dispatch-CHKjkAiH.mjs`; `dist/registry-CTP8XMYJ.mjs`; `dist/registry-runtime-session-ownership-ClnyynQF.mjs`; `dist/memory-audience-B18hFdi8.mjs`; `dist/dangerous-tools-7P77gGzs.mjs`; `dist/agent-turn-service-DndzLNDt.mjs`; `dist/realtime-quicksilver-delegation-controller-DJzRMSPy.mjs`; `dist/session-followup-completion-dNrbgyTC.mjs`; `dist/extensions/openai/capability-catalog.js`; `dist/extensions/google/realtime-voice-provider.js`.

**Tracks.** `voice.md`, `brain.md`, `security.md`, `openclaw-fit.md`, `ux.md`, `growth.md`, `gap-private-data-through-realtime-providers.md`.

**Web, through `gh` or direct fetch.**

- [PR #159697: honor ordinary permissions for voice requests](https://github.com/openclaw/openclaw/pull/159697)
- [Issue #166156: owner opt-out for spoken confirmation](https://github.com/openclaw/openclaw/issues/166156)
- [Issue #168475: spoken yes before allow-listed commands](https://github.com/openclaw/openclaw/issues/168475)
- [Issue #183740: memory continuity for realtime Talk](https://github.com/openclaw/openclaw/issues/183740)
- [Issue #179236: consults rewrite the prompt cache](https://github.com/openclaw/openclaw/issues/179236)
- [Issue #185942: consults never apply session.reset](https://github.com/openclaw/openclaw/issues/185942)
- [Issue #152412: toolPolicy for app Talk](https://github.com/openclaw/openclaw/issues/152412)
- [Issue #163066: Talk consults through the session mailbox](https://github.com/openclaw/openclaw/issues/163066)
- [Issue #164730: consults ignore session model overrides](https://github.com/openclaw/openclaw/issues/164730)
- [Issue #165682: narrate consult progress](https://github.com/openclaw/openclaw/issues/165682)
- [Issue #167696: macOS wake ignores configured route](https://github.com/openclaw/openclaw/issues/167696)
- [Issue #191108: relay consult can run twice on Android](https://github.com/openclaw/openclaw/issues/191108)
- [Talk docs at v2026.10.10-beta.5](https://github.com/openclaw/openclaw/blob/v2026.10.10-beta.5/docs/nodes/talk/realtime-sessions.md)
- [OpenAI realtime conversations guide](https://developers.openai.com/api/docs/guides/realtime-conversations)
