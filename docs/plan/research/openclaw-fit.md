# OpenClaw capability fit for Jorah

Track: OpenClaw capability fit. Researched 2026-11-02 against installed OpenClaw 2026.10.9 (8b18b55).
Research only. Nothing was installed, paired, configured or restarted.
An independent skeptic pass on 2026-11-02 corrected this file in place; section 14 lists what was checked and changed.

## How to read this file

Evidence labels:

- `[verified: X]`: checked directly at X (a local command, GitHub API, source file, vendor page).
- `[docs-only]`: stated in OpenClaw's own bundled docs, not exercised. Paths are relative to `DOCS` = `/opt/homebrew/lib/node_modules/openclaw/docs`.
- `[inference]`: my reasoning from the evidence. Treat as a hypothesis to test.
- `[secondary]`: reported by a third party; primary source not opened.
- `[unverified]`: tried to confirm and could not. Do not plan on it.

Evidence tiers matter here. No device node is paired on Adam's setup, and `/Applications/OpenClaw.app` does not exist [verified: `ls`]. So every voice, camera and companion-app line below is at most "shipped and documented". None has reached install, launch or signed-in device acceptance on Adam's hardware.

## 1. Bottom line

**Keep OpenClaw as Jorah's brain, memory, control plane and first voice surface. Do not replace it. Add small purpose-built pieces where it has real gaps.**

The most important findings:

