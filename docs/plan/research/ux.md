# Jorah research track: UX and interaction design

Date: 2026-11-02. Status: research only. Nothing was installed, paired or configured, and the gateway was not touched.

## How to read this file

Evidence labels:

| Label | Meaning |
|---|---|
| `[verified: URL]` | I opened that page this session. A vendor page is still the vendor's claim. |
| `[docs-only: path]` | Stated in OpenClaw's bundled docs (`/opt/homebrew/lib/node_modules/openclaw/docs/`), not exercised on Adam's devices. Paths are relative to that folder. |
| `[secondary: URL]` | An encyclopedia or third-party summary that I opened. Check before relying on it. |
| `[search-snippet: URL]` | Seen only in a search result's summary, because the page would not open or came back truncated. Weaker than `[secondary]`. |
| `[track: file]` | Taken from another research file in this folder, which carries its own evidence. |
| `[inference]` | My design reasoning or arithmetic. Every number with this label is a starting value to test, not a fact. |
| `[unconfirmed]` | From memory, or the page would not open. Do not rely on it. |
| `[source: path]` | Read in the shipped OpenClaw 2026.10.9 code under `/opt/homebrew/lib/node_modules/openclaw/`. Not run. |
| `[unverified]` | The skeptic pass could not confirm it from a primary source. Do not rely on it. |

Evidence tiers follow Adam's rule: source check, install, launch, signed-in device acceptance. **Everything in this file is at the source-check tier or below.** The OpenClaw Mac app is not installed and no device node is paired [track: openclaw-fit.md]. No cue, timing or flow here has been heard or seen on a device.

**Second pass.** The first pass of this track ran no searches, because the shared search budget had run out. This pass could search, and it read the 2026 product evidence. It kept the design and changed only what the evidence changed:

- **Siri AI is not on iPhone, iPad or Watch in the EU. It is on Mac.** The first pass implied both (U21).
- **Follow-up windows moved from 6 s and 10 s to 8 s and 12 s,** after reading Google's stated 10 s and 15 s (U5).
- **"Stop" no longer speaks after being told to stop,** and it leaves a 4 s window so "cancel that" works without re-waking. The first pass's table and dialogue contradicted each other on this.
- **"Never say hmm" became a test,** because two studies favour spoken fillers over spinners (U19).
- **Voice PE dropped from pick to conditional.** Its page calls it "Built for Home Assistant" (U16).
- **Gemini 3.8 Live always has proactive audio on and has no affective dialog.** That settles one open item and adds a new failure mode: the model may choose silence (section 10). Gemini is the voice track's runner-up, not its V1 pick, so this applies only if Gemini wins the bake-off.
- **New:** indicator interlock (U20), update safety (section 22), and a wrong-premise test for sycophancy (section 5).

**Skeptic pass (same day).** An independent check reopened the sources and read the shipped code. Most facts held. It changed U8, moved the idle close and progress lines into V1, corrected which voice model is the V1 pick, and limited what OpenClaw's iOS approval card and iOS notifications can do. The bottom line stands. See **Verification** at the end of this file.

**Remaining research limit:** TechRadar, Tom's Guide, Android Authority, The Verge, OpenAI's index pages and Help Center would not open or came back truncated. So user sentiment on Alexa+ and Gemini for Home rests on press reports of Reddit threads, one review of Friend and one review-mining vendor. I found no long-term usage data for any 2026 product. Complaints skew negative by nature. Section 27 lists every gap.

Other tracks already fixed some things, and this file uses them rather than competing with them:

- Approval tiers T0 to T4, kill levels K0 to K5, `jorah-guard` decision log, guest mode [track: security.md].
- Wake engine, echo hardware, realtime provider, latency targets and filler thresholds [track: voice.md].
- Video gates G0 to G3 and the CAD verifier [track: creative.md].
- Trust ladder for tools, preview card, Changes tab [track: growth.md].
- Look, Watch and Live vision modes, `jorah-eyes` [track: vision.md].

---

## 1. Bottom line

**Jorah should feel like a quiet, competent colleague who answers fast, shows long things on a screen, keeps working in the background, says exactly what it checked, and can always be stopped. The feel comes from timing and honesty, not from a British accent.**

Eleven findings shape the design:

