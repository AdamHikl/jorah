# Jorah architecture

Date: 2026-11-02. Scope: system design, components, three data flows, PC and Mac topology, migration, compatibility, performance budgets, model routing and cost.

**Evidence today: source, docs and read-only checks only.** Nothing here has been installed, launched or tried on a device. No PC exists in any test. Every hour, wattage and latency budget is a target to measure, not a result.

**Labels**

| Label | Meaning |
|---|---|
| `[verified: X]` | Read from primary source X today, or observed on this Mac |
| `[measured]` | Read-only command or log parse on this Mac today |
| `[source: file]` | Read in OpenClaw 2026.10.9's shipped code. Proves what the code says, not that it works at runtime |
| `[docs-only: path]` | OpenClaw's bundled docs say so. Paths are under `/opt/homebrew/lib/node_modules/openclaw/docs/` |
| `[track: file §n]` | Finding and its evidence label are in `docs/plan/research/`, not re-checked here |
| `[inference]` | Reasoning or arithmetic. Can be wrong |
| `[unverified]` | Could not be confirmed. Do not spend money or set a gate on it |

**Name prefixes**, because the tracks reuse letters: SEC-T = `security.md` §18 tests. TOPO-S and TOPO-A to F = `topology.md` §16. BRIDGE-S = `gap-voice-brain-context-and-delegation.md` §8, plus BRIDGE-S7 from `04-voice-and-vision.md` §7.3. EAR-E = `gap-room-and-pc-ear-after-cutover.md` §7. FLOW-T = `gap-post-cutover-workload-and-file-flow.md` §7. MOTION-T = `gap-voice-to-motion-path-and-local-stop.md` §12. GROW-S = `growth.md` spikes. APP-T = `apps.md` §11 tests. VIS-V = `vision.md` stages. R0 to R9 = `robotics.md` stages. RISK-T0 to T4 = approval tiers. M-numbers and B-numbers are roadmap milestones and purchases.

**Short file names:** `gap-voice-brain` = `gap-voice-brain-context-and-delegation.md`. `gap-room-and-pc-ear` = `gap-room-and-pc-ear-after-cutover.md`. `gap-voice-to-motion` = `gap-voice-to-motion-path-and-local-stop.md`. `gap-post-cutover` = `gap-post-cutover-workload-and-file-flow.md`. `gap-private-data` = `gap-private-data-through-realtime-providers.md`.

---

## 1. The design on one page

1. **One Gateway owns all state.** It is OpenClaw 2026.10.9, pinned. Nodes and apps are peripherals that dial out to it. There is never a second live Gateway on the same state [docs-only: `nodes/index.md`, `gateway/remote.md`].
2. **Lanes are chosen by trigger, not by a classifier.** Typed turns use Opus on Max. Voice uses a realtime model in front of a thin Haiku agent. Machine-triggered work uses API credits. Local models come later [track: brain.md §1, §8].
3. **Room audio never reaches the agent holding everything.** `voice` is thin. `main` is the only writer of memory and skills. They are linked by a typed plugin. The honest wording is "one Jorah, two transcripts, shared facts" [track: gap-voice-brain §1].
4. **Private content is never handed to the realtime model.** It goes to a screen, and the voice gets a pointer. That is enforced by a tool that returns no content [track: gap-private-data §4].
5. **Inside the Gateway only if it must be.** A plugin must need Gateway internals, have no model or native dependency, have no timing guarantee, be about 300 lines or fewer, and fail closed. Everything else is a separate process with its own OS user and supervisor [track: engineering.md §6.2].
6. **Boundaries are operating system boundaries.** Separate macOS users, Windows users, Linux users, microVMs, a Pi. Allowlists are a second layer, because the advisory history shows bypasses [track: openclaw-fit.md §9].
7. **Safety lives below the model.** A key switch, E-stop, relay, firmware and bridge do not depend on the Gateway. A spoken stop never passes through the Gateway or a model [track: gap-voice-to-motion §1].
8. **A failed route reports the failure.** Nothing moves to a paid meter or another vendor by itself. A missing source shows "not available", never zero [track: brain.md §10].
9. **Daily realtime talk runs on a client we own.** Only the connection that opened a Talk session can close it [source: `requireUnifiedTalkSessionConn` in `dist/session-registry-CcW20RXI.mjs`]. So the stock Mac app is for the bench, and `jorah-talk` is the daily ear (section 4.1).

### System diagram, end state after M17

```text
                     tailnet (WireGuard). No public ports, no Funnel, no port forwards.

 USER DEVICES, tailnet identity is the user
  Mac, user adam     OpenClaw.app: Voice Wake, Talk, overlay, approvals. Exec denied  ──┐
                     jorah-talk: own Talk client, closes itself when idle             ──┤
  iPhone, Watch      OpenClaw app: Talk, approvals, cards                             ──┤ wss://pc.<tailnet>.ts.net
  Browser            Control UI, review page. Video Talk frames go browser -> Google  ──┤
                                                                                        ▼
 ┌───────────────────────────── Windows 11 Pro PC, tag:jorah-pc ──────────────────────────────┐
 │ Tailscale on the host, Run unattended on. Serve: 443 -> Gateway, tcp 2222 -> SFTP,         │
 │ https 8443 -> review page. Gateway stays on loopback.                                      │
 │                                                                                            │
 │ WSL2 distro jorah-gw, owned by Windows user jorah-svc. Automount, fstab, interop off.      │
 │ Linux user jorah has no root and no sudo.                                                  │
 │   OpenClaw Gateway: channels, memory, cron, approvals, Talk relay                          │
 │     plugins  jorah-guard  jorah-bridge  jorah-vision  jorah-robot-guard  (in-process)      │
 │     agents   main  voice  background  reader-web  reader-private  builder  actor  robot    │
 │   Claude CLI brain, delegated Claude Code in bubblewrap (no network, no GPU)               │
 │   jorah-media: GPU worker, systemd, no network, reads a job spool                          │
 │   /srv/jorah-media in ext4, sshd on 127.0.0.1:2222 (chrooted SFTP), review page            │
 │   Ollama and local models, jorah-metrics                                                   │
 │                                                                                            │
 │ Windows users (standard)                                                                   │
 │   jorah-talk   S4U task: jorah-talk client, trained wake model, USB speakerphone           │
 │   jorah-desk   Node host: Fusion, Resolve on a leased console. LAN device bridges          │
 │   jorah-lab    Node host publishing jorah_lab MCP. sbx microVMs, deny-all egress           │
 │   adam         Admin, BitLocker recovery, updates. Holds no Jorah state                    │
 └───────┬───────────────────────────────┬───────────────────────────────────┬────────────────┘
         │ SSH 22, restricted key         │ node link, wss via Serve          │ LAN, IoT Wi-Fi
         ▼                                ▼                                   ▼
  Mac, other macOS users           Raspberry Pi 5, tagged, by the arm    ESP32 LAN devices
   jorah        iMessage bot,        robotd     owns serial, freezes,     Never nodes, never on
                rescue bot                      latches HALTED             the tailnet. Talk only
   jorah-build  iOS node, wrappers   node host  outside dialout,           to a bridge
                                                exec denied, MCP only
                                     jorah-ear  no network, stop model
                                     jorah-talk arm conversation, XVF3800, only on M17-D's Pi fork
                                          │ USB serial, CRC frames
                                          ▼
                                     ESP32-S3 safety supervisor, bus firewall
                                          │ relay, key switch, E-stop (hardware)
                                          ▼
                                     SO-101 arm. Later, the tracked base on its own Pi
```

### Who talks to which cloud

| Destination | What goes there | When | Meter |
|---|---|---|---|
| OpenAI (or Google if it wins the bench) | Everything the mic hears, including bystanders. Profile files up to 12,000 characters. Every consult answer spoken [source: `dist/realtime-bootstrap-context-dPeThtcK.mjs`; track: gap-private-data §2] | Only while a Talk session is open | Prepaid, capped |
| Google Live | 1 fps frames from the browser, bypassing the Gateway [docs-only: `nodes/talk/realtime-sessions.md`] | Explicit Live or Video Talk only | Prepaid, capped |
| Anthropic API | Consults, readers, background, unattended work, captions | Per call | $100 credits, no card |
| Claude plan (Max, through Claude CLI) | Typed turns, `ask_main` turns, delegated coding | A person asked | Plan limits |
| Telegram | Bot messages. Not end to end, so neutral lines for private data | Per message | Free |
| Apple | Speech if Talk falls back to native, and push notices | On fallback | Free |

---

## 2. Components

"Status" is the true state today. **Build** means we write it.

### Shipped software we use

| Component | Version | Where | Runs as | Supervised by | Status |
|---|---|---|---|---|---|
| OpenClaw Gateway, profile `jorah` | 2026.10.9 | Mac now, `jorah-gw` at M9 | `adam` now, `jorah` from M1 | Foreground now, LaunchAgent `ai.openclaw.jorah`, then systemd user unit | Running as `adam` on `127.0.0.1:43181` [measured]. `gateway.port` is unset, and the docs' default is 18789 [track: topology.md §2] |
| Claude CLI, separate login `~/.claude-jorah` | 2.1.300 | Same host as Gateway | Same | Spawned by Gateway | Working. Same Claude account as Adam's main login [measured: brain.md §2] |
| acpx and delegated Claude Code | Bundled | Same host | Same, in Seatbelt or bubblewrap | Spawned | Working on Mac. The repo sets `sandbox.failIfUnavailable: true`; keep it on the PC [verified: `scripts/setup-permissions.sh`] |
| Memory stack | Bundled | Gateway | Same | Gateway | memory-core, Active Memory, Memory Wiki, Dreaming, local EmbeddingGemma |
| OpenClaw.app | `OpenClaw-2026.10.9-arm64.dmg`, sha256 `8159c89174298c3238dac8ce1566b5dd43905f5f6f8e9a873c0222a23f219f72` [verified: GitHub release API, track: openclaw-fit.md §11] | Mac, user `adam` | `adam` | Login item | Not installed [measured]. Needs macOS 26+ for voice; this Mac has 27.0.1 [measured] |
| OpenClaw iOS app | Store 2026.10.70, needs iOS 26.2+ | iPhone | n/a | n/a | Not installed. Maps to Gateway 2026.10.7, so likely lacks the #180426 stall fix [track: apps.md Verification] |
| Tailscale | 1.96.5, Standalone on Mac | Windows host, Mac, iPhone, Pi | Device | OS | `NeedsLogin` on this Mac [measured] |
| Ollama | Present on Mac, no models | PC at M9 or later | `jorah` | systemd | Known trap on WSL2 with NVIDIA: boot reload can cause VM restart loops [docs-only: `gateway/local-models.md`] |
| LeRobot, MuJoCo | v0.6.1, Python 3.12 | Mac for sim, Pi from M15 | `robotd` | systemd | Not installed [track: robotics.md §5] |

### What we build

| Component | Kind | Repo path | Host | Does | First in | Effort [inference] |
|---|---|---|---|---|---|---|
| `jorah-adam-data` | launchd service under `adam` | `services/jorah-adam-data/` | Mac | Fixed typed tools for Reminders, inbox and outbox, later iMessage read, reached through `mcp.servers` over loopback with a token. No shell surface | M6 | 4-6 h |
| `jorah-guard` | Plugin | `plugins/jorah-guard/` | Gateway | `before_tool_call` policy, session taint, hash-chained audit log, generic approval text, no Allow Always. Fails closed | M3 | About 300 lines |
| `jorah-keychain-resolver` | Script | `scripts/` | Gateway host | Exec secrets provider for the gateway token. No built-in recipe exists [track: security.md §5] | M0 | Hours |
| `jorah-metrics` | Library and JSONL ledger; `jorah-status` is its text view | `services/jorah-metrics/` | Gateway host | Turn timing, tokens, cost by lane. Missing data shows "unknown" | M2 | 1 to 2 days |
| `jorah-bridge` | Plugin | `plugins/jorah-bridge/` | Gateway | Tools `ask_main`, `start_job`, `job_status`, `job_steer`, `job_cancel`, `note_for_main`, `web_answer`, `private_show`. Digest service. Inbox. `start_job` runs synthetic briefs only until `jorah-guard` taints `agent:main:voice-*` at M3 | M2b, widened at M3 and M4 | 2 to 3 days, plus 1 to 2 for `private_show` |
| `jorah-talk` | External Talk client, MIT fork of `e-jung/voice-pe-openclaw` | `services/jorah-talk/` | Mac (`adam`, signed app, LaunchAgent), then PC, then Pi | Local capture, wake model, RAM ring, `talk.session.*`, **idle close**, local stop list, marks acknowledged. No native fallback. The stock app has no idle close that could be found, relay sessions close only at 30 min, and an outside helper cannot close them [source: `RELAY_SESSION_TTL_MS`, `requireUnifiedTalkSessionConn`; track: voice.md §1 finding 8] | M2b on the Mac, M10 on the PC, M17 on the Pi | 30 to 45 h for M2b together with the bridge and digest [inference, `04-voice-and-vision.md` §2] |
| `jorah-ingestd`, `jorah-send` | Service and script | `services/jorah-ingestd/` | `jorah-gw`, and Adam's Mac and PC | SHA-256 check, `ffprobe` with no network, move to read-only source. `jorah-send` shows size, time and free space, then uploads on Adam's yes | M12 | 1 day |
| `jorah-media` | Worker service | `services/jorah-media/` | `jorah-gw` | Reads validated job files, renders and transcribes with GPU, `PrivateNetwork=yes` | M12 | 1 to 2 days |
| Review page | Local web service | `services/jorah-review/` | `jorah-gw`, Serve on 8443 | Proxy playback, Approve, time-coded notes. Requires Serve header and a per-review token | M12 | 1 to 2 days |
| `jorah-lab` | Host script, then node-hosted MCP | `scripts/jorah-lab` | Mac, then Windows user `jorah-lab` | Fixed verbs over `sbx` 0.50.1+, timeouts on every call, symlink refusal, audit log | M11 | Per `growth.md` |
| `jorah-eyes`, `jorah-vision` | Sidecar and plugin | `services/jorah-eyes/`, `plugins/jorah-vision/` | Machine with the camera | RAM ring, detectors, events. Tools `vision_look`, `vision_status`, `vision_pause`, `vision_arm`, `vision_recall`. Off at boot | M18. Look at M6 through `camera.snap` if it returns in under about 1 s | Signed app bundle adds work on Mac |
| `robot-bridge` (`robotd`) | Service | `services/robot-bridge/` | Mac sim, then Pi | Named skills, plan store, 30 Hz loop, freeze, `HALTED` latch, ear lease | M5 | Per `robotics.md` |
| `jorah-ear` | Service | `services/jorah-ear/` | Pi | microWakeWord `stop` model through `pymicro-wakeword` 2.5.0. No network | M17 | 2 to 3 days |
| `jorah-robot-guard` | Plugin | `plugins/jorah-robot-guard/` | Gateway | Session tap, preview delivery, `/robot-stop` | M17 | 1 to 2 days |
| Safety firmware | Arduino core 3.x, logic in plain C++ | `firmware/` | ESP32-S3 | Relay, watchdog, current sense, bus firewall | M8 | Per `robotics.md` |
| `jorah-voice`, `jorah-voice-provider`, `jorah-presence` | Pipecat 1.15 service, plugin, state hub | `services/`, `plugins/` | PC native Windows, Mac | V2 only, if a trigger fires | M20 | 2 to 3 weeks |
| Rescue bot | Second profile, own Telegram bot | `ops/` | Mac user `jorah` | Reports the PC is down. No real channels, no robots | M9 | Hours |

### Agents

Config home: `agents.entries.<id>`. Names follow `security.md` §6. `brain.md`'s `reader` lane is `reader-web` plus `reader-private`. Its `worker` lane is `builder` when shell is needed and `background` when not.

