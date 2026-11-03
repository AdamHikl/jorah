# Gap: private data through realtime providers

Date: 2026-11-02. Research only. No key, account, config or gateway was touched, and nothing was run with real audio. Not legal advice.

Labels: `[verified: source]` read directly this session; `[source: file]` read in OpenClaw 2026.10.9's shipped code, not run; `[docs-only]` OpenClaw's bundled docs say so, not run; `[track: file]` another track's finding, not re-checked; `[inference]` my reasoning; `[not read]` could not be confirmed. Web pages were read through a fetch tool that summarizes them, so check exact wording before quoting any term.

## Limits of this check

- **OpenAI's contract pages could not be read.** `openai.com/policies/services-agreement`, `openai.com/enterprise-privacy` and `help.openai.com` all returned HTTP 403 to the fetch tool. A direct `curl` with a browser user agent, which I tried, was blocked by this session's permission check as bot-check circumvention. I did not retry it or use a proxy, an archive or a browser to get past the block. So **OpenAI's minimum age for an API customer, its EEA contracting entity, its DPA and transfer mechanism, and its sub-processor list remain unconfirmed.** Section 9 gives Adam a 10-minute reading list.
- **OpenAI's developer docs could be read.** They give retention, training, zero data retention and data residency. Those claims are verified, but only at documentation level, not at contract level.
- **The shared web search budget was used up,** so I opened only known URLs.
- **No roadmap file exists on disk** under `docs/plan/`. I relied on the assignment's description of M2, M4 and section 5, so M-numbers below may need fitting to the final text.

## 1. Answer

**Who gets what.** Once a realtime session is open, OpenAI (or Google) receives everything the microphone hears, Adam's profile files, and every consult answer Jorah speaks. Lane names in the plan hide this: "the API lane" covers Haiku, not the realtime model in front of it.

**Are the terms bad?** No, but they are not private either. OpenAI's docs say API data does not train models by default and that abuse logs are kept up to 30 days and may contain prompts and responses. Google's paid terms say prompts and responses do not improve its products and that logs are kept for an unstated "limited period", in any country where it has facilities. Each provider's route to zero retention needs approval or a different product.

**Can private answers be kept from the provider?** Yes, but only by never handing the text over. A realtime model speaks what it is given, and there is no setting that hides the text from it. So the answer must go to a screen, or to local speech with the provider session closed.

**Pick.** Keep `gpt-realtime-2.1-mini` for ordinary conversation, subject to the M2 age and contract check in section 6. Treat mail, calendar content, messages, school data and camera frames with other people as **private class**: they never enter the realtime session. The enforcement is at the tool boundary, in code. People's names stay out of what the realtime model speaks.

## 2. Who receives what, by lane

