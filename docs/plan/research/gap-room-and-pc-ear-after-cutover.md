# Gap: the room and PC ear after cutover

Date: 2026-11-02. Status: research only. Nothing here has been installed, paired, flashed or run. No Gateway setting changed. No PC exists in any test below.

**How to read the labels.** `[verified: ...]` means I read the primary source or file today. For OpenClaw's `dist/` files and for repos, that means I read the code but did not run it. `[docs-only]` means bundled docs say so and nobody has tested it on Adam's setup. `[measured]` means I ran the command on this Mac today. `[inference]` means my own reasoning or my own number.

**Limits of this pass.**

- The shared web-search budget was already used up. Both searches I tried were refused. I opened known URLs directly and read GitHub records and the pinned package. Nothing here comes from a fresh search, and two questions stay open because of it (section 8).
- The roadmap is not on disk. `M2`, `M9`, `M10` and spike `S2` as milestones appear only in the brief, apart from `S2` in `topology.md`. M-number edits below are proposals for whoever holds the roadmap.
- `dist` means `/opt/homebrew/lib/node_modules/openclaw/dist` at OpenClaw 2026.10.9, which is still npm's `latest` [measured: `npm view openclaw dist-tags`].

---

## 1. The answer

1. **No ear can deliver realtime "Hey Jorah" on the pinned stack today.** Every path needs code we write. `talk.ptt.*` is not that path, and the Voice PE adapter as shipped fails on our provider.
2. **Pick: write one small Talk client, `jorah-talk`, forked from the adapter's MIT bridge.** It runs on `talk.session.*` over `gateway-relay`, with `gpt-realtime-2.1-mini` and a Platform API key. It is not a node, needs no Hub, and uses a wake model trained on "Jorah". This is the same code `gap-voice-to-motion-path-and-local-stop.md` line 235 already expects at M17.
3. **First host: the PC, in a standard Windows user `jorah-talk`, started by an S4U boot task, with a USB speakerphone.** One unverified fact decides this: whether that task can use the mic with nobody signed in. It takes about an hour to test (spike E1). If it fails, the runner-up is the Raspberry Pi the plan already requires at M17, pulled forward.
4. **No ChatGPT plan is needed.** Voice PE is a later far-field option, no longer the room plan.
5. **The extra hop is not the latency problem.** Serve and WSL should add single-digit to low-double-digit milliseconds [inference]. The default server VAD silence window alone takes 500 ms of the 800 ms target [verified: `dist/realtime-voice-session-policy-Sq5ivQfQ.mjs`]. Voice PE's 200 ms playback prebuffer is the one hop that threatens the target. M9 and M10 must re-run the 800 ms test by ear, not assume it.

**Added cost:** €0 in software. About €140 for a speakerphone already on the plan [`voice.md`]. It is shared with the desk path, not a new line. Usage: `voice.md` models $29 to $39 per month at 1 hour per day, and sessions that open only on wake should stay at the low end [inference]. Build time about 3 to 5 evenings [inference].

---

## 2. Direct answers

