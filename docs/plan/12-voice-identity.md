# 12. Voice identity and guest mode

Adam, 2026-11-19: "can you create a plan for voice recognition so that if it doesn't recognize my voice, it goes into host mode and can only do some limited things". Adam's "host mode" is called **guest mode** here, the name the plan already uses. This file is the plan. Nothing in it is built, downloaded or installed. Every claim is a source, docs or read-only check unless it says [measured], and [inference] marks my judgment.

## 0. Bottom line

**Today anyone who speaks to Jorah is treated as Adam for everything except writes.** Every spoken turn, from the Mac, iPhone Talk or later the Pi, lands in `agent:main:main`: the same chat as Telegram, with `USER.md`, `MEMORY.md` and the day's conversation in the model's context. The guard (P5, live since 2026-11-13) makes voice-asked writes, jobs and schedules wait for a Telegram tap, but it lets reads through. So a visitor who says "Jorah, what did Adam tell you about the robot budget?" hears the answer. No tool rule can stop that, because the answer is already in the model's context.

**The fix:** `jorah-voice` checks who is speaking on every turn, on the PC, before it sends the words anywhere.

| Verdict | Where the words go | What Jorah can do |
|---|---|---|
| **Adam** (speaker check passes) | `agent:main:main`, as today | Everything voice can do today. P5's voice rules still apply: writes wait for a tap, and confirmation by voice follows `p5-plan.md` 4.3 |
| **Someone else, or unsure** | A separate `guest` agent, in a session deleted when the conversation ends, and only if they said "Jorah". Otherwise nothing leaves the PC | Public questions only. No memory, no files, no chat history, no tools beyond web search. Nothing about Adam is in its context |
| Check broken or model missing | Guest, for everyone, until it is fixed (decision V5) | As guest |

