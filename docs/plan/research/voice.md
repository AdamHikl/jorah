# Jorah research track: real-time voice

Date: 2026-11-02. Research only: nothing was installed, configured or restarted. An independent verification pass on the same date corrected this file and changed the V1 provider pick; section 20 lists what changed.

Evidence labels:

- `[verified: URL or path]`: read directly this session, from a primary source, a vendor page or a local doc.
- `[measured: this Mac]`: a read-only command run on Adam's M1 Max today.
- `[vendor]` added to a verified label: the number comes from a party selling that product. Treat it as a claim.
- `[secondary]`: third-party page or search snippet. Check before relying on it.
- `[docs-only]`: documented behavior, not tried on any device.
- `[inference]`: my reasoning or arithmetic.
- `[unverified]`: I could not confirm it. See sections 17 and 20.
- `[source]`: read in OpenClaw's shipped code or its tagged GitHub source. Stronger than docs, weaker than a device run.

Limit of this research: the shared web search budget ran out late in the session. Direct page fetches still worked, but speakerphone prices, Parakeet on Windows, Pipecat's echo cancellation and Nemotron's language list could not be searched in the first draft. The verification pass closed some of these. Section 17 lists every remaining gap.

---

## 1. Bottom line

**Recommendation: build voice in three bounded steps, and do not start by writing a custom pipeline.**

1. **V0, day one, no new API keys.** Use OpenClaw's own macOS Talk and Voice Wake with Apple Speech in `en-US`, the existing Claude brain and local MLX speech. This proves "say Jorah, get an answer", but is slow, with several seconds to first audio. The aim is to test the wake phrase and the loop, not to feel like Jarvis. With "wake starts Talk Mode" on, the words after the wake phrase are dropped, so Adam says "Jorah", waits for the chime, then speaks [source: https://raw.githubusercontent.com/openclaw/openclaw/v2026.10.9/apps/macos/Sources/OpenClaw/VoiceWakeRuntime.swift].
2. **V1, the real-time feel, about $30 to $40 per month at 1 hour per day of short sessions, and up to about $93 if sessions are left open [inference, section 8].** Use OpenClaw realtime Talk over `gateway-relay` with `brain: agent-consult` and **`gpt-realtime-2.1-mini`** as the fast voice, with **Gemini 3.8 Live** as the runner-up in the same bake-off. Claude stays the deep brain behind `openclaw_agent_consult`. OpenClaw already has most of the hard parts here: delegation, steering, cancel, shared history, spoken confirmation and fallback to native speech. It does not have an idle close, which V1 must solve before daily use.
3. **V2, own the pipeline, about $1 to $30 per month.** Add a Pipecat service (`jorah-voice`) with a trained `jorah` wake word, Parakeet v3, Silero plus Smart Turn, a fast text model and local or hosted TTS, and plug it into OpenClaw as a realtime voice provider. This is also the **fully local fallback** and the **PC stack**, because OpenClaw on Windows only documents push-to-talk, not wake.

Nine findings change the plan (7 to 9 came from the verification pass):

