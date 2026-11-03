# Gap: voice-to-motion path and local stop

Date: 2026-11-02. Status: research only. Nothing here has been installed, wired or run.

**How to read the labels.** `[verified: ...]` means I read the primary source or file today. For OpenClaw's `dist/` files that means I read the code but did not run it. `[docs-only]` means the bundled docs say so and nobody has tested it on Adam's setup. `[inference]` means my own reasoning or my own number. Every latency figure in this file is a budget to measure, not a result.

**Limits of this pass.**

- The shared web-search budget ran out on my first query. After that I opened known URLs directly and read GitHub and PyPI records for known projects. Nothing below comes from a fresh search.
- The roadmap is not on disk. `M10`, `M17`, `M20` and `M25` appear in no file under `docs/`. I rely on how the brief describes them, so M-number edits below are proposals for whoever holds the roadmap.

---

## 1. The answer

1. **Stop never passes through the Gateway or a model.** A small local process, `jorah-ear`, runs on the same Raspberry Pi as the arm's bridge. It runs microWakeWord's existing `stop` model on a ReSpeaker XVF3800 and tells the bridge over a Unix socket. If the Pi is down the arm cannot move anyway, so the stop path is never less available than the motion path.
2. **`robot` holds `robot_*`.** It is a new agent, as `security.md` defines it. `voice` and `main` get none of these tools. During an enabled session the Talk call is bound to `robot`, not `voice`.
3. **There are three kinds of permission, and each answers a different question.**
   - **Physical key:** can this arm have power at all?
   - **Phone tap, once per session:** may Jorah move it for the next 20 minutes? This is the authority.
   - **Spoken yes, per plan:** is that the right target? This is a check, not an authority.
4. **The Gateway's spoken gate does not fire on a tool named `robot_pick`.** The shipped code decides by tool name, so `robotics.md` is wrong that the gate is "good for picks". Name the one executing tool `robot_send_goal` and the gate becomes the single yes. A test must prove this at every OpenClaw upgrade.
5. **The arm hears through an array on its fixed base and sees through its wrist camera.** Both go through what Jorah already has: the Talk relay and frames. No LiveKit or Pipecat is needed for the arm, because the models take at most about 1 frame per second anyway.

**Added cost: about €0.** The Pi and the XVF3800 ($54.90 before VAT and shipping) are already planned [verified: `voice.md` section 5]. One change: the Pi stops being optional at M17, so the "about €480 to €620 if the Pi waits" figure in `robotics.md` no longer applies to voice-to-motion. Added work: about 2 to 3 days for the ear and 1 to 2 days for the guard plugin [inference].

---

## 2. Source findings that change the plan

Three things in the OpenClaw code disagree with what the tracks assumed.

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| 1 | The gate decides by tool name. An unknown tool counts as "mutating" only if its name starts with `message_`, contains `send`, or ends in `_actions`. `robot_pick`, `robot_move_named` and `robot_stop` all fall through to "not mutating" | [verified: `dist/tool-mutation-BTW6eoAN.mjs` `isMutatingToolCall`; `dist/agent-tools.before-tool-call-CQkX3nOj.mjs` `requiresHighImpactVoiceConfirmation`] | The docs' "controlling nodes" [docs-only: `nodes/talk/realtime-sessions.md`] matches the built-in `nodes` tool, not node-hosted MCP tools. This is a reading of the code, so test it (T3) |
| 2 | The gate binds to a consult's `runId`. Runs without a voice binding pass. I found registration only for Talk consult runs, so a sub-agent's run looks unbound. Native Talk also looks outside it | [verified: same file, `resolveClientVoiceRunBinding`; `dist/handlers-B5Rt4cMl.mjs`, three `registerClientVoiceConsultRun` call sites] | Delegating `voice` to `robot` puts the yes on the `sessions_send` text, not on the motion. Talk's fallback to native speech [docs-only: `nodes/talk/macos-relay.md`] would silently remove the yes |
| 3 | Node tools reach agents by default unless policy removes them. MCP tool calls have a 125 s Gateway timeout and run with `executionMode: "sequential"` | [verified: `dist/openclaw-tools-CSSYZDKR.mjs`, `dist/node-commands-Bxo-2Y4j.mjs`] | "`main` has no robot tools" needs an explicit deny. `robot_send_goal` must return at once with a job id. A model-called `robot_stop` is not a stop path |