**Four layers enforce it, and the prompt is only for tone:** routing in `jorah-voice` (a guest's words never reach `main`), the `guest` agent's own OpenClaw tool allowlist, a `guest` section in `jorah-guard`'s matrix that blocks every other tool and fails closed, and a guest workspace with no private files.

**Voice identity is a privacy line, not a key.** A recording or a clone of Adam's voice passes it (section 9). So voice alone never unlocks money, messages to others, pushes or secrets. Those rules stay as Adam set them on 2026-11-11: voice alone only for actions that stay on the PC and can be undone, voice plus the card's 4-digit code for anything that leaves it, and a Telegram tap always.

**Adam overrides from Telegram** with `/voice` commands: guest mode for everyone while visitors are over, "that was me" for the current conversation, enrol, forget (section 8). Voice can never turn guest mode off.

**Cost:** one 101 MB model on the CPU, no GPU memory, and about no added delay, because the check runs alongside speech recognition on the same audio [inference, measured in VI-S1]. Guest answers run on Haiku 5.5 on the API key, not on Max (section 5.3).

| Piece | What it is | Section |
|---|---|---|
| Speaker check | NeMo TitaNet-Large through sherpa-onnx, already installed on the PC; enrolment of Adam only | 3, 4 |
| Routing | `jorah-voice` sends each turn to `main` or `guest` by verdict | 5 |
| Guest agent | `openclaw agents add guest`: own workspace, no memory, web search only, API key | 5, 6 |
| Guard section | `guest` rules in `config/permission-matrix.json` | 6 |
| `/voice` commands | Telegram-only overrides, in `jorah-voice-provider` | 8 |

## 1. What exists today

Read on 2026-11-19 from the repo and a read-only check on the PC.

| Path | How audio reaches Jorah | Identity today |
|---|---|---|
| Mac, `mac-ear` (push or wake word) | Tailscale Serve `:43211` → `jorah-voice` on 127.0.0.1:43210 → Chat Completions into `agent:main:main` | None. Every turn is "asked by voice" to the guard |
| iPhone Talk (AirPods or phone mic) | Gateway relay → `jorah-voice-provider` → `jorah-voice`, same turn path | None |
| Talk in the Control UI in a browser | Gateway relay → `jorah-voice`, same path | None |
| Siri "Ask Jorah" | Dictated text, no audio → `jorah-phone` → `agent:main:main` | The phone's token; never confirms anything (`docs/runbooks/phone.md`) |
| Telegram voice notes | Transcribed by `jorah-transcribe` | Adam's allowlisted Telegram account. A forward taints |
| Pi room ear (P4, not built) | Will reach `jorah-voice` the same way | Will use this check |

**Every live-audio path meets in `jorah-voice`.** One check there covers the Mac, the iPhone, the browser and the future room ear. Siri and Telegram voice notes carry no live audio, so they are outside this plan (decision V9 covers Siri).

**On the PC** [measured 2026-11-19]: OpenClaw 2026.10.9. `openclaw-gateway`, `jorah-voice` and `jorah-voice-qwen` active. 15,868 MB RAM, 9,494 MB available. RTX 5070 at 5,876 of 12,227 MiB used. 28 CPU threads. The voice venv holds sherpa-onnx `2.0.1+cuda13`, which has `SpeakerEmbeddingExtractor` and `SpeakerEmbeddingManager`, so no new Python package is needed. No speaker model is downloaded. Agents: `main`, `background`, `deep`. `talk.realtime.provider` is `jorah-local`. Voice-session counts from the journal came back empty as user `jorah`, which more likely means no journal access than no sessions, so they are unknown.

**G-S8 has not run.** `p5-plan.md` 4.3 planned the speaker check for voice confirmation, and `docs/runbooks/voiceprint-recording.md` has the enrolment script, but the recordings folder on the Mac doesn't exist [measured]. Voice confirmation is still off: every voice-asked write waits for a tap (`docs/runbooks/jorah-on-pc.md`, "P5.5").

## 2. What this builds on, and what it changes

| Earlier text | Now |
|---|---|
| `p5-plan.md` 4.3 and roadmap 2a "Voice confirmation" (Adam, 2026-11-11) | **Unchanged.** This plan supplies G-S8's speaker check and adds a second use for it. G-S9, how a verified "yes" reaches the guard, stays in P5 |
| `03` section 8: "Speaker recognition: a hint for personalisation only. Never an approval" | Already changed for confirmations by Adam on 2026-11-11. Now also a privacy boundary: who may hear Adam's things. Still never an approval for anything that leaves the PC without the card's code |
| `03` 9.4 and `01` U23: guest mode **closes Talk**, typed use only | That rule existed because a cloud realtime provider heard every word in the room. With local voice, audio never leaves the PC, so guest mode becomes **limited, not closed**. Closed stays available as `/voice off` |
| README decision 25: "Unknown speaker: ignore, or public questions only?" Pick: public questions only | This plan builds that pick. Decision V1 confirms it |
| `04` M10.7: the room ear needs no voice enrolment | Still true for the wake word. The Pi's turns pass through this check on the PC like any other |
| Roadmap 2a, 2026-11-05: one agent | `guest` is a second agent with no memory and no reach. It is not a split of Jorah's brain. Decision V1 |

## 3. Who is speaking: the check

### 3.1 Model

Checked on 2026-11-19 against each project's own pages. A file must be at least 7 days old by its own upload date.

| Model | Source and licence | Size | Accuracy (VoxCeleb1-O cleaned EER, from its source) | 7-day rule |
|---|---|---|---|---|
| **NeMo TitaNet-Large**, ONNX export | sherpa-onnx release `speaker-recongition-models` (sic), file `nemo_en_titanet_large.onnx`; model card CC-BY-4.0 (`nvidia/speakerverification_en_titanet_large`); sherpa-onnx Apache-2.0 | 101 MB, about 23M parameters | 0.66% (NVIDIA's card). Trained on VoxCeleb 1 and 2, Fisher, Switchboard, LibriSpeech, SRE | **Passes.** Uploaded 2024-10-14 |
| WeSpeaker ResNet34-LM | Same release, `wespeaker_en_voxceleb_resnet34_LM.onnx`; CC-BY-4.0 (WeSpeaker: "follows the license of its corresponding dataset") | 27 MB, 6.6M | 0.797% (WeSpeaker's VoxCeleb recipe) | **Fails until 2026-11-26.** Re-uploaded 2026-11-19 10:27 UTC |
| CAM++ (WeSpeaker or 3D-Speaker exports) | Same release; WeSpeaker CC-BY-4.0, 3D-Speaker Apache-2.0 | 29 MB, 7.2M | 0.707% with LM (WeSpeaker) | **Fails until 2026-11-26.** Re-exported on 2026-11-19 after a pooling fix (sherpa-onnx #4237, #4241) |
| WeSpeaker ResNet293-LM | Same release; CC-BY-4.0 | 114 MB, 28.6M | 0.532% | Fails until 2026-11-26 |
| SpeechBrain ECAPA-TDNN | `speechbrain/spkrec-ecapa-voxceleb`, Apache-2.0 | PyTorch checkpoint | About 0.8% [unverified] | Needs PyTorch and SpeechBrain in the voice venv: a new dependency for no gain |
| AASIST anti-spoofing | `clovaai/aasist`, MIT, last pushed 2023 | Small | Trained on ASVspoof 2019 | Not used as a gate (section 9) |

**Pick: TitaNet-Large.** It passes the 7-day rule today, runs on the sherpa-onnx already in the venv, and is the most accurate of the ones that pass. **Second look on or after 2026-11-26:** score ResNet34-LM or CAM++-LM on the same calibration set, and switch only if it is clearly better on Adam's own data. The install records the file's SHA-256, checks it against the release's `checksum.txt`, and pins it in `jorah_voice/models.py` like the other models. `checksum.txt` was rewritten on 2026-11-19 with the re-exports; the TitaNet file itself was not (uploaded 2024-10-14). Attribution goes in `config/licenses.tsv` and ADR 0001's table, as for Parakeet.

### 3.2 Where it runs

In `jorah-voice`, on the CPU, on the turn's held speech segments: the same audio Parakeet transcribes. It starts at the 0.3 s early pause together with transcription, and is redone if more speech arrives, the way `session.py`'s `_listen` already redoes the transcript. When the turn ends, both the text and the verdict are ready, and only then does `jorah-voice` choose where to send the words.

- **Score:** cosine similarity between the turn's embedding and each enrolled device centroid (section 4); the highest counts.
- **Never stored:** the turn's embedding lives in memory for the turn and is dropped. Logs get the verdict and a score bucket (`<0.3`, `0.3-0.5`, ...), never the embedding, the score to three places, or any words.

### 3.3 Per turn, with a memory per conversation

**Every turn is checked.** Checking only the first turn of a session would let anyone speak after Adam opened it, and the check costs about nothing (section 11).

| Turn | Verdict |
|---|---|
| At least 1.2 s of speech, score at or above the high threshold | **Adam** |
| At least 1.2 s of speech, score at or below the low threshold | **Someone else** |
| Between the two thresholds | **Unsure** |
| Under 1.2 s of speech ("yes", "no", "thanks") | **Inherits** Adam if the last turn in this conversation, within 30 s, was Adam and nobody else has spoken since. Otherwise **unsure**. Confirmations never inherit (3.6) |
| "Stop", "quiet", "cancel", "goodbye" and the other exact commands in `core.classify` | **No check.** Honoured from anyone, before routing, as today |
| Two voices in one turn | Whatever the score says. Mixed speech usually scores low, so it ends as unsure or someone else, which is the safe side [inference, tested in VI-S1] |

**"Someone else is here" sticks for the conversation (decision V4).** When a turn is clearly someone else, and that person addressed Jorah (section 5.2), the rest of that voice session goes to `guest`, Adam's turns included, until it ends or Adam sends `/voice me`. Otherwise the visitor would hear Adam's next private answer. An **unsure** turn does not set it: one bad score shouldn't cost Adam the whole conversation.

**The honest limit:** the check knows who spoke, not who is listening. Someone who stays silent in the room hears whatever Adam asks for. That's what `/voice guest` is for (section 8).

### 3.4 When it's unsure

| Situation | What happens | What Adam hears |
|---|---|---|
| Unsure, first time in a conversation | The turn goes to `guest` if it said "Jorah" (5.2), otherwise nowhere | "I couldn't tell that was you. Say it again, a bit longer, or send /voice me in Telegram." Said by `jorah-voice` itself, before any guest answer |
| Unsure twice in a row | Same, and a neutral Telegram line once per conversation (decision V7): "Voice: I couldn't recognise the speaker, so I kept to guest mode." | As above |
| Model missing, failed to load, or threw | Every turn is guest (decision V5) | "I can't check voices right now, so I'm in guest mode. Telegram works as usual." Once per conversation |
| Override state unreadable | Ignored, so no "that was me" applies. Guest-for-everyone wins if it was set and the file is unreadable: the check fails toward guest | |

### 3.5 Thresholds and the trade-off

| Error | What it costs | How bad |
|---|---|---|
| **False accept:** a visitor, a TV or Jorah's own voice is taken for Adam | They hear Adam's memory and chat aloud, and their requests reach `main` with Adam's voice standing. Writes still wait for a tap, and anything that leaves the PC still needs the card's code | A privacy leak in the room. Worse once mail and calendar connect (M4) |
| **False reject:** Adam is taken for someone else | Guest answers. Adam repeats, speaks longer, or taps `/voice me` | Annoying, never harmful |

So the thresholds lean toward rejecting:

- **High threshold** (Adam): the lowest score with **zero** false accepts on the whole impostor set, plus a margin set from the spread of impostor scores.
- **Low threshold** (someone else): below nearly all of Adam's genuine scores, so Adam rarely triggers the sticky flag.
- **Bar, kept from G-S8:** 0 false accepts in the 300 played-through-a-speaker trials, and Adam turned away at most 1 in 20 per device. **What the bar proves:** 0 in 300 bounds the false-accept rate at about 1% with 95% confidence (the rule of three, 3/n). To show about 0.1%, VI-S1 also scores about 3,000 recorded clips offline (section 12.2). Adam can change the bar (decision V6).
- **Short speech is the weak spot.** Embeddings from under about 1 to 2 s are much less reliable [inference from the literature, measured in VI-S1], which is why 3.3 sets a floor and confirmations need a full phrase.
- **No learning on its own.** The voiceprint never updates itself from Adam's turns, because a slow drift toward a clone or a recording would be invisible. Re-enrolment is Adam's command.
- Thresholds live in `~/.config/jorah-voice/voiceprint/thresholds.json`, written by the calibration tool, with the calibration date and the counts behind them.

### 3.6 Confirmations

P5's voice confirmation (4.3) uses this same check, with three extra rules: the "yes" must be at least 1.5 s of speech (Jorah asks for "Yes, do it", not "yes"), it never inherits, and it must score **Adam**, not unsure. Unsure means a tap. G-S9 still decides the wiring.

## 4. Enrolment

**Who:** Adam only. Never a guest, never a child (`03` section 8).

**How, through the live path:** recordings from Voice Memos (the existing runbook) are compressed differently from what `jorah-voice` hears, so enrolment uses the real clients.

1. Adam sends `/voice enrol` in Telegram. The plugin writes an enrolment request (section 8). It lasts 15 minutes.
2. Adam opens a voice session on the first device. `jorah-voice` sees the request, says "Enrolment. Read the lines I say after me", and speaks the lines from `docs/runbooks/voiceprint-recording.md` part by part (about 90 s). The model is not involved, and nothing goes to the Gateway.
3. Repeat on each device Adam uses: Mac mic, AirPods on the Mac, iPhone Talk with AirPods, iPhone Talk on the phone's own mic. Each device gets its own centroid, because the microphone and Bluetooth codec change the embedding [inference].
4. `jorah-voice` checks each part's length and level, and says which device needs another go.
5. Adam sends `/voice enrol done`. The tool writes the centroids and the thresholds file. Then calibration runs (section 12.2), and the check stays in shadow mode until Adam says to enforce it.

**Stored** in `/home/jorah/.config/jorah-voice/voiceprint/` (folder 700, files 600): `centroids.json` (one vector per device, the model's name and file hash), `thresholds.json`, and **only until the shadow week ends,** the enrolment audio (WAV, about 6 minutes in all), so a second model can be scored on 2026-11-26 without re-recording (decision V6). Then the audio is deleted and only the vectors remain.

**Re-enrol** with `/voice enrol` again: after a model change, a cold that lasts, or if Adam's rejections climb. **Forget** with `/voice forget`: deletes the folder; `jorah-voice` then treats every turn as guest and says so.

## 5. Routing: Adam's turns and guest turns

```text
mic ──> jorah-voice: speech segments ──┬─> Parakeet ──────> text
                                       └─> TitaNet ───────> verdict
                         exact command? ──> handle locally (stop, goodbye, ...)
                         verdict Adam ────> Chat Completions, model openclaw/main,
                                            session agent:main:main (as today)
                         guest or unsure ─> addressed to Jorah? no ──> dropped unheard
                                            yes ─> model openclaw/guest,
                                                   session agent:guest:voice-<conversation id>
```

### 5.1 Adam's turns

Exactly today's path: `brain.py` with `openclaw/main` and `agent:main:main`. The guard keeps treating them as voice ("asked by voice"), because a recording of Adam passes the check. The only change for Adam is confirmation by voice, which P5 turns on separately.

### 5.2 Guest turns

- **Addressed or dropped (decision V3).** A guest or unsure turn goes to `guest` only if Parakeet's text contains "Jorah" or a close mishearing (a short list in code, like `lexicon-names.txt`). Otherwise nothing is sent: a someone-else turn is dropped silently, and an unsure one gets only `jorah-voice`'s own "I couldn't tell that was you" line (3.4). Nothing reaches the Gateway or Anthropic, and nothing is kept. That keeps a visitor's conversation with Adam, or the TV, out of the cloud entirely.
- **Own agent, own session:** `model: openclaw/guest`, `x-openclaw-session-key: agent:guest:voice-<random id per voice session>`. `main`'s context, memory and chat are never in it.
- **Deleted at the end:** when the voice session closes, `jorah-voice` deletes the guest session through the Gateway. OpenClaw's incognito sessions keep everything in memory, but they can only be started from the Control UI [docs: `concepts/session.md`], so VI-S2 checks whether a Chat Completions caller can open one; if not, deletion is the path. The daily 04:00 reset bounds anything a failed delete leaves.
- **Caps:** 20 guest turns per voice session and 60 a day (decision V1), counted in `jorah-voice`. Then "That's all I can do for guests today."
- **Voice note:** the guest request carries its own short system note: speaking to a guest, aloud, one to three sentences.

### 5.3 The `guest` agent

| Setting | Value | Why |
|---|---|---|
| Id, workspace | `guest`, `/home/jorah/workspace-guest` from `workspace-guest/` in the repo | Separate from `main`'s, so no `USER.md`, `MEMORY.md`, `memory/`, skills or daily notes are loaded |
| Workspace files | `AGENTS.md` (guest rules and the lines in section 7), `SOUL.md` (Jorah's tone), `IDENTITY.md`. Nothing about Adam except that Jorah is Adam's assistant | A test fails the build if any other file appears (12.1) |
| Model and lane | Haiku 5.5 on the **API key**, embedded runtime | A guest is a third party, and Anthropic's consumer terms are read as not covering third-party traffic on a subscription (README decision 4). The embedded runtime also shows the model only OpenClaw's tools, not Claude Code's own. Under the existing $80 cap |
| Tools | `tools.allow: ["web_search"]` (decision V1). Everything else denied, including `web_fetch`, `browser`, `message`, `sessions_*`, memory, files, cron, GitHub | OpenClaw stops a run whose allowlist leaves no tool [docs: `tools/multi-agent-sandbox-tools.md`], so with web search off the guest gets one harmless read tool instead (`session_status`, checked at build) |
| Sandbox | On, no workspace write | No file it could leave behind |
| Memory, Dreaming | No memory plugin for `guest`. VI-S3 checks that Dreaming and `memory_search` never read `agent:guest:*` sessions, and that `main`'s `sessions_search` can't see them | A guest's words must not become Adam's facts |
| Bindings | None. Reached only through Chat Completions from `jorah-voice` | Telegram never routes to it |

## 6. Guest mode: what is allowed and blocked

| Guests can | Guests can't | Enforced by |
|---|---|---|
| Stop Jorah's speech, end the conversation | | `jorah-voice`, before routing |
| Ask the time, the date, maths, conversions, general knowledge | | The `guest` agent's own model |
| Ask public questions that need the web (weather, news, opening hours), if decision V1 allows | | `web_search` on `guest` only. The guard caps queries at 200 characters as for any session that has read outside text |
| | Hear anything about Adam: memory, `USER.md`, the chat, projects, repos, supplies, phone data, later mail and calendar | Routing: none of it is in `guest`'s context, and no tool reaches it |
| | Save, change or forget anything: memory, rules, skills, reminders, schedules | `guest`'s tool allowlist, then the guard's `guest` section |
| | Start jobs: Claude Code, `background`, `deep`, project runs | Same |
| | GitHub: clone, sync, push, pull requests | Same |
| | Send anything to anyone, Adam included | Same (`message` blocked) |
| | Confirm any card, by voice or otherwise | Guest turns never reach `main`, and confirmations need **Adam** (3.6) |
| | Open web pages, type into them | Same |
| | Turn guest mode off, enrol, or change voice settings | Only Telegram commands do that (section 8); no tool exists for it |

**The guard's `guest` section,** added to `config/permission-matrix.json`, is checked first for any call whose `agentId` is `guest` or whose session key starts with `agent:guest:`:

```json
"guest": {
  "about": "docs/plan/12-voice-identity.md section 6. Agent guest gets only these tools; anything else is blocked, whatever its class.",
  "agents": ["guest"],
  "sessionPrefixes": ["agent:guest:"],
  "allow": ["web_search", "session_status"]
}
```

A listed tool then goes through its normal rule (`web_search` keeps its 200-character cap, since a guest session is never Adam's own chat). It is defence in depth: the agent's OpenClaw allowlist already removes the other tools. A missing or unreadable `guest` section blocks every call from `guest`, as the guard does for any unreadable rule. `sessions_spawn` from a guest session is blocked by name as well, so no child can inherit an unlisted tool.

**`workspace/AGENTS.md`** gets a short "Voice and guests" section for `main`: guest turns never reach it; if Adam asks why Jorah didn't answer someone, the guest agent did; it never offers to "switch to Adam mode", because only Telegram does that.

## 7. What guests hear

Fixed lines, spoken by `jorah-voice` or written into the guest agent's rules. The guest agent words its own answers to public questions.

| When | Line |
|---|---|
| A guest asks about Adam: plans, memory, anything private | "That's something only Adam can ask me." |
| A guest asks Jorah to do something (save, remind, send, start, push) | "I can't do that for guests. Adam can ask me directly." |
| Asked "why?" or "who are you?" | "I'm Jorah, Adam's assistant. I don't know your voice, so I answer general questions only." |
| The day's guest cap is reached | "That's all I can do for guests today." |
| Guest mode forced from Telegram, at the start of a conversation | "Guest mode is on: general questions only." Once per conversation |
| Voice switched off from Telegram (`/voice off`) | "Voice is off right now." Then the session closes |
| Adam unsure, or the check is down | Section 3.4 |

Nothing in these lines says whether Adam is home or what the check scored.

## 8. Adam's override from Telegram

Plugin commands in `plugins/jorah-voice-provider` (`requireAuth`, refused unless `senderIsOwner`, like `/jorah-freeze`). They are commands, not tools, so the model can't call them, and voice can't reach them.

| Command | Effect | Lasts |
|---|---|---|
| `/voice` | Status: check on, shadow or off; forced guest or automatic; the open conversation's state (Adam, guest present, unsure); guest turns today; voiceprint date | |
| `/voice guest` | Every voice turn is guest, Adam's too. For visitors, parties, a babysitter | Until `/voice auto` |
| `/voice auto` | Back to the speaker check | |
| `/voice me` | The open voice conversation counts as Adam, and the sticky guest flag clears. `jorah-voice` says "Okay, treating this as Adam" aloud, so anyone in the room knows | Until that conversation ends, 15 minutes at most |
| `/voice off` | `jorah-voice` refuses new voice sessions and closes the open one (the old 9.4 "closed") | Until `/voice on` |
| `/voice enrol`, `/voice enrol done`, `/voice forget` | Section 4 | |
| `/voice enforce`, `/voice shadow` | Shadow mode logs verdicts and routes everything as today; enforce routes by verdict. Install starts in shadow (section 13) | |

**How a command reaches `jorah-voice`:** the plugin writes `/home/jorah/.jorah-voice-id/state.json` (folder 700, file 600, written atomically): `{ version, mode: "auto"|"guest"|"off", enforce: bool, me: { conversation, until } | null, enrol: { until } | null, forget: bool }`. `jorah-voice` reads it at every turn and writes `status.json` beside it for `/voice`. Both run as `jorah`. `main`'s file tools stop at its workspace and every shell is sandboxed, so the model can't reach the folder; VI-T5 tests that, as P5-N10 does for the guard's state. A file that won't parse counts as `mode: "guest"`, never as Adam.

**Telegram line when a guest talks (decision V7):** once per conversation, neutral: "Voice: someone other than you talked to Jorah at 19:05 (guest mode, 4 turns)." No words. VI-S4 checks the plugin can send it through OpenClaw's outbound path to Adam's chat; if it can't, `/voice` status shows the count instead.

## 9. Spoofing and replay

Speaker models are good at telling people apart and poor at telling a real person from a fake. Voice cloning from small samples can beat speaker verification, and detectors don't generalise across synthesis methods [`research/voice.md` 12, arXiv 2601.02914]. ASVspoof 5's overview (IEEE TASLP, April 2026) finds detectors degrade under adversarial attacks and codec compression, and overfit to the attacks they were trained on [arXiv 2601.03944]. **Qwen3-TTS `-Base`, already on this PC, clones a voice from a short sample** [measured 2026-11-08: the "Daniel clone" in the runbook], and Adam's voice may be online if videos are published (M12).

| Id | Attack | What the check does | What still holds |
|---|---|---|---|
| VI-T1 | A recording of Adam played near the mic | **Passes** [inference, tested] | Writes wait for a tap. Leaving-PC actions need the card's code, which never reaches the transcript or the room. A confirmation is single-use, bound to the action, and expires in 20 s (`p5-plan.md` 4.3) |
| VI-T2 | A TTS clone of Adam | **Passes often** [inference, tested in VI-S1 with a local clone made with Adam's consent and deleted after] | Same |
| VI-T3 | A visitor, child or TV asks for Adam's things | Fails the check: guest | Routing |
| VI-T4 | Jorah's own voice through the speakers (echo, barge-in) | Fails the check [tested] | Same |
| VI-T5 | The model, a job or a worker edits the voiceprint or the override file | | File modes, the workspace limit on `main`'s file tools, sandboxes. Tested |
| VI-T6 | Someone silent in the room overhears Adam's answers | Nothing: the check hears speakers, not listeners | `/voice guest` while people are over. Private answers go to Telegram once M4 has `private_show` |
| VI-T7 | A guest uses the guest agent as a free web proxy | | Turn caps, query length cap, API key's $80 limit |
| VI-T8 | Adversarial audio crafted against the embedding | Possible in research; needs the model and effort | Same as VI-T1. The voiceprint file never leaves the PC |

**Why voice alone never unlocks money, sends, pushes or secrets:** each can't be undone or reaches other people, and VI-T1 and VI-T2 mean a passed voice check proves only that something sounding like Adam spoke. So:

| Action | Voice can do it with | Rule from |
|---|---|---|
| Read Adam's things aloud | Adam's verdict | This plan |
| Stays on the PC and can be undone (a job, a memory line, a one-off reminder) | Adam's verdict on a full-phrase "yes" within 20 s, once P5 turns voice confirmation on | `p5-plan.md` 4.3 |
| Leaves the PC (push, pull request, recurring or web-fetching schedule) | Adam's verdict **plus** the 4-digit code from the Telegram card | Same, Adam 2026-11-11 |
| Money, purchases, messages to other people, anything RISK-T3 | **Never by voice.** None exists today; when one does, it is a tap on an unlocked device | `03` 4.1, roadmap 2a |
| Secrets (tokens, keys, codes) | Never spoken, never read aloud, never typed by Jorah | `CLAUDE.md`, `03` 6 |

**Anti-spoofing models are not used as a gate.** AASIST-style detectors could be a later extra signal (a spike, its own yes), never something that unlocks.

## 10. Privacy

- **Adam's voiceprint** stays on the PC in `~/.config/jorah-voice/voiceprint/`, mode 600 in a 700 folder. Never committed: `.gitignore` gains `voiceprint/`, `*.voiceprint.json` and `enrol-*.wav`, and a unit test fails if `git ls-files` shows any of them. Never in Telegram, never sent to the Gateway or Anthropic; it isn't text, and nothing reads it but `jorah-voice`.
- **Backups (decision V6):** the voiceprint is left out of the daily backup. Re-enrolment takes a few minutes, and the PC's disk encryption was waived in writing (roadmap P1.1), so fewer copies is better.
- **Guests' audio:** never stored, as for Adam today. A guest's embedding exists in memory for one turn, is compared, and is dropped. Never logged.
- **Guests' words:** dropped on the PC unless they address Jorah (5.2). Addressed turns go to Anthropic's API as text, are answered, and the guest session is deleted when the conversation ends. Never in `main`'s chat, memory or Dreaming (VI-S3).
- **Logs:** per turn, the verdict, a score bucket and the timing. Never words, embeddings or exact scores. `/voice` status shows counts only.
- **Law, not legal advice.** A voiceprint used to identify someone is special-category data under GDPR Art. 9; Adam's own use at home falls under the household exemption, and only Adam is enrolled. Comparing a guest's voice for one turn without storing it is my reading of a household use [inference, ask the lawyer with `03` 14's questions]. Slovak Civil Code §§ 11 to 13: the guest's words go to a provider only when they spoke to Jorah by name. **Notice for people at home**, for Adam to adapt: "Jorah listens when its light is on. It doesn't know your voice, keeps nothing you say, and only answers general questions if you say its name."

## 11. Latency and resources

| | Today [measured] | With the check |
|---|---|---|
| Recognition | Parakeet int8 on the CPU, 123 ms median a sentence | Unchanged |
| Speaker embedding | | 20 to 60 ms on the CPU for 2 to 5 s of speech [inference], **in parallel** with recognition |
| End of speech to first audio, Adam | About 3 to 3.5 s on a simple turn | Target: at most 50 ms more at P90. Measured in VI-S1 and the shadow week |
| Guest turn | | No 67K-token prefix, so probably no slower than Adam's [inference]; measured |
| Memory | 9,494 MB available | About 300 to 500 MB more resident [inference] |
| GPU | 5,876 of 12,227 MiB used | No change: the check runs on the CPU |

If the embedding turns out slower than recognition on long turns, it runs on the first 6 s of speech only.

## 12. Tests

### 12.1 Unit, in the repo (`just unit`, no model or network)

- **Routing,** with a stand-in verifier: Adam → `openclaw/main` and `agent:main:main`; someone else, unsure, short with no history, error, model missing → `openclaw/guest` and `agent:guest:voice-*`, **never** `agent:main:main`; unaddressed guest turns → nothing sent; sticky flag set by an addressed someone-else, not by unsure; `/voice me` clears it; exact commands work for guests; caps.
- **State file:** missing, malformed, expired `me`, unknown version → guest, never Adam.
- **Logs** hold no words, embeddings or exact scores.
- **Guard:** the `guest` section blocks every matrix tool but its list, from `agentId: guest` and from an `agent:guest:` key; unreadable section blocks all; `main`'s voice rules unchanged (the existing guard tests still pass).
- **Plugin commands:** refused unless owner; write the state file atomically with the right modes.
- **Guest workspace:** only `AGENTS.md`, `SOUL.md`, `IDENTITY.md`; none mention Adam's private facts (a list of canary words from a fixture).
- **No voiceprint in git** (section 10).

### 12.2 On the PC, outside the live service

| Id | Test | Pass means |
|---|---|---|
| VI-S1 | **Calibration, this plan's G-S8.** Adam's enrolment, then: 20 of Adam's answers per device; 300 clips played through a speaker near the mics (public-domain or CC speech, the TV, Jorah's Qwen and Kokoro voices); about 3,000 clips scored offline (LibriSpeech test sets, CC-BY-4.0, and a Slovak set if one can be fetched under an open licence); a local Qwen3-TTS clone of Adam, made only on Adam's yes and deleted after; a replay of Adam's own recording through a phone speaker; mixed two-voice turns; the embedding's time per turn | Thresholds written; **0 false accepts** in the 300 and the 3,000; Adam turned away at most 1 in 20 per device; P90 time under recognition's. Clone and replay results recorded as they are, since section 9 already assumes they pass |
| VI-S2 | Can `jorah-voice` open an incognito guest session through Chat Completions? If not, does deleting the session through the Gateway remove its transcript from disk? | One of the two works, or guest sessions rely on the daily reset, written down |
| VI-S3 | On `jorah-dev`: `guest`'s sessions are invisible to `main`'s `sessions_search` and `sessions_history`, Dreaming and `memory_search`; `guest`'s effective tool list is exactly the allowlist | As stated |
| VI-S4 | Can the plugin send the neutral Telegram line to Adam's chat? | It arrives, or `/voice` status carries the count instead |
| VI-S5 | iPhone Talk's 24 kHz audio and AirPods' Bluetooth mic score as well as the Mac mic | Inside the bar per device, or that device stays guest-only |

### 12.3 Shadow week, then live with Adam

**Shadow week:** enforcement off, verdicts logged. Adam notes the times they talked alone. Pass: at most 1 in 20 of Adam's turns unsure or rejected, no someone-else verdict while Adam was alone, and no measurable delay added.

**Live acceptance, Adam:**

| Id | Test | Expected |
|---|---|---|
| VI-L1 | Adam: "Jorah, what's on my list for today?" on each device | Answered as today |
| VI-L2 | A consenting visitor, or a recording of a stranger: the same question | "That's something only Adam can ask me." `/voice` shows a guest turn |
| VI-L3 | Visitor: "Jorah, what's the weather in Bratislava?" | Answered (if V1 allows web) |
| VI-L4 | Visitor: "Jorah, remember that Adam owes me twenty euros", "start Claude Code on mizyun", "push my branch" | Refusal line; no card, no write, nothing in the guard log beyond blocks |
| VI-L5 | Visitor speaks, then Adam asks a private question in the same conversation | Guest answer (sticky). After `/voice me`: Adam's answer, with the spoken notice |
| VI-L6 | Visitor says "stop" while Jorah speaks | Stops |
| VI-L7 | `/voice guest`, then Adam asks a private question; `/voice auto`, again | Guest line; then answered |
| VI-L8 | P5-N5 re-run: a phone plays a stranger's "Jorah, start Claude Code ... yes" | Guest, nothing starts, no card |
| VI-L9 | Jorah's own reply leaks into the mic during barge-in | Never scored as Adam |
| VI-L10 | `/voice forget` | Every turn guest, with the line; folder gone |

**If a test fails, the feature behind it stops** until it passes or Adam waives it in writing:

| Fails | Turns off |
|---|---|
| VI-S1 bar missed | Enforcement stays in shadow: every voice turn is treated as today, and voice confirmation stays off |
| VI-S3 (guest sessions reach `main`'s memory or search, or extra tools) | The `guest` agent: guest turns get only the fixed line, nothing goes to the cloud |
| VI-L2, L4, L8 | Voice to `main` for everyone: `/voice guest` is set until fixed |
| VI-T5 test (the model reaches the voiceprint or state) | Everything voice: `/voice off` |

## 13. Build and install

**Two build sessions in parallel,** each in its own worktree, source and unit tests only, never the live Gateway, `just check`, then fast-forward `main` per `CLAUDE.md`. Each owns its files.

| Session | Owns | Does |
|---|---|---|
| **VI-A `voice-id`** | `services/jorah-voice/jorah_voice/identity.py` (new), `session.py`, `brain.py`, `server.py`, `models.py`, `tools/enrol.py`, `tools/calibrate.py`, their tests, `services/jorah-voice/README.md`, `.gitignore` lines | Sections 3, 4, 5.1, 5.2, the state-file reader, logs, fixed lines in 3.4 and 7 |
| **VI-B `guest-and-commands`** | `workspace-guest/`, `config/pc/guest.patch.json5`, `scripts/pc/apply-guest.sh` (`--dry-run`, `--undo`), the `guest` section in `config/permission-matrix.json`, `plugins/jorah-guard/lib/policy.js` and `test/guest.test.js`, `/voice` commands in `plugins/jorah-voice-provider`, the "Voice and guests" section of `workspace/AGENTS.md`, `docs/runbooks/voice-identity.md` | Sections 5.3, 6, 7 (agent side), 8 |

The state file in section 8 is the contract between them.

**Install, one session, Adam's yes at each marked step:**

| Step | What | Adam's yes |
|---|---|---|
| 1 | Copy the reviewed commit to `/opt/jorah`, SHA-256 against `main` | No |
| 2 | Download `nemo_en_titanet_large.onnx`: source, size, licence, upload date and SHA-256 shown first | **Yes** |
| 3 | Deploy the new `jorah-voice` in **shadow** mode, restart it | **Yes** |
| 4 | Plugin update with `/voice` commands, plugin consent again | **Yes** |
| 5 | Enrolment: Adam speaks on each device (section 4) | **Adam does it** |
| 6 | VI-S1 calibration. The impostor download (LibriSpeech test sets, about 700 MB, CC-BY-4.0) and the local clone of Adam's voice each need their own yes | **Yes,** twice |
| 7 | `guest` agent: `openclaw agents add guest`, `guest.patch.json5` and the guard matrix, dry run first; on `jorah-dev`, then VI-S2 to S4 | **Yes** |
| 8 | Same on live, Gateway restarted with no voice call open | **Yes** |
| 9 | Shadow week | Adam talks as usual |
| 10 | `/voice enforce` | **Adam sends it** |
| 11 | Live tests VI-L1 to L10 | Adam, with a consenting visitor or recordings |
| 12 | Delete the enrolment audio (section 4) | **Yes** |

**Undo:** `/voice shadow` puts routing back to today's at once. Full undo: the previous `jorah_voice/` files back in `/opt/jorah` and a restart, `apply-guest.sh --undo`, the plugin's previous version.

## 14. Decisions only Adam can make

My pick comes first. **V1 to V5 block the build.**

| # | Question | Pick | Why |
|---|---|---|---|
| V1 | **What may guests do?** (a) Only stop and a fixed line, nothing to the cloud. (b) A `guest` agent on Haiku with the API key: general questions, plus web search, nothing about Adam, 20 turns a conversation and 60 a day. (c) As (b) without web search | **(b)** | Your "can only do some limited things". It is a second agent with no memory, an exception to "one agent" (2026-11-05). On the API key, because guests are third parties |
| V2 | What does "unsure" do? Guest for that turn, with "say it again" (pick), or ask by Telegram each time | Guest for that turn | A Telegram card per unsure turn would be many cards |
| V3 | Unknown voices that don't say "Jorah": dropped on the PC unheard (pick), or answered | Dropped | Keeps a visitor's conversation and the TV out of the cloud |
| V4 | Once someone else has spoken to Jorah, does the rest of the conversation stay guest, Adam's turns too, until `/voice me` or a new conversation? | Yes | Otherwise the visitor hears your next private answer. The cost: saying "goodbye" and starting again when they leave |
| V5 | When the speaker check is down: everyone is a guest (pick), or voice works as today | Everyone a guest | A failed gate stops what is behind it. Telegram keeps working |
| V6 | The bar (0 false accepts in 300 and in 3,000, you turned away at most 1 in 20); keep the enrolment audio only until the shadow week ends; leave the voiceprint out of backups | Yes to all three | Leans toward privacy; re-enrolment is a few minutes |
| V7 | A neutral Telegram line when someone else talks to Jorah, once per conversation | Yes | A security signal when you're away, with no words in it |
| V8 | A spoken challenge word for voice-alone confirmations ("say: yes, copper"), against replays | No, for now | Those actions stay on the PC and can be undone; revisit if VI-L8 or P5-N5 shows a replay working |
| V9 | Siri "Ask Jorah" has no audio to check. Should it require the phone unlocked? | Yes: check the shortcut doesn't run from the lock screen | Otherwise whoever holds the locked phone is Adam to Jorah |

## 15. Not verified yet

- Every behaviour above is planned. The embedding's speed, its accuracy on Adam's devices, and how short a phrase still verifies are unmeasured (VI-S1, VI-S5).
- Whether Chat Completions can open incognito sessions, and whether deleting a session removes its transcript (VI-S2).
- Whether `guest`'s sessions stay invisible to `main`'s search, history, memory and Dreaming (VI-S3).
- Whether the plugin can send a Telegram line itself (VI-S4).
- The voice-session counts on the PC (the journal wasn't readable as `jorah`).
- The legal reading in section 10, for the lawyer questions in `03` 14.

## 16. Sources

- sherpa-onnx speaker models: release `speaker-recongition-models` on `k2-fsa/sherpa-onnx` (asset dates read with `gh api`, 2026-11-19); commits #4237, #4239, #4241 (CAM++ export fixes, 2026-11-19); licence Apache-2.0.
- NVIDIA TitaNet-Large card: https://huggingface.co/nvidia/speakerverification_en_titanet_large (CC-BY-4.0, 0.66% EER).
- WeSpeaker pretrained models and VoxCeleb results: https://github.com/wenet-e2e/wespeaker/blob/master/docs/pretrained.md, `examples/voxceleb/v2/README.md`.
- 3D-Speaker: https://github.com/modelscope/3D-Speaker (Apache-2.0). SpeechBrain ECAPA: https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb (Apache-2.0). AASIST: https://github.com/clovaai/aasist (MIT).
- ASVspoof 5 overview: https://arxiv.org/abs/2601.03944. Cloning against speaker verification: https://arxiv.org/abs/2601.02914 (via `research/voice.md` 12).
- OpenClaw 2026.10.9 docs: `gateway/openai-http-api.md` (agent targets, session headers), `concepts/session.md` (incognito), `tools/multi-agent-sandbox-tools.md` (per-agent tool policy, empty allowlists).
- This repo: `p5-plan.md` 4.3 and section 5, `03` sections 4.1, 8, 9, 14, `docs/runbooks/jorah-on-pc.md`, `docs/runbooks/voiceprint-recording.md`, `docs/runbooks/phone.md`, `services/jorah-voice/`, `plugins/jorah-guard/`, `plugins/jorah-voice-provider/`.