| Lane | Processor | What it receives | Default retention |
|---|---|---|---|
| Wake | None | Audio on device, discarded [track: security.md; `docs/platforms/mac/voicewake.md`] | None. A false wake opens the next row |
| Voice front, `gpt-realtime-2.1-mini` | **OpenAI**, two models: the realtime model plus `gpt-4o-mini-transcribe` [source: `dist/realtime-voice-session-policy-Sq5ivQfQ.mjs`] | Each mic chunk while open, via `input_audio_buffer.append` [source: `dist/realtime-voice-bridge-CGOLqV8u.mjs`]. Profile files. Consult answers. History on a voice switch | No application state; abuse logs up to 30 days [verified: your-data] |
| Voice front, GPT-Live | **OpenAI**, `/v1/live/sessions` | Same, plus a delegation sideband | Abuse logs 30 days. Recording only if `store: true`; default off, and I found no `store` setting in OpenClaw's GPT-Live code [verified: your-data, live-conversations; source grep] |
| Voice front, Gemini 3.8 Live | **Google**, Developer API URL [source: `dist/extensions/google/realtime-voice-provider.js` line 29] | Same. Browser Video Talk also sends up to 1 frame per second straight to Google, bypassing the Gateway [docs-only: `nodes/talk/realtime-sessions.md`] | "Limited period" logs. Resumption state, including audio and video, up to 24 h when a handle exists, and OpenClaw's default requests one [verified: zdr page; source lines 260, 275] |
| Voice consult | **Anthropic**, commercial API | The question as the front model wrote it, tool results | 30 days, with exceptions; no training [track: vision.md section 4] |
| Typed, `main` | **Anthropic**, consumer Max login | Typed chat, memory, reader output. Also any voice transcript if Talk is not moved off `main` | Depends on Adam's model-improvement setting [track: vision.md, connectors.md] |
| Unattended, readers | **Anthropic** API, or local for EduPage | Mail, messages, school data | As consult [track: security.md section 6] |
| Vision | Local first. "Look" is **Anthropic Max**. Captions are Anthropic API. "Live" is **Google** | Frames | As above [track: vision.md] |
| Native speech fallback, also V0 | **Apple**, may be network. Brain as the Talk agent. TTS as configured: **ElevenLabs** if a key exists, system voice otherwise | Adam's speech, and anyone else's, while Talk listens | Audio not stored unless opted in; request data up to 2 years under a rotating random identifier; human review only on opt-in [verified: Apple Siri and Dictation page; `docs/nodes/talk.md`; source: `TalkModeRuntime.swift`] |
| V2 pipeline | Local, plus Anthropic API. Hosted STT or TTS only if chosen | Local audio; text to Haiku | Local on device. Hosted vendors' terms [not read] |
| Delivery | **Telegram**, not end to end. **Apple** push if used | Whatever is sent there | [track: connectors.md] |

**Two hidden inputs to the realtime model.** Neither appears in any track.

1. **Profile files.** The session instructions include `IDENTITY.md`, `USER.md` and `SOUL.md` up to 12,000 characters [source: `dist/realtime-bootstrap-context-dPeThtcK.mjs`]. They come from the owning agent's workspace, so `talk.agentId: "voice"` with a thin workspace controls them. Today these files total 4.6 KB in `workspace/` [verified: `wc -c`]. If `USER.md` later names family or friends, OpenAI gets those names every session.
2. **History replay.** Browser and Gateway-controlled sessions start with shared-session history. A Mac `gateway-relay` session starts with history only on a voice switch [source: `dist/handlers-B5Rt4cMl.mjs` lines 3162, 5015]. The limit is 16 entries and 8 KB [docs-only: `nodes/talk/realtime-sessions.md`]. If a chat in the same session held a mail summary, it can go to the provider this way.

**Transcripts stay on disk.** Finalized utterances are always appended to the agent session [docs-only: `nodes/talk/realtime-sessions.md`], so a guest's words land in the session store, and in later model turns of that agent. Incognito exists only for threads started in the Control UI [docs-only: `concepts/session.md`], so it does not help Talk.

### By data class

| Data class | Current plan sends it to | Required from M2 or M4 |
|---|---|---|
| **Adam's room audio** | OpenAI or Google while a session is open. Apple on fallback | Same, with a short idle close and a named indicator. Disclosed. Adam's own spoken names cannot be kept out, so that is disclosed too |
| **Bystander audio** | Same as above, with no filter. It reaches the transcriber and session store | **Guest mode closes Talk.** No realtime, no native fallback. Typed use only |
| **Calendar digest** | Realtime provider, through the `voice` agent's "read today's calendar" [track: security.md section 6; brain.md section 8] | Anthropic API or local reader, then screen. Realtime gets counts and times only, written by code |
| **Consult answers read aloud** | Realtime provider, always. Then replayed as context until the session closes | Non-private answers: unchanged. Private-class answers: never sent |
| **Mail summaries** | Reader API, then `main` on Max (`connectors.md` notes this gap), then realtime if spoken | Reader API, then screen. No realtime. No Max until `connectors.md`'s gap closes |
| **Camera frames** | "Look" on Max. Captions on API. "Live" on Google, or one JPEG to OpenAI in browser Talk | Look with anyone but Adam in frame goes to API or local. Live only with Adam alone, explicitly started |
| **School data** | Reader API or local, then possibly speech | Local or Anthropic API, then screen. **Never realtime, Telegram or Google** |
| **Profile files** (added) | Realtime provider, every session | Thin voice workspace. No third-party names. Reviewed with a diff |