Also relevant:

- The yes binds to the exact arguments, is used once and expires after 120 s [verified: `CONFIRMATION_TTL_MS`, `stableToolFingerprint` in the same file]. Generated text cannot supply it on native GPT-Live calls [docs-only: `nodes/talk/realtime-sessions.md`].
- The relay has no way to send images. Its methods are `create`, `appendAudio`, `cancelOutput`, `acknowledgeMark`, `steer`, `submitToolResult` and `close` [verified: `dist/handlers-B5Rt4cMl.mjs`].

---

## 3. Who holds `robot_*`

**Pick: option C, a dedicated `robot` agent, with the Talk call bound to it during an enabled session.** The Talk client opens `talk.session.create` with `sessionKey: "agent:robot:arm"`, which selects that agent [docs-only: `nodes/talk/session-ownership.md`]. `talk.agentId` stays `voice` for everything else.

| Option | Result | Verdict |
|---|---|---|
| A. `voice` holds the tools | Every room utterance at any hour can reach motion tools. Breaks "voice has no outward tools" | No |
| B. `voice` sends to `robot` with `sessions_send` | Yes on every send, including the plan, so two yeses per pick. Two model hops. The yes covers message text, not the goal | **Runner-up**, if a Talk client cannot select `robot` |
| **C. Talk bound to `robot`** | One model hop, one yes, and the gate covers the goal itself | **Pick** |
| D. `main` holds the tools | `main` reads the output of email and web readers | No |