| Agent | Runtime and model | Meter | Sees | Tools | Cannot |
|---|---|---|---|---|---|
| `main` | Claude CLI, Opus 5.5 | Plan | Memory, profile, reader fields | Memory, `skill_workshop`, `message` to Adam, `sessions_spawn` to listed agents | Shell (`group:runtime` denied), robot tools, reach any API key |
| `voice` | Embedded, Haiku 5.5, thinking off, prefix under 8K tokens | Credits | Room audio (untrusted), public-class digest | `jorah-bridge` tools, `vision_look` from M6. `memory_search` on its own corpus only, dropped if the canary fails. **Which of these it can really call depends on the client's token scopes, section 12 item N1** | Shell, `message`, `sessions_*`, `skill_workshop`, `wiki_*`, private text |
| `background` | Embedded, Haiku 5.5, local on PC later | Credits, then free | `main`'s memory files for the digest, no transcripts | None for completions; read-only for the heartbeat | Outward anything |
| `reader-web` | Embedded, Haiku 5.5, Sonnet 5.5 if it fails evals | Credits | Web, no memory | `web_search`, `web_fetch` | Secrets, POST |
| `reader-private` | Embedded API, or local for EduPage | Credits or free | Mail, messages, school | `read` on a drop folder, typed output | Network, `message` |
| `builder` | ACP Claude Code on plan, or embedded Sonnet 5.5. Chosen once at M3 (section 4.2) | Plan or credits | Its project folder | `exec`, fs in its workspace | Home, Google token |
| `actor` | Embedded API | Credits | Approved values only | Send, calendar write | Raw untrusted text, shell |
| `robot` | Embedded, fast API model. No channel binding | Credits | Camera frames (untrusted) | `robot_*` only | Everything else. Other agents have an explicit deny on `robot_*` and `base_*`, because node tools are visible by default [source: `dist/openclaw-tools-CSSYZDKR.mjs`] |

---

## 3. Lanes at a glance

| Trigger | Lane | Model | Where it runs | Spec |
|---|---|---|---|---|
| Mic audio before wake | Wake | On-device detector, no LLM | Ear device | Nothing leaves |
| After wake | Voice front | `gpt-realtime-2.1-mini`, challenger `gemini-3.8-live` | Provider, through Gateway relay | Section 8.2 |
| Realtime model needs tools | Consult | Haiku 5.5, `voice` | Gateway | Section 8.1 |
| Adam typed, or `ask_main` | Deep | Opus 5.5, `main`. Fable 5.1 only if Adam asks | Gateway | Section 8.1 |
| Adam asked for code | Coding | Claude Code via ACP, Sonnet 5.5 subagents | Gateway host, sandboxed | Section 4.2 |
| Machine-triggered | Unattended | Sonnet 5.5 API, Haiku for small steps | Gateway | Section 8.1 |
| Frames | Vision | Local detector first, then caption, Sonnet only for real analysis | Camera host | Section 4.1 row G |
| Motor loops | None | No LLM | Bridge, firmware | Section 4.3 |

---

## 4. Data flows

### 4.1 A voice turn

**Version:** V1, from M2. **Ears, in order:** the stock Mac app with relay on, for the M2a bench only, with Adam ending each session by hand. `jorah-talk` on the Mac from M2b, for daily use. `jorah-talk` on the PC from M10. Numbers are budgets [track: gap-voice-brain §5, gap-room-and-pc-ear §5], none measured.

```text
 Ear      Wake fires on device. Audio was RAM only until now. Earcon, indicator names the recipient.
          Mac app: talk.agentId -> voice.  jorah-talk: talk.session.create sessionKey agent:voice:<room>
 Ear>GW   talk.session.appendAudio: base64 PCM16 24 kHz, JSON over WebSocket over TCP
 GW>Prov  input_audio_buffer.append, while the session is open
 Prov     Server VAD ends the turn (OpenAI default 500 ms, bench 400, 500, 700. Gemini 500 first)
          Then one of the branches below
 Ear      Plays audio, acknowledges marks with talk.session.acknowledgeMark, sends timestamps
          Barge-in: talk.session.cancelOutput for the current turnId
 Close    jorah-talk: talk.session.close after 5 s with no speech, or 8 s after a reply, 12 s after a question.
          Each wake starts clean. Mac app and iPhone app: no idle close found, so Adam ends the session
```

| Branch | Request | Route | Who answers | Target to first audio, p50 / p90 |
|---|---|---|---|---|
| A | Greeting, repair, "what did you say" | No consult | Realtime model | Under 800 ms / 1,200 ms |
| B | Time, timer, "is the job done?", "note that", curated public notes | `openclaw_agent_consult`, `voice` plus one local tool | `voice` | About 2.8 s / 4.2 s |
| C | Adam's memory, decisions, reasoning | `ask_main`, holds the consult up to 25 s, on `agent:main:voice-bridge` | `main`, under about 60 words | About 5.8 s / 16 s. Acknowledgement under 1 s |
| D | Anything that takes work | `start_job`, on `agent:main:voice-job-<id>`, also posts Telegram with Cancel | `main` and workers, result on screen or Telegram | Receipt under 1 s |
| E | Mail, calendar content, messages, school | `private_show`: reader to a card. Returns `{status, surface, count, firstAt}` only | Screen. Voice says "Four things today, first at ten. It's on your Mac" | About 2.8 s plus reader time, unmeasured [inference] |
| F | Public web question | `web_answer` to `reader-web`, typed fields, capped | `reader-web` | About 6 to 9 s / 12 to 14 s |
| G | "What am I holding?" | Look: `voice` calls `vision_look`. One frame (`camera.snap` with `delayMs: 0` at first, the sidecar once it exists), then one small API vision call. Going through `main` would miss the target [inference: about 6 s at p50 to reach `main`] | Haiku 5.5 or Sonnet 5.5 by API, chosen by test T3, frame at 1,280 wide or less. The provider speaks the sentence, and does not get the frame. Anyone else in frame: a card and a neutral line | Under 2.0 s / 3.5 s [track: vision.md §8] |

**Why a held consult.** OpenClaw 2026.10.9 cannot push text into a realtime call on the tool-call path [source: `dist/handlers-B5Rt4cMl.mjs`, `dist/realtime-session-harness-76VKE8_t.mjs`]. So an answer is spoken in the same call only by holding the tool call open, and a held consult blocks the next one [docs-only: `concepts/queue.md`]. Past 25 s it converts to a job without cancelling `main`. How well each provider speaks a late result is unconfirmed, so BRIDGE-S5 tests it [track: gap-voice-brain §2, §4.3].

**What is in `voice`'s head.** A digest in `workspace-voice/USER.md`, under about 3,900 characters, public class only: no third-party names, health, school data or credentials. A plugin service writes it from `main`'s `USER.md` and `MEMORY.md` through `background`, debounced 10 minutes after a file change, at about $0.001 per refresh. A stale digest never produces invented facts: Jorah uses `ask_main` or says it does not know. Adam previews the first one and approves the automation [track: gap-voice-brain §4.7].

**Facts coming back.** "Remember that the arm uses M3 screws" becomes `note_for_main`. One end-of-call phone card shows the exact quote with Keep, Change, Forget. `main` writes only on Keep. Room audio cannot rewrite memory without a tap [track: gap-voice-brain §4.5].

**Failure behaviour**

| Failure | What happens | Evidence |
|---|---|---|
| Relay fails on the Mac app | Falls back to native speech with a visible reason. **The processor changes to Apple**, so the indicator must say so | [docs-only: `nodes/talk/macos-relay.md`; track: brain.md §10 path 13] |
| Relay fails on `jorah-talk` | No fallback. It says it is offline. Robot sessions run only on this client, so no motion can be requested | [track: gap-voice-to-motion §4] |
| Prepaid cap hit | Voice stops with the reason. No other vendor is tried | [track: brain.md §10] |
| Gateway restart mid-job | Job reported as "I lost track of that" or its true state, never "done" | [docs-only: `concepts/session-tool.md`; track: gap-voice-brain §4.2] |
| Haiku or API down | Consult fails aloud. Direct answers still work. No fallback chain, `fallbacks: []` | [track: brain.md §9] |
| Session left open | On the stock apps, a cloud mic and billing run up to 30 minutes per relay session. So daily use waits for `jorah-talk` on the Mac | [track: voice.md §1 finding 8; source: `requireUnifiedTalkSessionConn`] |
| Limited token on the ear | A `--voice-node` token gets `senderIsOwner: false` and only six safe read tools, so the bridge tools should vanish from the consult. Item N1 | [source: `resolveTalkAgentConsultAuthority`, read again today; not run] |

### 4.2 A delegated task

**Case A: typed in Telegram, today's path with stage 0 applied.**

```text
 Telegram long poll > Gateway > main (Opus 5.5 on Claude CLI)
   main has no shell, so it calls sessions_spawn
 > acpx > Claude Code in the OS sandbox
      Mac: Seatbelt.  WSL2: bubblewrap, failIfUnavailable true, allowUnsandboxedCommands false
      Writes only sandbox/ and ~/work. No home reads. No network. No git push
 > result to main > Telegram
```

ACPX routes cannot dispatch to a paired device, so Claude Code cannot be placed on a node [docs-only: `nodes/node-host.md`].

**Worker route, chosen once at M3 from this table [roadmap M3; track: security.md §5].**

| Spike result | Consequence |
|---|---|
| Hooks fire on `claude-cli` (GROW-S13) | `main` may keep guarded tools |
| Hooks do not fire | `main` keeps no outward tools. Outward tools live only in `actor` on the embedded runtime. Re-budget |
| Sandboxed exec fails on `claude-cli` (expected from source reading) | Builder uses a typed `jorah_lab` tool, or the embedded runtime on credits |
| Plugin tools do not reach `claude-cli` | One-entry exec allowlist for `jorah-lab` |
| `sbx` and Apple `container` both fail | Stop and report. Tart or Hyper-V Lab adds effort |

**Case B: started by voice.** `start_job` starts a non-owner turn on a tainted session whose key starts with `agent:main:voice-`. The key is host-set, so a model cannot change it. Inside that session, memory reads are allowed, writes need a phone card, anything outward goes to the phone, and voice cannot approve. Status comes from job records, not a model. Steer is a follow-up turn, because Claude CLI turns take no same-turn steering. Cancel says "cancelled" only after a terminal state [track: gap-voice-brain §2, §4.3, §4.4].

**Case C: a heavy video job after M9.** The sandbox gets no GPU and no exception, because `sandbox-runtime` skips `/dev/*` paths and mentions no `dxg` or `nvidia` [verified: `github.com/anthropic-experimental/sandbox-runtime` `linux-sandbox-utils.ts`; FLOW-T9 confirms on Claude Code itself].

```text
 Adam: jorah-send clip.mov my-slug   shows size, time, free space. Uploads on yes
 SFTP to pc.<tailnet>.ts.net:2222    chrooted xfer-ingest, resumable with sftp -a
 jorah-ingestd                       SHA-256, ffprobe, move to projects/<slug>/source, mode 0440
 Delegated Claude Code               reads source through allowRead, writes edl.json and a job file
 jorah-media (systemd)               validates schema, GPU render: NVENC if FLOW-T8 passes, else libx264
 review page, 8443                   Serve header plus per-review token. Adam approves on the phone
 Adam downloads and publishes        no upload path in the MVP
```

**Case D: a tool Jorah has not got.** `jorah_lab` verbs start an `sbx` microVM with deny-all egress. Install phase: registries only, no private data. Job phase: private data, no network. Output arrives in quarantine and never runs. Promotion needs evals plus Adam's yes [track: growth.md].

**Case E: an iOS build.** Request reaches a node in Mac user `jorah-build`. Preferred route is a typed MCP tool with `system.run` still denied; the runner-up is root-owned wrappers in `/usr/local/libexec/jorah` on an allowlist. K10a decides. The IPA stays on the Mac at `/Users/Shared/jorah-handoff/<run-id>`. Adam uploads with Transporter. A build result claims "build" tier only [track: gap-post-cutover §5, §6; topology.md §9].

**Data-flow limits.** File Transfer is capped at 16 MiB per file [docs-only: `nodes/file-transfers.md`]. Taildrop and Tailscale SSH do not work with tagged devices, so no media path uses them [verified: `tailscale.com/kb/1106/taildrop`, `kb/1193/tailscale-ssh`]. Live vision frames never cross machines, only events do. Footage for editing is a separate action Adam starts.

### 4.3 A robot command

**Three permissions, each answering a different question** [track: gap-voice-to-motion §1, §4].

| Check | Question | Who | Scope |
|---|---|---|---|
| Physical key | May this arm have power? | Adam's hand | Until turned off |
| Phone tap, `robot_request_arm` | May Jorah move it for 20 minutes? **The authority** | Adam, `allowedDecisions: ["allow-once","deny"]` | One session |
| Spoken yes, Gateway gate | Is that the right target? A check, not an authority | Anyone in the room | One `plan_id`, 120 s, single use |

**Tool names matter.** The Gateway's spoken gate decides by tool name: an unknown tool counts as mutating only if its name starts with `message_`, contains `send`, or ends in `_actions` [source: `dist/tool-mutation-BTW6eoAN.mjs`]. `robot_pick` would not fire it, so the executing tool is `robot_send_goal(plan_id)`. MOTION-T3 proves this at every upgrade. PR #159697 removes this gate after 2026.10.9 [verified: GitHub compare API, track: gap-voice-brain §2], so **the upgrade that removes the gate must move the per-plan check into `jorah-robot-guard` first.** If the gate does not fire, the guard requires a tap on every goal. Never patch the gate.

```text
 "Jorah, put the red cube in the bin"
 1 wake and end of turn            jorah-talk on the Pi, or Mac as a second ear       about 0.8 s
 2 relay and consult               sessionKey agent:robot:arm during an enabled session  1 s
 3 robot agent turn                fast API model                                      1 to 2 s
 4 robot_plan_pick("red cube")     node.invoke > mcp.tools.call.v1 > bridge on the Pi     500 ms
     local detector, annotated image, plan_id, expires in 60 s. Frames stay local
 5 robot_send_goal(plan_id)        BLOCKED by the gate. Guard posts the preview
     "Red cube by the mug. Yes?"
 6 "Yes"                           transcript grants one use, bound to these arguments
 7 robot_send_goal(plan_id)        returns a job id at once
     bridge checks: key, session, plan, ear alive, not HALTED, inside the box          100 ms
 8 bridge > 30 Hz servo commands   tone and beacon on, Jorah goes quiet                 200 ms
 Result: observed pose, photo, any fault. Never only what was asked
```

Targets: question asked within 5 s of speech ending, first motion within 1.5 s of the yes. Every failure here means no motion. The MCP call has a 125 s Gateway timeout and runs sequentially [source: `dist/node-commands-Bxo-2Y4j.mjs`], which is why the goal returns at once and why a model-called `robot_stop` is not a stop path.

**The stop path is separate and never touches the Gateway.**

```text
 "Stop"
 XVF3800 > ALSA > jorah-ear (no network)      stop.tflite        360 ms
 Unix datagram, sent 3 times                                       5 ms
 robotd: cancel job, read Present_Position,
 sync-write Goal_Position = present, latch HALTED                 50 ms
 Servos decelerate                                               100 ms    total about 515 ms
   still moving at T+500 ms   > relay off
   bridge wedged              > heartbeat silent 200 ms > relay off
   held 120 s, nobody acting  > warning tone, relay off
```

All [inference]; no accuracy figure exists for this model, so MOTION-T1 decides. Motion is refused unless `jorah-ear` sends heartbeats at 5 Hz with a mic level, so a muted or dead ear means no motion. Voice cannot clear `HALTED`; a new tap can. **The E-stop is the safety function. Spoken stop is a convenience. Nothing here is safety-rated** [track: gap-voice-to-motion §6, security.md §15].

**Mobile base (M25).** Same shape, with `base_send_goal(plan_id)`. A base microphone is useless next to tracks, so stop becomes a lease: signed heartbeats from a room ear at 5 Hz, three missed and the base halts. Firmware watchdog set to about 300 ms with `{"T":136,"cmd":300}`, down from 3,000 ms. A radio kill that does not depend on Wi-Fi is required before the first voice-driven move [track: gap-voice-to-motion §8].

**Seeing and hearing on the arm.** An array on the fixed base and the wrist camera at about 1 fps at most through tools. No LiveKit or Pipecat for the arm, because the models take no true live video and the relay carries audio only [track: gap-voice-to-motion §9, vision.md §1]. LiveKit's ESP32 SDK stays a candidate only for a device with no Pi, and its README says Developer Preview [track: openclaw-fit.md §7].