## 3. What the paid API terms say

| Question | OpenAI API | Google Gemini API, paid |
|---|---|---|
| **Training** | Not used to train or improve models unless the customer opts in [verified: your-data] | Prompts and responses not used to improve products [verified: aistudio terms, effective 2026-03-23]. Paid means a Cloud project with active billing. Unpaid quota, and AI Studio on an account without active billing, count as Unpaid Services, where reviewers may read content, so use a billed project [verified: same] |
| **Retention** | `/v1/realtime`: abuse logs up to 30 days, longer if law or harm requires; application state none [verified: your-data]. Logs "may contain" prompts and responses [verified: same] | Logs for "a limited period", no number given [verified: terms]. Developer logs are separate: up to 55 days, on by default for Interactions and for Generate Content in projects created from 2026-10-26; can be turned off [verified: logs-policy]. Page does not mention Live |
| **Human review** | Described only for Safety Retention flagged activity and flagged CSAM. Silent on the default case [verified: your-data]. Enterprise privacy page [not read]. Assume possible [inference] | Paid section silent, and it does not say who can open the logs [verified: terms]. Reviewers named only for Unpaid Services and datasets Adam shares [verified: terms, logs-policy]. Assume possible for abuse [inference] |
| **Zero retention** | ZDR eligible on `/v1/realtime`, but needs OpenAI's prior approval through sales [verified: your-data]. Not realistic for one prepaid hobby account [inference] | Developer API has no single switch. Guaranteed ZDR means Vertex AI [verified: zdr page]. I found no Vertex route in OpenClaw's Google realtime provider [source: grep]. Search and Maps grounding store 30 days with no opt-out [verified: zdr page] |
| **Age minimum** | **[not read]** Services Agreement unreadable. Developer docs set no account-holder minimum [verified: safety best practices, under-18 guidance] | **18 or older.** Also bars API clients directed at or likely to be used by under-18s [verified: terms] |
| **Children's data** | Docs say not to process personal data of children under 13 or the applicable age of digital consent without first implementing ZDR [verified: under-18 guidance]. Slovakia's age is 16 [track: security.md section 13]. The page addresses services for minors, so its reach here is [inference], but the wording is broad and obeying it is cheap | No equivalent found. The 18+ rule applies to the customer and the app [verified: terms] |
| **EU and transfers** | EU storage and processing exist for `/v1/realtime` at `eu.api.openai.com`, but **require** ZDR, MAM, Private Retention or Safety Retention, all by approval [verified: your-data]. Tracing is not EU-compliant there [verified: same]. So expect non-EU processing on a normal key [inference]. Contract entity and transfer tool [not read]. The page's code samples conflict on which project key EU processing needs | Data "may be stored transiently or cached in any country" with Google facilities [verified: terms]. DPA covers "Gemini API Paid Services" [verified: Google services list]. The DPA relies on EU-US DPF certification, with SCCs as fallback [verified: processor terms, version 10, 2026-05-07]. Slovakia is an available region; no EU residency stated [verified: available regions] |
| **Audio specifically** | `/v1/realtime` row does not mention audio, and the page does not say whether logs hold audio. Treat them as if they do [inference]. GPT-Live recording, only with `store: true`, is a stereo WAV kept 30 days [verified: live-conversations]. `/v1/realtime/transcription_sessions` is absent from the retention table [verified: your-data] | Terms do not mention audio or Live [verified: terms]. Resumption keeps text, audio and video state up to 24 h [verified: zdr page]. Another page says tokens stay valid 2 h [verified: session-management]; token validity is not deletion, so plan for 24 h [inference] |