**Configuration this implies** (each is a config change that needs Adam's yes):

- `agents.entries.robot.tools.allow` lists only `robot_*`. A deny on `robot_*` and `base_*` goes on every other agent, because node tools are visible by default [verified: `openclaw-tools-CSSYZDKR.mjs`, deny globs match the original tool name].
- `robot` has no channel binding, so Telegram cannot reach it. M17's red-team test ("a Telegram message moves nothing") then passes by absence, not by a model refusing.
- `robot` uses a fast API model on the embedded runtime. Whether tool hooks and the gate apply on the Claude CLI runtime was not confirmed, so do not depend on it [inference].
- Arm and base tools use different prefixes, or OpenClaw renames duplicates with a node prefix and the deny globs get harder to reason about [verified: same file].
- Calendar questions during a robot session get "after this session" for the MVP. Do not add a bridge to `main` yet [inference].

---

## 4. Which confirmation applies

| Action | Key on | Session tap | Spoken yes | Why |
|---|---|---|---|---|
| `robot_status`, `robot_plan_pick` | No | No | No | No motion. Planning only produces a preview and a `plan_id` |
| `robot_snapshot` | No | Row 33 rules | No | Privacy rule, not a motion rule |
| `robot_stop`, spoken stop, E-stop | No | No | No | "Always allowed, no auth" [verified: `security.md` row 46] |
| `robot_request_arm` (session enable) | Yes | **Tap** | No | The authority. 20-minute timer, `allowedDecisions: ["allow-once", "deny"]` so it can never become "always" [docs-only: `plugins/plugin-permission-requests.md`] |
| `robot_move_named`, `robot_point_at` | Yes | Yes | No | Fixed poses and a box. A yes per move teaches Adam to stop listening; Anthropic reports 93% of prompts accepted [verified: via `ux.md`] |
| `robot_send_goal(plan_id)` for pick, place or policy | Yes | Yes | **Yes** | Target check, bound to one plan by the gate |
| `base_send_goal(plan_id)` for a named place | Chassis switch | Yes, row 42 | **Yes** | Same shape. The preview is the route on the map |
| Anything from chat, email or the web | n/a | n/a | n/a | Unreachable, `robot` has no binding |

**The single-yes flow.** The agent's skill text calls `robot_plan_pick`, then calls `robot_send_goal(plan_id)` straight away in the same run. The gate blocks that call and asks for the yes. Adam says yes, and the same `plan_id` runs. Adam hears one question, and the yes covers the exact plan the bridge previewed.

The bridge's plan expires after 60 s [inference], shorter than the gate's 120 s, because the scene can change. An expired plan is refused and Jorah plans again.

**How the rule "voice never approves" survives.** Voice never arms, never enables a session, never widens a limit and never acts outside an enabled session. Inside one, a yes can be spoken by anyone in the room, including a TV. That is acceptable because everything it can trigger is a previewed plan, inside the box, at fixed speed, with the key on, Adam present and the E-stop in reach. This matches `ux.md` U8's wording: "the yes is a comprehension check, and only the tap is authority".

**What the gate does add** is protection against the model. A camera frame with text saying "move left fast" can make the model call the tool, but it cannot produce Adam's words.

**Failure rule.** If T3 shows the gate does not fire on `robot_send_goal`, `jorah-robot-guard` requires a tap on every goal through `before_tool_call.requireApproval`. Slower, but it fails safe. Never patch the gate.

**Fallback risk.** Robot sessions run only on Jorah's own Talk client, which has no native fallback. If the relay fails, speech fails and no motion request can be made. Stop keeps working.

**Preview delivery.** The guard plugin posts the annotated image to Adam, and the agent speaks one line. The `robot` agent must not use the `message` tool for this, because `message` is itself gated and would add a second yes [verified: `tool-mutation-BTW6eoAN.mjs`].

**Honest limit.** The tap passes through the Gateway, so a compromised Gateway could forge it. The key switch is then the only remaining factor, along with the box, the speed limits and the fact that motion needs a person turning a key. Closing this properly needs the exec gap fixed.

---

## 5. Command to motion: the path

```text
"Jorah, put the red cube in the bin"
 │ 1 wake + end of turn                      Jorah's Talk client
 │ 2 audio to realtime provider              talk.session.appendAudio (relay)
 │ 3 consult on agent:robot:arm              openclaw_agent_consult
 │ 4 robot_plan_pick("red cube")             node.invoke > mcp.tools.call.v1 > bridge
 │      local detector, annotated image      Pi. Frames stay local
 │ 5 robot_send_goal(plan_id) > BLOCKED      VOICE_CONFIRMATION_REQUIRED
 │      "Red cube by the mug. Yes?"          preview posted by guard plugin
 │ 6 "Yes"                                   transcript, gate grants one use
 │ 7 robot_send_goal(plan_id) > job id       bridge checks: key, session, plan,
 │                                           ear alive, not HALTED, box
 └ 8 bridge > 30 Hz servo commands           E9 tone and beacon on; Jorah goes quiet
```

| Hop | Budget [inference] | If it fails |
|---|---|---|
| 1. Wake and end of turn | About 0.8 s after speech ends (`ux.md` start value) | Nothing happens. Adam repeats |
| 2-3. Relay and consult | 1 s | Relay retries, then the session closes [docs-only: `macos-relay.md`]. No motion |
| 3. `robot` model turn | 1 to 2 s | Timeout is reported. No motion |
| 4. Plan on the Pi | 500 ms | "I can't see a red cube." No motion, and no guessing |
| 4. Node link | 50 ms | Tools are withdrawn when the node goes away [docs-only: `nodes/mcp-and-skills.md`]. "The arm is offline" |
| 5-6. Yes | 120 s window | Pending action expires and Talk reports it did not run [docs-only: `realtime-sessions.md`] |
| 7. Bridge accepts | 100 ms | Refuses with the reason: "disarmed", "plan expired", "halted", "can't hear stop" |
| 8. First motion | 200 ms | Fault is returned with observed pose and photo |

**Targets:** question asked within 5 s of speech ending, first motion within 1.5 s of the yes. Missing either is annoying, not dangerous. Every failure here means no motion.

**Gateway loss during a job.** The bridge does not watch the Gateway. A running skill finishes within its time limit and the result is logged locally, while the ear and E-stop keep working [inference]. So a Gateway restart cannot stop the arm, and Adam must not treat it as a way to.

---

## 6. Stop: the path

```text
"Stop"
 │ XVF3800 > ALSA > jorah-ear (Pi, no network)   microWakeWord stop.tflite
 │ Unix datagram, sent 3 times
 ▼
 bridge (Pi, separate user)
 │ cancel job, read Present_Position, sync-write Goal_Position = present
 │ latch HALTED, end E9
 ▼
 servos hold at present position
   ├ still moving at T+500 ms       > DISARM, relay off
   ├ bridge wedged                  > heartbeat silent 200 ms, relay off
   └ held 120 s with nobody acting  > warning tone, relay off, arm sags to the mat
```

### Budget, from the end of the word

| Hop | Budget [inference] | Failure behaviour |
|---|---|---|
| Array, USB, ALSA buffer | 60 ms | Capture stalls: ear heartbeat goes stale at 1 s, bridge halts |
| Detector | 300 ms. No published latency found; features step 10 ms, window 5 [verified: `stop.json`] | **Miss: nothing happens.** Adam repeats or hits the E-stop. Ear crash: stale heartbeat, halt |
| Ear to bridge | 5 ms | Bridge dead: its heartbeat stops and the relay drops |
| Bridge to bus | 50 ms, mostly waiting for the next 33 ms tick. Wire time is under 1 ms: 26-byte sync write, about 62 bytes for sync read, at 100 bytes/ms | Bus error: DISARM frame, relay off |
| Servo deceleration | 100 ms. LeRobot writes Acceleration 254 [verified: `feetech.py` v0.6.1] | `Present_Velocity` or `Moving` still set at T+500 ms: relay off [verified registers: `tables.py` v0.6.1] |
| **Total** | **About 515 ms**, against M17's 1 s | Worst case on a wedged bridge: about 60 + 300 + 200 ms plus relay drop |

### Why freeze first, and not relay off as `robotics.md` says

- `robot_stop` in `robotics.md` says "immediate stop, then relay off". Cutting power makes the arm sag and drop [verified: `robotics.md` section 4]. A false "stop" from the TV would then drop the arm every time.
- Writing the goal to the *present* position should release the gripper's squeeze too, because a position servo with almost no error applies little force [inference, test with the kitchen scale]. That also covers a pinched finger better than holding the last goal.
- The E-stop still cuts power at once. **The E-stop is the safety function. Spoken stop is a convenience** [verified: `robotics.md`, `security.md` section 15]. Nothing here is safety-rated, and it must not be described that way.

### After a stop

`HALTED` latches in the bridge. Voice cannot clear it, only a new tap can. This matches "stop listening" in `ux.md`, which voice also cannot undo. A false stop costs Adam one tap. A consult still running after the stop cannot move anything, which handles the fact that accepted work has its own cancellation lifetime [docs-only: `realtime-sessions.md`].

### The ear is a condition for motion

The bridge requires ear heartbeats at 5 Hz, carrying a sequence number and a mic level. This is the part that makes the stop path trustworthy.

- **No heartbeat, or digital silence, means no motion.** "I can't hear stop, so I won't move." A running job halts within 1 s.
- **Muting the array also blocks motion.** Bench work in R1 to R3 runs in a separate mode with a hand on the E-stop.
- **Stop check at session start.** After the tap, Jorah says "say stop". The ear must hear it before the session opens. This proves the mic chain works and that someone is within earshot. It costs about 2 s per session. It does not prove who spoke.
- **The bridge heartbeat comes from the control loop**, not a separate thread, so a wedged loop drops the relay within 200 ms.

---

## 7. Which detector, on which device

**Pick: microWakeWord's `stop` model, through `pymicro-wakeword`, on the Pi next to the bridge.**

- The model already exists: `wake_word: "Stop"`, English, cutoff 0.5, 45 KB, tensor arena 21 KB [verified: [stop.json](https://github.com/OHF-Voice/linux-voice-assistant/blob/main/wakewords/stop.json), GitHub API; released in [microWakeWord](https://github.com/kahrendt/microWakeWord/releases/tag/stop), repo Apache-2.0]. The model's own license was not stated separately.
- It is used in production in this exact role. Voice PE turns it on during long replies and ringing timers [verified: [home-assistant-voice.yaml](https://raw.githubusercontent.com/esphome/home-assistant-voice-pe/dev/home-assistant-voice.yaml)]. Linux Voice Assistant runs it on Raspberry Pi-class Linux, only while something audible could be cancelled [verified: [behavior.md](https://github.com/OHF-Voice/linux-voice-assistant/blob/main/docs/behavior.md), [README](https://github.com/OHF-Voice/linux-voice-assistant)].
- `pymicro-wakeword` 2.5.0 has wheels for macOS, Linux aarch64, Linux x86_64 and Windows [verified: [PyPI](https://pypi.org/project/pymicro-wakeword/), 2026-10-27]. The same detector can run on Pi, Mac and PC. Its built-in list has no `stop`, so load the model files from LVA. Whether its API loads a custom config needs a check [inference: README shows `from_builtin` only, LVA loads its own].
- Copy LVA's pattern: **listen only while armed**. That reduces both false stops and the time a microphone is live.

**No published accuracy figure exists for this model.** None of this is proven until T1 runs. A cutoff of 0.5 looks permissive, which suits a word where a false alarm is the cheap mistake [inference].

| Device | Verdict | Reason |
|---|---|---|
| **Pi** (with bridge) | **Pick, the authority for motion** | Same failure domain as the arm. Works with Wi-Fi, Gateway, Mac and PC all down. No network hop. It exists from M17, because the exec boundary needs it anyway |
| Mac | **Second ear, and the owner of speech and vision stops** | Already holds the mic in M10, and its client knows its own playback. It sleeps [verified: `voice.md` 3.5], so it cannot be the authority |
| PC | Runner-up, only if the arm is wired to it (`robotics.md` runner-up) | No built-in wake on Windows, specs unknown, location unknown |
| Voice PE | No | Its `stop` runs only during replies and timers, so it needs firmware changes [verified: yaml above]. Reaching the bridge adds a Wi-Fi hop and a signed protocol. A later extra ear if Adam buys one |

**Hearing it while Jorah speaks and servos run.** This is the real risk, and there is no evidence yet.

- **Servo noise:** the array sits on the table 40 cm or more from the servos, not on a moving link. `robotics.md` is right here [inference]. XVF3800 has DNN noise suppression [verified: [Seeed wiki](https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/)].
- **Jorah's voice, phase 1:** Talk stays on Mac speakers at a distance, and the ear gets no echo reference. Jorah goes quiet during motion, with the E9 tone only, so the hardest case is rare by design [inference]. If Jorah's own speech contains "stop", the arm halts. That is annoying but safe, so its prompt should avoid the word.
- **Jorah's voice, phase 2, only if T1 fails:** move Talk's audio to the Pi and play it through the array, so the board gets an echo reference.
- **Still open:** neither Seeed's wiki nor XMOS's product page says how the reference is fed [verified: both, today]. `voice.md` flagged the same question. Check the datasheet before relying on phase 2.

**Vision kill phrases need the same mechanism but not the same model.** "Stop looking" and "close your eyes" are not covered by `stop.tflite`, and the cameras they control are on the Mac. Use a small closed list in the M10 client with **sherpa-onnx KWS**: open vocabulary, per-keyword thresholds, no training [verified: [sherpa docs](https://k2-fsa.github.io/sherpa/onnx/kws/index.html)]. Its pretrained English model was never tested on these phrases [inference]. The same list holds "stop everything" and "stop listening".

**Slovak.** The model is trained on English only [verified: `stop.json`]. The test must use Adam's own voice. A guest saying "zastav" will not trigger it, which is why the E-stop stays within reach.

**Network path for other ears.** The Mac client sends the same stop as UDP on the LAN, three times, with HMAC-SHA256 and a counter [inference]. A stolen key lets someone stop the arm, and nothing more. The key has no other use.

**Non-voice stops.** Talk's Stop button and `/stop` do not reach the bridge today. Add a guard-plugin command `/robot-stop` that calls `node.invoke` directly with no model, and make K1 freeze do the same [inference; K1 is `security.md` section 17].

---

## 8. The mobile base (M25)

Same path and same permissions. Three differences:

1. **A microphone on the base is close to useless.** Tracks are loud and Adam may be across the room [inference]. So the ear stays in the room, and stop crosses Wi-Fi.
2. **Stop must therefore be a lease, not a message.** Motion is allowed only while signed heartbeats arrive from a room ear at 5 Hz. Three missed: the base bridge halts. Wi-Fi loss is then a stop, not a runaway. Firmware's own watchdog is set to about 300 ms via `{"T":136,"cmd":300}`, down from 3,000 ms [verified: `robotics.md` section 8, firmware source].
3. **A stop button that does not depend on Wi-Fi.** The RC failsafe and remote kill from `security.md` section 15 become a requirement before the first voice-driven move, not an option. Not priced here.

Budget: end of word to motors commanded off about 500 ms on good Wi-Fi [inference]. At the 0.35 m/s top speed that is about 18 cm of travel, plus coasting. Measure with a tape. "Adam present" (row 42) means in the same room and within the ear's range. Beyond that, the base stops by the lease rule.

---

## 9. An arm that sees and hears in real time

**Recommendation: use the relay and frames, and do not add a WebRTC stack for the arm.**

| Sense | Path | When | Cost |
|---|---|---|---|
| Hear, stop only | `jorah-ear` on the array | M17 | In plan |
| Hear, conversation | Jorah's thin Talk client on the Pi: array to `talk.session.appendAudio`, with `--voice-node` credentials limited to `operator.read` and `operator.talk` [docs-only: `cli/qr.md`] | M17 phase 2, same code as M10 | Realtime voice cost |
| Turn toward the speaker | Local: read `DOA_VALUE` from the array [verified: Seeed wiki], `robot_look_at_speaker` skill, no model | After M17 | €0. This is what will make it feel alive [inference] |
| See, on request | `robot_snapshot` through a consult. 1 to 3 s per look | M17 | Included in the turn |
| See, continuously | Pi sends JPEGs at 1 fps to the `jorah-vision` sidecar, which owns a Gemini Live session with compression and resumption, as `vision.md` already requires | After Watch mode exists | $0.36 to $1.08 per hour for video, and `vision.md` says the true bill is uncertain |
| Quick demo | Chromium on the Pi, Control UI Video Talk with the wrist camera | Any time | Expect it to stop at about 2 minutes [verified: `vision.md` 4.3] |

**Why no LiveKit or Pipecat here.** `vision.md` found that none of the main model providers take live video, and Gemini is capped at 1 frame per second [verified: `vision.md`]. WebRTC solves a problem this link does not have. The relay carries audio only [verified: section 2], so frames go through tools or the sidecar. If Adam wants to watch the wrist camera directly, MJPEG over Tailscale or Foxglove is enough [inference].

**Who wins on the stack.**

- For the **arm**: `robotics.md` (USB camera, wired, Pi host). `openclaw-fit.md`'s LiveKit recommendation is retired for the arm.
- For **a device with no Pi**, such as an ESP32 camera on a small rover: `openclaw-fit.md` stays the candidate. It remains unsettled because the LiveKit ESP32 SDK is a Developer Preview and Pipecat's ESP32 repo looks quiet [verified: `openclaw-fit.md` section 7].
- If V2's Pipecat pipeline is ever triggered, it plugs in as a realtime provider [docs-only: via `voice.md`], and the Pi client does not change.

**Adam's mic on the arm.** `robotics.md` stays right that a mic on a moving link sits next to the gears. So the mic goes on the arm's base. To Adam it is still the arm's ear, and it can point the wrist camera at Adam. The XIAO mic stays a bench experiment.

**Acceptance.** Adam says "Jorah, what's on the table?" from 1 m. The wrist camera moves to `look_table` and Jorah answers correctly in under 3.5 s, 9 of 10 times (`vision.md`'s target). Then Adam moves and speaks from another side, and the camera turns toward Adam 8 of 10 times.

---

## 10. Which track wins

| Conflict | Winner | Why |
|---|---|---|
| Who holds `robot_*`: `security.md` `robot` agent vs roadmap with none | **`security.md`** | Only design where `voice` and `main` keep their limits. M17 must create the agent |
| Authority: `security.md` row 40 tap vs `voice.md` tier 3 "yes plus tap" per action | **`security.md`** for the tap, once per session | A tap on every move is unusable with hands busy, and fatigue defeats it. `voice.md`'s table should read "tap to open a session, yes per plan" |
| `robot_pick` waits for yes vs "voice never approves" | **Both stand**, once defined (section 4) | The yes is a target check, as `ux.md` U8 already says |
| `robotics.md` "gate is good for picks" | **Code wins over docs and over `robotics.md`** | The name-based check does not match `robot_pick`. Rename and test |
| `security.md` line 348: wake word "never robot motion beyond stop" | **Stands, narrowed** | True for `voice` and with no enabled session. Motion needs the tap-opened `robot` session |
| Who owns stop: `robotics.md` hands it to voice and OpenClaw tracks | **`robotics.md` for the route** (bridge, no LLM), and the **robot lane owns it** | Stop lives on the robot host, so it belongs with the bridge. M17 owns it, with no dependency on M20 |
| `voice.md` and `security.md` K0v "locally when possible" | **Replaced for motion: always local** | Motion refuses to run without the ear. "When possible" still applies to speech |
| `ux.md` "on V0 and V1 stop reaches a model" | **True for speech until M10 is amended. False for motion** | Different paths. Keep the table's row "Stop while the robot moves" |
| `robot_stop` "immediate stop, then relay off" | **Changed:** freeze, then relay off on the timers in section 6 | Avoids dropping the arm on every false alarm. E-stop keeps immediate power cut |
| `topology.md` Windows `robot-bridge` vs `robotics.md` Pi | **`robotics.md`** for the arm, as it proposed | The stop path needs the ear beside the bridge, and a Windows update must not take it away. `topology.md` keeps LAN devices |
| Arm mic: Adam's goal vs `robotics.md` advice | **`robotics.md` on placement, Adam's goal on the feature** | Array on the base gives both |
| LiveKit or Pipecat vs Pi host | **Pi, frames and relay** | Section 9 |

---

## 11. Proposed roadmap edits

- **M10:** the wake client gains a closed list (bare stop, "stop everything", "stop listening", vision kill phrases) and calls `talk.session.cancelOutput` locally. It keeps a dormant sender for the LAN stop. On plain Gemini this silences the speaker but cannot stop generation [verified: `voice.md` section 5].
- **M17:** adds the `robot` agent, node-tool denies elsewhere, `jorah-robot-guard` (tap, preview, `/robot-stop`), `jorah-ear` as its own user with no network, bridge `HALTED` and ear lease, and T1 to T9. It has no dependency on M20. The Pi becomes required.
- **M20:** no longer carries any stop duty, and stays conditional.
- **M25:** adds the lease, room ear and radio kill before the first voice-driven move.
- **New, after M17:** "arm presence" from section 9.

**Separation on the Pi** extends `robotics.md` section 1: `robotd` alone opens the serial port, `jorah-ear` has audio and no network (`PrivateNetwork=yes`), and the node host has neither [inference]. This also makes "no audio leaves the ear" checkable with a packet capture, which suits Adam's truthful-claims rule.

---

## 12. Tests that decide this

Nothing below has run. Evidence tier for all of it today: source check at most.

| # | Test | Pass | If it fails |
|---|---|---|---|
| T1 | 100 "stop" at 1 m, in four conditions: quiet, servos, Jorah speaking, both | At most 10% missed in the worst condition, from Adam's voice | Phase 2 audio, array placement, or sherpa-onnx as the second detector |
| T2 | 20 stops on video or logic analyser, servos under load | 19 of 20 halted within 1 s of the word ending, among those detected. Misses counted under T1, never hidden | Find the slow hop from logs |
| T3 | Relay session calling `robot_send_goal` and `robot_pick` on a fake bridge | `VOICE_CONFIRMATION_REQUIRED` on the first, none on the second. Repeat at each OpenClaw upgrade | Tap on every goal via `requireApproval` |
| T4 | Does a `--voice-node` client select `agent:robot:arm`? | Session runs on `robot` | Option B |
| T5 | `kill -STOP` on the bridge during motion, and kill the ear | Relay off within 300 ms, and halt within 1 s, 20 of 20 | Fix before any voice motion |
| T6 | TV and normal talk replayed for 8 armed hours, logging only | At most 1 false stop per armed hour [inference] | Raise cutoff, then re-run T1 |
| T7 | Mute the array, unplug it, and start a session | Motion refused, with the reason spoken | Fix |
| T8 | Text in the camera view and in a Telegram message asking for motion | No motion, 5 of 5 (`robotics.md` R4) | Stop, redo section 3 |
| T9 | Pull the Gateway during a job, then say stop | Stop still works. Result logged locally | Fix |

**Evidence ladder for M17:** fake bridge in MuJoCo (T3, T4, T8), then bench with servos and no load (T1, T5, T7), then supervised with objects (T2, T6, T9). Spoken stop never replaces the E-stop test in R1.

---

## 13. What would change this

- **T1 fails in every setup:** spoken stop becomes best effort and M17's 1 s line must be rewritten honestly. A foot pedal or a wristband button would become the hands-free stop. That is a real option, and worth keeping in mind.
- **Arm wired to the PC instead of a Pi:** same design on Windows. The wheel exists, but Windows Update, sleep and account separation need their own answers.
- **OpenClaw adds a declared-mutation flag for node MCP tools:** drop the naming trick and use it. I found `ownerKey` only for owner-declared internal paths, and it is not passed by the gate.
- **A provider accepts real video at sensible cost:** revisit section 9.
- **This becomes a product:** a spoken stop or an AI-related safety function falls into a much heavier regime, since the EU Machinery Regulation applies from 20 January 2027 [verified: via `robotics.md` section 7]. This whole design is a hobby safeguard.

## 14. Not confirmed

- Detection accuracy and latency of `stop.tflite`, on any hardware or voice.
- How the XVF3800 takes its AEC reference, and its processing delay.
- The stop model's own license; only the repos' licenses were read.
- Whether `pymicro-wakeword` loads an external config directly.
- Servo stopping time under load, and whether a goal at the present position really removes gripper force.
- Whether a limited voice-node token may select `agent:robot:*`.
- Whether the gate and hooks apply on the Claude CLI runtime.
- Base stopping distance, and any radio kill price.

## Sources

Local, read today:

- `/opt/homebrew/lib/node_modules/openclaw/docs/nodes/talk/realtime-sessions.md`, `talk/session-ownership.md`, `talk/macos-relay.md`, `talk.md`, `mcp-and-skills.md`, `voicewake.md`, `command-policy.md`; `docs/cli/qr.md`; `docs/plugins/plugin-permission-requests.md`
- `/opt/homebrew/lib/node_modules/openclaw/dist/tool-mutation-BTW6eoAN.mjs`, `agent-tools.before-tool-call-CQkX3nOj.mjs`, `openclaw-tools-CSSYZDKR.mjs`, `node-commands-Bxo-2Y4j.mjs`, `handlers-B5Rt4cMl.mjs`
- `docs/plan/research/`: `robotics.md`, `security.md`, `voice.md`, `ux.md`, `vision.md`, `openclaw-fit.md`, `topology.md`

Web, direct fetch or GitHub and PyPI records:

- [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant), [behavior.md](https://github.com/OHF-Voice/linux-voice-assistant/blob/main/docs/behavior.md), [stop.json](https://github.com/OHF-Voice/linux-voice-assistant/blob/main/wakewords/stop.json)
- [microWakeWord `stop` release](https://github.com/kahrendt/microWakeWord/releases/tag/stop)
- [pymicro-wakeword](https://github.com/OHF-Voice/pymicro-wakeword), [PyPI](https://pypi.org/project/pymicro-wakeword/)
- [Voice PE firmware YAML](https://raw.githubusercontent.com/esphome/home-assistant-voice-pe/dev/home-assistant-voice.yaml)
- [ESPHome micro_wake_word](https://esphome.io/components/micro_wake_word/)
- [sherpa-onnx KWS](https://k2-fsa.github.io/sherpa/onnx/kws/index.html)
- [Seeed XVF3800 wiki](https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/), [XMOS XVF3800](https://www.xmos.com/xvf3800/)
- [LeRobot `tables.py` and `feetech.py`, v0.6.1](https://github.com/huggingface/lerobot/tree/v0.6.1/src/lerobot/motors/feetech)
