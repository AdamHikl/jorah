# 07. Apps and devices

Companion strategy for Jorah: what runs in Adam's hand, on the desk and in the room. Written 2026-11-02 against OpenClaw 2026.10.9.

**Sources:** `research/apps.md`, `research/ux.md`, `research/openclaw-fit.md`, `research/vision.md`, `research/gap-room-and-pc-ear-after-cutover.md`, `research/gap-private-data-through-realtime-providers.md`, `research/gap-voice-brain-context-and-delegation.md`. M-numbers come from the merged roadmap.

**Related plan documents:** `04-voice-and-vision.md` owns `jorah-talk`, wake models and latency. `03-security-and-privacy.md` owns approval tiers and `SEC-T` tests. `06-connectors.md` owns what the iPhone node reads. `02-architecture.md` owns the token and agent layout. `01-vision-and-ux.md` owns wording and state. This file owns app setup, device tests and own-app milestones.

**Evidence today: source and docs only.** `/Applications/OpenClaw.app` does not exist and no node is paired [verified: local check, 2026-11-02]. Install, launch and signed-in device acceptance are all open for every line below.

**Labels:**

- `[verified: X]`: read at X. For OpenClaw source that means code at tag `v2026.10.9`, not a running app.
- `[docs-only: X]`: OpenClaw's own docs say so, not exercised.
- `[secondary: X]`: third-party source.
- `[inference]`: judgment. All thresholds, efforts and own-build estimates are this.
- `[unverified]`: looked and could not confirm. Do not rely on it until the named test settles it.

**Paths:** `D/` = `/opt/homebrew/lib/node_modules/openclaw/docs/`. `GH/` = `https://github.com/openclaw/openclaw/blob/v2026.10.9/`.

**Test names:** `APP-T` = section 11 of this file. `SEC-T` = `03-security-and-privacy.md`. `E0` to `E3` and `S2b` = section 8 here, from the room-ear gap (`02-architecture.md` calls them `EAR-E0` and so on). `BR-S7` = `04-voice-and-vision.md` section 7.3. Phase "A7" is the two-week log, not decision row A7 in `research/apps.md`.

---

## 1. Bottom line