**Privacy does not overturn the pick.** OpenAI gives a stated number, no application state and a route to EU processing. Google gives an unstated period and resumption state by default, but its contract is the one I could read. Neither is clearly safer on paper [inference], so the cost-based order in `voice.md` and `brain.md` stands. If Adam is under 18, Gemini is out on Google's own terms, and Claude consumer terms are also affected [track: brain.md open question 6].

**Consumer routes are a different thing.** `gpt-live-1-codex` through ChatGPT sign-in [docs-only: `nodes/talk.md`] would not be the API lane. I have not read which terms cover it, so it is not usable for anything but Adam's own test talk [inference]. Credits from ChatGPT Pro that apply to the API are a billing matter and should be checked separately [track: brain.md].

**Runner-up if this becomes a business: Azure.** OpenClaw's realtime config accepts `azureEndpoint` [source: `dist/realtime-voice-session-policy-Sq5ivQfQ.mjs`]. Microsoft's page says prompts do not reach OpenAI, a DataZone deployment in an EU state processes within the EU, and for EEA deployments the human reviewers are in the EEA [verified: learn.microsoft.com data-privacy]. It also has abuse monitoring, opt-out by application. Availability of a realtime model there, and whether audio falls under that text, are [not read].

## 4. Can a private answer be kept from the provider?

**What does not work.**

- **`suppressResponse`.** It stops the provider from generating speech, but the tool result is still submitted [source: `handlers-B5Rt4cMl.mjs` lines 1680, 1975 to 2002].
- **`force-agent-consult`.** It routes more through OpenClaw, and then tells the provider to "speak this result" [source: same, line 1772]. The provider still hears and gets the text.
- **Out-of-band responses or `conversation: "none"`.** These keep text out of the replayed conversation, but OpenAI still receives it [verified: realtime-conversations]. They shorten replay, not exposure.
- **Prompting the model not to repeat something.** It has already received the text.
- **Headphones.** `ux.md` gives headphones "full detail". That protects the room, not the processor.

**What works, and the MVP.**

```text
Adam: "Jorah, what's my day?"           -> provider hears this, unavoidable
 realtime model -> openclaw_agent_consult
 voice agent (Haiku, no connector tools) -> private_show(kind: "agenda", range: "today")
 plugin -> reader lane -> structured result -> card on Mac app or iOS app
 plugin returns to Haiku only: { status: "shown", surface: "mac", count: 4, firstAt: "10:00" }
 Provider speaks: "Four things today, first at ten. It's on your Mac."
```

- **The plugin returns no content, by construction.** So the guarantee does not depend on a model behaving. `security.md` already warns that instructions are not controls.
- **No classifier.** `brain.md` rejected one, and it is not needed. The voice agent simply has no tool that returns private text.
- **Card, not Telegram.** Show it in the Mac app or iOS app. Telegram is not end to end [track: connectors.md], so `ux.md`'s "otherwise Telegram" gets a neutral line only: "Jorah has something for you on your Mac." Push text stays neutral for the same reason.

**"Read it to me" with local speech.**

1. Close the provider session (`talk.session.close` exists [source: handlers line 5195]).
2. Speak through local TTS: `talk.provider: "system"` or `"mlx"` [docs-only: `nodes/talk.md`]. Do not configure ElevenLabs for this, or it becomes a new processor.
3. Stay closed until the next wake.

Closing is needed because a local voice on the speaker goes back into the open mic, and from there to OpenAI. Echo suppression is documented only for the provider's own playback [docs-only: `nodes/talk/macos-relay.md`]. Whether Mac pause stops the audio stream is unconfirmed, so close is the safe form. Whether a plugin can trigger `talk.speak` on the Mac while no relay is open is **not verified**: budget a one-day spike, with a small Mac helper as the fallback. This is why the screen ships first.