1. **Much more ships than the current setup uses.** The Mac app is a signed download, the iPhone app is on the App Store, Voice Wake with custom triggers is real, realtime voice with tool delegation is real, Windows Hub exists, and a Wear OS companion is in the Android source and changelog (Play delivery of the watch app is [unverified]). No companion app needs to be built for an MVP.
2. **Voice is OpenClaw's weakest serious surface for this goal.** Its own scorecard grades "Voice and realtime talk" M2 Alpha and Apple Watch surfaces M1 Experimental, while the Gateway and iOS app are M4 Stable [docs-only: `maturity/scorecard.md`].
3. **There is no wake word on Windows or Linux.** Voice Wake exists only on macOS, iOS and Android [docs-only: `nodes/voicewake.md`]. Windows Hub has a hotkey instead [verified: Windows Hub README]. A preview wake PR was closed unmerged (#1071) and its follow-up proposal closed as not planned (#1124), so do not wait for upstream [verified: `openclaw-windows-node` GitHub API]. This is the largest gap for "PC always on, say Jorah". The PC needs a thin wake client, or the Mac or a room device stays the ears.
4. **"Sees" means snapshots, not vision.** Native nodes capture a photo or a clip of up to 60 s. Continuous video reaches a model only in Browser Video Talk, and only Gemini Live gets a stream, capped at 1 frame per second [docs-only: `nodes/talk/realtime-sessions.md`]. OpenClaw also deliberately has no standalone microphone command [docs-only: `nodes/camera.md`].
5. **Native Talk speaks only after the whole agent run finishes** [docs-only: `nodes/talk/macos-relay.md`, `nodes/talk.md`]. With an Opus turn running tools, that will not feel like Jarvis. Realtime Talk fixes this, but needs an OpenAI, Google or xAI credential, which the Max subscription does not cover. Google lists a free tier for Live models, but free-tier data may be used to improve its products, so it is unsuitable for personal audio [verified: https://aistudio.google.com/docs/pricing]. A ChatGPT OAuth route exists only for `gpt-live-1-codex` [docs-only: `nodes/talk.md`].
6. **Exec allowlists are not a safe boundary.** The September 2026 advisory batch alone includes several allowlist and approval bypasses (section 9). Use OS-level isolation: a container or separate host. The allowlist is only a second layer.
7. **Several defaults are dangerously open for a node you are about to pair.** Sandboxing is off by default; node hosts default to exec approval `full` with no prompts [docs-only: `nodes/node-host.md`]; the Mac app's Allow Computer Control defaults on with no per-action confirmation [docs-only: `nodes/computer-use.md`]. Harden before pairing, not after.
8. **Robotics is entirely missing, but the seams are good.** Gateway source already recognises an ESP32 device family and `openclaw qr --voice-node` issues a least-privilege credential for embedded voice clients [verified: `src/gateway/server/ws-connection/connect-device-metadata.ts`, `openclaw qr --help`]. Actuator control would be a plugin or MCP server, with safety enforced in firmware.
9. **Upgrade risk is high in volume and manageable in practice.** 17 stable-labelled releases in October 2026, 722 published advisories, and a build refuses to open a database newer than itself, so rollback needs a snapshot. Pin, snapshot, read notes, then update on a deliberate schedule.

## 2. Capability matrix

Status key:

- **A** built-in and usable now (shipped in a release, documented; not yet accepted on Adam's devices)
- **B** built-in but needs work (config, missing parts, or real limits)
- **C** plugin or skill (official or community)
- **D** missing (must be built or bought)

### 2.1 Voice and hearing

| Goal item | Status | What exists | What is missing or limiting | Evidence |
|---|---|---|---|---|
| Say "Jorah" or "Hey Jorah" on the Mac | B | Voice Wake: always-on, on-device recognizer; one global trigger list of up to 32 entries, so `jorah` and `hey jorah` can be set | App not installed. Needs macOS 26+ (this Mac has 27.0.1). Recognition accuracy for the rare word "Jorah" is unknown | [docs-only: `nodes/voicewake.md`, `platforms/mac/voicewake.md`] |
| Wake word language | B | `en-US` reports on-device recognition on this Mac; `en-GB`, `sk-SK` and `cs-CZ` do not | Passive wake refuses to start without on-device support and never falls back to network. So wake must use `en-US` here unless more assets install | [verified: `SFSpeechRecognizer` probe on this Mac, 2026-11-02] |
| Wake word on iPhone | B | Local toggle; recognized commands go to the active session | Treated as best-effort when not active. Source has an explicit background suppression reason | [docs-only: `platforms/ios.md`], [verified: `apps/ios/Sources/Voice/VoiceWakeManager.swift`] |
| Wake word on Android | B | Foreground-only, on-device | Foreground only | [docs-only: `nodes/voicewake.md`] |
| Wake word on the Windows PC | **D** | Windows Hub has Ctrl+Alt+Shift+V, local STT, spoken output | No wake word in README or repo code search | [verified: Windows Hub README; `main` tree has no wake source file; code search for "wake" hits only Cron files, a mascot test and triage notes; #1071 closed unmerged, #1124 closed not planned] |
| Wake word on Linux | **D** | Control UI Talk in a regular browser only; the shell cannot grant the mic to its WebView | No wake | [docs-only: `platforms/linux.md`] |
| Talk back and forth, Mac | A | Native Talk loop: Apple Speech, Gateway chat, `talk.speak`; overlay with Listening, Thinking, Speaking; interrupt on speech defaults on | Speaks the complete reply only after the run finishes. Apple Speech in Talk may use network services | [docs-only: `nodes/talk.md`, `nodes/talk/macos-relay.md`] |
| Wake leads straight into a conversation | B | "Trigger Talk Mode" setting | Source shows this path skips capture and turns Talk on, and the trigger path drops any words said with the wake phrase. So "Hey Jorah" (chime), then speak | [verified: `apps/macos/Sources/OpenClaw/VoiceWakeRuntime.swift`], [inference on exact feel] |
| Instant, interruptible speech with tools | B | Realtime Talk with `brain: agent-consult`: the voice model talks, the Gateway agent does tool work, spoken cancel and steer work, chat and voice share history | Needs OpenAI Platform key or ChatGPT OAuth route, or Google or xAI key. On Mac requires `mode: realtime`, `transport: gateway-relay`, `brain: agent-consult`, plus a default-off local opt-in. M2 Alpha. Several open bugs (section 3.4) | [docs-only: `nodes/talk.md`, `nodes/talk/realtime-sessions.md`] |
| Realtime voice on Claude | **D** | Claude can be the consult brain behind a realtime voice model | No Claude realtime speech provider in the docs | [docs-only: `grep` across `providers/`] |
| Hands-free room use on Mac speakers | B | Echo handling exists for turn-based providers; iPhone has voice processing | For continuous providers such as GPT-Live, the docs tell Mac users to wear headphones because the mic stays open. Google's provider declares the same `handlesInputAudioBargeIn: true` as OpenAI's, so assume Gemini Live needs headphones on a Mac too until tested | [docs-only: `nodes/talk/macos-relay.md`], [verified: installed `dist/extensions/google/realtime-voice-provider.js`], [inference on Gemini behaviour] |
| Ambient listening without a wake word | **D** | Nothing for audio. "Ambient room events" applies to group chat text, not microphones | No standalone mic command by design | [docs-only: `nodes/camera.md`, `channels/ambient-room-events.md`] |
| Slovak | B | `talk.speechLocale` passes a locale for native STT | No on-device Slovak on this Mac, so no Slovak wake. Realtime language hint is an open request (#176044) | [verified: probe; GitHub #176044], [docs-only: `nodes/talk.md`] |
| Spoken confirmation for risky actions | A | Voice-started consults need a fresh exact spoken yes before sending messages, controlling nodes, browser or computer actions, service changes, destructive shell, publishing | Good safety. Also friction: each robot move by voice would hit it. Opt-out requested in #166156 | [docs-only: `nodes/talk/realtime-sessions.md`] |
| Choosing a voice | A | ElevenLabs, MLX local on Mac (including Fish S2 Pro reference voice), system, plus voice directives | Per-agent Talk settings are an open request (#164995) | [docs-only: `nodes/talk.md`] |

### 2.2 Seeing

| Goal item | Status | What exists | Limit | Evidence |
|---|---|---|---|---|
| Photo on demand | A | `camera.snap` on iOS, Android, macOS, Linux, Windows; dangerous opt-in via `gateway.nodes.commands.allow` | iOS and Android foreground only; Mac setting defaults off | [docs-only: `nodes/camera.md`, `nodes/command-policy.md`] |
| Short video | A | `camera.clip`, up to 60 s, with audio | Mac cap about 18.75 MiB of MP4 per clip | [docs-only: `nodes/camera.md`] |
| Understanding the media | B | Media understanding summarizes inbound image, audio, video before the reply; provider selection and fallback | M2 Alpha. Video needs a capable provider key | [docs-only: `nodes/media-understanding.md`, `maturity/scorecard.md`] |
| Continuous vision while talking | B/D | Browser Video Talk only. Gemini Live: JPEG frames up to 1 fps. OpenAI: one JPEG when `describe_view` asks | No native-app path. Frames bypass the Gateway, so the agent itself does not see them | [docs-only: `nodes/talk/realtime-sessions.md`, `providers/google.md`] |
| See the screen | A | `screen.snapshot`, `screen.record`, `desktop.stream`, `computer` tool screenshots (model-only) | Mac must be unlocked for capture and input | [docs-only: `nodes/computer-use.md`, `nodes/command-policy.md`] |
| Pan and tilt a real camera | A | Mac app: `camera.ptz.status` and `camera.ptz.control` for UVC USB cameras; explicit opt-in; returns observed position | Mac only. A cheap first "body" before the arm exists | [docs-only: `nodes/camera.md`] |

### 2.3 Deployment and devices

| Goal item | Status | What exists | Limit | Evidence |
|---|---|---|---|---|
| Runs on the Mac meanwhile | A | M4 macOS Gateway host; LaunchAgent `ai.openclaw.jorah` for this profile | Adam runs it in a foreground terminal today; a service is a persistent change that needs his yes | [docs-only: `platforms/mac/bundled-gateway.md`] |
| Always-on on the PC | A/B | WSL2 Gateway M3 Beta; native Windows M2 Alpha; Windows Hub can provision an app-owned WSL distro; boot-before-login recipe | WSL needs systemd plus a boot task; WSL >= 2.6.1.0 has a noted regression workaround | [docs-only: `platforms/windows.md`, `maturity/scorecard.md`] |
| PC talks to Mac as a work machine | B | Mac as a node: `exec host=node`, node-hosted MCP and skills, optional hosted sessions, file transfer, `desktop.stream` | Claude Code through ACP cannot run on a paired device (ACPX routes cannot dispatch to one). See section 4 | [docs-only: `nodes/node-exec.md`, `nodes/node-host.md`, `nodes/session-hosting.md`] |
| iOS builds from the PC | B | `exec host=node` running `xcodebuild` on the Mac | Mac must be awake and unlocked for GUI work. Allowlist or session design needed | [docs-only: `nodes/node-exec.md`], [inference] |
| Mac companion app | A | DMG and ZIP on GitHub Releases for 2026.10.9 (arm64, x86_64, universal). Docs call the app signed; the signature itself is not checked until step 5. Menu bar, Quick Chat, WebChat, voice, node host, approvals | M3 Beta. Requires macOS 15; voice needs 26. Named-profile caveats in section 5 | [verified: GitHub release assets], [docs-only: `platforms/macos.md`] |
| iPhone companion app | A | App Store: OpenClaw, seller OpenClaw Foundation, free, version 2026.10.70, requires iOS 26.2+, rating 3.4 from 71 ratings | Requires a reachable authenticated Gateway. Background voice limited | [verified: App Store listing], [docs-only: `platforms/ios.md`] |
| Apple Watch | B | Included in the iOS app. Talk to Claw (dictation, one turn) and Talk on Watch (realtime WebRTC) | M1 Experimental. Physical wrist-down, routing and cellular behaviour unverified by the project itself. Needs a public-trust HTTPS endpoint; tailnet-only is not enough away from the phone | [docs-only: `platforms/ios.md`, `nodes/talk/client-ui.md`] |
| Android phone | A | Google Play and signed APK on selected releases; M4 Stable; rich phone commands | Adam's phone type is unconfirmed | [docs-only: `platforms/android.md`] |
| Wear OS | A/B | Companion in the Android source and changelog: phone-proxied, select session, read transcripts, text and dictated replies, realtime Talk over the Data Layer | Requires a paired Android phone holding the Gateway connection. Merged after 2026.10.9: default-assistant support (#187587, 10-30) and a fix for Talk ending at screen timeout (#187586, 10-31). The Play listing did not render, so how the watch app reaches a watch is [unverified]. Release 2026.10.9 has no Android APK asset | [docs-only: `platforms/android.md`], [verified: GitHub PRs, `apps/android/CHANGELOG.md`, `apps/android/wear/`, release asset list] |
| Windows node | B | Windows Hub: tray, chat, screen, camera, notifications, `system.run`, `talk.ptt.*`, local MCP server mode, sandbox presets | M3 Beta. Separate release train (v2026.9.8-1, 2026-10-07) | [verified: `openclaw-windows-node` release API], [docs-only: `platforms/windows.md`] |
| Smart glasses | **C/D** | Nothing official. Community Even G2 node (MIT, 1 star, last pushed 2026-07-03). Core integration closed as not planned | Would be a side project | [verified: GitHub #98227, repo API] |

### 2.4 Growth, memory and doing real work

| Goal item | Status | What exists | Limit | Evidence |
|---|---|---|---|---|
| Remember facts and preferences | A | memory-core, hybrid search, Active Memory, Memory Wiki, Dreaming (already configured) | Memory provenance controls exist; a Dreaming privilege issue was patched in September | [docs-only: `concepts/memory-provenance.md`], [verified: advisory GHSA-62qm-6fjj-6g23] |
| Remember how to do things | A/B | Skill Workshop: saves and patches learned skills, undo, archive after 30 unused days, `/learn` | Works in the foreground on Claude CLI. Background reviews need a runtime that reports its model and tool state; the docs name the embedded runner and Codex harness | [docs-only: `tools/skill-workshop.md`, `tools/self-learning.md`] |
| Evolves unattended | B | Background reviews, Learn from history, Dreaming | On the Claude CLI runtime, Jorah misses background reviews. Fix options: run them on an API-key embedded agent, or a scheduled `/learn`-style job (needs Adam's approval) | [docs-only: `tools/self-learning.md`], [inference] |
| Finds and installs tools for a task | B | `exec`, `plugins` tool, ClawHub, MCP, `mcporter` skill, sandbox `setupCommand` | Tension: the Docker sandbox defaults to `network: none`, and "download the tools" needs network. Needs a deliberate policy (section 6) | [docs-only: `gateway/sandboxing/supported-capability-matrix.md`], [inference] |
| Long autonomous jobs | A/B | Session goals, sub-agents, Swarm in Code Mode, ACP sessions, Workboard, background process, durable cron | Code Mode and Tool Search are experimental. Automation M3 Beta | [docs-only: `tools/goal.md`, `tools/swarm.md`, `tools/index.md`] |
| Edit raw video into a YouTube cut | **D** as a feature, B as a path | Nothing built in. `video_generate` creates new video and is not an editor. Playback and transcode exist. Exec plus ffmpeg (not installed) and a learned skill is the path | All the craft lives in skills to write | [docs-only: `tools/video-generation.md`, `nodes/media-playback.md`], [verified: no ffmpeg on this Mac per task brief] |
| Design in Fusion | **D** as a feature, B as a path | `computer` tool on Mac (Peekaboo or CUA). Windows and Linux via experimental `cua-computer`. Node-hosted MCP for a Fusion API bridge | On Windows the provider controls the primary display only, and rejects held keys and modifier-held click, drag and scroll. CAD navigation commonly needs those, so prefer Fusion's scripting API over clicking | [docs-only: `nodes/computer-use.md`, `nodes/mcp-and-skills.md`], [inference on CAD] |
| Present the result | A | Assistant files open in chat with Download; video plays inline on iOS and macOS; 100 MB document limit on iOS downloads | Long videos need a separate delivery path | [docs-only: `platforms/ios.md`, `nodes/media-playback.md`] |

### 2.5 Messages, mail, calendar, school, web

| Goal item | Status | What exists | Limit | Evidence |
|---|---|---|---|---|
| Telegram | A | Bundled, working for Adam, DM pairing | It is a bot, so it cannot read Adam's personal Telegram chats | [docs-only: `channels/telegram.md`], [inference] |
| WhatsApp | C | Official plugin over WhatsApp Web (Baileys), QR linking, M3 Beta | Unofficial client linked to a personal account: account risk to weigh | [docs-only: `channels/whatsapp.md`], [inference on risk] |
| iMessage | C | Official plugin via `imsg` on a signed-in Mac. From a PC Gateway, an SSH wrapper reaches the Mac | Needs Full Disk Access and Automation. Replies, tapbacks and more need private API, which means disabling SIP. Do not do that on Adam's primary Mac. BlueBubbles support removed | [docs-only: `channels/imessage.md`, `announcements/bluebubbles-imessage.md`] |
| Signal | C | Official plugin via signal-cli | M2 Alpha | [docs-only: `channels/signal.md`, `maturity/scorecard.md`] |
| SMS | C | Twilio plugin. Android node `sms.search`, `sms.send` with dangerous opt-in | Android only for phone SMS | [docs-only: `channels/sms.md`, `nodes/command-policy.md`] |
| Messenger, Instagram | **D** | Not in the channel catalog | Would need custom work | [docs-only: `channels/index.md`] |
| Email, inbound | A/C | Bundled IMAP trigger (no webhook, no send, no flag changes, no backfill) routed to a restricted reader agent. Gmail via `gog` plus Pub/Sub, which needs a public HTTPS endpoint | Treat mail as hostile; reader sandboxing is the documented pattern | [docs-only: `automation/imap.md`, `automation/cron-jobs/gmail.md`] |
| Email, send | C | `gog` and `himalaya` skills ("send via skills") | Keep behind approval | [verified: `skills/` directory], [docs-only: `start/why-openclaw/openclaw-and-hermes-agent.md`] |
| Calendar | B/C | `gog` skill for Google. iOS and Android node `calendar.events`; `calendar.add` needs opt-in | The macOS app does not declare device and personal-data commands despite the policy row | [docs-only: `nodes/device-commands.md`, `nodes/command-policy.md`] |
| EduPage | **D** | Zero mentions in docs. Community `edupage-api` Python library, now at `EdupageAPI/edupage-api` (GPL-3.0, 103 stars, pushed 2026-10-12, release 0.13.3) | Wrap in a read-only MCP or skill. GPL matters for any business version. Terms check belongs to another track | [verified: `grep` of docs, repo API] |
| Browse the web | A | Managed isolated browser, optional attach to signed-in Chrome, `web_search`, `web_fetch`, sandboxed browser, cookie import and sync | M3 Beta. Attaching to the real profile widens blast radius | [docs-only: `tools/browser.md`, `platforms/macos.md`] |

### 2.6 Robotics

| Goal item | Status | What exists | Limit | Evidence |
|---|---|---|---|---|
| ESP32 robot arm control | **D** | No servo, MQTT, serial or ROS support in the docs; `grep` for esp32, mqtt, ros2 and arduino finds nothing relevant. Seams: tool plugins, plugin-owned node commands with their own policy, node-hosted MCP. Maintainers say embedded devices should be clients of a Gateway, not hosts | LLM tool calls are not a control loop. Motion limits and e-stop belong in firmware and a local bridge | [docs-only: `plugins/tool-plugins.md`, `nodes/command-policy.md`, `nodes/mcp-and-skills.md`], [verified: GitHub #11676], [inference] |
| ESP32 as a voice client | B | `openclaw qr --voice-node` gives a node token plus only `operator.read` and `operator.talk`. Gateway source special-cases `esp32` | I could not find the referenced ESP32-S3 room-node firmware repository. Community Voice PE adapter (`e-jung/voice-pe-openclaw`, experimental, 0 stars; GitHub shows no SPDX licence, its README says adapter code MIT and firmware patches GPLv3) uses `talk.session.*` through a host bridge | [verified: `openclaw qr --help`, `docs/cli/qr.md`, source file, GitHub #115709, #166367] |
| Camera and mic on the arm | B/D | A USB camera on a Linux node (V4L2, FFmpeg) or Mac gives snap and clip. A UVC PTZ camera can move today | Live A/V from an ESP32 is not in OpenClaw. See LiveKit in section 7 | [docs-only: `nodes/camera.md`], [verified: LiveKit ESP32 docs] |
| Moving robot, RC vehicle, drone, plane | **D** | Same seams as the arm | Add stricter safety. Drones and planes are out of scope for this track's MVP | [inference] |
| Prior art | C | `HJN-Bot/robot-arm-mahjong`: OpenClaw, robot arm and mahjong demo (1 star, created 2026-02-25, last pushed 2026-03-02). Not reviewed in depth | A reference, not a dependency | [verified: GitHub search] |

### 2.7 Safety

| Goal item | Status | What exists | Limit | Evidence |
|---|---|---|---|---|
| Stops strangers | A | DM pairing, device pairing plus a separate command-surface approval, scopes, Tailscale Serve | Node pairing is by design operator-level remote execution on that device | [docs-only: `nodes/command-policy.md`, `gateway/security/trust-model.md`] |
| Limits what Jorah can do | B | Tool profiles, per-agent policy, `tools.exec.mode` (`deny`, `allowlist`, `ask`, `auto`, `full`), `tools.fs.workspaceOnly`, hardened baseline, `before_tool_call` hooks | Sandbox is off by default. Today `agents.defaults.sandbox.mode`, `tools.exec.mode` and `gateway.auth.mode` are all unset for profile `jorah` | [verified: `openclaw --profile jorah config get`], [docs-only: `gateway/sandboxing.md`, `tools/permission-modes.md`] |
| Isolates execution | B | Docker, Podman, SSH, OpenShell and Crabbox backends; `off`, `non-main`, `all`; containerised worker sessions on Linux and macOS node hosts | Docs call the sandbox not a perfect boundary. Gateway and native plugins stay on the host. Container isolation unsupported on Windows node hosts | [docs-only: `gateway/sandboxing.md`, `nodes/session-hosting.md`] |
| Plugin and skill safety | B | Install trust checks, ClawHub scanning | Plugins run in-process, unsandboxed. ClawHub is M2 Alpha with a real malware history (section 9) | [docs-only: `gateway/sandboxing/supported-capability-matrix.md`], [verified: Unit 42] |
| Secrets | A/B | SecretRefs, 1Password plugin, Vault plugin, `ask_user` and `secrets` tools | Needs setup | [docs-only: `gateway/secrets.md`, `plugins/onepassword.md`] |

## 3. Voice loop in depth

### 3.1 The two loops

**Native Talk** (no extra key):

1. Apple Speech transcribes. On Mac, Talk may use network services; only the passive wake path is on-device-only.
2. After `silenceTimeoutMs` (default 700 ms on macOS and Android, 900 ms on iOS) the transcript goes to the active session.
3. The agent runs to completion, the Mac app reads the complete reply from history, then `talk.speak` plays it [docs-only: `nodes/talk.md`].

Consequence: time to first word is roughly silence window + entire agent turn + TTS start. An Opus 5.5 turn with tools can be many seconds or minutes. I found no published latency numbers, so this must be measured [inference]. Native Talk is good enough for a first demo and bad for Jarvis feel.

**Realtime Talk** (`talk.realtime`):

- A realtime speech model (OpenAI GA Realtime, GPT-Live, Google Live, xAI) holds the conversation, and `openclaw_agent_consult` delegates real work to the Gateway agent.
- Finalized utterances append to the same session history, so chat and voice share context. Consult work outlives the audio connection.
- `talk.consultThinkingLevel` and `talk.consultFastMode` tune the consult run [docs-only: `nodes/talk.md`].

Exact Mac config required [docs-only: `nodes/talk/macos-relay.md`]:

```json5
{ talk: { realtime: {
    provider: "<openai|google|xai>",
    providers: { /* model, voice, key by SecretRef */ },
    mode: "realtime",
    transport: "gateway-relay",
    brain: "agent-consult",
} } }
```

Then enable **Use realtime Gateway relay** locally on that Mac. A partial config silently stays on the native path, and failures fall back to native with a visible reason. `talk.catalog` must advertise the transport and brain for that provider.

### 3.2 Which realtime provider

| Provider and model | Rough price | Fit |
|---|---|---|
| Gemini 3.8 Live or 3.1 Flash Live | Input audio $0.005/min, output audio $0.018/min, input video $0.002/min, which are token rates of $3, $12 and $1 per 1M tokens; prior context is re-billed each turn, see below [verified: https://aistudio.google.com/docs/pricing] | Cheapest for short sessions, and the only option with a continuous frame stream (browser only, 1 fps). Docs describe backend bridges, but the installed provider declares `provider-websocket` and `gateway-relay` plus `supportsVideoFrames` [verified: installed `dist/extensions/google/realtime-voice-provider.js`]. Not exercised: check `talk.catalog` on the Mac |
| GPT-Live `gpt-live-1` | $0.05/min of session, billed per second; tool and backend use extra [verified: developers.openai.com pricing] | Native full-duplex, handles interruption itself. 30-minute session limit, 8 concurrent per Gateway [docs-only]. Status table says Gateway relay implemented; iOS and Watch live verification pending |
| `gpt-realtime-2.1` | Audio $32 in, $64 out per 1M tokens [verified] | Documented default sample config; pricier per token |
| `gpt-realtime-2.1-mini` | Audio $10 in, $20 out per 1M tokens [verified] | Cheaper GA path |

Cost example, voice layer only, at 30 minutes a day [inference unless marked]:

- **GPT-Live:** about $1.50 per day, or $45 per month, flat. Tool and backend use is extra.
- **Gemini Live, base rates only:** about $0.012 per minute with speech output 40% of the time, so about $11 per month. **This is a floor, not an estimate.** The first version of this file presented it as the cost, which was wrong.
- **Why it is a floor:** each turn is charged against the full context, including past exchanges and the system instruction, and audio accumulates at about 25 tokens per second [verified: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices]. Forum replies on Google's developer forum say re-billing covers raw audio from earlier turns, that gemini-3.8-live has no context caching, and that thought tokens are billed on top. Those posters' affiliation is not stated [verified as posted: https://discuss.ai.google.dev/t/pricing-of-speech-to-speech-live-model/140340 , https://discuss.ai.google.dev/t/title-context-caching-or-cached-input-pricing-for-the-gemini-live-api-native-audio/186850 , https://discuss.ai.google.dev/t/gemini-3-8-live-missing-billable-token-details-and-pre-generation-spending-bounds/188765].
- **Gemini, 20 short sessions a day** (90 s, 3 turns each): about 90,000 re-billed tokens, adding $0.07 to $0.27 a day depending on whether re-billing uses the text or audio input rate. Total about $13 to $19 per month.
- **Gemini, one open 30-minute session with a turn every 30 s:** about 1.37M re-billed tokens, adding $1.03 to $4.12 per day. Total about $42 to $135 per month. This can exceed GPT-Live. Continuous video adds more context, so the earlier "about $13 with video" figure is withdrawn.
- OpenClaw sends `contextWindowCompression: { slidingWindow: {} }` by default with no explicit trigger [verified: installed provider source]. Whether that trims a 30-minute session is [unverified]. Google warns compression loses history.
- Consult work on the Claude CLI draws from Max limits, not these figures. Anthropic paused its announced June 2026 change, so `claude -p` and third-party app usage still draw from plan limits [verified: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan]. That could change again, and advertised limits assume ordinary individual use [verified: https://code.claude.com/docs/en/legal-and-compliance].

**Pick for bench testing: bench Gemini Live and GPT-Live side by side, on a paid tier, and read the real bill** [inference]. Keep Gemini first in the order because of the vision path, not because it is assumed cheaper. Design for short wake-started sessions either way, since that is what keeps Gemini cheap. Choose on measured time to first word, barge-in quality, consult reliability and billed cost. Google's free tier is ruled out for personal audio; the privacy track should still review paid-tier terms.

### 3.3 Wake word behaviour and the "Jorah" problem

- Triggers: `voicewake.set` via Control UI **Settings → Talk**. Normalized, up to 32 entries, 64 UTF-16 units each. Defaults `openclaw`, `claude`, `computer` should be replaced, because `claude` and `computer` will misfire in normal speech [docs-only: `nodes/voicewake.md`], [inference].
- The Mac gate requires a pause of about 0.55 s after the trigger per the docs, but source also has a text-only fallback match after 1.0 s of silence or on a final transcript. So "Hey Jorah what time is it" with no pause may fire with extra delay [verified: `VoiceWakeRuntime.swift`, `VoiceWakeRecognitionDebugSupport.swift`].
- The matcher works on Apple's transcript, not an acoustic model, so a rare name is the risk. Expect possible transcriptions such as "Jora", "Zora", "Dora", "Jura", "Georgia" [inference]. Up to 32 triggers allow adding the real misrecognitions, at the cost of false positives. A proposal in the Windows Hub repo says the same: general speech-to-text does not spell short invented names stably, and reliable always-on wake probably needs an acoustic model [verified: `openclaw-windows-node` #1124]. **Test before relying on it.**
- Trigger Talk Mode: if on, the wake skips capture and starts Talk, and any command spoken in the same breath is not forwarded [verified: source], [inference on feel].
- Forwarding goes to the active WebChat session, else main, with a machine-hint prefix [docs-only: `platforms/mac/voicewake.md`].
- While Talk or push-to-talk owns the mic, wake pauses.

**Wake acceptance test to run first** (Adam speaking, real room):

- 40 tries at 1 m and 3 m, half with music or TV in the background.
- 30 minutes of normal speech and 1 hour of TV for false positives.
- Record the actual transcripts and add variants.
- Pass proposal [inference]: at least 90% at 1 m, at least 70% at 3 m, fewer than 2 false wakes per hour.
- Fail means go to a custom keyword model (section 3.5) or a dedicated device.

### 3.4 Open Talk issues worth watching

All open as of 2026-11-02 [verified: GitHub search]:

- #190146 macOS Talk stuck in Thinking after pausing.
- #138972 realtime session becomes "Unknown Talk session" before a tool-result round trip completes.
- #167876 Talk consultations lose caller authority after setup. This matters for the security model.
- #183740 memory continuity for realtime Talk (feature).
- #186263 fallback chain for realtime providers (feature). There is none today.
- #165363 `talk.catalog` reports no `stt-tts` readiness, so local-only installs cannot enable Talk cleanly.
- #187511 and #189985 Android native Talk blocked when no realtime provider is ready.

Also note that most issues about hardware and integrations get closed by automated triage or redirected to ClawHub. Do not plan on upstream implementing Jorah's needs.

### 3.5 Filling the wake gap on the PC

Options, best first:

1. **Keep the Mac and iPhone as ears during the Mac phase.** Costs nothing. Mac app in Remote mode still runs wake against the PC Gateway later [docs-only: `platforms/macos.md`, `platforms/mac/voicewake.md`].
2. **Thin wake client on the PC.** Try sherpa-onnx keyword spotting first, then openWakeWord. On detection, invoke `talk.ptt.once` or `talk.ptt.start` on the Windows node, or open a `talk.session.*` relay session. `talk.ptt.*` is allowed by default for Talk-capable nodes [docs-only: `nodes/command-policy.md`].
   - **sherpa-onnx:** Apache-2.0, 15,686 stars, v2.0.1 on 2026-10-26 [verified: repo API]. Hermes documents it as taking any typed phrase with no training [verified: https://hermes-agent.nousresearch.com/docs/user-guide/features/wake-word]. Individual model licences and accuracy on "Jorah" are [unverified].
   - **openWakeWord:** code is Apache-2.0, but its pre-trained models are CC BY-NC-SA 4.0, so non-commercial, and "hey jorah" needs custom training from thousands of synthetic clips plus negative data. The licence of a custom model is not stated and depends on the data used [verified: https://github.com/dscripka/openWakeWord]. Last release v0.6.0 in February 2024, last push 2025-12-30 [verified: repo API]. Fine to learn with. A business version needs a licence check or a different engine.
   - The glue is untested [inference]. Size: a few days including the wake test, not the single day estimated earlier [inference].
3. **Room device** (Home Assistant Voice Preview Edition or ESP32-S3 satellite) with on-device wake, using the Voice PE adapter approach, `talk.session.*` and `--voice-node` credentials. Solves far-field mic and echo cancellation in hardware [inference]. The adapter is experimental: GitHub shows no SPDX licence, and its README says adapter code MIT, firmware patches GPLv3. One EU retailer lists Voice PE at EUR 59 including tax, on an undated page [secondary: search result for https://www.domadoo.fr/en/smart-home-hub/7558-nabu-casa-home-assistant-voice-preview-edition-0860011789727.html?domid=8 , page not opened]. "Jorah" would still need a custom wake model.
4. **Replace the loop with LiveKit or Pipecat** (section 7). Only if 1 to 3 fail or for the robot.

## 4. Topology: PC, Mac and "Mac as sandbox"

**Recommended end state** [inference]:

```
                 Tailscale (private; no public Gateway)
 Windows PC (always on)                    MacBook (when awake)
 ├─ WSL2: OpenClaw Gateway ◄────────────── OpenClaw.app in Remote mode = 1 node
 │   ├─ Claude CLI brain                     ├─ Voice Wake, Talk, camera, screen
 │   ├─ memory, skills, channels             ├─ exec host=node (xcodebuild, Simulator)
 │   └─ Docker sandbox for tools             └─ iMessage via SSH wrapper (optional)
 ├─ Windows Hub = Windows node
 │   screen, camera, talk, notifications     iPhone: app = node, approvals inbox
 ├─ wake client (custom, section 3.5)        ESP32 room / robot: --voice-node, MCP bridge
 └─ Fusion, DaVinci on the Windows desktop
```

Key facts:

- **One Gateway owns everything.** Nodes are peripherals, and channel messages land on the Gateway [docs-only: `nodes/index.md`]. Do not run two equal Gateways with shared memory. A rescue profile on the Mac is a supported separate pattern [docs-only: `gateway/multiple-gateways.md`].
- **Moving from Mac to PC is documented:** stop, back up, copy the state directory and workspace, restore, doctor [docs-only: `install/migrating.md`]. The Claude CLI login in `~/.claude-jorah` must be redone on the PC. Absolute paths and any macOS-only skills will need review [inference].
- **Mac sandbox from the PC, three routes:**
  - `exec host=node` on the Mac. Simple. Runs as the app's or node's user, subject to the node's own approvals, which default to `full` with `ask: off`. **Set these before pairing.**
  - Hosted worker sessions (`nodeHost.workerRuns.enabled`) with `isolation: "container"`. Container isolation works on macOS and Linux hosts [docs-only: `nodes/session-hosting.md`]. A container cannot run Xcode, so this does not help iOS work [inference].
  - Claude Code on the Mac. ACPX routes cannot dispatch to a paired device [docs-only: `nodes/node-host.md`]. Options: run a scripted `claude -p` through `exec host=node` with its own sandbox settings, or a second macOS user. Existing `~/work` plus Claude Code sandbox behaviour carries over in the first case [inference]. **This needs a design pass with the security track.**
- **Best hardening for the Mac as a build node** [inference]: a separate standard macOS user for the node, so the agent cannot read Adam's home at all. Note that the app-owned node runs in the signed-in GUI session. A headless `openclaw node run` under a second user is the alternative, without camera or voice in that session.
- **USB from WSL2.** USB devices are not directly visible in WSL2 without `usbipd` [inference]. Prefer Wi-Fi ESP32s or a bridge on the Windows side published as a node-hosted MCP server via Hub local MCP or a Windows CLI node.
- **Windows computer control.** `cua-computer` must run from `openclaw node run` in the interactive desktop session, and is experimental [docs-only: `nodes/computer-use.md`]. Whether this coexists cleanly with Windows Hub's node needs a test; the docs warn against two nodes on a Mac but say nothing explicit for Windows.
- **Gateway on PC requires the iPhone and Mac to reach it:** `gateway.bind` loopback plus Tailscale Serve is the recommended path [docs-only: `platforms/ios.md`, `gateway/stable-https-url.md`]. Node-role connections need token-style machine auth, since Tailscale identity headers do not authenticate nodes [docs-only: `nodes/node-host.md`].
- **PC requirements are outside this track**, but OpenClaw's own needs are modest. Idle workers cost several hundred MiB each [docs-only: `nodes/session-hosting.md`]. Check on the PC: Windows edition and build (Hub needs Windows 10 20H2+ or 11), virtualization enabled for WSL2, disk for Docker images, mic and speakers.

## 5. Companion apps: use or build

**Pick: use the official Mac and iOS apps. Build nothing now.** Runner-up: fork the MIT apps later (`apps/ios`, `apps/macos`, `apps/android`, `apps/linux`, `apps/swabble`) [verified: GitHub contents API]. It would change if Adam needs a Jarvis-branded HUD, a different iPhone wake behaviour or commercial distribution. A fork loses the hosted push relay: official App Store builds are the only ones allowed on it, so a fork needs its own relay or direct APNs [docs-only: `platforms/ios.md`]. Adam already ships iOS, so this is feasible but a real maintenance load against a daily-changing upstream.

**Mac app notes:**

- Download `OpenClaw-2026.10.9-arm64.dmg` from the 2026.10.9 release (arm64 asset exists) [verified: release API]. Match the app to the pinned Gateway.
- Named profile. The Gateway uses profile `jorah` on port 43181. The app supports named profiles through `OPENCLAW_PROFILE` and `openclaw-mac --profile jorah`, preferences suite `ai.openclaw.mac.profile.jorah`. Attach-only mode requires the listener to belong to that profile's Gateway *service* [docs-only: `platforms/mac/bundled-gateway.md`, `platforms/mac/remote.md`]. The docs also say attach-only does not permit attaching another process or profile. So Adam's foreground-terminal Gateway probably does not qualify. Expect to need a LaunchAgent for this profile. A direct remote-style connection to `ws://127.0.0.1:43181` is the untested alternative; the docs describe direct mode for LAN and tailnet URLs. **[unverified]: test first.** Updates may be unavailable while a named app profile is active [docs-only: `platforms/macos.md`]. That suits pinning, but updates become manual.
- Set `gateway.auth` before connecting. The app must pair; loopback is reachability, not identity [docs-only: `nodes/computer-use.md`].
- Turn off **Allow Computer Control** before pairing, because it defaults on. Leave Camera off (default off) until needed. Decide on Desktop sharing (default enabled) [docs-only: `platforms/macos.md`, `nodes/computer-use.md`].
- Native capability prompts default to Cancel. TCC grants need the app at a stable path [docs-only: `platforms/macos.md`, `nodes/computer-use.md`].

**iPhone notes:**

- Requires iOS 26.2 or later, so check Adam's phone [verified: listing]. `visionOS` is also listed.
- Chat, Sessions, approvals, Talk, Voice Wake, camera, location, optional Health. Offline transcript cache and an outbox of up to 50 messages for 48 hours [docs-only: `platforms/ios.md`].
- "Start Live Voice" App Shortcut can be bound to the Action Button. It still needs foreground and unlock [docs-only]. This is the best iPhone pickup gesture, better than wake.
- Local Xcode builds cannot use the hosted push relay [docs-only].

**Wear OS:** ships with the Android app and works through the phone. Google's Wear OS phone pairing is Android-only as far as I know, so it needs an Android phone [inference]. If Adam only has an iPhone, use Apple Watch instead.

## 6. Growth and self-improvement fit

What "grows by itself" needs, and where OpenClaw stands:

| Need | OpenClaw | Gap to close |
|---|---|---|
| Decide what tools a task needs | Model reasoning plus web search | None |
| Install them | `exec` with package managers on host, or a sandbox image plus `setupCommand` | Sandbox defaults block network. Policy needed: a dedicated `workshop` agent or sandbox profile with an egress allowlist proxy, and a human approval for each new tool class. Not built in as a network allowlist on Docker; `docker.network` is `none` or a named network [docs-only] |
| Do the job | Goals, sub-agents, `exec`, `computer`, MCP | Heavy media jobs need GPU access in the sandbox or on a node. Docker GPU passthrough on WSL2 needs a test [inference] |
| Record the method | Skill Workshop with history and undo | Works. On Claude CLI only via foreground and `/learn` |
| Improve unattended | Background review | Not on Claude CLI. Add embedded API-key agent, or a scheduled review with Adam's explicit yes |
| Stay safe while evolving | Announce plus undo for learned skills | Every skill change applies immediately [docs-only: `tools/skill-workshop.md`]. Adam's rule is preview and explicit yes for automation. Skills that add commands should be reviewed. Consider `skills.workshop.autonomous.mode: off` plus `/learn` for high-risk agents |
| Portable toolbelt | Skills directories, node-hosted skills | Keep learned skills in git. Back up with `openclaw backup` [docs-only: `cli/backup.md`] |

The current largest gap, Jorah's `exec` running as Adam's macOS user: `exec host=auto` resolves to `sandbox` when a sandbox runtime is active and `gateway` otherwise [docs-only: `tools/exec.md`]. CLI backends doc says managed Claude turns use OpenClaw's policy-filtered MCP tools and restricted runs keep sandbox policy inside OpenClaw [docs-only: `gateway/cli-backends.md`]. But the same doc warns that native Bash approval is argument policy and not sandboxing, and points to a paired node or the embedded runtime when sandboxed execution is required. **So whether `agents.defaults.sandbox.mode: all` fully contains `exec` under `claude-cli` is unproven. Test it with `whoami`, `ls ~` and an outbound `curl` before trusting it.**

## 7. Alternatives for the voice loop, only where OpenClaw has a gap

The gaps: no PC wake word, no native continuous vision, no room echo handling on Mac with continuous providers, no streaming TTS on the native path, no robot A/V.

| Option | Version and licence | Strength | Weakness for Jorah | Use it for |
|---|---|---|---|---|
| **LiveKit Agents** | `livekit-agents@1.8.10`, 2026-10-29; Apache-2.0; 15,059 stars [verified: GitHub API] | Voice, video and text as first-class; turn detection; Python and Node; self-hostable server [verified: docs.livekit.io]. ESP32-S3 and P4 SDK: publish 1 video and 1 audio track, subscribe 1 audio track, Opus and H.264, RPC to peripherals [verified: LiveKit ESP32 docs] | Another server and a bridge to Gateway tools and memory; two conversation owners unless carefully designed. The ESP32 SDK README says Developer Preview and not ready for production (v0.3.12, 2026-10-30) [verified: `livekit/client-sdk-esp32`] | **Runner-up now; first candidate for the robot's live A/V plane later. Re-check SDK status then** |
| **Pipecat** | v1.15.0, 2026-10-29; BSD-2-Clause; 17,005 stars [verified: GitHub API] | Modular Python pipelines; ESP32 SDK over SmallWebRTC, developed on ESP32-S3 [verified: `pipecat-ai/pipecat-esp32` README] | Same ownership problem. The ESP32 repo is MIT with 115 stars but was last pushed 2025-10-06, so it looks quiet [verified: repo API]. Python only for the server. No SFU if more participants are needed [inference] | Second choice for robot A/V. Better if a simple peer-to-peer LAN link is enough |
| **Home Assistant Assist** | Core 2026.10.4 [verified: GitHub API]; Voice Preview Edition is recommended hardware; wake words such as "Hey Jarvis" and "Hey Nabu"; ESPHome satellites; Android wake even when locked [verified: home-assistant.io] | Mature room hardware and smart-home control | Not a brain. A second assistant unless wired to OpenClaw. Custom "Jorah" model requires training | Room mic hardware and smart-home. Not the main loop |
| **Hermes Agent** | v0.22.6, 2026-11-02; MIT; 259,812 stars [verified: GitHub API] | Voice on CLI, TUI, desktop, Telegram, Discord. Wake phrase on CLI, TUI and desktop, with openWakeWord on Windows x64 and sherpa or Porcupine as options [verified: Hermes wake-word docs]. Streaming STT, sentence-by-sentence TTS, strong barge-in, local Faster-Whisper, GPT-Live on desktop [verified: Hermes voice docs] | Would mean replacing the brain and redoing memory, security and channels. OpenClaw's comparison of the two is written by OpenClaw, so discount it. That doc lists a CLI, messaging gateway and desktop app; I did not check for a phone or Mac device-node equivalent | **Reference design** for streaming TTS, barge-in and PC wake. It documents answers to the voice gaps OpenClaw leaves open, so it is the real fallback if OpenClaw voice fails the bench and thin fixes do not close it |

**Recommendation.** Do not adopt LiveKit or Pipecat for the MVP. The cheapest path is OpenClaw Talk plus a realtime provider plus a thin wake client. Adopt LiveKit when the robot needs live camera and mic streams, connected to OpenClaw by tool calls or `talk.session.*`.

What would change this: if the bench shows OpenClaw relay Talk has unfixable reliability problems (repeated "Unknown Talk session", consult failures), or time to first word above about 2 s on a good network with a realtime provider [inference threshold]. Then build the voice front end on LiveKit Agents, with OpenClaw reached through its HTTP APIs (`gateway/openresponses-http-api.md`, `gateway/tools-invoke-http-api.md`). That is roughly 1 to 2 weeks [inference]. Consider cost: LiveKit self-hosted is free software plus your compute; hosted pricing was not checked. Before committing to that build, spend half a day on Hermes voice on the PC as a comparison, because it already has wake, streaming TTS and barge-in [inference]. Its Windows behaviour is documented, not tested.

## 8. Maturity snapshot

From `DOCS/maturity/scorecard.md` [docs-only], which grades itself: overall Alpha at 68% (quality 65%, completeness 71%), with coverage unscored.

| Level | Surfaces relevant to Jorah |
|---|---|
| M4 Stable | Gateway runtime, CLI, Linux Gateway host, macOS Gateway host, iOS app, Android app |
| M3 Beta | macOS companion app, Windows via WSL2, Windows App / Node, Linux companion, Agent runtime, Plugins, Security and pairing, Browser, exec and sandbox tools, Automation, Session and memory lifecycle, Anthropic provider path, Containers, Telegram, WhatsApp, iMessage |
| M2 Alpha | **Voice and realtime talk**, Media understanding and generation, Native Windows, ClawHub, Signal, Local model providers, External apps and interoperability |
| M1 Experimental | **watchOS companion surfaces**, Voice Call channel |

No separate scorecard row exists for Wear OS. The FaceTime plugin is labelled experimental and requires reduced SIP protections: avoid it [docs-only: `plugins/facetime.md`].

## 9. Licensing, governance, cadence, breakage, security, upgrade risk

### Licence and governance

- MIT, copyright OpenClaw Foundation [verified: installed `LICENSE`, GitHub API]. Commercial use is allowed. Trademark or name rules were not checked, so **do not assume "OpenClaw" branding is free to use in a Jorah product**.
- Repo: about 393,700 stars, 82,700 forks, about 7,700 open issues and PRs combined (the API field counts both) [verified: GitHub API 2026-11-02].
- OpenClaw's docs describe an independent 501(c)(3) funded by donations, with no paid tier or token [docs-only: `start/why-openclaw/openclaw-and-hermes-agent.md`]. The founder's own post says he is joining OpenAI, that the project moves to a foundation, and that OpenAI already sponsors it; the page shows no date [verified: https://steipete.me/posts/2026/openclaw]. The 501(c)(3) status remains [unverified] without a filing. The practical risk is priorities leaning toward OpenAI voice paths [inference]; the docs show GPT-Live as the most complete voice path.
- Stated scope: microcontrollers as clients only (maintainer comment, #11676), community integrations belong on ClawHub (automated triage bot, #166367, citing `VISION.md`) [verified: GitHub].
- **Business limit from the brain's side.** Anthropic does not permit third-party developers to offer Claude.ai login in their own apps or to route requests through Free, Pro, Max or Ultra credentials for their users. Products running Claude Code need its commercial terms, and each end user signs in with their own credentials [verified: https://code.claude.com/docs/en/legal-and-compliance]. So the Max-subscription brain is a personal setup and cannot be resold as Jorah's backend.

### Release cadence

- Latest stable is 2026.10.9 (2026-10-29), which is what Adam has pinned. Latest beta is 2026.10.10-beta.5 (2026-10-30) [verified: GitHub releases].
- Stable-labelled releases: 11 in September 2026, 17 in October 2026. October's 17 are 11 mainline (2026.9.8, 9.9, 10.1 to 10.9) and 6 maintenance (2026.8.34, 8.35, 9.33 to 9.36) [verified: GitHub releases API]. The version number is a sequence, not a date.
- Channels: stable, extended-stable, beta, dev. Extended-stable is gateway-only and trails mainline (2026.9.36 is end-of-September code plus critical fixes), and it never auto-applies [verified: release notes], [docs-only: `install/development-channels.md`].
- Not every stable has Mac assets. Windows and Android APK assets are only on selected releases [verified: asset list]. Mac DMG present on all recent mainline tags; Windows Hub is on its own train.

### Breaking change history

Examples [verified: release notes; docs-only where noted]:

- 2026.10.6: requires Node 24.22.1+ or 26.12.1+. This Mac has Node 26.13.0, fine [verified: `node --version`].
- 2026.9.3: dropped Node 22, Node 25 and earlier 24 and 26 builds.
- 2026.8.1: removed OpenProse and `/prose`.
- 2026-07: Android retired its voice wake stack (#104914), then added a new foreground one (#107081) days later.
- BlueBubbles removed in favour of `imsg` [docs-only].
- `nodes.run` removed in 2026.3.31 [docs-only: `tools/exec.md`].
- Windows and Linux CUA moved from a daemon and MCP integration to an SDK [docs-only: `nodes/computer-use.md`].
- Project itself renamed Warelay, Clawdbot, Moltbot, OpenClaw [verified: `VISION.md`].
- Config policy: runtime reads the current schema only; `openclaw doctor --fix` migrates [verified: `VISION.md`].

Expect the voice surface to change often: iOS removed native settings pages in favour of Dashboard pages, and the Control UI and settings paths move [docs-only: `platforms/ios.md`, `nodes/talk/macos-relay.md` still says Settings > Voice & Talk].

### Security record

- **722 published repository advisories** through 2026-09-11: 14 critical, 249 high, 390 medium, 69 low; 39 carry a CVE field [verified: GitHub API, deduplicated]. Publication is in batches (75 on 2026-09-11; 67 on 2026-05-28; 59 on 2026-03-31). OpenClaw's docs rightly say counts are not a safety score. Large public counts reflect heavy auditing as well as bugs [inference].
- **Critical chains:** Feb to Apr 2026 pairing and scope escalation reaching node RCE (GHSA-gv46-4xfq-jv58, GHSA-4jpw-hj22-2xmc, GHSA-hf68-49fm-59cq, GHSA-fqw4-mph7-2vr8, GHSA-9hjh-fr4f-gxc4), sandbox escapes (GHSA-9p3r-hh9g-5cmg, GHSA-g5cg-8x5w-7jpm), env injection (GHSA-8rh7-6779-cjqq), plugin install path traversal (GHSA-qrq5-wjgg-rvqw). No critical published after 2026-04-16 in this data.
- **CVE-2026-25253** one-click RCE through token exfiltration from `gatewayUrl`; GHSA-g8p2-7wf7-98mq, high, 2026-02-02 [verified: GitHub advisory database]. GitHub's advisory database gives CVSS 8.8 (network, no privileges, user interaction required). The repo copy of the advisory was published 2026-01-31 [verified: GitHub API `advisories/GHSA-g8p2-7wf7-98mq`]. NVD itself did not render.
- **Directly relevant to Jorah from the 2026-09-11 batch:**
  - Exec allowlists and approvals: GHSA-9f86-pvv5-rxfw (escaped newlines), GHSA-74gc-hg2m-79p9 (reusable approvals with changed arguments), GHSA-ghpx-6xwq-2w4w (wrapper allowlists trust inner commands), GHSA-3mq7-q27j-mq7q (approvals outlive reviewed cwd).
  - Node, sandbox and browser: GHSA-9x88-f7rh-4c83, GHSA-224w-vfr9-h35c, GHSA-5m4g-88rg-69pj.
  - Skills, memory, voice: GHSA-7cp7-87pj-p32v, GHSA-62qm-6fjj-6g23, GHSA-rrxp-5mx8-mvhh.
  - iOS: GHSA-jjpc-p3xf-8g7p, GHSA-gcm4-fmcp-2f9r, GHSA-5j57-84cx-r295.
- **ClawHub malware.** Koi Security counted 341 malicious of 2,857 skills in early 2026, tracked as ClawHavoc; other counts run from about 800 to 1,184 and disagree [secondary]; the Koi post URL now redirects to a Palo Alto product page, so the primary is [unverified]. OpenClaw added VirusTotal scanning in February [secondary]. Palo Alto Unit 42 reported on 2026-06-23 five skills that scanning had not blocked, including an AMOS dropper with about 22 MB of README padding, plus TradingView skills delivering a macOS infostealer; OpenClaw banned the accounts and deleted the skills [verified: Unit 42]. **Rule for Jorah: no ClawHub skill or community plugin without reading its source and pinning a version. Prefer writing our own.**
- Latest maintenance notes in 2026.10.9 patch dependencies including an IMAP sender-spoofing fix through nodemailer, and apply `tools.fs.workspaceOnly` to Gateway-built tools [verified: installed `CHANGELOG.md`]. So staying within a few weeks of current has real security value.
- Trust model: one trust boundary per Gateway; prompt-injection-only findings are closed as no-action; session tools have Gateway-wide reach by default (`tools.sessions.visibility: all`) [docs-only: `gateway/security/trust-model.md`]. **Business implication: one Gateway per customer. Never a shared multi-tenant Gateway.**

### Upgrade risk and policy

Risks:

- A build refuses to open a database newer than itself, so a rollback after migration needs a pre-upgrade snapshot [docs-only: `start/why-openclaw/versioned-state-guarded-upgrades.md`].
- The Gateway and app protocol can mismatch; the app shows an alert naming which side to update [docs-only: `platforms/macos.md`].
- Node runtime floors move.
- Node hosts must match the Gateway's worker dialect for session hosting [docs-only: `nodes/session-hosting.md`].

**Pick: stay on the `stable` channel, pinned, with a deliberate update window.** Runner-up: `extended-stable`. It is the better long-term choice once voice settles, but it is gateway-only and trails the voice work Jorah needs. Change if a stable update breaks Jorah twice in a quarter.

Procedure for each update:

1. Read release notes and any new advisories.
2. `openclaw backup create` and verify; snapshot the workspace.
3. Update Gateway first when the release notes say so; see `nodes/pairing-and-status.md` for fleet order.
4. `openclaw doctor`, then `openclaw doctor --lint`.
5. Run a smoke script: Telegram round trip, memory search, ACP delegation, sandbox containment check, one Talk turn.
6. Update Mac app manually to the same version, and iOS when its App Store build follows.

Cadence: every 2 to 4 weeks, or within 48 hours of a critical or high advisory affecting an enabled surface [inference]. Keep auto-update off; `update.checkOnStart` is read-only for hints.

## 10. Decisions

| Decision | Pick | Why | Runner-up | What changes it | Rough cost |
|---|---|---|---|---|---|
| Core platform | Stay on OpenClaw | Fits most goals, MIT, already working, device apps ship | Hermes Agent, which already has PC wake, streaming TTS and barge-in | Voice bench failure that thin fixes cannot close | $0 |
| Companion apps | Official Mac and iOS apps | Ship today, signed, push relay included | Fork MIT source | Jarvis HUD or product needs | $0 |
| First voice MVP | Native Talk plus Voice Wake on the Mac, then realtime consult | Fastest proof; no key for step one | Build on LiveKit | Unfixable relay reliability | $0, then voice API |
| Realtime provider | Bench Gemini Live and GPT-Live on paid tiers; Gemini first for video, price decided by the real bill | No Claude realtime exists; two workable paths; Gemini re-bills context so it is not always cheaper | gpt-realtime-2.1-mini | Measured latency, barge-in, bill | At 30 min/day: GPT-Live about $45/month flat; Gemini about $13 to $19 in short sessions, up to about $135 in one long session [inference] |
| TTS on native path | MLX local on the Mac to start; ElevenLabs if quality falls short | Local, no key | ElevenLabs | Voice quality | $0 to ElevenLabs plan (not priced here) |
| PC wake word | Mac and iPhone as ears first; then thin client plus `talk.ptt.*`, trying sherpa-onnx before openWakeWord | Smallest change; sherpa needs no training and openWakeWord's stock models are non-commercial | ESP32 or Voice PE room device | Wake test results; desire for far-field | Time; about EUR 59 if Voice PE, undated listing |
| Gateway on PC | WSL2 | M3 vs native M2; containers and Linux tooling | Native Windows | WSL boot or USB pain | $0 |
| Mac as work machine | Node with `exec host=node`, separate macOS user, explicit allowlist | Real isolation, keeps Xcode | Worker sessions in containers (no Xcode) | iOS build needs | $0 |
| Live vision | Browser Video Talk with Gemini for the MVP; snapshots elsewhere | Exists today | LiveKit | Robot phase | $0.002/min video |
| Robot control | Local bridge exposed as plugin or MCP; safety in firmware | No built-in; LLM is not a control loop | Plugin-owned node commands on a custom node | Robotics track | Hardware only |
| Robot live A/V | LiveKit Agents plus ESP32-P4 or S3 SDK, later, if it has left Developer Preview or the risk is accepted | RPC plus video in one SDK | Pipecat ESP32 (repo quiet since 2025-10) | Robotics track | Self-host $0 |
| Update channel | Stable pinned, 2 to 4 week window | Voice is moving fast | extended-stable | Two breakages per quarter | Time |
| ClawHub | Off by default; read and pin everything | Malware history | Own skills only | Nothing soon | $0 |
| Personal channels | Telegram now; iMessage read-only via `imsg` without SIP changes later; WhatsApp after explicit risk yes | Least risk first | Signal | Adam's preference | $0 |

## 11. Steps for the next sessions

Every step that changes data or automation needs a preview and Adam's explicit yes. Acceptance names the evidence tier.

### Phase A: harden before anything pairs (source and config)

1. Propose and apply `gateway.auth.mode: token` with a SecretRef-held token; keep loopback bind. Accept: `openclaw security audit --deep` clean or findings listed; restart proof.
2. Propose `tools.exec.mode` and a sandbox:
   - Set `agents.defaults.sandbox.mode: all` with the Docker backend.
   - Prove containment under `claude-cli` with `whoami`, `ls ~`, `curl` from Jorah in a real turn.
   - Accept: outputs show container identity, no home access, no network. If containment does not hold under `claude-cli`, escalate to the node-based design from section 4.
3. Set `tools.sessions.visibility: agent`, `tools.agentToAgent.enabled: false` unless needed; deny `gateway`, `cron` for non-owner. Compare with `gateway/security/hardened-baseline.md`.
4. Set node exec approvals before pairing, since the default is `full` with `ask: off`.

### Phase B: Mac voice MVP (install, launch, signed-in acceptance)

5. Download the 2026.10.9 arm64 DMG (about 237 MB). Verify with `spctl -a -vv` and `codesign -dv`, and compare with GitHub's asset digest `sha256:8159c89174298c3238dac8ce1566b5dd43905f5f6f8e9a873c0222a23f219f72` [verified: release API]. Install only with Adam's yes.
6. Resolve the profile question: run with `OPENCLAW_PROFILE=jorah` and try the existing listener. The docs suggest this will be refused for a foreground process (section 5), so prepare the LaunchAgent preview for Adam beforehand. Never install one silently.
7. Before pairing: Allow Computer Control off, Camera off, Desktop sharing decided, automatic updates off.
8. Approve device pairing and then the command surface separately (`openclaw devices list`, `openclaw nodes pending`). Accept: `openclaw nodes status` shows the Mac connected.
9. Set triggers to `jorah`, `hey jorah`; remove defaults. Language `en-US`. Run the wake acceptance test from section 3.3 and record results in the repo.
10. Enable Talk native with `talk.provider` MLX or system. Measure end of speech to first audio for a one-line question, a memory question, and a tool question. Record a table. Include Haiku and Opus via `talk.agentId` or a dedicated voice agent to see the model's effect. Note shared memory implications of a second agent.
11. Install the iPhone app after confirming iOS 26.2+. Tailscale Serve for reach. Accept: chat round trip, approval prompt answered on the phone, Talk from the Action Button.

### Phase C: realtime and vision

12. Adam adds a paid-tier Google key, OpenAI key, or both, stored by SecretRef, with a provider spend cap. Check `talk.catalog`. Enable relay on the Mac and repeat the measurements. Test: barge-in, spoken cancel, a 20-minute session, tool consult with a spoken confirmation, and a Gateway restart mid-call. Use headphones first, then a speakerphone with hardware echo cancellation.
13. Browser Video Talk with Gemini Live: point the camera at an object and ask. Record `describe_view` behaviour. Compare the billed cost for a short and a long session with section 3.2.
14. Decide the provider from data. Update this doc.

### Phase D: connectors

15. IMAP reader agent with sandbox and `minimal` tools for Adam's mail. Preview the config first.
16. `gog` skill for Google Calendar read-only; approval on writes.
17. EduPage read-only MCP using `edupage-api` in a sandbox with a credential by SecretRef. Check school terms first.
18. iMessage read-only path on the Mac. No SIP changes.

### Phase E: PC move

19. Inspect the PC: Windows build, virtualization, GPU, mic, Docker.
20. Install WSL2, Gateway at the same pinned version, Windows Hub. Copy state by the documented migration after backup. Re-login Claude CLI in a separate config. Boot-before-login recipe. Accept: reboot with no login, Telegram answers.
21. Switch the Mac app to Remote mode. Accept: wake on Mac reaches the PC brain.
22. Mac as a build node under a separate user, allowlist `xcodebuild` and friends, test an iOS build from Telegram.
23. Thin wake client on the PC. Accept with the same test as step 9.
24. `cua-computer` for one low-risk Windows app; verify coexistence with Hub.

### Phase F: growth and robotics hooks

25. Decide background learning (API-key agent or scheduled review) with Adam.
26. Create a `workshop` agent: sandbox with a controlled egress, tool install policy, `ffmpeg` video skill as the first learned capability.
27. Robot bridge: start with a UVC PTZ camera through `camera.ptz.control` as the first physical motion through the real approval flow. It proves arm-style gating with no hardware build. Then an ESP32 bridge as an MCP server per the robotics track.

## 12. What could not be confirmed

- Real wake accuracy for "Jorah", and actual latency numbers for any OpenClaw voice path. No published benchmark found, and I did not run audio tests, to avoid a permission prompt on Adam's machine.
- That a Mac app in a named profile can attach to a foreground Gateway.
- That the Docker sandbox fully contains `exec` under the `claude-cli` runtime.
- That Google Live works end to end through the macOS Gateway relay. Installed source declares `gateway-relay`; the Mac doc example only shows OpenAI, and nothing was exercised.
- Whether Apple clients treat Gemini as a continuous, mic-open provider. Provider capability suggests yes; no matching Swift logic was found in a limited scan.
- Actual Gemini Live cost. Figures in section 3.2 are arithmetic from Google's rates and forum replies, not a bill.
- How the Wear OS app is delivered (Play listing did not render).
- Where the upstream ESP32-S3 room-node firmware referenced in #115709 lives.
- Trademark policy for the OpenClaw name; 501(c)(3) status from a primary filing.
- Exact ClawHub malware totals; the Koi post URL redirects away.
- Advisories published after 2026-09-11: the API returned none, though 2026.10.x notes mention security fixes. They may publish in a later batch.
- LiveKit Cloud and ElevenLabs pricing; Hermes wake accuracy and real Windows behaviour (docs read, not run).
- The web search budget for this session ran out near the end, so the OpenAI pricing fetch used the vendor page directly and no further searches were run.

## 13. Sources

Local (all paths under `/opt/homebrew/lib/node_modules/openclaw/docs/` unless absolute):

- `nodes/talk.md`, `nodes/talk/realtime-sessions.md`, `nodes/talk/macos-relay.md`, `nodes/talk/client-ui.md`, `nodes/talk/session-ownership.md`, `nodes/voicewake.md`, `nodes/camera.md`, `nodes/computer-use.md`, `nodes/node-exec.md`, `nodes/node-host.md`, `nodes/session-hosting.md`, `nodes/mcp-and-skills.md`, `nodes/command-policy.md`, `nodes/device-commands.md`, `nodes/media-understanding.md`, `nodes/media-playback.md`, `nodes/index.md`, `nodes/presence.md`
- `platforms/macos.md`, `platforms/mac/voicewake.md`, `platforms/mac/bundled-gateway.md`, `platforms/mac/remote.md`, `platforms/ios.md`, `platforms/android.md`, `platforms/windows.md`, `platforms/linux.md`, `platforms/index.md`
- `maturity/scorecard.md`, `channels/index.md`, `channels/imessage.md`, `channels/whatsapp.md`, `channels/ambient-room-events.md`, `announcements/bluebubbles-imessage.md`
- `gateway/cli-backends.md`, `gateway/sandboxing.md`, `gateway/sandboxing/supported-capability-matrix.md`, `gateway/sandboxing/what-gets-sandboxed.md`, `gateway/sandboxing/modes-scope-and-backend.md`, `gateway/openshell.md`, `gateway/multiple-gateways.md`, `gateway/security/trust-model.md`, `gateway/security/hardened-baseline.md`, `gateway/operator-scopes.md`
- `tools/exec.md`, `tools/permission-modes.md`, `tools/self-learning.md`, `tools/skill-workshop.md`, `tools/goal.md`, `tools/swarm.md`, `tools/browser.md`, `tools/index.md`
- `automation/imap.md`, `automation/cron-jobs/gmail.md`, `plugins/plugin-inventory.md`, `plugins/facetime.md`, `plugins/sdk-migration/compatibility-policy.md`, `providers/google.md`, `providers/xai.md`, `providers/anthropic.md`, `cli/qr.md`, `cli/backup.md`, `install/migrating.md`, `install/development-channels.md`, `start/why-openclaw/openclaw-and-hermes-agent.md`, `start/why-openclaw/versioned-state-guarded-upgrades.md`
- `/opt/homebrew/lib/node_modules/openclaw/LICENSE`, `/opt/homebrew/lib/node_modules/openclaw/CHANGELOG.md`, `/opt/homebrew/lib/node_modules/openclaw/skills/`
- Commands run 2026-11-02: `openclaw --version`, `openclaw qr --help`, `openclaw --profile jorah config get <non-secret paths>`, `node --version`, `ls /Applications/OpenClaw.app`, a Swift `SFSpeechRecognizer` locale probe with no audio and no authorization request.

OpenClaw on the web:

- Repo and releases: https://github.com/openclaw/openclaw , https://github.com/openclaw/openclaw/releases
- Advisories: https://github.com/openclaw/openclaw/security/advisories (queried through the GitHub API)
- Windows Hub: https://github.com/openclaw/openclaw-windows-node
- App Store: https://apps.apple.com/app/openclaw-ai-that-does-things/id6780396132
- VISION: https://github.com/openclaw/openclaw/blob/main/VISION.md
- Source: `apps/macos/Sources/OpenClaw/VoiceWakeRuntime.swift`, `apps/macos/Sources/OpenClaw/VoiceWakeRecognitionDebugSupport.swift`, `apps/ios/Sources/Voice/VoiceWakeManager.swift`, `src/gateway/server/ws-connection/connect-device-metadata.ts` in the repo above
- Issues and PRs (prefix https://github.com/openclaw/openclaw/issues/ or /pull/): 11676, 85984, 98227, 104914, 107081, 108781, 115709, 130139, 134798, 138972, 164995, 165363, 166156, 166367, 167876, 176044, 183740, 186263, 187511, 187586, 187587, 189985, 190146
- Advisory lookup for CVE-2026-25253: https://github.com/advisories?query=CVE-2026-25253
- Unit 42 on ClawHub: https://unit42.paloaltonetworks.com/openclaw-ai-supply-chain-risk/
- Secondary on ClawHub and governance: https://insiderllm.com/guides/openclaw-clawhub-security-alert/ , https://www.esecurityplanet.com/ja/threats/hundreds-of-malicious-skills-found-in-openclaws-clawhub/ , https://thenewstack.io/openclaw-foundation-nonprofit-status/ (only the headline was retrievable on re-check) , https://www.trendingtopics.eu/opwnclaw-foundation-launches-with-openai-nvidia-microsoft-and-tencent-as-sponsors/

Community:

- https://github.com/e-jung/voice-pe-openclaw
- https://github.com/solavrc/openclaw-even-g2-node
- https://github.com/HJN-Bot/robot-arm-mahjong
- https://github.com/EdupageAPI/edupage-api (the old `ivanhrabcak/edupage-api` path redirects here)

Alternatives and pricing:

- https://github.com/livekit/agents , https://docs.livekit.io/agents/ , https://docs.livekit.io/frontends/build/hardware/esp32/ , https://github.com/livekit/client-sdk-esp32
- https://github.com/pipecat-ai/pipecat , https://github.com/pipecat-ai/pipecat-esp32
- https://www.home-assistant.io/voice_control/ , https://github.com/home-assistant/core/releases
- https://github.com/NousResearch/hermes-agent , https://hermes-agent.nousresearch.com/docs/user-guide/features/voice-mode , https://hermes-agent.nousresearch.com/docs/user-guide/features/wake-word
- https://github.com/dscripka/openWakeWord , https://github.com/k2-fsa/sherpa-onnx
- https://aistudio.google.com/docs/pricing (`ai.google.dev/gemini-api/docs/pricing` now redirects here) , https://developers.openai.com/api/docs/pricing
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan , https://code.claude.com/docs/en/legal-and-compliance
- https://steipete.me/posts/2026/openclaw
- https://github.com/openclaw/openclaw-windows-node/pull/1071 , https://github.com/openclaw/openclaw-windows-node/issues/1124

## 14. Verification

Independent skeptic pass, 2026-11-02. Each claim below was checked again from the source named, without relying on this file's links. Reading docs or source is a source check. Nothing here is install, launch or device evidence. No audio was captured, nothing was paired or installed, and only this file was edited.

**Recommendation after corrections.** The core recommendation holds: keep OpenClaw, use the official apps, add thin pieces. Three sub-recommendations changed:

1. Realtime provider: Gemini is no longer expected to be the cheapest in all cases. Bench both and read the bill.
2. PC wake client: try sherpa-onnx before openWakeWord, because of training effort and model licences.
3. Robot A/V: LiveKit's ESP32 SDK is a Developer Preview, so it is a candidate to re-check, not a settled pick.

Hermes is also a stronger runner-up than first written, because it documents the PC wake word that OpenClaw lacks.

**Corrected**

| # | Claim as first written | Finding | Source |
|---|---|---|---|
| 1 | Gemini Live costs about $11 per month at 30 min/day, about $13 with video | Understated. Per-minute rates ignore per-turn re-billing of context. New range about $13 to $135 | Google best-practices page, pricing page, forum replies |
| 2 | Realtime needs "a paid OpenAI or Google key" | Incomplete: xAI too, a Google free tier exists but its data may be used for product improvement, and an OAuth route exists for `gpt-live-1-codex` | `nodes/talk.md`, pricing page |
| 3 | Pricing link `ai.google.dev/gemini-api/docs/pricing` | Redirects; link updated. Prices themselves correct | WebFetch |
| 4 | openWakeWord "custom model licensing should be checked", about a day | Stock models are CC BY-NC-SA 4.0, custom training is real work, last release 2024-02. Sherpa-onnx added as first try | openWakeWord README, repo API, Hermes docs |
| 5 | LiveKit ESP32 maturity unknown | SDK README says Developer Preview, not production ready | `livekit/client-sdk-esp32` |
| 6 | Pipecat ESP32 details secondary | S3 and SmallWebRTC confirmed; repo last pushed 2025-10-06 | README, repo API |
| 7 | Hermes v0.22.5; wake and Windows unchecked | v0.22.6 today; wake word documented on CLI, TUI and desktop, openWakeWord on Windows x64 | GitHub API, Hermes docs |
| 8 | CVE-2026-25253 CVSS not confirmed | CVSS 8.8 in GitHub's advisory database | GitHub API |
| 9 | `robot-arm-mahjong` dated May 2026 | Created 2026-02-25, last pushed 2026-03-02 | GitHub API |
| 10 | `ivanhrabcak/edupage-api` | Repo now `EdupageAPI/edupage-api` | GitHub API |
| 11 | Voice PE adapter "licence unclear" | README: adapter MIT, firmware patches GPLv3 | README |
| 12 | "7,652 open issues" | The API field counts issues and PRs together | GitHub API |
| 13 | Founder and OpenAI link secondary | Confirmed by the founder's post, except the page shows no date | steipete.me |
| 14 | "Wear OS ships"; "Signed DMG" as verified | Source and changelog confirmed; delivery to a watch [unverified]. Asset exists; signature is docs-only until checked | GitHub tree and assets |
| 15 | Foreground Gateway "may not satisfy" the named profile rule | Docs are stricter than that: attach-only does not permit another process or profile | `platforms/mac/bundled-gateway.md` |
| 16 | Unit 42 "passed scanning" | Softened: not blocked at analysis time, one audit still in review | Unit 42 |

**Added**

- Windows wake history (#1071 closed unmerged, #1124 closed not planned).
- Anthropic's limit on routing plan credentials for users, which constrains the business version.
- Paused Agent SDK change, confirming consult work draws on Max limits today.
- GitHub digest for the arm64 DMG.

**Checked and held up**

- Maturity levels and overall 68% (quality 65%, completeness 71%): parsed from `maturity/scorecard.md`.
- No Windows or Linux wake word; macOS needs 26+; 32 triggers; defaults `openclaw`, `claude`, `computer`: `nodes/voicewake.md`, `platforms/linux.md`, Hub README and `main` tree.
- Speech locale probe re-run on this Mac: on-device `en-US` true; `en-GB`, `sk-SK`, `cs-CZ` false.
- Native Talk speaks only after the run completes; relay requires `mode`, `transport`, `brain` plus the local opt-in; headphones warning: `nodes/talk/macos-relay.md`.
- Vision limits: 60 s clips, about 18.75 MiB, 1 fps Google frames that bypass the Gateway, no standalone mic: `nodes/camera.md`, `nodes/talk/realtime-sessions.md`, `platforms/linux.md`.
- Dangerous defaults: node exec `full` with `ask: off`, Allow Computer Control on with no per-action confirmation, sandbox off, Docker `network: none`: `nodes/node-host.md`, `nodes/computer-use.md`, `gateway/sandboxing.md`, capability matrix.
- ACPX routes cannot dispatch to a paired device: `nodes/node-host.md`.
- Native Bash approval is not sandboxing under Claude CLI, so containment stays a test item: `gateway/cli-backends.md`.
- Background reviews need a runtime reporting model and tool state: `tools/self-learning.md`.
- Prices for `gpt-live-1`, `gpt-realtime-2.1` and mini: OpenAI pricing page. Gemini per-minute and token rates: Google pricing page.
- App Store: seller, free, 2026.10.70, iOS 26.2+, 3.4 from 71 ratings, re-fetched. The listing also requires watchOS 11 for the Watch.
- Release counts (11 in September, 17 in October), latest stable and beta, npm tags, arm64 DMG on sampled tags, `gateway-only` wording on 2026.9.36: GitHub API, npm.
- 722 advisories with 14, 249, 390, 69 by severity, 39 with CVE, batch sizes, last critical 2026-04-16, and all cited GHSA ids: GitHub API.
- All listed Talk issues still open; #98227, #11676, #166367 closed not planned; Wear and Android PRs merged on the stated dates: GitHub API.
- `openclaw qr --voice-node`, `backup`, `doctor --lint`, `security audit --deep`, `nodes pending`: local CLI help. ESP32 family check: source at tag v2026.10.9.
- Node 24.22.1+ or 26.12.1+ (2026.10.6), Node floor change (2026.9.3), OpenProse removal (2026.8.1): release notes, `package.json`, `docs/prose.md`.
- Profile config unset values for sandbox, exec mode, auth mode; `gateway.bind` loopback: `openclaw --profile jorah config get`.
- LiveKit and Pipecat versions, Home Assistant 2026.10.4, its recommended hardware and wake words, Unit 42 date and action.
- No Anthropic realtime speech API found in Anthropic's provider docs bundled here or in a web search. This is an absence of evidence, and no official Anthropic statement was found.

**Could not confirm:** see section 12. Marked [unverified] in place where a plan could lean on it.