### 4.4 What each provider receives, by data class

| Data class | Goes to | Never goes to | Gate |
|---|---|---|---|
| Adam's room audio | Realtime provider while open. Apple on fallback | Disk as raw audio, by default | Idle close, named indicator |
| Bystander audio | Nowhere: guest mode closes Talk, typed only | Realtime, native fallback | Guest mode test |
| Calendar, mail, messages | Anthropic API or local reader, then a card | Realtime, Telegram text | Canary test at M4 |
| School data | Local or Anthropic API, then a card | Realtime, Telegram, Google | Role and terms check |
| Frames with anyone but Adam | API or local | Max login | Local person count routes it |
| Frames with Adam alone | Max, once the training setting is confirmed off | Disk until exec boundary holds | Adam checks the setting |
| Profile files | Realtime provider every session | | Thin workspace, reviewed diff |

**Canary test** [track: gap-private-data §6]. Plant `Zeltrova-7Q` in a test calendar event, test mail and memory entry. Ask over voice. Pass only if the canary is absent from all outgoing provider events and present on the card. Repeat after a voice switch and after a relay drop. Do not state "not sent to OpenAI" until this passes on a device.

---

## 5. Topology

### 5.1 Stages

**PC first since 2026-11-03: `10-roadmap.md` section 2a wins over the rest of this section.** No Mac `jorah` user, and no Windows Pro or BitLocker unless a P1 or P5 check forces it. The room ear and rescue bot live on a Pi 5.

| Stage | Gateway | Mac | PC | Pi 5 | Reach |
|---|---|---|---|---|---|
| Today | `adam`, foreground, `127.0.0.1:43181` | CLI only | n/a | n/a | Telegram, loopback |
| P0 (M0) | Same, with stage 0 config | Same | n/a | n/a | Same |
| P1 (M7) | Stays on the Mac | Same | Staging profile, fresh test bot, 7-day soak | n/a | Tailnet for setup |
| P2 (M9) | PC, `jorah-gw` | Adam's own Claude Code. Old state stopped | Real Gateway | Rescue bot | `wss://pc.<tailnet>.ts.net` |
| P3 (M20) | PC | Optional client when open | Local voice stack | Same | iPhone through the relay |
| P4 (M10) | PC | Same | Same | Room ear | Same |
| M15 to M17 | PC | Same | Same | Arm's Pi decided at M15 | Pi as tagged node |
| M19 | PC | `jorah-build` iOS node, only while open | Fusion if Home allows it | Same | Same |

### 5.2 Accounts and boundaries

| OS | Account | Rights | Owns | Autologon |
|---|---|---|---|---|
| macOS | `adam` | Admin | OpenClaw.app under profile `jorah-app`, Voice Wake, `jorah-talk`, Serve on the interim route, `jorah-adam-data` from M6 | n/a |
| macOS | `jorah` | Standard | Gateway until M9, then iMessage bot and rescue bot | No |
| macOS | `jorah-build` | Standard, `_developer` | Headless iOS node, Development certificate only | No |
| Windows | `adam` | Admin | Own use, BitLocker recovery | No |
| Windows | `jorah-svc` | Standard | WSL distro and boot task, VHDX | No |
| Windows | `jorah-desk` | Standard | Node host, Fusion, Resolve, COM ports, leased console | No at first |
| Windows | `jorah-lab` | Standard | `sbx` microVMs, typed MCP | No, Password task |
| Windows | `jorah-talk` | Standard | Mic and speaker client, S4U task | No |
| WSL | `jorah` | No root, no sudo after install | Gateway, Claude CLI | n/a |
| WSL | `jorah-media` | Service | GPU worker | n/a |
| WSL | `xfer-ingest`, `xfer-desk`, `xfer-lab` | Chrooted SFTP, no shell | Their chroots | n/a |
| Pi | `robotd`, node user, `jorah-ear`, `jorah-talk` | Only `robotd` is in `dialout` | Bridge, node, stop, talk | n/a |

**Why a separate macOS user is not enough alone.** `/Users/adam` is `drwxr-x---+` and group `staff` can read and traverse it, 63 top-level items are readable, and `OneDrive` is 777 [track: security.md Verification]. Close the home first with Adam's yes.

**Why WSL2 flags are not a boundary alone.** Microsoft says drives can still be mounted by hand, and root can edit `wsl.conf`. So `jorah` has no root and no sudo, and SEC-T17 must pass in full [verified: `learn.microsoft.com/en-us/windows/wsl/wsl-config`; track: security.md §11].

### 5.3 Decisions that fix the PC shape

| Fact | Consequence | Evidence |
|---|---|---|
| Claude Code sandbox runs on macOS, Linux and WSL2. Native Windows runs commands unsandboxed | Gateway goes in WSL2 | [verified: `code.claude.com/docs/en/sandboxing`] |
| Worker container isolation unsupported on native Windows | Same | [docs-only: `nodes/session-hosting.md`] |
| Fusion has no Linux desktop build. Windows 10 22H2+, macOS 14+ | GUI stays on Windows or Mac | [track: topology.md §2 fact 14, search summary only] |
| No built-in wake word on Windows or Linux. PR #1071 closed unmerged, #1124 closed not planned | Own client | [verified: `openclaw-windows-node` GitHub] |
| `talk.ptt.*` is turn-based, has no target, no handler in the CLI node or in Hub's source at HEAD or stable, despite `platforms/windows.md` | Own client uses `talk.session.*` | [source: `dist/nodes-BBBXZ_Tl.mjs`; verified: `git grep` of Hub; track: gap-room-and-pc-ear §2] |
| Windows Tailscale client disconnects when nobody is signed in unless Run unattended is on | `tailscale set --unattended=true` is mandatory | [verified: `tailscale.com/kb/1088/run-unattended`] |
| Tailscale says do not run on both Windows and WSL | Tailscale on the host only | [verified: `tailscale.com/kb/1295/install-windows-wsl2`] |
| WSL can stop 15 to 20 s after the last terminal closes, open issue #13416, unconfirmed on 3.0.x | Boot chain plus a 7-day soak | [verified: `github.com/microsoft/WSL/issues/13416`] |

**Runner-up:** a small always-on Linux box for the Gateway, with the Windows PC as GPU and desktop node. It wins if the 7-day soak fails, the PC is a daily gaming machine, or TOPO-S2 fails. The migration runbook is the same [track: topology.md §4].

### 5.4 Network

Tailscale identity is per machine, not per OS user. Tag the PC and the Pi. Keep Mac and iPhone as user devices, because tags are for machines and a tagged phone would lose the Serve identity headers the review page uses [verified: `tailscale.com/kb/1068/tags`, `kb/1312/serve`; track: gap-post-cutover §5].

```powershell
# Windows, tailnet device owner. Adam approves.
tailscale set --unattended=true
tailscale serve --bg --https=443  http://127.0.0.1:43181
tailscale serve --bg --tcp=2222   tcp://127.0.0.1:2222
tailscale serve --bg --https=8443 http://127.0.0.1:<review-port>
```

```json5
// Tailnet policy. Replaces allow-all. Addresses and login are placeholders. Adam approves the diff.
{
  "groups":    { "group:owner": ["adam@example.com"] },
  "tagOwners": { "tag:jorah-pc": ["group:owner"], "tag:jorah-arm": ["group:owner"] },
  "hosts":     { "adam-mac": "100.x.y.z", "adam-iphone": "100.x.y.w" },
  "grants": [
    { "src": ["group:owner"],  "dst": ["tag:jorah-pc"], "ip": ["tcp:443", "tcp:22", "tcp:3389"] },
    { "src": ["adam-mac"],     "dst": ["tag:jorah-pc"], "ip": ["tcp:2222", "tcp:8443"] },
    { "src": ["adam-iphone"],  "dst": ["tag:jorah-pc"], "ip": ["tcp:8443"] },
    { "src": ["tag:jorah-arm"],"dst": ["tag:jorah-pc"], "ip": ["tcp:443"] },
    { "src": ["tag:jorah-pc"], "dst": ["adam-mac"],     "ip": ["tcp:22"] }
    // Interim only, remove at cutover: { "src": ["adam-iphone"], "dst": ["adam-mac"], "ip": ["tcp:443"] }
  ],
  "tests": [
    { "src": "adam@example.com", "accept": ["tag:jorah-pc:443"] },
    { "src": "adam-iphone",  "accept": ["tag:jorah-pc:8443"], "deny": ["tag:jorah-pc:2222"] },
    { "src": "tag:jorah-pc", "accept": ["adam-mac:22"], "deny": ["adam-mac:5900", "adam-mac:445", "adam-iphone:443"] }
  ]
}
```

Syntax is from `tailscale.com/kb/1324/grants` and `kb/1337/policy-syntax`. Whether a tag `src` to a host alias `dst` behaves as written is FLOW-T1. Personal is free and non-commercial with 50 tagged resources; a business needs Standard at $8 per user per month [verified: `tailscale.com/pricing`]. ESP32 devices stay off the tailnet on a separate Wi-Fi.

**`gateway.trustedProxies: ["127.0.0.1"]` warning.** A loopback entry trusts same-host processes to supply proxy attribution, so token auth must stay on. On WSL NAT "same host" includes anything on Windows that can reach localhost [docs-only: `gateway/tailscale.md`; inference]. Loopback node pairing can also be auto-approved, so TOPO-S2 checks whether a Windows-side node triggers an approval. `jorah-talk` connects through the Serve URL, not WSL's localhost forward, for this reason.

### 5.5 PC configuration

`%UserProfile%\.wslconfig` for `jorah-svc`, written before the distro is created [verified keys: Microsoft wsl-config; track: topology.md §4].

```ini
[wsl2]
memory=24GB              ; default is 50% of RAM. Size to the PC
swap=8GB
networkingMode=nat       ; keeps the Gateway off the LAN
firewall=true
guiApplications=false
nestedVirtualization=false
; distributionInstallPath=D:\\wsl   ; recommended tier only, must be set before creating the distro
[general]
instanceIdleTimeout=-1   ; documented, -1 disables auto shutdown
[experimental]
sparseVhd=true
```

`/etc/wsl.conf` in `jorah-gw`. **`mountFsTab=false` wins over `topology.md`** [track: security.md §11, gap-post-cutover §5].

```ini
[boot]
systemd=true
[automount]
enabled=false
mountFsTab=false
[interop]
enabled=false
appendWindowsPath=false
[user]
default=jorah
```

Boot chain [docs-only: `platforms/windows.md`, adapted]:

```bash
# Inside jorah-gw, as jorah, before sudo is removed
sudo apt-get install -y dbus-x11 bubblewrap socat
sudo loginctl enable-linger jorah
openclaw --profile jorah gateway install
sysctl kernel.apparmor_restrict_unprivileged_userns   # if 1, add the AppArmor profile from the Claude Code sandbox docs
```

```powershell
# Admin PowerShell. /ru must be the distro's owner, not SYSTEM. Adam runs this.
schtasks /create /tn "JorahWSLBoot" /tr "wsl.exe -d jorah-gw --exec dbus-launch true" /sc onstart /ru jorah-svc
```