| Question | Answer | Evidence |
|---|---|---|
| Does `e-jung/voice-pe-openclaw` work with API-key `gpt-realtime-2.1-mini`? | **Not as shipped. Yes after a small fork, untested.** Four blockers below | [verified: `src/bridge.mjs`, `src/audio.mjs`; `dist/realtime-voice-events-DlxISUIr.mjs`] |
| With `gemini-3.8-live`? | **Same blockers.** Google's bridge also emits one mark per audio chunk. Audio format is not a blocker: the relay fixes PCM16 24 kHz both ways, which passes the adapter's check | [verified: `dist/extensions/google/realtime-voice-provider.js` lines 543, 821; `dist/handlers-B5Rt4cMl.mjs` lines 4543 to 4545] |
| Must Adam have a ChatGPT plan for `gpt-live-1-codex`? | **No.** That route is not selected. Docs also say it falls back to a Platform key, which disagrees with the adapter README's "not interchangeable" for 2026.9.8. I did not test either | [docs-only: `nodes/talk.md`; verified: adapter README] |
| Does an own bridge need writing? | **Yes, as a fork.** `talk.session.*` already has what it needs at 2026.10.9 | [verified: `dist/handlers-B5Rt4cMl.mjs`, `docs/gateway/protocol/rpc-talk-config-and-agents.md`] |
| Where does the adapter's process run? | **A server you host.** Its own README uses a private NAS. It listens for the device and holds Gateway credentials. See section 4 | [verified: `src/server.mjs`, README] |
| Is `talk.ptt.*` turn-based native Talk? | **Yes.** The Gateway stamps its events `mode: "stt-tts"`, `transport: "managed-room"`. The iOS client runs it through its native capture path. It cannot give the realtime feel | [verified: `dist/nodes-BBBXZ_Tl.mjs` lines 504 to 531; `apps/ios/Sources/Voice/TalkModeManager.swift` at `v2026.10.9`] |
| Can `talk.ptt.*` target `voice`? | **No per-call target.** `TalkCommands.swift` defines only result payloads, and iOS uses its own `mainSessionKey`. By contrast `talk.session.create` takes `sessionKey: "agent:voice:room"` | [verified: `apps/shared/OpenClawKit/.../TalkCommands.swift`; docs-only: `nodes/talk/session-ownership.md`] |
| Can `talk.ptt.*` run on the headless node? | **No.** `talk.ptt` appears in `dist` only in command policy and event emission. There is no handler in the CLI node host | [verified: `grep -rl "talk\.ptt" dist`] |
| Can it run on Windows Hub? | **No, despite the bundled doc.** `platforms/windows.md` lists it, but the Hub source has no `talk.ptt`, `talk.speak`, `talk.session` or `talk.client`, at HEAD `2ff4d16` (2026-11-02) or at stable tag `v2026.9.8-1`. Hub's voice surface is `stt.*` and `tts.*`, turn-based | [verified: `git grep` of `openclaw/openclaw-windows-node`; `SttCapability.cs`, `TtsCapability.cs`] |
| Does Hub have wake? | **No.** The wake phrase PR #1071 closed unmerged. The follow-up to Talk Mode, #1124, closed as not planned | [verified: GitHub] |
| Modelled round trip? | **About 510 to 925 ms on the PC path, plus the provider's own time to first audio,** which has no published figure. See section 5 | [inference, with measured provider timing] |

### What blocks the adapter on our provider

All found by reading code. I did not run the adapter.

1. **Hard-coded route.** `createSession` sends `provider: 'openai', model: 'gpt-live-1-codex', voice: 'cove'` [verified: `src/bridge.mjs`]. One line to change.
2. **Marks kill the call.** GA OpenAI emits one playback mark per audio delta, and the Gateway forwards each to the client [verified: `dist/realtime-voice-events-DlxISUIr.mjs` lines 68 to 70, `dist/handlers-B5Rt4cMl.mjs` lines 4239 to 4248]. The adapter stores marks, never acknowledges them, and fails with `unacknowledged-mark-overload` at 100 [verified: `src/bridge.mjs`]. GPT-Live's bridge emits none, which is why the author never saw this [verified: no `onMark` in `dist/realtime-quicksilver-*`]. So a stock adapter pointed at mini should drop the call after about 100 deltas [inference]. The fix: call `talk.session.acknowledgeMark` once that audio has reached the speaker.
3. **One second of playback queue.** `PlaybackQueue` throws above 48,000 bytes, 1 second at 24 kHz, and the bridge then fails with `playback-overload` [verified: `src/audio.mjs`]. If GA delivers audio faster than real time, a normal answer overflows it [inference, check in E0]. The adapter paces playback itself, so a larger bound is safe.
4. **Stale barge-in position.** It sends `appendAudio` with no `timestamp`, so the Gateway's media clock stays still, and GA truncation on interruption computes from that clock [verified: `src/bridge.mjs`; `dist/realtime-voice-protocol-Ddgcp2Wm.mjs` line 159 onward, `dist/handlers-B5Rt4cMl.mjs` `sendTalkRealtimeRelayAudio`]. The model may believe Adam heard nothing, or the wrong amount [inference].