**Slovak.** The system voice `Laura` exists on this Mac [track: voice.md], so a Slovak school note can be read locally, even though recognition of Slovak goes through Apple's network.

## 5. Decisions

| Decision | Pick | Why | Runner-up | What would change it | Cost |
|---|---|---|---|---|---|
| Private class on voice | **Option A: pointer only.** Screen first, local TTS on request | Holds regardless of unread OpenAI terms and without ZDR | **Option B:** Adam accepts OpenAI as a processor for their own calendar only, in writing, after reading the contract. School, mail and minors stay out | OpenAI approves ZDR or MAM, or V2 ships | About 1 to 2 days to build, plus a 1-day TTS spike. $0 cash. Reader costs fall under API credits |
| How spoken private answers return | **V2 pipeline later:** local STT, Haiku, local TTS. No realtime provider | Natural speech with Anthropic API as the only cloud | Hosted STT or TTS, after reading their terms | V2 latency fails | `voice.md` V2: about $1 to $30 per month |
| Guest mode | **Talk closed.** Typed only, cameras off | Realtime cannot meet "no cloud STT" or "no retention", and native fallback also stores transcripts | Local V2 with no retention, once built | Lawyer says notice is enough, and Adam chooses it | $0 |
| Realtime provider | **Unchanged:** `gpt-realtime-2.1-mini`, then bake-off | Terms do not separate it from Gemini | Gemini 3.8 Live, with `sessionResumption: false`, grounding off, developer logging off | Contract check fails, or age rules | As `voice.md` |
| ZDR or EU application | **Do not pursue now.** It needs a sales conversation | One-person prepaid account; pointer rule removes the need | Azure EU route | Business use | $0 |
| Native fallback | **Keep, disclose, private class unaffected** | Apple gets Adam's speech only, since answers stay local. I could not confirm whether Talk forces on-device | Disable Talk when relay fails, with a watcher | Source shows it can force on-device for `en-US` | $0 |

## 6. What must change in M2 and M4

### M2, before any key is bought

1. **Age gate first.** Adam answers `brain.md` open question 6. Under 18 rules out Gemini, and the OpenAI answer comes from the next item. Section 5 question 1 of the roadmap must name **OpenAI**, not only Claude and Gemini.
2. **Contract check.** Adam reads section 9's list before prepaying. Stop if the age rule blocks them.
3. **Thin voice workspace now, not at B3.** `talk.agentId: "voice"` with no third-party names in its profile files. Without it, transcripts reach `main`, and so the Max login.
4. **Idle close becomes a privacy gate.** It is already a V1 gate in `voice.md`. Keep it short, and name the recipient in the indicator: "Streaming to OpenAI", not "cloud" or a plain dot.
5. **Guest mode closes Talk.** Include the physical mute.
6. **Bake-off uses scripted, synthetic content only.** No real names, mail or calendar. Other people in the room stop the test.
7. **Gemini settings for the bake-off:** `sessionResumption: false`, no grounding, developer logging off, billed project. Note that resumption off limits a connection to about 10 minutes [verified: session-management], which is fine for short sessions.
8. **Check `Improve Siri and Dictation` is off on this Mac,** and leave `talk.provider` off ElevenLabs unless chosen.
9. **First trust report** with section 8's wording.

### M4, before real mail and calendar connect

1. **Widen the blocking decision.** It covers reader output on `main`. It must also ask: "May private-class text enter the realtime provider?" Default answer: no, Option A. A yes is Adam's explicit choice, per class.
2. **Build `private_show`** before connecting Gmail or Calendar. Screen surface first.
3. **Remove from `voice`:** "read today's calendar" and `memory_search`. Add `private_show`. `voice`'s send-only line to `main` returns a pointer only.
4. **Rewrite spoken lines:** "Message from Jana" becomes "A new message. It's on your phone". "Email to Jana is ready" becomes "The email is ready on your phone". Names appear on the screen only.
5. **Add voice sessions to memory exclusions.** `connectors.md` already excludes Gmail hooks only. Dreaming and backfill can read voice transcripts [inference from `concepts/memory-provenance.md`]; review them before a transcript becomes a memory.
6. **Pass the canary test below before any real data.** This is a gate, not a nice-to-have.
7. **EduPage waits** for local reader or field filter, per `security.md`, and is never routed through the voice front.