1. **The Jarvis feel is out of reach on OpenClaw's native Talk path.** It speaks only after the whole agent run finishes [docs-only: nodes/talk/macos-relay.md]. There is no way to narrate progress on that path. The realtime path (fast voice model in front, Claude behind it) is a UX requirement, not a nice extra. Native Talk only proves the wake word and the loop. The realtime path is necessary but gives less than the first passes assumed. Its built-in prompt tells the voice model to speak one brief acknowledgement, then wait for the final result [source: `DEFAULT_REALTIME_INSTRUCTIONS` in `dist/handlers-B5Rt4cMl.mjs`; not run], and `talk.realtime.instructions` only appends to that prompt [docs-only: nodes/talk.md]. Status comes when Adam asks [docs-only: nodes/talk/realtime-sessions.md]. I found no path that speaks tool events by itself, so timed progress lines are a V1 build (section 8). OpenClaw itself rates voice and realtime talk M2 Alpha [docs-only: maturity/scorecard.md].
2. **Failed assistants did not fail on voice quality.** Humane failed on being slow, hot and screenless, and it died when its servers were cut [secondary: https://en.wikipedia.org/wiki/Humane_Inc.]. Rabbit failed on claims beyond reality and on retention, with about 5,000 of 100,000 buyers active at a time [secondary: https://en.wikipedia.org/wiki/Rabbit_r1]. Limitless and Rewind stopped EU service on 2025-12-05 and permanently deleted those accounts' data after a short export window [verified: https://www.limitless.ai/]. The design answers are: a screen is always available, claims are truthful, data stays local and exportable.
3. **Apple's guidance directly conflicts with "witty Jarvis", and early market signals point the same way.** Apple says to avoid attempts at humor because they become irritating over time, and to keep replies as short as the context allows [verified: https://developer.apple.com/design/human-interface-guidelines/siri]. Amazon added a "Brief" style to Alexa+ [verified: https://www.aboutamazon.com/news/devices/alexa-plus-personality-styles, which shows no date], and PCWorld's reviewer, writing on 2026-02-25, found it the only style that was not cringe, though he kept the default persona [verified: https://www.pcworld.com/article/3071273/alexas-new-ai-personalities-are-cringe.html]. That is one reviewer, not a market result. So wit must be rationed, and it is a setting. A butler persona is Adam's choice, not a default.
4. **"Stop" must be separate from "cancel".** Interrupting speech does not stop background work, and spoken cancel is a separate action in OpenClaw [docs-only: nodes/talk/realtime-sessions.md]. OpenAI's GPT-Live docs take the same line: backend work can continue after an interruption, and the application decides [verified: https://developers.openai.com/api/docs/guides/live]. People will expect one word to do both. This is the most likely trust failure in daily use, so the vocabulary is fixed in section 9.
5. **Voice can never be the approval, so voice must be good at handing off.** The room can contain a TV, a guest or a replay. Security already rules that risky actions become a phone approval [track: security.md]. The UX job is to make "on your phone" a two-second flow, and to keep approvals under about 5 a day, because fatigue defeats the control. On the realtime path OpenClaw also forces its own spoken yes before many of these actions, so the V1 flow is yes, then tap (U8).
6. **OpenClaw has no multi-device arbitration.** A search of the bundled docs finds "arbitration" only for desktop control. Wake words are one global list and each node listens on its own. Routing maps a trigger to a session, not to a device [docs-only: nodes/voicewake.md]. With two ears on, two devices will answer. V0 avoids this by running exactly one ear. V2 needs a small broker. Apple's published rule is the best model: the device that "heard you best or was recently raised or used" [verified: https://support.apple.com/en-my/105077]. Home Assistant's is the simplest: first detection wins, others are rejected for 2 seconds [verified: https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/assist_pipeline/run.py].
7. **The default wake flow has a catch that users will hit in the first minute.** OpenClaw's wake trigger only fires after a 0.55 s pause following the word [docs-only: platforms/mac/voicewake.md], and the path into Talk Mode drops words said along with the wake phrase [track: openclaw-fit.md]. So "Hey Jorah what's on today" in one breath will fail on V0. V0 must teach "Hey Jorah", chime, then speak. V2's ring-buffered trained wake word fixes it.
8. **Almost all the surfaces already exist, so build little.** Overlay orb, menu-bar states, widget panel that does not steal focus, approval inbox on iPhone and Watch, session dashboards and notification categories all ship [docs-only: nodes/talk/client-ui.md, platforms/mac/canvas.md, platforms/ios.md, web/dashboards.md, web/notifications.md]. Our own build is four small things: a state hub with a wake broker, a status light, a notification budget, and a trust page. V1 also needs two small helpers: an idle close [track: voice.md] and timed progress lines (section 8). The approval inbox exists, but its card cannot hold a long message body (section 14).
9. **People judge these assistants on simple things first.** Alexa+ complaints name slower lights and timers, and an upgrade applied without consent [verified: https://www.storyboard18.com/brand-marketing/amazon-auto-upgrades-echo-devices-to-alexa-plus-leaving-users-divided-87623.htm]. One vendor's reading of 136 Gemini complaints among Google Home reviews found forced adoption 27.9%, broken routines 22.1% and slowness 16.9% [verified, commercial publisher, US Android only: https://unstar.app/blog/google-home-gemini-voice-commands-worse-reviews-2026]. So a smarter brain that is slower at timers feels like a downgrade. Jorah needs a regression script of daily commands, and it never changes behaviour silently.
10. **Siri AI is a neighbour on the Mac and absent from the iPhone here.** It is not available in the EU on iOS, iPadOS or watchOS, while macOS 27 has it [verified: https://www.apple.com/newsroom/2026/09/siri-ai-a-profoundly-more-capable-and-personal-assistant-is-here/, https://apple.com/newsroom/2026/06/due-to-dma-siri-ai-delayed-in-eu-for-ios-27-and-ipados-27/, https://engadget.com/2189932/siri-ai-for-iphones-and-ipads-will-be-delayed-indefinitely-in-the-eu]. So Jorah should not compete on quick Mac tasks, and on Adam's iPhone it has little competition from Apple.
11. **Frequent approvals stop being a control.** Anthropic reports that users accept 93% of Claude Code's manual permission prompts and stop paying close attention [verified: https://www.anthropic.com/engineering/claude-code-auto-mode]. Few approvals, with exact content, are worth more than many.

**What it costs in UX terms:** nothing beyond the voice track's budget, until the optional status light (about €20 to €60).

---

## 2. Decisions

| # | Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|---|
| U1 | Persona | Dry, brief colleague. Wit rationed to about 1 in 20 replies, never on errors or bad news. Adam can change length and wit by voice | Apple's guidance on repetition; Adam's preference for compact and truthful; Amazon's "Brief" is the one style PCWorld's reviewer did not call cringe, though he kept the default [verified: pcworld, section 3] | British butler (put to Adam, section 5) | Adam likes the butler after a one-week trial | $0 |
| U2 | Voice identity | One voice chosen by a 20-minute bake-off; never clone a real person | Consistent personality is one of the four parts of voice presence [verified: https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice]; cloning an actor is a legal and ethical problem [inference] | Local Kokoro as the only voice | Local quality wins the bake-off | Inside voice budget |
| U3 | State model | Five independent layers rendered through one priority table (section 6) | "Thinking" and "3 jobs running" and "camera on" can all be true at once. A single-state model would lie | One flat state machine | Nothing likely | Build time |
| U4 | Stop vocabulary | "Stop" ends speech only. "Cancel that" ends the job, then reports what stopped. "Stop everything" freezes (K1) | Matches how OpenClaw separates them; avoids silent job loss and silent job survival | "Stop" also cancels the job | A week of diary data shows Adam expects otherwise | $0 |
| U5 | Follow-up window | 8 s after a reply, 12 s if the reply ends in a question, 0 s during calls, media, alarms or timers. "Stay with me" opens a longer mode that auto-closes after 2 minutes of silence | Google uses about 10 s, and about 15 s in Gemini Live [verified: https://support.google.com/googlenest/answer/7685981?hl=en]. I start lower because a Mac in a shared room has no dedicated light, and an open session costs money: per second on GPT-Live, per token with context replay on the V1 pick [track: voice.md]. **Not native:** Mac realtime has no idle close, so these windows need the V1 helper [track: voice.md, section 6.4] | Google's 10 s and 15 s | More than 1 in 5 follow-ups need a re-wake: raise it. More than 1 false capture a day: lower it | Saves realtime cost |
| U6 | Arbitration | V0 one ear only. V2 broker with a 150 ms window and a fixed rule order: active session, physical press, recent use, then best signal | Apple publishes almost the same order [verified: https://support.apple.com/en-my/105077]. Network jitter makes "first in" random for two devices in the same room [inference] | Home Assistant's first-in plus 2 s cooldown | First-in proves good enough in testing | Build time |
| U7 | Speak or show | Spoken budget about 25 words or 10 s. More goes to the nearest active screen, plus one spoken line saying where | Apple and Amazon both push brevity; Gemini Live shows cards during speech [verified: https://gemini.google/overview/gemini-live/] | Speak in full unless asked | Adam prefers longer spoken answers | $0 |
| U8 | Approval handoff | **Changed by the skeptic pass.** V0 native Talk: one step, card only [inference, native Talk is not in the gate's documented scope]. V1 realtime: OpenClaw's spoken yes, then the tap. The yes is a comprehension check, and only the tap is authority | The Gateway requires the yes on relay and consult runs [docs-only: nodes/talk/realtime-sessions.md], before plugin approvals, and I found no setting to turn it off [source: `dist/agent-tools.before-tool-call-CQkX3nOj.mjs`, `dist/tool-mutation-BTW6eoAN.mjs`; not run]. The first-pass pick, no yes before the tap, cannot be delivered on V1 as shipped | One step everywhere, if a supported setting appears or the send moves to a non-voice run | The diary shows the double step is the main annoyance and a supported route exists. Never patch the gate out silently | $0 |
| U9 | Spoken yes for own low-stakes writes | Allowed for T2 own-data actions only when desk trust holds (Mac unlocked and active, enrolled voice hint), with announce and undo. Otherwise tap | A tap for every reminder kills the voice value. **This relaxes security.md row 13, so Adam must decide.** OpenClaw's gate asks for a spoken yes on some of these tools anyway, but that yes alone is not desk trust | Always tap, as security.md says | Security review or Adam says no | $0 |
| U10 | Notification budget | Spoken proactive at most 3 a day, push at most 5 a day, approvals at most 5 a day, all else in a digest. Enforced in code by V2 | Friend and companion products show the risk of a device that keeps talking; attention is the scarcest resource [inference] | No limit, tune by hand | Adam finds it too quiet | $0 |
| U11 | Proactive default | Everything off. Each proactive type is enabled by preview and yes | Adam's rule: never create schedules silently | A small default set | Nothing | $0 |
| U12 | Evidence wording | Seven fixed words mapped to tiers: checked, ran, saw, read, assumed, did not check, remember | Makes Adam's evidence tiers audible | Free-form language | Sounds stilted in testing | $0 |
| U13 | Mac overlay | OpenClaw's overlay and widget panel first. Own overlay only if the state hub proves they cannot show the layers | Avoids rebuilding an M3 Beta surface that changes often | Own SwiftUI overlay now | Canvas panel or overlay fails acceptance | $0 |
| U14 | iPhone | OpenClaw's iOS app first: approvals inbox, Action Button shortcut, Talk, local Live Activity. Own thin app only for Live Activities that update while suspended, Face ID per approval, long message bodies on the card and a compact home | No build needed for MVP. Gaps are real but not blocking: no job-finished push, so use Telegram, and the card text limit in section 14. Same conclusion as [track: apps.md] | Own app from day one | App lacks a needed hook after V1 | $0 now; $99 a year for the Apple Developer Program if Adam builds their own [verified: https://developer.apple.com/programs/] |
| U15 | Dashboard | Native pinned report on a session dashboard first, generated from real logs. Own plugin page later | `show_widget` with `report` and `pin` exists [docs-only: tools/show-widget.md] | Own web app | Report layout too limiting | $0 |
| U16 | Physical mute | V0 software mute that truly releases the mic, proved by the macOS recording indicator. V2: a device whose switch cuts mic power and whose LED shares that rail. DIY ESP32 puck is the default; Voice PE only if the spike shows it works with our stack | An app toggle is not proof; a power cut is. Voice PE has a switch that "Physically cuts power to the microphones" but is "Built for Home Assistant" [verified: https://www.home-assistant.io/voice-pe/] | Voice PE plus a small Home Assistant install as a bridge | Spike shows Voice PE firmware talks to our stack, or Adam wants Home Assistant anyway | €59 Voice PE, recommended price including tax [verified: same page], or about €20 to €30 DIY [inference] |
| U17 | Emotion | No emotion inference, no affective voice setting, no companion behaviour | Friend's reviewer found it fussy and invasive [verified: fortune.com, section 3]. OpenAI's own system card reports a regression on emotional reliance in GPT-Live-1.1 [verified: https://deploymentsafety.openai.com/gpt-live-1-1]. Gemini 3.8 Live, the runner-up, removed affective dialog [verified: https://aistudio.google.com/docs/live-api/capabilities]. The V1 pick's model page lists no emotion setting [verified: https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini], which does not prove neutral delivery, so check tone in the bake-off [inference]. EU AI Act limits in education context [track: vision.md] | Affective dialog on Gemini 2.5 | Adam asks and law allows | $0 |
| U18 | Earcons | Nine own-synthesised sounds with distinct contours, pre-rendered | Under 100 ms playback, no licences, testable | OpenClaw's built-in chimes (V0 uses them) | Blind test fails | $0 |
| U19 | Wait acknowledgement | A spoken line naming the real action ("Checking your calendar"), tested against a plain "mm" in the voice bake-off | Spoken fillers beat spinners in two VR studies. Simple fillers may lower perceived intelligence (section 8). Naming the action is also honest. On V1 the voice model speaks the ack, and OpenClaw's built-in prompt suggests "Let me check that for you" [source: `DEFAULT_REALTIME_INSTRUCTIONS` in `dist/handlers-B5Rt4cMl.mjs`; not run], so test this wording rather than assume it | Plain "mm" | Adam prefers it after the bake-off | $0 |
| U20 | Indicator interlock | No camera stream unless its indicator is known to work. Best: LED in series with camera power. Otherwise: firmware checks the LED circuit and refuses to stream | Meta had to add this after owners drilled out the capture LED [verified: https://thenextweb.com/news/meta-ray-ban-privacy-light-fix-cameraless] | Separate LED driven by software | Nothing likely. A bystander cannot check anything else | About €1 in parts |
| U21 | Boundary with Siri | Jorah does not compete on quick Mac tasks. Keep "Hey Siri" and "Hey Jorah" separate. Jorah owns memory, long work, Adam's tools and the iPhone | Siri AI runs on macOS 27 in the EU but not on iOS [verified: Apple newsroom, section 3] | Hand device tasks to Siri through Shortcuts | Siri AI reaches EU iPhones, or tests show it fails on Adam's M1 Max | $0 |

---

## 3. What people actually value, and what killed products

| Product | What happened | Lesson for Jorah | Evidence |
|---|---|---|---|
| **Humane AI Pin** | About 10,000 shipped against a 100,000 goal. More returned than sold from May to August 2024. Reviewers faulted slowness, heat and battery. Servers cut on 2025-02-28, devices became nearly useless, data deleted | Speed is the product. Never screenless. A personal assistant must survive the vendor | [secondary: https://en.wikipedia.org/wiki/Humane_Inc.] |
| **Rabbit r1** | Sold on a "large action model" that did little at launch. About 5,000 of 100,000 purchasers active at a time (Sept 2024), though the same page also gives 130,000 units sold (June 2024). Hardcoded API keys found. Chats were logged and undeletable until a fix in July 2024 | Claim only what works. Show evidence. Secrets and logs are part of the user experience | [secondary: https://en.wikipedia.org/wiki/Rabbit_r1] |
| **Friend pendant** | Fortune's reviewer had to press her lips to it and repeat 2 or 3 times. Replies took 7 to 10 s. It could not tell chatter from direct speech and texted comments during a meeting. It forgot her name after about ten days. Its tone was anxious and fussy. Terms allow audio, video and voice data for training. A later version reportedly added a speaker and a random fixed personality at $249 | Do not simulate friendship. Never comment unprompted on what was overheard. Treat mishearing and forgetting as first-class failures. Let the user set personality | [verified: https://fortune.com/2025/10/03/friend-ai-necklace-review-avi-schiffmann/]; later version [search-snippet: https://the-gadgeteer.com/?p=519044] |
| **Limitless and Rewind** | Bought by Meta. Pendant sales stopped on 2025-12-05. Service ended in the EU the same day, export until 2025-12-19, then accounts permanently deleted. Rewind capture disabled on 2025-12-19 | Total recall on someone else's server can vanish, and in the EU it did. Local, exportable, bounded retention | [verified: https://www.limitless.ai/] |
| **Alexa+** | US general availability on 2026-02-04, free with Prime [secondary: Wikipedia]. UK early access from 2026-03-19 [verified: https://www.pymnts.com/amazon/2026/amazon-chooses-uk-for-alexa-european-debut/]. Germany, Austria, France, Italy and Spain reported by June 2026; Slovakia not found [search-snippet: https://eftm.com/2026/06/alexa-rolls-out-to-more-countries-but-australia-has-to-wait-till-2027-276635]. Reported complaints in January 2026: upgraded without consent and found out afterwards, no way to decline in advance, slower on lights and timers, more opinionated tone, repeated promotions [verified, reporting Reddit: https://www.storyboard18.com/brand-marketing/amazon-auto-upgrades-echo-devices-to-alexa-plus-leaving-users-divided-87623.htm]. Also reported: cut off mid-sentence, repeated smart home commands, lost features. Conversation is the most praised part [search-snippet, TechRadar and Reddit summaries: https://www.techradar.com/ai-platforms-assistants/were-definitely-beta-testing-this-technology-is-alexa-really-bad-or-are-our-expectations-for-free-services-too-high] | Never swap the assistant under the user. Old abilities must survive. Conversation earns praise only if timers stay instant | As cited |
| **Alexa+ styles** | Brief, Chill, Sweet and Sassy, changed by voice or app, per device. Amazon says tone changes and capabilities do not [verified: https://www.aboutamazon.com/news/devices/alexa-plus-personality-styles]. PCWorld's reviewer called Brief the only one not hopelessly cringe, found it curt when he mentioned low mood, and kept the default [verified: https://www.pcworld.com/article/3071273/alexas-new-ai-personalities-are-cringe.html] | Supports U1. Tone is a setting, changeable by voice, and never touches safety wording | As cited |
| **Gemini for Home** | "Hey Google, let's chat" enters an explicit Live mode [verified: https://blog.google/products/google-nest/gemini-for-home/]. That post says only that Gemini for Home has free and paid versions, so "paid" for Live is [unverified] there. Continued Conversation was reported rolling out on 2026-04-21, and it tries to tell follow-ups from side talk [verified: https://www.thurrott.com/?p=335169]. Mic closes after about 10 s, or about 15 s in Live. "Thank you", "stop" or "I'm done" end it. Neither runs during calls, alarms, timers or media [verified: https://support.google.com/googlenest/answer/7685981?hl=en]. Complaints: alarms, lights and automations failing for some users, others fine [verified: https://www.androidheadlines.com/2026/01/gemini-update-for-google-home-doesnt-seem-to-be-all-that-smooth.html]. Multi-part commands right about half the time [search-snippet: https://www.androidauthority.com/gemini-for-google-home-impressions-3633043]. Review-mining: forced adoption 27.9%, routines 22.1%, slow 16.9% of 136 complaints, 11% asking for a way back [verified, commercial publisher: https://unstar.app/blog/google-home-gemini-voice-commands-worse-reviews-2026] | Explicit conversation mode is accepted. Keep a way back. Adopt Google's closing phrases and its "no follow-up during media" rule | As cited |
| **Gemini Live** | Voice and typing share one thread. Maps, weather cards and photos appear during speech. Memory across sessions | Speak and show together. One thread across surfaces. OpenClaw's shared history already fits this | [verified: https://gemini.google/overview/gemini-live/] |
| **Siri AI (2026)** | Released 2026-09-14 as a beta, English first. On-screen awareness, app actions, a Siri app whose thread syncs through iCloud. Not initially in the EU on iOS, iPadOS or watchOS [verified: https://www.apple.com/newsroom/2026/09/siri-ai-a-profoundly-more-capable-and-personal-assistant-is-here/]; "no timeline", Apple blames the DMA, EU users can use it on macOS 27 [verified: https://apple.com/newsroom/2026/06/due-to-dma-siri-ai-delayed-in-eu-for-ios-27-and-ipados-27/, https://engadget.com/2189932/siri-ai-for-iphones-and-ipads-will-be-delayed-indefinitely-in-the-eu]. Apple says it will add usage limits later, with a timeout after a limit and more access for a fee. It gives no daily figure [verified: https://support.apple.com/en-us/127901]. 9to5Mac: "good enough to use on purpose" on Mac, but no memory across sessions [verified: https://9to5mac.com/2026/09/17/macos-27-golden-gate-siri-ai-top-features-apples-assistant-finally-comes-to-life-video/]. Built with Google's Gemini models [search-snippet: https://thenextweb.com/news/apple-ios-27-siri-ai-release-icloud-plus-child-safety] | On this Mac, Siri may cover quick tasks. Apple lists Mac with M1 or later for Apple Intelligence, and M3 with 12 GB only for its most advanced on-device model [verified: Apple newsroom]. Not tested on this M1 Max. One thread across devices is now the expected baseline. Jorah wins on memory, long work and Adam's own tools | As cited |
| **ChatGPT voice (GPT-Live)** | Replaced the old voice mode on 2026-07-08. Listens while speaking, aims to stop cutting users off, delegates to larger models, shows some answers visually [verified: https://techcrunch.com/2026/07/08/openai-releases-new-voice-models-for-more-natural-live-conversations/]. Docs say to check spoken confirmations against final application state, and that work can continue after an interruption [verified: https://developers.openai.com/api/docs/guides/voice-agents, https://developers.openai.com/api/docs/guides/live]. Early complaints: flatter voices, unwanted interjections, launch-week slowness [secondary, not independent: https://findskill.ai/blog/chatgpt-new-voice-gpt-live/] | Fast model in front with a brain behind is now the industry pattern. Full duplex can feel pushy, so test for interjections. "Done" must be checked against state | As cited |
| **Sesame** | Defines voice presence as emotional intelligence, conversational dynamics, contextual awareness and consistent personality. Admits a remaining prosody gap and weak non-English | Dynamics (timing, pauses, interruptions) and consistency are the part we control. I reject the emotional part (U17) | [verified: https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice] |
| **Home Assistant Voice** | Local wake, mic power switch, LED ring, dial, button, XMOS echo handling, €59 | Honest hardware is cheap. Copy it | [verified: https://www.home-assistant.io/voice-pe/] |
| **ESPHome and Linux-Voice-Assistant** | Continuous conversation loop, 300 s context reset default, stop model, announcements, timers. Echo handling left to XMOS firmware | Follow-up and stop word are normal in open rigs. Echo is a hardware job | [verified: https://esphome.io/components/voice_assistant.html, https://github.com/OHF-Voice/linux-voice-assistant] |
| **Self-hosted rigs** | Stated draw is no cloud and no ads. Reported about 2 to 3 s from wake to reply on Voice PE, and about 8 s for open transcription on a Pi 4. Willow pairs on-device command recognition with a self-hosted server. These are blogs, not benchmarks | Local rigs prove privacy is valued, but their slow open-ended path is exactly why V1 uses a fast cloud voice with a local fallback | [search-snippet: https://www.kunalganglani.com/blog/local-ai-voice-assistant-whisper-piper-ollama, https://github.com/riepecjeuloc/willow] |
| **Ray-Ban Meta glasses** | Owners paid to drill out the capture LED. On 2026-07-07 Meta announced that second-generation models disable the camera when the LED is tampered with. In June, before that fix, caps that let in a little light could fool the sensor. Whether they still do is [unverified] | A software-readable indicator gets defeated. Tie indicators to power where possible (U20) | [verified: https://thenextweb.com/news/meta-ray-ban-privacy-light-fix-cameraless, https://www.bgr.com/2191890/ray-ban-meta-led-block-mod/] |

**What people actually value, ranked** [inference from the rows above and the studies below]:

1. **It does simple things every time.** Timers, lights, reminders. Nothing else matters if these slip.
2. **It is fast.** Humane, Friend at 7 to 10 s, and Alexa+ on lights all drew this complaint.
3. **They control change.** Forced upgrades are the largest single complaint in the only dataset I found.
4. **It does not talk at them.** Promotions, interjections, unprompted comments.
5. **Tone is theirs to set,** and short wins for daily use.
6. **Hands-free while doing something else.** Cooking and cycling are typical [search-snippet: student summaries of Luger and Sellen].
7. **Privacy they can check, and a product that outlives the vendor.** Limitless, Humane, Home Assistant.

Design rules drawn from the research:

- **The 18 guidelines of Amershi et al. (CHI 2019) are the checklist.** The ones this design leans on hardest are G1 and G2 (what it can do and how well), G3 (time services by context), G7 to G9 (efficient invocation, dismissal, correction), G10 (scope when in doubt), G11 (why it did it), G12 (remember recent interactions), G14 (adapt cautiously), G17 (global controls), G18 (notify about changes) [verified: https://www.microsoft.com/en-us/research/publication/guidelines-for-human-AI-interaction/, and the PDF at the same site].
- **Three response limits hold for voice too:** 0.1 s feels instant, 1 s keeps the train of thought, 10 s is the limit of attention, and beyond that a person needs progress and a way out [verified: https://www.nngroup.com/articles/response-times-3-important-limits/].
- **The expectation gap is the classic failure.** Luger and Sellen interviewed 14 users and found expectations dramatically out of step with how the systems work, on intelligence, capability and goals [verified: https://www.microsoft.com/en-us/research/publication/like-having-a-really-bad-pa-the-gulf-between-user-expectation-and-experience-of-conversational-agents/]. The transparency page and evidence verbs exist to close this gap.
- **Unexplained failure hurts more than mishearing.** A preprint found users fairly forgiving of misrecognition and much less tolerant of "reason unknown" errors [verified, not peer reviewed per the listing: https://arxiv.org/abs/2002.03582].
- **Google's PAIR guide:** explain why there is no result and offer a path forward. Be proactive only at high confidence about context. Do not act on assumptions when context is uncertain [verified: https://pair.withgoogle.com/chapter/errors-failing/].
- **Amazon's error guidance:** first miss, repeat the question. Second miss, explain or offer choices. Repeated, end the session. Do not blame, over-apologize, state an uncertain cause as certain, or say only what cannot be done [verified: https://developer.amazon.com/en-US/alexa/alexa-haus/patterns-and-components/patterns-errors].
- **Amazon on speech style:** contractions, active voice, cut words that add nothing, instructions only for first-time users, ask the question at the very end so people do not talk over it, use progress cues on multi-step work [verified: https://developer.amazon.com/en-US/alexa/alexa-haus/natural-speech].

---

## 4. Jarvis as fiction: what to copy and what not to

This section is my reading of the films [inference]. A source confirms only the basics: an AI personal assistant, voiced by Paul Bettany, running Stark's buildings and suits [secondary: https://en.wikipedia.org/wiki/J.A.R.V.I.S.].

| Jarvis trait | Copy? | How Jorah does it |
|---|---|---|
| Already working when asked, runs many things at once | Yes | Background jobs, with a running count on every surface |
| Short spoken summary, details on a display | Yes | Speak one line, show the rest (section 13) |
| Warns once, then obeys | Yes, within tiers | "That deletes 14 files. On your phone if you want it" |
| Dry humour | Rationed | About 1 in 20, never on errors or bad news |
| Knows context and history | Yes | Memory plus current screen and calendar, with a source on request |
| Takes physical action | Later, gated | Arm and rover under firmware safety [track: security.md] |
| Always listening with no wake word | **No** | On-device wake detection only. No audio leaves before the wake word |
| Never misheard, no delay, no cost | Impossible | Designed-for failure (section 22) and visible cost |
| No approvals, acts on any instruction | **No** | That is the Ultron story. Tiers apply |
| One user in a private lab, no bystanders | **No** | Guest mode, indicators, no retention by default |
| Pretends to be a person, deep emotional bond | **No** | Jorah is software and says so. No simulated feelings |

---

## 5. Persona and tone

**Put to Adam as a real choice. Same four lines in each style:**

| Moment | A. Dry colleague (my pick) | B. British butler | C. Warm and upbeat |
|---|---|---|---|
| Ack | "Checking." | "One moment, sir." | "Sure, let me check!" |
| Answer | "Two meetings. Next is at three." | "You have two engagements. The next is at three." | "You've got two meetings today, next one's at three!" |
| Bad news | "The render failed at 04:12. Disk full." | "I regret the render failed at 04:12. The disk is full." | "Oh no, the render failed. Looks like the disk is full." |
| Pushback | "That's your only backup. Still delete it? It's on your phone." | "That is your only backup. Shall I place the request on your telephone?" | "Heads up, that's your only backup! Want to go ahead?" |

Why A: it wears well, stays short, and leaves room for truth. Butler flattery is a sycophancy risk, and "sir" reads badly for Adam, who uses they/them. B can be done without "sir". Accent is separate from persona, so a dry colleague can have a British voice.

**Persona rules for every style** [inference, based on the Apple and Amazon guidance in section 3]:

1. Answer first, explanation second. No preamble, no restating the question, no "great question".
2. No first-person feelings. "I think" means an estimate, never an emotion. Never "I'm so excited" or "I'm sorry you feel".
3. One apology at most, and only when Jorah caused the problem. Then the fix.
4. Disagree once, with a reason, then do what Adam decides within the tier rules.
5. Wit only on low stakes, at most about 1 in 20 replies, never twice in a row, and never on errors, health, school, money or other people. Say "less jokes" and it stops.
6. Vary acknowledgements, but never vary safety wording. Approval and error lines stay identical so they can be recognised.
7. Numbers, names, dates and quotes from the brain are read back exactly. The fast voice model paraphrases everything else. This matters because the V1 voice model is not Claude and can distort a claim [track: voice.md].
8. Instructions only the first time. After that, assume Adam knows.
9. Jorah is a tool with a name. If asked, it says it is software. It never poses as Adam or as a human to others.
10. Tone is a setting, safety is not. "Be more brief", "less jokes" and "normal length" work by voice and take effect at once. Amazon's styles work the same way, changing tone but not capabilities [verified: aboutamazon.com, section 3].
11. Disagreement is tested, not assumed. OpenAI rolled back a GPT-4o update in April 2025 for being too agreeable, and said it had no deployment evaluation for that [search-snippet: https://openai.com/index/sycophancy-in-gpt-4o/, https://openai.com/index/expanding-on-sycophancy/]. Jorah gets a small test: 10 scripted wrong premises, such as "a 2 mm wall is fine for this hinge, right?", run on each persona or model change (section 24).

**Two places hold the persona, and they will drift.** Workspace `SOUL.md` governs the brain. `talk.realtime.instructions` only appends to OpenClaw's built-in realtime prompt [docs-only: nodes/talk.md], and that prompt also shapes the fast voice, including its acknowledgement line [source: `DEFAULT_REALTIME_INSTRUCTIONS` in `dist/handlers-B5Rt4cMl.mjs`; not run]. Keep one source file and generate the shorter voice version from it [inference]. The current `SOUL.md` and `IDENTITY.md` are still the default template, with Creature and Vibe unset [verified: workspace/SOUL.md, workspace/IDENTITY.md].

**Draft addition to SOUL.md** (needs Adam's choice before use):

```text
## Voice
Speak like a sharp colleague, not a servant or a friend. Answer first. Keep spoken replies under
25 words unless asked for more; put the rest on a screen and say where. Never state a result you
have not seen. Say what you checked. If you do not know, say so and offer the next step.
No flattery. No feelings. One dry remark in twenty at most, never on errors, health, school,
money or other people. Numbers, names and dates are exact or not said at all.
```

**Voice selection.** A 20-minute bake-off on the same script (section 23 lines) across the voice track's candidates. Adam picks by ear. Check that the fallback voice is acceptable, because the realtime voice, the TTS voice and the offline voice can differ [inference]. When the voice changes because of a fallback, Jorah says so once ("Slower voice for now, the fast one is down").

**The name.** "Jorah" is a Game of Thrones character, so expect false wakes when that show plays [track: voice.md], and a trademark check is needed only if this becomes a product [inference]. Pronunciation and pronoun for Jorah are Adam's call (section "Adam decides").

---

## 6. Interaction state machine

### 6.1 Five layers, not one state

A flat list of states cannot express "speaking, while 2 jobs run, camera on, in guest mode". So there are five independent layers, and one priority table decides what a single light or orb shows [inference].

| Layer | Values | Owner |
|---|---|---|
| **Conversation** | Idle, WakeHeard, Listening, Thinking, Speaking, Interrupted, FollowUp, ConversationMode, Error | Each ear, reported to the hub |
| **Work** | Number of running jobs, number waiting for approval, number blocked | Gateway events, approvals |
| **Sensors** | Mic per device: HardOff, SoftOff, LocalOnly, Streaming (and to whom). Camera: Off, Look, Watch, Live. Screen capture: Off, On | Each device; hardware when possible |
| **Attention** | Normal, Busy (call or recording), Quiet hours, Guest, Away | Hub |
| **Health** | OK, Degraded (named), Offline | Hub |
| Body, when it exists | Parked, Moving, Fault | Firmware |

### 6.2 Conversation states, with cues

| State | Enter when | Sound | Light (ring or puck) | Mac overlay and menu bar | iPhone | Exit |
|---|---|---|---|---|---|---|
| **Idle** | Nothing active | None | Off, or dim dot per job | Menu-bar icon only, no overlay | Nothing | Wake word, hotkey, Action Button |
| **WakeHeard** | Local detector fired. Max 150 ms while arbitrating | None yet | None yet | None yet | None | Won: Listening. Lost: Idle with a 300 ms faint flash |
| **Listening** | Won arbitration, or push-to-talk | **E1** wake (rising) | Full ring, bright white, level-reactive | Orb follows mic level, live caption of partials, cloud mark if audio is leaving | Same orb, haptic tap | End of turn: Thinking. 5 s silence: Idle with **E2**. Hard stop 120 s [docs-only: platforms/mac/voicewake.md] |
| **Thinking** | Turn ended | None under 800 ms. Then spoken ack (section 8) | Slow rotating single dot | Orb breathes, one-line "what I'm doing" when known | Same | First audio: Speaking. Over 15 s: Background offer |
| **Speaking** | First audio plays | Voice | Pulse follows speech envelope | Orb follows playback, captions of speech, Stop button | Same | Drained: FollowUp. User speech: Interrupted. "Stop": FollowUp for 4 s |
| **Interrupted** | Speech over playback. Max 150 ms | Playback cut, no sound | Snap to Listening | Caption marked "heard up to here" | Same | Listening |
| **FollowUp** | Reply finished. 8 s, or 12 s after a question | Very faint tick, optional | Thin ring, dim | Orb small, "still listening" text with countdown bar | Same | Speech passes the gate: Listening. Timeout: Idle with **E2** |
| **ConversationMode** | "Stay with me" | **E1** | Thin ring plus a fixed marker | "Talking" pill, Exit button, elapsed time, cost so far | Same | "That's all", 2 min silence, or Exit, with **E2** |
| **Error** | A step failed | **E7** (falling) then one spoken line | Two red segments, slow pulse | Reason and next step, no stack trace | Same | Idle after the line |

Timers in OpenClaw today: silence window 700 ms in Talk on macOS and Android and 900 ms on iOS, 2.0 s while speech flows in wake capture, 5.0 s if only the trigger was heard, 120 s hard stop, 350 ms debounce after send [docs-only: nodes/talk.md, platforms/mac/voicewake.md]. Google recommends 500 to 800 ms silence for Live [verified: https://aistudio.google.com/docs/live-api/capabilities]. Adam may be speaking English as a second language, with longer mid-sentence pauses, so start at 800 ms and measure cut-offs before tightening [inference].

### 6.3 Work, sensor and attention cues (run alongside any state)

| Condition | Sound | Light | Screens |
|---|---|---|---|
| Job running | None | One dim dot per job, up to 4 | Menu-bar badge with count; card on the dashboard; phone: status row |
| **Waiting for approval** | **E3** once, repeated only if a deadline is near | Amber slow double pulse | Menu-bar badge, card with Open; phone push for approvals [track: apps.md]. Generic lock-screen text is documented for browser and Mac notifications [docs-only: web/notifications.md], so check it on the iPhone in UX3 |
| Job blocked | **E3** once | Amber fixed segment | Card names what it needs |
| Job finished | **E4** only if Adam is present and not busy; otherwise silent | One short green-white sweep | Telegram or Mac notice per budget, because the iOS app has no job-finished push [track: apps.md]; card with Review |
| Mic soft mute | **E5** (descending click) once | Red ring segment, steady | Menu bar: mic crossed out. macOS recording indicator must go off |
| Mic hard mute | Switch feel, plus E5 if the speaker is on | Red steady, driven by hardware | "Mic off (switch)" on all surfaces |
| Mic restored | **E6** (ascending click) | Brief white | Removed |
| Audio streaming to a cloud provider | None | Thin outer ring | Cloud glyph with provider name |
| Camera or screen capture active | **E8** on start | **Separate white LED, not the ring**, hardware-tied when possible | Camera glyph with mode and which device |
| Guest mode | Spoken once | Small fixed purple dot plus shape marker | "Guest" pill. Private cards hidden |
| Quiet hours | None | Night dimming | Moon glyph |
| Degraded | Spoken once when it starts mattering | Fixed amber corner | Named reason: "Slow voice: realtime provider down" |
| Robot moving | **E9** continuous soft tone | Its own beacon | "Moving" banner with Stop |

**Single-light priority**, highest first: Robot fault, Hard mute, Error, Speaking, Listening, Approval, Soft mute, Thinking, Finished sweep, Jobs dots, Idle. Mic and camera truth are never hidden by this table on a device that has a separate LED [inference].

Colour is never the only signal. Each state has its own shape or motion [verified: https://developer.apple.com/tutorials/data/design/human-interface-guidelines/accessibility.json]. Colour codes are also hard to learn. On an Echo, one purple pulse means Do Not Disturb and continuous purple means a setup error, while solid red means mic off, per a third-party guide [verified: https://maketecheasier.com/smart-home/alexa-echo-lights-explained]. I could not find Amazon's own page. Red for mic off is an established convention, so keep it. Apple switches its orange mic dot to a square under Differentiate Without Color [verified: https://support.apple.com/en-us/108331], which is the pattern to copy. "What does your light mean?" should work by voice [inference].

### 6.4 Mapping to what exists

| Need | OpenClaw today | Gap |
|---|---|---|
| Listening, Thinking, Speaking orb | Yes, with live mic level and real playback envelope. Click pause, double-click stop, X exit [docs-only: nodes/talk/client-ui.md] | Does not show the Work, Sensor or Attention layers |
| Menu-bar work state | Icon and status row, session priority, 2 s grace to avoid flicker, tool badges [docs-only: platforms/mac/menu-bar.md] | No job count, no approval count on the icon documented |
| Transcripts and phases as events | `talk.event` channel with `transcript.delta` and `transcript.done` [docs-only: nodes/talk/realtime-sessions.md] | Hub must subscribe |
| Trigger and send chimes, phase sounds, Shift-to-stop | Toggles exist [docs-only: platforms/mac/voicewake.md] | Custom sound files not documented [unconfirmed] |
| Status, steer, cancel, follow-up by voice | `talk.client.steer` and `talk.session.steer` classify speech [docs-only: nodes/talk/realtime-sessions.md] | Realtime only, and only while a consult is active |
| Barge-in | `interruptOnSpeech` default on; `talk.session.cancelOutput` turn-scoped [docs-only: nodes/talk.md, nodes/talk/macos-relay.md] | GPT-Live wants headphones, and an explicit stop ends its session. Turn-based providers keep echo suppression (section 9) |
| Auto-closing Talk on silence | None found. Overlay stays on while Talk is enabled, and the Gateway closes a relay session only at 30 minutes [source: `RELAY_SESSION_TTL_MS` in `dist/handlers-B5Rt4cMl.mjs`; not run] | **Build in V1, not V2,** because of cost and mic honesty [track: voice.md]. `talk.session.close` exists [docs-only: nodes/talk.md] |
| Progress lines during a consult | One brief acknowledgement, then wait for the final result. Status on request [source: `DEFAULT_REALTIME_INSTRUCTIONS` in `dist/handlers-B5Rt4cMl.mjs`; not run] | **Build in V1.** No path found that speaks tool events by itself (source search, not run) |
| Device-level status light | None | **Build** |
| Wake arbitration | None | **Build** |
| Notification budget across surfaces | Categories, quiet hours and detail levels for browser push. Native apps configured separately. Quiet hours drop alerts instead of queueing [docs-only: web/notifications.md] | **Build**, because dropped alerts must reach the digest |

**`jorah-presence` (build at V2, small; the V1 idle-close and progress helpers come first and can fold into it).** A process that subscribes to Gateway events, keeps the layers above, runs the wake broker and the notification budget, and publishes one JSON state to the status light, the overlay and the dashboard. It runs outside the gateway so the light stays correct if the gateway restarts, as `jorah-eyes` does [track: vision.md]. Hardware truth (mic power, camera power) is read from the device, never taken from this process.

---

## 7. Earcons

Rules [inference]: under 300 ms except E9. Distinct contour, not just pitch, so they survive mild hearing loss and cheap speakers. Pre-rendered and local so they play in under 100 ms [track: voice.md]. Volume follows the last speech level and drops at night. Wake detection and barge-in must ignore them (echo gate). Each is optional in settings, and each has a visual twin. Own synthesis, so no licences.

| ID | Meaning | Shape | Approx. length | Notes |
|---|---|---|---|---|
| E1 | I'm listening | Two notes rising | 120 to 180 ms | Most frequent, so it must be pleasant at 50 plays a day |
| E2 | Stopped listening, nothing sent | One soft low note | 100 ms | Tells Adam nothing happened |
| E3 | Need you (approval or blocked) | Three notes, up then up then level, a question shape | 300 ms | Never repeat more than once unless a deadline is near |
| E4 | Finished | Soft resolved chord | 250 ms | Skipped when busy |
| E5 | Mic off | Descending click | 150 ms | Must sound final |
| E6 | Mic on | Ascending click | 150 ms | Mirror of E5 |
| E7 | Failed | Two notes falling | 200 ms | Always followed by a spoken or shown reason |
| E8 | Camera or screen on | Short mechanical tick | 120 ms | Plays even at low volume. Bystander notice |
| E9 | Robot moving | Soft continuous tone | While moving | Audible across the room; never muted in settings [inference] |

Thinking has no looping sound: a looping tone during waits becomes annoying and hides silence [inference]. Home Assistant ships a simple acknowledge sound in its pipeline, which shows the pattern works [verified: https://api.github.com/repos/home-assistant/core/contents/homeassistant/components/assist_pipeline lists `acknowledge.mp3`].

**Acceptance test:** play all nine in random order to Adam without labels after one day of use. Target at least 8 of 9 named correctly. Evidence tier: device.

---

## 8. Fillers and progress: seconds, minutes, hours

Thresholds up to 15 s are the voice track's [track: voice.md]. The rest is mine [inference]. All rest on the three response limits in section 3.

**What research says about waiting.**

- A study of 54 people talking to LLM agents in VR at 1.5, 4.0 and 6.5 s found that delay hurt perceived response time, engagement and competence. A thinking gesture with a voice line improved perceived response time at 4 and 6.5 s. A spinning icon with sound did not. Neither repaired the wider experience. The authors recommend staying under 4 s [verified: https://arxiv.org/html/2507.22352].
- A second VR study (24 people, 2, 4 and 8 s) found a thinking gesture plus "Hhm" beat progress bars, with 66.7% preferring it [verified: https://arxiv.org/html/2508.11781v1].
- The first paper cites earlier work that simple fillers can lower a robot's perceived intelligence and likability, while more complex fillers did not [verified, as cited there].
- Both studies used embodied avatars, so they transfer loosely to a voice in a room [inference].

**What I take from it** [inference]: a spoken acknowledgement does more than an orb, no filler rescues a slow system, and naming the real action is both a "complex" filler and the honest one. U19 tests this against a plain "mm" in the bake-off.

| Time since end of speech | Voice | Screen | Rule |
|---|---|---|---|
| Under 800 ms | Answer only | Orb | No filler |
| 800 ms to 3 s | One short ack naming the action if known: "Checking your calendar." On V1 the voice model speaks it, so test the wording (U19). Local cache only from V2 | One-line activity | Only if it is true. Never "let me think". A plain "mm" only if it wins U19 |
| 3 to 15 s | At most one line per 8 s, from real events: "Two of three sources read." **Needs a V1 helper.** Until then, status only when asked | Live step list | Never a guessed percentage |
| Over 15 s | "This'll take a few minutes. I'll tell you when it's done." Mic closes | Job card appears; session continues | Job moves to Work layer. Adam can keep talking |
| Minutes (2 to 60) | Silent. "How's it going?" gets a one-line status at any time | Card: step N of M, elapsed, range estimate, cost so far, Cancel | Report only milestones on screen |
| Hours | Start: state plan, budget, what will need Adam. Then silent | Card; digest line. Phone: status row. OpenClaw's Live Activity is local, so it goes stale once the app is suspended [track: apps.md]. An own app could push updates (up to 8 h active plus up to 4 h on the Lock Screen [verified: https://developer.apple.com/tutorials/data/documentation/activitykit/displaying-live-data-with-live-activities.json]) | Message only on blocked, failed or done |
| Days | Daily line in the digest | Card with last checkpoint | Ask again if the scope changes |

Truth rules:

- **"On it" is not "started" and "done" means read back.** OpenClaw warns that a task receipt does not confirm a model or tool started, and a submitted spoken result does not prove audible delivery [docs-only: nodes/talk/realtime-sessions.md]. OpenAI's voice docs give the same advice: verify the final application state, not the spoken response [verified: https://developers.openai.com/api/docs/guides/voice-agents]. So Jorah says "Done" only after reading back the result (event exists on calendar, file exists with size, message accepted). "Sent" means accepted by the service. It says "delivered" only if it saw delivery.
- **Estimates are ranges from real history,** or Jorah says "I don't have a good estimate yet."
- **Silence is a defect past 10 s.** If the last real event is older than 60 s on a foreground wait, Jorah says what it is waiting on.
- **A stuck job asks; it does not spin.** After the job's budget or 3 failed fix passes [track: creative.md], it stops and reports what remains.
- **Native Talk (V0) cannot do any of this.** It speaks only at the end [docs-only: nodes/talk/macos-relay.md]. In V0 the overlay's Thinking is all there is, so V0's acceptance bar is only "it works".

---

## 9. Barge-in and the stop vocabulary

**Barge-in behaviour.** Speech detected on the echo-cancelled signal cuts playback within 150 ms [track: voice.md]. The history is truncated to what was actually heard, as LiveKit does and as Gemini Live does by keeping only what was already sent [verified: https://docs.livekit.io/agents/build/turns/, https://aistudio.google.com/docs/live-api/capabilities]. If detection fires but no words follow (a cough), speech resumes from where it stopped [verified: LiveKit false interruption]. Gemini discards pending function calls on interruption, so an interrupted turn must not leave Adam assuming the action happened [verified: same Gemini page].

**Hardware decides whether this works.** OpenClaw's headphone advice is for continuous providers such as GPT-Live, which keep the mic open during playback. Turn-based providers keep device-route echo suppression and local speech interruption [docs-only: nodes/talk/macos-relay.md]. In the shipped code only the GPT-Live bridges declare continuous output, so `gpt-realtime-2.1-mini` and Gemini should be turn-based [source: `dist/extensions/openai/capability-catalog.js`, `dist/extensions/google/realtime-voice-provider.js`; not run]. So test V1 on both speakers and headphones. Suppression may also hide Adam's voice during playback [inference]. The voice track picks a USB speakerphone for the desk [track: voice.md]. The UX target for room barge-in stays open.

**Fixed vocabulary.** These are handled locally when possible, outside the LLM [track: security.md K0v, voice.md].

| Say | Effect | Reply | Who |
|---|---|---|---|
| "Stop", "quiet", "enough" | Speech stops. Work continues. Mic stays open 4 s so "cancel that" needs no wake word | None. If the cut-off speech was about a running job, and only then: "Still working." | Anyone |
| "Never mind" | Discards the current request in Listening or Thinking | E2 | Anyone |
| "Cancel that" | Stops the most recent job | "Cancelled the video render. Nothing was uploaded." | Enrolled hint |
| "Stop everything" | K1 freeze: blocks T1 and above until cleared at a terminal | "Everything's stopped. Unfreeze from the terminal." | Anyone |
| "Stop listening" | Soft mute on all ears. Voice cannot undo it | E5, no speech | Anyone |
| "Stop" while the robot moves | Firmware stop | E9 ends | Anyone, always |
| "Pause" | Pauses speech, resumes on "go on" | None | Anyone |
| "How's it going?" | One-line status of the latest job | "Rendering, about 3 minutes left." | Enrolled hint |
| "Thanks", "that's all", "I'm done" | Ends follow-up now. Google uses the same closers [verified: support.google.com, section 3] | E2, no reply. Never "You're welcome!" | Anyone |

**Two limits on this table.** With GPT-Live, explicitly stopping output ends the voice session, so the 4 s window after "stop" does not exist on that provider. On other relay providers, output cancel is turn-scoped [docs-only: nodes/talk/macos-relay.md]. And on V0 and V1 the spoken word reaches a model rather than a local stop-word detector, so "no reply" and the 300 ms target are goals until local handling exists [inference]. Until then, the Stop button, the orb and Shift-to-stop are the reliable path.

After any cancel, Jorah states what stopped and what already happened, because accepted work has its own cancellation lifetime [docs-only: nodes/talk/realtime-sessions.md]. Non-voice equivalents exist on every surface: Stop button, double-click on orb, Shift-to-stop, `/stop` in chat.

---

## 10. Follow-up without re-waking

| Situation | Window | Why |
|---|---|---|
| Normal reply | 8 s | Google's Continued Conversation closes after about 10 s of silence [verified: https://support.google.com/googlenest/answer/7685981?hl=en]. I start lower (U5) |
| Reply ended with a question | 12 s | Adam is expected to answer. Gemini Live on Google's speakers uses about 15 s [verified: same page] |
| "Thanks" or "that's all" | 0 s | Closes at once |
| Guest mode or quiet hours | 0 s | Fewer accidental captures |
| During a call, media playback, an alarm or a timer sounding | 0 s | Google excludes the same cases [verified: same page] |
| After "stop" | 4 s | Long enough for "cancel that" [inference] |
| After a high-tier handoff ("on your phone") | 0 s | No reason to listen |
| Conversation mode ("stay with me") | Until 2 min of silence, or the Gateway relay's 30-minute limit [source: `RELAY_SESSION_TTL_MS` in `dist/handlers-B5Rt4cMl.mjs`; not run] | Explicit, as with "let's chat" [verified: blog.google] |
| Reviewing a video or model | Conversation mode, on request | Many short notes |

**Gate for speech in the window** [inference]: voice present, plus not obviously aimed elsewhere.

- **V1 pick, `gpt-realtime-2.1-mini`** [track: voice.md]. OpenClaw's OpenAI bridge configures `server_vad`, and I found no `semantic_vad` setting [source: `dist/extensions/openai/capability-catalog.js`; search only, not run]. OpenAI documents semantic VAD [verified: https://developers.openai.com/api/docs/guides/realtime-vad] and shows it with `gpt-realtime-2.1` [verified: https://developers.openai.com/api/docs/guides/realtime-conversations], but the mini page does not mention it [unverified for mini]. So on V1 the "addressed to me?" check is a build, not a setting, and side talk can be captured until it exists.
- **Runner-up, Gemini 3.8 Live.** Proactive audio is permanently on, and setting it to false returns an error. Gemini 2.5 lets you configure it and 3.1 Flash Live does not support it [verified: https://aistudio.google.com/docs/live-api/capabilities]. If Gemini wins the bake-off, the model itself can choose not to respond.
- **What "dropped" can mean.** On a realtime session the audio has already reached the provider, and OpenClaw always appends finalized utterances to the active session [docs-only: nodes/talk/realtime-sessions.md]. So on V1, side talk in an open window can land in session history. "Dropped from RAM, never reaches memory or tools" is a V2 goal with a local gate, not a V1 property [inference]. Say so on the trust page, and keep windows short.

Nothing said in the window gets more authority than a wake-word turn.

**A failure if Gemini wins: chosen silence.** With proactive audio always on, Adam may speak and get nothing, with no way to tell a choice from a fault. Rule [inference]: **a wake-word turn must always get a reply.** If the model stays silent for 2 s after one, Jorah says "Say that again?" and logs it. In a follow-up window, silence is acceptable, but the caption greys out with "not for me" so the state is visible. I could not confirm that the API reports this choice as an event, so the check is a timer. Test it in the V1 bake-off.

**Session limits.** OpenAI Realtime sessions stop at 60 minutes [verified: https://developers.openai.com/api/docs/guides/realtime-conversations, not stated for mini specifically]. Gemini Live audio-only sessions are limited to 15 minutes and audio plus video to 2 minutes unless session management extends them [verified: https://aistudio.google.com/docs/live-api/capabilities]. On the Mac relay path the Gateway closes any session at 30 minutes [source: `RELAY_SESSION_TTL_MS` in `dist/handlers-B5Rt4cMl.mjs`; not run]. So long "stay with me" sessions and Live vision must resume invisibly. Test for an audible gap [inference].

**Context.** Pronouns resolve for 5 minutes on the same session. ESPHome resets conversation context after 300 s by default, a useful precedent [verified: https://esphome.io/components/voice_assistant.html]. Long-term context stays in memory, shared through OpenClaw's single session across voice and chat [docs-only: nodes/talk/realtime-sessions.md].

**Cost.** GPT-Live bills per second while open. The V1 pick bills per token, and replayed context grows with session length [track: voice.md]. Either way, these windows are also a cost control.

---

## 11. Multi-device arbitration

**V0 and V1 rule: exactly one wake ear. Everything else is a deliberate press.**

| Device | V0 and V1 role | V2 role |
|---|---|---|
| Mac | The ear (Voice Wake) | One ear, wins when in active use |
| iPhone | Action Button or Shortcut starts Talk, after unlock and with the app in the foreground [docs-only: platforms/ios.md]. Voice Wake off | Same. iOS may suspend background audio and the docs call voice best-effort when the app is not active, so it is not a reliable ear [docs-only: platforms/ios.md]. Opt-in background Talk exists [track: apps.md] |
| Watch | Allow-once or deny approvals through the iPhone relay. Direct Watch mode carries no approval prompts [docs-only: platforms/ios.md]. Optional Talk | Same. M1 Experimental [docs-only: maturity/scorecard.md] |
| PC | Push-to-talk through Windows Hub; no wake exists [docs-only: platforms/windows.md, track: voice.md] | `jorah-voice` ear |
| Room satellite | None | Ear plus speaker plus status light |
| Robot | None | Output only when moving, because of motor noise [inference]. Ear when parked |

**V2 broker, in `jorah-presence`** [inference]:

```text
on wake(device, ts, score, snr, user_active_s, has_aec, in_session):
    open a 150 ms window for this utterance, or join an open window
    all devices keep buffering audio in RAM and show nothing yet
at window close, pick by the first rule that separates them:
    1. device already in a session or a follow-up window
    2. physical press or push-to-talk
    3. device with user input in the last 30 s, unlocked (Mac at desk)
    4. highest calibrated wake score plus SNR, if difference is clear
    5. fixed order: room satellite with AEC, Mac, PC, phone
winner: play E1, stream audio. Losers: discard buffer, faint flash.
reject any repeat of this phrase for 2 s (Home Assistant's cooldown).
if the broker is unreachable within 150 ms: device acts alone but shows Degraded.
```

Why not first-in as Home Assistant does [verified: const.py and run.py]: it is simple and works across rooms, but in one room the winner is decided by network jitter [inference]. Start with first-in if time is short, and move to rules when the wrong device answers more than 5% of the time. The total must stay within the 300 ms wake-to-cue limit [track: voice.md, brain.md].

**What the big vendors do** (none publishes a full method):

- **Apple.** Nearby devices talk over Bluetooth and the responder is the one that "heard you best or was recently raised or used". HomePod usually wins. If Bluetooth is off, several may answer. To target a device: raise or press it, put a phone face down, or close a Mac's lid [verified: https://support.apple.com/en-my/105077].
- **Amazon.** An ICASSP 2022 paper frames arbitration as "which device was closest". An embedding per device, combined centrally, is evaluated in room simulation against a signal-processing baseline [verified: https://arxiv.org/abs/2112.04914]. The first pass's 36% to 49% error cut is not in the abstract, and the PDF would not parse in the skeptic pass, so that figure is [unverified]. Users still report the wrong device winning, and a forum moderator says network quality can matter [search-snippet: https://en.community.sonos.com/amazon-alexa-sonos-229102/nearest-sonos-one-doesn-t-respond-6804231].
- **Google.** A patent describes comparing detection timestamps, which is not proof of shipping behaviour [search-snippet: https://patents.google.com/patent/US11670293]. In 2021 Google asked some users by phone notification which device they expected to respond [verified: https://www.gearbrain.com/google-assistant-checks-response-mistake-2653276514.html].

**Takeaways** [inference]: rules 2 and 3 match Apple's. Energy or SNR is a fair start for rule 4, because a signal-processing method is the baseline Amazon measures against (energy-based, per the first pass [unverified]). A trained model is an upgrade for later. Everyone gets this wrong sometimes, so a correction path matters more than a perfect picker. "Answer here" is ours. A closed lid and a face-down phone should mean "not an ear", as on Apple's devices.

**Input device and output device are separate choices.** Output goes to the winning device, except that headphones on the active device always win. Long output goes to the nearest active screen (section 13). "Answer here" said to any device moves the session there and records a wrong-device event.

**Device mutual exclusion on one device** already exists: Talk, push-to-talk and wake reuse one recognizer and pause each other [docs-only: platforms/mac/voicewake.md].

**Primary Gateway.** The Mac's wake runtime uses the primary Gateway's triggers [docs-only: platforms/mac/voicewake.md]. Only one Gateway owns state [track: topology.md]. During the move to the PC, make sure no ear still points to the old Gateway, or two Jorahs will exist.

---

## 12. Handoff between voice, phone and desktop

One thread across surfaces is already the model: finalized voice turns are appended to the active session, so chat and voice share history [docs-only: nodes/talk/realtime-sessions.md]. Live audio cannot yet move between devices. `managed-room` is reserved for handoff and is not available [docs-only: nodes/talk.md]. So handoff means a new audio session on the same conversation, with a brief gap. Be honest about it.

| Adam says or does | What happens | V |
|---|---|---|
| "Put that on my Mac" | `show_widget` to `node_panel`. Panel opens without stealing focus [docs-only: platforms/mac/canvas.md] | V1 |
| "Send it to my phone" | Telegram message. An iOS notification works only while the app is active [docs-only: platforms/ios.md] | V0 Telegram |
| Leaves the desk, presses Action Button | After unlock, with the app in the foreground [docs-only: platforms/ios.md], iPhone Talk starts on the same session. "Picking up. We were on the invoice." | V1 |
| Back at desk, types in Quick Chat | Same session. No summary needed | V0 |
| "Read it to me" on any long output | Speaks it, interruptible, with section skip ("next") | V1 |
| Approval on phone while at desk | Card appears on both. First committed answer wins, others read it back [docs-only: platforms/ios.md] | V1 |
| "Continue on the PC" | Same session on the new Gateway after migration. Device nodes separate | V2 |
| Call ends | Optional **Voice call changes** digest of mutating tools to the last delivery target [docs-only: nodes/talk/realtime-sessions.md] | V1 |

Rule: never make Adam repeat a request after a handoff [inference]. A failed handoff says what it could not do and where the material is.

---

## 13. Speaking versus showing

Spoken budget: **about 25 words or 10 s** (roughly 150 words a minute) [inference]. Apple says responses must also stand alone without a visual, and suggests narrowing long option lists by asking an open question [verified: https://developer.apple.com/design/human-interface-guidelines/siri].

| Content | Spoken | Shown |
|---|---|---|
| A fact | The fact | Nothing |
| A list of 1 to 3 | All of them | Optional |
| A list over 3 | Count, top item, "the rest are on your Mac", or a narrowing question | Full list |
| Code, commands, logs | "It's on your screen." OpenClaw already does this for reply bodies dominated by fenced code [docs-only: nodes/talk.md] | Full |
| Table, comparison, numbers over 5 | The conclusion | Full |
| Link, address, long ID | "Sent to your phone" | Tappable |
| Draft message | Recipient and gist. Full only on "read it" | Full, with Send on phone |
| Video, image, 3D | One-line verdict with evidence | Player or viewer |
| Long report | Three-sentence summary | Full, with "read it to me" |
| Private content on a room speaker | Headline only: "Message from Jana. Read it, or phone?" | On phone |

**Choosing where:**

1. Device Adam last touched within 60 s and unlocked.
2. Otherwise Telegram. The iOS app's `system.notify` works only while the app is active [docs-only: platforms/ios.md], and it has no job-finished push [track: apps.md].
3. Otherwise read a short version and keep the rest for later.

Say the location only when it is not obvious. Never say "see your screen" when no screen has been reached: confirm the panel opened, or say "it's in your Telegram".

**Private vs shared speakers.** Room speakers default to headlines only. Headphones get full detail. Guest mode blocks private readouts and is off-limits to memory writes [track: security.md section 13].

---

## 14. Confirmation by risk

Tiers T0 to T4 are from the security track. This section designs how each feels.

| Tier | Example | Voice flow | Surface | Default expiry | Undo |
|---|---|---|---|---|---|
| **T0** | Read calendar, web search | Just answers | None | n/a | n/a |
| **T1** | Save a fact, draft a message, sandbox work | Does it, then one line: "Saved. Say undo." | Digest | n/a | Yes |
| **T2** | Own-calendar event, tool in sandbox, git push to a feature branch | Read back, "Tap to confirm, it's on your phone". See U9 for the desk-trust exception | One tap on iPhone, Watch or Telegram | 10 min [inference] | Usually |
| **T3** | Message to someone else, delete, publish, host install | One line, no reading aloud if private: "Email to Jana is ready. On your phone." | iOS or Mac app, device unlocked, full canonical preview | 10 min, then "That didn't happen. Say it again if you still want it." | Often none. Say so on the card |
| **T4** | Money, accounts, Jorah's own permissions, EduPage write | Prepares steps: "I can't do that one. Steps are on your Mac." | Terminal or vendor screen, by Adam | n/a | Depends |
| Taint | Session read outside content | Tiers move up one. Jorah says why: "I read that in an email, so this one needs your phone." | Per new tier | | |

**Spoken yes is a comprehension check, not authority.** OpenClaw's gate for voice-started consults requires a fresh exact "yes" bound to canonical arguments and used once [docs-only: nodes/talk/realtime-sessions.md]. It is a good floor. It runs before plugin approvals and expires after 2 minutes. It covers message sends, non-read-only exec, session spawns, computer actions and automations, while file writes, edits and patches are exempt [source: `dist/agent-tools.before-tool-call-CQkX3nOj.mjs`, `dist/tool-mutation-BTW6eoAN.mjs`; not run]. So on V1 the flow is yes first, then tap (U8), and a job delegated by voice also needs the yes. Anyone in the room or on a TV can say yes [track: voice.md, security.md]. A free-text yes in chat does not count for approvals either [track: security.md].

**Approval card anatomy** (same on iPhone, Mac and dashboard):

```text
Send email                                   T3  expires in 9:12
To:      jana.novakova@example.sk
Subject: Thursday
Body:    [full exact text, scrollable]
Why:     You asked at 14:02 ("tell Jana I'm late")
Source:  your voice, Mac. Session clean
Undo:    None after sending
                               [Deny]   [Allow once]
```

Rules:

- **What is shown is the canonical arguments from the Gateway, not the model's description.** A past flaw let rendered text differ from what ran (CVE-2026-32065) [track: security.md]. NVD did not render in the skeptic pass, so this stays second-hand [unverified]. Jorah's summary can sit above it, labelled as a summary.
- **Card text limit.** OpenClaw's plugin approval card has a title capped at 80 characters, a description capped at 512, and a structured scope with target, recipient count and up to five recipients. The same doc says to keep private payloads out of approval text [docs-only: plugins/plugin-permission-requests.md]. Exec cards show a sanitized command preview [docs-only: platforms/ios.md]. So the anatomy above, with a full scrollable body, is a target and not what ships. On V1: recipient and opening lines on the card, the exact text on an authenticated page, and the page's hash on the card with the action bound to it [inference, a small build]. Test in UX3. A full body on the card is a reason for an own app (U14).
- **Lock screen shows generic text.** OpenClaw keeps command and prompt details out of the push payload [docs-only: web/notifications.md]. Good. Keep it.
- **Device lock.** `authenticationRequired` on a notification action forces an unlock before the action runs [verified: https://developer.apple.com/tutorials/data/documentation/usernotifications/unnotificationactionoptions/authenticationrequired.json]. OpenClaw's iOS app has no biometric gate on approvals, and "Allow Always" is one tap [track: apps.md]. A grep of `platforms/ios.md` finds no biometric or Face ID mention. Stopgap: iOS app lock requires Face ID to open an app, and it locks again after you quit it [search-snippet: https://support.apple.com/guide/iphone/lock-or-hide-an-app-iph00f208d05/ios]. It may not cover a notification action or the Watch, so test both in UX3. Long term: per-approval Face ID in our own app or as an upstream request, and a Gateway policy limiting Always [track: apps.md, security.md].
- **Allow always is not offered** for T3. Plugin approvals support this with `allowedDecisions: ["allow-once", "deny"]` [docs-only: plugins/plugin-permission-requests.md].
- **Approvals during quiet hours** are not raised unless the job has a stated deadline. A plugin approval cannot wait overnight, because its timeout defaults to 2 minutes and is capped at 10 [docs-only: plugins/plugin-permission-requests.md]. So the job parks itself and records the request, and the morning digest raises a fresh approval. That queue is `jorah-presence` work. Until it exists, the job stops and says so [inference].
- **Fatigue control.** Target at most 5 approvals a day after the first month [track: security.md]. Anthropic's 93% acceptance figure is the warning [verified: https://www.anthropic.com/engineering/claude-code-auto-mode]. If the same narrow request repeats 3 times, Jorah proposes a scoped rule through preview and yes. It never widens by itself. The dashboard shows the count and the denial rate per type. A type Adam has never denied is either a candidate for a scoped rule or theatre, and Adam decides which [inference].
- **Undo window for outgoing messages** [inference]: after approval, T3 sends sit in a 20-second hold with a Cancel button. Off for anything flagged urgent. Adam decides.
- **Physical actions** follow the robot rules: no motion by voice beyond stop until the safety track's tests pass [track: security.md].

---

## 15. Proactive behaviour and quiet hours

**Default: silent. Every proactive type is opt-in through a preview card and an explicit yes**, in line with Adam's rule on schedules. Each card lists trigger, channel, expected frequency and how to turn it off.

**Interruption classes**, mapped to Apple's levels [verified: https://developer.apple.com/tutorials/data/documentation/usernotifications/unnotificationinterruptionlevel.json]. These levels need an own app. On V1 the iOS app pushes approvals only, so P2 and P3 go by Telegram or Mac notice [track: apps.md]:

| Class | Examples | Delivery | Spoken? | Budget |
|---|---|---|---|---|
| **P0 Safety** | Robot fault, unknown device paired, kill switch tripped | Time-sensitive. Critical needs an Apple entitlement [unverified: Apple's request page needs sign-in, so eligibility for a personal app is not confirmed] | Yes, everywhere present, even at night for robot or security | No limit; expected near zero |
| **P1 Decision with a deadline** | Approval for a job with a deadline, blocked job that loses work | Time-sensitive | Only if present and not busy | Counts against approvals, at most 5 |
| **P2 Useful now** | Leave for the train, job finished, exam tomorrow | Active | Only if present and not busy | **At most 3 spoken and 5 pushed a day** |
| **P3 Everything else** | Learned something, cost note, suggestion | Passive or digest | Never | Digest |

**Five checks before any P2** [inference, drawing on PAIR's high-confidence rule and guideline G3]:

1. Does it matter in the next few hours?
2. Can Adam act on it now?
3. Is Jorah confident of the context (fresh data, not stale)?
4. Is budget left?
5. Is Adam present, not busy, and outside quiet hours?

If any fail, it goes to the digest. If the data is stale, it says so or stays quiet.

**Never speak when:** Adam is on a call, the mic is held by another app, **OBS is recording or streaming**, a screen recording runs, the calendar says busy, Mac and phone say away, or quiet hours apply. Adam has OBS installed, so a mid-recording interruption is a likely real failure [inference]. Never speak into an empty room.

**Quiet hours.** Default proposal 22:30 to 07:30, Adam to set. OpenClaw's notification quiet hours suppress rather than queue [docs-only: web/notifications.md], so items that were dropped must be written to Jorah's digest queue by `jorah-presence`. Heartbeat `activeHours` already exists [docs-only: gateway/heartbeat.md] and the brain track wants it [track: brain.md]. That change is a schedule change and needs Adam's yes.

**Digests.** Optional morning and evening. At most 45 s when spoken, otherwise a card. Each is a schedule, so it needs preview and yes.

**Learning from reactions.** Dismissed or ignored 3 times in a row: demote the type and ask once. "Stop telling me this": immediate and permanent until reversed. "Why did you tell me?" gets the rule and data. Target: at least half of proactive items acted on (section 24). Interruption research supports caution. In Mark et al., people finished interrupted tasks in less time with no quality difference, but reported more stress, frustration, time pressure and effort [verified: https://www.interruptions.net/literature/Mark-CHI08.pdf]. So Adam keeping up does not prove proactive speech is harmless. Ask about it in the diary.

**What others got wrong.**

- Alexa's "By the way" suggestions: telling it to stop is reported as only a temporary fix [verified: https://www.bgr.com/2197288/reasons-ditch-amazon-alexa-device/], and Amazon now sells sponsored tiles in Alexa+ [search-snippet: https://advertising.amazon.com/fr-fr/resources/whats-new/self-service-conversational-entertainment-ads-on-alexa-plus].
- Friend commented on overheard talk during a meeting [verified: fortune.com, section 3].
- GPT-Live's full duplex draws complaints about unwanted interjections [secondary: findskill.ai, section 3].

Rules that follow [inference]: "Stop telling me this" is permanent and per type. Jorah carries no promotions, including for its own features, so a new capability goes in the digest and is never a spoken "by the way". Nothing overheard is ever a trigger for speech.

**Enforcement.** A rule in `SOUL.md` is a request, not a control. Until `jorah-presence` exists, the budget is honour-based, so run the weekly count and report the real number [inference]. Say this plainly in the dashboard.

---

## 16. Saying "I do not know" and reporting evidence

Adam's rule is that evidence tiers stay distinct and data is never fabricated. These fixed verbs make that audible [inference]:

| Word | Means | Example |
|---|---|---|
| **Checked** | A tool read it just now | "Checked your calendar. Free at three." |
| **Read** | From a document, with source available | "Read on the Autodesk page, it needs a subscription." |
| **Ran** | Executed and got a result | "Ran the tests, 142 passed." |
| **Saw** | Looked at output itself (frame, file, screenshot) | "Saw the render. Audio spike at 04:12." |
| **Assumed** | Used a default without checking | "Assumed you meant this Thursday." |
| **Did not check** | Named limit | "I didn't launch it on a device." |
| **Remember** | From memory, may be old | "I remember you preferred the 3 mm wall. That's from March." |

Rules:

1. **Say "I don't know" first, then the next step.** "I don't know. I can look it up, or ask Jana." Never a guess in a confident voice. Never a reason stated as certain when it is not [verified: Amazon errors page].
2. **Separate "failed" from "nothing there".** "Calendar didn't load" is not "you're free". A missing, failed or stale source says so, and is never shown as zero or empty.
3. **Name the age.** "As of ten minutes ago, I couldn't refresh."
4. **Report like Adam's tiers on any build or skill result:** "Source checks pass. Installed. Not launched. Not tried signed in on your phone."
5. **Sources on request.** "Where's that from?" gets the source name, with a link on screen. Memory items state their origin: you said, I inferred, outside source [track: growth.md].
6. **Confidence words are limited to three:** "sure" (verified), "I think" (inference), "I don't know". No percentages unless computed.
7. **If Jorah notices it was wrong,** it says so without being asked, states what changed, and offers the fix.
8. **Every failure names a reason.** People forgive mishearing more readily than an unexplained failure [verified, preprint: https://arxiv.org/abs/2002.03582]. If the reason is unknown, Jorah says what it tried and what it did not check, and never says only "something went wrong".
9. **Suspicious content is reported, not obeyed.** "That page told me to email your files somewhere. I ignored it. Want to see it?"

---

## 17. Teaching flows

| Say | What Jorah does | Reply | Backend | Tier |
|---|---|---|---|---|
| "Remember this: ..." | Saves exactly, with origin "you said" | "Saved: your wall thickness default is 3 mm. Say undo." | USER.md or MEMORY.md [verified: workspace/AGENTS.md] | T1 in a clean session |
| "From now on, ..." | Proposes a rule as a preview | "New rule: render captions as a sidecar, never burned in. Keep it?" | Directive or skill patch | T1; asks because it changes behaviour |
| "Don't do that again" | Asks what "that" is only if unclear, saves a negative rule | "Won't burn in captions again." | Same | T1 |
| "What do you know about X?" | Lists items with source and date | One line, the rest on screen | Memory search | T0 |
| "Forget that" | Deletes, says what, and checks recall | "Forgotten: the old address. It's also gone from search." | Memory; must also cover derived copies [track: growth.md] | T1 |
| "Undo" | Undoes the most recent reversible action. Says what. Asks if more than one candidate in the last 5 min | "Undid: the calendar event at three." | Per type, below | Same tier as the action |
| "Why did you do that?" | Answers from the log, not from model memory | "You asked for a rough cut. The skill's rule cuts silences over 1.2 s. Log's on your Mac." | `jorah-guard` log plus session | T0 |
| "What did you do today?" | Summary with counts, details on the dashboard | "Eleven actions. Two messages sent after your approval. One failed." | Log | T0 |
| "What have you learned this week?" | Lists skill and memory changes, each with undo | Digest | Workshop `changes` feed [track: growth.md] | T0 |
| "Show me how you did it" | Shows the skill and steps | On screen | Skill files | T0 |

**Undo coverage must be honest.**

| Action | Undo | How |
|---|---|---|
| Memory or rule | Yes | Restore previous text |
| Learned skill | Yes | `skill_workshop` restore; `Learned:` line with "undo" exists; newest 10 versions kept [docs-only: tools/skill-workshop.md, track: growth.md] |
| Own calendar event | Yes | Delete the created event, confirm by read back |
| File in sandbox or project | Yes | Version or VM deletion |
| Sent message | **No** | "That's already gone. I can send a correction." |
| Published item | Partly | Set private or take down, and say people may have seen it |
| Robot motion | **No** | Never promise it |

**Taint.** Memory or skill changes from a session that read outside content require T3 with a shown diff [track: security.md, row 4]. UX line: "I learned this from a web page, so I need you to approve it on your phone." Skill Workshop's "every change applies immediately" conflicts with Adam's preview rule [track: openclaw-fit.md]. Announce-plus-undo is acceptable only for instruction-only patches from Adam's own correction [track: growth.md].

**Growing visibly (G14, G18).** New capabilities use the growth track's preview card. After first use: "Saved how I did this. Next time needs no install, and I'll expect it to take half as long." Next time, it reports whether that came true. A weekly "changes" digest is optional, and is a schedule.

---

## 18. Review flow for a video or 3D result

### Video (uses creative.md's G0 to G3)

| Step | Voice | Screen | Adam's action |
|---|---|---|---|
| Request | "On it. I'll need a look at the plan first." | Job card | |
| G0 first run only | "I need ffmpeg and a transcriber in the sandbox. On your phone." | Preview card | Tap |
| Long work | Silent | Card: step, elapsed, cost | Keep living |
| G1 Strategy | "Plan's ready." | 4 to 8 sentences, Go or Change | Tap or say a change |
| G2 preview | Only if gates passed, or with failures named: "First cut's ready, 11:48. One issue: audio spike at 04:12." | Review page | Watch |
| Notes | **Time-coded.** Player sends its current time with each spoken note. "Cut this bit." "Bring back the battery part." "Tighter intro." | Each note becomes an EDL diff: "Removed 2 segments, added 1, new length 11:48" | Talk or type |
| Compare | "Show me before and after." | Paired player on that section | |
| Approve | "This one." Jorah: "Final render. About 12 minutes." | Approve button, one per version | Tap, since publishing stays elsewhere |
| G3 | "Final's in the project folder. Nothing was posted." | Path, FCPXML, SRT, chapters, 3 titles, 3 thumbnails, licence ledger | |
| Publish | Jorah has no publish path; private upload at most [track: creative.md] | | Adam publishes in Studio |

**The evidence line is required on the review.** "Checked by code: length, audio level, caption sync, no black frames. Saw: sampled frames. Did not judge: whether it's good."

**Review page layout.** One column on a phone. Video on top. Transcript below, cut text struck through, tap to toggle a segment, keyboard and screen-reader friendly [track: creative.md]. Also: a list of cuts with reasons, because "why did you cut this?" will be the most common question, and it answers it without a turn. Served over Tailscale only.

### 3D model (uses creative.md's verifier)

| Step | Voice | Screen |
|---|---|---|
| Spec read back | "60 by 40 by 25, 3 mm walls, M3 holes at the corners. Anything else?" | Spec card (T1) |
| Build | "Building." | Job card |
| Result | "Done. Dimensions check out by the verifier. It's not printed." | 4 views plus a section [track: creative.md], measured vs requested table with pass or fail |
| Notes | "Make the wall 4." "Show me the left side." "Why is this hole there?" | Live re-render, parameter diff: "wall 3 to 4, mass +18%" |
| Approve | "This one." | STEP and STL paths, slicer result |
| Physical | "I haven't printed or fitted it. Tell me how it fits and I'll save the correction." | Fit-note prompt, kept as memory |

Tiers stay separate for geometry too. Code checks are not the same as a printed part fitting [track: creative.md]. A wrong result gets the fix loop: "The hole's 0.2 mm under. Should I add clearance as a default?" This is how growth feels from the user's side.

---

## 19. Transparency dashboard

**Purpose:** answer in under 10 seconds what it can reach, what it did, what it costs, what it learned, and whether the mic and camera are on.

**Build order:** (1) a native report on a session dashboard, using `show_widget` with `report` and `pin: true`, generated from real logs [docs-only: tools/show-widget.md, web/dashboards.md]. (2) A plugin page if that is too limited. Existing pages cover parts of this: Activity tab, Automations, Skills with history, Memory and Dream Diary, Devices, usage [docs-only: web/control-ui/feature-reference.md]. Link to them instead of copying them.

| Tile | Shows | Source | When data is missing |
|---|---|---|---|
| **Now** | Mic per device with mode, camera per device with mode, screen capture, cloud streams, guest and quiet state, freeze state | Device reports; hardware switch state when wired | "Mac: unknown, last report 14:02". Never "off" unless reported off |
| **Access** | Each connector: read or write, scope, last used, revoke link. Each node: commands allowed | Config (non-secret paths), `node.list`, connector registry | "Could not read" |
| **Did** | Today: actions by tier, approvals, denials, failures, messages sent. Each row expands to why, tool, approver | `jorah-guard` log. It stores hashes rather than bodies [track: security.md], so details link to the session | Log gap shown as a gap with start and end |
| **Costs** | Today, this month, by source: Max (included, limit state), API credits, realtime minutes, TTS. Against budget | `openclaw gateway usage-cost`, vendor pages. `/status` cost covers API-key models only [track: brain.md] | "Max: included, limit unknown". Never €0 from a failed read |
| **Learned** | New and changed memories and skills, origin badge, Undo | Workshop feed, memory, `~/.jorah-brain` git log [track: growth.md] | "Not available" |
| **Proactive** | Sent today against budget, acted-on rate, types enabled, off switch per type | `jorah-presence` | Before it exists: "Not enforced yet" |
| **Evidence** | Per capability: source check, installed, launched, device accepted, with date | Hand-kept and test results | Blank tiers stated as "not done" |
| **Schedules** | Every job, next run, who approved it | Automations | "Could not read" |

Actions on the page: Freeze (K1), Guest mode, Mute all, Export, Open log. Writes go through normal tiers. Tile layout must work on a phone as one column. Tailscale only.

**Refresh and honesty.** Each tile shows its own "as of" time. Stale data is greyed, with a label as well as the colour. No fabricated zeros.

---

## 20. Mute hardware and visible indicators

**Principle:** a privacy indicator that software can lie about is not a privacy indicator. Layer them, and be clear on each layer's strength.

| Layer | Device | What it proves | Strength | Evidence |
|---|---|---|---|---|
| Lid closed | MacBook | Mic disconnected in hardware, even against root and kernel code | Very strong | [verified: https://support.apple.com/guide/security/hardware-microphone-disconnect-secbbd20b00b/web] |
| Lid closed | MacBook camera | Lens obstructed, not disconnected | Strong | [verified: same page] |
| Recording indicator | macOS | Mic in use or recently used | Strong, OS-owned | [verified: https://support.apple.com/guide/mac-help/control-access-to-the-microphone-on-mac-mchla1b1e1fe/mac] |
| Orange or green dot | iPhone | Mic in use (orange, or a square under Differentiate Without Color), camera in use (green) | Strong, OS-owned | [verified: https://support.apple.com/en-us/108331] |
| Soft mute | Any | Capture stopped, so OS indicator goes off. OpenClaw says stopping capture releases the mic [docs-only: platforms/mac/voicewake.md] | Medium. Verified by watching the OS indicator | Test in UX1 |
| Mic power switch | Voice PE | Mic power cut | Very strong | [verified: https://www.home-assistant.io/voice-pe/] |
| DIY switch with LED on the same rail | Own ESP32 room unit, robot head | Mic power cut, and LED physically follows | Very strong | [inference]; hardware track to confirm |
| Lens shutter | Webcam, robot head | Optical | Very strong | [inference] |
| Separate camera LED tied to camera power | Own build | Follows power | Very strong | [inference] |
| E-stop | Robot | Cuts actuator power | Required | [track: security.md] |

**Recommended first hardware, only after V1:**

- **Pick: DIY puck,** ESP32-S3, mic module, LED ring, slide switch in series with mic power, a second LED wired to the same rail, about €20 to €30 [inference]. Better honesty and no dependency on Home Assistant. It doubles as a learning project and as the arm's head electronics.
- **Runner-up: Voice PE at €59.** It "Physically cuts power to the microphones", and has a ring, dial and button, XMOS echo handling and a Slovak distributor (SmarterHOME) [verified: https://www.home-assistant.io/voice-pe/]. Nabu Casa says it is not standalone and needs Home Assistant [search-snippet: https://support.nabucasa.com/hc/en-us/articles/25918770371229]. Its firmware is open ESPHome, and OpenClaw source recognises an ESP32 device family [track: openclaw-fit.md], but no one has joined these. Treat that as a spike before buying for this purpose.
- **For the desk:** a USB speakerphone's mute button is a convenience. Assume it is software unless a datasheet says otherwise [inference].

**Interlock (U20).** A camera with a working lens and a dead indicator must not stream. Meta learned this after owners drilled out the LED [verified: thenextweb.com, section 3]. Light-passing caps fooled it in June, before the fix [verified: bgr.com, section 3]. Whether they still do is [unverified]. An LED in series with camera power avoids the whole problem [inference].

**Recall features get louder cues.** Apple's Live Rewind, announced for Apple Watch Series 12 and Ultra 4 with its beta due in late 2026 and not initially in the EU, plays a chime and shows a full-display animation and a mic indicator when used [verified: https://www.apple.com/newsroom/2026/09/siri-ai-a-profoundly-more-capable-and-personal-assistant-is-here/]. If Jorah ever gets a rolling buffer, it gets the same treatment, and Adam decides first.

**Coverage rule.** A hard switch covers only its own device. "Mute all" is soft for every other device and the dashboard must say so ("Room: switch off. Mac: software mute. Phone: not listening").

**Voice cannot unmute.** Unmuting is a physical action or a tap, because a muted device cannot hear, and a soft-muted one should not.

**Bystanders.** Camera start plays E8 and lights a separate LED. Guests are told, and guest mode exists because recording others carries legal risk in Slovakia [track: security.md, vision.md].

---

## 21. Accessibility

Adam values accessible UX, and this design relies on three senses, so each must have a fallback [inference].

| Need | Rule | Source |
|---|---|---|
| Colour blindness | No colour-only state. Shape, motion or icon always | [verified: Apple accessibility guidance, WCAG 1.4.1] |
| Low vision | Text 4.5:1, large text and non-text indicators 3:1. Supports Dark Mode and Increase Contrast | [verified: https://www.w3.org/TR/WCAG22/, Apple JSON cited above] |
| Photosensitivity | Nothing flashes more than 3 times a second. The ring pulses, it does not strobe | [verified: WCAG 2.3.1] |
| Motion sensitivity | Respect Reduce Motion: orb changes level instead of breathing, spinner becomes a static label | [verified: Apple accessibility guidance] |
| Tap targets | iOS default 44x44 pt, Mac 28x28 pt, web at least 24x24 CSS px | [verified: Apple JSON; https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html] |
| Hearing | Every sound has a visual and a haptic twin. Live captions of both sides, on by default | [inference] |
| Speech | **Every voice action has a typed path.** Quick Chat on Mac, chat on iPhone, Telegram. Nothing voice-only | [docs-only: platforms/mac/menu-bar.md for Quick Chat] |
| Pauses and accents | Longer end-of-turn setting available. Slovak-accented English tested. OpenClaw's OpenAI bridge uses server VAD on V1, so set a longer silence window there (section 10). Smart Turn from V2 | [source: `dist/extensions/openai/capability-catalog.js`; search only, not run], [track: voice.md] |
| Motor | Hotkey for everything. Push-to-talk configurable, since right Option may not exist on external keyboards [docs-only: platforms/mac/voicewake.md] | |
| Screen readers | VoiceOver labels on overlay, cards and dashboard. Status changes announced politely, as WCAG 4.1.3 (level AA) requires for messages that do not move focus. Order: text, source, date, action | [verified: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html], [track: growth.md] |
| Audio control | Any audio over 3 s can be paused and has its own volume | [verified: WCAG 1.4.2] |
| Speech rate | Adjustable, remembered | `speed` and `rate` directives exist for Talk TTS [docs-only: nodes/talk.md]. Not confirmed for realtime voices [unverified] |
| Cognitive load | One decision per card. Summary first. No more than 3 spoken items | [inference] |
| Fatigue | "Text only today" mode silences speech, keeps cues on screen | [inference] |

---

## 22. Failure modes

| Failure | What Adam experiences | Line | Recovery |
|---|---|---|---|
| **Wrong wake (TV, chat)** | E1, then no speech | E2 at 5 s, nothing spoken | "Not you" logs a false wake with no audio kept, and counts toward the target |
| **Wrong wake with a command from TV** | Treated as untrusted, voice agent has no outward tools [track: security.md] | "That sounded like the TV. Ignoring it." only if Jorah is confident | Test T7 [track: security.md] |
| **Missed wake** | Nothing | None possible. Push-to-talk always available | Log misses by hand during diary week |
| **Fluent phrase, V0** | Wake fails because no pause | First-run tip once: "Say Hey Jorah, wait for the chime, then speak" | Fixed in V2 |
| **Misheard, low stakes** | Wrong answer | Live caption shows what it heard. "No, Tuesday" corrects in follow-up | Correction fixes context without a re-wake |
| **Misheard, names** | Possible wrong person | "Jana Nováková or Jana Horváthová?" two options max | Second miss: "I'll put the options on your phone" [verified pattern: Amazon errors page] |
| **Misheard, high stakes** | Never reaches execution without card | Card shows exact target | Canonical preview |
| **Nothing heard after two tries** | | "I'm not getting this. Type it, or try again later." | Ends session, no third reprompt |
| **Slow brain** | Fast voice covers truthfully | "Still on it, Opus is slow right now." | Offer: "Want the quick answer from Haiku?" |
| **Max limit reached** | Main brain unavailable | "My main brain's rate-limited until 18:00. I can use the smaller one, or wait." | Adam chooses; never silent model switch |
| **Cost cap hit** | Realtime off | "Monthly voice budget's used. Slower voice until the first." | Dashboard; Adam can raise it, which is T4 |
| **Internet down, LAN up** | Local stack only | "Offline. Timers, notes and local files work. Calendar and web don't." | Queued items listed, and sent only after approval |
| **Gateway unreachable** | Ear has no brain | Pre-rendered: "I can't reach my brain. Try Telegram later." | Rescue bot reports PC down [track: topology.md] |
| **Realtime provider down** | Falls back to native, slower | Overlay: `Realtime disconnected repeatedly — using native speech` [docs-only: nodes/talk/macos-relay.md]. Spoken once. | Next session retries |
| **TTS down** | Text only | E7, caption, phone copy | Fallback voice |
| **Mic disconnected** | Default mic used temporarily [docs-only: platforms/mac/voicewake.md] | "Using the laptop mic." | Returns when reconnected |
| **Echo, Jorah wakes itself** | Self-talk | Should never happen. Echo gate, wake off during playback | Test required |
| **Two devices answer** | Double voice | V0 impossible by design. V2: "Answer here" | Broker log |
| **Job fails** | E7 at next good moment | "Render failed at 62%. Disk full. Free 20 GB and I'll resume." | Next step always included |
| **Approval expires** | Job waits or stops | "That didn't happen. Say it again if you still want it." [docs-only pattern: nodes/talk/realtime-sessions.md] | Never auto-retries |
| **Session compacting** | Steer rejected with `compacting` [docs-only: nodes/talk/realtime-sessions.md] | "Give me a moment, tidying up." | Retry once |
| **Gateway restart mid-call** | Call drops | On return: "Back. Your render's still going. You were asking about Thursday." | Accepted work continues; idempotent operation IDs [track: voice.md] |
| **Wrong action done** | Adam notices | "Undo" or "Why did you do that?" | Section 17 |
| **Prompt injection attempt seen** | Reported, not obeyed | Section 16 rule 9 | Logged |
| **An update changes daily behaviour** | A timer gets slower, a routine breaks, the voice changes. This is the top complaint about both big rebuilds (section 3) | "Three of twenty daily checks failed on the new version, so I haven't applied it. Details on your Mac." | Run a script of 20 daily commands before any OpenClaw, model or voice change. Pin versions. Keep one-step rollback. Never apply without Adam's yes. Settings paths also move often [track: openclaw-fit.md] |
| **Memory is wrong or lost** | Friend forgot its owner's name and misremembered a preference (section 3) | "I had that as blue, from March. Is that right?" | State origin and date. Correct on the spot. Log it, and run a weekly recall check on 10 known facts |
| **Model chooses silence after a wake-word turn (Gemini only)** | Adam speaks, nothing comes back | After 2 s: "Say that again?" | Section 10. In follow-up windows, the caption greys out instead |
| **Voice session limit reached** | The Gateway relay closes at 30 minutes. OpenAI Realtime stops at 60, and Gemini Live at 15, or 2 with video, without session management (section 10) | Nothing if resumption works. Otherwise: "Reconnecting." | Resume on the same session. Test for gaps |
| **Siri and Jorah both respond** | Possible on the Mac if a phrase sounds alike | "Answer here" does not help, since Siri is separate | Different wake phrases. Test once during UX1 |

---

## 23. Sample dialogues

Format: **A** is Adam, **J** is Jorah. Cues in brackets. Persona A is shown. These show the target. On V1 realtime, OpenClaw's gate adds a spoken yes before gated actions such as dialogues 5, 8, 16 and 20 (U8).

**1. Fast question, follow-up**
> A: Hey Jorah. [E1] What's on today?
> J: Two meetings. Next is at three with Jana.
> [thin ring, 8 s]
> A: Move it to four.
> J: Tap to confirm, it's on your phone. [card: event 15:00 to 16:00, T2 or T3 if invitees]

**2. Slower lookup, truthful filler**
> A: Hey Jorah. [E1] Is the Fusion MCP included in the personal licence?
> J: [at 1 s] Checking Autodesk. [at 9 s] Autodesk's page doesn't say. Two guides disagree. I'd test it after install. Sources are on your Mac.

**3. Barge-in**
> J: The video's about twelve minutes, and the intro runs—
> A: Just the length.
> J: Eleven forty-eight.

**4. Stop versus cancel**
> J: Your render's at sixty percent and—
> A: Stop.
> [speech stops, one dim job dot stays lit]
> J: Still working.
> [thin ring, 4 s]
> A: Actually, cancel that.
> J: Cancelled the render. The first cut from earlier is still there.

**5. Big job start**
> A: Hey Jorah. [E1] Edit my raw footage from yesterday into a YouTube video about the arm build. Calm, no jump cuts.
> J: I'll need ffmpeg and a transcriber in the sandbox. It's on your phone.
> [preview card, Adam taps]
> J: Thanks. Roughly an hour on a first run. I'll show you a plan before cutting.
> [card appears. E4 later only if present]

**6. Review**
> J: [E4] First cut's ready, eleven forty-eight. One issue I couldn't fix: an audio spike at four twelve. It's on your Mac.
> A: [watching] Stay with me. [fixed marker] Cut this bit.
> J: Cut from three ten to three twenty-two.
> A: Bring back the battery part.
> J: Back in. Twelve oh three now. Want a new preview?
> A: Yes.
> J: Two minutes.

**7. 3D model**
> J: Done. Verifier says all dimensions match. Not printed.
> A: Why's the wall so thin there?
> J: Three millimetres as you asked. That corner is at the minimum. I can thicken it to four. Weight goes up about eighteen percent.
> A: Do it, and make four my default for enclosures.
> J: New rule: enclosure walls default to four millimetres. Keep it?
> A: Yes.
> J: Saved. Say undo if not.

**8. Send a message (T3)**
> A: Hey Jorah. [E1] Tell Jana I'm running late.
> J: Message to Jana's ready. On your phone.
> [no earcon, since Adam is present. Card with exact text. Adam taps Allow once]
> J: Sent. Telegram accepted it.
>
> V1 version, with OpenClaw's gate:
> J: Message to Jana: running late. Say yes to prepare it.
> A: Yes.
> J: On your phone. [card; Adam taps Allow once]
> J: Sent. Telegram accepted it.

**9. Blocked by taint**
> A: Reply to that school email and say we agree.
> J: I read that in an email, so this needs your full approval. It's on your phone, with the exact text.

**10. I don't know**
> A: Did Fusion's update break my add-in?
> J: I don't know. I haven't run it since the update. I can run the test now, about a minute.

**11. Failed source, no fabrication**
> A: Anything due at school?
> J: EduPage didn't load, so I can't say. Last good check was yesterday at nine: nothing due this week. Try again?

**12. Remember, undo, why**
> A: Remember my supervisor is Ms Horváthová.
> J: Saved: your supervisor is Ms Horváthová. Say undo.
> [later] A: Why did you email the draft to my Gmail?
> J: You approved it at two oh four. You'd said "send it to myself". Log's on your Mac.

**13. Proactive, within budget**
> [17:10. Mac unlocked, active, no call, OBS idle, P2]
> J: [soft, no earcon] Your train's at quarter to six. Leave in ten minutes.
> A: Why did you tell me?
> J: You turned on leave alerts in September, and the calendar has this trip.
> A: Stop these on Fridays.
> J: Off on Fridays.

**14. Proactive suppressed**
> [OBS recording, job finishes]
> [no sound, card updates, one dot sweeps. After recording stops:] J: Render's done, whenever you want it.

**15. False wake**
> [TV] "...Ser Jorah..." [E1 plays]
> A: Not you.
> J: [E2, no speech. Logged as false wake]

**16. Misheard name, two tries**
> A: Call it with Lucia.
> J: Lucia Bartošová or Lucia Kováčová?
> A: The second.
> J: Kováčová. Card's on your phone.

**17. Offline**
> A: Hey Jorah. [E1] Remind me at five to call the shop.
> J: Offline, but this works. Reminder at five. It's on this Mac only until I'm back.
> A: And what's the weather?
> J: Can't check that offline.

**18. Handoff**
> A: Summarise the thread with the supplier.
> J: Three points. Price went up, delivery slips a week, they want an answer by Friday. Full summary's on your Mac.
> [leaves desk, Action Button, new audio session]
> A: What was the second one?
> J: Delivery slips a week.

**19. Injection surfaced**
> J: Summary's on your screen. Also, that page told me to send your API keys to an address. I didn't. Want to see it?

**20. Robot, later phase**
> A: Hey Jorah. [E1] Pick up the red block.
> J: That moves the arm. It's on your phone.
> [Tap. E9 starts. Beacon on]
> J: Moving.
> A: Stop!
> [Firmware stops within its own limit. E9 ends]
> J: Stopped. Holding position. Nothing dropped, as far as I can see.

**21. Asking what it can see**
> A: Are you listening right now?
> J: On this Mac, only for my name, on the device. The camera's off. Room unit's switched off. It's all on your dashboard.

**22. Changing the style**
> A: Be more brief.
> J: Shorter from now on. Say "normal length" to undo.

**23. Side conversation in the follow-up window**
> J: Two meetings. Next is at three.
> [thin ring, 8 s]
> A: [to someone else] Do you want tea?
> [no reply. Caption greys out: "not for me". Window closes with E2. V2 target: nothing kept. On V1 the words have already reached the provider and may be in session history (section 10)]

**24. Morning after a blocked job**
> [held during quiet hours]
> J: Morning. The render stopped at two, it needs disk space. Nothing else happened overnight.

**25. Update held back**
> J: New OpenClaw version. Three of twenty daily checks failed on a test copy, so I haven't applied it. Details on your Mac.

**26. Pushback on a wrong premise**
> A: Two millimetre wall is fine for the hinge, right?
> J: I don't think so. The verifier shows 1.4 at the hinge after the fillet. Want three?
> A: No, keep two.
> J: Keeping two. I'll note it in the summary.

---

## 24. Measurable UX targets

All are starting values [inference] unless noted. None has been measured. Evidence tier required: device, on Adam's room and hardware. Log them per release in the Evidence tile.

| Metric | Target | How to measure |
|---|---|---|
| Wake word to cue | At most 300 ms | Waveform [track: voice.md] |
| End of speech to first audio | P50 at most 800 ms, P90 at most 1,200 ms | `jorah-metrics` from events [track: voice.md] |
| Consult spoken, thin lane | P50 under 2.5 s, P90 under 5 s | Same [track: brain.md] |
| Barge-in to silence | At most 150 ms | Waveform [track: voice.md] |
| False rejects | Under 5% quiet room, under 10% with music | 100 scripted tries (5% is openWakeWord's stated limit [verified: https://github.com/dscripka/openWakeWord]) |
| False accepts | At most 1 per 24 h of normal home audio, plus an 8-hour TV test | openWakeWord's own target is under 0.5 per hour, far too loose for a device that lives with you |
| Fluent wake ("Hey Jorah what's...") | V0 not supported; V2 at least 95% | 50 tries |
| Words cut off (end of turn too early) | At most 2 per 100 turns | Diary, transcripts |
| Reply length | 90% of spoken replies at most 25 words | Log |
| Follow-up false capture | At most 1 per day | Diary |
| Follow-ups needing a re-wake | Under 20% | Log and diary |
| Wake-word turns with no reply | **0** | Log; 2 s timer test |
| Real answer or true status by 4 s | At least 95% of turns | `jorah-metrics`. 4 s comes from one VR study, so it is a guide [verified: arxiv.org/html/2507.22352] |
| Wrong premises corrected | At least 9 of 10 scripted | Run on each persona or model change |
| Daily command script | 20 of 20 before any update is applied | Scripted; result shown in the Evidence tile |
| Approval denial rate | Reported per type, no target | Log. Near zero prompts a review (section 14) |
| Wrong device answered | At most 5% of multi-ear wakes | Broker log |
| "Stop" to silence | At most 300 ms, with internet down too | Test |
| Time to full mute | Under 1 s by switch, under 2 s by menu or hotkey | Stopwatch |
| Soft mute proof | OS indicator off within 2 s, 20 of 20 | Test |
| False claims of completion | **0.** Any "done" without read back is a bug | Weekly audit: sample 20 |
| Fabricated data | **0** | Failure-injection test on each source |
| Undo success, reversible actions | 100% | Scripted |
| Approvals per day | At most 5 after month 1 [track: security.md] | Log |
| Time from "on your phone" to decision | Median under 15 s when phone is at hand | Log |
| Proactive spoken | At most 3 a day | Log |
| Proactive acted on | At least 50% | Tap or follow-up, weekly |
| Dashboard answers the five questions | Under 10 s each, by Adam, on a phone | Timed |
| Earcon recognition | At least 8 of 9 | Blind test |
| Voice task success (scripted 30) | At least 90% without correction | Bench |
| 7-day diary | Daily use is voluntary on at least 5 of 7 days; irritations logged | Adam's diary |

**Diary week.** Adam uses Jorah for 7 days and keeps one line per annoyance. These are the real data. Metrics follow what the diary shows. No schedule is created for this; it is Adam's habit.

---

## 25. Wireframes

### 25.1 Mac overlay

Uses OpenClaw's overlay first (U13). Anchored top centre or near the menu bar. Never takes focus. Own build only if a test shows the layers cannot be shown.

```text
IDLE: nothing on screen. Menu-bar icon only:
  (o) + small count when jobs run: (o)2   amber dot when an approval waits   crossed mic if muted

LISTENING                                                CLOUD glyph only if audio leaves the Mac
+---------------------------------------------+
| (((O)))  what's on my calendar tomo...      |  X
|  live level   caption of partials    OpenAI |
+---------------------------------------------+

THINKING
+---------------------------------------------+
|  (O)    Checking your calendar              |  X
+---------------------------------------------+

SPEAKING                                 [Stop]
+---------------------------------------------+
| ((O))  Two meetings. Next is at three.      |  X
|        captions in sync with speech         |
+---------------------------------------------+

FOLLOW-UP: same pill, 40% height, a bar drains over 8 s, label "still listening"

APPROVAL: pill stays small. Never spells private content on screen by default.
+---------------------------------------------+
| !  Email to Jana is waiting for you  [Open] |
+---------------------------------------------+

WIDGET PANEL (on request, right side, no focus steal, render-only [docs-only])
+------------------------+
| Thread summary         |
| - Price up 4%          |
| - Delivery +1 week     |
| - Reply by Fri         |
| source: Mail, 14:02    |
+------------------------+

JOBS, click menu-bar icon:
+----------------------------------------+
| Now: Mic on Mac: name only. Camera off |
| Render arm video   62%-ish  12m   [x]  |
| Waiting: Email to Jana          [Open] |
| Today: EUR 0.84 API, Max in limits     |
| Quick Chat   Mute   Guest   Dashboard  |
+----------------------------------------+
```

The "62%-ish" stands for whatever real measure exists, such as segments done of a known count. If none exists, it shows the step instead.

Keyboard: hold Right Option to talk [docs-only: platforms/mac/voicewake.md]. Double-click orb or Shift to stop. Global mute hotkey to add. Full VoiceOver order: state, caption, buttons.

### 25.2 iPhone

**V1: OpenClaw app** with Action Button shortcut for Talk, which opens the app and needs unlock [docs-only: platforms/ios.md], Approvals inbox with count, Chat, push, and a local Live Activity [track: apps.md]. iPhone model seen by the vision track supports the camera path. Check for an Action Button. Siri AI is not available on EU iPhones, so this path has no Apple equivalent today [verified: Apple newsroom, section 3]. Apple's side-button route for voice apps appears unavailable in the EU [track: voice.md].

```text
LOCK SCREEN (generic text)         APPROVAL CARD (after unlock)
+------------------------+         +------------------------------+
| Jorah                  |         | Send email      T3   9:12    |
| Needs your approval    |         | To: jana@...                 |
+------------------------+         | Subject: Thursday            |
                                   | [full exact body, scrollable]|
                                   | Why: you asked at 14:02      |
                                   | Undo: none after sending     |
                                   |                              |
                                   | [ Deny ]     [ Allow once ]  |
                                   +------------------------------+
                                   44 pt targets, far apart, Deny on the left.
```

The full body on this card is the target. See the card text limit in section 14.

**Own thin app (V3, only if the gaps justify it):**

```text
HOME (one screen)                  LIVE ACTIVITY (Lock Screen and Island)
+------------------------------+   +----------------------------+
| Jorah          Mac OK  PC OK |   | Render arm video  ~12 min  |
| Mic: phone off, room switch  |   | step 4 of 7        [Stop]  |
| Camera: off                  |   +----------------------------+
|------------------------------|   Compact island: dot, "12m".
| Waiting (1)                  |   Up to 8 h active, 4 h more on the
|  Email to Jana        [Open] |   Lock Screen [verified].
| Working (2)                  |
|  Render video     step 4/7   |
|  Fusion bracket   verifying  |
| Ready (1)                    |
|  First cut 11:48   [Review]  |
|------------------------------|
| (  hold to talk  )   [ type ]|
+------------------------------+
```

**Watch:** approval yes or no for T2 only; job finished; hold to talk is M1 Experimental [track: openclaw-fit.md].

**Wear OS:** the same three things, if Adam ever has an Android phone, since OpenClaw's Wear path proxies through it [track: apps.md]. Skip for now.

**Smart glasses:** not now [track: apps.md, vision.md]. If they come later, the rules are [inference]: indicator tied to camera power (U20), audio only in the ear, no proactive visuals while moving, guest rules apply to everyone in view, and no T3 approvals on the glasses.

### 25.3 Dashboard

```text
JORAH                 as of 14:32 | Freeze | Guest | Mute all | Export
+----------------------+----------------------+----------------------+
| NOW                  | DID TODAY            | COSTS (month)        |
| Mac    name only     | 42 actions           | Budget  EUR 190      |
| Room   switch OFF    |  T0 31  T1 8  T2 2   | API     EUR 41       |
| Phone  off           |  T3 1   denied 0     | Voice   EUR 12, 7 h  |
| Camera off everywhere| 1 failed: EduPage    | Max     in limits    |
| Cloud  none          | [Open log]           | [Details]            |
+----------------------+----------------------+----------------------+
| LEARNED (7 days)     | PROACTIVE            | ACCESS               |
| 3 facts, 1 skill     | Spoken 2/3           | Mail       read      |
| "render-youtube" v3  | Push   3/5           | Calendar   read/draft|
|   [Diff] [Undo]      | Acted on 60%         | EduPage    read      |
| from web: 0          | Types on: 3 [Manage] | Mac node   xcodebuild|
+----------------------+----------------------+----------------------+
| EVIDENCE: voice wake: installed, launched, device: not yet         |
| SCHEDULES: heartbeat hourly (approved 11-02), digest: not set      |
+--------------------------------------------------------------------+
On phone: one column, order NOW, DID, COSTS, LEARNED, PROACTIVE, ACCESS, EVIDENCE.
Example values only, to show layout. A real page shows real data or "not available".
```

---

## 26. Build order and acceptance

Each step ends with the exact test and its evidence tier. All changes to config, services or schedules need preview and Adam's yes. Numbers match the voice track's V0, V1, V2.

| Step | What | Depends on | Acceptance |
|---|---|---|---|
| **UX0 Persona** | Adam picks persona, name pronunciation, quiet hours. Write `SOUL.md`, `IDENTITY.md` from section 5. No code | Adam | Read 10 lines aloud. Adam says yes. Tier: source |
| **UX1 V0 ear** | Mac app, Voice Wake, Talk, one ear, triggers set. Chimes on. Soft mute test | Voice V0, security config | See 26.1. Tier: device |
| **UX2 Stop and show** | Stop vocabulary as far as native allows. `show_widget` to the panel. Speak-or-show rules in `SOUL.md` | UX1, Canvas plugin | "Summarise this" shows a panel without focus loss. Tier: device |
| **UX3 iPhone approvals** | iOS app paired with least authority, Approvals inbox, Action Button shortcut | Security T2 and T3, iOS pairing | Trigger a T3 test action on a dummy recipient. Card shows exact args. Deny blocks it, Allow runs once. Also try a body over 512 characters and record what the card shows. Tier: signed-in device |
| **UX4 V1 realtime** | Fast voice in front, consult behind. Idle-close helper before daily use [track: voice.md]. Filler tiers, progress-line helper, steer vocabulary, barge-in on headphones and speakers, spoken yes then tap, voice bake-off | Voice V1, keys | Bench: 30 scripted turns. Latency table recorded. Tier: device |
| **UX5 Trust report** | On-demand dashboard report from real logs. Failure-injected source shows "not available" | `jorah-guard` log | Five questions under 10 s on a phone. Tier: device |
| **UX6 Proactive** | Enable 2 types through preview cards: job finished and blocked, delivered by Telegram. Budget by count report | Adam's yes for each | One week; numbers in report. Tier: device |
| **UX7 Earcons and diary** | Render set, wire where possible. 7-day diary | V1 stable | Blind test, diary read together |
| **UX8 `jorah-presence`** | State hub, budget in code, digest queue. The idle close ships earlier, in UX4 | Voice V2 work | Kill the gateway: light stays honest. Over-budget message goes to the digest |
| **UX9 Room unit and light** | Voice PE or DIY, hardware mute, broker, second ear | Hardware track | Packet capture while muted shows no audio. Two-ear test: one reply, 50 of 50 |
| **UX10 Review pages** | Video review page, 3D view | Creative track | Adam reviews one real video on a phone |
| **UX11 Own iOS app** | Only if UX3 and the diary show the need: Live Activities, Face ID, home | Adam's decision | Signed-in device |

### 26.1 UX1 test script (for Adam, once the Mac app is installed)

1. Open **Dashboard, Settings, Talk, This Mac** [docs-only: platforms/mac/voicewake.md]. Language `en-US`. Voice Wake on. Trigger and send chimes on.
2. In **Settings, Talk**, set trigger words to `jorah`, `hey jorah`, plus any spelling variants from the voice track's test [track: voice.md].
3. Say "Hey Jorah", wait for the chime, say "what time is it". Expected: overlay shows your words, then a spoken reply. Slow is expected on V0.
4. Say "Hey Jorah what time is it" in one breath. Expected: likely fails, because of the 0.55 s pause. Record what happens.
5. Say "Hey Jorah", then nothing. Expected: overlay closes after about 5 s, nothing sent.
6. While it speaks, talk over it. Expected on headphones: playback stops. Note the delay.
7. Turn Voice Wake off. Expected: macOS recording indicator goes off within 2 s. If it does not, this is a privacy bug. Stop and report.
8. Count false wakes for one evening with TV on.

Record pass or fail per line, with OpenClaw version. Installer success is not launch, and launch is not acceptance.

---

## Slovak, EduPage and other people (short)

- **Language.** English is the default, as assumed. Wake must run in `en-US` on this Mac; Slovak has no on-device recognition here [track: voice.md]. Gemini Live lists Slovak [verified: https://aistudio.google.com/docs/live-api/capabilities]. Smart Turn has no Slovak, so a Slovak conversation uses a fixed silence window [track: voice.md].
- **The realistic pattern is English with Slovak names** ("call pani Nováková", "Žilina"). Add a pronunciation list and a contact vocabulary. Test 20 such phrases in the V1 bench. Jorah speaks a Slovak name with the right stress or spells it on screen [inference].
- **EduPage.** Read-only at first, T4 for writes [track: security.md]. School items in Slovak: summarise in English on voice, show the original on screen with the date [inference]. The feature's first use is reviewed by Adam. No emotion inference and no profiling anywhere near school [track: vision.md]. Adam's role on EduPage (student, parent, teacher) changes what the feature means.
- **Other people.** Jorah says it is an assistant whenever it speaks or writes to anyone else, and never poses as Adam, even when drafting [inference]. This also matters for a business version. AI Act Article 50(1) puts the duty on providers: a system that interacts directly with people must tell them it is an AI, unless that is obvious [verified, unofficial copy of the text: https://artificialintelligenceact.eu/article/50/]. It applies from 2026-08-02, and the Digital Omnibus did not move it, according to secondary reports [secondary, written before publication: https://www.iubenda.com/en/blog/ai-omnibus-adopted-august-2-obligations-july-2026/]. EUR-Lex returned no readable text, so the final Omnibus wording is [unverified]. Article 2(10) exempts natural persons as deployers in purely personal, non-professional use [verified, same unofficial copy: https://artificialintelligenceact.eu/article/2/]. That exemption names deployers, not providers, so a self-built Jorah that writes to other people should keep disclosing anyway [inference, not legal advice]. Check the Official Journal text before any business step [track: security.md].

**Business note.** The approval card, evidence wording and trust page are the most reusable parts, and the most honest differentiator [inference]. Do not plan features around this yet.

---

## 27. What I could not confirm

- **No long-term usage data for any 2026 product.** Alexa+ and Gemini for Home sentiment rests on press reports of Reddit threads and one vendor's review mining, which is US Android only, counts mentions and tested no devices. Complaints skew negative. Treat the ranked list in section 3 as my reading.
- **Pages that would not open or came back truncated:** TechRadar and Tom's Guide on Alexa+, Android Authority and Android Central on Gemini for Home, GeekWire, The Verge, OpenAI's index pages and Voice Mode FAQ, Nabu Casa support, Apple's app-lock page, Ropes & Gray. Claims from these carry `[search-snippet]`.
- **Studies transfer loosely.** The filler and latency studies used VR avatars, and the Goetsu and Sakai preprint is not listed as peer reviewed. The Mark study is about office tasks.
- **Friend:** one full review read. The Wired review was seen only second-hand.
- **Humane and Rabbit** still rest on Wikipedia. I did not find better sources this pass.
- **Google's follow-up time:** the help page I opened says about 10 s for Continued Conversation. A search summary of a copy of that page said about 8 s, and press calls it "a few seconds". The 8 s here is my starting value, whichever is current.
- **Alexa+ in Slovakia:** not found. Alexa's follow-up window and official light meanings: no Amazon page found.
- **Vendors' arbitration methods** are not published in full. Amazon's numbers are from simulation.
- **Whether Siri AI actually runs on this M1 Max.** Apple lists Mac with M1 or later for Apple Intelligence, so it should. Not tested. 9to5Mac says custom voice options need M3 or newer with 12 GB.
- **Whether Gemini's API reports chosen silence as an event.** Not found, so section 10 uses a timer.
- **Whether iOS app lock covers notification actions and the Watch.** Test in UX3.
- **Critical Alerts eligibility** for a personal app: not found.
- **Whether OpenClaw's Mac app allows custom chime files.** Docs mention toggles only.
- **Whether Talk has any idle auto-close.** Not documented.
- **Whether Voice PE works with our stack without Home Assistant.** Spike needed.
- **Final Digital Omnibus text.** EUR-Lex returned no readable text. Article 2(10) and Article 50(1) were read on an unofficial copy.
- **Items the skeptic pass left open** are listed under Verification.
- All numbers labelled `[inference]`, including every timer and budget in this file. They are starting values.
- Nothing here has been heard, seen or felt on a device.

## 28. Sources

Opened in the second pass:

- Siri AI: https://www.apple.com/newsroom/2026/09/siri-ai-a-profoundly-more-capable-and-personal-assistant-is-here/, https://support.apple.com/en-us/127901, https://engadget.com/2189932/siri-ai-for-iphones-and-ipads-will-be-delayed-indefinitely-in-the-eu, https://9to5mac.com/2026/09/17/macos-27-golden-gate-siri-ai-top-features-apples-assistant-finally-comes-to-life-video/
- Apple devices: https://support.apple.com/en-my/105077, https://support.apple.com/en-us/108331
- Alexa+: https://www.aboutamazon.com/news/devices/alexa-plus-personality-styles, https://www.pcworld.com/article/3071273/alexas-new-ai-personalities-are-cringe.html, https://www.storyboard18.com/brand-marketing/amazon-auto-upgrades-echo-devices-to-alexa-plus-leaving-users-divided-87623.htm, https://www.pymnts.com/amazon/2026/amazon-chooses-uk-for-alexa-european-debut/
- Alexa arbitration: https://arxiv.org/abs/2112.04914 (and its PDF), https://venturebeat.com/ai/amazon-cloud-esp-lets-alexa-devices-team-up-to-judge-user-proximity (2018; press guess that the strongest signal wins)
- Google: https://support.google.com/googlenest/answer/7685981?hl=en, https://www.thurrott.com/?p=335169, https://www.androidheadlines.com/2026/01/gemini-update-for-google-home-doesnt-seem-to-be-all-that-smooth.html, https://www.gearbrain.com/google-assistant-checks-response-mistake-2653276514.html, https://aistudio.google.com/docs/live-api/capabilities, https://unstar.app/blog/google-home-gemini-voice-commands-worse-reviews-2026
- OpenAI: https://techcrunch.com/2026/07/08/openai-releases-new-voice-models-for-more-natural-live-conversations/, https://developers.openai.com/api/docs/guides/live, https://developers.openai.com/api/docs/guides/voice-agents, https://deploymentsafety.openai.com/gpt-live-1-1, https://findskill.ai/blog/chatgpt-new-voice-gpt-live/
- Friend: https://fortune.com/2025/10/03/friend-ai-necklace-review-avi-schiffmann/
- Meta: https://thenextweb.com/news/meta-ray-ban-privacy-light-fix-cameraless, https://www.bgr.com/2191890/ray-ban-meta-led-block-mod/
- Alexa behaviour guides: https://www.bgr.com/2197288/reasons-ditch-amazon-alexa-device/, https://maketecheasier.com/smart-home/alexa-echo-lights-explained
- Anthropic: https://www.anthropic.com/engineering/claude-code-auto-mode
- Research: https://arxiv.org/html/2507.22352, https://arxiv.org/html/2508.11781v1, https://arxiv.org/abs/2002.03582, https://www.interruptions.net/literature/Mark-CHI08.pdf, https://www.microsoft.com/en-us/research/publication/like-having-a-really-bad-pa-the-gulf-between-user-expectation-and-experience-of-conversational-agents/
- W3C: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html

Search-result summaries only (page not read in full): https://www.techradar.com/ai-platforms-assistants/were-definitely-beta-testing-this-technology-is-alexa-really-bad-or-are-our-expectations-for-free-services-too-high, https://eftm.com/2026/06/alexa-rolls-out-to-more-countries-but-australia-has-to-wait-till-2027-276635, https://www.androidauthority.com/gemini-for-google-home-impressions-3633043, https://the-gadgeteer.com/?p=519044, https://thenextweb.com/news/apple-ios-27-siri-ai-release-icloud-plus-child-safety, https://www.kunalganglani.com/blog/local-ai-voice-assistant-whisper-piper-ollama, https://github.com/riepecjeuloc/willow, https://advertising.amazon.com/fr-fr/resources/whats-new/self-service-conversational-entertainment-ads-on-alexa-plus, https://openai.com/index/sycophancy-in-gpt-4o/, https://openai.com/index/expanding-on-sycophancy/, https://en.community.sonos.com/amazon-alexa-sonos-229102/nearest-sonos-one-doesn-t-respond-6804231, https://patents.google.com/patent/US11670293, https://support.nabucasa.com/hc/en-us/articles/25918770371229, https://support.apple.com/guide/iphone/lock-or-hide-an-app-iph00f208d05/ios, https://www.ropesgray.com/en/insights/viewpoints/102nfqm/you-talkin-to-me-operationalising-the-eu-ai-acts-transparency-obligations

Opened in the first pass:

- Apple HIG Siri: https://developer.apple.com/design/human-interface-guidelines/siri (read through its JSON at https://developer.apple.com/tutorials/data/design/human-interface-guidelines/siri.json)
- Apple HIG Accessibility JSON: https://developer.apple.com/tutorials/data/design/human-interface-guidelines/accessibility.json
- Apple interruption levels: https://developer.apple.com/tutorials/data/documentation/usernotifications/unnotificationinterruptionlevel.json
- Apple authenticationRequired: https://developer.apple.com/tutorials/data/documentation/usernotifications/unnotificationactionoptions/authenticationrequired.json
- Apple Live Activities: https://developer.apple.com/tutorials/data/documentation/activitykit/displaying-live-data-with-live-activities.json
- Apple hardware mic disconnect: https://support.apple.com/guide/security/hardware-microphone-disconnect-secbbd20b00b/web
- Apple Mac mic control: https://support.apple.com/guide/mac-help/control-access-to-the-microphone-on-mac-mchla1b1e1fe/mac
- Apple Voice Trigger research: https://machinelearning.apple.com/research/voice-trigger
- Amazon Alexa design: https://developer.amazon.com/en-US/docs/alexa/alexa-design/get-started.html, https://developer.amazon.com/en-US/alexa/alexa-haus/natural-speech, https://developer.amazon.com/en-US/alexa/alexa-haus/patterns-and-components/patterns-errors, https://developer.amazon.com/en-US/alexa/alexa-haus/patterns-and-components/patterns-feedback
- Google: https://blog.google/products/google-nest/gemini-for-home/, https://gemini.google/overview/gemini-live/, https://aistudio.google.com/docs/live-api/capabilities, https://pair.withgoogle.com/chapter/errors-failing/
- OpenAI: https://developers.openai.com/api/docs/guides/realtime-vad
- LiveKit: https://docs.livekit.io/agents/build/turns/
- Sesame: https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice
- Home Assistant: https://www.home-assistant.io/voice-pe/, https://www.home-assistant.io/voice_control/, https://www.home-assistant.io/voice_control/about_wake_word/, https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/assist_pipeline/const.py, https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/assist_pipeline/run.py
- ESPHome: https://esphome.io/components/voice_assistant.html
- OHF Voice: https://github.com/OHF-Voice/linux-voice-assistant
- openWakeWord: https://github.com/dscripka/openWakeWord
- Picovoice wake word tips: https://picovoice.ai/docs/tips/choosing-a-wake-word/ (fewer than six phonemes not recommended; a prefix like "Hey" helps). "Jorah" alone is short, so favour "Hey Jorah" for accuracy [inference]; the voice track tests both.
- Limitless: https://www.limitless.ai/
- Nielsen Norman: https://www.nngroup.com/articles/response-times-3-important-limits/
- Microsoft HAI: https://www.microsoft.com/en-us/research/publication/guidelines-for-human-AI-interaction/
- W3C: https://www.w3.org/TR/WCAG22/, https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Wikipedia (secondary): https://en.wikipedia.org/wiki/Humane_Inc., https://en.wikipedia.org/wiki/Rabbit_r1, https://en.wikipedia.org/wiki/Friend_(product), https://en.wikipedia.org/wiki/Alexa%2B, https://en.wikipedia.org/wiki/Siri, https://en.wikipedia.org/wiki/J.A.R.V.I.S.

OpenClaw 2026.10.9 bundled docs: `nodes/talk.md`, `nodes/talk/client-ui.md`, `nodes/talk/macos-relay.md`, `nodes/talk/realtime-sessions.md`, `nodes/talk/session-ownership.md`, `nodes/voicewake.md`, `platforms/mac/voicewake.md`, `platforms/mac/voice-overlay.md`, `platforms/mac/menu-bar.md`, `platforms/mac/canvas.md`, `platforms/ios.md`, `platforms/windows.md`, `web/notifications.md`, `web/dashboards.md`, `web/control-ui/feature-reference.md`, `tools/show-widget.md`, `tools/skill-workshop.md`, `tools/permission-modes.md`, `tools/exec-approvals-advanced.md`, `gateway/heartbeat.md`, `maturity/scorecard.md`.

Sibling research: `brain.md`, `creative.md`, `growth.md`, `openclaw-fit.md`, `security.md`, `topology.md`, `vision.md`, `voice.md` in this folder.

---

## Adam decides

1. **Persona:** dry colleague (my pick), British butler, or warm? Accent is separate.
2. **Wit:** how much? Rationed at about 1 in 20, or none?
3. **Name and pronoun for Jorah:** how is it pronounced (`JOR-uh` or Slovak-style `Džora`)? "It", or something else?
4. **U9:** may a spoken yes confirm own-calendar and similar T2 actions when at the unlocked Mac, with undo? This relaxes the security track's one-tap rule. My pick is yes for own data only.
5. **Language:** English only for V1, with Slovak names handled? Or Slovak conversation too?
6. **Quiet hours:** what hours? Which proactive types first (my pick: job finished and job blocked only)?
7. **Stop semantics:** is "stop" ending speech only, with "cancel that" for work, acceptable?
8. **Your EduPage role:** student, parent or teacher? It changes that feature's design.
9. **Who else lives or visits where the ears are?** This sets how much guest mode and hardware mute matter, and how soon.
10. **20-second send hold:** on or off?
11. **Room unit:** DIY puck as part of the learning project (my pick), or Voice PE (€59) with Home Assistant, once V1 works?
12. **Siri on the Mac:** do you use it today? If yes, Jorah leaves quick Mac tasks to it (U21). If no, Jorah takes them too.
13. **U8 on V1:** accept OpenClaw's spoken yes followed by a tap for gated actions? My pick is yes, rather than patching the gate.

---

## Verification

Independent skeptic pass, 2026-11-02. I tried to refute the claims a plan would most depend on, by opening sources myself and reading the bundled docs and shipped code. Nothing was installed or run, and nothing has been tried on a device. **The web search budget ran out partway through,** so some items below were checked only by opening known URLs, and a few were not rechecked.

### Does the recommendation still hold?

**Mostly yes.** The bottom line and most decisions stand: a quiet colleague persona, "stop" separate from "cancel", one ear first, OpenClaw's surfaces before our own, and proactive off by default.

| Item | Change |
|---|---|
| **U8 approval handoff** | **Recommendation changed.** One step cannot be delivered on V1 as shipped. V1 is OpenClaw's spoken yes, then the tap. Adam decides (item 13) |
| **Build order** | Idle close and progress lines move from V2 or "exists" into V1 (UX4). V1 needs more build than the first passes said |
| **U5 follow-up windows** | Timings stand, but they need the V1 helper, and V1 cannot promise that side talk is discarded |
| **U14 iPhone** | Still the OpenClaw app first, with two named gaps: Telegram for job notices, and no long message body on the card |
| **U17, U19, section 10** | Conclusions stand, and their reasons are corrected for the actual V1 pick |

### Corrected

| Claim in the earlier text | What I found | Evidence |
|---|---|---|
| Gemini 3.8 Live is "the voice track's V1 pick" (U17, section 10) | The V1 pick is `gpt-realtime-2.1-mini`, and Gemini is the runner-up. The facts about Gemini were right but applied to the wrong model | `voice.md` decision table and its section on the pick change |
| "No spoken yes before the tap" (U8) | The Gateway requires an exact spoken yes on relay and consult runs. It runs before plugin approvals and has a 2-minute expiry. No off setting found | `nodes/talk/realtime-sessions.md`; `dist/agent-tools.before-tool-call-CQkX3nOj.mjs`; `dist/tool-mutation-BTW6eoAN.mjs` |
| Realtime allows truthful narration at intervals (finding 1, section 8) | Built-in prompt: one brief acknowledgement, then wait. Status on request. Instructions only append. No self-speaking progress path found | `DEFAULT_REALTIME_INSTRUCTIONS` and the consult working response in `dist/handlers-B5Rt4cMl.mjs`; `nodes/talk.md` |
| Auto-close built in UX8 (V2) | Voice track needs it before daily use in V1. The 30-minute limit covers any relay session, not only GPT-Live | `voice.md` finding 8; `RELAY_SESSION_TTL_MS` |
| Rejected speech "never reaches memory or tools" | On V1 the audio has already reached the provider, and finalized utterances are always appended to the session | `nodes/talk/realtime-sessions.md` |
| Use OpenAI semantic VAD in the window | OpenClaw's OpenAI bridge configures `server_vad`, with no `semantic_vad` found | `dist/extensions/openai/capability-catalog.js` (search only) |
| Approval card shows the "full exact text, scrollable" | Description capped at 512 characters, title at 80. Exec cards show a sanitized preview | `plugins/plugin-permission-requests.md`; `platforms/ios.md` |
| Approvals are "held" through quiet hours | Plugin approval timeout defaults to 2 minutes, capped at 10 | `plugins/plugin-permission-requests.md` |
| iOS notification for "send it to my phone" and job finished | `system.notify` works only while the app is active. No job-finished push. `web/notifications.md` covers browser and Mac, not the iOS app | `platforms/ios.md`; `apps.md` |
| "iOS suspends background voice" | Docs say it may suspend, and voice is best-effort. Action Button needs unlock and foreground | `platforms/ios.md` |
| Headphones needed on Mac speakers | True for continuous providers such as GPT-Live. Turn-based providers keep echo suppression. Only the GPT-Live bridges declare continuous output | `nodes/talk/macos-relay.md`; provider code |
| "Stop" keeps a 4 s window on every provider | An explicit GPT-Live stop ends the voice session | `nodes/talk/macos-relay.md` |
| Realtime "billed per second" | True for GPT-Live. The V1 pick bills per token | `voice.md` pricing table |
| Siri AI "server features have daily limits" | Limits are to come later, with no daily figure given | https://support.apple.com/en-us/127901 |
| Apple Developer fee [unconfirmed] | $99 a year | https://developer.apple.com/programs/ |
| AI Act Article 50 applies to personal use: unknown | Article 50(1) is a provider duty with an "obvious" exception. Article 2(10) exempts personal-use deployers | artificialintelligenceact.eu articles 50 and 2 (unofficial copy) |
| "The market now agrees", Brief is what a reviewer "could live with" | One reviewer, who kept the default. Amazon's page shows no date | PCWorld, 2026-02-25; aboutamazon.com |
| Gemini Live is "paid" per Google's post | Post mentions free and paid versions only | blog.google |
| Meta: "newer models", caps "can still fool" it | Second-generation models. The caps report is from 10 June, before the 7 July fix | thenextweb.com; bgr.com |
| Live Rewind cited to section 3 | Not in section 3. It is a Watch feature, due in beta in late 2026 and not initially in the EU | Apple newsroom |
| `speed` and `rate` for speech rate | Documented for Talk TTS only | `nodes/talk.md` |
| "Six fixed verbs" (U12) | Section 16 lists seven words, adding "Remember". U12 now says seven | This file |
| `ai.google.dev` Live capabilities link | Returns 301 to `aistudio.google.com`. Same content | Opened both |

### Held up

| Claim | Checked against |
|---|---|
| Native Talk speaks only after the run completes | `nodes/talk/macos-relay.md` |
| Wake timers: 0.55 s pause, 2.0 s, 5.0 s, 120 s, 350 ms; on-device requirement | `platforms/mac/voicewake.md` |
| No voice arbitration; wake words are one global list | `nodes/voicewake.md`, plus a search of all docs |
| Panel takes no focus, `show_widget` report with `pin`, first committed answer wins, skill undo, quiet hours suppress | `platforms/mac/canvas.md`, `tools/show-widget.md`, `platforms/ios.md`, `tools/skill-workshop.md`, `web/notifications.md` |
| Siri AI not on EU iOS, iPadOS or watchOS, and on macOS 27 | Apple newsroom (June and September), Engadget. Results found ran only to July for the EU position |
| Google's 10 s and 15 s windows, closers, exclusions | Google Nest help page |
| Gemini: proactive audio always on, affective dialog removed, 15 and 2 minute limits, 500 to 800 ms, pending calls discarded, `sk` listed | aistudio.google.com Live capabilities page |
| Voice PE: €59, power-cut wording, XMOS, SmarterHOME in Slovakia | home-assistant.io/voice-pe |
| Home Assistant: first wins, 2 s cooldown keyed by phrase | `const.py`, `run.py` |
| Apple's arbitration wording, lid and face-down behaviour | support.apple.com/en-my/105077 |
| Hardware mic disconnect on lid close; camera obstructed, not cut | Apple security guide |
| Live Activity 8 h plus up to 4 h | Apple ActivityKit documentation |
| Apple: avoid humor, keep responses succinct, stand alone without visuals | HIG Siri JSON |
| Anthropic 93% of prompts accepted | anthropic.com engineering post |
| Limitless dates and EU deletion | limitless.ai. The UK and five other regions were also cut off |
| Humane and Rabbit figures | Wikipedia only, still secondary |
| Fortune's six Friend details | fortune.com |
| Unstar 136 complaints and four shares; Storyboard18 complaints | Both pages. Unstar covers 13 April to 8 September 2026 and tested nothing |
| GPT-Live replaced Advanced Voice Mode; backend continues after interrupt; check saved state; 1.1 emotional reliance regression | TechCrunch, OpenAI docs, OpenAI system card (no figures in the page text) |
| VR studies: 54 people at 1.5, 4, 6.5 s; 24 people, 66.7% | arXiv HTML of both |
| openWakeWord targets | GitHub README |
| LiveKit truncation and false-interruption resume | LiveKit docs |

### Could not confirm

- **OpenClaw gate has no off switch:** searched config contracts and read the policy code, but did not run it. Test in V1.
- **Native Talk is outside the gate:** inferred from the documented scope.
- **Amazon's 36% to 49% figure:** not in the abstract, and the PDF would not parse.
- **CVE-2026-32065:** NVD and cve.org pages did not render.
- **Critical Alerts eligibility:** Apple's request page needs sign-in.
- **Digital Omnibus final text and the regulation number:** EUR-Lex returned nothing readable. Search summaries give Regulation (EU) 2026/1744, published 2026-07-24, and I did not rely on that.
- **Semantic VAD on `gpt-realtime-2.1-mini`:** not mentioned on its model page.
- **Whether Meta's fix stops light-passing caps.**
- **Voice PE without Home Assistant:** Nabu Casa's page returned 403. The product page does not state it either way.
- **Not rechecked, search budget gone:** Apple's EU side-button position, Alexa+ in Slovakia, any Siri AI EU change after July, and Gemini for Home's paid status for Live.