**What still fits at 2026.10.9:** `GatewayClient` is exported from `plugin-sdk/gateway-runtime.js`, `sessions.messages.subscribe` exists, and the consult run prefix the bridge matches is unchanged [verified: `dist`]. The adapter's README warning stands: the pairing with this version is unverified.

**Cheapest test of the stock adapter, if ever wanted:** public `gpt-live-1` with `marin`. It uses a Platform key and emits no marks, so only blocker 1 applies. It costs $0.05 per minute [verified: https://developers.openai.com/api/docs/models/gpt-live-1, through `voice.md`]. I would not build on it, because M2 selected mini.

---

## 3. Decision: the ear

**Pick: `jorah-talk`, on the PC, with a USB speakerphone, for M10.**

| | **PC, S4U, speakerphone (pick)** | **Pi 5, array or speakerphone (runner-up)** | **Voice PE plus fork (third)** | PC node with `talk.ptt` | Android spare phone |
|---|---|---|---|---|---|
| Realtime on mini | After fork | After fork | After fork, plus firmware | **No, turn-based** | Relay yes, but wake and Talk are separate paths [docs-only: `nodes/voicewake.md`, `platforms/android.md`] |
| Says "Jorah" on day one | Yes, via `livekit-wakeword` from `voice.md` | Yes | No. Stock words are Okay Nabu, Hey Jarvis, Hey Mycroft [verified: home-assistant.io/voice-pe]. A custom model needs firmware work, and one user reported a crash [`voice.md`] | Would need the same client | Trigger strings through on-device speech, not tested |
| Depends on a Windows session | **Unverified. Decides this.** | No | No | Hub needs a session | No |
| Extra hop latency | Lowest | Low, wired or Wi-Fi | **Adds 200 ms prebuffer plus Wi-Fi** | n/a | Wi-Fi |
| Network exposure | None new, outbound only | Own tailnet device | **LAN listener, plain `ws://` bearer token** [verified: README] | Hub | App |
| Firmware or licence burden | None | None | Patches are "not a ready-to-flash config", GPLv3 C++, possible automatic XMOS DFU [verified: `firmware/README.md`] | None | None |
| Purchase | About €140, already planned | Pi 5 4 GB €123.90 [`robotics.md`], plus the speakerphone or a $54.90 XVF3800 [`voice.md`]. Both planned for M17, so this only moves the spend earlier | €59 MSRP [verified] | €0 | €0 if owned |

**Why this pick.** It is the only option with no firmware, no new listener and the right word, and the one unknown can be settled in an hour before spending anything. The same code then moves to the Pi at M17.

**What would change it:**

- **E1 fails** (no mic or speaker with nobody signed in): move to the Pi now. Do not add autologon, because that breaks `topology.md`'s decision and the lease model.
- **PC sits in another room from where Adam talks:** move to the Pi, or use a long USB cable if the distance allows.
- **Speakerphone misses at 3 m:** add the XVF3800 array. Far field is its job.
- **E0 shows mini cannot hold the target:** the client does not change. Run `voice.md`'s bake-off, then consider `talk.client.create` with `gateway-control-v1`. That takes media direct from the client to OpenAI over WebRTC, with the Gateway keeping control and the Platform key [docs-only: `nodes/talk/realtime-sessions.md`]. It removes Serve, WSL and TCP from the audio path, but needs a WebRTC stack and is OpenAI only.

### What the fork changes

1. Omit `provider`, `model` and `voice`, so `talk.realtime` in config rules. One place to change a provider.
2. Fix blockers 2, 3 and 4 above.
3. Widen the input budget from 500 ms (24,000 bytes) to 3 s, matching the fix for #180426 in the Apple client [verified: `apps.md`]. The adapter's own comments say a 600 ms round trip overflows the old queue, and mention tailnet latency spikes.
4. Replace the device socket with local capture and playback plus the wake model. Keep the device interface behind a small seam so Voice PE stays possible.
5. Close on idle. Keep the adapter's 12-second follow-up window. That also answers `voice.md`'s open "idle close" item, and limits replay cost.
6. Send no audio before wake. Audio is held in a RAM ring of about 2 s, per `voice.md` section 3.3, and goes out only after the wake fires. Prove it with a packet capture.
7. Keep the metadata-only telemetry: `inputRttMaxMs`, `tickGapMaxMs` and queue highs. E0 and S2b use these.

The adapter's README warns that a fresh relay does not restore all voice-model context, and claims no multi-hour reliability [verified]. A relay also expires at 30 minutes [verified: `RELAY_SESSION_TTL_MS` in `dist/handlers-B5Rt4cMl.mjs`]. Wake-opened short sessions avoid most of that, and each wake starts clean.

---

## 4. Where it runs and how it is secured

**Host (PC, pick).** Standard Windows user `jorah-talk`, separate from `jorah-svc`, `jorah-desk` and `adam`. A boot and logon scheduled task with an S4U principal. OpenClaw documents S4U for the Gateway on Windows: it runs before login, stores no password, and has no Windows network credentials or access to encrypted files [docs-only: `platforms/windows.md`]. So:

- The token goes in a file with a tight NTFS ACL. DPAPI or EFS may not be available to it [inference from that doc].
- It needs only ordinary outbound sockets, so losing Windows network credentials should not matter [inference].

**Connection.** Use the Serve URL `wss://pc.<tailnet>.ts.net`, the same way in as every other client. Do not use WSL's localhost forward:

- `topology.md` already flags that a forwarded Windows connection may look like loopback to the Gateway and pair silently, and that reaching `jorah-svc`'s VM from another user is unverified.
- This also keeps token auth and TLS on the path.

`tailscale set --unattended=true` from `topology.md` is what keeps that URL reachable with nobody signed in. Check that it works from an S4U token in E1.

**Credentials.** `openclaw qr --voice-node` gives a node token plus an operator token limited to `operator.read` and `operator.talk` [docs-only: `cli/qr.md`]. Use only the operator token, since this is not a node. Confirm with `openclaw devices list` that no node role was granted. Approval stays a normal pairing, with Adam's yes.

**Authority.** A connection with those scopes gets `senderIsOwner: false` and consults limited to `safe-read-only` tools [verified: `resolveTalkAgentConsultAuthority`, `dist/handlers-B5Rt4cMl.mjs` line 693]. This is enforced in the Gateway, so it is stronger than a prompt, and it matches `security.md`'s rule that voice has no outward tools. Writes from this ear must go through the phone, as `security.md` already requires.

**Open point for the security track.** The session key is client-chosen. A stolen token could open a call on `agent:main:main` with those read-only tools, and `operator.read` itself is broad. `security.md` line 340 notes the agent-key behaviour. So treat this token as able to read private data. Send `agent:voice:room` from `jorah-talk`, keep the token off shared drives, and add a test that it reads nothing of `main`'s [inference, untested].

**Runner-up host (Pi).** Its own tailnet device with a tag. Own Linux user for `jorah-talk`, kept separate from the network-less stop process in the sibling gap, which already uses the name `jorah-ear`. This is why I named this client `jorah-talk`.

**Voice PE host, if ever used.** The ESP32 cannot join the tailnet, so the adapter must listen on the LAN [inference]. Not in `jorah-gw`: `topology.md` keeps WSL on NAT so the LAN cannot reach it, and adding `netsh portproxy` would undo that [verified: `learn.microsoft.com/en-us/windows/wsl/networking`]. Use the `jorah-talk` Windows user, bound to the IoT interface only, firewalled to the device's one address, on the IoT VLAN from `topology.md`. Plain `ws://` still carries the bearer token, so that VLAN is the only protection [verified: README].

**Coexistence with the lease model.** `jorah-talk` never needs the console. If E1 passes, `jorah-desk`'s lease and `adam`'s own use are unaffected, except that Windows' microphone privacy switch still applies to all desktop apps together [verified: Microsoft support]. Test with `adam` signed in, with `jorah-desk` leased, and with nobody.

---

## 5. The whole-loop model

**Definition,** from `voice.md` section 10: the end of Adam's speech to the first sound of the real answer in the air, measured on an audio recording.

**What I could measure.** From this Mac on Adam's network, five unauthenticated requests per host, no key sent [measured]:

| Endpoint | TCP connect (typical) | Time from TLS done to first byte (401 or front page) |
|---|---|---|
| `api.openai.com` | 12 to 15 ms, spikes to 92 | 135 to 234 ms |
| `eu.api.openai.com` | 13 ms, spike to 100 | 62 to 86 ms |
| `generativelanguage.googleapis.com` | 13 to 18 ms | 27 to 30 ms, spike to 116 (a front page, not Live) |

These are REST requests to edges, not realtime sessions. They bound the network part only and do not include model time. The Mac is not the PC. The difference between the two OpenAI hosts suggests the default route reaches further than the EU route [inference]. `eu.api.openai.com` needs a retention agreement by approval, and `gap-private-data-through-realtime-providers.md` already says do not pursue it now. So the default-route figures apply. OpenClaw does accept a `baseUrl` if that changes [verified: `dist/realtime-voice-bridge-CGOLqV8u.mjs` line 331].

**The model.** All in milliseconds. Every row except provider network is my estimate, because I found no published measurement of Serve or WSL forwarding latency [inference].

| Stage | Mac loopback (M2 baseline) | PC `jorah-talk` via Serve | Mac or iPhone on LAN via Serve (M9) | Voice PE via adapter | Phone on cellular, direct path |
|---|---|---|---|---|---|
| Capture, AEC, 20 ms framing | 30 to 70 | 30 to 70 | 30 to 70 | 30 to 70 | 30 to 70 |
| To Gateway and back: Tailscale, Serve, WSL forward | 0 to 1 | 2 to 10 | 4 to 20 | 4 to 20 plus Wi-Fi 10 to 60 | 60 to 200 |
| Server VAD silence: **tuned 300,** default 500 [verified default] | 300 to 500 | 300 to 500 | 300 to 500 | 300 to 500 | 300 to 500 |
| Provider network, round trip [measured bound] | 135 to 234 | 135 to 234 | 135 to 234 | 135 to 234 | 135 to 234 |
| **Model time to first audio** | **X, unknown** | **X** | **X** | **X** | **X** |
| Gateway frames, event loop | 2 to 10 | 2 to 10 | 2 to 10 | 2 to 10 | 2 to 10 |
| Client jitter buffer and playback | 40 to 100 | 40 to 100 | 40 to 100 | **200 prebuffer** [verified: `playback_prebuffer_ms`], plus 10 to 30 | 60 to 150 |
| **Total without X** | **507 to 915** | **509 to 924** | **511 to 934** | **691 to 1,124** | **587 to 1,164** |

**What this says.**

- **The Serve and WSL hop is small next to everything else.** The added 2 to 20 ms is under 3% of the budget [inference]. Tailscale must be direct: DERP is generally slower, and relaying is a common cause of poor performance [verified: tailscale.com/kb/1257]. Add a direct-path check to the test.
- **Silence and provider are the budget.** With the default 500 ms silence, X must be under about 90 ms even in the best case. With 300 ms silence, it must be under about 290 ms on the PC path. Neither vendor publishes X [`voice.md`]. **So P50 under 800 ms on mini is plausible only with tuning, and I expect the truthful-acknowledgement clause to matter** [inference].
- **Too short a silence clips Adam,** so `silenceDurationMs` is a bake-off setting, not a number to fix here. Start at 400 ms and move by ear.
- **Voice PE starts about 200 ms worse.** The prebuffer is likely there to prevent underruns over Wi-Fi, so cutting it has a cost [inference]. The adapter comments also report about 1.5 s to first provider partial on GPT-Live, which is author-reported, not checked [verified as a comment only].
- **First turn after wake is a separate number.** Each wake opens a session, and the adapter allows 15 s to ready and buffers speech meanwhile [verified: `readyDeadline`, `maxStartupInputBytes`]. For Voice PE it also tells the firmware to wait 700 ms after wake [verified: `wake_open_delay_ms`]. So the first reply is slower than the table. If that proves bad, keep a connected session idle with no audio appended, renewed before the 30-minute limit. It should cost little, since audio tokens bill for audio [inference]. Measure before adding.
- **TCP is the hidden risk.** All relay audio is base64 JSON over WebSocket over TCP, so one lost packet on Wi-Fi delays everything behind it [inference]. The Gateway does not rescue a slow client: its send-buffer limit is 50 MiB, far above any voice need [verified: `MAX_BUFFERED_BYTES` in `dist/server-constants-BH_EolwD.mjs`]. So the client must bound its own queues, which is why the fork keeps them.
- **#180426 stays a client matter.** It is about the Apple client's budget, not the Gateway [verified: `apps.md`], and `jorah-talk` sets its own. The iPhone still predates the fix, so `apps.md`'s T10 stands. The added Serve hop is too small to change that verdict on LAN. On cellular it could [inference].

---

## 6. Which track wins

| Contradiction | Winner | Why | Edit needed |
|---|---|---|---|
| Provider route for the room ear: M2 mini versus adapter's Codex route | **`voice.md` (M2)** | Documented Platform-key relay, cost picked on real comparison, same as the Mac path | `apps.md` and `openclaw-fit.md`: note the adapter needs the fork in section 3 |
| PC trigger: `talk.ptt.*` on Hub (`voice.md` line 35, `apps.md` lines 213 and 427, `openclaw-fit.md` lines 88 and 229) versus headless CLI node with Hub not load-bearing (`topology.md`) | **`topology.md`, and neither needs the node** | `talk.ptt` is turn-based, has no target, has no handler in the CLI host and none in Hub. `jorah-talk` is an operator client | Replace `talk.ptt.*` with `talk.session.*` in those rows. Drop the "Hub and CLI node coexistence" question from M10's concerns. Keep it only if Hub is wanted for its own sake |
| Bundled `platforms/windows.md` lists `talk.ptt.*`, Hub source has none | **The source** | Grepped at HEAD and at stable tag. `topology.md`'s row "Talk: Hub, PTT" (line 700) is out of date | Fix `topology.md` fact 6 and the feature row. Consider telling upstream. Sending anything needs Adam's yes |
| Room device: `apps.md` A6 "Voice PE first room device, the true always-on answer" versus `voice.md` "later, not a first buy" | **`voice.md`** | Word, firmware, listener and 200 ms prebuffer all weigh against it | Change A6 to third choice. Keep it as a far-field option |
| Host for the always-on client | **`topology.md`'s no-autologon rule stands** | `voice.md` called for a Windows-native service but did not say which user. An S4U task in its own user satisfies both, if E1 passes | `voice.md` PC layout: name the user. V2's `jorah-voice` can absorb this client later |
| Latency target | **`voice.md`'s 800 and 1,200 ms stand** | M9's check that wake reaches the PC brain is not enough | Add S2b to M9 and M10 below |
| Name `jorah-ear` | **Sibling gap keeps it** for the network-less stop process | Two names for two trust levels | Use `jorah-talk` for this client |

---

## 7. Tests to add

Evidence tiers stay separate. Source check, install, launch and device acceptance are different claims, and only E3 and M10's last row count as acceptance.

**E0: fork against the Mac, before any PC. About two evenings.** Needs Adam's yes, because it needs M2's API key and config change. Preview that change first. Same 30 scripted turns as `voice.md`'s bake-off, then 10 minutes continuous with a slow consult.
Pass: no `unacknowledged-mark` or `playback-overload` failures, barge-in stops within 500 ms by ear (my limit), the consult result is spoken, marks are acknowledged in order, and `operator.read` plus `operator.talk` are the only scopes in `hello`.

**E1: Windows session test. About one hour, first thing on the PC.** A throwaway program, no Jorah credentials, under an S4U boot task as `jorah-talk`. Cases: nobody signed in after a cold reboot, `adam` signed in, `jorah-desk` leased, screen locked. Each case captures 10 s of mic audio and plays a tone.
Pass: non-silent PCM and an audible tone in all four cases, three reboots running. Also reach the Serve URL from that context.
Fail: stop and go to the Pi. Do not reach for autologon.

**S2b: extend `topology.md`'s S2 with audio timing.** S2 today proves connectivity only. Keep S2 as is and add this, on the same reboot, nobody signed in. Run `appendAudio`-sized frames through the real path and log round trip P50, P90 and max for 10 minutes, once on a direct Tailscale path and once forced through DERP if possible. Record `tailscale status` showing direct.
Pass: on direct, adds under 25 ms P50 and under 75 ms P90 compared with loopback on the same machine. Those limits are mine, based on section 5. If it fails, investigate before going further. The fallback is `gateway-control-v1`.

**E2: run M2's test again, per path.** Record the room with a separate microphone and read the gap from the waveform. Paths: Mac loopback baseline, PC `jorah-talk`, Mac through Serve, iPhone on LAN through Serve. Per path, 30 turns and the same script. Report P50, P90 and worst, and separately first turn after wake.

**E3: soak. One overnight and one working day.** Wake every 30 minutes by playing a recording, plus normal use.
Pass: 20 of 20 wakes answered with the Mac asleep and the lid shut, one response only when the Mac is awake and in range (`voice.md` step 3.4), no audio on the wire before wake by packet capture, and clean recovery from a Gateway restart and a Windows reboot. No false wakes above `voice.md`'s target.

**Proposed M10 acceptance:**

| Tier | Claim | Evidence |
|---|---|---|
| Source | Fork tests pass, with marks, playback bound and timestamps covered | Test run |
| Install | `jorah-talk` installed under its user, pinned to the Gateway's version, task visible | `schtasks /Query`, version |
| Launch | Starts after reboot with nobody signed in | PID, log line, `operator` connection in `openclaw devices list` |
| **Device acceptance** | **Adam, in the room, Mac asleep: "Hey Jorah" works, E2 numbers written down, E3 passed** | Recording, table, Adam's verdict |

**Proposed M9 change:** after cutover, also run E2's "Mac through Serve" path. Compare it to the M2 baseline. M9's existing wake-reaches-PC check stays, and is not a latency claim.

**A note on version moves.** The fork imports the Gateway's SDK by file path, so it breaks silently on upgrade if not pinned. Run E0's script after any Gateway version change.

---

## 8. Not confirmed

- **Whether WASAPI capture and playback work from an S4U task with nobody signed in.** Microsoft's WASAPI and audio-session pages I opened do not cover services or session 0. Search was unavailable. E1 decides it [inference until then]. Microsoft's privacy page says desktop-app mic access is one group switch, and does not say how it applies to a service [verified: support.microsoft.com].
- **Serve and WSL forwarding latency.** No vendor figure, and Tailscale's Serve page makes no latency statement [verified: tailscale.com/kb/1242]. Section 5 is modelled until S2b runs.
- **Mini's model time to first audio.** Same for Gemini 3.8 Live. E0 measures it.
- **Whether GA actually sends audio faster than real time through this relay,** and how many deltas a normal answer takes. Blockers 2 and 3 are read from code, and only their trigger point is unknown.
- **WebSocket through Serve.** Tailscale's page does not mention WebSocket [verified: tailscale.com/kb/1242], while OpenClaw's Tailscale doc describes the Gateway's WebSocket through Serve [docs-only: `gateway/tailscale.md`]. `topology.md`'s S2 already tests this.
- **`gpt-live-1-codex` on a plain Platform key at 2026.10.9.** Not needed, not tested.
- **PC facts:** where it sits relative to where Adam talks, and whether it has a free USB port near a suitable spot. Check before buying.
- **`livekit-wakeword` accuracy for "Jorah", and on Windows.** `voice.md`'s open items stand. A bad result moves wake to `sherpa-onnx`, without changing anything else here.

---

## 9. Sources

**Pinned package, 2026.10.9.** `dist/handlers-B5Rt4cMl.mjs`, `dist/nodes-BBBXZ_Tl.mjs`, `dist/node-command-policy-I3ly1VaT.mjs`, `dist/realtime-voice-events-DlxISUIr.mjs`, `dist/realtime-voice-protocol-Ddgcp2Wm.mjs`, `dist/realtime-voice-session-policy-Sq5ivQfQ.mjs`, `dist/realtime-voice-bridge-CGOLqV8u.mjs`, `dist/extensions/google/realtime-voice-provider.js`, `dist/plugin-sdk/gateway-runtime.js`, `dist/server-constants-BH_EolwD.mjs`, `dist/client-DZgDBpiJ.mjs`. Docs: `nodes/talk.md`, `nodes/talk/realtime-sessions.md`, `nodes/talk/session-ownership.md`, `nodes/talk/macos-relay.md`, `nodes/voicewake.md`, `nodes/command-policy.md`, `nodes/node-host.md`, `platforms/windows.md`, `platforms/ios.md`, `platforms/android.md`, `gateway/protocol/rpc-talk-config-and-agents.md`, `gateway/tailscale.md`, `plugins/sdk-migration/talk.md`, `cli/qr.md`.

**GitHub.**

- [e-jung/voice-pe-openclaw](https://github.com/e-jung/voice-pe-openclaw): README, SECURITY, `src/bridge.mjs`, `src/server.mjs`, `src/audio.mjs`, `firmware/README.md`, SKILL at commit `3ea4ee3d`, 0 stars, last pushed 2026-10-07.
- [openclaw/openclaw at v2026.10.9](https://github.com/openclaw/openclaw/tree/v2026.10.9): `apps/ios/Sources/Model/NodeAppModel.swift`, `apps/ios/Sources/Voice/TalkModeManager.swift`, `apps/shared/OpenClawKit/Sources/OpenClawKit/TalkCommands.swift`, `apps/android/README.md`.
- [openclaw/openclaw-windows-node](https://github.com/openclaw/openclaw-windows-node): HEAD `2ff4d16`, tag `v2026.9.8-1`, `SttCapability.cs`, `TtsCapability.cs`, `VoiceService.cs`, [#1124](https://github.com/openclaw/openclaw-windows-node/issues/1124), [#1071](https://github.com/openclaw/openclaw-windows-node/pull/1071).

**Web.** [Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking), [WASAPI](https://learn.microsoft.com/en-us/windows/win32/coreaudio/wasapi), [audio sessions](https://learn.microsoft.com/en-us/windows/win32/coreaudio/audio-sessions), [microphone privacy](https://support.microsoft.com/en-us/windows/windows-camera-microphone-and-privacy-a83257bc-e990-d54a-d212-b5e41beba857), [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve), [Tailscale connection types](https://tailscale.com/kb/1257/connection-types), [OpenAI gpt-realtime-2.1-mini](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini), [OpenAI data residency](https://developers.openai.com/api/docs/guides/your-data), [Home Assistant Voice PE](https://www.home-assistant.io/voice-pe/).

**Sibling tracks.** `voice.md` sections 3, 5, 8, 10, 15, 16; `apps.md` sections 2.5, 4 and A6; `openclaw-fit.md`; `topology.md` sections 2, 5, 6; `security.md`; `gap-voice-to-motion-path-and-local-stop.md`; `gap-private-data-through-realtime-providers.md`.