### Canary test

Plant a unique invented name, such as `Zeltrova-7Q`, in a test calendar event, a test mail and a memory entry. Then, over voice, ask for today's agenda, the latest mail and that person's details. Pass only if the canary appears:

- **Nowhere** in the provider's outgoing events (log tool results, `instructions` and `sendUserMessage` at the Gateway bridge, in a debug run with hashes kept).
- **On** the card.

Run it again after a voice switch and after a relay drop into native fallback.

Evidence tiers stay separate: source check, then launch, then signed-in device acceptance on a real Mac. **None of these has been done.** All of section 4 is a source and doc check.

## 7. Contradictions resolved

| Conflict | Who wins | Why |
|---|---|---|
| `voice.md` passes OpenAI terms to a legal track; `security.md` hands STT terms to voice; `brain.md` did not check | **This file** closes it at docs level. Contract remains with Adam (section 9) | Nobody owned it |
| `brain.md` rule "other people's data goes through API or local" vs realtime being an API | **Rule stands but is too coarse.** New wording: other people's data goes only to the processors named per class in section 2 | Terms-wise OpenAI is commercial, but it was never assessed |
| `security.md` guest mode "no cloud STT except wake commands, no retention" vs `voice.md` V1 streaming an open mic | **`security.md`** | Legal risk under Slovak Civil Code § 12 and Criminal Code § 377 is higher than a voice feature's value. Realtime has no "wake command only" form. Guest mode therefore closes Talk |
| `security.md` table gives `voice` "read today's calendar"; `brain.md` gives it calendar and memory reads | **Neither, as written.** Those reads move behind `private_show` | Their results would go straight to the realtime provider. On memory, `security.md`'s "not for voice" wins over `brain.md`, for the same reason |
| `ux.md` "headline only: Message from Jana" and "headphones get full detail" | **This file** for realtime sessions. `ux.md` stands on V2 | Those rules consider who is in the room, not who processes it |
| `ux.md` treats realtime failure as only "slower"; `brain.md` path 13 flags Apple | **`brain.md`**. `ux.md` adds a disclosure | Fallback changes the processor |
| `vision.md` D2: "Look" on Max, vs `security.md` "other people's data never on consumer login" | **`security.md`** when anyone but Adam is in frame. Apple Vision's local person count can route it. Adam alone stays on `vision.md`'s D2 | A photo of someone is their personal data |

## 8. Truthful wording for the trust report

**Say:**

- "When the realtime dot is on, what the microphone hears goes to OpenAI, including anyone else in the room. OpenAI's docs say this isn't used for training by default, and that abuse logs last up to 30 days, or longer if law or safety requires."
- "Processing is probably outside the EU."
- "Mail, calendar details and school data go to Anthropic's API or a local model, and appear on your screen. They are not sent to OpenAI."
- "If realtime fails, your speech may go to Apple."

**Do not say:** "private", "nothing is stored", "EU only", "no human can read it", or "only you hear this". **Do not say** "not sent to OpenAI" until the canary passes on a device.

**Bystander and household questions for a lawyer now name recipients.** Ask: "Household exemption and § 12 and § 377: does a guest's speech reaching a US-based AI provider, kept up to 30 days in abuse logs, change the answer?" `security.md` already calls this possibly "otherwise using" a recording. The exemption covers Adam, not the provider, which stays regulated [verified via track: Recital 18].

## 9. Adam's 10-minute reading list

Open these in a normal browser, before M2 prepayment. Answers belong in `status.md` or the plan, with date.