1. **Anthropic has no real-time voice API that I could find.** The OpenAI compatibility layer returns a 400 error for `input_audio`, ignores the `audio` and `modalities` request fields, and always returns empty audio output [verified: https://platform.claude.com/docs/en/api/openai-sdk]. Anthropic's own cookbook pairs third-party STT and TTS with text calls [verified: https://platform.claude.com/cookbook/third-party-elevenlabs-low-latency-stt-claude-tts]. Claude can therefore only be the brain, never the voice layer. A separate fast voice model is required.
2. **Porcupine is out.** Picovoice's free tier ended on 2026-06-30, keys stop working at engine start, and there is "no non-commercial tier planned" [secondary, Picovoice reply quoted at: https://community.home-assistant.io/t/fyi-picovoice-confirmed-free-tier-accesskeys-will-stop-working-after-june-30-2026/1012744].
3. **openWakeWord has gone stale.** The last release is v0.6.0 from February 2024 [measured: PyPI JSON], and its training notebook needs community patches [secondary: https://github.com/alfiedennen/openwakeword-colab-2026]. **`livekit-wakeword`** (Apache-2.0, v0.3.0, 2026-09-30) is the better pick. It claims 0.08 false positives per hour against openWakeWord's 8.50 on the same evaluation [verified, vendor: https://github.com/livekit/livekit-wakeword]. That evaluation is LiveKit's own, on "hey livekit" only, with 25 hours of audio, so 0.08 per hour is about 2 events [inference]. Its install notes cover macOS and Ubuntu/Debian only, so Windows is [unverified].
4. **Apple on-device speech cannot do Slovak on this Mac.** `SFSpeechRecognizer` reports `sk-SK` as not on-device, and `SpeechTranscriber` does not list Slovak at all [measured: this Mac]. OpenClaw's Voice Wake refuses to run without on-device recognition [verified: `docs/platforms/mac/voicewake.md`], so wake must run in `en-US`.
5. **OpenClaw native Talk cannot meet an 800 ms target by design.** It waits for the whole agent run and then speaks the complete reply [verified: `docs/nodes/talk/macos-relay.md`].
6. **The OpenClaw Mac app is not installed** (nothing in `/Applications`), and macOS needs it for Voice Wake and Talk [measured: this Mac; verified: `docs/platforms/mac/voicewake.md`]. Windows documents only `talk.ptt.*` and `talk.speak` [verified: `docs/platforms/windows.md`], so wake on the PC is our own work.
7. **Gemini Live re-bills its whole context on every turn, with no caching.** Google's own page says each turn bills all context tokens, including history and system instruction [verified: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices]. A forum reply says caching is unavailable for `gemini-3.8-live` [secondary: https://discuss.ai.google.dev/t/title-context-caching-or-cached-input-pricing-for-the-gemini-live-api-native-audio/186850], and the model page agrees [verified: https://aistudio.google.com/docs/models/gemini-3.8-live]. The first draft's $22 to $45 is not defensible, and Gemini is no longer the cheapest pick. See section 8.
8. **Realtime Talk on the Mac has no idle close that I could find.** The Mac Talk sources I read contain no idle timeout, and the Gateway closes a relay session only at 30 minutes [source: `RELAY_SESSION_TTL_MS` in `dist/handlers-*.mjs`; `TalkModeRuntime+Realtime.swift` at tag v2026.10.9]. So one "Jorah" can leave a cloud microphone open and billing until Adam stops it. This is a privacy and cost gate for V1, not a detail.
9. **Parakeet v3 has a published Slovak figure and is the first local Slovak candidate:** 8.82% WER on FLEURS, CC-BY-4.0 [verified: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3]. Nemotron's multilingual model reports about 21% to 25% [verified: https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b], so it is for English only.

---

## 2. Decision table

| Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|
| Wake engine, Mac now | OpenClaw Voice Wake (Apple Speech, `en-US`) | Already built, runs locally | Trained `livekit-wakeword` | Apple Speech mishears "Jorah" (likely, it is a rare name), or misses the gates in section 3 | $0 |
| Wake engine, Mac later and PC | `livekit-wakeword` | Apache-2.0, Python, Rust and Swift runtimes, ONNX compatible with openWakeWord | openWakeWord with patched notebook | Fails the section 3 gates on Adam's real audio, or does not run on Windows [unverified] | $0 to a few $ of GPU time |
| Wake engine, ESP32-S3 | microWakeWord (ESPHome) | Built for ESP32-S3, self-trainable | ESP-SR WakeNet | Quote from Espressif turns out cheap | $0; WakeNet needs a paid quote |
| VAD | Silero VAD 6.2.3 | Under 1 ms per chunk, MIT, in Pipecat | TEN VAD | TEN's claimed faster end-of-speech holds up in our tests | $0 |
| End of turn | Smart Turn v3.2 (English) plus 200 ms VAD stop | BSD, about 8 MB, local, 12 to 65 ms | Fixed silence window | Slovak: Smart Turn has no Slovak, so Slovak uses a fixed window | $0 |
| Echo and barge-in, desk | USB speakerphone, or a headset for V0 | Hardware owns both mic and speaker, so no software integration | Apple voice processing in our own native client | Apple voice processing proves good enough on the built-in speakers | About €140 for a Jabra Speak2 55 at Alza's Austrian shop [secondary: search result]; Slovak price [unverified] |
| Echo and barge-in, robot or far field | ReSpeaker XVF3800 | $54.90, AEC, beamforming, direction of arrival, up to 5 m | Home Assistant Voice PE (€59) | Playback reference path proves awkward | $54.90 |
| STT, local | Parakeet TDT 0.6 v3 | 52.7x real time on M1 Max, Slovak 8.82% WER on FLEURS, CC-BY-4.0 | Whisper large-v3-turbo (14.3x) | Parakeet is poor on Adam's Slovak | $0 |
| STT, hosted | Soniox `stt-rt-v5` | $0.12/h, Slovak page, claimed sub-200 ms | ElevenLabs Scribe v2 Realtime ($0.39/h, ~150 ms) | Scribe wins clearly on Adam's speech | ~$4 per month |
| TTS, local English | Kokoro-82M | Apache-2.0, 11.9x to 15.5x real time on M1 Max | Soprano (OpenClaw default) | Quality bake-off | $0 |
| TTS, local Slovak | Piper `sk_SK-lili` | Only open Slovak voice found. The runtime is GPL-3.0, relevant for a business | macOS `Laura` | A better Slovak local voice appears | $0 |
| TTS, hosted | ElevenLabs Flash v2.5 | ~75 to 100 ms, Slovak confirmed, $0.04/1K chars | Cartesia `sonic-3.6` (Slovak confirmed) | Soniox TTS ($0.70/h) sounds good enough | ~$26 per month |
| Speech-to-speech (V1) | `gpt-realtime-2.1-mini` | Lowest modelled cost once replay is counted, because replayed audio is $0.30 per 1M when cached. Mac relay path is documented | Gemini 3.8 Live (Slovak confirmed, continuous camera in browser Talk, async tools) | Slovak or continuous vision needed in V1; bake-off shows bad barge-in or handoff; first bills show replay cache misses | $29 to $39 per month in short sessions; $37 to $93 if left open [inference] |
| Orchestration (V1) | OpenClaw realtime Talk | Delegation, gating, history and clients exist | Pipecat from day one | Google or OpenAI paths fail device acceptance | $0 |
| Orchestration (V2) | Pipecat 1.15 | BSD-2, local transport, local Smart Turn, no paid cloud for interruption | LiveKit Agents 1.8 | Multi-party rooms or robot fleets become important | $0 |
| Speaker ID | ECAPA or WeSpeaker embeddings, local, used only for personalization | Filters TV, routes people | None | Never use as authentication | $0 |
| Fast text model (V2) | Claude Haiku 5.5, thinking disabled, effort low | Very cheap, may be covered by Max's API credits, one vendor | Gemini Flash-Lite | P90 first token above 500 ms in the spike, or reasoning-like text in the reply, which Anthropic says is more common with thinking off or at low effort [verified: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5]. On a voice path that text would be spoken | ~$1 per month |

---

## 3. Wake word

### 3.1 Options

| Option | Status on 2026-11-02 | Verdict |
|---|---|---|
| **OpenClaw Voice Wake (Apple Speech)** | Always-on on-device recognizer matching trigger strings. Global list of up to 32 triggers of up to 64 UTF-16 units. Fires only after a 0.55 s pause following the trigger. 2.0 s silence window while speech flows, 5.0 s if only the trigger was heard, 120 s hard stop, 350 ms debounce. It can also start Talk Mode [verified: `docs/nodes/voicewake.md`, `docs/platforms/mac/voicewake.md`]. When it does, capture is skipped and any words after the phrase are not forwarded [source: `VoiceWakeRuntime.swift` at tag v2026.10.9]. | Use for V0 |
| **livekit-wakeword** | v0.3.0 from 2026-09-30, Apache-2.0, 304 stars, pushed 2026-10-23 [measured: PyPI and GitHub APIs]. Trains from synthetic TTS with noise and reverb augmentation. Python, Rust and Swift (iOS 16+ and macOS 14+ using ONNX Runtime with CoreML). Reports 0.08 false positives per hour and 86.1% recall against openWakeWord's 8.50 and 68.6%, on LiveKit's own "hey livekit" set (15,000 positive clips, 45,084 negatives, 25 hours), with an `eval` command for DET curves [verified, vendor: https://github.com/livekit/livekit-wakeword, https://livekit.com/blog/livekit-wakeword]. Install notes cover macOS and Ubuntu/Debian. The wheel is pure Python for 3.11+ [measured: PyPI], which makes Windows plausible but [unverified]. | **Pick for V2 and PC** |
| **openWakeWord** | v0.6.0 from 2024-02-11 [measured: PyPI]. Code Apache-2.0, pretrained models CC BY-NC-SA 4.0. Target under 5% false rejects and under 0.5 false accepts per hour. A Raspberry Pi 3 core runs 15 to 20 models. Not suitable for ESP32-S3 (several seconds per 80 ms frame). Custom verifier models exist [verified: https://github.com/dscripka/openWakeWord]. Official notebook is broken on current Colab; a community fix takes 75 to 90 minutes on Colab Pro and about 2.5 hours on a free T4 [secondary: https://github.com/alfiedennen/openwakeword-colab-2026; thread with a failure and fix at https://community.home-assistant.io/t/colab-notebooks-to-train-your-custom-openwakeword-or-microwakeword/1026635]. | Runner-up |
| **Porcupine** | Free tier ended 2026-06-30 [secondary, see section 1]. The pricing page returned no content to my fetch, so a paid price is [unverified]; the company says it is focusing on enterprise deployments. | Reject |
| **sherpa-onnx KWS** | v2.0.1 from 2026-10-27 [measured: PyPI]. Open vocabulary, custom keywords without retraining, per-keyword threshold. The docs call it essentially a tiny ASR limited to the keyword list [verified: https://k2-fsa.github.io/sherpa/onnx/kws]. | Good quick trial; second-stage candidate |
| **speech-swift KWS Zipformer** | 3M parameters, CoreML, 26x real time, configurable keyword list; Apache-2.0, 1,260 stars [verified, vendor: https://github.com/soniqo/speech-swift; measured: GitHub API]. | Good for a native Swift client |
| **Apple Speech as a wake word on iOS** | "iOS may suspend background audio; treat voice features as best-effort" [verified: `docs/platforms/ios.md`]. | Do not rely on it |

### 3.2 Why "Jorah" is a hard wake word [inference]

- Two syllables, a soft onset and an open vowel ending. Short wake words produce more false accepts than three or four syllable phrases, so "Hey Jorah" will be more reliable than bare "Jorah".
- Close English neighbours: Laura, Nora, Cora, Dora, Zora, Torah, Sora.
- **Slovak trap: "Jura" is a common nickname for Juraj.** If Slovak is spoken in the home, this needs specific negative samples.
- **TV trap:** "Jorah" is a Game of Thrones character. Add those clips to the negative set.
- Apple Speech will likely transcribe a rare name as something else. Mitigate in V0 by adding spelling variants to the triggers (`jorah`, `hey jorah`, `jora`, `hey jora`). Test each. Avoid `laura` or `nora`, which would raise false accepts.
- Adam needs to confirm the pronunciation before training. `/ˈdʒɔːrə/` (as in English) and a Slovak-style `Džora` are different audio.

### 3.3 Two-stage design for V2

```
mic -> AEC -> ring buffer (RAM only, max 2 s)
   -> Stage 1: livekit-wakeword ("jorah", "hey jorah"), low threshold
   -> Stage 2: speaker embedding similarity OR local Parakeet check on the buffered audio
   -> earcon and visible "listening" state, open a session
```

- Train a `jorah` positive set, then test whether it also fires on "hey jorah", since that phrase ends in the same word. If so, one head is enough. If bare "jorah" needs a stricter threshold than "hey jorah", use two heads [inference].
- The README lists Piper for English synthetic samples and VoxCPM for multilingual, and warns that multilingual models score lower [verified: https://github.com/livekit/livekit-wakeword]. Check that the TTS actually says "Jorah" correctly by listening, and use a phonetic spelling if not.
- Record 50 to 200 real samples of Adam at several distances for threshold calibration. Do not train only on synthetic voices.
- Stored samples and household audio stay local and are deleted after calibration. Get consent from anyone recorded.

### 3.4 Targets

openWakeWord's stated target of under 0.5 false accepts per hour [verified] means up to 12 per day during continuous household audio. That is too many when a false accept can open a cloud microphone. Targets for Jorah [inference]:

| Metric | Gate | Stretch | Test |
|---|---|---|---|
| False accepts, full two-stage chain | At most 1 per 24 h of real household audio including TV | At most 1 per week | 24 h continuous replay, then 7 days live |
| False accepts, stage 1 only | At most 0.25 per hour | 0.08 per hour (LiveKit's claim) | Same audio, logging only |
| False rejects, near field in quiet | At most 5% | 2% | 100 utterances at 1 m |
| False rejects, 3 m with music | At most 15% | 8% | 100 utterances at 3 m |
| False rejects while Jorah speaks | At most 20% | 10% | 100 "Jorah, stop" during playback |
| Wake to earcon | At most 300 ms | 150 ms | Waveform measurement |

Note that LiveKit's claimed 0.08 per hour comes with 86.1% recall [verified, vendor], which is a 14% false-reject rate. That misses the near-field gate at that threshold, so thresholds must be tuned on real audio.

### 3.5 Power on the Mac

No published figure was found for always-listening power on Apple Silicon [unverified]. A tiny model should be a small fraction of one efficiency core; openWakeWord's Pi 3 claim supports that [inference]. A continuous Apple Speech recognizer should cost more than a tiny keyword model [inference]. Measure rather than guess:

```bash
sudo powermetrics --samplers cpu_power,ane_power -i 5000 -n 12   # needs Adam's password, read-only
```

Run it for no voice, Voice Wake on, and a keyword model. Gate: under 1 W added on battery.

**Sleep is the real limit.** A sleeping Mac does not listen. A MacBook with the lid closed and no external display sleeps. So the Mac listens only while awake, in practice plugged in and open. Only the always-on PC makes "any time I say Jorah" true [inference].

### 3.6 iPhone

- OpenClaw: background audio is best-effort; a "Start Live Voice" App Shortcut can go on the **Action Button**, or a Home Screen shortcut or Siri; it needs unlock and foreground [verified: `docs/platforms/ios.md`].
- Keyword listening while locked: a developer's direct question on Apple's forum has no answer [verified: https://developer.apple.com/forums/thread/826681]. Developers report App Review rejecting background recording under the audio mode [secondary: https://developer.apple.com/forums/thread/91872].
- Apple's side-button route for voice apps appears to be Japan-only, with the EU still disputed over the DMA [secondary: https://gori.me/en/apple/apple-news/167082/, https://9to5mac.com/2025/11/17/ios-26-2-leak-shows-iphone-might-let-you-replace-siri-as-default-assistant/]. I could not find a confirmed EU rollout [unverified].
- **Recommendation: no always-on wake on iPhone.** Use Action Button, Watch and AirPods-style "tap to talk". A personally signed build skips App Review, so a background mic experiment is possible later, but iOS can still suspend it and it will drain the battery [inference].

### 3.7 ESP32-S3

- microWakeWord: TFLite model through ESPHome; per-model probability cutoff and sliding window. ESPHome's page lists no chip variants and treats PSRAM only as an optional stack setting, so the ESP32-S3 and PSRAM need rests on the community repo below. Apache-2.0, last push 2026-07-09 [verified: https://esphome.io/components/micro_wake_word/; measured: GitHub API; secondary on the PSRAM need: https://github.com/MorningstarOwl/wake-word-models].
- A notebook trains from Piper audio to a ready `.tflite`, for any Piper language [secondary: Home Assistant thread above].
- A community user reported a self-trained model crashing a Voice PE [secondary: https://community.simon42.com/t/eigenes-micro-wake-word-auf-den-esp32-assist-aber-wie/54847]. Expect iteration.
- ESP-SR WakeNet custom words require Espressif's sales process, at least 20,000 corpus entries if you bring your own, and 2 to 3 weeks; a one-time fee with no public price, and wake words typically of 3 to 6 syllables, longer than "Jorah" [verified: https://docs.espressif.com/projects/esp-sr/en/latest/esp32/wake_word_engine/ESP_Wake_Words_Customization.html]. Not for a personal project.
- **Pattern:** the ESP32 detects the wake word only, then streams audio over Wi-Fi to the PC. The PC does everything else. Motor noise from the arm means placing the mic away from the servos, and possibly suppressing listening while motors run [inference].

---

## 4. VAD and turn detection

- **Silero VAD:** v6.2.3 from 2026-09-23 [measured: PyPI]. 30+ ms chunks, under 1 ms per chunk on one CPU thread, MIT, ONNX supported [verified: https://github.com/snakers4/silero-vad].
- **TEN VAD:** v1.0.6.9 from 2026-10-09 [measured: PyPI]. Its README claims Silero lags several hundred ms at speech-to-silence transitions [verified, vendor: https://github.com/TEN-framework/ten-vad]. Worth a head-to-head test in V2, not on faith.
- **Smart Turn v3.2:** about 8 MB CPU model, BSD-2, 23 languages, **no Slovak** [verified: https://github.com/pipecat-ai/smart-turn]. 12 ms on modern CPUs, about 60 to 65 ms on small cloud instances [verified, vendor: https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/]. Pipecat recommends VAD `stop_secs` of 0.2 with it, and it is the default stop strategy from v0.0.102 [secondary: https://docs.pipecat.ai/server/utilities/turn-detection/smart-turn-overview]. One evaluation of v3 gave 58.9% recall and 68.4% precision on a specific dataset, so do not assume it is flawless [secondary: https://www.ai.engineer/talks/hMlLw1LeIK8-designing-voice-agents-real-conversations].
- **Gemini Live built-in VAD:** tunable; Google recommends 500 to 800 ms of silence [verified: https://aistudio.google.com/docs/live-api/capabilities]. The server default is about 800 ms, and 100 to 200 ms fragments utterances [verified: same page]. That window alone uses up most of an 800 ms budget, so Gemini may miss the target [inference]. Start at 500 ms and go lower only while the cut-off rate stays acceptable.
- **OpenClaw native:** `silenceTimeoutMs` defaults to 700 ms on macOS, 900 ms on iOS [verified: `docs/nodes/talk.md`].

**Choice:** V1 uses the provider's VAD. V2 uses Silero plus Smart Turn in English, and Silero with a 500 to 600 ms silence window in Slovak.

---

## 5. Echo cancellation, barge-in, microphones

Without good echo cancellation, an open mic hears Jorah and Jorah interrupts itself. Barge-in is a hardware and signal problem before it is a software one.

### Mac

- **Apple voice processing (`VoiceProcessingIO`)** gives AEC, noise suppression and gain control; it monitors system output as the echo reference, but it **ducks other audio and that cannot be turned off** [secondary: https://docs.rs/crate/sys-voice/latest]. Spatial Audio on MacBook speakers can interfere [secondary: https://www.forasoft.com/ship-log/spatial-audio-vpio].
- **OpenClaw:** turn-based providers keep device-route mic echo suppression. On iPhone, sessions on the built-in speaker share one voice-processing engine. Continuous providers such as GPT-Live keep the mic open, and the docs say **"Use headphones to avoid speaker audio feeding back into an open microphone"** [verified: `docs/nodes/talk/macos-relay.md`]. So GPT-Live on MacBook speakers needs a headset or speakerphone.
- **speech-swift `LocalVQE`:** streaming on-device AEC, 16 kHz, 16 ms algorithmic latency, takes mic and playback streams [verified, vendor: https://github.com/soniqo/speech-swift]. A candidate for a custom native client; untested.
- **Browser Talk** gets the browser's WebRTC AEC, which is a cheap route for early tests [inference].

### PC

- A browser or WebRTC client gets AEC3 for free [inference]. A Pipecat `SmallWebRTCTransport` with a browser client is the simplest high-quality route. The `macos-local-voice-agents` example uses this transport [verified: https://github.com/kwindla/macos-local-voice-agents].
- Pipecat's transport guide credits echo cancellation to the browser's WebRTC stack and to Daily [secondary, search summary: https://docs.pipecat.ai/client/concepts/choosing-a-transport]. A feature request and community projects using `LocalAudioTransport` point to headphones [secondary: https://github.com/pipecat-ai/pipecat/issues/670]. I did not read the transport source, so "no AEC" stays [unverified]. Plan on hardware AEC or the browser route.
- WSL2 is a poor place for live audio. Run the voice service natively on Windows even if the Gateway stays in WSL2 [inference]. Check this in the PC acceptance test.

### Hardware

| Device | Price | Use | Notes |
|---|---|---|---|
| Wired or Bluetooth headset | Already owned? | V0 and V1 | Solves echo fully; ties Adam to a headset |
| USB speakerphone (Jabra Speak2 55, Anker PowerConf S3 class) | Jabra Speak2 55 UC about €143 at Alza.at [secondary: search result]; Slovak shops [unverified] | Desk, Mac and PC | The device owns both mic and speaker, so firmware AEC just works. Other PC audio on different outputs is not cancelled [inference] |
| ReSpeaker XVF3800 USB 4-mic | $54.90 at Seeed [verified, excludes VAT and shipping: https://www.seeedstudio.com/ReSpeaker-XVF3800-USB-Mic-Array-p-6488.html] | Room, robot | AEC, beamforming, direction of arrival, 5 m pickup. Dual I2S and USB. **Check how the AEC reference is fed**; neither the product page nor Seeed's wiki says [verified: https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/]. The wiki has Windows and macOS tools. A XIAO ESP32-S3 version exists [secondary: https://thepihut.com/products/respeaker-flex-xvf3800-linear-with-xiao-esp32s3] |
| Home Assistant Voice PE | About €59 [secondary: domadoo listing at https://www.domadoo.fr/en/smart-home-hub/7558-nabu-casa-home-assistant-voice-preview-edition-0860011789727.html] | Ready-made ESP32-S3 satellite | Needs Home Assistant [secondary]. A later option, not a first buy |

**Purchase advice:** buy nothing for V0. If V1 passes with a headset and Adam wants hands-free, buy one speakerphone. Buy the ReSpeaker when the robotics track starts. Direction of arrival is also useful for pointing the arm's camera at the speaker.

**Barge-in design:** detect user speech on the AEC-cleaned signal; stop playback within 150 ms; cut the queued TTS; record **what was actually heard** using playback marks so the brain does not assume the user heard the whole answer. OpenClaw notes an interruption timestamp for the next prompt, and its relay cancel is scoped to `turnId` [verified: `docs/nodes/talk/macos-relay.md`]. Add a local "Jorah, stop" keyword that cuts playback on the device. On Gemini this matters more than the first draft said. On plain `gemini-3.8-live`, OpenClaw's `handleBargeIn` does nothing and interruption comes only from Google's server-side voice detection. The client stop exists only on Extended Thinking, and there it is best effort [verified: `docs/providers/google.md`; source: `dist/extensions/google/realtime-voice-provider.js`, `supportsClientContentInterrupt`]. A local keyword can silence the speaker but cannot stop generation on that model [inference].

---

## 6. Speech to text

| Engine | Speed and latency | Slovak | Price | Notes |
|---|---|---|---|---|
| **Parakeet TDT 0.6 v3** (MLX) | **M1 Max 64 GB: 52.7x real time, 0.30 s load** on a 46.7 s synthetic clip [verified page, third-party benchmark: https://vllm-mlx.is-a.dev/benchmarks/audio/]. About 110x on M4 Pro in CoreML batch [verified, vendor: https://huggingface.co/FluidInference/parakeet-tdt-0.6b-v3-coreml] | **8.82% WER on FLEURS**, one of 25 languages [verified: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3] | Free | CC-BY-4.0 [verified: same card]. `parakeet-mlx` 0.6.0, 2026-11-02 [measured: PyPI]. NVIDIA documents chunked streaming in NeMo; one post reports streaming partials every 500 ms using MLX [secondary: https://instagit.com/huggingface/speech-to-speech/live-transcription-parakeet-tdt-apple-silicon-performance/]. **First Slovak local option to test** |
| **Whisper large-v3-turbo** (MLX) | M1 Max: 14.3x, with a slow 21.79 s first load [secondary: same benchmark]. Whisper-class latency is cited as 600 to 800 ms [verified, vendor: https://www.daily.co/blog/building-voice-agents-with-nvidia-open-models/] | Slovak works. large-v2 11.7% WER on FLEURS [secondary: https://arxiv.org/html/2509.19270v1]; large-v3 13.2% in a vendor table [verified, vendor: https://elevenlabs.io/speech-to-text/slovak] | Free | Fine-tuned Slovak Whisper models are public (`NaiveNeuron/slopal`), reducing WER by up to 70% [verified: https://arxiv.org/abs/2509.19270]. Second Slovak local option, mainly for the fine-tunes |
| **Apple SpeechTranscriber** | No published accuracy or latency numbers [secondary] | **No Slovak on this Mac** [measured] | Free | 45 locales; 9 English locales installed [measured]. `DictationTranscriber` lists `sk-SK` but not on-device for `SFSpeechRecognizer` here [measured]. Fine for English V0 |
| **Nemotron Speech Streaming** | **RTX 5090: 19 ms P50 final, DGX Spark: 27 ms**, after a 200 ms pause trigger plus padding [verified, vendor: Daily post above] | **English only** [verified: https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b]. Multilingual Nemotron 3.5 ASR lists `sk-SK` at about 21% to 25% WER on FLEURS [verified: https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b] | Free | Best candidate for English on an NVIDIA PC, not for Slovak. The card's preferred OS is Linux, so Windows is [unverified] |
| **Soniox `stt-rt-v5`** | Claims sub-200 ms [secondary, vendor] | Slovak `sk`, real time and async [verified: https://docs.soniox.com/stt/concepts/supported-languages] | **$0.12/h** [verified: https://soniox.com/pricing] | Cheapest hosted pick |
| **Gemini 3.5 Transcribe Live** | No figure; 4.0% streaming WER, dataset not stated [verified, vendor: https://blog.google/innovation-and-ai/technology/developers-tools/build-real-time-voice-applications-gemini-audio/] | 85+ languages; Slovak not checked | About $0.009/min, or $0.54/h [verified: https://aistudio.google.com/docs/pricing] | GA since August 2026 [verified: https://aistudio.google.com/docs/changelog]. Missing from the first draft. Costs more than Soniox |
| **ElevenLabs Scribe v2 Realtime** | ~150 ms [verified, vendor: https://elevenlabs.io/pricing/api] | Scribe v1: 3.4% WER on FLEURS [verified, vendor: https://elevenlabs.io/speech-to-text/slovak]; no figure for v2 | $0.39/h | Probably the most accurate Slovak claim; verify with Adam's voice |
| **Deepgram Nova-3** | Not measured here | Slovak in mono and multi [verified: https://developers.deepgram.com/docs/models-languages-overview] | About $0.0048 to $0.0058/min [secondary, sources conflict] | **Flux does not support Slovak** [verified, same page] |
| **OpenAI `gpt-realtime-whisper`** | Not measured here | Not confirmed | $0.017/min [verified: https://developers.openai.com/api/docs/pricing] | Expensive compared with Soniox |
| **Voxtral Realtime** | Sub-200 ms configurable [secondary: https://docs.mistral.ai/capabilities/audio_transcription] | **No Slovak**; 13 languages [secondary] | Open weights | Not a fit |

**Sanity math for M1 Max** [inference]: a 5 s utterance takes about 95 ms on Parakeet and about 350 ms on turbo once loaded. Keep models resident, since a first-load penalty ruins latency.

**NVIDIA PC:** Parakeet on Windows is not proven. The sherpa-onnx changelog lists a Parakeet v3 export and prebuilt CUDA wheels for Windows x64 [secondary: search summary, exact version not checked], and NVIDIA's card lists NeMo-Speech.cpp with GGUF [verified: card; Windows untested]. Candidates to test are `sherpa-onnx` with CUDA (v2.0.1), `faster-whisper` 1.2.1 and NVIDIA NeMo 3.0.0 under WSL2 [measured versions: PyPI]. OpenClaw notes sherpa and whisper.cpp can run with CUDA [verified: `docs/nodes/audio.md`].

---

## 7. Text to speech

| Engine | Latency | Slovak | Price | Notes |
|---|---|---|---|---|
| **Kokoro-82M** | M1 Max MLX: **11.9x to 15.5x real time**, 0.22 to 2.81 s load [secondary: benchmark above]. CPU: **3,658 ms to first speech on a Ryzen 7 5700X** [verified, vendor with competing product: https://picovoice.ai/blog/on-device-tts/] | No | Free, Apache-2.0 [verified: https://github.com/hexgrad/kokoro] | Good on Apple Silicon and GPU, too slow on CPU alone. Available through `speech-swift` and `mlx-audio` |
| **Soprano-80M** | Not measured on Mac; 1,702 ms on Ryzen [same] | Not confirmed | Free | **OpenClaw's default macOS MLX voice** [verified: `docs/nodes/talk.md`] |
| **Fish S2 Pro (local)** | ~200 ms claim [secondary] | Not confirmed | Personal use only | Research licence, commercial use needs a separate licence [verified: `docs/providers/fish-audio.md`]. Has voice cloning |
| **Piper** | 1,720 ms on Ryzen [same] | **`sk_SK-lili`** [secondary: https://huggingface.co/rhasspy/piper-voices/raw/refs%2Fpr%2F15/sk/sk_SK/lili/medium/MODEL_CARD] | Free | **`piper-tts` 1.8.0 is GPL-3.0-or-later** [measured: PyPI]. Fine for personal use, needs review for a product |
| **Chatterbox Turbo** | ~470 ms on GPU [secondary]; 48 s on CPU [Picovoice, vendor]. Sub-200 ms applies only to Resemble's paid service [verified] | **No Slovak** [verified: https://github.com/resemble-ai/chatterbox] | MIT | English cloning on GPU; ~6 GB VRAM [secondary]. Includes a Perth watermark [verified] |
| **ElevenLabs Flash v2.5** | ~75 ms on pricing page, ~100 ms on capabilities page [verified, vendor] | **Yes**, read from the page's wording: 32 languages, all of v2's plus three, and Slovak is in v2's list [verified: https://elevenlabs.io/docs/overview/capabilities/text-to-speech] | **$0.04/1K chars** on the current API page [verified: https://elevenlabs.io/pricing/api]; another localized listing showed $0.05, check at signup | Default OpenClaw hosted provider. Eleven v4 Turbo (~100 ms) also exists; Slovak not confirmed |
| **Cartesia `sonic-3.6`** | No first-party number found | **Yes** [verified: https://docs.cartesia.ai/build-with-cartesia/tts-models/latest] | About 1 credit per char [verified: https://docs.cartesia.ai/pricing]; plans $5 per 100K, $49 per 1.25M [secondary, sources conflict] | Runner-up |
| **Soniox TTS** | Not measured | Slovak page exists [secondary] | ~$0.70 per hour of speech [verified: https://soniox.com/pricing] | Cheapest hosted; test quality |
| **OpenAI `gpt-4o-mini-tts`** | Not measured | Not confirmed | $12 per 1M audio tokens [verified: OpenAI pricing] | Not needed if a Realtime provider handles voice |
| **Gemini 3.8 Flash TTS** | Batch-style | Not needed separately | $0.00225 per 10 s through 2026, doubles January 2027 [verified: https://ai.google.dev/gemini-api/docs/pricing] | Watch the price change |

**Voice choice and consent.**

- **Do not imitate Paul Bettany or J.A.R.V.I.S.** ElevenLabs bars cloning a voice without consent or legal right [secondary: https://conductatlas.com/platform/elevenlabs/elevenlabs-usage-policy/non-consensual-voice-cloning-prohibition/, plus https://elevenlabs.io/docs/help-center/product/voices/voice-cloning/are-there-any-restrictions-on-what-voices-i-can-upload-for-voice-cloning]. Pick a stock calm voice or design an original one.
- **Cloning Adam's own voice:** allowed, but it creates an asset that can scam people who know Adam. Keep reference audio local, and do not use it as Jorah's default [inference].
- **Other people's voices:** only with explicit consent, recorded in the repo as a simple dated note.

---

## 8. Speech-to-speech APIs

Prices read today. Cost per hour assumes 60 minutes with the mic open and Jorah speaking 40% of the time (24 minutes). "Month" means 1 hour per day, 30.4 hours [inference]. "Base" ignores context replay; the second table adds it.

| Model | Published price | Per hour | Per month | Slovak | Notes |
|---|---|---|---|---|---|
| **Gemini 3.8 Live** | Audio in **$0.005/min**, out **$0.018/min**, video $0.002/min; $3 and $12 per 1M audio tokens, $0.75 per 1M text in [verified: https://aistudio.google.com/docs/pricing] | $0.73 base | **$22 base; $38 to $51 short sessions; ~$163 left open** | **Yes** (`sk`) [verified: https://aistudio.google.com/docs/live-api/capabilities] | Whole context re-billed each turn, no caching. Async function calling by default. Up to 1 fps video. Paid tier content is not used for product improvement; free tier content is [verified] |
| **gpt-realtime-2.1-mini** | $10 and $20 per 1M audio tokens, $0.30 cached [verified: https://developers.openai.com/api/docs/pricing]. ~600 tokens/min in, ~1,200 out [secondary, uncited: https://www.layer3labs.io/guides/openai-realtime-api-pricing] | $0.94 base | **$29 base; $29 to $39 short sessions; $37 to $93 left open** | Not confirmed | The Mac relay docs' example uses `gpt-realtime-2.1`, and `gpt-realtime-2.1-mini` is a listed GA relay model that needs a Platform key [verified: `docs/nodes/talk/macos-relay.md`, `docs/nodes/talk.md`]. Wake-name gating is documented for Discord voice, not Mac Talk [verified: `docs/channels/discord/voice-channels.md`] |
| **gpt-realtime-2.1** | $32 and $64, $0.40 cached [verified] | $3.00 | **$91**; 2x to 5x possible [secondary] | Not confirmed | Most capable GA model; not worth it over mini without evidence |
| **GPT-Live-1** | **$0.05/min**, billed per second; backend separate [verified: https://developers.openai.com/api/docs/models/gpt-live-1] | $3.00 | **$91** | Voice table lists English, Portuguese, German, French, Hindi, Japanese, Korean; no Slovak voice; the page does not say other spoken languages are unsupported [verified: https://developers.openai.com/api/docs/guides/live-conversations] | Flat published rate, so no replay risk in the price. Full duplex, built-in delegation, most natural. No host-enforced wake-name gating [verified: `docs/channels/discord/voice-channels.md`]. OpenClaw also has a `gpt-live-1-codex` route via ChatGPT OAuth [verified: `docs/nodes/talk.md`]; whether that is covered and allowed for this use is an Adam question |
| **Amazon Nova 2 Sonic / 2.5 Sonic** | $3 and $12 per 1M speech tokens [secondary] | ~$0.90 [secondary estimate $0.015/min] | ~$27 | **No**; seven languages [secondary] | Stockholm region reported. Adds AWS. Reject |
| **ElevenLabs Realtime v1 / Speech Engine** | $0.08/min plus LLM; 570 to 620 ms to first audio [verified, vendor: https://elevenlabs.io/pricing/api] | $4.80+ | **$146+** | Not confirmed for Realtime | Too expensive |
| **Anthropic** | None found | n/a | n/a | n/a | See section 1. Claude Code voice is dictation and needs a claude.ai login [verified: https://code.claude.com/docs/en/voice-dictation] |

**Cost with replay [inference from the verified rates above].** All rows are 60 connected minutes per day, 100 turns, 15 minutes of Adam's speech and 24 of Jorah's. Gemini: 25 audio tokens per second in context, replayed at $3 per 1M, plus a 3K text prompt per turn. Mini: the third-party token rates, replayed at the cached rate or with 20% of replay missing the cache. These are models, not bills.

| Usage pattern | Gemini 3.8 Live | Mini, all replay cached | Mini, 20% misses | GPT-Live-1 |
|---|---|---|---|---|
| Left open, two 30-minute relay sessions | $5.35/h, **~$163/month** | $1.22/h, **~$37** | $3.06/h, **~$93** | $3.00/h, $91 |
| 12 sessions of 5 minutes | $1.69/h, **~$51** | $0.98/h, **~$30** | $1.29/h, **~$39** | $3.00/h, $91 |
| 30 sessions of 2 minutes | $1.25/h, **~$38** | $0.95/h, **~$29** | $1.08/h, **~$33** | $3.00/h, $91 |

Replay grows with the square of session length, so short sessions matter more than the provider. One hour per day is also a heavy assumption: costs fall in proportion with real use. A forum poster found that summing every per-turn snapshot matched a real Gemini Live bill within about 3%, while pricing only the final snapshot was about 8.6x too low [secondary: https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248].

**Why `gpt-realtime-2.1-mini` for V1:** cheapest or tied in every modelled pattern, the Mac relay path is documented with a working config shape, and English is enough for V1. The weak point is that its tokens-per-minute figure is third-party, so log real usage in the bake-off before trusting this.

**Why Gemini 3.8 Live stays the runner-up:** Slovak confirmed, continuous camera at $0.002/min, and async tool calls so it can keep talking during a consult. It becomes the pick if Slovak or continuous vision is needed in V1. Continuous camera is documented only for browser Video Talk, where frames go straight from the browser to Google; the provider sets `supportsVideoFrames`, but Mac relay video is [unverified] [verified: `docs/nodes/talk/realtime-sessions.md`; source: `dist/extensions/google/realtime-voice-provider.js`]. Google's default turn coverage for 3.8 includes all video, so video tokens may also be replayed [inference from https://aistudio.google.com/docs/live-api/capabilities].

**Gemini caveats, if it wins or is chosen:**

- Audio sessions end at 15 minutes and audio-video at 2 minutes without compression. A connection lasts about 10 minutes, followed by `GoAway`. Resumption handles last 2 hours [verified: https://aistudio.google.com/docs/live-api/session-management]. OpenClaw enables resumption and compression by default [verified: `docs/providers/google.md`].
- **OpenClaw's default Google model for Voice Call is `gemini-3.1-flash-live-preview`, which has different function calling.** Set `gemini-3.8-live` explicitly [verified: `docs/providers/google.md`, https://aistudio.google.com/docs/live-api/capabilities].
- **Replay:** see the table above. `contextWindowCompression` is only on or off in OpenClaw, and it sends an empty `slidingWindow` with no trigger or target [source: `dist/extensions/google/realtime-voice-provider.js`]. Google's example uses a 100K trigger and 4K target and warns of history loss [verified: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices]. So OpenClaw's default may not limit replay in short or medium sessions [inference], and lowering the trigger needs a code change. Thought tokens bill on top at the text output rate, and there is no per-turn spending cap [secondary, Google reply: https://discuss.ai.google.dev/t/gemini-3-8-live-missing-billable-token-details-and-pre-generation-spending-bounds/188765]. **Read real bills in week one.**
- **Mac path:** the shipped code gives the Google provider `transports: ["provider-websocket", "gateway-relay"]` and tool calls, and the catalog builder then lists `agent-consult` [source: `dist/extensions/google/realtime-voice-provider.js`, `buildTalkCatalog` in `dist/handlers-*.mjs`]. The same provider code reads `silenceDurationMs`, `sessionResumption` and `contextWindowCompression`. This is a source check, not a device run, so step 1.2 still applies.
- **Status conflict:** the release notes list Gemini 3.8 Live as GA on 2026-09-15 and the model page calls it stable, while the capabilities page says the Live API is in preview [verified: https://aistudio.google.com/docs/changelog, https://aistudio.google.com/docs/models/gemini-3.8-live, https://aistudio.google.com/docs/live-api/capabilities]. Treat behaviour as subject to change.

**Bake-off (V1, one evening):** Gemini 3.8 Live, `gpt-realtime-2.1-mini`, GPT-Live-1. Same 30 scripted turns, same mic. Score real token usage per session, time to first audio, barge-in stop time, handoff smoothness, wrong delegations, and Adam's subjective preference. Adam picks using real numbers. GPT-Live wins if it is clearly better and $91 per month is acceptable.

---

## 9. Orchestration

| Layer | Status | Use |
|---|---|---|
| **OpenClaw Talk** | v2026.10.9 pinned, latest upstream as well [measured: GitHub API]. Modes: native loop, realtime. Clients: macOS, iOS, Watch, browser, Android [verified: `docs/nodes/talk.md`] | V0 and V1, plus the permanent client and policy layer |
| **Pipecat** | 1.15.0 from 2026-10-29 [measured: PyPI]. BSD-2. Local, SmallWebRTC, Daily, LiveKit, WebSocket transports. Kokoro and Piper listed. Krisp and RNNoise in audio processing [verified: https://github.com/pipecat-ai/pipecat] | V2 voice service |
| **LiveKit Agents** | 1.8.10 from 2026-10-28 [measured: PyPI]. **Adaptive interruption has no self-host release plan** beyond a dev allowance; a reply says production needs LiveKit Cloud [secondary: https://community.livekit.io/t/roadmap-for-adaptive-interruption-handling-in-self-hosted-livekit-workers/1172]. Self-hosted per-request fees reported from 2026-10-23: turn detection $0.50 and interruption $1.20 per 1,000 [secondary: https://www.usagepricing.com/blueprint/activity/livekit-2026-10-23-self-hosted-turn-detection-fees] | Runner-up. Local-first favors Pipecat. Consider if rooms or many robots matter |
| **speech-swift** | Apache-2.0. Parakeet, Kokoro, Silero, KWS, AEC and speaker embeddings on Apple Silicon. `speech-server` is an OpenAI-compatible local TTS endpoint OpenClaw can use directly [verified: `docs/tools/tts/configuration.md`; verified, vendor: https://github.com/soniqo/speech-swift] | Easy local TTS in V0, native parts in V2 |

**How V2 plugs into OpenClaw:** register a provider through `api.registerRealtimeVoiceProvider`, with `transports: ["gateway-relay"]`, `supportsBargeIn`, `supportsToolCalls`, PCM16 at 24 kHz, and a `createBridge` that connects to the local Pipecat process over a Unix socket or loopback WebSocket [verified: `docs/plugins/sdk-provider-plugins/voice-and-audio.md`]. Mac and iPhone Talk should then use Jorah's own pipeline without changing clients, since non-OpenAI configs stay on the Gateway relay [verified: `docs/nodes/talk.md`]. **Apple Watch will not:** it needs `webrtc` transport with `gateway-control-v1` and fails visibly otherwise [verified: `docs/platforms/ios.md`]. The same limit should apply to Gemini on the Watch [inference]. `runAgentConsult`, gating and history stay in the host. This has not been tried, so run it as a one-day spike first [inference].

**Gaps OpenClaw does not cover (ours to build):**

- Custom-model wake word on Mac and any wake word on Windows.
- An idle close for realtime sessions on the Mac. I found none in the Mac sources, only a 30-minute Gateway relay limit [source: see section 1, finding 8]. `talk.session.close` exists, so a small helper could do it [inference]. Needed in V1.
- A documented way for an external detector to start Talk on Mac. `talk.ptt.*` is documented for iOS and Windows nodes but not macOS [verified: `docs/platforms/ios.md`, `docs/platforms/windows.md`]. Check this when building V2.
- A fully offline brain.

---

## 10. Latency budget

**Definition:** from when Adam stops speaking to when the first sound of Jorah's real answer reaches the air. This is measured on an audio recording, not in logs. Daily found client-side numbers run about 250 ms higher than server logs over WebRTC, and telephony adds 300 to 600 ms [verified, vendor: https://www.daily.co/blog/building-voice-agents-with-nvidia-open-models/].

### Measured figures

| Stack | Stage figures | End to end | Source quality |
|---|---|---|---|
| RTX 5090, Nemotron ASR, Nemotron 3 Nano, Magpie TTS | ASR final 19 ms P50, LLM first token 171 ms, TTS first byte 108 ms | **508 ms P50, 544 P90, 639 max, server-side**; ~760 ms client-side | Vendor-adjacent, stated method [verified: Daily post] |
| DGX Spark, same stack | 27, 750, 185 ms | 1,180 ms P50, 1,359 P90 | Same |
| M-series Mac, Silero, Smart Turn, MLX Whisper, Gemma, Kokoro | No breakdown | "<800 ms" | Claim only, no method or chip [verified: https://github.com/kwindla/macos-local-voice-agents] |
| Anthropic cookbook: Scribe v1 batch, Haiku 4.5, Turbo v2.5 | STT 0.54 s, first token 0.71 s, TTS first chunk 0.39 s | 1.48 s from Claude to first audio via sentence streaming | Single run, indicative [verified: Claude cookbook] |
| ElevenLabs Realtime v1 Mini / Max | n/a | 620 / 570 ms to first audio | Vendor [verified] |
| Claude Haiku 5.5 at low effort, adaptive thinking, 10K input | First answer token **about 6 to 9 s** (8.83 s first chunk and 9.05 s answer token on recheck) | n/a | Artificial Analysis, medians [verified: https://artificialanalysis.ai/models/claude-haiku-5-5-low/providers]. Thinking on with long input, so not a voice setup. **Thinking disabled was not measured** |
| Gemini 2.5 Flash-Lite | About 380 ms first token | n/a | [secondary: https://www.fast.io/resources/fastest-ai-2026.md]; older model |
| OpenClaw native Talk | 700 ms silence window, then the **full agent run**, then TTS | Multi-second, longer with Opus thinking | Inference from [verified: `docs/nodes/talk/macos-relay.md`] |

### Target

**P50 at most 800 ms, P90 at most 1,200 ms to first audio. If a real answer will take longer, a truthful acknowledgement starts within 800 ms.**

| Stage | Mac, V2 pipeline (ms) | PC with RTX, V2 (ms) | Basis |
|---|---|---|---|
| End-of-turn detection (VAD 200 + Smart Turn) | 215 to 265 | 215 to 265 | Pipecat recommendation, Smart Turn 12 to 65 ms |
| STT final (parallel with the above) | +0 to 100 | +0 to 30 | Parakeet 52.7x; Nemotron 19 ms |
| Fast LLM first token | 250 to 450 | 170 to 400 | Network or local; **must be measured** |
| TTS first audio | 100 to 250 | 100 to 150 | Flash ~100; Kokoro MLX estimate; Magpie 108 |
| Audio output and AEC buffering | 50 to 100 | 50 to 100 | Estimate |
| **Total** | **~615 to 1,165** | **~535 to 945** | [inference] |

**For V1:** no measured first-party latency was found for either provider [unverified]. Google says Gemini 3.8 Live is engineered for sub-second latency, with no figure [verified, vendor: https://aistudio.google.com/docs/changelog]. Measure it. On Gemini, start silence at 500 ms against Google's 500 to 800 ms recommendation.

**Latency tactics, in order of payoff** [inference]:

1. Keep every model resident and every connection warm. One cold load costs seconds.
2. Stream the LLM to TTS on sentence boundaries, and synthesize the first clause early.
3. Keep the fast layer's prompt small and cached.
4. Pre-render fillers and earcons locally so they play in under 100 ms.
5. Start the LLM on an early transcript and discard it if the user continues.
6. Keep streaming STT partials warm for instant barge-in handling.

---

## 11. Fast voice to deep Claude brain handoff

This is the design that makes it feel like one assistant.

### Roles

- **Fast voice (Gemini Live or Haiku).** Personality, small talk, turn-taking, status, clarifying questions. It holds a small persona prompt and a bounded digest of memory. It has **no direct tools** other than consult, and possibly harmless local ones (time, timer).
- **Deep brain (Claude Opus 5.5 through OpenClaw).** All memory, all actions, all reasoning. It owns truth.

### Routing rule, in the fast voice's prompt

> Answer directly only for greetings, repairs ("what did you say"), and things already in this conversation. For anything about Adam's data, memory, schedule, the world, or any action, call `openclaw_agent_consult`. Never guess. Never say a thing is done until the tool result says so.

OpenClaw has a config switch: `realtime.consultRouting` is `provider-direct` or `force-agent-consult` [verified: `docs/nodes/talk.md`]. **Start with `provider-direct`.** Forcing every utterance through Opus would make "thanks" take seconds. Test whether the fast voice invents facts, and flip to `force-agent-consult` if it does.

### Sequence

```
Adam: "Jorah, what's on my calendar tomorrow and move the dentist to Friday?"
  t+0.0   End of speech
  t+0.3   Fast voice decides to delegate
  t+0.6   Spoken acknowledgement ("On it, checking.")
          [OpenClaw's neutral receipt is documented for GPT-Live native calls.
           On Gemini or GA Realtime expect the model's own filler, which the
           section 11 rules must constrain. A receipt is not proof a tool started]
  t+2..15 Claude runs. Adam may speak meanwhile:
             "how's it going?"  -> status
             "only if it's after 3pm" -> steer, queued into the active run
             "never mind" -> cancel
  t+n     Claude returns: facts plus a proposed change
          Fast voice paraphrases, asks for confirmation of the move
  Adam:   "yes"
          OpenClaw's spoken-confirmation gate consumes it for that exact action
  Done.   Result stored in shared history; a digest goes to the last non-web channel
```

### What OpenClaw provides [verified: `docs/nodes/talk/realtime-sessions.md`]

- **`talk.client.steer` / `talk.session.steer`:** classifies speech as `status`, `steer`, `cancel` or `followup`, with explicit rejection reasons. The shared Apple relay client calls `talk.session.steer` [source: `RealtimeTalkRelaySession.swift` at tag v2026.10.9].
- **Shared history:** finalized user and assistant speech is appended to the same agent session. Later chat and voice turns share one history. Generated consult prompts are hidden from chat and later model context.
- **Bounded context in:** new native calls get history as quoted background, newest 16 entries, 800 chars each, 8,000 bytes total. It does not establish live task state. This limit is documented for Gateway-controlled native WebRTC calls, meaning GPT-Live; direct WebSocket seeds keep their existing form, and the doc gives no limit for them.
- **Accepted work outlives the audio connection.** A spoken replacement is not guaranteed, so the answer stays visible in chat.
- **Spoken confirmation gate:** exact and single-use, bound to canonical arguments; generated text cannot supply it.
- **Voice call changes digest** at call end.
- **`consultThinkingLevel`, `consultFastMode`** tune the brain for voice [verified: `docs/nodes/talk.md`].

### GPT-Live client delegation, if chosen [verified: https://developers.openai.com/api/docs/guides/live-delegation]

- `session.delegation.created` carries only an ID. Build the request from `session.input_transcript.delta` and `output_transcript.delta`.
- Feed results with `session.commentary.append` (spoken) and `session.thinking.append` (quiet), up to 500 tokens each.
- Interrupting speech does **not** stop backend work. Your app owns cancellation, and should confirm it before saying it is cancelled.
- Track operation IDs and task revisions so retries cannot duplicate actions.
- `acknowledgement_delay_ms` controls automatic acknowledgements.

### Rules for V2 and for truthful speech [inference]

1. **Filler tiers:**
   - Under 800 ms: nothing, just answer.
   - 800 ms to 3 s: short acknowledgement, varied, from local cache.
   - 3 to 15 s: one progress line per 8 seconds at most, based on real events only.
   - Over 15 s: "I'll work on this and message you when it's done", then close the mic. The answer goes to Telegram.
2. **Never speak a claim the brain has not returned.** Fillers must not state outcomes. This matches Adam's truthful-claims rule.
3. **Keep the transcript honest.** Store what was heard up to the barge-in, not what was generated. Summarize tool output for voice, and put long material on screen. OpenClaw already redirects code-heavy replies to the screen [verified: `docs/nodes/talk.md`].
4. **Idempotency:** every action carries an operation ID, so reconnects and resumptions cannot repeat it.
5. **Reconnection:** on fallback from provider A to B, seed the same bounded digest. Check unfinished work before continuing, as OpenAI's docs also recommend [verified: https://developers.openai.com/api/docs/guides/live-conversations].
6. **Slow brain check:** Claude CLI turn latency over ACP has not been measured. Measure time from consult start to first useful text. It sets the filler tiers. Note that Opus 5.5 thinking cannot be disabled, and effort is the only control [verified: Claude API skill]. API fast mode is API-only, so it may not apply to the Max CLI runtime [inference, check `consultFastMode`].

---

## 12. Speaker identification and why voice is not authentication

**Use speaker ID to improve quality, never for permission.**

### What it is for

- Reject TV and other people for wake stage 2.
- Personalize: "my calendar" means the enrolled speaker's calendar.
- Stop the unknown speaker's turn from reading Adam's private data aloud.

### Tools

`speech-swift` lists WeSpeaker ResNet34, ReDimNet2-B6 and CAM++ embeddings [verified, vendor]. SpeechBrain 1.1.2 (Apache-2.0) and pyannote.audio 4.0.7 are current [measured: PyPI]. openWakeWord custom verifier models are designed for this [verified].

### Why it is not authentication

- Voice cloning from very small samples can bypass commercial speaker verification, and anti-spoofing detectors do not generalize well across synthesis methods [verified, abstract: https://arxiv.org/abs/2601.02914]. The authors recommend multi-factor authentication.
- In spoofing-aware literature, conventional ECAPA-TDNN scored about 0.83% EER on ordinary impostors but about 29.3% EER against spoofs [secondary, search snippet, exact paper unconfirmed]. Roughly: great at telling people apart, poor at telling a real person from a fake.
- Other attack routes [inference]: a voice on the TV or YouTube, a recording, a visitor, a child, a video call on speaker. Inaudible-command attacks are also described in research.

### Action tiers, a proposal for the security track

| Tier | Examples | Voice alone? | Required |
|---|---|---|---|
| 0 Public | Time, weather, general knowledge | Any speaker | Nothing |
| 1 Personal read | Calendar, unread count, memory | Enrolled speaker **and** Adam's device near or Adam at desk | Enrolled embedding, and session opened on a trusted device |
| 2 Reversible write | Add a reminder, draft a message | Enrolled speaker with a spoken yes | OpenClaw exact confirmation |
| 3 Sends or changes for others | Send a message, move an event, publish, drive the robot | **No** | Spoken yes **plus** a tap on iPhone, Watch or Telegram |
| 4 Irreversible or financial or security | Delete, pay, change credentials, run shell commands on the host | **Never by voice** | Sit at the keyboard, or a strong approval flow |

OpenClaw's voice gate requires a new exact spoken confirmation for sends, node control, browser and computer actions, service changes, destructive shell commands and publication [verified: `docs/nodes/talk/realtime-sessions.md`]. **That is a good floor but a spoken "yes" is not proof of identity**, so tier 3 needs out-of-band approval. This also covers the known gap of Jorah's exec tool running as Adam's macOS user: voice sessions should not reach exec at all without keyboard-level approval [inference].

### Also

- **Audio prompt injection:** treat the transcript as untrusted input, as with web pages. Instructions heard from media must not grant permissions.
- **Visible state:** clear states for "local listening", "streaming to cloud" and "muted", plus a hardware mute or keyboard shortcut. The Mac menu-bar indicator exists [verified: `docs/platforms/mac/voicewake.md`].
- **Retention:** no raw audio on disk by default; RAM ring buffer only. Transcripts go into memory under the same rules as chat.
- **Keys:** provider keys remain on the Gateway. Browser clients receive only ephemeral constrained credentials [verified: `docs/nodes/talk.md`].
- **Wake gating saves money and privacy.** Close provider sessions after an idle period, since billing and cloud listening continue while open. OpenClaw's Mac client does not appear to do this (section 1, finding 8), so V1 must. Gateway relay sessions close at 30 minutes [source], and GPT-Live has a 30-minute TTL [verified: `docs/nodes/talk.md`].

---

## 13. Slovak support summary

| Layer | English | Slovak local | Slovak hosted |
|---|---|---|---|
| Wake phrase | Train in English pronunciation; include Adam's accent | n/a | n/a |
| Apple Speech | On-device `en-US` [measured] | **Not on-device** on this Mac [measured] | `sk-SK` via Apple network services, for Talk and PTT only [measured, verified: `docs/platforms/mac/voicewake.md`] |
| STT | Parakeet v3, Whisper | Parakeet v3 (8.82% WER on FLEURS), Whisper or `slopal` fine-tunes | Scribe v2, Soniox v5, Nova-3 |
| Turn detection | Smart Turn | **Not supported**, use a silence window | Provider VAD |
| TTS | Kokoro | Piper `sk_SK-lili`, macOS `Laura` [measured] | ElevenLabs Flash v2.5, Cartesia 3.6, Soniox |
| S2S | All | None | **Gemini 3.8 Live** confirmed; others not confirmed |

**Recommendation:** English is the primary spoken language for Jorah. Slovak is a Phase 2 feature using Gemini Live or a hosted STT/TTS pair. Mixed English and Slovak in one sentence (names, school subjects, EduPage terms) is a likely real need. Test with names and places, and add a custom vocabulary if the provider offers one. OpenClaw's Gemini path does not send `languageCodes` since the current Google SDK rejects them on that API path, so language is auto-detected [verified: `docs/providers/google.md`]. Google recommends setting the language explicitly [verified: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices], so test mixed speech with care.

---

## 14. Law and consent in Slovakia and the EU

Not legal advice. Have someone qualified check before any business use.

- **Purely personal use:** GDPR does not apply to processing "in the course of a purely personal or household activity" [verified: https://gdpr-info.eu/art-2-gdpr/]. A **possible business** removes that shelter for customers and pilot users [inference].
- **Voice prints:** biometric data used to uniquely identify a person is special-category data, banned by default, with explicit consent as one exception [verified: https://gdpr-info.eu/art-9-gdpr/]. Enrolling family or visitors should be opt-in, and revocable with deletion. Do not enrol anyone without asking [inference].
- **Recording others at home:** an always-listening mic near visitors and family deserves a visible indicator and a mute, whatever the legal analysis. Slovak personality-rights rules on voice recordings were not researched [unverified]. The legal track should cover them.
- **EU AI Act Article 50:** providers must make it clear that people are interacting with AI, and generated audio needs a machine-readable mark; deployers must disclose deepfakes [verified: https://artificialintelligenceact.eu/article/50/]. Timing: Art. 50 applies from 2026-08-02 [verified: same page]. The Digital Omnibus was published on 2026-07-24 and has been in force since 2026-07-27. It gives generative systems placed on the market before 2026-08-02 until 2026-12-02 for labelling [secondary, law firm: https://cms.law/en/gbr/publication/the-eu-s-digital-omnibus-streamlined-ai-act-compliance-rules-are-now-in-force]. A system placed on the market later gets no grace period, so a future Jorah product would need marking from launch [secondary, search summaries]. I did not read the Official Journal text [unverified]. For a business, Jorah must tell callers and other people it is AI, and hosted TTS terms matter. Chatterbox watermarks output [verified].
- **Provider terms:** Google requires API users to be 18 or older. Anyone making an API client available to users in the EEA, Switzerland or the UK may use only Paid Services. On unpaid services, human reviewers may read content [verified: https://aistudio.google.com/docs/terms]. Slovakia is an available region [verified: https://aistudio.google.com/docs/available-regions]. OpenAI's equivalent terms were not checked [unverified].
- **Licences that matter only if this becomes a business:** Fish S2 Pro research licence [verified]; openWakeWord pretrained models CC BY-NC-SA [verified]; Piper GPL-3 [measured]; Kokoro Apache-2.0 [verified]; Pipecat BSD-2 [verified]; livekit-wakeword Apache-2.0 [verified].

---

## 15. Recommended stacks and costs

Assumes 1 hour of talk per day, 30.4 hours per month. Excludes the existing Claude Max subscription. API prices exclude tax.

### Mac now

| Layer | V0 | V1 | V2 (hybrid) | Fully local fallback |
|---|---|---|---|---|
| Wake | Apple Speech `en-US` | Apple Speech, or `livekit-wakeword` if it fails | `livekit-wakeword` plus stage 2 | Same |
| Capture and AEC | Headset | Headset or speakerphone | Speakerphone or `VoiceProcessingIO` | Same |
| VAD and turn | OpenClaw 700 ms | Provider VAD | Silero 6.2 plus Smart Turn 3.2 | Same |
| STT | Apple Speech | Provider | Parakeet v3 | Parakeet v3 (Whisper or `slopal` for Slovak) |
| Fast voice | None | **`gpt-realtime-2.1-mini`** (or Gemini 3.8 Live) | Haiku 5.5 no-thinking, or Flash-Lite | Local Gemma or Qwen class via MLX; 64 GB is ample |
| TTS | MLX Soprano or Kokoro | Provider | Kokoro, or ElevenLabs Flash | Kokoro, Piper `sk_SK-lili` |
| Deep brain | Claude via OpenClaw | Claude via consult | Claude via consult | **Offline:** local model only, plus a queue for Claude when back online. Must say "I'm offline" |
| Orchestration | OpenClaw native | OpenClaw realtime | Pipecat behind OpenClaw provider | Pipecat alone if Gateway is down |
| First audio (target) | Several seconds | Measure; aim under 800 ms | Under 800 ms | Under 1,200 ms |
| **Monthly cost** | **$0** | **$29 to $39** short sessions; up to $93 left open | **~$1 local voices; ~$27 with ElevenLabs** | **$0** plus ~€0.30 electricity [inference] |

Fully local fallback is limited on tools: it should do time, timers, notes, read-only local memory, and home or robot commands if already authorized. It should queue the rest, and it must never pretend to be the Claude brain.

### Cost detail for hosted and hybrid options [inference from verified prices]

Assumes 24 minutes of Jorah speech per hour at about 900 characters per minute, so 21,600 characters per hour.

| Combination | Per hour | Per month |
|---|---|---|
| Parakeet + Haiku 5.5 + Kokoro | ~$0.02 | **~$0.60**, perhaps covered by Max's $100 API credits (check) |
| Parakeet + Haiku 5.5 + ElevenLabs Flash ($0.04 per 1K) | ~$0.88 | **~$27** |
| Soniox STT + Haiku 5.5 + Soniox TTS | $0.12 + $0.02 + $0.28 = $0.42 | **~$13** |
| Soniox STT + Haiku 5.5 + ElevenLabs Flash | ~$1.00 | **~$30** |
| Scribe v2 Realtime + Haiku 5.5 + ElevenLabs Flash | ~$1.27 | **~$39** |
| Gemini 3.8 Live, short sessions | $1.25 to $1.69 | **$38 to $51** |
| Gemini 3.8 Live, left open | $5.35 | **~$163** |
| Gemini camera on all the time | +$0.12 base, plus any video replay | **+$4 or more** |
| gpt-realtime-2.1-mini, short sessions | $0.95 to $1.29 | **$29 to $39** |
| gpt-realtime-2.1-mini, left open | $1.22 to $3.06 | **$37 to $93** |
| GPT-Live-1 | $3.00 | **$91** |

Haiku estimate: about 100 turns per hour, with a cached 4K prompt at $0.01 per MTok, ~300 new input tokens at $0.10 per MTok and ~80 output tokens at $0.50 per MTok [verified prices: https://platform.claude.com/docs/en/about-claude/pricing]. The Claude consult cost itself is against the Max limits. Heavy voice use may hit those; watch usage.

### PC later

PC specs are unknown. **Check:** GPU model and VRAM (`nvidia-smi`), CPU, RAM, free disk, Windows or Linux, whether a mic and speaker exist near it, and network to the Mac.

| Tier | Hardware [inference, based on figures above] | What runs locally | Expected |
|---|---|---|---|
| **Minimum** | 8-core desktop CPU, 16 GB RAM, no GPU | Wake, VAD, Smart Turn, Parakeet ONNX on CPU, Piper. Kokoro on CPU is slow (3.7 s to first speech on a Ryzen 7 5700X) | Use hosted TTS and a hosted fast model. ~1 s first audio is plausible |
| **Recommended** | NVIDIA with at least 12 GB VRAM, 32 GB RAM | Plus GPU Parakeet or Nemotron streaming, Kokoro or Chatterbox Turbo (~6 GB) | Local STT and TTS well below 200 ms each. Fast LLM still hosted |
| **Ideal** | NVIDIA with 32 GB VRAM, for example the measured RTX 5090 (32 GB [verified: https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/]) | Plus a local small LLM such as Nemotron 3 Nano 4-bit, which alone needs about 24 GB [verified, vendor: Daily post] | 508 ms server-side P50, ~760 ms audible, as measured by Daily with a different stack [verified, vendor] |

**Layout:** Windows native `jorah-voice` service (Pipecat, wake, audio), with a browser or Pipecat client for AEC. Gateway stays in WSL2 or on Linux per the infrastructure track. Mac remains a Talk client over Tailscale. When both hear the wake word, keep the higher confidence device and drop the other within about 300 ms [inference].

---

## 16. Step-by-step plan

Evidence tiers per step: **Source** (docs read), **Install**, **Launch**, **Device acceptance** (real voice, signed in). Every config change is previewed for an explicit yes, and nothing runs on a schedule.

### V0: prove the loop (half a day)

| # | Step | Needs Adam | Acceptance |
|---|---|---|---|
| 0.1 | Adam confirms the pronunciation, and whether Slovak speech matters in V1 | Answer | Noted in `docs/` |
| 0.2 | Install the OpenClaw macOS app at the pinned version (`OpenClaw-2026.10.9.dmg` is on the GitHub release [measured: GitHub API]), pair it to the `jorah` Gateway, grant Mic and Speech | Yes, and native prompts | **Launch:** app shows connected; node visible |
| 0.3 | Preview and set triggers via `voicewake.set`: `jorah`, `hey jorah`, `jora`, `hey jora` | Yes | **Source:** `voicewake.get` returns them; test with the Mac mic panel |
| 0.4 | Set `speechLocale: en-US`, Talk provider `mlx` and enable "wake starts Talk Mode". Adam then says "Jorah", waits for the chime and speaks; words in the same breath are dropped | Yes | **Launch:** overlay moves through Listening, Thinking, Speaking |
| 0.5 | Headset test: 20 attempts at each phrase at 1 m and quiet | Adam speaks | **Device:** count hits; log what Apple heard; time first audio on a recording |
| 0.6 | 4 hours of ordinary audio with Voice Wake on, logging false fires | Adam present | **Device:** false accepts per hour recorded; compare with section 3.4 |
| 0.7 | Measure power on and off using `powermetrics` | Password | Under 1 W added |

**Exit:** the loop works and we have real numbers for Apple's hit rate on "Jorah". If under 80%, bring `livekit-wakeword` forward.

### V1: real-time feel (2 to 3 days)

| # | Step | Needs Adam | Acceptance |
|---|---|---|---|
| 1.1 | Get an OpenAI Platform API key, plus a paid Gemini API key for the bake-off (Google's free tier uses content for product improvement, and its terms require age 18+ [verified]). Set low budget alerts | Account, keys, yes | Keys stored per the secrets approach; alerts visible |
| 1.2 | Read `talk.catalog` and confirm both providers show `gateway-relay` and `agent-consult` readiness. Shipped code says they should | None | **Source:** catalog output saved. If one is absent, drop it from the bake-off |
| 1.3 | Preview and apply the config below. Enable "Use realtime Gateway relay" on the Mac | Yes | **Launch:** overlay shows relay, not fallback |
| 1.4 | First conversations with a headset. Log time to first audio from a recording, 30 turns | Adam speaks | **Device:** P50 at most 800 ms, P90 at most 1,200 ms |
| 1.5 | Consult test: 10 tasks needing Claude. Include status, steer, cancel and a long task that outlives the call | Adam speaks | **Device:** correct answers, history visible in chat, receipts truthful, no invented results |
| 1.6 | Confirmation test: "send a Telegram to myself" | Adam speaks | **Device:** gate triggers; a TV "yes" test is recorded honestly |
| 1.7 | Barge-in test: 20 interruptions | Adam speaks | **Device:** audio stops within 300 ms median; correct context afterwards |
| 1.8 | Provider bake-off (section 8) | Adam prefers | Decision recorded with numbers |
| 1.9 | Failure tests: pull network; revoke key; kill Gateway | Yes | **Device:** falls back with visible reason per docs. No silent idle |
| 1.10 | iPhone: pair, set Action Button to Start Live Voice | Yes, phone in hand | **Device:** give exact steps; result recorded; Watch later |
| 1.11 | Read one week of bills, and compare token usage per session with section 8 | Adam looks | Monthly projection against $50 |
| 1.12 | Idle test: wake, ask one question, then stay silent for 5 minutes. Read provider usage. Preview an idle-close helper for an explicit yes | Yes | **Device:** mic state and billed time recorded. No daily use until sessions close reliably |

Config to preview (shape from local docs, **not validated by running it**; key handling per security track):

```json5
{
  talk: {
    speechLocale: "en-US",
    interruptOnSpeech: true,
    provider: "mlx",                  // native fallback path
    realtime: {
      provider: "openai",             // switch to "google" for the bake-off
      providers: {
        openai: {
          model: "gpt-realtime-2.1-mini",
          speakerVoice: "<pick by ear>",
        },
        google: {
          model: "gemini-3.8-live",   // not the default 3.1 preview
          speakerVoice: "<pick by ear>",
          silenceDurationMs: 500,     // Google recommends 500 to 800
          sessionResumption: true,
          contextWindowCompression: true,
        },
      },
      mode: "realtime",
      transport: "gateway-relay",
      brain: "agent-consult",
      consultRouting: "provider-direct",
      instructions: "You are Jorah. Speak in one or two short sentences. <routing rule from section 11>",
    },
    consultThinkingLevel: "low",      // measure, then raise if answers suffer
  },
}
```

Note: the Google keys are documented under the Voice Call plugin's config [verified: `docs/providers/google.md`], and the provider's config reader takes them from a `providers.google` block [source: `normalizeProviderConfig` in `dist/extensions/google/realtime-voice-provider.js`]. Whether `talk.realtime` passes that block through unchanged was not run, so validate before applying.

### V2: Jorah's own pipeline, and the local fallback (2 to 3 weeks, in stages)

| # | Step | Acceptance |
|---|---|---|
| 2.1 | Train `jorah` with `livekit-wakeword`. Compare with a patched openWakeWord and sherpa-onnx KWS | **Source:** `eval` DET curve on real audio |
| 2.2 | Run in shadow mode for 7 days. Logs only, no actions | **Device:** section 3.4 gates |
| 2.3 | Build a stage 2 speaker check, plus a short STT check | **Device:** false accepts at most 1 per 24 h |
| 2.4 | Pipecat spike on Mac: Silero, Smart Turn, Parakeet, Kokoro, with per-stage timers | **Launch:** logs show all stages |
| 2.5 | Haiku 5.5 no-thinking test: 20 runs, cached 2K prompt, using API credits. Gate P90 first token under 500 ms. Else Gemini Flash-Lite | **Measured:** table saved |
| 2.6 | Register `jorah-voice` as a realtime provider in an OpenClaw plugin (one-day spike) | **Launch:** Talk clients use it; consult works |
| 2.7 | Offline mode: local LLM, tool allowlist, spoken "I'm offline" | **Device:** works with Wi-Fi off, and is truthful |
| 2.8 | Replace wake on the Mac with the custom model. Find a way to start Talk from an external detector | **Device:** full flow with the app or own client |
| 2.9 | Voice bake-off: Kokoro, ElevenLabs, Cartesia. Adam picks by ear | Decision recorded |
| 2.10 | Slovak test: Parakeet, `slopal` Whisper, Scribe, Soniox on 50 of Adam's real utterances. Piper against hosted | **Measured:** WER, by hand-checking 50 |

### PC and hardware (after the infrastructure track)

| # | Step | Acceptance |
|---|---|---|
| 3.1 | Collect PC specs, pick the tier | Saved in docs |
| 3.2 | Port `jorah-voice` natively to Windows. Test Parakeet or Nemotron, Kokoro with CUDA | **Measured:** per-stage timing |
| 3.3 | Buy a speakerphone if the desk path needs it. Run the test matrix | **Device:** section 10 gates |
| 3.4 | Multi-device wake arbitration with Mac | **Device:** one response only, 20 of 20 |
| 3.5 | ESP32-S3 satellite: microWakeWord `jorah`, stream to PC, ReSpeaker for far field | **Device:** 3 m tests; motors on and off |
| 3.6 | Direction of arrival to point the arm camera | Later, in the robotics track |

### UX rules for all phases [inference]

- **Sound and light:** a short rising earcon on wake; a menu-bar or orb state. A distinct state whenever audio is going to a cloud provider.
- **Follow-up window:** stay open 8 to 15 seconds after an answer, without needing the wake word, then close with a soft sound. This makes it conversational and limits cost. OpenClaw's Mac client does not do this today, so it is our work.
- **Speech style:** one or two sentences by default. Long content goes on screen or Telegram with "I sent it to you".
- **Stop words:** "stop", "cancel", "never mind" handled locally when possible.
- **Accessibility:** captions in the overlay. Everything voice can do, the keyboard can too. Push-to-talk (Right Option on Mac) remains available as a quiet alternative [verified: `docs/platforms/mac/voicewake.md`].

---

## 17. Not confirmed, and what to do about it

| Item | Status | How to settle it |
|---|---|---|
| Realtime provider latency, barge-in quality, real replay cost | No first-party measurements; cost is modelled only | V1 tests and first week's bill |
| Google relay plus agent-consult on macOS | Shipped code advertises both; no device run | Step 1.2 |
| Claude CLI turn latency over ACP, and Haiku 5.5 with no thinking | Not measured anywhere. Claude Haiku 5.5 thinking can be disabled only at effort high or below [verified: Claude API skill] | Steps 1.5 and 2.5 |
| Does Max's $100 API credit apply to this Haiku use? | Stated in the project context; not tested | First API call; read Console |
| Official OpenAI audio tokens per minute | Third-party figure only, and it now supports the V1 pick | Read real usage blocks in the bake-off |
| Idle close and wake behaviour on Mac realtime | Source search of four Mac files and Gateway code; not run. The Mac may behave differently after the 30-minute close | Step 1.12 |
| Mac relay video with Gemini | Provider flag exists; docs cover browser only | Test only if vision is needed in V1 |
| OpenAI age and region terms; AI Act Official Journal text | Not read | Legal track |
| Parakeet v3 on Adam's Slovak | Licence and FLEURS WER now confirmed; real speech untested | Step 2.10 |
| Parakeet and Nemotron on Windows; `livekit-wakeword` on Windows | Languages now confirmed; Windows runtime claims only from a changelog summary or absent | Step 3.2 |
| Pipecat `LocalAudioTransport` echo cancellation | Docs credit the browser and Daily; transport source not read | Read the source, or test with speakers |
| USB speakerphone prices in Slovakia | Alza.at about €143 from a search result; no Slovak shop price | Check Heureka.sk or Alza.sk before buying |
| Porcupine current paid pricing | Pricing page gave no content | Not needed; rejected |
| Always-on power on M1 Max | No source found | Step 0.7 |
| Slovak legal rules for recording voices; EU side-button status | Not researched or disputed | Legal track; re-check in iOS releases |
| ECAPA spoofing figures | Search snippet; exact paper not confirmed | Read the SASV papers before quoting |
| Soniox and Whisper Slovak quality on Adam's accent | Vendor claims and older models only | Step 2.10 |
| Apple Speech accuracy on the word "Jorah" | Untested | Step 0.5 |

---

## 18. Questions for Adam

1. How do you pronounce Jorah? English `/ˈdʒɔːrə/`, or Slovak-style `Džora`?
2. Do you want to speak Slovak to Jorah in the first version, or is English enough until Phase 2?
3. Are you OK spending about $30 to $50 per month on API keys for V1, or up to $91 for GPT-Live if it clearly wins? Do you have a ChatGPT plan that may unlock the `gpt-live-1-codex` route?
4. Do you want a hands-free desk setup, meaning a speakerphone at roughly €140, or is a headset fine for now?
5. Which voice? A stock British-style calm voice or an original designed voice. Not a clone of the film character.
6. Who else is in the room or home? This decides speaker enrolment, consent and how strict tier 1 must be.
7. What should happen for an unknown speaker: ignore, or answer public questions only?
8. PC specs when available: GPU and VRAM, CPU, RAM, Windows or Linux.
9. Are you 18 or older? Google's API terms require it, and OpenAI's need checking before you sign up.

---

## 19. Sources

### Local (OpenClaw 2026.10.9 bundled docs, under `/opt/homebrew/lib/node_modules/openclaw/docs/`)

`nodes/talk.md`, `nodes/talk/realtime-sessions.md`, `nodes/talk/macos-relay.md`, `nodes/talk/client-ui.md`, `nodes/voicewake.md`, `nodes/audio.md`, `platforms/mac/voicewake.md`, `platforms/mac/voice-overlay.md`, `platforms/ios.md`, `platforms/windows.md`, `providers/google.md`, `providers/fish-audio.md`, `providers/openai/voice-and-speech.md`, `tools/tts/configuration.md`, `tools/tts/quickstart.md`, `plugins/sdk-provider-plugins/voice-and-audio.md`, `plugins/architecture.md`, `channels/discord/voice-channels.md`.

### Measured on this Mac on 2026-11-02 (read-only)

- `SFSpeechRecognizer`: 62 locales, including `sk-SK` and `cs-CZ`. `supportsOnDeviceRecognition`: `en-US` true, `en-GB`, `sk-SK` and `cs-CZ` false.
- `SpeechTranscriber`: 45 supported locales, no `sk`; 9 English locales installed.
- `DictationTranscriber`: 54 locales, includes `sk-SK` and `cs-CZ`.
- `say -v '?'`: `Laura sk_SK`, `Zuzana cs_CZ`.
- Audio devices: MacBook Pro mic and speakers, iPhone Continuity mic, Teams virtual device. No speakerphone or array attached.
- No `/Applications/OpenClaw*`.
- Package versions from PyPI JSON and GitHub API: pipecat-ai 1.15.0, livekit-agents 1.8.10, openwakeword 0.6.0, livekit-wakeword 0.3.0, silero-vad 6.2.3, parakeet-mlx 0.6.0, mlx-audio 0.6.3, mlx-whisper 0.4.3, kokoro 0.9.4, kokoro-onnx 0.6.1, chatterbox-tts 0.1.7, piper-tts 1.8.0, sherpa-onnx 2.0.1, faster-whisper 1.2.1, nemo-toolkit 3.0.0, ten-vad 1.0.6.9, pyannote.audio 4.0.7, speechbrain 1.1.2.

### Web

Speech-to-speech and pricing:

- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/models/gpt-live-1
- https://developers.openai.com/api/docs/guides/live
- https://developers.openai.com/api/docs/guides/live-delegation
- https://developers.openai.com/api/docs/guides/live-conversations
- https://www.layer3labs.io/guides/openai-realtime-api-pricing
- https://aistudio.google.com/docs/pricing
- https://aistudio.google.com/docs/terms
- https://aistudio.google.com/docs/available-regions
- https://aistudio.google.com/docs/changelog
- https://aistudio.google.com/docs/models/gemini-3.8-live
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices
- https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248
- https://discuss.ai.google.dev/t/title-context-caching-or-cached-input-pricing-for-the-gemini-live-api-native-audio/186850
- https://discuss.ai.google.dev/t/gemini-3-8-live-missing-billable-token-details-and-pre-generation-spending-bounds/188765
- https://blog.google/innovation-and-ai/technology/developers-tools/build-real-time-voice-applications-gemini-audio/
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5
- https://ai.google.dev/gemini-api/docs/pricing
- https://aistudio.google.com/docs/live-api/capabilities
- https://aistudio.google.com/docs/live-api/session-management
- https://tokenkarma.app/blog/gemini-live-api-pricing-voice-agents-2026/
- https://aws.amazon.com/blogs/aws/introducing-amazon-nova-2-sonic-next-generation-speech-to-speech-model-for-conversational-ai
- https://www.techplained.com/amazon-nova-2
- https://elevenlabs.io/pricing/api
- https://elevenlabs.io/docs/overview/capabilities/text-to-speech
- https://platform.claude.com/docs/en/about-claude/pricing
- https://platform.claude.com/docs/en/api/openai-sdk
- https://platform.claude.com/cookbook/third-party-elevenlabs-low-latency-stt-claude-tts
- https://code.claude.com/docs/en/voice-dictation
- https://artificialanalysis.ai/models/claude-haiku-5-5-low/providers
- https://www.fast.io/resources/fastest-ai-2026.md

Wake word:

- https://github.com/livekit/livekit-wakeword
- https://livekit.com/blog/livekit-wakeword
- https://github.com/dscripka/openWakeWord
- https://github.com/alfiedennen/openwakeword-colab-2026
- https://community.home-assistant.io/t/colab-notebooks-to-train-your-custom-openwakeword-or-microwakeword/1026635
- https://community.home-assistant.io/t/fyi-picovoice-confirmed-free-tier-accesskeys-will-stop-working-after-june-30-2026/1012744
- https://k2-fsa.github.io/sherpa/onnx/kws
- https://esphome.io/components/micro_wake_word/
- https://github.com/MorningstarOwl/wake-word-models
- https://community.simon42.com/t/eigenes-micro-wake-word-auf-den-esp32-assist-aber-wie/54847
- https://docs.espressif.com/projects/esp-sr/en/latest/esp32/wake_word_engine/ESP_Wake_Words_Customization.html
- https://developer.apple.com/forums/thread/826681
- https://developer.apple.com/forums/thread/91872
- https://gori.me/en/apple/apple-news/167082/
- https://9to5mac.com/2025/11/17/ios-26-2-leak-shows-iphone-might-let-you-replace-siri-as-default-assistant/

VAD and turn:

- https://github.com/snakers4/silero-vad
- https://github.com/TEN-framework/ten-vad
- https://github.com/pipecat-ai/smart-turn
- https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/
- https://docs.pipecat.ai/server/utilities/turn-detection/smart-turn-overview
- https://www.ai.engineer/talks/hMlLw1LeIK8-designing-voice-agents-real-conversations

Echo and hardware:

- https://docs.rs/crate/sys-voice/latest
- https://www.forasoft.com/ship-log/spatial-audio-vpio
- https://www.seeedstudio.com/ReSpeaker-XVF3800-USB-Mic-Array-p-6488.html
- https://thepihut.com/products/respeaker-flex-xvf3800-linear-with-xiao-esp32s3
- https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/
- https://docs.pipecat.ai/client/concepts/choosing-a-transport
- https://github.com/pipecat-ai/pipecat/issues/670
- https://www.domadoo.fr/en/smart-home-hub/7558-nabu-casa-home-assistant-voice-preview-edition-0860011789727.html

STT:

- https://vllm-mlx.is-a.dev/benchmarks/audio/
- https://huggingface.co/FluidInference/parakeet-tdt-0.6b-v3-coreml
- https://build.nvidia.com/nvidia/parakeet-tdt-0_6b/modelcard
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b
- https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
- https://docs.soniox.com/stt/concepts/supported-languages
- https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/
- https://instagit.com/huggingface/speech-to-speech/live-transcription-parakeet-tdt-apple-silicon-performance/
- https://www.daily.co/blog/building-voice-agents-with-nvidia-open-models/
- https://arxiv.org/abs/2509.19270
- https://arxiv.org/html/2509.19270v1
- https://elevenlabs.io/speech-to-text/slovak
- https://soniox.com/pricing
- https://soniox.com/speech-to-text/slovak
- https://developers.deepgram.com/docs/models-languages-overview
- https://docs.mistral.ai/capabilities/audio_transcription
- https://arxiv.org/pdf/2602.11298

TTS:

- https://github.com/hexgrad/kokoro
- https://github.com/resemble-ai/chatterbox
- https://picovoice.ai/blog/on-device-tts/
- https://huggingface.co/rhasspy/piper-voices/raw/refs%2Fpr%2F15/sk/sk_SK/lili/medium/MODEL_CARD
- https://docs.cartesia.ai/build-with-cartesia/tts-models/latest
- https://docs.cartesia.ai/pricing
- https://elevenlabs.io/docs/help-center/product/voices/voice-cloning/are-there-any-restrictions-on-what-voices-i-can-upload-for-voice-cloning
- https://conductatlas.com/platform/elevenlabs/elevenlabs-usage-policy/non-consensual-voice-cloning-prohibition/

Orchestration:

- https://github.com/pipecat-ai/pipecat
- https://github.com/kwindla/macos-local-voice-agents
- https://github.com/soniqo/speech-swift
- https://community.livekit.io/t/roadmap-for-adaptive-interruption-handling-in-self-hosted-livekit-workers/1172
- https://www.usagepricing.com/blueprint/activity/livekit-2026-10-23-self-hosted-turn-detection-fees

Security and law:

- https://arxiv.org/abs/2601.02914
- https://artificialintelligenceact.eu/article/50/
- https://gdpr-info.eu/art-2-gdpr/
- https://gdpr-info.eu/art-9-gdpr/
- https://www.winstontaylor.com/insights/ai-act-rules-on-high-risk-ai-delayed-as-ai-digital-omnibus-agreed
- https://cms.law/en/gbr/publication/the-eu-s-digital-omnibus-streamlined-ai-act-compliance-rules-are-now-in-force

OpenClaw source read at tag v2026.10.9 (`dist/` is the installed package; Swift files are on GitHub under `apps/`):

- `dist/extensions/google/realtime-voice-provider.js`, `dist/realtime-voice-model-contract-*.mjs`, `dist/handlers-*.mjs`
- `apps/macos/Sources/OpenClaw/VoiceWakeRuntime.swift`, `TalkModeRuntime.swift`, `TalkModeRuntime+Realtime.swift`, `TalkModeController.swift`
- `apps/shared/OpenClawKit/Sources/OpenClawKit/RealtimeTalkRelaySession.swift`

---

## 20. Verification

Independent check on 2026-11-02. I opened each source myself rather than trusting this file's links. No account, key or config was touched, and no gateway was started. Nothing here was tried with real audio or on a device, so these are source and vendor-page checks only.

### Does the recommendation still hold?

**Partly.** The three-step shape (V0 OpenClaw native, V1 OpenClaw realtime, V2 own pipeline) holds. **The V1 provider pick did not:** Gemini 3.8 Live was chosen as cheapest, and that fails once per-turn context billing is counted. I changed the pick to `gpt-realtime-2.1-mini`, with Gemini as runner-up and the bake-off kept. This new pick rests partly on a third-party tokens-per-minute figure, so it is a starting order, not a proven result. Also new: V1 needs an idle close before daily use, whichever provider wins.

### Changed

| # | Claim in the first draft | Finding | Evidence |
|---|---|---|---|
| 1 | Gemini V1 costs $22, plan up to $45 | **Wrong.** Every turn bills all context, with no caching. Modelled $38 to $51 in short sessions, ~$163 left open | Google best-practices page, model page, forum replies, my arithmetic |
| 2 | Gemini is the cheapest speech-to-speech | **No longer holds** in any modelled pattern if OpenAI's cached rate applies | Same, plus OpenAI pricing page |
| 3 | Wake and session gating limit cost, assumed available | Mac sources show no idle close; relay closes at 30 minutes | `handlers-*.mjs`, Mac Swift sources |
| 4 | Wake then Talk reads like one flow | With "wake starts Talk Mode", words after the phrase are not forwarded | `VoiceWakeRuntime.swift` |
| 5 | Gemini stop caveat applied generally | Plain `gemini-3.8-live` has no client stop; `handleBargeIn` returns early | `docs/providers/google.md`, provider code |
| 6 | Continuous camera is a V1 reason on Mac | Documented for browser Video Talk only | `docs/nodes/talk/realtime-sessions.md` |
| 7 | `talk.catalog` for Google is the first unknown | Largely settled at source level: `gateway-relay` and `agent-consult` are advertised | Provider code, `buildTalkCatalog` |
| 8 | Custom relay provider reaches Mac, iPhone and Watch | Watch needs `webrtc` with `gateway-control-v1` | `docs/platforms/ios.md` |
| 9 | Neutral receipt and 16-entry history apply to V1 | Documented for GPT-Live native paths | `docs/nodes/talk/realtime-sessions.md` |
| 10 | Parakeet licence and Slovak WER unknown | CC-BY-4.0, 8.82% on FLEURS. Now the first local Slovak candidate | NVIDIA Hugging Face card |
| 11 | Nemotron is the NVIDIA PC candidate, languages unknown | English only; multilingual model is 21% to 25% on Slovak | Two NVIDIA cards |
| 12 | Ideal PC: 16 to 24 GB VRAM, such as RTX 5090 | RTX 5090 has 32 GB; Nemotron 3 Nano Q4 alone needs about 24 GB | NVIDIA page, Daily post |
| 13 | Compatibility layer "strips" audio input | Returns a 400 error | Claude docs |
| 14 | Silence setting of 400 ms in the config | Below Google's 500 to 800 ms; changed to 500 | Capabilities page |
| 15 | Art. 50(2) delay "reported" | Omnibus published and in force; no grace for later launches | CMS summary, search summaries |
| 16 | No mention of Google's terms | Added 18+ and EEA paid-only rules | Google terms |
| 17 | Haiku no-thinking plan had no output risk | Added Anthropic's warning on reasoning-like text in replies | Claude docs |
| 18 | Speakerphone €100 to €200 | Narrowed to about €143 at Alza.at; Slovak price still open | Search result only |
| 19 | Hosted STT list | Added Gemini 3.5 Transcribe Live; Soniox Slovak upgraded to docs | Google pages, Soniox docs |

### Checked, no change needed

- Gemini per-minute rates, Slovak `sk`, 1 fps video, 500 to 800 ms VAD, session limits, resumption window. The 3.1 preview default and its synchronous function calling are also correct.
- OpenAI rates for `gpt-realtime-2.1`, its mini, `gpt-realtime-whisper` and `gpt-4o-mini-tts`; GPT-Live-1 at $0.05/min, billed per second.
- Haiku 5.5 at $0.10, $0.01 cached and $0.50; thinking can be disabled at low, medium or high.
- ElevenLabs $0.04 per 1K, Scribe v2 Realtime $0.39/h, Realtime v1 at $0.08/min; Soniox $0.12/h and about $0.70/h TTS; Deepgram Flux has no Slovak and Nova-3 does.
- ReSpeaker XVF3800 at $54.90, in stock. Smart Turn v3.2, BSD-2, no Slovak. Daily's latency tables. Cartesia `sonic-3.6` is GA with Slovak.
- Package versions and licences on PyPI today: `livekit-wakeword` 0.3.0, `pipecat-ai` 1.15.0, `silero-vad` 6.2.3, `parakeet-mlx` 0.6.0, `piper-tts` 1.8.0 (GPL-3.0-or-later). OpenClaw v2026.10.9 is the latest release, with Mac `.dmg` assets.
- `sk-SK` and `en-GB` not on-device here and `en-US` on-device, re-run with `SFSpeechRecognizer`. Voice Wake's on-device rule, 0.55 s pause and trigger limits. Native Talk waits for the whole run. Windows documents `talk.ptt.*` and `talk.speak` only. The iPhone app is on the App Store and Start Live Voice can go on the Action Button.
- vllm-mlx page does show 52.7x, 14.3x and 11.9x to 15.5x on M1 Max 64 GB. Its STT clip is synthetic and 46.7 s.
- Anthropic: no first-party realtime speech API found on search. Absence is not proof.
- ESP-SR customisation terms. GDPR Art. 2(2)(c). AI Act Art. 50 summary.

### Could not confirm

- **Porcupine's free tier end:** Only a forum post quoting Picovoice's email. No Picovoice page found. The rejection stands, because even the possibility rules it out for a personal build.
- **OpenAI tokens per minute of audio,** and how often Realtime replay hits the cache. OpenAI's cost guide URL returned 404.
- **Gemini replay costs in real bills.** Mechanism is on a Google page, while magnitude comes from a forum post and my model. Whether unspoken mic audio bills as input is also unknown, so the $0.73 base may be high.
- **Measured latency** for Gemini 3.8 Live or the mini model.
- **Mac realtime behaviour after the 30-minute close,** and whether a Mac file I did not read has an idle rule.
- **Windows** for `livekit-wakeword`, Parakeet and Nemotron. **Pipecat** `LocalAudioTransport` AEC at source level. **ReSpeaker** AEC reference path.
- **Not re-opened:** Apple forum threads and the EU side-button status, Home Assistant Voice PE price, spoofing papers, TEN VAD, Amazon Nova, LiveKit's self-hosting fees. Their labels above stand as written.