Fallback if the distro idles out: a Windows task running `wsl.exe -d jorah-gw --exec sleep infinity`. That report covers about 20 minutes of uptime, so the soak must prove it [verified: issue #13416].

**BitLocker:** TPM only, so a power cut recovers unattended [inference]. **Windows Update:** a device with no signed-in user is restarted regardless of no-auto-restart policy, so plan a weekly window and a health script after each reboot [verified: `learn.microsoft.com/en-us/windows/deployment/update/waas-restart`].

**PC check first.** PC specs are unknown. Adam runs this in admin PowerShell and shares the output, from `topology.md` §15. Buy nothing before it.

```powershell
winver
Get-ComputerInfo | Select-Object OsName,OsVersion,OsArchitecture,CsTotalPhysicalMemory,CsProcessors
Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size
Get-Volume | Select-Object DriveLetter,SizeRemaining,Size
Get-Tpm | Select-Object TpmPresent,TpmReady
wsl --version
Get-NetAdapter | Select-Object Name,LinkSpeed,Status
systeminfo | findstr /i "Virtualization Hyper-V"
```

Also check: Restore on AC and Wake-on-LAN in BIOS, Ethernet, edition (Home blocks Hyper-V and Windows Sandbox), free USB ports near where Adam talks, PSU wattage, gaming use, noise and who can touch it.

| Tier | CPU | RAM | GPU | Disk | Gets you |
|---|---|---|---|---|---|
| **Minimum** | 6 cores, virtualization | 32 GB | Any NVIDIA 8 GB, or none with cloud voice | 1 TB NVMe, default distro path | Gateway, cloud voice and brain, light desktop |
| **Recommended** | 8+ | 64 GB | NVIDIA 16 GB | 2 TB NVMe plus a second SSD | Local STT and TTS, one moderate local model, Fusion, 4K Resolve, detector at about 4 to 12 ms [track: vision.md §5.1] |
| **Stretch** | 12+ | 96 to 128 GB | 24 GB or more | 4 TB plus data disk | Local LLM alongside media. `gemma4:26b` or `qwen3.6:27b` need 18 to 19 GB [verified: `ollama.com/library`] |

GPU prices are distorted. RTX 5060 Ti 16 GB is about €775 to 855, RTX 5070 Ti €1,176, RTX 5090 above €5,000 with the November price unconfirmed [track: topology.md §15]. A local GPU saves only about $2 to $15 a month in tokens, so it does not pay for itself on savings [track: brain.md §6]. It is justified only by privacy, offline use or a failed tier check.

### 5.6 The Mac after the move

| Situation | Behaviour | Evidence |
|---|---|---|
| Lid open, on power | Stays awake (`sleep 0` on AC) | [measured] |
| Lid closed, power, external display or dummy, keyboard and mouse approved | Runs | [verified: `support.apple.com/en-us/102282`] |
| Lid closed, no display | Sleeps. Nodes disconnect. Tailscale cannot wake it | [inference] |
| `pmset disablesleep` | Not in `man pmset`. Do not use | [measured] |
| Asleep or away | Jorah says "waiting for the Mac". Never pretends work happened | [docs-only: `nodes/session-hosting.md`] |
| After a reboot | FileVault blocks everything. SSH unlock must come over the LAN, because the Standalone client has no tunnel before login | [verified: `tailscale.com/kb/1065/macos-variants`; docs-only: Geerling] |

**Pick:** when home, dock it with Charge Limit 80. Wake-on-LAN is sent by the Windows node, because WSL NAT cannot broadcast to the LAN [inference]. Must-stay-on-Mac: iMessage, Xcode, Apple Speech wake.

**If the MacBook travels daily,** keep the order and price a Mac mini for iMessage and builds [track: topology.md §8].

### 5.7 Where each job runs after M9

| Job | Machine and user | Boundary | GPU | If it fails |
|---|---|---|---|---|
| Brain, memory, channels | `jorah-gw`, `jorah` | No `exec` on main, hardened distro | No | Rescue bot, manual only |
| Delegated Claude Code | `jorah-gw`, `jorah` | Bubblewrap, no network | No | No fallback outside the sandbox |
| Transcription, render | `jorah-gw`, `jorah-media` | systemd, `PrivateNetwork=yes`, validated EDL only | NVENC if FLOW-T8 passes | `libx264` in the same unit, never Windows `ffmpeg.exe` |
| Lab, untrusted tools | Windows `jorah-lab` | `sbx` microVM | None | Mac `sbx`, then Hyper-V VM |
| Code CAD | `jorah-gw`, `jorah` | Bubblewrap | No | n/a |
| Fusion, Resolve | Windows `jorah-desk`, leased console on Adam's yes | Standard user | Native | Mac under a dedicated user |
| iOS | Mac `jorah-build` | Wrappers or MCP, no distribution cert | n/a | Wait for the Mac |
| Vision sidecar | Whichever machine has the camera | Frames stay local | Local | Camera off |
| Arm | Pi, `robotd` | OS user separation | No, heavy vision on PC | No motion |
| LAN robot devices | Windows `jorah-desk` bridge, node MCP | Firmware and bridge | n/a | Device stops itself |

**PC cameras need a session.** Windows services run in session 0 and `jorah-desk` has no autologon, so a PC camera is live only during a session [track: gap-post-cutover §9]. Vision work stays on the Mac or a leased session unless Adam decides otherwise.

---

## 6. Migration

### 6.1 Mac: `adam` to `jorah` (M1). Tested first, moved once.

**Who: Adam runs every `sudo`, password and login step. Claude prepares and reads results.** Rule: 4-hour cap on the spike. Do not pair the app until the Gateway has moved.

```bash
# Adam, after a yes on each. Password is prompted, never on the command line.
chmod 700 /Users/adam                      # then check Adam's own apps and sharing still work
sudo sysadminctl -addUser jorah -fullName "Jorah" -home /Users/jorah -password -
sudo createhomedir -c -u jorah 2>/dev/null || true
dscl . -read /Groups/admin GroupMembership  # jorah must NOT be listed
id jorah                                    # note group membership
sudo fdesetup list                          # needs root. Note whether jorah can unlock FileVault
sysadminctl -secureTokenStatus jorah        # FileVault is on [measured]
# Log in once through Fast User Switching, to finish Setup Assistant and create the login Keychain
```

**Prove the boundary before moving anything (SEC-T13).** Adam first creates a canary file at `~/Documents/jorah-canary.txt`. Each line must be denied:

```bash
sudo -iu jorah cat ~adam/Documents/jorah-canary.txt
sudo -iu jorah ls ~adam
sudo -iu jorah cat ~adam/.gitconfig
sudo -iu jorah ls ~adam/.claude
sudo -iu jorah touch ~adam/OneDrive/x
sudo -iu jorah test -w /opt/homebrew/bin; echo $?   # expected 1
```

**Spike a scratch Gateway as `jorah`, on its own profile `jorah-spike`, port 43301, never the live state.** The exact script is roadmap steps 1.4 to 1.6b. The app under `adam` uses a separate profile, `jorah-app`, set up with `configure-remote` before first launch, because a named profile needs the listener to belong to that profile's Gateway service, and a fresh profile would host its own [docs-only: `platforms/mac/bundled-gateway.md`, `platforms/mac/remote.md`]. **Do not open it from Finder.** Nothing should listen on 18789 [track: apps.md Verification]. **Untested. Record the result here and in `docs/evidence/m1/spike.md`.**

**Before the move, session M1-A2:** `scripts/deploy-workspace.sh`, `ops/launchd/gateway-env.sh` and `ops/bin/oj` written and tested on a scratch directory (`09` 3.3).

**On pass, move.** **This table is the single procedure.** Roadmap 1.7 and `03` W1.4 point here. From step 2 on, live commands go through `oj`, and Adam runs them. "In `jorah`'s Terminal" means logged in through Fast User Switching, not `sudo`.

| Step | Who | Action | Check |
|---|---|---|---|
| 1 | Claude, Adam's yes | Set `gateway.port` to 43181 explicitly, already done by stage 0. `openclaw node run` defaults to 18789, so always pass the port | `config get gateway.port` |
| 2 | Adam | Stop the foreground Gateway. `openclaw --profile jorah backup create --output ~/Backups/openclaw --verify`. **Then at once `mv ~/.openclaw-jorah ~/.openclaw-jorah.pre-move-$(date +%Y%m%d)`,** so a stale write fails loudly, and no app shares a directory with it | Verify passes. `ls -d ~/.openclaw-jorah` finds nothing |
| 3 | Adam | Copy archive to `/Users/Shared`, restrict to `jorah` by ACL. As `jorah`: `backup restore <archive> --target ~/openclaw-restored`. Restore never activates in place, so move assets per `manifest.json`, then delete the shared copy | Files present |
| 4 | Adam, a yes | Workspace transfer, no clone, because the runtime account holds no GitHub credential and after `chmod 700` it cannot read Adam's checkout. As `adam`, from the merged commit: `scripts/deploy-workspace.sh --yes`, which streams `git archive <commit> workspace workspace-voice workspace-background scripts config ops \| sudo -u jorah tar -x -C /Users/jorah/jorah`. Then move the restored private files (`USER.md`, `MEMORY.md`, `memory/`, `DREAMS.md`) into `/Users/jorah/jorah/workspace`. Adam's dev clone stays in `~/Documents` | `.deployed-commit` matches. `ops/launchd/gateway-env.sh` exists |
| 5 | Claude previews, Adam runs with `oj` | **A path patch, not `configure.sh`,** which does not touch these and would reset other things. Preview and apply, all to `/Users/jorah/...`: `agents.defaults.workspace`, `agents.entries.main.workspace`, `plugins.entries.acpx.config.cwd`, `secrets.providers.macos_keychain.command`, `logging.file`, `env.vars.CLAUDE_CONFIG_DIR`. Then `setup-permissions.sh` alone as `jorah`. Move `~/work` under `jorah` | `oj config file` prints `/Users/jorah/.openclaw-jorah/openclaw.json`. `oj config get agents --json \| grep -c /Users/adam` prints 0, and the same for each other path |
| 6 | **Adam, in `jorah`'s Terminal** | `CLAUDE_CONFIG_DIR=$HOME/.claude-jorah claude auth login`. Keychain entries do not move between users, so also re-create `jorah-gateway-token` and `jorah-telegram-bot-token` in the `jorah` login Keychain, and install the resolver at `/Users/jorah/.jorah/bin/` [`03-security-and-privacy.md` W0.5, W1.4] | `switch-brain.sh status --probe` shows `ACTIVE ROUTE: cli`. `oj secrets audit --check --allow-exec` clean |
| 7 | Claude prints, Adam runs | Re-download the embedding runtime. The `tools` tree is excluded from archives | Memory search finds a known fact |
| 8 | **Adam, in `jorah`'s Terminal, a yes** | Roadmap 1.8: `gateway install --port 43181 --runtime-path "$PINNED_NODE" --wrapper ~/jorah/ops/launchd/gateway-env.sh`. It has no dry run, and it installs and starts, so compare against a hand-written plist. Confirm `CLAUDE_CONFIG_DIR` reaches the process and no `ANTHROPIC_API_KEY` is set | Logs show `~/.claude-jorah` in use. `plutil -p` matches |
| 9 | **Adam**, as `adam` | `tailscale serve --bg --https=443 http://127.0.0.1:43181`. A standard user cannot read `/Library/Tailscale/sameuserproof-*`, so `jorah` does not use `tailscale.mode: serve`. `oj config set gateway.trustedProxies '["127.0.0.1"]' --strict-json` | iOS shows **Full** later |
| 10 | Adam | Keep `~/.openclaw-jorah.pre-move-*` under Adam, stopped, for two weeks | Stopped |

**Acceptance (signed-in device):** Telegram reply with no new pairing. Ask to run `whoami`: refused by stage 0, offers delegation. `/acp doctor`, then a delegated task, works and cannot read outside, by SEC-T9's M1 version. `oj status` shows one Gateway and the right state directory. Write down who must log in after a reboot.

**If it fails:** the spike already uses `--direct-url`. Wake proceeds under Adam's user with stage 0, voice only, no connectors, and Adam chooses between a VM and an earlier PC before M3 finishes. Never decided silently.

Open points to test: whether the tunnel stays up for a `jorah` LaunchAgent when `adam` logs out; Docker Desktop's socket from `jorah`, since it is set up for `adam` [unverified; track: topology.md §7].

### 6.2 PC staging (M7)

**Order:** Adam shares the PC check. Then TOPO-C2, C3 and so on. **First hour on the PC is EAR-E1,** because it decides where the room ear lives.

| Step | Who | Action | Pass |
|---|---|---|---|
| 1 | **Adam** | Windows 11 Pro, updates, users, BitLocker, Tailscale tag, unattended, `.wslconfig` | After a reboot with nobody signed in, the PC answers on the tailnet |
| 2 | Claude, with Adam at the keyboard | WSL 3.x, distro `jorah-gw`, section 5.5 config, then remove sudo from `jorah` | SEC-T17: `ls /mnt/c`, `cmd.exe /c ver`, `sudo -n true`, `mount -t drvfs C: /mnt/c`, write to `/etc/wsl.conf` all fail |
| 3 | Claude | **EAR-E1:** throwaway program, no Jorah credentials, S4U task as `jorah-talk`. Cold reboot nobody signed in, `adam` signed in, `jorah-desk` leased, locked | Non-silent PCM and an audible tone in all four, three reboots running, and the Serve URL reachable. Fail: go to the Pi, never autologon |
| 4 | **Adam creates the bot at BotFather and stores its token,** Claude does the rest | New profile, **fresh test bot**, no restored state. 7-day soak | Log shows no idle kills, including a no-login reboot |
| 5 | Claude | Claude Code in WSL | `/sandbox` clean. `~/.ssh` read and outbound blocked. `failIfUnavailable` refuses when `bwrap` is removed |
| 6 | Claude | **TOPO-S2 and S2b:** Serve into WSL with `jorah-svc` not signed in, node join from `jorah-desk`, iOS Full. Run `appendAudio`-sized frames for 10 min | Works after reboot. Direct path adds under 25 ms P50 and 75 ms P90 over loopback. `tailscale status` shows direct |
| 7 | Claude | **TOPO-S3:** node host in `jorah-desk`, `openclaw plugins enable cua-computer`, `openclaw doctor --lint --only cua-computer/driver-artifacts` | No findings. Notepad test |
| 8 | Claude | **FLOW-T8, replaces TOPO-S5:** real `h264_nvenc` encode as a `jorah-media` systemd unit with `PrivateNetwork=yes`, `DeviceAllow=/dev/dxg`, `ProtectHome=yes`. Then the same in a delegated Claude Code run (FLOW-T9, expected to fail) | Output plays, yes or no recorded |
| 9 | Claude | **FLOW-T6, T7, T10, T13** on real sockets | 45 GB at 30 MB/s or better on wired LAN, hashes match. Each Windows user sees only its chroot |
| 10 | Claude | **K10b:** `sbx` 0.50.1+ as `jorah-lab` after reboot, nobody signed in. MicroVM cannot reach `100.x` or `127.0.0.1:2222` | Create, run, remove. Else Mac Lab, then Hyper-V VM |
| 11 | Adam | Plug meter baseline | Written down |
| 12 | Adam | **Written decision:** PC passes, parts needed, or fork to Linux box or Mac mini | In `docs/adr/` |

K10a runs on the Mac before this stage, see section 10. Stage A of the file-flow test (FLOW-T1 to T5) also runs before the PC, on a disposable tagged node.

### 6.3 Cutover (M9)

**What moves** [verified: `openclaw backup create --dry-run --json` today; docs-only: `install/migrating.md`].

| Artifact | Method | After restore |
|---|---|---|
| `openclaw.json` | Archive | A previewed path patch, as 6.1 step 5, set port and trusted proxies. `configure.sh` only with `--diff` |
| `state/openclaw.sqlite` (pairing, cron, voicewake, auth store) | Archive only, **never raw copy** | None |
| Agent DBs, workshop skills, `wiki/main`, workspace | Archive | Check paths inside skills |
| Repo | `git clone` | Needs a first commit |
| Telegram token, DM pairing, offset | Archive | Check token without printing it. Should not need re-pairing. Telegram keeps updates up to 24 h |
| Gateway token and other SecretRefs | **Re-point** | The stage 0 provider calls macOS Keychain, which WSL does not have. Move to the PC store first: 1Password service account per `03-security-and-privacy.md` §6 (price unverified), or `openclaw secrets store` for low-value keys |
| `jorah-talk` on the Mac | Reconfigure | New token, `wss://pc.<tailnet>.ts.net`. Rerun EAR-E0's script |
| `~/.claude-jorah` extras, `~/.jorah-lab` | restic | `openclaw backup` does not cover them [`09-engineering-and-ops.md` §1] |
| **Claude login** | **Do not move** | `claude auth login` on the PC, stored at `~/.claude-jorah/.credentials.json` mode 0600 |
| Claude settings | Regenerate | `setup-permissions.sh`. Remove Mac-only paths |
| Plugin `node_modules` | Reinstall | `openclaw doctor --fix` |
| Embedding runtime | Re-download | macOS binary does not move |
| Embedding model, `models/` 313 MB | Archive | No reindex expected [inference] |
| Exec approvals | Archive, then **reset** | Mac paths are meaningless |
| Cron jobs | Archive | List and review before enabling. Adam reconfirms each |
| Device pairings | Archive | Re-enrol nodes with `devices join-code`, remove stale rows |
| `~/.jorah-brain` | `git bundle` | Mac copy becomes read-only |
| `~/work` clones | Re-clone | `~/work/cognio` is local-only, push stays disabled |

**Runbook. Adam approves the window. Rehearse first with staging and the second bot.**

1. Mac: `openclaw --profile jorah gateway stop`. Confirm stopped.
2. Mac: `openclaw --profile jorah backup create --output <dir> --verify`, then `backup verify` on the copy after transfer.
3. PC in WSL: same OpenClaw and Node. Never run an older build on migrated data. `backup restore <archive> --target ~/openclaw-restored`, move per `manifest.json`.
4. The previewed path patch from 6.1 step 5, then `setup-permissions.sh` alone. **Adam logs Claude in, and enters the PC secret store's token.** Re-download the runtime. `openclaw --profile jorah secrets audit --check --allow-exec`, `doctor`, `gateway install`, start.
5. Prove: Telegram reply with no pairing, `/acp doctor`, sandboxed delegated task, `switch-brain.sh status --probe`, memory search, one Gateway in `openclaw status`, `main`'s fallback chain still empty.
6. Serve. Re-enrol Mac and iPhone. On Mac: `openclaw-mac primary set --direct-url wss://pc.<tailnet>.ts.net --token-file <file>`.
7. Remove the interim grant. Keep Mac's old state stopped for two weeks.

**Rollback.** Before step 5 passes: stop PC, start Mac. After the PC takes real traffic: state has diverged, so back up the PC, restore on the Mac, accept the gap. **Never run both.** Two pollers on one bot token conflict [inference: standard Telegram behaviour].

**Acceptance, recorded by tier:** reboot with nobody signed in and Telegram replies with no re-pairing. Wake on the Mac reaches the PC brain. Run the "Mac through Serve" path of EAR-E2 and compare with the M2 baseline, because reaching the brain is not a latency claim. Brief runs with the Mac asleep. Seven clean days and one verified restore.

### 6.4 Failover and backups

**Pick: manual promotion with a Mac rescue bot.** Automatic takeover is rejected: split brain could double-fire cron, double-answer channels and drive a robot twice [track: topology.md §13]. Runner-up: read-only Mac with no promotion, until one drill has passed.

| Stage | Behaviour |
|---|---|
| PC healthy | Mac is a node. Rescue bot idle except a health probe, which is a schedule Adam approves |
| PC unreachable | Rescue bot says so, offers Wake-on-LAN. Main bot messages wait up to 24 h |
| PC down long | Adam says "promote". Mac checks the PC is off, or tells Adam it cannot. Restores the last verified archive as `jorah` |
| PC back | Fence the PC's Gateway first. Back up Mac, restore on PC |

Rescue bot: no main bot token, no real channels, read-only snapshot, no robots. Profile `rescue`, base port at least 120 away [docs-only: `gateway/multiple-gateways.md`].

| Layer | What | How | Where |
|---|---|---|---|
| 1 | Full encrypted archive daily, on a yes | `openclaw backup enable --to <location> --every 24h --keep-daily 7 --keep-weekly 4 --keep-monthly 12` | Second disk, `filesystem` location |
| 2 | Copy to Mac | Restricted SSH upload key | `/Users/jorah/backups` |
| 3 | Offsite, if Adam wants it | restic, encrypted before upload. `backup --to` has no SFTP provider, and `--output` is plaintext | Hetzner Storage Box BX11, about €4 a month plus an unknown setup fee [track: engineering.md §10] |
| 4 | Learning history | `snapshot-brain.sh` | Local git. **Not a backup**: no auth, sessions, config or cron |
| 5 | Media | Not in archives. Originals stay with Adam | Own policy |

Passphrase: `OPENCLAW_STORAGE_PASSPHRASE` from a secret store, with Adam's offline copy. A backup is not proven until restored: `openclaw backup verify` plus a staging restore monthly, on a yes.

---

## 7. Compatibility

### 7.1 Capabilities by platform

Yes, no, limited, `?` = spike needed. Win = native Windows.

| Capability | Win | WSL2 | Mac | iPhone | Watch | Android, Wear | Linux, Pi | ESP32 | Note |
|---|---|---|---|---|---|---|---|---|---|
| Gateway | M2 Alpha | **Pick**, M3 Beta | Interim, M4 | no | no | no | M4 | no | 1 |
| Claude CLI brain | yes | yes | yes | no | no | no | yes | no | |
| Delegated Claude Code sandbox | **no** | yes | yes | no | no | no | yes | no | 2 |
| Claude Code placed on a node | no | no | no | no | no | no | no | no | 3 |
| Worker container isolation | no | ? likely | yes | no | no | no | yes | no | 4 |
| Exec on node | limited | n/a | yes | no | no | no | yes | no | 5 |
| Node-hosted MCP | ? on `claude-cli` | n/a | ? on `claude-cli` | no | no | no | ? on `claude-cli` | no | 6 |
| Built-in wake word | **no** | no | yes, macOS 26+, `en-US` | best effort | no | foreground | no | custom | 7 |
| Native Talk | no | no | yes | yes | one turn | yes | no | n/a | 8 |
| Realtime relay Talk | through own client | Gateway side | yes, local opt-in | yes | no relay: WebRTC with `gateway-control-v1` | yes | own client | adapter | 9 |
| `talk.ptt.*` | **not in Hub source** | n/a | not documented | yes | no | ? | no handler in CLI node | no | 10 |
| `jorah-talk` | ? EAR-E1 | no | yes, EAR-E0 at M2b | no | no | no | yes | through adapter | 11 |
| Realtime idle close | own client | n/a | **not in the app**, own client | none found | ? | ? | own client | adapter | 24 |
| Video Talk | browser | no | browser | browser | no | browser | browser | no | 12 |
| Camera commands | Hub | no | yes, off by default | foreground | no | foreground | V4L2 | custom | 13 |
| UVC pan and tilt | no | no | Mac app only | no | no | no | no | no | 13 |
| `computer.act` | experimental, limited | no | yes | no | no | `mobile.ui.*` | experimental | no | 14 |
| Xcode, signing | no | no | **only here** | no | no | no | no | no | |
| iMessage | no | via SSH to Mac | **only here** | no | no | no | via SSH | no | 15 |
| Telegram, WhatsApp, Signal, email | Gateway | **Gateway** | Gateway | | | | Gateway | | |
| Calendar via node | no | n/a | **not declared** by the app | yes | no | yes | no | no | 16 |
| Fusion | yes | **no** | yes | no | no | no | **no** | no | 17 |
| Resolve GUI, scripting | Studio for scripting | no | Studio for scripting | no | no | no | Rocky, Studio | no | 18 |
| ffmpeg headless | yes | yes, dynamic link for NVENC | CPU in sandbox | no | no | no | yes | no | 19 |
| NVENC | yes | likely, FLOW-T8 | no | no | no | no | yes | no | 19 |
| CUDA | yes | yes, with limits | no | no | no | no | yes | no | 20 |
| Metal, VideoToolbox | no | no | yes, **but not inside the Claude Code sandbox** | no | no | no | no | no | 21 |
| `sbx` microVM | Win 11 listed, `jorah-lab` unattended ? | not listed | macOS 27 ? | no | no | no | Ubuntu with KVM | no | 22 |
| USB serial to ESP32 | yes | usbipd, fails badly if VM restarts | yes | no | no | no | yes | n/a | 23 |

Notes:

1. [docs-only: `maturity/scorecard.md`, which grades itself: overall Alpha 68%, voice M2 Alpha, watchOS M1 Experimental].
2. [verified: `code.claude.com/docs/en/sandboxing`].
3. "ACPX routes cannot dispatch to a paired device" [docs-only: `nodes/node-host.md`].
4. [docs-only: `nodes/session-hosting.md`]. WSL as Linux is [inference].
5. Windows shell wrappers need approval. An unconfigured node defaults to approvals `full` with `ask: off`, so set this before pairing [docs-only: `nodes/node-host.md`, `tools/exec-approvals.md`].
6. Documented [docs-only: `nodes/mcp-and-skills.md`]. `--commands` disables it. `gateway.nodes.pluginTools.enabled: false` hides it. Reach on the `claude-cli` runtime is K10a.
7. Passive wake refuses to run without on-device recognition. `en-US` reports on-device here, and `en-GB`, `sk-SK`, `cs-CZ` do not [measured: `SFSpeechRecognizer` probe].
8. Speaks only after the whole agent run [docs-only: `nodes/talk/macos-relay.md`].
9. Mac needs `mode: realtime`, `transport: gateway-relay`, `brain: agent-consult` plus **Use realtime Gateway relay**, off by default. Watch cannot use a relay-only provider, so Gemini and own providers do not reach it [docs-only: `platforms/ios.md`; inference for Gemini]. Issues #138972, #167876, #190146 were open today.
10. [source: `dist/nodes-BBBXZ_Tl.mjs`; verified: Hub source; track: gap-room-and-pc-ear §2]. `platforms/windows.md` says otherwise; source wins.
11. Fork needs fixes before it works on mini or Gemini: hard-coded route, marks never acknowledged (fails at 100), 1 s playback bound, no timestamps [source: `e-jung/voice-pe-openclaw` `src/bridge.mjs`, `src/audio.mjs`; track: gap-room-and-pc-ear §2]. Windows runtime for `livekit-wakeword` is [unverified].
12. Frames bypass the Gateway. Expect a stop at about 2 minutes, with no reconnect, because the browser path sends no compression or resumption [source; track: vision.md §4.3]. "Configuring Gateway relay forces the backend relay path" [docs-only: `web/control-ui/chat.md`], see section 12 item N8.
13. `camera.snap`, `camera.clip`, `camera.ptz.control` need an explicit allow. Macs wait 2 s unless `delayMs: 0` [docs-only: `nodes/camera.md`, `nodes/command-policy.md`].
14. Windows: primary display only, no held modifiers, `key` rejects digits and punctuation. Prefer scripts [docs-only: `nodes/computer-use.md`].
15. Bot Apple ID in `jorah`, basic mode, SIP on. Watch for AppleEvents `-1743` [docs-only: `channels/imessage/setup.md`].
16. `topology.md` row 11 was wrong; the macOS app does not declare calendar, contacts or reminders [track: connectors.md §21]. Use Google through the Gateway.
17. [track: topology.md fact 14, search summary only; Autodesk's page returned 403].
18. Free Resolve lost scripting in 21.1 [verified: Blackmagic readme]. Not in the MVP.
19. A static ffmpeg fails on WSL's `libcuda` shim. No NVIDIA statement on NVENC in WSL; community reports only [track: topology.md §4].
20. Partial NVML, no GPU selection by index [verified: `docs.nvidia.com/cuda/wsl-user-guide`].
21. A probe under the published sandbox rules got no Metal device and VideoToolbox hardware H.264 failed with -12908. It used a copy of the rules, not a real run [track: creative.md Verification].
22. `sbx` CVE-2026-77179 (Critical, macOS) and CVE-2026-79994 (High) are fixed in 0.42.0, with later symlink fixes. Floor is 0.50.1, a timeout on every call, symlink refusal on copy-out. Open macOS hang issue docker/sbx-releases #163 [track: growth.md Verification]. These findings apply everywhere, though only `growth.md` records them.
23. [verified: `learn.microsoft.com/en-us/windows/wsl/connect-usb`]. usbipd-win 5.3.0. The arm's USB goes to the Pi, not WSL.
24. `talk.session.close` throws "Talk session is not owned by this connection" for any other connection [source: `dist/session-registry-CcW20RXI.mjs`, read today, not run]. iPhone is [inference, same relay and no timer found; `04-voice-and-vision.md` M2.13 tests it].

### 7.2 Versions and pins

| Item | Value | Rule | Evidence |
|---|---|---|---|
| OpenClaw | 2026.10.9, latest stable | Exact pin in `config/versions.env`. Every 2 to 4 weeks, or within 48 h of a relevant high advisory. Canary first. Never older on migrated data | [track: openclaw-fit.md §9, engineering.md §5] |
| Operator clients (`jorah-talk`, eval runner) | Same as Gateway | Exact wire version, no N-1 window. Fork imports the SDK by file path, so it breaks on upgrade if not pinned. Rerun EAR-E0 after every upgrade | [track: engineering.md §5, gap-room-and-pc-ear §7] |
| Nodes | N-1 accepted | Upgrade Gateway first. `nodeHost.autoUpdate.enabled: false` | [docs-only: `nodes/pairing-and-status.md`, `nodes/node-host.md`] |
| Node.js | 26.13.0 here, floor 24.22.1 or 26.12.1 | Same on PC | [measured; verified: release notes] |
| Mac app | Matches Gateway. Automatic updates off | A named profile may have no updates anyway | [docs-only: `platforms/macos.md`] |
| iOS app | 2026.10.70 | Record versions at APP-T10 | [track: apps.md] |
| Claude Code | 2.1.300 | | [measured] |
| macOS, Mac | 27.0.1, M1 Max, 64 GB, 180 GiB free | Docker Desktop 4.60.1 predates listed fixes, Adam updates | [measured; track: growth.md] |
| WSL | 3.0.3 stable, kernel 6.18.54.1 | Update by hand in the window, then soak | [verified: `github.com/microsoft/WSL/releases`] |
| Windows Hub | Stable v2026.9.8-1 | Not load-bearing | [verified: GitHub API] |
| `sbx` | 0.50.1 or later | | [track: growth.md Verification] |
| `livekit-wakeword`, `sherpa-onnx`, `pymicro-wakeword` | 0.3.0, 2.0.1, 2.5.0 | Pin. Licence checked: Apache-2.0 for the first two | [track: voice.md, gap-voice-to-motion] |
| Pipecat | 1.15.0, BSD-2 | M20 only | [track: voice.md] |
| LeRobot | v0.6.1, Python 3.12 | Pin a tag, `main` moves fast | [track: robotics.md §5] |
| Default Google Live model | `gemini-3.1-flash-live-preview`, earliest shutdown **2026-11-17** | Always name `gemini-3.8-live` explicitly | [verified: `aistudio.google.com/docs/deprecations`, track: vision.md] |

---

## 8. Model routing and cost

### 8.1 Routing

**Rule: route by surface and trigger, escalate by tool call.** OpenClaw routes by agent, binding, session, heartbeat, cron and subagent model, not per message [docs-only: `concepts/multi-agent.md`]. `decisionModel` plugins are unpublished and absent from `plugins list` [docs-only: `concepts/decision-models.md`; measured].

| Task | Lane and model | Effort | Meter | Target |
|---|---|---|---|---|
| Wake | Local detector | n/a | Free | Under 300 ms |
| Quick reply | Realtime model | Low | Voice cap | Under 800 ms |
| Consult, simple | `voice`, Haiku 5.5, `consultThinkingLevel: "off"` | Off. Consult thinking defaults to high if unset [source] | Credits | About 2.8 s |
| Consult needing memory | `ask_main` to `main`, on the API from M2b (decision 4) | Medium | Credits | About 5.8 s, re-measure |
| Typed assistant | `main`, Opus 5.5 CLI until M3, then API unless Anthropic confirms in writing | Medium | Plan, then credits and cash | Unimportant |
| Deep reasoning | `main`, Opus high. Fable 5.1 only if Adam says so | High | Plan, Fable limit | Minutes |
| Coding | Claude Code via ACP, Sonnet 5.5 subagents. Adam's own sessions stay on Max. Jorah-started ones move with `main` | Default | Plan, then credits | Minutes |
| Untrusted reader | `reader-*`, Haiku 5.5, Sonnet 5.5 if it fails evals | Low | Credits | Seconds |
| Unattended | Sonnet 5.5 API, with a task budget where exposed | Medium | Credits | Minutes |
| Vision, gate | Apple Vision on Mac, RF-DETR Nano on PC | n/a | Free | Under 25 ms |
| Vision, caption | Haiku 5.5, local on PC later | Low | Credits | About 1 s |
| Vision, voice Look | `voice` calls `vision_look`, one API call on Haiku 5.5 or Sonnet 5.5, 1,280 px or less | Low | Credits | Under 2 s |
| Vision, typed Look | `main`, Opus 5.5 CLI, Adam alone in frame, training setting confirmed off | Low | Plan | Unimportant |
| Summaries, titles, Activity recaps | `utilityModel`: Haiku on CLI while `main` is on CLI, an exception listed in decision 4, then with `main`, local on PC later | Lowest | Plan, then credits or free | Seconds |
| Dreaming | Paused from M0 on Adam's yes (roadmap 0.13a). Back at step 1.26 with `dreaming.model` and `subagent.allowModelOverride` if a scratch run shows the API lane. Local on PC later | Low | Credits or free | Overnight |
| Heartbeat | Off from M0. Haiku 5.5 on `background` from step 1.26. Script first only if spike 2.4a works | Off | Credits | Seconds |
| Digest | `background`, tool-free completion | Off | Credits | Debounced 10 min |
| Robot goals | `robot`, fast API model | Low | Credits | 1 to 2 s |
| Motor loops | **No LLM** | n/a | n/a | Real time |

**What stays on Max (README decision 4's pick):** Adam's own Claude Code sessions, always. Typed turns on `main` and utility calls only until M3, and after that only if Anthropic confirms in writing. **What moves to credits:** consults, readers, unattended, heartbeat from M1, `ask_main` and voice-started jobs from M2b, the Gateway by M3. **What moves local on the PC:** recaps, heartbeat checks, simple captions, Dreaming.

**Why not everything on Max.** Consumer Terms section 3 bars automated access absent an API key or explicit permission. The support pages conflict on third-party harnesses, and I could not resolve it. `~/.claude-jorah` is the same account as Adam's main login, so a used-up limit or enforcement reaches Mizyun too [verified: `anthropic.com/legal/consumer-terms`; track: brain.md §3]. Jorah already hit the plan's 5-hour limit on day 2 [measured: brain.md §2]. **Keeping typed use on Max is a risk Adam accepts, not a settled permission.** SEC-T21 proves the exit before any connector. Max also cannot back a product [verified: `code.claude.com/docs/en/legal-and-compliance`]. Not legal advice.

**Local models (PC).**

| VRAM | Pick | Use |
|---|---|---|
| 8 GB | `gemma4:e2b` | Below minimum for agent work. Titles, classification |
| 12 GB | `gemma4:12b` | Summaries, utility, simple vision |
| 16 GB | `gemma4:12b`, `gemma4:26b` is tight | Same, some tools |
| 24 GB | `gemma4:26b` or `qwen3.6:27b` | Background agent with tools. Run Jorah's own tool test first |
| 32 GB | `qwen3.6:35b` plus local STT and TTS | Background agent plus voice stack |

Server: Ollama, with `num_ctx` explicit; runner-up llama.cpp if measured slow. Local models get read, summarize and propose only. Never both untrusted content and write tools. On this Mac a 67K prefix takes about 744 s to process on dense 27B, so local is never for live replies here [inference from a community benchmark; track: brain.md §6].

### 8.2 Realtime provider

**Pick: `gpt-realtime-2.1-mini`, candidate to beat. Challenger and camera path: `gemini-3.8-live`. A real bench decides.** Slovak, continuous video or non-blocking consults flip it to Gemini. Bench cost about $2.40 to under €10.

| Model | List price per M tokens | Modelled per connected minute | Slovak | Notes |
|---|---|---|---|---|
| `gpt-realtime-2.1-mini` | Audio $10 in, $20 out, $0.30 cached | $0.009 short, $0.016 at 10 min, $0.021 at 30 min | Not confirmed | Documented relay model, needs Platform key. **Rates per minute rest on third-party or search-only figures** |
| `gemini-3.8-live` | Audio $3 in, $12 out, video $1, text $0.75 in | $0.015 short, $0.054 at 10 min, $0.13 at 30 min | Yes | Whole context re-billed every turn, no caching. Async tools. No client-side stop on plain 3.8 |
| `gpt-live-1` | $0.05 per session minute | $0.05 plus backend | Not stated | Full duplex, no vision, 30-min limit. iOS live verification pending. Only provider with real later-speech path |

Sources: `developers.openai.com/api/docs/pricing`, `aistudio.google.com/docs/pricing`, `aistudio.google.com/docs/live-api/best-practices` [verified]. The tracks' monthly models differ because they assume different session shapes: `voice.md` §8 has mini at $29 to $39 in short sessions and $37 to $93 left open at 1 h a day, Gemini at $38 to $51 and about $163. **These are models, not bills. Replace them with vendor usage from the M2 bench.** Replay grows with the square of session length, so short sessions matter more than the provider.

**Not in those figures:** OpenClaw's OpenAI input transcription, `gpt-4o-mini-transcribe`, is billed separately [track: brain.md §5]. **Could lower them:** ChatGPT Pro includes API credits that cover Realtime and GPT-Live, and Plus does not [verified: `developers.openai.com/api/docs/guides/chatgpt-api-credits`]. Adam says which plan, if any.

**Hard rule: never stream before wake.** A mic to Gemini all month costs at least $216 before context re-billing [inference; track: brain.md §5]. The privacy reason is stronger than the cost reason.

**Terms gate before any key.** Google and Anthropic consumer terms require 18+ [verified: `aistudio.google.com/docs/terms`, `anthropic.com/legal/consumer-terms`]. OpenAI's Services Agreement, DPA and sub-processor list returned 403, so OpenAI's age and EU transfer terms are unconfirmed. **Adam reads them in a browser before prepaying** (10-minute list in `gap-private-data-through-realtime-providers.md` §9). Stop if the age rule blocks them. Google's free tier is excluded for personal audio. Expect non-EU processing on a normal key [inference].

### 8.3 Target config

**Sketch only. Not applied, not validated. Preview, get a yes, test on `jorah-dev` first.** **Per-agent keys need `models auth order set` too, since `auth.order.anthropic` is `[]` globally [measured]. The result of that test goes here (roadmap 1.12): not yet run.** Google keys come from the provider's reader; whether `talk.realtime` passes that block through was not run [track: voice.md §16].

```json5
{
  agents: {
    defaults: {
      model: { primary: "anthropic/claude-opus-5-5", fallbacks: [] },
      utilityModel: "anthropic/claude-haiku-5-5",            // on CLI for now, local later
      embeddedAgent: { cyberFailover: { mode: "off" } },
    },
    entries: {
      main: {
        model: { primary: "anthropic/claude-opus-5-5", fallbacks: [] }, // holds a live 10-step chain today
        tools: { deny: ["group:runtime"] },                             // stage 0
      },
      voice: {
        // Authoritative block: 03 W1.7 (workspace, agentDir, deny list, background policy). Bridge tools added by milestone.
        model: { primary: "anthropic/claude-haiku-5-5", fallbacks: [] },
        models: { "anthropic/claude-haiku-5-5": { agentRuntime: { id: "openclaw" } } },
        memory: { search: { extraPaths: ["~/.openclaw-jorah/shared/voice-notes"] } },
      },
      background: {
        model: { primary: "anthropic/claude-haiku-5-5", fallbacks: [] },
        models: { "anthropic/claude-haiku-5-5": { agentRuntime: { id: "openclaw" } } },
        heartbeat: { every: "1h", isolatedSession: true, lightContext: true,
                     activeHours: { start: "07:00", end: "23:00" } },   // schedule, Adam's yes
      },
    },
  },
  talk: {
    agentId: "voice",
    speechLocale: "en-US",
    interruptOnSpeech: true,
    provider: "mlx",                 // native fallback path, not ElevenLabs
    consultThinkingLevel: "off",
    realtime: {
      provider: "openai",
      providers: {
        openai: { model: "gpt-realtime-2.1-mini", speakerVoice: "<pick by ear>", silenceDurationMs: 500 }, // sweep 400, 500, 700
        // Bench settings. Resumption off limits a connection to about 10 min, fine for short sessions.
        google: { model: "gemini-3.8-live", speakerVoice: "<pick by ear>", silenceDurationMs: 500,
                  sessionResumption: false, contextWindowCompression: true },
      },
      mode: "realtime",
      transport: "gateway-relay",
      brain: "agent-consult",
      consultRouting: "provider-direct",  // flip to force-agent-consult if the wake test scores invented answers
    },
  },
  plugins: {
    entries: {
      "jorah-bridge": { enabled: true },
      "memory-wiki": { config: { vault: { scope: "agent" } } },  // set BEFORE the voice agent exists, back up first
    },
  },
}
```

**Why `vault.scope: agent`.** Today's `vaultMode: bridge` and `vault.scope: global` mean every agent shares the vault, so `voice` could read `main`'s compiled memory [verified: `config get plugins.entries.memory-wiki.config`; docs-only: `plugins/memory-wiki.md`].

**Also on the Mac:** Settings > Voice & Talk > Use realtime Gateway relay. And `talk.catalog` must show `gateway-relay` and `agent-consult`; shipped code says it will [source: `dist/handlers-B5Rt4cMl.mjs`].

### 8.4 Spending caps and the silent-fallback rule

> A failed route reports the failure with its reason and reset time. Jorah never moves work onto a paid meter, a more expensive model or another vendor on its own. Changing a route needs Adam's explicit yes in that conversation, and applies only to what Adam approved. A local model may answer read-only requests during an outage, and the answer must say it came from the local model. [track: brain.md §10]

| Meter | Phase 1 cap | Mechanism | Who |
|---|---|---|---|
| Anthropic API | $100 a month | Credits only, no card, auto-reload off, workspace `jorah` limit $100. Hard stop by construction | **Adam** links Console org (cannot be undone without support) |
| Claude plan overage | $0 | Usage credits off or low cap | **Adam** |
| OpenAI | $10 prepaid | Auto-recharge off, project hard limit on (opt-in) | **Adam** |
| Gemini | $15 prepaid | Auto-reload off, HTTP 402 at $0. Project cap is experimental, billing can lag about 10 min | **Adam** |
| **New cash** | **$25 or less**, until Adam raises it | | |

**Silent paths to close, in order** [track: brain.md §10].

| # | Path | Guard | Checked by |
|---|---|---|---|
| 1 | **Live today:** `agents.entries.main.model.fallbacks`, 10 steps including Fable and `anthropic/*`. Fired on two real runs, and walked on four heartbeats at the limit [measured]. `models status` prints `Fallbacks (0)`, because it shows the defaults | `fallbacks: []` on the entry as well as defaults, other agents and cron `payload.fallbacks`. **Before any key exists.** Recheck after each upgrade | `switch-brain.sh status`, new `PROBLEM` line |
| 2 | Auth rotation to a key on the same provider | Empty order on `main`, key absent from its store | Same |
| 3 | Utility model jumps to HTTP once a credential exists | Explicit `utilityModel` with explicit runtime | Same |
| 4 | `ANTHROPIC_API_KEY` in the Gateway environment | Process-env check | Same |
| 5, 6 | Plan usage credits, Console auto-reload | Off | Reminder, account setting |
| 7 | GPT-Live OAuth falling back to a Platform key | No Platform key on that Gateway if OAuth is used | Same |
| 8 | OpenAI cyber refusal escalates to Daybreak | `cyberFailover.mode: "off"` | Same |
| 10 | Media tool cross-provider fallback | Explicit `mediaModels`; test what can be disabled | Same |
| 12 | Fast mode | `consultFastMode` unset | Same |
| 13 | Relay failure to native speech | Not a paid move, but changes the processor, so disclose | Overlay |

### 8.5 Monthly cost

USD list, no VAT. Unit costs are list prices with my token assumptions [track: brain.md §7].

| Unit | Assumption | Cost |
|---|---|---|
| Haiku thin consult, one pass | 6K prefix, 300 in, 120 out, half cold | $0.0005 |
| Sonnet mid consult | 15K prefix, 500 in, 300 out, half cold | $0.0235 |
| Opus typed turn at today's prefix | Measured blend over one setup day. API equivalent, not a bill | $0.12 |
| Digest refresh | 5K in, 1K out on Haiku | $0.001 |
| Frame caption on Haiku | 1280x720, 200 in, 60 out | $0.00017 |
| Voice Look, one small API call | 1280x720, short answer. Haiku / Sonnet | About $0.0002 / $0.0035 [`04-voice-and-vision.md` §8.2, inference] |
| Autonomous run | Small, about 40 Sonnet requests / large | $0.50 / $1.50 |
| Voice, planning number | Between short and long sessions | $0.04 per connected minute |

| Level | Assumes | Voice | Claude metered | Max | Power | **Total** |
|---|---|---|---|---|---|---|
| Pilot, this Mac | 10 min a day, 30 consults a day | $12 | $1.08 | $100 | | **About $113** |
| Daily driver, PC on | 60 min a day, 100 consults, 2 autonomous runs | $72 | About $51 | $100 | About $17 | **About $240 metered plus plan, about $189 cash** since the $51 sits inside the $100 credits [track: `research/engineering.md`]. API-only is not modelled |
| Full Jarvis | 3 h a day, 300 consults, 5 large runs | $220 | About $337, less $100 credits | $100 | About $34 | **About $590** |

| Change | Daily driver | Full Jarvis |
|---|---|---|
| Voice on mini at $0.017 | −$41 | −$124 |
| Gemini short sessions only, $0.015 | −$45 | −$135 |
| Gemini 30-minute sessions, $0.13 | +$162 | +$486 |
| No local GPU | +$2.50 | +$14 |
| Sonnet lane keeps a 67K prefix | About +$51 | About +$152 |

**Thinning the prompt beats any model or GPU choice.** Prefix is 67K tokens today, and cache writes are 70% of Opus cost [measured: brain.md §2]. **Plan draw is not in these numbers:** every `ask_main` adds a plan turn at that prefix, consults can rewrite the prompt cache [issue: #179236], and 159 Activity recaps in 23 hours sit outside the token table [measured]. Read `/usage` weekly. Ultra ($200, $200 credits, no 5-hour limit once verified) costs the same as Max once API spend is reliably above $200 [verified: support article 17728952].

Electricity is 19.85 ct/kWh, H1 2026, secondary citing Eurostat [track: topology.md §13], so €139 a year idle at 80 W and €261 at 150 W. Max is about €89 a month before tax and about €109 if 23% VAT applies. **Adam reads the invoice.** Hardware and the euro budget are in the roadmap and `engineering.md` §15.

---

## 9. Performance budgets

Measure voice on an audio recording, not logs. Daily found client numbers about 250 ms above server logs [verified, vendor: `daily.co/blog/building-voice-agents-with-nvidia-open-models`]. `just perf` writes to `docs/evidence/perf/<date>-<host>.json`. A regression above 20% needs a note in the PR.

### 9.1 Measured today on this Mac

| Item | Value | Note |
|---|---|---|
| Opus 5.5 user turn, warm | p50 1.2 s, p90 5.6 s | Whole turn, not first token. n=27 |
| Opus 5.5 user turn, no reuse | p50 3.2 to 3.3 s, p90 12.1 s | n=36 to 37 |
| Opus 5.5, reuse invalidated | p50 9 to 11 s, about 29 s at p90 | Tiny sample |
| Haiku 5.5 summary, cold spawn | p50 3.1 s, p90 4.7 s | n=159 |
| Gateway RSS, CPU at rest | 850 to 965 MB, 0.4% to 1.8% of a core | A few samples |
| Memory on a busy day | 61 to 62 of 64 GB used | **The practical case for the PC** [inference] |
| Apple Vision person, feature print, JPEG | About 10, 8, 4 ms | Still images, not a camera |
| Provider edge, unauthenticated | `api.openai.com` 135 to 234 ms to first byte | REST, not a realtime session |
| Direct API latency | **Not measured.** No key exists | B2 at M2 |
| Realtime first audio | **Not measured** on any provider | M2 |

### 9.2 Latency budgets

| Path | Target | Modelled now | Status and gate |
|---|---|---|---|
| Wake to cue | At most 300 ms | n/a | Unmeasured. M1 |
| Voice, first audio, realtime direct | P50 at most 800 ms, P90 at most 1,200 ms | 510 to 925 ms **plus X**, the provider's unpublished time to first audio | Unmeasured. M2, repeat at M9 and M10 |
| Truthful acknowledgement when work takes longer | Inside 800 ms | | M2 |
| Barge-in stops audio | Median at most 300 ms on V1, 150 ms on V2 | | M2, M20 |
| Session closes when idle | 5 s with no speech, 8 s after a reply, 12 s after a question. Usage flat afterwards | | M2b, EAR-E0 and `04-voice-and-vision.md` M2.35 |
| First turn after wake | Record separately. Slower than later turns, because each wake opens a session | | M2b, M10 |
| Consult with one local tool | About 2.8 s / 4.2 s | | Bench |
| `ask_main` | About 5.8 s / 16 s. Reopen the design if a row misses by more than 2x | Rests on 1.0 s per Haiku pass, see below | Bench |
| Public `web_answer` | Within 25 s on 9 of 10 | About 6 to 9 s | M3 |
| Look, first word | Under 2.0 s / 3.5 s | | M6, M18 |
| Mic state after turning off Voice Wake | Under 2 s, 20 of 20 | | M1 |
| Action Button to talking | Median under 3 s | | M2 |
| Telegram simple reply | P50 under 5 s | Today's CLI is under this at p50 | M0 |
| "Stop" to silence, speech | At most 300 ms, internet down too | The stock apps reach a model, so this is a goal until the local stop list in `jorah-talk` exists. On plain `gemini-3.8-live` it silences the speaker but cannot stop generation [source: `handleBargeIn`] | M2b |
| Spoken stop, motion | Within 1 s of the word ending | About 515 ms | MOTION-T2, M17 |
| Bridge wedged to relay off | Heartbeat silent 200 ms | | MOTION-T5 |
| Host loss to relay trip, bench | At most 300 ms, 20 of 20 | | M8 |
| Motion: asked within 5 s, first move within 1.5 s of yes | | | M17 |
| Base stop | Motors commanded off about 500 ms on good Wi-Fi, about 18 cm at 0.35 m/s plus coast | | M23, tape measure |
| Robot reflex, visual | Under 100 ms, local only. **No cloud in a reflex loop** | | Later |
| Gateway restart to ready, reboot to Telegram | Under 30 s, under 3 min | | M9, monthly |

**Whole-loop model** [inference except where marked; track: gap-room-and-pc-ear §5].

| Stage, ms | Mac loopback | PC `jorah-talk` | Mac or iPhone via Serve | Voice PE | Phone, cellular |
|---|---|---|---|---|---|
| Capture, AEC, framing | 30 to 70 | 30 to 70 | 30 to 70 | 30 to 70 | 30 to 70 |
| Tailscale, Serve, WSL | 0 to 1 | 2 to 10 | 4 to 20 | 14 to 80 | 60 to 200 |
| Server VAD silence, tuned 300, default 500 [source] | 300 to 500 | 300 to 500 | 300 to 500 | 300 to 500 | 300 to 500 |
| Provider network [measured bound] | 135 to 234 | 135 to 234 | 135 to 234 | 135 to 234 | 135 to 234 |
| Model first audio | X | X | X | X | X |
| Gateway | 2 to 10 | 2 to 10 | 2 to 10 | 2 to 10 | 2 to 10 |
| Jitter buffer, playback | 40 to 100 | 40 to 100 | 40 to 100 | 210 to 230, verified 200 prebuffer | 60 to 150 |
| **Total without X** | **507 to 915** | **509 to 924** | **511 to 934** | **691 to 1,124** | **587 to 1,164** |

**What this says.** The Serve and WSL hop is under 3% of the budget. The silence window and the provider are the budget: at 500 ms silence X must be under about 90 ms, at 300 ms silence under about 290 ms. So P50 under 800 ms on mini is plausible only with tuning, and the truthful acknowledgement will matter. Too short a silence clips Adam, so it is a bench setting. First turn after wake is a separate number and will be slower. All relay audio is JSON over TCP, so one lost Wi-Fi packet delays everything behind it, and the client must bound its own queues.

**The Haiku assumption is the weakest number in the voice design.** The bridge's budget assumes about 1.0 s per Haiku pass with thinking off, unmeasured. The only Haiku 5.5 figures found are 6 to 9 s to first answer token at low effort with adaptive thinking on and 10K input [verified: `artificialanalysis.ai/models/claude-haiku-5-5-low/providers`], which is not a voice setup. **B2 settles this first.** If P90 first token stays above 500 ms with thinking off, try `gpt-6-luna` at the same list price [track: brain.md §11], or have `before_agent_reply` skip Haiku on simple rows if it fires on consult runs [unverified].

### 9.3 Resource budgets [track: engineering.md §11]

| Host | Resource | Budget | Check |
|---|---|---|---|
| Mac as host | Gateway | 1.2 GB RSS, under 3% of a core idle. 2 GB talking | `ps` |
| Mac as host | Wake | Under 1 W added on battery, under 200 MB | `sudo powermetrics --samplers cpu_power,ane_power -i 5000 -n 12`, **Adam's password** |
| Mac as host | OpenClaw.app | Under 400 MB idle, under 600 MB talking | `ps` |
| Mac as host | `jorah-eyes` | 0 when off: no process, no camera. Watch under 500 MB, 15% of a core | `ps`, indicator |
| Mac as host | All Jorah | Under 4 GB idle, under 12 GB talking with local speech | `ps` |
| Mac as node | Total | At most 1 GB. Must not block sleep unless docked. Docked about 15 W | `ps`, meter |
| PC | Power | At most 80 W idle, stretch 50 W. At most 150 W average | Plug meter, 24 h and 7 days |
| PC | Idle CPU | Under 5% | `Get-Counter`, `top` |
| PC | Idle VRAM | Under 2 GB, models unload after 10 min | `nvidia-smi` |
| PC | WSL memory | Explicit limit, so Windows jobs survive | `wsl --status` |
| PC | Disk growth | Under 1 GB a week excluding media, alert at 85%. Media shares the volume, so a full disk can stop the Gateway. `jorah-ingestd` refuses at the guard limit, and the SFTP upload itself is not bounded | FLOW-T13 |
| PC | Transfer | At least 30 MB/s wired, 45 GB in about 25 min | FLOW-T6 |
| PC | Under a full render | Gateway still answers, worker capped by `MemoryMax` | FLOW-T12 |
| Pi 5, 4 GB | Bridge plus node | Under 1 GB idle. Heavy vision on PC | R3 |

GPU use by Resolve, models and the sidecar conflicts. The worker runs one GPU job at a time. Schedule rather than share [inference].

### 9.4 Privacy and money budgets

| Budget | Target | Check |
|---|---|---|
| Bytes to any cloud voice or vision vendor before a wake | **0** | Packet capture at phase end |
| False-wake cloud openings | At most 1 per 24 h, two-stage chain | 24 h replay, then 7 days live |
| Stage 1 false accepts | At most 0.25 per hour. LiveKit's 0.08 is its own phrase and about 2 events | Shadow mode |
| Camera at boot | Off. No resume without re-arming | Reboot test |
| Disk retention of camera data | None before the exec boundary holds on that host | Gate, M18 |
| Idle money | Any idle spend above €1 a month is a bug. Heartbeat about $0.19 | `jorah-metrics` |

---

## 10. Build steps

Each row is one issue, session and worktree. **Adam** marks what only Adam can do. Every config, schedule, service, account change and purchase is previewed and needs an explicit yes. Keep evidence tiers apart: source, install, launch, signed-in device, bench, supervised hardware, voice to motion. Results go in `docs/evidence/<issue>/`.

| # | M | Who | Action | Files | Acceptance |
|---|---|---|---|---|---|
| A1 | M0 | Claude, Adam's yes | Set `fallbacks: []` on `agents.entries.main.model` and defaults, `cyberFailover: off`, explicit `utilityModel`, explicit `gateway.port` 43181. Before any key exists | Config preview in `docs/evidence/` | `config get agents.entries.main.model.fallbacks` empty. Forced failure reports an error and no model change |
| A2 | M0 | Claude | Extend `switch-brain.sh status`: paths 1, 2, 3, 4, 7, 8, 10, 12 print `PROBLEM`. `setRuntime` stops rewriting `agents.entries.*`, and `mixed` becomes lane-aware | `scripts/switch-brain.sh`, `docs/switch-brain.md` | Planted chain and planted env var each print `PROBLEM` |
| A3 | M0 | Adam, then Claude | Security stage 0 per `security.md` §5, keeping `talk-voice` in `plugins.allow`. **Adam** rotates the Telegram token, enables the firewall | Config preview | SEC-T1 to T4, T9 |
| A4 | M0 | **Adam**, then Claude | **Adam** links Console org, creates workspace `jorah`, $100 limit, no card, pastes key at a prompt. Claude runs `switch-brain.sh` both ways | None new | SEC-T21 |
| A5 | M1 | **Adam**, Claude | Section 6.1 | `docs/evidence/m1-move/` | SEC-T13, SEC-T15, section 6.1 acceptance |
| A6 | M1 | Claude | Backup, set `vault.scope: agent`, add `voice` and `background` on a scratch profile. Own `agentDir`, key only in its store | `workspace-voice/` from one persona source | `main` cannot reach the key. `main`'s utility calls do not jump to HTTP. Prefix under 8K. Canary in `MEMORY.md` unreadable from `voice` |
| A7 | M1 | Claude, Adam speaks | Install app, triggers `jorah`, `hey jorah`, relay off, Computer Control off, node exec denied. SEC-T7 supervised | Trigger list | Session key shows `voice` on the wake-into-Talk path. 40 tries: 90% at 1 m, 70% at 3 m, under 2 false wakes an hour |
| A8 | M2 | Claude | **B2 latency baseline:** 20 short prompts on Haiku through CLI warm, CLI cold and direct API, thinking off. Time to first delta | `scripts/latency-baseline.ts`, `docs/evidence/perf/` | Numbers with date and route. Spend under $0.10. Updates section 9.2 |
| A9 | M2 | Claude | `jorah-metrics` ledger and `jorah-status` | `services/jorah-metrics/`, schema in `packages/contracts/` | Failed source shows "unknown" |
| A10 | M2a | Claude, Adam speaks | `openclaw --profile jorah gateway call talk.catalog --json` saved. Idle test on the stock Mac app: wake, one question, 5 silent minutes. **Adam ends every other stock-app session by hand** | `docs/evidence/m2/` | Catalog shows `gateway-relay` and `agent-consult` per provider. Mic state and usage recorded. Expected: stays open and billing |
| A11 | M2a | Adam reads terms, then Claude | **Adam** reads the OpenAI list, prepays. Claude previews config (section 8.3). Bake-off on synthetic script, 10-minute sessions, real vendor usage | Config preview, `docs/adr/` | P50 at most 800 ms, P90 at most 1,200 ms, 20 barge-ins, one week's bill against the model |
| A12 | M2b | Claude | **EAR-E0 on the Mac, on Adam's yes on D1 (section 13):** fork the adapter at commit `3ea4ee3d` after a full read. Omit provider and model, acknowledge marks, widen the playback bound, send timestamps, widen input budget to 3 s, close on idle, no audio before wake. Closed-list stop phrases and wake through sherpa-onnx 2.0.1, typed phrase. Signed `.app`, LaunchAgent on a yes | `services/jorah-talk/`, `ops/launchd/ai.jorah.talk.plist` | 30 turns, 10 min with slow consult. No `unacknowledged-mark` or `playback-overload` failures. `talk.session.close` logged at 8 s and 5 s, usage flat afterwards. Packet capture shows no audio before wake |
| A13 | M2b | Claude | **Bridge spikes on scratch profile:** BRIDGE-S1 plugin path, S2 memory audience, S3 hook firing on `claude-cli`, S4 cancel, S5 25 s hold, S6 canary, **S7 token scopes (item N1)**. S2 and S3 are stop-the-line | `plugins/jorah-bridge/` | Table in `gap-voice-brain` §8. **Add: which scopes the Mac app's consult holds.** Item N1 decided by the security doc's owner and Adam |
| A13b | M2b | Claude | Build `jorah-bridge`: tool names contain no `send`, do not start with `message_`, do not end in `_actions`. Records survive restart as unknown. `start_job` synthetic only until M3. Security track signs off on avoiding the spoken yes | `plugins/jorah-bridge/` | M2 script in `gap-voice-brain` §8: 10 jobs, status, steer, cancel, TV test, restart test |
| A14 | M3 | Claude | GROW-S13, S15, SEC-T5, GROW-S1 to S7, S16. **K10a:** with `system.run` denied and `pluginTools.enabled: true` on a test node, can `main` call a typed node MCP tool with no free-form string, given the global `tools.deny` on `nodes`? | One-page note each | Fork table in section 4.2 resolved once |
| A15 | M3 | Claude | `jorah-guard`, agents `reader-web`, `reader-private`, `builder`, `actor`. Decide `tools.sessions.visibility` (item N6) | `plugins/jorah-guard/`, `config/permission-matrix.json` | SEC-T1 to T6, T8, T9, T10, T12, T13, T14, T18, T20, T21 |
| A16 | M3 | Claude | `web_answer` to `reader-web`, on security sign-off | `plugins/jorah-bridge/` | 10 public questions, 9 within 25 s. Injection page changes nothing |
| A17 | M4 | Claude | `private_show`, screen first. Remove calendar and memory reads from `voice`. Rewrite spoken lines with no names. Digest service. **Adam** approves digest automation | `plugins/jorah-bridge/` | **Canary test passes** before any real data |
| A18 | M4 | Claude | One-day spike: can a plugin trigger local `talk.speak` on the Mac after closing the provider session? | Note | Yes, or fallback to a small Mac helper |
| A19 | Before M7 | Adam, Claude | FLOW Stage A on a disposable tagged node. Adam's yes on Remote Login for T5 only | `docs/evidence/flow/` | T1 to T5. T2 must fail |
| A20 | M7 | **Adam**, Claude | Section 6.2 | `docs/adr/`, `ops/windows/`, `ops/systemd/` | Section 6.2 table |
| A21 | M9 | **Adam**, Claude | Section 6.3, then 6.4 | `docs/runbooks/cutover.md`, `failover.md` | Section 6.3 acceptance. One failover drill. One restore |
| A22 | M10 | Claude | Build `jorah-talk` for Windows under user `jorah-talk`, pinned to the Gateway's version. S4U task preview for a yes. EAR-E1 must already have passed in section 6.2 | `ops/windows/jorah-talk.xml` | `schtasks /Query`, version. Starts after reboot with nobody signed in: PID, log line, `operator` connection in `openclaw devices list` |
| A23 | M10 | Claude, **Adam** consent | Train `jorah` with `livekit-wakeword`, compare `sherpa-onnx` KWS on the same audio, shadow 7 days, stage 2 check | `services/jorah-talk/`, `fixtures/manifest.yaml` | Section 9.4 targets. 100 scripted tries |
| A24 | M10 | Claude, Adam | **Adam** buys the speakerphone after EAR-E1 passes (about €143 at Alza.at, Slovak price unverified). Simple broker for two ears | `ops/windows/` | EAR-E2, E3: 20 of 20 wakes with the Mac asleep, one reply, no audio before wake by packet capture |
| A25 | M12 | Claude | Ingest, spool, `jorah-media`, review page | `services/` | FLOW-T11, T12, T14 |
| A26 | M15 | Claude, Adam | Pi: section 4.3 users. **Adam's yes** on `gateway.nodes.pluginTools.enabled: true` and the tag. Auto-update off | `ops/pi/` | R3: approvals set to full temporarily, node user still cannot open serial |
| A27 | M17 | Claude | `robot` agent, denies elsewhere, `jorah-robot-guard`, `jorah-ear`, `HALTED`, ear lease | `plugins/`, `services/` | MOTION-T1 to T9 in order: fake bridge in MuJoCo, then bench, then supervised |
| A28 | M19 | Adam, Claude | Create `jorah-build`, wrappers or MCP from K10a, Development certificate | `/usr/local/libexec/jorah` root-owned | TOPO-S4, S6, first iOS build at "build" tier |

---

## 11. Decisions

| Decision | Pick | Why | Runner-up | What would change it | Cost |
|---|---|---|---|---|---|
| Core platform | OpenClaw pinned | Brain, memory, apps ship today | Hermes, which documents PC wake, streaming TTS, barge-in | Voice bench fails and thin fixes cannot close it. Spend one week on Hermes before any rebuild | $0 |
| PC OS and Gateway | Windows 11 Pro, WSL2 distro `jorah-gw` | Only option with sandbox plus Fusion on one box | Small Linux box plus Windows node | Soak or TOPO-S2 fails, gaming PC | Pro about €145 [unverified] |
| Interim boundary | macOS user `jorah`, after `chmod 700` | Cheapest real boundary, rehearses the move | Docker sandbox for exec | Cross-user app link fails | €0 |
| `voice` to `main` link | `jorah-bridge` typed plugin | Job control, typed input, holds with or without the gate | One agent with guard | Hooks proven on `claude-cli`, plan cost tolerable, Adam wants one literal thread | 2 to 3 days |
| Same-call results | Hold consult up to 25 s, else a job | Only shipped path on tool-call providers | Upstream push RPC, V2's own provider | GPT-Live wins the bench | $0 |
| Private data on voice | Pointer only, screen first | Holds without unread OpenAI terms and without zero retention | Adam accepts OpenAI as processor for own calendar only, in writing | Zero retention approved, or V2 ships | 1 to 2 days |
| Where idle close lives | `jorah-talk` on the Mac at M2b | Only a client that owns its session can close it, and this also gives the durable fix for wake landing on `main` | No daily realtime until M10, with native Talk as the daily path | EAR-E0 fails, or Adam finds native Talk good enough | About 20 to 35 h more, 3 to 4 weeks' slip for later milestones [inference, `04-voice-and-vision.md` §2] |
| Room and PC ear | `jorah-talk` on the PC with a speakerphone | No firmware, no listener, right word, one hour to test | Pi 5, then Voice PE third | EAR-E1 fails, PC in another room, 3 m miss | About €140 |
| Wake | Voice Wake on the Mac at M1, `sherpa-onnx` typed phrase in `jorah-talk` from M2b, `livekit-wakeword` from M10 | Already built, then no training, then trained | `sherpa-onnx` stays if training fails. Porcupine rejected. openWakeWord stock models non-commercial | Apple's hit under 80%, or `livekit-wakeword` fails on Windows | $0 to a few $ of GPU |
| Realtime | Section 8.2 | | | | Section 8.5 |
| Voice Look | `voice` makes one small API vision call | `main` adds about 6 s, which misses the 3.5 s target | Through `main`, typed Look only | T3 shows Haiku and Sonnet both too weak | About $0.0002 to $0.0035 per look |
| Stop for motion | `jorah-ear` on the Pi, no network | Same failure domain as the arm | PC ear, only if the arm is wired there | MOTION-T1 fails in every setup: foot pedal or wristband | €0, in plan |
| `robot_*` holder | `robot` agent, Talk bound during an enabled session | One hop, one yes, `voice` and `main` keep limits | `voice` sends to `robot` | MOTION-T4 fails | €0 |
| Arm host | Dedicated Pi | Only placement that creates the boundary and survives a Windows update | USB to the PC, saves about €165 | PC sits by the arm and its account is locked down | About €165 with cooler, card and supply |
| Media | ext4 in the distro, SFTP via Serve, spool to a worker | Keeps `mountFsTab=false`, no sandbox hole, one build | SFTP to Windows OpenSSH on D: | Under 30 MB/s on wired LAN, or ProRes | €0 |
| Lab host | Windows `jorah-lab`, typed MCP | Lab would stop with no leased console under `jorah-desk`; an escape lands away from COM ports | Mac Lab, then Hyper-V VM | K10a or K10b fail | €0 |
| Failover | Manual, rescue bot | Split-brain risk | Read-only Mac | One successful drill | €0 |
| Local GPU | Keep what is there | Savings do not pay | RTX 5060 Ti 16 GB, used 3090 | Failed tier, privacy | €0 to 855+ |
| Intent routing | None | Deterministic by surface | ONNX `decisionModel` | Plugin ships and consult misroutes | $0 |

---

## 12. Contradictions

### Settled by this document

| Conflict | Winner | Why |
|---|---|---|
| `mountFsTab=true` with a drvfs media folder (`topology.md`) or false (`security.md`) | `security.md` | The store works without it. SEC-T17 alone would not catch an fstab line, so the `wsl.conf` block is the real control |
| Mac `jorah` runs builds (`topology.md`) or `jorah-build` (`security.md`) | `security.md` | Build scripts should not share an account with the bot's Messages session |
| `talk.ptt.*` on Hub (`voice.md`, `apps.md`, `openclaw-fit.md`, bundled doc) | Source | No handler in CLI node or Hub, turn-based, no target |
| `topology.md` Windows `robot-bridge` for the arm or `robotics.md` Pi | `robotics.md` | Stop needs the ear beside the bridge. Windows bridge stays for LAN devices |
| `robot_stop` "then relay off" (`robotics.md`) or freeze first | Freeze first | A false stop from the TV should not drop the arm. The E-stop still cuts power at once |
| Tag phone and Mac (`security.md` §11) or user devices (`topology.md`) | `topology.md` | Tailscale's advice, and Serve headers |
| `voice` reads calendar and memory (`brain.md`, `security.md` table) | Neither | Results would reach the realtime provider. Behind `private_show` |
| Send-only delegation (`security.md`) or plugin | Plugin | Send-only forbids status, steer and cancel, and on 2026.10.9 needs a spoken yes on every ask |
| Spoken yes plus tap (`voice.md`, `ux.md`) | Tap is the authority | Plan for one step, since the next stable removes the yes. Robot per-plan check moves to the guard then |
| Windows `ffmpeg.exe` fallback (`topology.md`) | `libx264` in the worker | No Windows hop, no unsandboxed execution |
| Gemini first (`openclaw-fit.md`) or mini first (`voice.md`, `brain.md`) | Mini, then bench | Google bills all context per turn |

### New, found while merging. None has been run. These need action.

| # | Conflict | Evidence | Default here | Who decides |
|---|---|---|---|---|
| **N1** | **A limited room-ear token cannot reach the bridge or the robot.** `gap-room-and-pc-ear` gives `jorah-talk` `operator.read` plus `operator.talk`. `gap-voice-brain` gives it `ask_main` and `start_job`, and `gap-voice-to-motion` calls `robot_send_goal` from a client with those same credentials. But a client without `operator.write` gets `toolsAllow` of exactly `read`, `web_search`, `web_fetch`, `x_search`, `memory_search`, `memory_get`, so plugin tools should be filtered out | [source: `resolveTalkAgentConsultAuthority`, `dist/handlers-B5Rt4cMl.mjs` line 693; `SAFE_READ_ONLY_TOOLS`, `dist/agent-run-control-shared-1_6cGD_R.mjs` line 128]. `operator.write` also allows sending messages, invoking tools and relaying node commands [docs-only: `gateway/operator-scopes.md`] | Test in BRIDGE-S7, EAR-E0 and MOTION-T4. **`03-security-and-privacy.md` (ruling 19, SEC-T23) and `09-engineering-and-ops.md` still specify read and talk only, while `04-voice-and-vision.md` picks adding write, so those documents disagree today.** **Option 1 (pick):** `jorah-talk` holds `operator.write` without `operator.admin`, so `senderIsOwner` stays false and `voice`'s tool policy is the limit. Its token gets a tight ACL under its own user. A stolen token can do much more, so `jorah-guard` must block by session key and tool. **Option 2:** keep read and talk only, and the room ear answers from the digest with jobs and memory on the phone. Option 2 fails the "any time I say Jorah" goal for anything real | **Security track, then Adam** |
| N2 | Roadmap M10 says one Voice PE, stop-gap "Hey Jarvis", PC client calling `talk.ptt.*`. Roadmap section 6 has the speakerphone off the list. `gap-room-and-pc-ear` makes Voice PE third and the speakerphone required | Section 5.3 | This document follows the gap. M10's purchase becomes the speakerphone at about €143, not €59 to €158 | Roadmap owner |
| N3 | Roadmap M7 tries `sbx` under `jorah-desk`. `gap-post-cutover` says `jorah-lab`, and splits K10 | Section 11 | `jorah-lab`. K10a on the Mac first | Roadmap owner |
| N4 | Roadmap M3 gives `voice` send-only to `main`, and M4 gives it today's agenda | `gap-voice-brain`, `gap-private-data` | Bridge and pointer | Roadmap owner |
| N5 | Stage 0 sets `gateway.nodes.pluginTools.enabled: false` and global `tools.deny: ["nodes", ...]`, which hide node-hosted MCP. The robot path, the Lab route and the iOS route all need it | [docs-only: `nodes/mcp-and-skills.md`] | Keep off until K10a. Turning it on is global, so any node that needs nothing else runs `--commands`, and each MCP node publishes only our own servers | Adam's yes, first at M11 on the PC, else M15. M6 no longer needs it |
| N6 | Stage 0 sets `tools.sessions.visibility: "tree"`. The bridge expects `agent`, so `ask_main` can read `agent:main:main` with `sessions_history` | [docs-only: `gateway/config-tools/sessions-and-subagents.md`] | `tree` at M0. Revisit at A15, and give up that read if `agent` widens anything else | Security track |
| N7 | Haiku pass of 1.0 s in the bridge budget against 6 to 9 s measured with thinking on | Section 9.2 | A8 first | Measurement |
| N8 | M2's first sight needs browser Video Talk on Gemini while `talk.realtime` is set to OpenAI with `gateway-relay`. The docs say configuring relay forces the backend path, and video is browser only. No per-session override was found in the UI docs [unverified] | [docs-only: `web/control-ui/chat.md`] | Run VIS-V0 on a scratch profile with `provider: "google"` and no relay transport, not by flipping the daily config | Claude, previewed |
| N9 | `voice.md` idle tail of 30 to 60 s (cost model `brain.md`: 45 s) against `ux.md`'s follow-up window of 8 s, 12 s after a question | Tracks | 8 and 12 s for `jorah-talk`. Cost model is then conservative | Adam by ear |
| N10 | `voice.md` config `consultThinkingLevel: "low"`, gap says set it, `brain.md` says off on API | Tracks | `"off"`, measure, raise if answers suffer | Bench |
| **N11** | **An idle-close helper cannot work.** Roadmap M2 step 2, `voice.md` step 1.12 and `ux.md` plan a helper calling `talk.session.close`. The Gateway refuses that call from any connection but the owner | [source: `requireUnifiedTalkSessionConn`, read today, not run; first found in `04-voice-and-vision.md` §2] | `jorah-talk` moves from M10 to M2b. M2 splits into M2a (22 to 32 h) and M2b (30 to 45 h), and M10 shrinks to 15 to 24 h. **Later dates in the roadmap slip about 3 to 4 weeks** | Adam (D1), roadmap owner |
| N12 | Roadmap M7 step 5 builds PC wake glue with sherpa-onnx. `gap-room-and-pc-ear` starts the PC with EAR-E1, a mic test with no wake at all | Section 6.2 | EAR-E1 first, and the wake model waits for M10 | Roadmap owner |
| N13 | `09-engineering-and-ops.md` dates `jorah-bridge` M3 and `jorah-talk` M10 | `04-voice-and-vision.md` M2.30, M2.39 | M2b, with `start_job` on synthetic briefs until the M3 guard | Roadmap owner |
| N14 | Vision D2 sends Look to Opus through Claude CLI, while the bridge puts `main` about 6 s away | `04-voice-and-vision.md` §2 row 3 | Voice Look is a small API call from `voice`. Typed Look stays on `main` | Settled here, Adam rules on frames through Max at M6 |

---

## 13. Only Adam can do or decide

**Decide**

1. Age: 18 or older? Claude consumer terms and Gemini API terms require it, and OpenAI is unread. If no, stop before any paid key and sort out who holds accounts with a responsible adult.
2. Is the Max risk acceptable, given the shared account? Link a Console org, which cannot be undone without support?
3. Is the PC a daily or gaming machine? Run the section 5.5 check.
4. Does the MacBook stay docked or travel daily?
5. How is Jorah pronounced? Is English enough until M20?
6. Who lives at or visits this home? This decides guest mode and consent.
7. Who holds a write-scoped token in the room (item N1)?
7a. **D1:** build `jorah-talk` on the Mac at M2b, at the cost of 3 to 4 weeks' slip, or stay without daily realtime until M10? Pick: M2b.
8. Should the Mac's `jorah` user and `chmod 700` go ahead? The LaunchAgent?
9. BitLocker TPM-only, or a pre-boot PIN?
10. Offsite backup at Hetzner through restic, or a rotated disk? Where does the passphrase live?

**Do personally:** Tailscale sign-in, tags, policy approval. Console link, keys at a prompt, prepayment, auto-reload off. Claude logins on each host. Training setting and usage credits. macOS firewall and Docker Desktop update. Windows install, users, BitLocker. Reading OpenAI's contract pages. All purchases.

---

## 14. Not confirmed

| Open point | Answered at |
|---|---|
| Direct API latency, Haiku with thinking off | A8 |
| Realtime first audio, barge-in, real voice cost, mini's token rates, Google config passthrough | M2 |
| Stock Mac and iPhone app behaviour when idle, and after the 30-minute close. Expected: no idle close | A10, `04-voice-and-vision.md` M2.13 |
| EAR-E0 on API-key mini: marks, playback bound, timestamps, all read from code | A12 |
| Memory audience on plugin-started turns. Hook firing on `claude-cli`. Cascade cancel | A13 |
| Whether plugin tools are really filtered for limited tokens, as the source implies | A13 |
| Node-published MCP on the Claude CLI runtime. Interaction with the global `nodes` deny | A14 |
| `sbx` on macOS 27 from a standard user, and unattended on Windows | A14, K10b |
| Cross-user localhost into `jorah-svc`'s WSL. WebSocket through Serve. Serve latency | TOPO-S2, S2b |
| WASAPI from an S4U task with nobody signed in | EAR-E1 |
| WSL idle-shutdown bug on 3.0.x | 7-day soak |
| NVENC under a systemd unit in WSL. `DeviceAllow` for `/dev/dxg` | FLOW-T8 |
| `livekit-wakeword` on Windows, and accuracy on "Jorah". sherpa-onnx's pretrained English model on "Jorah" and the stop phrases | A12, A23 |
| Whether two macOS users hold separate node identities | TOPO-S4 |
| Tailnet behaviour for a `jorah` LaunchAgent when `adam` logs out | A5 |
| Stop model accuracy and latency. XVF3800 AEC reference path | MOTION-T1 |
| Whether a limited or write-scoped client can select `agent:robot:*` | MOTION-T4 |
| Fusion's API headless, licence on automation | M19 |
| Current PC parts prices, Slovak stock | Before each order |
| Anthropic's position on an always-on gateway on a Max login | Adam. Not settled by this plan |
| OpenAI age, EU transfer, sub-processors. Whether abuse logs hold audio | Adam's reading list |

Not re-checked here: prices and versions are as the tracks recorded them today, except the read-only checks run on this Mac and in OpenClaw's installed code (items N1 and N11, `talk.realtime` docs, port listener, free disk, npm tags). This merge ran no web searches.

---

## 15. Sources

**Research files, read for this document:** `docs/plan/research/topology.md`, `brain.md`, `openclaw-fit.md`, `voice.md`, `vision.md`, `gap-voice-brain-context-and-delegation.md`, `gap-room-and-pc-ear-after-cutover.md`, `gap-voice-to-motion-path-and-local-stop.md`, `gap-post-cutover-workload-and-file-flow.md`, `gap-private-data-through-realtime-providers.md`. Sections of `security.md` (§5, §6, §11), `engineering.md` (§3, §6, §7, §11) and `robotics.md` (§1, §5, §6). Each has its own full source list. **Sibling plan documents, read where they touch this one:** `03-security-and-privacy.md`, `04-voice-and-vision.md`, `09-engineering-and-ops.md`.

**OpenClaw 2026.10.9, local.** Docs: `nodes/talk.md`, `nodes/talk/realtime-sessions.md`, `nodes/talk/macos-relay.md`, `nodes/talk/session-ownership.md`, `nodes/node-host.md`, `nodes/mcp-and-skills.md`, `nodes/command-policy.md`, `nodes/computer-use.md`, `nodes/session-hosting.md`, `nodes/file-transfers.md`, `platforms/windows.md`, `platforms/mac/bundled-gateway.md`, `platforms/mac/remote.md`, `platforms/ios.md`, `gateway/tailscale.md`, `gateway/remote.md`, `gateway/operator-scopes.md`, `gateway/multiple-gateways.md`, `gateway/config-tools/sessions-and-subagents.md`, `gateway/protocol/rpc-talk-config-and-agents.md`, `web/control-ui/chat.md`, `install/migrating.md`, `concepts/multi-agent.md`, `cli/qr.md`. Code: `dist/handlers-B5Rt4cMl.mjs`, `dist/agent-run-control-shared-1_6cGD_R.mjs`, `dist/tool-mutation-BTW6eoAN.mjs`, `dist/agent-tools.before-tool-call-CQkX3nOj.mjs`, `dist/openclaw-tools-CSSYZDKR.mjs`, `dist/node-commands-Bxo-2Y4j.mjs`, `dist/nodes-BBBXZ_Tl.mjs`, `dist/realtime-bootstrap-context-dPeThtcK.mjs`, `dist/session-registry-CcW20RXI.mjs`.

**Primary, web.**
[Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing) ·
[Claude Code legal](https://code.claude.com/docs/en/legal-and-compliance) ·
[Claude consumer terms](https://www.anthropic.com/legal/consumer-terms) ·
[Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing) ·
[API credits for subscribers](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers) ·
[OpenAI pricing](https://developers.openai.com/api/docs/pricing) ·
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data) ·
[Gemini pricing](https://aistudio.google.com/docs/pricing) ·
[Live API best practices](https://aistudio.google.com/docs/live-api/best-practices) ·
[Live session management](https://aistudio.google.com/docs/live-api/session-management) ·
[Gemini deprecations](https://aistudio.google.com/docs/deprecations) ·
[Gemini terms](https://aistudio.google.com/docs/terms) ·
[Tailscale run unattended](https://tailscale.com/kb/1088/run-unattended) ·
[Tailscale on Windows and WSL](https://tailscale.com/kb/1295/install-windows-wsl2) ·
[Tailscale Serve CLI](https://tailscale.com/kb/1242/tailscale-serve) ·
[Tailscale Serve](https://tailscale.com/kb/1312/serve) ·
[Tags](https://tailscale.com/kb/1068/tags) ·
[Grants](https://tailscale.com/kb/1324/grants) ·
[Taildrop](https://tailscale.com/kb/1106/taildrop) ·
[Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh) ·
[macOS variants](https://tailscale.com/kb/1065/macos-variants) ·
[Tailscale pricing](https://tailscale.com/pricing) ·
[WSL config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) ·
[WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking) ·
[WSL USB](https://learn.microsoft.com/en-us/windows/wsl/connect-usb) ·
[WSL issue 13416](https://github.com/microsoft/WSL/issues/13416) ·
[Windows Update restarts](https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart) ·
[CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) ·
[sbx install](https://docs.docker.com/ai/sandboxes/install/) ·
[sandbox-runtime Linux source](https://github.com/anthropic-experimental/sandbox-runtime/blob/main/src/sandbox/linux-sandbox-utils.ts) ·
[Voice PE adapter](https://github.com/e-jung/voice-pe-openclaw) ·
[Windows Hub](https://github.com/openclaw/openclaw-windows-node) ·
[livekit-wakeword](https://github.com/livekit/livekit-wakeword) ·
[microWakeWord stop model](https://github.com/kahrendt/microWakeWord/releases/tag/stop) ·
[pymicro-wakeword](https://pypi.org/project/pymicro-wakeword/) ·
[sherpa-onnx KWS](https://k2-fsa.github.io/sherpa/onnx/kws/index.html) ·
[PR #159697](https://github.com/openclaw/openclaw/pull/159697) ·
[Issue #179236](https://github.com/openclaw/openclaw/issues/179236) ·
[Issue #183740](https://github.com/openclaw/openclaw/issues/183740) ·
[Apple closed-lid use](https://support.apple.com/en-us/102282).