1. **`openai.com/policies/services-agreement`:** minimum age or capacity to accept; contracting entity for an EEA customer; whether the DPA applies automatically.
2. **`openai.com/policies/data-processing-addendum`:** does it cover a prepaid individual; SCC or DPF for EU transfers.
3. **`openai.com/policies/sub-processor-list`:** who else may touch audio.
4. **`openai.com/enterprise-privacy`:** who may access API content, and on what trigger.
5. **Usage policies:** anything on recording others, voice and biometrics.
6. **Console, after signup:** project's data retention and region as actually shown.
7. **`~/.claude-jorah` account:** model-improvement setting, already asked in `vision.md`.

**A stop condition:** if item 1 requires 18 and Adam is younger, neither researched realtime provider can be used on Adam's own account. The voice lane then waits for V2's local speech, and who may hold the accounts, including Anthropic's [track: brain.md], has to be settled first.

## 10. Still unconfirmed

- All of section 9.
- Whether Talk's native path can force on-device for `en-US`. `TalkModeRuntime.swift` delegates to `SpeechRecognitionRequestPolicy`, and I could not find that file. Docs say Talk may use the network.
- Whether OpenAI's abuse logs hold audio, or only text.
- Whether the Live API falls under Google's developer logging. `logs-policy` does not mention it.
- Google's real abuse-log period. The current terms give none.
- Whether plugin hooks can see or rewrite consult output. Not needed for Option A.
- Terms of Soniox, ElevenLabs and any other hosted STT or TTS. Read them before V2 uses one.
- Anthropic's own rules on minors' data in the commercial terms. Read them before EduPage.

## Sources

OpenAI, read:

- https://developers.openai.com/api/docs/guides/your-data
- https://developers.openai.com/api/docs/guides/live-conversations
- https://developers.openai.com/api/docs/guides/realtime-conversations
- https://developers.openai.com/api/docs/guides/safety-best-practices
- https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance

OpenAI, returned 403, not read:

- https://openai.com/policies/services-agreement/
- https://openai.com/enterprise-privacy/
- https://help.openai.com/en/articles/5722486-how-your-data-is-used-to-improve-model-performance

Google:

- https://aistudio.google.com/docs/terms
- https://aistudio.google.com/docs/logs-policy
- https://aistudio.google.com/docs/zdr
- https://aistudio.google.com/docs/live-api/session-management
- https://aistudio.google.com/docs/available-regions
- https://business.safety.google/processorterms/
- https://business.safety.google/services/

Apple:

- https://www.apple.com/legal/privacy/data/en/ask-siri-dictation/
- https://developer.apple.com/documentation/speech/sfspeechrecognitionrequest/requiresondevicerecognition.md

Microsoft:

- https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy

OpenClaw 2026.10.9, local at `/opt/homebrew/lib/node_modules/openclaw/`:

- Docs: `docs/nodes/talk.md`, `docs/nodes/talk/realtime-sessions.md`, `docs/nodes/talk/macos-relay.md`, `docs/nodes/talk/session-ownership.md`, `docs/platforms/mac/voicewake.md`, `docs/concepts/session.md`, `docs/concepts/memory-provenance.md`
- Code: `dist/realtime-bootstrap-context-dPeThtcK.mjs`, `dist/handlers-B5Rt4cMl.mjs`, `dist/agent-run-control-shared-1_6cGD_R.mjs`, `dist/realtime-voice-session-policy-Sq5ivQfQ.mjs`, `dist/realtime-voice-bridge-CGOLqV8u.mjs`, `dist/extensions/google/realtime-voice-provider.js`
- https://raw.githubusercontent.com/openclaw/openclaw/v2026.10.9/apps/macos/Sources/OpenClaw/TalkModeRuntime.swift

Tracks: `voice.md`, `brain.md`, `security.md`, `connectors.md`, `ux.md`, `vision.md` in this folder.