1. **Use the official OpenClaw Mac and iPhone apps. Build no companion app, and never fork.** Upstream changed `apps/ios` 137 times and `apps/macos` 182 times in 30 days [verified: `gh api`, `research/apps.md` 2.3]. The one native artifact on the plan is `jorah-talk`'s small signed Mac wrapper, which exists for mic consent and is not a companion app (`04-voice-and-vision.md` 5.6).
2. **An iPhone cannot be an always-on "Jorah" mic.** No third-party app gets a Siri-grade locked wake word. Solve hands-free in layers: Mac wake now, phone gesture now, room ear at M10.
3. **The room ear is our own small client, not a bought satellite.** `jorah-talk` on the PC with a USB speakerphone is the pick, a Pi is the runner-up, and Voice PE is third. Nothing on the pinned stack delivers realtime "Hey Jorah" without code we write [verified by source read: `research/gap-room-and-pc-ear-after-cutover.md` section 1]. Under `04-voice-and-vision.md` decision D1 the same client also becomes the Mac's daily realtime ear at M2b, because only the connection that owns a Talk session can close it.
4. **Notices go by Telegram first, then Web Push.** The iOS app has no job-finished push [verified: `GH/src/gateway/server-methods/push.ts`, `nodes.wake.ts`].
5. **Realtime on the iPhone is a session Adam starts and ends by hand.** I found no idle close in the tagged iOS Talk source, and no outside helper can close it (section 6.2). That does not meet roadmap gate 4 for daily use, so Adam decides how to treat it (section 13, question 15).
6. **An own app needs a named trigger from a two-week log.** Then a 2 to 3 day spike comes first, then stoppable milestones.
7. **Skip for now:** Wear OS (needs an Android phone), glasses (Slovakia is not on Meta's list, re-read for this file), CarPlay.

**Cost through M10:** €0 for the apps, about €143 for the speakerphone, plus an optional USB power switch. No own-app money unless a trigger fires.

---

## 2. Decisions

| # | Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|---|
| D1 | Mac companion | Official `OpenClaw-2026.10.9-arm64.dmg`, started under its own profile `jorah-app`, never `jorah`, never from Finder | Wake, push-to-talk, overlay, approvals, node host and widget panel ship [docs-only: `D/platforms/macos.md`]. M3 Beta [docs-only: `D/maturity/scorecard.md`] | Own menu bar app | Wake fails on "Jorah", or the app cannot reach the `jorah` user's Gateway | €0 |
| D2 | iPhone companion | Official App Store app, free, 2026.10.70, iOS 26.2+ | Chat, Talk, background Talk, Live Activity, approvals, share sheet, Watch [verified: App Store listing]. M4 Stable by its own grade, but its README says "Foreground-first", so plan by the README | Own-signed upstream build | A section 7 trigger | €0 |
| D3 | Custom native work | None now. If triggered, a new thin app, Jorah Remote | Fork cost is about 1 day a week [inference] | Patch fork | Upstream slows a lot | 6 to 9 weeks if fully built [inference] |
| D4 | iPhone spoken phrase | Vocal Shortcut "Hey Jorah" running a Shortcut around Start Live Voice, if APP-T8 passes | Free, no code | "Hey Siri, Jorah" Shortcut | Battery, false triggers, or a Siri dependency in the EU [unverified] | €0 |
| D5 | iPhone daily gesture | Action Button Shortcut plus Face ID | Opens the app and "does not bypass iOS unlock" [docs-only: `D/platforms/ios.md`] | Own app with push-to-talk intent after spike S1 | Hard trigger H1 | €0 |
| D6 | Job-finished notices | Telegram first, native notice at the Mac, Web Push from the installed Control UI next | No native job-finished push. Telegram works today | Own app with direct APNs | Telegram too noisy or too exposed | €0 |
| D7 | Approval alerts | Hosted relay, only after APP-T5 passes, with generic text. Web Push if it fails | Only push path for the Store build | Own-signed build with direct APNs | Adam rejects a third-party relay | €0 |
| D8 | Phone access | Pair Full to configure, then try `--limited` for daily carry | A lost phone should not hold `operator.admin`. Also, a Talk consult from a connection with `operator.admin` runs with `senderIsOwner: true`, and without it `false` [verified by reading: `resolveTalkAgentConsultAuthority`, `dist/handlers-B5Rt4cMl.mjs` line 693; not run] | Stay Full with the lost-phone runbook | Settings or approvals stop working under Limited | €0 |
| D9 | Custom UI first | Server side: `show_widget`, Mac widget panel, tailnet review page, pinned dashboard report | Renders in official apps with no signing [docs-only: `D/tools/show-widget.md`, `D/platforms/mac/canvas.md`] | Own app | Native lock-screen need | Days, €0 |
| D10 | First room ear (M10) | `jorah-talk` on the PC, S4U task, USB speakerphone | No firmware, no new listener, says "Jorah" from day one | Pi 5 with the same client | Spike E1 fails, or the PC is in another room | About €143 (Alza.at, availability "on request"; no Alza.sk listing found [secondary: search summary]), plus €5 to €15 for a switch [inference] |
| D11 | Voice PE | Third choice, a later far-field extra | Fixed wake words, firmware work, plain `ws://` LAN listener, 200 ms prebuffer | ReSpeaker XVF3800 | Speakerphone and array both miss at 3 m | €59 at Domadoo, tax included, undated [secondary: search summary]. No Slovak listing found |
| D12 | DIY ESP32 puck | Optional learning project at M27 | Honest mute and LED, but no echo cancelling hardware | Voice PE | Adam wants it sooner for its own sake | €20 to €30 [inference] |
| D13 | Apple Watch | If owned: Talk to Claw through iPhone, plus approvals. Skip standalone Talk | See section 9 | Own Watch app | Adam accepts a public endpoint | €0 |
| D14 | Wear OS | Skip unless Adam gets an Android phone | Phone-proxied by design [docs-only: `D/platforms/android.md`] | Spare Android phone as host | Adam gets one | €0 if owned |
| D15 | Smart glasses | Do not buy. Off the committed roadmap | Slovakia is not on Meta's list [verified: `research/vision.md` section 3] | Android XR later | Section 9 gate | €335 or more |
| D16 | CarPlay | Skip | Needs own app and Apple's entitlement approval, and has no wake word | Bluetooth audio with kept-alive Talk | Adam drives daily with CarPlay | Own app plus approval risk |
| D17 | Own-app signing, if ever | Ad Hoc on the paid team, no public Store | Apple points family-and-friends apps to Xcode or Ad Hoc [verified: App Review Guidelines] | Internal TestFlight (90-day builds) | Business decision | $99 a year, likely paid |
| D18 (README decision 21, `04` D1) | Daily realtime ear on the Mac (M2b) | `jorah-talk` wrapper in Adam's session. OpenClaw.app stays for approvals, node and panel, and its realtime Talk is bench only. Owned by `04-voice-and-vision.md` D1 | An outside helper cannot close the app's session, and gate 4 needs an idle close | No daily realtime until M10. Native Talk stays daily | E0 fails, or Adam finds native Talk enough | 30 to 45 h in M2b [track: `04-voice-and-vision.md` section 2] |
| D19 | iPhone realtime | Deliberate sessions, ended by hand. "Talk in the background" off for daily use until APP-T22 is read | No idle close found, relay stops only at 30 minutes, and every word reaches the provider | Native Talk only on the phone | APP-T22 shows a close I missed, or a newer Store build adds one | Billed per use |
| D20 | How cards reach a surface | Table in section 6.5: `show_widget` for typed turns, panel for display at the desk, `chat.inject` note plus approval for voice-started cards | `show_widget` is hidden when the client that started the turn lacks `inline-widgets`, and the panel is render-only | Authenticated tailnet page | APP-T20 | About 1 day, already in the bridge budget [inference] |

---

## 3. What Adam does, by place

| Where | Say or do | What happens | Honest limit |
|---|---|---|---|
| Desk, Mac on, M1 | "Hey Jorah", chime, then speak | Mac wake starts native Talk | Words in the same breath are dropped on this path [verified: `apps/macos/.../VoiceWakeRuntime.swift`]. Slow, since it speaks after the whole run |
| Desk, Mac on, M2b | "Hey Jorah", cue, then speak | `jorah-talk` opens a realtime session and closes it after 8 s of silence | Depends on E0 and on Adam's yes to D18. Headset first. OpenClaw's overlay will not show this client's state [inference, `01-vision-and-ux.md`] |
| Desk, Mac on | Hold Right Option | Push-to-talk | Right Option may not exist on an external keyboard |
| Phone in hand | Action Button, Face ID | Start Live Voice | Needs unlock and foreground. Target median under 3 s. **Adam ends the session by hand** (D19) |
| Phone unlocked | "Hey Jorah" | Vocal Shortcut starts Talk | Locked phone will want unlock [inference, APP-T8]. Always-on mic indicator, so off at school |
| Long walk | Start Talk once, AirPods in | Background Talk stays live when locked | Must start in the foreground. Calls and Siri can end it. Every utterance reaches the provider, and billing runs until Adam stops or the 30-minute relay limit |
| Room, from M10 | "Hey Jorah, what's on today?" in one breath | `jorah-talk` answers with the Mac asleep | Depends on spike E1 |
| Anywhere | Type in Telegram or the app | Same Jorah | Every voice action has a typed path [track: `research/ux.md` section 21] |

"Stop" ends speech only, "cancel that" ends the job, and "stop everything" freezes [track: `research/ux.md` U4].

Do not sell this as Jarvis everywhere. At home it is hands-free, in hand it is one press, and on the phone it never listens on its own.

---

## 4. What to use from OpenClaw

Status is what ships at 2026.10.9, untested on Adam's devices.

### 4.1 Use

| Feature | Surface | When | Setting or note | Test |
|---|---|---|---|---|
| Voice Wake, en-US | Mac | M1 | Triggers `jorah`, `hey jorah`, replacing `openclaw`, `claude`, `computer`. The list is global. `en-US` is on-device here, `en-GB`, `sk-SK`, `cs-CZ` are not [verified: `SFSpeechRecognizer` probe in `research/openclaw-fit.md`] | APP-T2, SEC-T7 |
| Native Talk, overlay, Quick Chat | Mac | M1 | MLX local voice to start. Speaks only after the whole run [docs-only: `D/nodes/talk/macos-relay.md`] | APP-T2 |
| Push-to-talk | Mac | M1 | Hold Right Option | APP-T3 |
| Realtime Talk over relay | Mac | M2, **bench only** | `mode: realtime`, `transport: gateway-relay`, `brain: agent-consult`, plus the local opt-in [docs-only: `D/nodes/talk/macos-relay.md`]. Pressed sessions, ended by hand. Daily realtime moves to `jorah-talk` at M2b | `04-voice-and-vision.md` VOICE-V1a |
| Chat, Sessions, offline cache | iPhone | M2 | 50-message outbox for 48 h [docs-only: `D/platforms/ios.md`] | APP-T4 |
| Approvals inbox and cards | iPhone, Mac, Watch | M2, real use M3 | First answer wins across surfaces [docs-only: `D/platforms/ios.md`] | APP-T6, SEC-T20 |
| Background Talk, Live Activity | iPhone | M2 | "Talk in the background" on. Live Activity is local only, so it goes stale when the app is suspended [verified: `LiveActivityManager.swift`, `pushType: nil`] | APP-T9 |
| Share sheet | iPhone | M2 | Text, 1 URL, 10 images, 1 movie [verified: `GH/apps/ios/project.yml`] | Open bug [#162011](https://github.com/openclaw/openclaw/issues/162011) |
| `show_widget`, widget panel | iPhone, Mac | M2 to M6 | Job cards in typed sessions, HUD. **The panel is render-only** and needs a presenter plugin [docs-only: `D/platforms/mac/canvas.md`, `D/tools/show-widget.md`]. Section 6.5 | APP-T20 |
| iPhone node reads | iPhone | M6 | `calendar.events`, `contacts.search`, `reminders.list`, foreground only. Owned by `06-connectors.md` C9 | Its tests |
| Control UI as Home Screen app | iPhone | M2 test, used if needed | Web Push with an Agent finished category and a Private detail level, no OpenClaw relay [docs-only: `D/web/notifications.md`] | APP-T18 |
| Pinned dashboard report | Control UI | M3 | Trust report from real logs [docs-only: `D/tools/show-widget.md`] | `research/ux.md` UX5 |
| `camera.snap` | Mac first | M6 | `delayMs: 0`, explicit opt-in, `includeAudio: false` on clips [docs-only: `D/nodes/camera.md`] | `research/vision.md` T0 |
| Remote mode | Mac | M9 | Voice Wake forwards to the PC [docs-only: `D/platforms/mac/remote.md`] | M9 acceptance |

### 4.2 Keep off

| Feature | Why | Until |
|---|---|---|
| Allow Computer Control (default on, no per-action confirmation) [docs-only: `D/nodes/computer-use.md`] | Runs as `adam`, which re-opens the exec gap | Set off before pairing. Revisit at M19 |
| Mac node `system.run` | Same. Node default is `full` with `ask: off` [docs-only: `D/nodes/node-host.md`] | Local approvals set to deny for good |
| Mac Camera, Desktop sharing | Not needed for voice | Camera at M6. Desktop sharing stays off unless asked |
| iPhone Voice Wake | Foreground only, sends text with no spoken reply, and the on-device claim is not backed by iOS code [verified: `NodeAppModel.swift`, `project.yml`; `requiresOnDeviceRecognition` found only under `apps/macos`] | APP-T17 passes, and then probably still off |
| "Allow Always" on risky classes | One tap with no biometric gate | Removed by policy, plugin approvals through `allowedDecisions: ["allow-once", "deny"]` [docs-only: `D/plugins/plugin-permission-requests.md`] |
| `camera.*`, `screen.record`, `health.summary`, `sms.*` in `gateway.nodes.commands.allow` | Each is a privacy opt-in | A stated use with Adam's yes |
| Health, Location automation | Separate from Mizyun, not needed | Unplanned |
| ClawHub skills for any of this | Malware history [verified: Unit 42, in `research/openclaw-fit.md` section 9] | Read and pin, or do not use |

### 4.3 Real gaps, and what closes each

| Gap | Closed by | Own app needed? |
|---|---|---|
| Always-on iPhone wake | Nothing, for anyone | No app closes it |
| Realtime session left open | Mac: `jorah-talk` at M2b. iPhone: Adam ends it by hand | Only for the iPhone, in N3 |
| Job-finished notice on iPhone | Telegram, then Web Push | Only if both fail |
| Live progress on the lock screen | Telegram milestones, job card in chat | N1, if it matters |
| Long message body on an approval card (title 80, description 512 characters) [docs-only: `D/plugins/plugin-permission-requests.md`] | Excerpt plus an authenticated page bound by hash [inference] | N2, if it matters |
| Face ID on each approval | iOS app lock as a stopgap, may not cover notification actions or Watch [secondary: Apple support snippet, tested in `research/ux.md` UX3] | N2, hard trigger H3 |
| Locked one-press talk | Unproven for anyone | Spike S1 decides |
| Large video review (100 MB iOS download limit) [docs-only: `D/platforms/ios.md`] | Tailnet review page | N5 only if the page falls short |
| Mic state across devices | `jorah-presence` and the trust report | No |

---

## 5. Mac scope and steps

### 5.1 What the Mac does over time

| Phase | Role |
|---|---|
| M1 to M8 | Gateway runs in macOS user `jorah`. The app runs in `adam`'s session as voice and presence node |
| M2b | `jorah-talk` wrapper in `adam`'s session becomes the wake and realtime ear, if Adam accepts D18. Voice Wake goes off the same day (section 5.4). The app keeps approvals, panel, push-to-talk and node |
| M6 | Adds Look, and the HUD job card in the widget panel |
| M6 onward, if Adam agrees | The `jorah-adam-data` launchd service for Reminders and iMessage, with typed tools and no node role, owned by `06-connectors.md`. It is separate from the app |
| M9 onward | App in Remote mode, `jorah-talk` to the Serve URL, Mac as second ear. Rescue bot in the `jorah` user |
| M10 | Mac stays a second ear, under the broker in `04-voice-and-vision.md` M10.9 |
| M18 | `jorah-eyes` sidecar, a separate signed app bundle with `NSCameraUseContinuityCameraDeviceType` [track: `research/vision.md`] |
| M19 | Separate headless build node, not this app [track: `research/topology.md` section 9] |

**Never fork the Mac app.** It is the largest codebase, TCC grants tie to signature and path [docs-only: `D/platforms/mac/permissions.md`], and it is M3 Beta. A Jarvis-style HUD is a hosted page in the widget panel, for display only because the panel disables widget actions [docs-only: `D/platforms/mac/canvas.md`]. Plugins cannot add native surfaces [inference].

### 5.2 Install and connect (M1)

Prerequisite: M0 gate passed, and Adam's yes on the app, its permissions and the node exception. Work inside the roadmap's cross-user spike.

| # | Who | Step | Accept |
|---|---|---|---|
| 1 | **Adam**, one owner, because it writes outside the repo | The block below | Digest `8159c89174298c3238dac8ce1566b5dd43905f5f6f8e9a873c0222a23f219f72` [verified: release API; measured: 236733193 bytes]. Signature accepted. Record both. Installed, which is install tier only. A fixed path keeps TCC grants. **Do not open from Finder** |
| 2 | Adam (admin), Claude previews the config | Spike: `tailscale serve --bg --https=443 http://127.0.0.1:43301`. After the move: the same to 43181. The `jorah` user cannot read Tailscale's proof file, so `adam` runs Serve as an external route [verified: `research/topology.md` A7]. An external route gets no managed Tailscale semantics and no tokenless auth, needs `gateway.trustedProxies` set narrowly, and token auth stays on [docs-only: `D/gateway/tailscale.md`, warning in `02-architecture.md`] | Route listed by `tailscale serve status`. Token still required |
| 3 | Adam | Before first launch, with the full path, since remote setups skip the CLI link: `/Applications/OpenClaw.app/Contents/MacOS/openclaw-mac configure-remote --profile jorah-app --direct-url wss://<mac>.<tailnet>.ts.net --token-file <600 file>`. Docs say this marks onboarding complete and needs no running app [docs-only: `D/platforms/mac/remote.md`]. Token file readable by `adam` only, never in the repo | Onboarding never appears. If it does, stop and record it |
| 4 | Adam | `open --env OPENCLAW_PROFILE=jorah-app /Applications/OpenClaw.app`. **Never profile `jorah`,** which resolves to `~/.openclaw-jorah`. The app takes its profile only from that variable, and a Finder launch means the default profile, port 18789, and possibly a second Gateway [verified: `AppProfile.swift`; docs-only: `D/platforms/mac/bundled-gateway.md`] | APP-T1, with all of: `openclaw-mac primary show --json` names the route, Gateway log shows the connection, `lsof -nP -iTCP:18789 -sTCP:LISTEN` empty, `~/.openclaw-jorah` absent or unchanged, `which openclaw` unchanged |
| 5 | Adam | If the app links `openclaw-mac` under `<state>/bin` and adds it to shell profiles [docs-only: `D/platforms/mac/bundled-gateway.md`], that can change which `openclaw` Adam's shell runs. Check `~/.zshrc`. Later connection changes while the app runs: `openclaw-mac --profile jorah-app primary set --direct-url <url> --token-file <file>`. **Note for SEC-T13:** the app's own credentials necessarily live under `adam`, so that test covers the Gateway's tokens, not this one [inference] | App connected. Direct URL to a Serve route on the same Mac is untested. If it fails, follow the roadmap's M1 fallback and stop for Adam's decision |
| 6 | Adam | Before pairing, in the app: Allow Computer Control off, Camera off, Desktop sharing off, automatic updates off, Mic and Speech permissions only. Native prompts default to Cancel, so read each one | Recorded with screenshots in `docs/evidence/apps/m1-mac/` |
| 7 | Adam runs, Claude prepares and reads the output | **Order matters, proven in the spike (`03` W1.6).** App connected, not approved: `openclaw --profile jorah-app approvals set --stdin` with `{version:1, defaults:{security:"deny", ask:"off", askFallback:"deny"}}`, then `approvals get`. If refused, the app's Settings page, with a screenshot. **Only then** `oj devices list`, `oj devices approve <id>`, `oj nodes pending`, and `oj nodes approve <id>` **only if SEC-T15b passed.** Then `oj approvals get --node <id>` | `nodes status` lists the Mac, or the row records operator only. `nodes describe` shows no `system.run` reach. SEC-T15, T15b. Trust `nodes status`, not the app's label [#182723](https://github.com/openclaw/openclaw/issues/182723) |
| 9 | Adam | **Dashboard → Settings → Talk → This Mac**: Voice Wake on, English (US), chimes on, wake starts Talk. Set triggers. A native confirm appears with Cancel as default. Add spelling variants only from what Apple actually heard | APP-T2 |
| 10 | Claude | Keep the login path honest. Login items will not carry the variable [inference]. If Adam wants auto-start, preview a small LaunchAgent that runs the `open --env` line, and install only on a yes | Reboot steps written in `docs/runbooks/mac-app-start.md`, including who must log in |

```bash
# DMG block, Adam. M1.2 in `04` and roadmap 1.5 refer here.
gh release download v2026.10.9 -R openclaw/openclaw -p 'OpenClaw-2026.10.9-arm64.dmg' -D <scratch dir>
cd <scratch dir>
echo "8159c89174298c3238dac8ce1566b5dd43905f5f6f8e9a873c0222a23f219f72  OpenClaw-2026.10.9-arm64.dmg" | shasum -a 256 -c
hdiutil attach -nobrowse -readonly OpenClaw-2026.10.9-arm64.dmg     # note the mount point
codesign -dv --verbose=2 <mount>/OpenClaw.app
spctl -a -vv <mount>/OpenClaw.app
ditto <mount>/OpenClaw.app /Applications/OpenClaw.app               # ditto, so quarantine and TCC behave one known way
hdiutil detach <mount>
```

**Gateway service.** A foreground terminal Gateway will not qualify for attach [docs-only: `D/platforms/mac/bundled-gateway.md`], which is why the spike uses a direct URL. The roadmap's `gateway install` on a yes covers the live one. Never install it silently.

**Updates.** The app may not self-update under a named profile [docs-only: `D/platforms/macos.md`], which suits pinning. Update by hand to the Gateway's version.

### 5.3 Mac after cutover (M9)

| # | Who | Step | Accept |
|---|---|---|---|
| 1 | Claude and Adam | `openclaw-mac primary set --direct-url wss://pc.<tailnet>.ts.net --token-file <file>` [verified: `research/topology.md` line 584]. Point `jorah-talk` at the same URL and re-issue its token (`04-voice-and-vision.md` M9.1) | Wake on the Mac reaches the PC brain |
| 2 | Claude | Check nothing still points at the old Gateway. Two Jorahs must never exist [track: `research/ux.md` section 11] | `nodes status` on the PC lists the Mac once. Old route removed |
| 3 | Claude | Run `E2`'s "Mac through Serve" path against the M2 baseline | Latency table saved. Connectivity alone is not a latency claim |

### 5.4 Handing the ear to `jorah-talk` (M2b, only on a yes to README decision 21)

`04-voice-and-vision.md` M2.30 to M2.37 build the client. These are the app-side steps.

| # | Who | Step | Accept |
|---|---|---|---|
| 1 | **Adam only** | Choose the Apple team for the wrapper. A stable signature is what keeps the mic grant [docs-only for OpenClaw's app: `D/platforms/mac/permissions.md`; inference for ours]. Keep it separate from Mizyun if a business is likely | Written in `docs/adr/` |
| 2 | Adam | When M2.33 passes: **Dashboard → Settings → Talk → This Mac**, Voice Wake off. Native Talk's local opt-in for the relay off | Two wake paths never run together. Say "Hey Jorah" once: exactly one new session in `openclaw --profile jorah sessions` |
| 3 | Adam | Turning Voice Wake off drops any app mic use within 2 s, while the wrapper's own mic use continues | Status word in the wrapper is true. Recorded |
| 4 | Claude | The HUD job card in the panel reads state from `jorah-metrics` or `jorah-presence`, since the overlay no longer sees the call [inference] | Panel and wrapper agree on 10 state changes |
| 5 | Adam | Check push-to-talk in the app still works, and decide if it stays. It would run native Talk on the same mic | APP-T3 re-run, or set off |

**This is not an own app under roadmap gate 9.** The wrapper has one status word and no chat, approvals or settings. If it grows beyond that, gate 9 applies [inference].

---

## 6. iPhone scope and steps

### 6.1 Check first

| Who | Step | Accept |
|---|---|---|
| Adam | **Settings → General → About** | iOS 26.2 or later. `iPhone17,1` appears as a Continuity camera on this Mac [verified: `system_profiler`], probably a 16 Pro with an Action Button [inference]. Confirm it is the daily phone |
| Adam | Install Tailscale on the iPhone and sign in. Install OpenClaw from the App Store: https://apps.apple.com/app/openclaw-ai-that-does-things/id6780396132 | Both installed |
| Claude | Write `docs/runbooks/lost-phone.md` **before pairing**: `openclaw --profile jorah devices list`, `devices revoke <id>` for each role, `nodes remove <id>`, Find My, rotate the Gateway token if Full. Verify revoke flags against `openclaw devices revoke --help` then | Runbook exists. SEC-T16 uses it |

### 6.2 The transport finding

`talk.realtime.transport` is one config value [docs-only: `D/nodes/talk.md`]. The Mac uses the relay only when it says `gateway-relay`, and an explicit `gateway-relay` also keeps iOS on the relay [docs-only: `D/nodes/talk/macos-relay.md`, `D/platforms/ios.md`]. So the Mac config pins the iPhone to the relay as well [inference, no per-device override found].

That has two consequences:

1. **The phone's Talk may drop on slow paths until a newer Store build ships.** Store 2026.10.70 maps to Gateway 2026.10.7 [verified: `GH/apps/ios/VERSIONING.md`], and the stall fix for [#180426](https://github.com/openclaw/openclaw/issues/180426) is in the client at `v2026.10.9` but not `v2026.10.7` [verified: `RealtimeTalkRelaySession.swift` at both tags]. A build numbered 2026.10.90 or later should carry it [inference]. Do not judge relay Talk on cellular before then. The consult-cancel fix is on `main` only.
2. **Standalone Talk on Watch fails visibly under this config,** because it needs `webrtc` [docs-only: `D/nodes/talk.md`]. This applies to `gpt-realtime-2.1-mini` as well as Gemini, so it is wider than `research/apps.md` A12 says.
3. **No idle close on the phone.** A search of `apps/ios/Sources/Voice/TalkModeManager.swift` and `RealtimeTalkRelaySession.swift` at `v2026.10.9` finds no silence or inactivity close for realtime [verified by search only, not run]. `talk.session.close` needs the owning connection [source, via `04-voice-and-vision.md` section 2], so nothing outside the app can close it. The Gateway ends a relay at 30 minutes [verified: `RELAY_SESSION_TTL_MS`, via the room-ear gap]. APP-T22 measures it.
4. **A failed relay can change who hears Adam.** The kit's comment says errors other than cancellation route Talk to its native fallback [verified: `RealtimeTalkRelaySession.swift` line 519], and Apple Speech on iOS may use the network [docs-only: `D/nodes/talk.md`]. Guest mode therefore means Talk closed on the phone too, not only on the Mac.

### 6.3 Setup (M2)

Each step that changes Gateway config needs a preview and a yes first. Under the roadmap's M1 exception, nodes get mic and approvals only.

| # | Who | Step | Accept |
|---|---|---|---|
| 1 | **Adam**, in a Terminal attached to no agent | Show the setup code in the terminal only: `oj qr --url wss://<mac>.<tailnet>.ts.net`. Anything a Claude session runs lands in its transcript. It holds a short-lived bootstrap token, so treat it as a password. Never paste it in chat or Telegram. `--url` is a documented flag [verified: `openclaw qr --help`], and this use with an external Serve route is [inference] | QR shown |
| 2 | Adam | **Settings → Gateway**, scan, review role and scopes, choose Full | Pending request |
| 3 | **Adam**, Claude reads `devices list` afterwards | `oj devices list`, then `oj devices approve <requestId>` | `nodes status` lists the iPhone. APP-T4 |
| 4 | Adam | **Settings → This iPhone → Notifications** on. Accept "Enable OpenClaw Hosted Push Relay?" if D7 is accepted | Consent recorded |
| 5 | Claude | `openclaw --profile jorah nodes push --node <id> --title Test --body Test` with the phone locked | JSON with `transport: relay` and a banner. APP-T5. If no registration, toggle Notifications off and on, because of [#146791](https://github.com/openclaw/openclaw/issues/146791). A first `410` can be stale, so retry after a few minutes ([#120241](https://github.com/openclaw/openclaw/issues/120241)) |
| 6 | Adam | **Settings → Talk → This iPhone**: "Talk in the background" on for APP-T9 and APP-T22, then off for daily use unless Adam decides otherwise (D19). Voice Wake stays off | APP-T9, APP-T22 |
| 7 | Adam | **Shortcuts → +** → add OpenClaw **Start Live Voice** → name it **Jorah** | Runs |
| 8 | Adam | **Settings → Action Button** → **Shortcut** → **Jorah** | APP-T7 |
| 9 | Adam | **Settings → Accessibility → Vocal Shortcuts → Set Up** → Shortcut **Jorah** → type "Hey Jorah" → say it three times. Decline sharing recordings with Apple | APP-T8. Keep it only if it passes |
| 10 | Adam | Add the Jorah Shortcut as a Lock Screen and Control Center control if iOS offers it [inference] | APP-T7 |
| 11 | Adam | Show Previews "When Unlocked" for OpenClaw and Telegram [inference] | Recorded |
| 12 | **Adam**, Claude reads the results | After APP-T5, T6, T9: `oj qr --limited --url ...`, re-scan, re-run those tests. Limited keeps the node token and omits only `operator.admin` [docs-only: `D/cli/qr.md`], so consults still run with `voice`'s full tool policy, as non-owner. Limited loses Activity, Workboard and Settings pages | Result recorded, including `senderIsOwner` read from APP-T19. If approvals or background Talk break, stay Full with the runbook |
| 13 | Adam | Lost-phone drill | SEC-T16, before daily phone use |
| 14 | Adam | Start the A7 log | Section 7.1 |

**Version drift.** Operator clients must support the Gateway's current protocol, and only nodes get an N-1 window [docs-only: `D/gateway/protocol/versioning.md`]. Before each Gateway upgrade, compare the Store app version and run APP-T16.

**After M9:** a new setup code from the PC. The app keeps several Gateways [docs-only: `D/platforms/ios.md`]. Remove the old one.

### 6.4 Notices, cards and status without native code

| Need | Pick | Rule | Milestone |
|---|---|---|---|
| Job finished or blocked | Telegram message | Names a job, never its content. For private-class work, a neutral line only: "Jorah has something for you on your Mac." Telegram is not end to end [track: `research/gap-private-data-through-realtime-providers.md`] | M6, by preview and yes |
| Same, if Telegram falls short | Web Push from the Home Screen install, Private detail | Quiet hours drop alerts rather than queue them [docs-only: `D/web/notifications.md`], so the digest must catch them | After APP-T18 |
| Approval on the lock screen | Relay or Web Push | Exec text is fixed. **Plugin approval title and description go through the relay and onto the lock screen** [verified: `GH/src/infra/push-apns.ts`, `push-apns.relay.ts`]. `jorah-guard` must write generic text | M3 |
| Approval expiry | 2 min default, 10 max [docs-only: `D/plugins/plugin-permission-requests.md`] | Nothing waits overnight. The job parks and the morning digest raises a fresh one | M3 |
| Spoken yes and tap | On 2026.10.9 voice runs may need a spoken yes first, and the tap is the authority. PR [#159697](https://github.com/openclaw/openclaw/pull/159697) removes the gate after this version, so design for one step (`03-security-and-privacy.md` section 2.2) and re-test at each upgrade | Voice never approves | M2, M3 |
| Private readout | `private_show` card by the section 6.5 route. The tool returns only a neutral pointer to the voice model | Build before Gmail or Calendar connect | M4 |
| Spoken "remember this" | End-of-call note with the exact quote, tap by generic approval: Keep, Change, Forget | A note waits if the phone is absent, never written silently. Route in section 6.5 is untested | M2b, APP-T20 |
| Progress | `show_widget` job card inline. Mac: same card in the panel | Show a real measure such as segments done, or the step name. Never draw status the system cannot confirm | M6 |
| "What is mic and camera doing?" | Trust report, one column on a phone. "Mac: unknown, last report 14:02", never "off" unless reported off | Tailscale only | M3 |
| Video review | Page on Tailscale only, opened in Safari: `tailscale serve --https=8443`, identity header plus a per-review token [track: `research/gap-post-cutover-workload-and-file-flow.md` F8]. `sendPrompt` does not exist in Safari, so Approve and notes need their own authenticated route [inference] | YouTube upload stays manual | M12, APP-T14 |

**Build items, all by Claude, previewed:**

| File | What | Accept |
|---|---|---|
| `workspace/skills/job-card/SKILL.md` | When and how to render a job card with `show_widget`, status words from `research/ux.md` section 6 | Card appears in iOS chat and the Mac panel, with no invented percentage. Any Pause button is tested in iOS chat, because `sendPrompt` is documented for the Control UI [docs-only: `D/tools/show-widget.md`] and the native transcript is [unverified] |
| `plugins/jorah-bridge/` | `private_show` and `note_for_main` cards, per section 6.5. Owned with `06-connectors.md` and `04-voice-and-vision.md` | Canary string never reaches the provider, read from the session log |
| `docs/evidence/apps/` | Results per test, with versions | Each test row has a date and versions |

### 6.5 How a card actually reaches a surface

The plan promises cards from voice: `private_show`, and Keep, Change, Forget. **No track says how they get there, and the obvious tool will not do it.** `show_widget` is exposed only when the client that started the turn declares `inline-widgets`, or a current-channel presenter matches [docs-only: `D/tools/show-widget.md`]. `jorah-talk` is an operator client that does not declare it [inference from the adapter's source], and a Telegram or plain cron turn does not either.

| Route | Reaches | Buttons | Limit | Use for |
|---|---|---|---|---|
| `show_widget` inline | Transcript of the client that started the turn | `sendPrompt` in Control UI. Native app [unverified] | Hidden for clients without the capability | Typed turns in the app |
| `show_widget`, `presentation.target: node_panel` | A connected Mac | **None, render-only** | Needs a presenter plugin. Falls back inline, or fails visibly [docs-only] | Private readout at the desk, HUD |
| `chat.inject` | Whoever opens that session | None | Appends a note with no agent run [docs-only: `D/web/webchat.md`]. Which scope it needs and whether a plugin may call it are [unverified] | Private text on the phone, in a dedicated session |
| Plugin approval (`requireApproval`) | iOS, Mac, Watch, Control UI, perhaps Telegram | Allow once, deny | Title 80, description 512 characters, 2 to 10 minutes. **Text goes through the relay and onto the lock screen** | The tap itself, with generic text only |
| Pinned report | Control UI dashboard | None | 8 KB, `pin: true` | Trust report |
| Authenticated tailnet page | Safari | Our own route | We build it | Long bodies bound by hash, video |

**Pick** [inference, untested]:

- **`private_show`:** the plugin writes the result by `chat.inject` into a dedicated session, `agent:reader-private:cards`, excluded from memory and never the voice session. If the Mac is the active surface, it also opens the panel. Telegram or push gets the neutral line only.
- **Keep, Change, Forget:** the exact quote goes in the same injected note. The tap is a plugin approval with a generic title such as "Review a note": allow once means Keep, deny means Forget, and Change happens by typing in that session. **The quote cannot go in the approval text,** because that text reaches the relay and the lock screen. This reverses the "exact quote on the card" wording in `03-security-and-privacy.md` row 51 and `01-vision-and-ux.md` U24 for phone use.
- **Timeout:** approvals expire in at most 10 minutes, so a note outlasts them. An expired card leaves the note waiting, and it is re-raised with a fresh approval when Adam opens that session or in the morning digest. It is never written silently.
- **If `chat.inject` is closed to plugins:** use the authenticated tailnet page, about 1 to 2 days more.

**Who and when:** Claude, half a day on a scratch profile before `note_for_main` is used on real speech at M2b. Result in `docs/evidence/apps/cards.md`. APP-T20 is the acceptance.

---

## 7. Trigger to build our own

### 7.1 The A7 log

**Two weeks of daily use, starting at M2.** No schedule, and Adam writes it by hand. Claude creates `docs/evidence/apps/a7-log.md` with these columns:

`date | where | gesture | seconds to listening | failed? | how I learned a job finished | had to open the app to check? | Talk died? | annoyance`

Add one column once D19 is settled: `Talk left open?`. Claude writes `docs/adr/native-app-decision.md` at M4's exit: go or no-go, naming which trigger fired with the rows that show it. **No own-app work before this file exists** (roadmap hard gate 9). The Mac wrapper in section 5.4 is outside this gate as long as it stays a wrapper.

### 7.2 Triggers

Start spike S1 if **any hard trigger** fires, or **any two soft triggers**. Thresholds are proposals [inference].

| Type | Trigger |
|---|---|
| **H1** | Adam needs one-press talk with the phone locked in a pocket, and Action Button plus Face ID is not acceptable |
| **H2** | Adam decides to commercialize, or the app must carry the Jorah name and privacy claims |
| **H3** | The safety review requires Face ID on phone approvals. RISK-T3 rests on the phone's own lock today, since code search finds no `LAContext` [verified: `research/apps.md` 2.4] |
| **H4** | APP-T5 fails, the bug stays open after two more Store releases, **and** APP-T18 also fails |
| Soft | Action Button to "Listening" over 3 s in more than 20% of tries |
| Soft | Background Talk dies more than once per 30 minutes of walking |
| Soft | Adam leaves phone Talk open by accident more than once a week, shown by the A7 log or the bill |
| Soft | Jobs over 10 minutes are common, and Adam still opens the app daily to check status |
| Soft | The hosted relay becomes unacceptable |
| Soft | Adam repeatedly wants live iPhone camera streaming that Continuity cannot give |

**Not triggers:** cosmetic preference, or wanting an always-on iPhone mic, which an own app does not solve.

### 7.3 Spike S1, locked one-press talk (2 to 3 days)

**Question:** phone locked in a pocket. Can one Action Button press give a live mic in under 1.5 s, with no Face ID, and play a reply? Evidence conflicts, so nobody knows [verified: Apple forums 748430, 771457, 815725].

**Setup:** throwaway app on the paid team, Development signing, no Gateway code. **Adam must approve registering an App ID and capabilities.** The Push to Talk capability looked self-service as of a 2022 Apple reply [verified: forum 707980], and today's state is [unverified].

| Path | Build | Check |
|---|---|---|
| A. Push to Talk | Capability, `push-to-talk` background mode, Push Notifications. Join a channel in the foreground. App Intent adopting `PushToTalkTransmissionIntent`. Record after `didActivate`. Reply through a `pushtotalk` APNs push, topic `<bundle>.voip-ptt`, priority 10 | Locked? Face ID? How intrusive is the system UI? Does a reply wake and play? |
| B. Audio recording | Intent conforming to `AudioRecordingIntent` and `LiveActivityIntent`, on the Action Button. Start the Live Activity, then the audio session | Starts at all from locked, or fails with "Target is not foreground"? |

**Pass:** 9 of 10 per path, locked in a pocket, mic live under 1.5 s. Record interruption by a call or Siri, and battery over 30 minutes.

**Outcome, written to `docs/evidence/apps/s1.md`:** B works, prefer it. Only A works, accept its system UI. Neither works, H1 cannot be solved by an own app, so say so and drop N4.

### 7.4 Jorah Remote, if triggered

iPhone only, iOS 26+, English. New SwiftUI target at `apps/jorah-remote/`, vendoring `OpenClawKit` at the pinned tag with `git subtree` [inference]. The official app stays for settings, skills and history. **Each milestone is useful alone, and Adam can stop after any of them.**

| # | Scope | Effort | Closes | Accept (signed-in device) |
|---|---|---|---|---|
| N1 Status | Pairing at narrowest scope, Keychain. Gateway-side `jorah-status` with a direct APNs key. Live Activity with `pushType: .token`: job, step, percent, state. Widget. Time-sensitive job-finished push | 1 to 2 weeks | Progress, notices | A 40-minute job updates on the lock screen with the app suspended |
| N2 Approvals | Card with canonical preview, Face ID before Allow, no Allow Always, generic push. Revocation tested | About 1 week | H3, H4 | Dummy RISK-T3: Face ID required, deny blocks, allow runs once |
| N3 Talk | Large button, one status word, last lines, stop, relay. App Intents with "Jorah", controls. VoiceOver and Dynamic Type from day one | 2 to 3 weeks | Own voice surface | Same latency table as M2 |
| N4 Locked press | The path S1 proved. BLE button if useful | 1 to 2 weeks | H1 | S1's pass, end to end |
| N5 Review | AVPlayer on a tailnet URL, Approve, Change, timed note | About 1 week | Native review | One real video reviewed |

**Most likely only N1 and N2.** Total if all built: 6 to 9 weeks plus the spike [inference]. The roadmap's M31 says 5 to 8.

**Out of scope:** chat history, settings, skills, sessions, camera streaming, Watch, CarPlay, Health, iPad layouts, localization.

**If Adam rejects a mobile UI, restore the previous layout rather than refining it.**

**What an own app loses and costs:**

- No hosted relay. It requires App Attest and a StoreKit transaction from the official path [docs-only: `D/platforms/ios.md`]. Direct APNs uses `OPENCLAW_APNS_TEAM_ID`, `KEY_ID`, `PRIVATE_KEY_PATH` on the Gateway.
- Live Activity limits: 8 h active, up to 12 on the Lock Screen, 4 KB [verified: Apple ActivityKit docs].
- Half a day per Gateway bump [inference].
- **Only Adam:** choose which of the 2 Apple teams in the keychain hosts it [verified: `security find-identity`], check membership, create the APNs key and App IDs, install. Bundle IDs stay separate from Mizyun. APNs key in the Gateway credentials dir at `chmod 600`, never in the repo.

### 7.5 If it ever reaches the App Store

Only after H2 and the roadmap's business gate. Main risks [verified guideline text; ranking is inference]:

1. Review needs a live demo Gateway, as OpenClaw runs one, plus 4.2.3(i) standalone function.
2. 2.5.4: background services for intended purposes only. Keyword gating would be hard to defend.
3. 2.5.14: consent and a clear recording indicator.
4. 5.1.2(i): disclose third-party AI and get permission.
5. Push to Talk for an AI may be questioned. Nothing found either way.
6. Purpose strings must be true. Do not copy OpenClaw's "on-device" string unless on-device is enforced.
7. Max cannot back a product [verified: https://code.claude.com/docs/en/legal-and-compliance]. No "Claw" or "Jarvis" in a public name.

---

## 8. Room satellites

### 8.1 The pick

**No ear delivers realtime "Hey Jorah" on 2026.10.9 today** [verified by reading code: `research/gap-room-and-pc-ear-after-cutover.md`]:

- `talk.ptt.*` is turn-based, has no per-call target, and has no handler in the CLI node host or in Windows Hub, despite `D/platforms/windows.md`.
- The Voice PE adapter `e-jung/voice-pe-openclaw` fails as shipped on API-key `gpt-realtime-2.1-mini` and `gemini-3.8-live`: hard-coded route, unacknowledged marks drop the call at 100, a 1 s playback queue, and stale barge-in position. Not run. No ChatGPT plan is needed.

| | **PC `jorah-talk`, speakerphone (pick)** | **Pi 5 `jorah-talk` (runner-up)** | **Voice PE plus fork (third)** | DIY puck |
|---|---|---|---|---|
| Realtime | After fork | After fork | After fork plus firmware | Needs a host bridge |
| Says "Jorah" day one | Yes, `livekit-wakeword` | Yes | No. Okay Nabu, Hey Jarvis, Hey Mycroft | After training |
| Windows session risk | **Unverified, E1 decides** | None | None | None |
| Modelled round trip, before model time | 509 to 924 ms | Low, similar | 691 to 1,124 ms, 200 ms prebuffer | Unknown |
| New network exposure | None, outbound only | Own tailnet device | LAN listener, plain `ws://` bearer token | LAN listener |
| Echo cancelling | In the speakerphone [inference] | Speakerphone or XVF3800 | XMOS | **None, it would hear itself** |
| Hard mic mute | USB power switch, section 8.3 | Same, or array | **Real, cuts mic power** [verified: https://www.home-assistant.io/voice-pe/] | Real, by design |
| Price | About €143, one retailer (Alza.at) | Pi €123.90 is planned for M15 anyway | €59 MSRP, Slovak stock [unverified] | €20 to €30 [inference] |

### 8.2 Steps

Evidence tiers stay separate. Only E3 and M10's last row count as acceptance. Each pairing, service and purchase needs Adam's yes.

| When | # | Who | Step | Pass |
|---|---|---|---|---|
| M2b, per `04-voice-and-vision.md` M2.30 and M2.31 | E0 | Claude, Adam's yes | Fork the MIT bridge at commit `3ea4ee3d` into `services/jorah-talk/`. Changes: omit provider, model and voice so config rules; acknowledge marks with `talk.session.acknowledgeMark`; larger playback bound; send `timestamp` on `appendAudio`; 3 s input budget; replace the device socket with local capture and wake behind a small seam; idle close with a 12 s follow-up; RAM ring of about 2 s and no audio before wake; keep metadata telemetry. Run against the Mac: 30 scripted turns, then 10 minutes with a slow consult | No mark or playback failures, barge-in within 500 ms by ear, consult spoken, scopes in `hello` as BR-S7 decided |
| **M7 (my proposal, earlier than the gap's M10)** | E1 | Claude, Adam present | About 1 hour. Throwaway program, no Jorah credentials, in Windows user `jorah-talk` under an S4U boot task. Cases: nobody signed in after cold reboot, `adam` signed in, `jorah-desk` leased, locked. Capture 10 s and play a tone. Reach the Serve URL | Non-silent PCM and audible tone in all four, three reboots. **Fail: go to the Pi. Do not add autologon** |
| M7 | Place | Adam | Where does the PC sit relative to where Adam talks? Free USB port? | Written down before buying |
| M7 or M9 | S2b | Claude | With `research/topology.md` S2, nobody signed in: run `appendAudio`-size frames for 10 minutes, direct and through DERP if possible | Under 25 ms P50 and 75 ms P90 added against loopback, direct |
| M9 passes | Buy | **Adam** | USB speakerphone. Check the PC location first | Delivered |
| M10 | 1 | **Adam runs it and approves pairing**, in a terminal attached to no agent | `openclaw qr --voice-node` on the Gateway. Use **only the operator token**, in a file with a tight NTFS ACL. Connect to `wss://pc.<tailnet>.ts.net`, not WSL localhost. Session key `agent:voice:room`. Confirm with `openclaw devices list`. **Scope follows BR-S7:** `operator.read` plus `operator.talk` limits consults to `read`, `web_search`, `web_fetch`, `x_search`, `memory_search`, `memory_get`, so `ask_main`, `start_job` and `private_show` should be filtered out [verified by reading; not run]. If BR-S7 confirms that, add `operator.write` without admin, which is `02-architecture.md` N1 option 1 and needs security sign-off. `openclaw devices rotate --scope` exists for this [verified: `--help`] | No node role granted. `senderIsOwner` false. Token cannot read `main`'s data, test added. A stolen token with `operator.write` can do much more, so the guard blocks by session key |
| M10 | 2 | Claude | Train `jorah` with `livekit-wakeword` after pronunciation is settled. Compare sherpa-onnx KWS on real audio. Windows support is [unverified]. Shadow mode 7 days, logs only, then a second-stage check | Roadmap M10 thresholds: under 5% false rejects quiet, under 10% music, at most 1 false accept per 24 h |
| M10 | 3 | Claude | Boot task via `schtasks`, under `jorah-talk`. The fork imports the Gateway SDK by file path, so pin it and re-run E0 at each Gateway version change | PID, log line, `operator` connection after reboot with nobody signed in |
| M10 | 4 | Claude, Adam | E2: room recorded by a separate mic. Paths: Mac loopback, PC `jorah-talk`, Mac via Serve, iPhone on LAN via Serve. 30 turns each, plus first turn after wake | P50 at most 800 ms, P90 at most 1,200 ms, or a truthful recorded reason. Start silence at 400 ms and tune by ear |
| M10 | 5 | Claude, Adam | E3: overnight and a working day, a recording plays a wake every 30 minutes | 20 of 20 answered with the Mac asleep, one response when the Mac is awake, packet capture clean before wake, recovers from a Gateway restart and a Windows reboot |
| M10 | 6 | Claude | Simple broker for two ears, per `04-voice-and-vision.md` M10.9: 150 ms window, rules from `research/ux.md` section 11. Include the phone: a Vocal Shortcut outside the broker can still open a second session, so APP-T8's desk line applies | Two ears, one reply, 50 of 50. Wrong device at most 5% |
| M10 | 7 | Adam | **Device acceptance:** in the room, Mac asleep, says it works | Recording, table, Adam's verdict |

**If E0 shows mini cannot hold the target:** the client stays. Run the bake-off, then consider `talk.client.create` with `gateway-control-v1` [docs-only: `D/nodes/talk/realtime-sessions.md`].

**If the speakerphone misses at 3 m:** add the XVF3800 ($54.90) [track: `research/voice.md`].

**At M17:** the same code moves to the Pi for conversation. `jorah-ear` is a separate no-network stop process [track: `research/gap-voice-to-motion-path-and-local-stop.md`]. Keep the names apart.

**Buying notes for Adam:** Slovak prices were not found for either device. Check Heureka.sk and Alza.sk first. Voice PE is listed at Domadoo for €59 and in stock at The Pi Hut at £55.80 on undated pages [secondary: search summary], and no SmarterHOME listing turned up.

**Voice PE if ever used:** Nabu Casa says it needs Home Assistant [secondary: search snippet in `research/ux.md` section 20], so running it through a bridge alone is an untested spike. Adapter in the `jorah-talk` Windows user, bound to the IoT interface, firewalled to the device's one address. Not in `jorah-gw`. Firmware patches are GPLv3 and "not a ready-to-flash config" with possible XMOS DFU [verified: its `firmware/README.md`]. Stock "Hey Jarvis" is private-only stop-gap.

**Windows Hub:** not load-bearing. Its source has no `talk.*`, only `stt.*` and `tts.*` [verified: `git grep` at HEAD and `v2026.9.8-1`]. Wanted only for its own sake.

### 8.3 Mute, indicators and guests

| Rule | How | Test |
|---|---|---|
| Hard mute on the room ear | A speakerphone mute button is treated as software unless a datasheet says otherwise [track: `research/ux.md` section 20]. So use a USB inline power switch in the speakerphone's cable, or pull the plug [inference, no product checked, about €5 to €15]. This keeps the roadmap's "mute under 1 s by switch" | APP-T21 |
| Voice cannot unmute | Physical act or a tap | APP-T21 |
| Name the recipient | "Streaming to OpenAI", not "cloud" or a plain dot [track: `research/gap-private-data-through-realtime-providers.md`] | M2 |
| Guest mode closes Talk | No realtime, no native fallback, typed only, cameras off. It beats `research/voice.md` on legal risk | M3 onward. Mic state read from the device |
| Coverage is per device | "Room: switch off. Mac: software mute. Phone: not listening" | Trust report |
| No audio before wake | Packet capture while idle and muted | E3, roadmap M10 |
| Camera interlock | No stream unless its indicator works. LED in series with camera power on anything we build | `research/ux.md` U20 |

---

## 9. Other devices

### AirPods

A route, not a product. Talk works through them [inference], iOS handles input mute itself [verified: Apple `setInputMuteStateChangeHandler` is macOS only], and push-to-talk does not map them. Announce Notifications may read Telegram messages from the bot with no code [inference, APP-T13].

### Apple Watch, only if Adam owns one

| Part | Pick | Why |
|---|---|---|
| Talk to Claw | Use | One turn, relayed through iPhone [docs-only: `D/platforms/ios.md`] |
| Approvals, allow once or deny | Use, RISK-T2 only | Through the iPhone relay. Direct Watch mode carries no approval prompts |
| Talk on Watch, standalone | Skip | Public-trust `wss://`, UDP with no TURN, `webrtc` transport. Tailnet-only fails away from the phone, and section 6.2 rules it out under the relay config. M1 Experimental, physical verification pending upstream |

**Steps:** Pair in Apple's Watch app. **Watch app → My Watch → Available Apps** → install OpenClaw. Open once on both. Accept: one Talk to Claw turn, one allow-once on a dummy.

### Wear OS

**Skip unless Adam gets an Android phone.** The companion uses the phone's Gateway connection, and the watch never holds credentials [docs-only: `D/platforms/android.md`]. It offers sessions, transcripts, text and dictated replies, abort and realtime Talk over the Data Layer. Android realtime uses the relay, so it fits our config [docs-only: `D/nodes/talk.md`], but Android live audio verification is "pending" upstream.

Facts to weigh:

- Wear OS and iPhone: Google states incompatibility only for Wear OS 3 [verified: https://support.google.com/wearos/answer/6056630]. Newer models are [unverified]. The decision does not hinge on it, because OpenClaw's path needs Android.
- Fixes for default assistant (#187587) and Talk ending at screen timeout (#187586) merged after 2026.10.9 [verified: GitHub PRs]. Release 2026.10.9 has no APK asset [verified: release list]. How the watch app reaches a watch is [unverified].
- EU notification forwarding on iOS could show Jorah's notices on one third-party watch, but it does not run OpenClaw's Wear app, and turns off Apple Watch notifications [secondary: MacRumors]. Shipped state in Slovakia is [unverified].

**If triggered (M30, Adam buys or owns the phone):**

| # | Who | Step | Accept |
|---|---|---|---|
| 1 | Claude | Re-read the Wear section of the installed docs and confirm the pin includes the two fixes | Written note |
| 2 | Adam | Install the Android app and Tailscale, pair with `openclaw qr --limited` | `nodes status` lists it |
| 3 | Adam | Install the watch app, by whatever route step 1 found | Opens on the watch |
| 4 | Adam | Run: select session, dictate a reply, abort a run, 10 minutes of Talk with wrist down | Each result recorded, battery noted |

A spare Android phone is also the only route to `sms.*` and notification reading, which an iPhone cannot give. Personal WhatsApp stays off either way.

### Smart glasses

**Do not buy.** D15 stands, and it is off the committed roadmap.

| Product | State on 2 Nov 2026 | Verdict |
|---|---|---|
| Ray-Ban Meta Gen 2 and others on the list | Toolkit 1.0 stable, Developer Mode allows own unpublished app. **Slovakia not on Meta's list, Austria is** [verified: https://www.meta.com/help/ai-glasses/4961066940605960/, https://developers.meta.com/wearables/faq]. Whether Developer Mode works from Slovakia is [unverified]. Mic 8 kHz mono | Blocked |
| Ray-Ban Meta Gen 3, $449 | Not on the toolkit's device list | Recheck before any purchase |
| Android XR | Launch reports conflict, from November to mid-December. Regional availability is unannounced and no EU market was found [secondary: search summary, `research/vision.md`]. Camera API is Android only | Wait |
| Even Realities G2, $599 | No camera, no speaker | Maybe a display later |
| Brilliant Halo | Shipping and price [unverified] | Do not order |

**The gate, at M30 only:** Slovakia on Meta's list, or Adam accepts the risk of an Austrian unit that may not work here.

**Free step first, no purchase:** VisionClaw's phone mode tries the same idea with the iPhone camera [verified: https://github.com/Intent-Lab/VisionClaw]. Its LICENSE is not open source and points to Meta's terms, so use it as a personal reference only. **Do not copy its `bind: "lan"` gateway setup.**

**If the gate opens:** own iOS app in Developer Mode, 8 kHz mic test, phone mic for wake if needed, 1 hour of real use with battery, heat and hinge-close reconnect recorded [track: `research/vision.md` V6]. That app is a separate decision from Jorah Remote.

**Rules for any glasses** [inference]: indicator tied to camera power, audio only in the ear, no proactive visuals while moving, guest rules for everyone in view, no RISK-T3 approvals, no vision at school. Rules on wearables in public are unsettled in the EU [secondary: Noerr, in `research/vision.md`]. No emotion inference.

### The rest

| Device | Decision |
|---|---|
| CarPlay | Skip. Voice category exists since iOS 26.4 [verified: https://developer.apple.com/carplay/], but entitlement approval for a one-user app seems doubtful [inference] |
| iPad | Same app, sidebar at 800 pt. A docked iPad is a decent wall panel if one exists. No purchase |
| Spare phone on a charger | Foreground, keep-awake ear, only if one exists. It breaks the one-ear rule until the broker exists |
| OBSBOT Tiny 2 Lite | Owned by `research/vision.md`, €199, buy with easy returns. Lite UVC is [unverified] |
| iPhone as arm camera | No. `camera.*` is foreground only with 60 s clips [docs-only: `D/nodes/camera.md`] |
| BLE pocket clicker | ESP32 learning project, only with an own app after S1 |
| Phone call into Voice Call | Not now. Weak auth, public surface, M1 |
| Windows PC screen | Browser Control UI and Telegram. No companion app. Windows Hub is optional, not load-bearing (section 8.2). Headless node per `02-architecture.md` |

---

## 10. Security rules for apps

Enforced from the first pairing. `research/security.md` owns the tiers.

1. A phone with `operator.admin` can drive the agent, and its Talk consults run as owner. Aim for Limited, with the runbook before pairing.
2. Setup codes are passwords. Tailnet only, with no Funnel or public endpoint.
3. Node commands stay narrow until each has a stated use. Before stage 1, mic and approvals only.
4. Plugin approval text is generic, because it reaches a third-party relay and the lock screen. That includes quotes from spoken notes (section 6.5).
5. Remove "Allow Always" on risky classes, and test that policy really removes it (SEC-T32).
6. Telegram is not end to end. RISK-T3 on Telegram is rejected, or the guard's own second factor exists (SEC-T20). OpenClaw documents no surface limit.
7. Voice never approves. Stop is honoured from anyone.
8. Phone and Mac stay user devices on the tailnet, not tagged, so Serve identity headers survive [track: `research/gap-post-cutover-workload-and-file-flow.md`].
9. Keep OpenClaw's iOS advisories in the upgrade check (GHSA-jjpc-p3xf-8g7p, GHSA-gcm4-fmcp-2f9r, GHSA-5j57-84cx-r295) [verified: GitHub API, in `research/openclaw-fit.md`].
10. Native fallback adds Apple as a recipient, since Talk may use network speech [docs-only: `D/nodes/talk.md`]. Disclose it.

---

## 11. Acceptance tests

All reach **signed-in device** tier unless noted. Record date, app and Gateway versions, result and what was seen on failure, in `docs/evidence/apps/`. Thresholds are proposals [inference]. T1 to T18 are from `research/apps.md` section 11, with changes marked.

| ID | When | Who | Steps | Pass |
|---|---|---|---|---|
| APP-T1 | M1 | Adam, Claude reads | Start under profile `jorah`. Menu bar → **Connection…**. `lsof -nP -iTCP:18789 -sTCP:LISTEN` | Connected to `jorah`, About shows 2026.10.9, nothing on 18789 |
| APP-T2 | M1 | Adam | "Hey Jorah", pause, "what time is it" at 1 m. Then 40 tries, half with music or TV | Partial text, then a reply. At least 90% at 1 m, 70% at 3 m, under 2 false wakes an hour |
| APP-T3 | M1 | Adam | Hold Right Option, speak, release | Sends within 2 s |
| APP-T4 | M2 | Adam, Claude reads | Scan, approve, `nodes status`. Wi-Fi off, Tailscale on, "ping". Chat open 10 minutes | Listed connected, reply arrives, drops noted ([#167179](https://github.com/openclaw/openclaw/issues/167179)) |
| APP-T5 | M2 | Claude, Adam watches | Section 6.3 step 5, locked, no Focus | Banner within 10 s. If it fails: toggle, then T18, then H4 |
| APP-T6 | M2 | Adam | Locked. Trigger an exec approval, repeat with a Focus on, repeat with a plugin approval | Generic text, **Review** opens the card, first answer wins. Note what Focus does, since alerts set no `interruption-level` [verified: `push-apns.ts`] |
| APP-T7 | M2 | Adam | Locked and unlocked: Action Button, "Hey Siri, Jorah", Lock Screen control. 10 timed Action Button tries | Median under 3 s. Note what Siri asks on iOS 27 in the EU |
| APP-T8 | M2 | Adam | 20 unlocked, 5 locked, 5 AirPods, 5 during Talk, 5 with Siri off. 8 hours of normal speech. **Added: 10 tries at the desk with Mac wake on, phone locked and unlocked** | At least 16 of 20, under 2 false triggers in 8 h. Battery and locked behaviour recorded. **Added: only one live mic session.** If both answer, change the phone phrase or drop the Vocal Shortcut |
| APP-T9 | M2 | Adam | Start Talk, background on, lock, "Name one animal" | Spoken answer, Live Activity, last words kept ([#171499](https://github.com/openclaw/openclaw/issues/171499)), speakerphone loud enough ([#167810](https://github.com/openclaw/openclaw/issues/167810)) |
| APP-T10 | M2, repeat when a newer Store build ships | Adam | Record the Store version first. 10 minutes on cellular with a slow consult, same on the Mac. Force a Talk failure during a consult | Call does not end from latency on a build carrying the fix. **On 2026.10.70 a drop is expected and is not a verdict on relay** (6.2). Note whether the consult answer survives |
| APP-T11 | M2 | Adam | T9 with AirPods, stem mute, a call, Siri, Music | Route, echo, mute, what ends the session, recovery |
| APP-T12 | M2 | Adam | 30 minutes kept-alive Talk with AirPods from 80% | % used, thermal state. No target yet |
| APP-T13 | M2 | Adam | AirPods on, phone locked, Telegram message from the bot | Whether Siri reads it |
| APP-T14 | M12 | Adam | 720p proxy via `MEDIA:`, then a 200 MB file. Tailnet review page in Safari on cellular, then from a `show_widget` | First plays with seek, second fails visibly, real caps recorded, page seeks under 2 s |
| APP-T15 | M2 | Adam | VoiceOver on, approve through T6 | All controls read correctly |
| APP-T16 | Each upgrade | Claude | Compare Store version before updating the Gateway | No `protocol mismatch` after |
| APP-T17 | Only if Voice Wake on iPhone is wanted | Adam | Airplane mode, Tailscale off, foreground, Voice Wake on, "Jorah test", then off | Logs whether it ran offline. Failure means network speech, so it stays off |
| APP-T18 | M2 | Adam, after a yes | Over Serve HTTPS in Safari: **Share → Add to Home Screen**, open it, pair, **Settings → Notifications → Enable notifications**, **Send test**. Agent finished on, detail Private. Lock. Short job, then an approval | Banners with generic text, tapping opens the request. Note Focus, and delivery with Tailscale off |
| APP-T19 (new) | M2 | Adam, Claude reads | Start Talk by Action Button and Vocal Shortcut, ask one question, read the session key and the consult's `senderIsOwner`, under Full and under Limited | `agent:voice:…`, never `main`. iOS and macOS route handling is unproven ([#167696](https://github.com/openclaw/openclaw/issues/167696)). Owner under Full, non-owner under Limited, or a recorded reason. A failure on `main` blocks M4 |
| APP-T20 (new) | M2b for notes, M4 for `private_show` | Adam, Claude reads | From a `jorah-talk` call: trigger a `private_show` card and a Keep, Change, Forget card, on iPhone and Mac. Let one approval expire. Include a body over 512 characters on an approval. Use a canary quote | Cards render by the section 6.5 route, push and lock screen show generic text, canary absent from the provider log **and from the relay payload**, tap reaches `main`, an expired card leaves the note waiting, injected session absent from memory search, real card limit recorded |
| APP-T21 (new) | M10 | Adam | Throw the switch while Jorah is listening. Try to unmute by voice | Device gone from the audio list under 1 s, packet capture quiet, voice cannot unmute, trust report says "switch off" |
| APP-T22 (new) | M2 | Adam, Claude reads | Record the Store version. Start Talk by Action Button on a paid key, ask one question, stay silent 5 minutes with the app foreground, then again locked with background on. Read the orange dot, the session state and vendor usage. Then pull the network mid-session and note which speech path takes over | Written down: does anything close it, what it billed, whether a fallback named Apple. If nothing closes it, D19 stands. Repeat when a newer Store build ships |

---

## 12. Schedule and cost

| Milestone | Work here | Tests | One-off cost |
|---|---|---|---|
| This week | Adam's answers, section 13 | None | €0 |
| M1 | Section 5.2 | APP-T1 to T3, SEC-T7 | €0, headset assumed |
| M2 | Section 6, A7 log starts | APP-T4 to T13, T15, T18, T19, T22, SEC-T16 | €0 |
| M2b | Section 5.4, section 6.5 spike, E0 | APP-T3 re-run, T20 for notes | €0. Signing on the existing paid team [inference] |
| M3 | Generic approval text, trust report | SEC-T20, APP-T6 re-run | €0 |
| M4 | `private_show`, native-app decision at exit | APP-T20 | €0 |
| M6 | HUD job card, Telegram notices, Look | `research/vision.md` T0 | €0 |
| M7 | E1, placement, S2b | E1, S2b | €0 |
| M9 | Section 5.3, phone re-pair | E2 Mac path | €0 |
| M10 | Section 8.2 | E2, E3, APP-T21 | About €143, €5 to €15 for the switch |
| M12 | Review page with `research/creative.md` | APP-T14 | €0 |
| M27 | Optional XVF3800 satellite, DIY puck | Its own gates | €50 to €130 |
| M30 | Watch, Wear OS, glasses, on triggers | Section 9 | €0 to €401, more with a phone |
| M31 | S1, then N1 onward, on a trigger | Section 7 | $99 a year, likely paid |

**Prices:** Voice PE €59 MSRP [verified: home-assistant.io/voice-pe]. Speakerphone about €143 at one retailer [track: `research/voice.md` section 20]. Recheck both at order time, and check Slovak delivery. Adam places every order.

**Maintenance:** Store app and Gateway move independently, so one check per upgrade (APP-T16).

---

## 13. Adam decides

| # | Question | When | My pick |
|---|---|---|---|
| 1 | Which iPhone and iOS is the daily phone? Own AirPods, Watch, Android phone, spare iPhone or iPad? | Before M1 | Check Settings |
| 2 | OK to install OpenClaw.app and grant Mic and Speech, with Computer Control off? | M1 | Yes |
| 3 | OK for the `jorah` Gateway service, and a login helper for the app if wanted? | M1 | Service yes, helper only if reboots annoy |
| 4 | Is the hosted relay acceptable, knowing plugin approval text passes through it? | M2 | Yes, with generic text |
| 5 | Is Telegram OK for job notices, or generic Web Push if APP-T18 passes? | M2, M6 | Telegram with neutral text |
| 6 | Is Limited OK for daily use, knowing Activity, Workboard and Settings then need the Mac or a return to Full? | M2 | Yes |
| 7 | Keep Vocal Shortcuts on, with an always-on mic indicator, outside school? | M2 | Yes if APP-T8 passes, off at school |
| 8 | **Away from home, is Action Button plus Face ID enough?** This most decides any own app | M4 exit | Start with yes |
| 9 | Accept spoken yes then tap on 2026.10.9? | M2 | Yes, never patch the gate |
| 10 | Where does the PC sit, and is a USB speakerphone at that spot workable? | M7 | Tell me |
| 11 | Buy the speakerphone after M9, instead of the Voice PE in the roadmap's B5? | M9 | Yes |
| 12 | DIY puck at M27, or never? | M27 | Learning project only |
| 13 | Which Apple team signs the `jorah-talk` wrapper and `jorah-eyes`, and any later own app? Is it active? | M2b | Separate from Mizyun if a business is likely |
| 14 | Do you drive with CarPlay enough to care? | Any time | Skip |
| 15 | **Roadmap gate 4 says no daily realtime before idle close is proven, and the phone has none.** Accept deliberate phone sessions ended by hand as outside the gate, or native Talk only on the phone? | M2 | Deliberate sessions, background Talk off, read one week's bill |
| 16 (README decision 21) | Accept `jorah-talk` on the Mac at M2b (`04-voice-and-vision.md` D1)? | M2 | Yes |

---

## 14. Conflicts settled here

| Conflict | Settled as | Why |
|---|---|---|
| First room device: Voice PE (`research/apps.md` A6, roadmap B5 and M10 step 1, `research/engineering.md` 16.3), DIY puck (`research/ux.md` U16), `jorah-talk` on PC (room-ear gap) | **Room-ear gap** | Latest and code-read: right word, no firmware, no listener. Roadmap B5 and M10 steps 1 to 4 need editing |
| Roadmap "Not on the list: speakerphone" against the gap needing one at M10 | **Add it to the purchases, after M9** | Replaces Voice PE at about €143 against €59 to €158, so the total barely moves |
| PC trigger by `talk.ptt.*` (`research/apps.md`, `research/openclaw-fit.md`, `research/voice.md`, roadmap M10 step 6) | **`talk.session.*` over relay** | No handler in the CLI node or Hub. Source beats `D/platforms/windows.md` |
| Roadmap M10 "mute by switch" against a speakerphone with no hard mute | **USB power switch** [inference] | Keeps the test honest. Unbought, untested |
| Vocal Shortcut "Hey Jorah" against "exactly one ear" (`research/ux.md` section 11) | **Allowed, gated by a new APP-T8 line** | The phone only opens the app when unlocked, but both can hear the same phrase |
| Watch ruled out by Gemini only (`research/apps.md` A12) | **Ruled out by the relay transport** | Applies to the current pick too |
| `research/apps.md` 5.3 `gateway --tailscale serve` against `research/topology.md` A7 | **Topology: external route by `adam`** | Proof file is admin-only on this Mac |
| "Spoken yes, then tap" (`research/ux.md` U8) against one-step plan (voice-brain gap) | **Yes then tap on 2026.10.9, tap is the authority, re-test each upgrade** | Version-specific |
| Windows Hub as node (`research/openclaw-fit.md`) against headless node (`research/topology.md`) | **Topology.** Hub is not load-bearing | No Talk surface in its source |
| Job notices naming a job (`research/apps.md`) against neutral lines (private-data gap) | **Neutral for private-class work** | Telegram is not end to end |
| "Build nothing native" (`research/apps.md`) against a signed wrapper and `jorah-eyes` (`04-voice-and-vision.md`, `research/vision.md`) | **No companion app. Wrappers allowed for OS consent only** | Mic and camera grants need an app identity. Section 5.4 sets the limit |
| Idle-close helper (roadmap M2, `01-vision-and-ux.md` table, `02-architecture.md` component row) against "helper cannot close the app's session" (`04-voice-and-vision.md` section 2) | **`04-voice-and-vision.md`** | It read the owning-connection check. The other two still name a helper and need editing |
| Roadmap "real-time conversation, phone" at M2 against gate 4 | **Phone sessions by hand, Adam decides** | No close found in the tagged iOS source. Question 15 |
| Exact quote on the Keep card (`03-security-and-privacy.md` row 51, `01-vision-and-ux.md` U24) against generic approval text (`03-security-and-privacy.md` section on `requireApproval`) | **Generic approval, quote in an injected note** | Approval text reaches the relay. Section 6.5, untested |
| `private_show` "card on the app" (private-data gap, `06-connectors.md`) against `show_widget`'s capability rule | **`chat.inject` and panel** | A `jorah-talk` turn has no inline surface. Section 6.5, untested |
| `plugins/jorah-private-show/` (earlier draft of this file) against `plugins/jorah-bridge/` (`02-architecture.md`, `06-connectors.md`) | **`jorah-bridge`** | One plugin |
| E1 at M7 (`02-architecture.md`, first hour on the PC) against M10 (`04-voice-and-vision.md` M10.1, room-ear gap) | **M7** | It costs an hour, decides where the ear lives, and comes before any purchase |
| Mute "by switch if the device has one" (`04-voice-and-vision.md` M10.11) against a required switched line (`01-vision-and-ux.md` U16) | **Required for M10 acceptance** | Roadmap keeps "mute under 1 s by switch" |

---

## 15. Not confirmed

| Item | Settled by |
|---|---|
| App reaching a Gateway in another macOS user; direct URL to a Serve route on the same Mac | Section 5.2 step 6, APP-T1 |
| `openclaw-mac --profile jorah-app` launching the app as that profile, and keeping it across login | APP-T1 |
| Vocal Shortcuts locked behaviour, Siri dependency in the EU on iOS 27, battery | APP-T8 |
| Hosted push on Adam's phone (#146791) | APP-T5 |
| Any idle close on iOS realtime Talk (search found none) | APP-T22 |
| `chat.inject` scope and plugin access, `sendPrompt` in the native transcript, `jorah-talk` lacking `inline-widgets` | Section 6.5 spike, APP-T20 |
| Whether a plugin-approval decision can map to Keep and Forget cleanly | APP-T20 |
| Web Push on iPhone over a tailnet HTTPS origin | APP-T18 |
| Limited phone keeping approvals and device settings | Section 6.3 step 12 |
| A per-device override for `talk.realtime.transport` (none found) | Re-read at M2 with `talk.catalog` |
| Which Store build first carries the stall fix | APP-T10 |
| Whether `talk.agentId` holds on iOS and macOS Talk paths | APP-T19, SEC-T7 |
| Locked one-press talk by any path; Push to Talk capability today; App Review view of PTT for an AI | S1, then App Review if ever |
| WASAPI from an S4U task with nobody signed in | E1 |
| Serve and WSL latency, model time to first audio | S2b, E0 |
| `livekit-wakeword` accuracy on "Jorah" and on Windows | M10 step 2 |
| Voice PE stock and shop price at SmarterHOME, and running without Home Assistant | Before any order |
| A USB inline switch that suits the chosen speakerphone | Before M10 |
| iOS app lock covering notification actions and Watch | `research/ux.md` UX3 |
| Current Wear OS on iPhone, EU forwarding in Slovakia, delivery of the Wear app | Only if triggered |
| Meta Developer Mode from Slovakia, EU Gen 2 price, Android XR dates | Only at the glasses gate |
| EUR price of the Apple Developer Program in Slovakia | Invoice, if triggered |

**Checks made for this file:** Store listing re-read (2026.10.70, free, 3.4 from 71 ratings, iOS 26.2, no Slovak). Meta's country list re-read (Slovakia absent, Austria present). npm `latest` and GitHub latest release are still 2026.10.9. `/Applications/OpenClaw.app` still absent. Three web searches for Voice PE stock, the speakerphone price and Android XR, whose results came through a summarizer. Tagged iOS source searched, bundled docs and `dist` read, CLI help for `qr`, `devices`, `nodes`. Other prices and versions are as the tracks recorded them on 2026-11-02. **Nothing was installed, paired or run.**

---

## 16. Sources

**Research files:** `research/apps.md` (sections 2 to 12 and Verification), `research/ux.md` (sections 2, 6, 11, 12, 14, 19, 20, 21, 25, 26), `research/openclaw-fit.md` (sections 2, 3, 5, 9, 14), `research/vision.md` (sections 3, 7, 11, 13, 15), `research/gap-room-and-pc-ear-after-cutover.md`, `research/gap-private-data-through-realtime-providers.md`, `research/gap-voice-brain-context-and-delegation.md`, `research/gap-voice-to-motion-path-and-local-stop.md`, `research/gap-post-cutover-workload-and-file-flow.md`, `research/topology.md`, `research/security.md`, `research/voice.md`.

**Plan documents read for consistency:** `01-vision-and-ux.md`, `02-architecture.md`, `03-security-and-privacy.md`, `04-voice-and-vision.md`, `06-connectors.md`, `09-engineering-and-ops.md`.

**Bundled docs (`D/`):** `gateway/tailscale.md`, `web/webchat.md`, `plugins/sdk-overview/tools-and-commands.md`, `gateway/protocol/handshake.md`, `platforms/ios.md`, `platforms/macos.md`, `platforms/android.md`, `platforms/windows.md`, `platforms/mac/remote.md`, `platforms/mac/bundled-gateway.md`, `platforms/mac/permissions.md`, `platforms/mac/voicewake.md`, `platforms/mac/canvas.md`, `nodes/talk.md`, `nodes/talk/macos-relay.md`, `nodes/talk/client-ui.md`, `nodes/talk/realtime-sessions.md`, `nodes/voicewake.md`, `nodes/camera.md`, `nodes/command-policy.md`, `nodes/computer-use.md`, `nodes/node-host.md`, `tools/show-widget.md`, `web/notifications.md`, `plugins/plugin-permission-requests.md`, `gateway/protocol/versioning.md`, `cli/qr.md`, `maturity/scorecard.md`.

**OpenClaw source (`GH/`):** `apps/ios/README.md`, `VERSIONING.md`, `project.yml`, `Sources/Model/NodeAppModel.swift`, `Sources/LiveActivity/LiveActivityManager.swift`, `Sources/StartLiveVoiceIntent.swift`, `apps/macos/Sources/OpenClaw/AppProfile.swift`, `apps/shared/OpenClawKit/.../RealtimeTalkRelaySession.swift`, `src/infra/push-apns.ts`, `src/infra/push-apns.relay.ts`, `src/gateway/server-methods/push.ts`.

**Web:**

- App Store listing: https://apps.apple.com/app/openclaw-ai-that-does-things/id6780396132
- Releases: https://github.com/openclaw/openclaw/releases
- Windows Hub: https://github.com/openclaw/openclaw-windows-node
- Voice PE: https://www.home-assistant.io/voice-pe/. Retailers, search summary only: https://www.domadoo.fr/en/box-domotique/7558-nabu-casa-home-assistant-voice-preview-edition-0860011789727.html?domid=39, https://thepihut.com/products/home-assistant-voice-preview-edition
- Speakerphone, search summary only: https://m.alza.at/jabra-speak2-55-uc-d7703043.htm?o=5
- Android XR, search summary only: https://androidauthority.com/samsung-smart-glasses-launch-date-3717873, https://www.rttnews.com/3695963/samsung-s-first-android-xr-smart-glasses-reportedly-set-for-november-2026-launch.aspx?type=alleco
- Adapter: https://github.com/e-jung/voice-pe-openclaw
- Push to Talk: https://developer.apple.com/documentation/pushtotalk/creating-a-push-to-talk-app.md
- `AudioRecordingIntent`: https://developer.apple.com/documentation/appintents/audiorecordingintent.md
- `PushToTalkTransmissionIntent`: https://developer.apple.com/documentation/appintents/pushtotalktransmissionintent.md
- Apple forums: https://developer.apple.com/forums/thread/748430, https://developer.apple.com/forums/thread/771457, https://developer.apple.com/forums/thread/815725, https://developer.apple.com/forums/thread/707980
- Side button, Japan only: https://developer.apple.com/documentation/appintents/launching-your-voice-based-conversational-app-from-the-side-button-of-iphone.md
- Siri AI in the EU: https://www.apple.com/newsroom/2026/06/due-to-dma-siri-ai-delayed-in-eu-for-ios-27-and-ipados-27/
- Vocal Shortcuts: https://www.apple.com/newsroom/2024/05/apple-announces-new-accessibility-features-including-eye-tracking/ (secondary how-to: https://mcmw.abilitynet.org.uk/how-to-perform-actions-on-your-device-using-vocal-shortcuts-in-ios-26-on-your-iphone-or-ipad)
- Live Activities: https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities.md
- App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- Developer Program: https://developer.apple.com/programs/
- CarPlay: https://developer.apple.com/carplay/
- Wear OS on iPhone: https://support.google.com/wearos/answer/6056630
- Meta toolkit FAQ: https://developers.meta.com/wearables/faq
- Meta supported countries: https://www.meta.com/help/ai-glasses/4961066940605960/
- VisionClaw: https://github.com/Intent-Lab/VisionClaw
- Claude Code terms: https://code.claude.com/docs/en/legal-and-compliance
