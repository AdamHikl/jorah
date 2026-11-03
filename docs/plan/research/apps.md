# Companion apps and devices

Track: what Jorah runs on in Adam's hand, on the desk and in the room. Written 2026-11-02 against OpenClaw 2026.10.9. This replaces the earlier pass of this file, which ran without web search. An independent re-check the same day corrected it in place; see the Verification section at the end.

## 0. How to read this file

**Bottom line.** Use the official OpenClaw Mac and iPhone apps first and build nothing native. An iPhone cannot be a dependable always-on "Jorah" microphone, so solve hands-free in layers:

1. The Mac listens for the wake word.
2. The iPhone gets a free spoken "Hey Jorah" through Apple's Vocal Shortcuts, plus the Action Button.
3. A room device comes later.

Use Telegram, not the iPhone app, for "job finished" notices. If Telegram is not enough, or the hosted push relay fails, try Web Push from the Control UI installed on the Home Screen (T18) before any native work. If a concrete trigger fires (section 8.2), first run a 2 to 3 day spike on one question: can an own app start talking from a locked phone with one press? Only then build a small separate app in stoppable milestones. Do not fork OpenClaw's apps.

**Evidence labels.**

- `[verified: X]`: I read X in this session. For OpenClaw source that means code at tag `v2026.10.9`, not a running app.
- `[docs-only: X]`: OpenClaw's own docs say so; not confirmed in code or on a device.
- `[secondary: URL]`: a third-party page or forum post. Weaker than `verified`, and check it before relying on it.
- `[inference]`: my reasoning or estimate.
- `[unconfirmed]`: I looked and could not establish it. Section 13 lists these.
- `[unverified]`: the independent re-check tried to confirm this and could not. Do not rely on it until a stated test or source settles it.

**Evidence tier for this whole track: source and docs only.** Nothing here has been installed, launched or accepted on Adam's devices. `/Applications/OpenClaw.app` does not exist and no node is paired [verified: local check]. Install, launch and signed-in device acceptance are all open gates (section 11).

**Path shorthand.**

- `GH/` = `https://github.com/openclaw/openclaw/blob/v2026.10.9/`
- `D/` = `/opt/homebrew/lib/node_modules/openclaw/docs/`
- "Code search" means GitHub code search, which covers the `main` branch today, not the tag. It finds no matches only as far as its index goes.

### What this pass changed from the earlier file

| Earlier claim | Now | Why it matters |
|---|---|---|
| "Hey Siri, Jorah" is the only free hands-free phone path | **Vocal Shortcuts** can run a Shortcut on a custom phrase without saying Siri | A real spoken "Hey Jorah" on iPhone with no code, at least while unlocked |
| Long jobs end with "Telegram message and app push" | The iOS app has **no job-finished push**. `nodes push` is documented as a test push, and one reporter says visible alerts were accepted but never shown | Telegram becomes the notice channel |
| Hosted push "just works" | **Open bug #146791**: the App Store app may never register for push, reproduced on iOS 27.0.1 | Test it before trusting approvals on the phone |
| BLE button is the reliable locked trigger | Apple engineers point to **`PushToTalkTransmissionIntent`** on the Action Button, and to **`AudioRecordingIntent`** | The own-app spike may need no hardware |
| iOS 27, EU and CarPlay not searched | **Siri AI is not on iPhone in the EU.** Side button stays Japan-only. **CarPlay has a voice app category** since iOS 26.4 | Closes those questions |
| Approval lock-screen text unknown | Exec approval text is generic. **Plugin approval title and description go through the relay and onto the lock screen** | Direct requirement on the guard plugin |
| `setInputMuteStateChangeHandler` for AirPods mute | That method is macOS only; iOS handles mute itself | Corrected |
| "Mac listing says macOS 26.2" | That line describes the iPhone app running on a Mac. OpenClaw.app needs macOS 15, and macOS 26 for voice | Corrected |

---

## 1. Decisions

| # | Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|---|
| A1 | Mac companion | Official `OpenClaw-2026.10.9-arm64.dmg`, matching the pinned Gateway, started under profile `jorah` and not from Finder (5.2) | Wake word, push-to-talk, overlay, approvals, node host and widget panel all ship | Own menu bar app | Wake fails on "Jorah", or the app cannot run against profile `jorah` without a service Adam rejects | €0 |
| A2 | iPhone companion | Official App Store app, currently 2026.10.70, free | Chat, Talk, background Talk, Live Activity, approvals, Watch and share sheet exist | Own-signed upstream build | Section 8.2 triggers | €0 |
| A3 | Custom native work | None now. If triggered: a new thin app in milestones, never a fork | Upstream changed `apps/ios` 137 times, `apps/macos` 182 and `apps/shared` 157 in 30 days | Patch fork | Upstream slows down a lot | 6 to 9 weeks if fully built |
| A4 | Always listening on iPhone | Do not chase it. iOS code suppresses background wake and Apple blocks background mic start in general | Nobody can give a third-party app a Siri-grade locked wake word | Kept-alive Talk with keyword gating (spike only) | A spike shows hours-long survival at acceptable battery | €0 |
| A5 | Spoken phrase on iPhone | **Vocal Shortcut "Hey Jorah"** running a Shortcut around Start Live Voice | Free, no code, custom phrase. Runs an intent that opens the app, so a locked phone will still want unlock | "Hey Siri, Jorah" Shortcut | Battery cost or false triggers too high (T8) | €0 |
| A6 | Room microphone | Home Assistant Voice PE as the first room device, **after** voice V1, not a first buy | Echo cancelling XMOS chip, dual mic, on-device wake, €59 MSRP, Slovak distributor listed (current stock [unverified]) | ReSpeaker XVF3800 (voice track's far-field pick) | Voice track's bridge proves unworkable | €59 plus time |
| A7 | Custom UI first | Server side only: `show_widget`, the Mac widget panel, a tailnet review page | Renders inside official apps; no signing or Store | Own app | Need for native lock-screen surfaces | Days, €0 |
| A8 | Job-finished and attention notices | **Telegram first.** Native macOS notice at the desk. App push for approvals only | No job-finished push exists in the iOS app, and Telegram already works | Web Push from the installed Control UI, which has an Agent finished category and skips the OpenClaw relay [docs-only; T18]. Own app with direct APNs only if that also fails | Telegram proves too noisy or leaks too much | €0 |
| A9 | Push for approvals | Accept the hosted relay, **after** T5 proves it works on Adam's phone | Only push path for the native Store build. Stays out of the design if it fails | Web Push from the installed Control UI (T18), then own build with direct APNs | Adam rejects a third-party relay, or T5 fails | €0 |
| A10 | Phone access level | Pair Full to configure, then try `--limited` for daily carry | A lost phone should not hold `operator.admin`. But the phone's own settings pages need admin | Stay Full with a lost-phone runbook | Device settings do not survive re-pairing, or approvals stop | €0 |
| A11 | Signing any own app | Development or Ad Hoc on the paid team, never public Store at first | Apple says family-and-friends apps do not suit the Store and points to Xcode or Ad Hoc | Internal TestFlight (90-day builds) | Business decision to ship | About €99 a year, likely already paid |
| A12 | Apple Watch | If owned: "Talk to Claw" through the iPhone and approvals. Skip standalone Talk | Scored M1. Standalone needs a publicly trusted endpoint, UDP without TURN, and a provider that speaks `gateway-control-v1`, so voice track's Gemini pick will not work | Own Watch app | Adam wants phone-free runs and accepts a public endpoint | €0 |
| A13 | Wear OS | Skip unless Adam gets an Android phone | OpenClaw's Wear path proxies through Android. Google says Wear OS 3 watches do not work with its iPhone app; newer models [unverified] (section 9) | Spare Android phone as host | Adam gets one | €0 |
| A14 | CarPlay | Skip | Voice category exists since iOS 26.4, but needs an own app and Apple's entitlement approval; no wake word; no vehicle or phone control | Bluetooth audio with kept-alive Talk | Adam drives daily with CarPlay and wants it | Own app plus approval risk |
| A15 | Smart glasses | Follow `vision.md` D10: not now | Slovakia not on Meta's list; needs its own iOS app | None | Vision track | €350 or more |
| A16 | First native step, if any | **2 to 3 day spike of locked one-press talk**, before any app design | It is the only gap an own app can close that nothing else can, and the evidence conflicts | Build milestones without the spike | Trigger H1 never fires | Time only |

---

## 2. What actually exists today

### 2.1 Availability and ownership

| App | State | Identity and owner | Evidence |
|---|---|---|---|
| iPhone, iPad | App Store, free, version 2026.10.70, updated "5d ago", seller OpenClaw Foundation, rating 3.4 from 71 ratings, requires iOS 26.2, Watch part requires watchOS 11. No in-app purchases mentioned | `ai.openclawfoundation.app`, `.share`, `.activitywidget`, `.watchkitapp`; team `FWJYW4S8P8`. Adam owns none of these | [verified: https://apps.apple.com/app/openclaw-ai-that-does-things/id6780396132], [verified: GH/apps/ios/Signing.xcconfig] |
| Store app versioning | Gateway version plus revision digit, so 2026.10.70 maps to Gateway 2026.10.7 with revision 0, two releases behind the pin [verified: GH/apps/ios/VERSIONING.md]. Client fixes after 2026.10.7 are not on the phone yet (see #180426 in 2.5) [inference] | | Protocol rule below |
| Mac | Signed DMG and ZIP on GitHub, Sparkle updates, not on the Mac App Store. Needs macOS 15; voice needs macOS 26. This Mac is on 27.0.1 | `ai.openclaw.mac`, debug `ai.openclaw.mac.debug` | [verified: release assets via `gh api`], [docs-only: D/platforms/macos.md, D/platforms/mac/permissions.md] |
| Android | Google Play and selected signed APKs; Wear OS companion through the phone | `ai.openclaw.app` | [docs-only: D/platforms/android.md] |
| Windows | Windows Hub published separately; latest stable `v2026.9.8-1`, 2026-10-07 | `openclaw/openclaw-windows-node` | [verified: `gh api`] |
| TestFlight | No public route in the docs or iOS README. Distribution is App Store plus local builds | | [verified: GH/apps/ios/README.md] |
| Maturity | iOS app M4 Stable (quality 80%), macOS M3 Beta (66%), Voice and realtime M2 Alpha (61%), watchOS M1 (41%), Voice Call M1 (41%) | | [docs-only: D/maturity/scorecard.md] |
| Third-party clients | `FPS1024/OpenClaw` calls itself a light iOS chat client: 0 stars, last push 2026-07-19. Not worth building on | | [verified: `gh api`] |

**Update risk.** The Store app and the pinned Gateway move independently. Operator and UI clients must support the Gateway's current protocol, while only node connections get an N-1 window [docs-only: D/gateway/protocol/versioning.md]. So a Store update could refuse a Gateway pinned too far behind [inference]. Keep the Gateway within a few weeks of the Store app, and treat `protocol mismatch` as the signal. The Mac app's docs say updates may be unavailable while a named profile is active, which suits pinning but means manual updates [docs-only: D/platforms/macos.md].

### 2.2 Adam's hardware facts

- This Mac: macOS 27.0.1, Xcode 27.2. `pnpm` and Tailscale are present. **`xcodegen`, `rustup` and `cargo` are missing**, and an upstream iOS build needs them [verified: local check, GH/apps/ios/README.md].
- `en-US` reports on-device recognition on this Mac; `en-GB`, `sk-SK` and `cs-CZ` do not [verified by sibling probe: `openclaw-fit.md`]. Passive wake refuses to run without on-device support, so **Mac wake must run in en-US**.
- An iPhone with model ID `iPhone17,1` appears as a Continuity camera on this Mac [verified: `system_profiler SPCameraDataType`]. As far as I know that is an iPhone 16 Pro, which has an Action Button and Dynamic Island [inference]. **Its iOS version is unknown** and the app needs 26.2.
- The keychain holds code signing identities for 2 different Apple teams [verified: `security find-identity`; IDs not reproduced]. Which is paid, and which should host Jorah, is Adam's call.

### 2.3 Size and churn, the real cost of forking

| Path | Code at tag | Commits on `main`, 2026-10-03 to 2026-11-02 |
|---|---|---|
| `apps/ios` | 4.5 MB in 308 files | 137 |
| `apps/macos` | 8.0 MB in 705 files | 182 |
| `apps/shared` (OpenClawKit, chat UI, Watch RTC) | 6.4 MB in 500 files | 157 |
| `apps/android` | 9.2 MB in 613 files | not counted |

[verified: `gh api` tree and commits]. Sizes count `.swift`, `.kt`, `.rs`, `.cs` and `.ts`, excluding localizations. Licence MIT.

### 2.4 Source findings that change the plan

1. **iPhone Voice Wake is foreground only, by code.** On `.background` the app calls `voiceWake.setSuppressed(true, reason: .background)` [verified: GH/apps/ios/Sources/Model/NodeAppModel.swift line 1146].
2. **The iPhone's speech claim and code disagree.** The usage string says "on-device speech recognition" [verified: GH/apps/ios/project.yml line 196]. Code search finds `requiresOnDeviceRecognition` only under `apps/macos`, and Apple documents that property as what stops audio going over the network [verified: https://developer.apple.com/documentation/speech/sfspeechrecognitionrequest/requiresondevicerecognition.md]. OpenClaw's docs also say Apple Speech on iOS may use network services [docs-only: D/nodes/talk.md]. **Consequence:** keep iPhone Voice Wake off until T17 settles it.
3. **iPhone wake sends text with no spoken reply.** It goes through `sendVoiceTranscript` [verified: NodeAppModel.swift line 1110]; "use Talk mode for spoken assistant replies" [docs-only: D/platforms/ios.md].
4. **Background Talk is real and Apple has seen it.** With "Talk in the background" on, continuous Talk stays live when locked, and OpenClaw's App Review script tests exactly that [verified: GH/apps/ios/APP-REVIEW-NOTES-APPLE.md, GH/apps/ios/Sources/Voice/TalkModeManager.swift `canKeepContinuousTalkActiveInBackground`]. It must already be running: a start while backgrounded is ignored and logged as "app backgrounded" [verified: TalkModeManager.swift lines 714, 2127]. Push-to-talk captures are cancelled on backgrounding [verified: same file, `suspendForBackground`]. Remote `talk.*` commands are blocked when backgrounded [verified: GH/apps/ios/README.md].
5. **Live Activity is local only.** Started with `pushType: nil`, so the Gateway cannot update it once the app is suspended [verified: GH/apps/ios/Sources/LiveActivity/LiveActivityManager.swift line 363]. State has a status enum, tool name and free-text `verbatimDetail`, but no progress value [verified: OpenClawActivityAttributes.swift]. A 40-minute render will not show live progress on the lock screen.
6. **No job-finished push.** `sendApnsAlert` is used by `push.test` and the "needs a quick reopen" nudge only [verified: GH/src/gateway/server-methods/push.ts, nodes.wake.ts]. Docs describe `openclaw nodes push` as a test push [docs-only: D/cli/nodes.md]. Two near misses: `push.test` does take custom title and body, so a job-end script could call it as an unsupported stopgap [inference]; and `openclaw nodes notify` or the agent's `nodes` tool `notify` action posts a local `system.notify`, which the README lists as foreground only on iOS [verified: GH/src/agents/tools/nodes-tool.ts, GH/apps/ios/README.md line 320]. A separate job-finished path exists outside the native app: Web Push (section 6).
7. **Approval alert text.** Exec approvals send fixed text, "Exec approval required" and "Open OpenClaw to review this request". **Plugin approvals send the request's own title and truncated description** [verified: GH/src/infra/push-apns.ts lines 443 to 475]. The whole payload is POSTed to the relay's `/v1/push/send` [verified: GH/src/infra/push-apns.relay.ts line 164]. **Consequence:** any guard plugin must write generic titles and descriptions, or its text reaches a third-party relay and the lock screen [inference].
8. **Approval alerts are ordinary alerts.** The payload sets no `interruption-level` [verified: push-apns.ts lines 84 to 106] and the base entitlements file has no time-sensitive entry [verified: GH/apps/ios/Sources/OpenClaw.entitlements]. A Focus mode may hold them back [inference; T6 tests it].
9. **No Home Screen widget, no Control Center control.** The widget bundle contains only the Live Activity [verified: GH/apps/ios/ActivityWidget/OpenClawActivityWidgetBundle.swift]; code search finds no `ControlWidget`.
10. **One App Intent.** `StartLiveVoiceIntent` with `openAppWhenRun = true` and the phrase "Start live voice with OpenClaw" [verified: GH/apps/ios/Sources/StartLiveVoiceIntent.swift]. Last changed in September [verified: `gh api` commits].
11. **No CarPlay, PushToTalk or AudioRecordingIntent.** Code search finds no `CPVoiceControlTemplate`, `PTChannelManager` or `AudioRecordingIntent`. Background modes are `audio`, `fetch`, `location`, `remote-notification` [verified: GH/apps/ios/project.yml lines 169 to 173].
12. **No biometric gate on approvals.** Code search finds no `LAContext`. The lock-screen "Review" action uses `.foreground`, so it opens the app and needs unlock [verified: GH/apps/ios/Sources/Push/ExecApprovalNotificationBridge.swift line 164; inference on unlock]. "Allow Always" appears when the request offers it [verified: GH/apps/ios/Sources/Gateway/ExecApprovalPromptDialog.swift line 207]. **This answers the open question in `security.md`:** T3 approval rests on the phone's own lock only.
13. **No Slovak.** The listing names 22 languages and neither Slovak nor Czech is among them [verified: listing].

### 2.5 Open upstream bugs that bear on this plan

State read today [verified: `gh api`]. Most are single-reporter and not reproduced by maintainers, so read them as things to test, not facts about Adam's setup.

| Issue | Claim | Why it matters | Test |
|---|---|---|---|
| [#146791](https://github.com/openclaw/openclaw/issues/146791) open | App Store app connects but never publishes `push.apns.register`. Reproduced by a reporter on iOS 27.0.1, Gateway 2026.10.5 | Approvals on a locked phone depend on it | T5 |
| [#178927](https://github.com/openclaw/openclaw/issues/178927) closed by a bot as a duplicate of #146791 (state reason `not_planned`, no fix) | Workaround: toggle the app's Notifications switch off and on. Follow-up: visible alerts accepted, never shown; silent wake reaches the phone, then the app disconnects after 2 to 3 s | Same | T5, T6 |
| [#120241](https://github.com/openclaw/openclaw/issues/120241) open | Relay push keeps replaying a stale cached registration after APNs `410 Unregistered`. The #178927 reporter hit a 410 first, then a 200 | A first failed test may not mean T5 has failed; repeat after a few minutes | T5 |
| [#180426](https://github.com/openclaw/openclaw/issues/180426) open, partly fixed | Two defects in the Apple client. **Stall:** the call ended after about 2 s of `appendAudio` backlog. Fix [#180572](https://github.com/openclaw/openclaw/pull/180572) is in the kit at tag `v2026.10.9` (3 s audio budget, 30 s liveness), but tag `v2026.10.7` still has the old limit of 48 [verified: `RealtimeTalkRelaySession.swift` at both tags]. **Consult cancel:** a Talk failure aborts the agent answer. Fix [#180571](https://github.com/openclaw/openclaw/pull/180571) merged to `main` on 2026-10-24 but is in neither `v2026.10.9` nor `v2026.10.10-beta.5` [verified: same file] | **Voice track's V1 uses `gateway-relay`.** The Mac app at 2026.10.9 has the stall fix. The Store iPhone app at 2026.10.70 maps to 2026.10.7, so it should still drop calls on a slow path [inference]. Do not judge cellular relay Talk on the phone until a Store build from 2026.10.9 or later ships | T10 |
| [#167179](https://github.com/openclaw/openclaw/issues/167179) open | iOS connection keeps dropping over Tailscale; thin report | Tailscale is our only remote path | T4 |
| [#182723](https://github.com/openclaw/openclaw/issues/182723) open | Node auth fails while the UI says Connected | Check `openclaw nodes status`, never the app's label | T4 |
| [#171499](https://github.com/openclaw/openclaw/issues/171499) open | iOS push-to-talk drops the last words | Affects Talk button use | T9 |
| [#167810](https://github.com/openclaw/openclaw/issues/167810) open | Talk output very quiet on speakerphone | Affects hands-free | T9 |
| [#97993](https://github.com/openclaw/openclaw/issues/97993) open | CarPlay request | No sign of native support yet | None |

The iOS README itself says "Foreground-first", with socket suspension and "occasional reconnect churn" [verified: GH/apps/ios/README.md]. That reads rougher than the docs' M4 Stable label, so plan by the README.

---

## 3. Must-have features versus OpenClaw's apps

Status words: **Yes**, **Partial**, **No**. All are source or docs tier, untested on device.

| Must-have | Mac app | iPhone app | Gap and honest note | Fix path |
|---|---|---|---|---|
| Wake word "Jorah" | **Yes**, on-device, en-US here, 32 triggers, global list [docs-only: D/platforms/mac/voicewake.md, D/nodes/voicewake.md] | **Partial**: app wake is foreground only, no spoken reply (2.4). Vocal Shortcuts adds a phrase outside the app [secondary] | Accuracy on the rare word "Jorah" is unknown (`openclaw-fit.md` 3.3) | Test. Room device for always-on |
| Push-to-talk | **Yes**, hold Right Option [docs-only] | **Partial**: Talk button. Remote `talk.ptt.*` foreground only | No hold-to-talk hardware path | Own app with PushToTalk |
| Action Button | n/a | **Yes**, Shortcut around Start Live Voice. Opens app; "does not bypass iOS unlock or foreground restrictions" [docs-only: D/platforms/ios.md] | Face ID step when locked | Accept. Spike if not enough |
| Siri | Not checked | **Yes**, fixed phrase or a Shortcut name. Apps need unlock on a locked phone [secondary: the poster's words in https://developer.apple.com/forums/thread/748430; Apple's reply there does not address Siri] | Phrase says "OpenClaw" unless wrapped | Shortcut named Jorah |
| Lock screen | n/a | **Partial**: Live Activity with status during Talk or tool work [verified: 2.4] | No lock-screen widget or control of its own | Add the Shortcut as a control [inference: T7]; own app |
| Approvals from phone | Native prompts for Mac-hosted commands [docs-only] | **Yes**: inbox, cards, Watch allow-once or deny, first answer wins across surfaces [docs-only: D/platforms/ios.md] | No Face ID; depends on push working; "Allow Always" one tap | Gateway policy to drop Always; Web Push as the alert path if the relay fails (T18); own app adds Face ID |
| Answer agent questions | Dashboard | **Yes**, native cards with options and expiry [docs-only] | None for MVP | None |
| Camera sharing | **Yes**: snap, clip, default off [docs-only: D/nodes/camera.md] | **Partial**: `camera.snap`, `camera.clip` up to 60 s, **foreground only**, needs command allow-list [docs-only] | No live stream from iPhone | Continuity Camera on Mac (`vision.md`); own app later |
| Location | `location.get`, default off [docs-only] | **Partial**: While Using or Always. App does not push location updates by itself, per [#163480](https://github.com/openclaw/openclaw/issues/163480) | Geofence automation is marked "Testing" in the README | Enough for now |
| Widgets | Widget panel [docs-only: D/platforms/mac/canvas.md] | **No** native widgets [verified] | `show_widget` renders inline in chat [docs-only: D/tools/show-widget.md] | Own app |
| Conversation history | **Yes** | **Yes**: offline read cache, 50-message outbox for 48 h [docs-only] | None for MVP | None |
| Live status | **Yes**: menu bar, overlay orb | **Partial**: Live Activity only while the app has runtime [verified] | Stale once suspended | Own app with ActivityKit push |
| Task progress | Dashboard Activity and Workboard | **Partial**: tool name only, plus embedded Activity and Workboard pages that need `operator.admin` [docs-only] | No progress value; no remote updates | Job card widget, Telegram milestones; own app |
| Job-finished notice | **Yes** for background-started sessions; generic text [docs-only: D/web/notifications.md] | **No** dedicated path in the native app (2.4). The installed Control UI has an Agent finished Web Push category [docs-only: D/web/notifications.md] | Decision A8 | Telegram, then T18 |
| Artifact preview, video review | **Yes**: inline player, seekable [docs-only: D/nodes/media-playback.md] | **Partial**: inline player, "Download file" up to 100 MB [docs-only] | A real edit will not fit (section 7) | Tailnet review page |
| Voice while phone locked | n/a | **Partial**: yes if Talk started in foreground with the setting on; "best-effort" [verified: review notes; docs-only] | Calls, Siri and other audio can end it | Accept; own app with PTT |
| Push notifications | Native | **Partial**: hosted relay, opt-in consent [verified: review notes], with open bug (2.5) | Third party in the path; local builds lose it unless direct APNs | T5, then A9 |
| AirPods | Route only | Route only, no stem gesture integration [inference from source] | iOS handles input mute itself [verified: https://developer.apple.com/documentation/avfaudio/avaudioapplication/setinputmutestatechangehandler(_:).md, method is macOS only] | T11 |
| Apple Watch | n/a | **Partial**: Talk to Claw, Talk on Watch [docs-only] | Upstream says wrist-down, routing, cellular and battery are unverified | A12 |
| Wear OS | n/a | Through Android phone only [docs-only] | Needs Android phone | A13 |
| CarPlay | n/a | **No** [verified: code search] | | A14 |
| Share to Jorah | Drag and drop | **Yes**: text, 1 URL, 10 images, 1 movie [verified: project.yml lines 259 to 263] | Open bug on share credentials, [#162011](https://github.com/openclaw/openclaw/issues/162011) | Shared folder for big files |
| Browse agent files | Dashboard | **Yes**, read-only Files with previews [docs-only] | None | None |
| Health | n/a | Optional today-only summary, off by default [docs-only: D/platforms/ios-healthkit.md] | Separate from Mizyun | Leave off |
| Accessibility | Not rated | Recent release notes mention larger accessibility text sizes [verified: listing]. Not otherwise rated | Test VoiceOver on approvals | T15 |
| Slovak | Wake not available on this Mac | No localization [verified] | English UI; `talk.speechLocale` could try `sk-SK` in Talk, and Apple Speech may then use the network [docs-only: D/nodes/talk.md] | Voice track |

**Verdict on MVP scope.** Most core features are Yes or a usable Partial with no code. The real gaps are: always-on on iPhone, remote task progress, large video review, biometric approval gate, and job-finished push in the native iPhone app. Server-side work, Telegram or Web Push covers video and notices. An own app could close progress, the biometric gate and locked one-press talk. Nobody can fully close always-on.

---

## 4. iPhone always listening: what is really possible

**The honest answer: no third-party app gets a Siri-grade locked wake word.** Apple's side-button route is Japan only, the official app stops at the foreground, and background mic start is blocked in general.

What Apple's own material says:

- **Background start is generally not allowed.** An Apple engineer wrote that generally an app cannot start audio recording while in the background, and pointed to `AudioRecordingIntent` as an alternative [verified: https://developer.apple.com/forums/thread/771457, Jan 2025].
- **`AudioRecordingIntent`** (iOS 18+) tells the system the app records audio. The app must start a Live Activity when recording begins and keep it active or the recording stops [verified: https://developer.apple.com/documentation/appintents/audiorecordingintent.md].
- **`LiveActivityIntent`** (iOS 17+) lets the system launch the app process without opening the app and start a Live Activity from a control [verified: https://developer.apple.com/documentation/appintents/liveactivityintent.md].
- **Conflicting report.** A developer got "Target is not foreground" trying this from Shortcuts or the Action Button, and a non-Apple reply says the first start must be in-app [secondary: https://developer.apple.com/forums/thread/815725, Feb 2026]. That error came from the Live Activity start, so a `LiveActivityIntent` conformance might change the outcome [inference]. **Unsettled. Spike S1.**
- **PushToTalk is the one documented background mic path.** The system activates the session, "even if the app is in the background" [verified: https://developer.apple.com/documentation/pushtotalk/creating-a-push-to-talk-app.md]. An Apple engineer, answering a question about locked phones, listed three routes: Lock Screen system UI, a CoreBluetooth event, and `PushToTalkTransmissionIntent` on the Action Button or widgets [verified: https://developer.apple.com/forums/thread/748430, June 2024]. An Apple engineer repeats the Controls route in a later thread [verified: https://developer.apple.com/forums/thread/773981, Apr 2025]. The intent is iOS 17.4+ [verified: https://developer.apple.com/documentation/appintents/pushtotalktransmissionintent.md]. The thread does not state outright that the Action Button works while locked, so test it.
- **Costs of PushToTalk:** joining a channel needs foreground and explicit interaction. Only one channel is active system-wide. System sounds cannot be replaced. Calls take priority [verified: PushToTalk article]. The system UI cannot be hidden [verified: https://developer.apple.com/forums/thread/770491, Dec 2024]. Apple describes it as a "walkie-talkie style app".
- **Wired headsets and CarPlay map to transmit; AirPods are not listed** [verified: PushToTalk article].
- **Side button for voice apps is Japan only**, needs `com.apple.developer.side-button-access.allow`, and the Apple Account and the physical location must both be in Japan on production devices [verified: https://developer.apple.com/documentation/appintents/launching-your-voice-based-conversational-app-from-the-side-button-of-iphone.md]. Slovakia does not qualify.
- **Siri AI is not on iPhone or iPad in the EU** with iOS 27, with no timeline; watchOS 27 is also excluded because it needs a paired iPhone with Siri AI. macOS 27 is included. EU-based developers cannot test the new Siri AI features in iOS, iPadOS or watchOS apps [verified: https://www.apple.com/newsroom/2026/06/due-to-dma-siri-ai-delayed-in-eu-for-ios-27-and-ipados-27/]. A Siri Extensions framework for third-party AI is reported as dormant in beta [secondary: https://thenextweb.com/news/apple-siri-extensions-third-party-ai-missing-wwdc]. **Do not plan around any of this.** Whether "Hey Siri, run this Shortcut" behaves differently in the EU on iOS 27 is unconfirmed; T7 checks it.
- **iOS 27 adds audio session deactivation notifications** that report whether the app or the system ended the session [verified: https://developer.apple.com/documentation/avfaudio/avaudiosession/deactivationsource.md]. Useful for honest status in an own app. It does not add background start, as far as I found.
- **Background modes are narrow:** `audio` is described as playing audible content, and 2.5.4 limits background services to intended purposes [verified: https://developer.apple.com/documentation/xcode/configuring-background-execution-modes.md, https://developer.apple.com/app-store/review/guidelines/].

**Vocal Shortcuts, the free find.** Settings, Accessibility, Vocal Shortcuts lets you teach the iPhone a phrase, spoken three times, that runs an action including a Shortcut, without saying Siri [secondary: https://mcmw.abilitynet.org.uk/how-to-perform-actions-on-your-device-using-vocal-shortcuts-in-ios-26-on-your-iphone-or-ipad]. Apple's own announcement describes assigning "custom utterances that Siri can understand" to launch shortcuts [verified: https://www.apple.com/newsroom/2024/05/apple-announces-new-accessibility-features-including-eye-tracking/]. So whether it depends on Siri settings, and how it behaves in the EU on iOS 27, is [unverified]; T8 checks it. Apple's guide page exists for iOS 27, 26 and 18, and a search snippet says a status bar indicator shows it is listening [secondary: search snippet of https://support.apple.com/en-hk/guide/iphone/iph7f242ea2c; the article body would not load]. Limits reported:

- Works when locked only for shortcuts that do not need unlock, and opening an app does need it. **[unverified]**: only an earlier search snippet of https://www.techradar.com/phones/this-new-ios-18-voice-control-feature-could-be-even-more-useful-than-the-new-siri says so; the page body was not readable on re-check, and Apple's guide body would not load either. T8 settles it.
- Orange dot always on, processed on device, can drain battery, and existing phrases cannot be edited, per one third-party article; Apple's announcement makes no on-device statement for this feature [secondary: https://ios.gadgethacks.com/how-to/unlock-power-vocal-shortcuts-iphone-for-custom-voice-commands-without-saying-siri-0385638/].

Since Start Live Voice opens the app, expect: **phone unlocked gives a spoken "Hey Jorah" that starts Talk; phone locked gives an unlock prompt** [inference]. Unknown until tested: whether it pauses while Talk holds the mic, whether it hears through AirPods, and false trigger rate. Turn it off at school and anywhere an always-on indicator would be awkward [inference].

### Options, ranked for Adam

| Option | Hands-free? | Works locked? | Needs | Cost | Verdict |
|---|---|---|---|---|---|
| **Mac Voice Wake** | Yes | Mac must be awake and logged in | Official app | €0 | **Use now** at the desk |
| **Vocal Shortcut "Hey Jorah"** | Yes | Unlock needed to open the app [inference] | Shortcut, 2 minutes | Battery unknown | **Use**: best free phone phrase. T8 |
| **Action Button** | One press | Opens after Face ID | Shortcut | €0 | **Use**: daily driver away from home |
| **"Hey Siri, Jorah" Shortcut** | Yes | "You'll have to unlock" [secondary: poster in forum 748430] | Shortcut, Siri settings | €0 | **Fallback**, also works through AirPods [inference] |
| **Kept-alive Talk**, AirPods, phone in pocket | Yes after first start | Yes until interrupted | App setting | Battery, plus every utterance reaches the model | **Use selectively** on walks. No battery number exists: T12 |
| **Room device** with on-device wake | Yes | Independent of phone | Voice PE, custom model, bridge | €59 | **Later**: the true always-on answer at home |
| **PC thin wake client** | Yes | PC always on | `livekit-wakeword` plus `talk.ptt.*` (`voice.md`) | Time | **Later**, after PC deploy |
| **Spare phone on a charger**, foreground, keep-awake | Yes | Stays unlocked, foreground | Spare device. Android wake is on-device and foreground-only [docs-only: D/nodes/voicewake.md] | €0 if owned | **Maybe**, if one exists |
| **Own app, Action Button, PTT or AudioRecording intent** | One press | Claimed, not proven | Own app, S1 | 2 to 3 day spike | **Spike if H1 fires** |
| **Own app, BLE button** | One press | Yes per Apple's article | Own app, ESP32 | Evening of firmware [inference] | **After spike**; good ESP32 learning |
| **Own app, keyword gating inside kept-alive audio** | Yes | Until interrupted; cannot restart in background [inference] | Own app | 1-week spike | **Not now**. Fragile; 2.5.4 risk under review; dot always on. Picovoice is out, since its free tier reportedly ended 2026-06-30 [secondary: a forum poster quoting Picovoice's email, https://community.home-assistant.io/t/fyi-picovoice-confirmed-free-tier-accesskeys-will-stop-working-after-june-30-2026/1012744; Picovoice's own pages would not load, so [unverified]] |
| **BLE pendant** with its own wake word (Omi pattern) | Yes | Yes | Hardware, firmware, own app | Months | **Far later**. Omi declares `audio`, `bluetooth-central`, `voip` and others [verified: https://github.com/BasedHardware/omi `app/ios/Runner/Info.plist`] |
| **Phone call**: "Hey Siri, call Jorah" into Voice Call plugin | Yes | Yes [inference] | Telco number, public webhook, caller allowlist; M1 [docs-only: D/plugins/voice-call.md] | Telco fees | **Not now**. Caller ID is weak auth and adds a public surface [inference] |

**Mental model to state plainly.** At the desk or at home: say "Hey Jorah". Phone in hand: say "Hey Jorah" to the phone, or press the Action Button. Long walk: start Talk once and keep AirPods in. Do not sell this as Jarvis everywhere.

### Room device detail

- **Voice PE:** dual mic, XMOS XU316 for echo cancellation, noise and gain, ESP32-S3 with 16 MB flash and 8 MB PSRAM, on-device microWakeWord with "Okay Nabu", "Hey Jarvis", "Hey Mycroft". MSRP €59 including tax. SmarterHOME is listed as shipping from Slovakia; its current stock and shop price are [unverified]. Home Assistant says training new wake words needs very powerful hardware and large datasets, and is impractical for most users [verified: https://www.home-assistant.io/voice-pe/].
- **Custom word:** ESPHome's `micro_wake_word` accepts a model by URL or local JSON [verified: https://esphome.io/components/micro_wake_word/]. The trainer `kahrendt/microWakeWord` is Apache-2.0, pushed 2026-07-09 [verified: `gh api`]. A self-trained model crashed one community user's Voice PE [secondary, via `voice.md`]. **"Hey Jarvis" works as a stop-gap on day one.**
- **Bridge:** `openclaw qr --voice-node` issues a node token plus an operator token limited to `operator.read` and `operator.talk`, the right minimal scope for a room box [docs-only: D/cli/qr.md]. Adapter `e-jung/voice-pe-openclaw` exists: experimental, MIT `LICENSE` file (GitHub's API labels it `Other`), 0 stars, pushed 2026-10-07 [verified: `gh api`]. Licence does not block reuse, but maturity might: read it first, and expect a fork or our own bridge. The voice track owns that. `voice.md` rates Voice PE "later, not a first buy" and I agree.
- **DIY XIAO ESP32S3 Sense** has no hardware echo cancellation, so a talking room box would hear itself [inference]. Good for the robot, not the room.

---

## 5. What to use first, exact setup

Each step that changes Gateway config, starts a service or changes automation needs Adam's explicit yes first. These are plan steps, not done.

### 5.1 Before anything (15 minutes)

1. iPhone: **Settings → General → About**. Expect iOS 26.2 or later.
2. Adam answers section 14.
3. Read `openclaw-fit.md` section 5 and `topology.md` "Adam's OpenClaw.app node". Turn off Allow Computer Control before pairing the Mac.

### 5.2 Mac app

1. Download `OpenClaw-2026.10.9-arm64.dmg`, verify, drag to `/Applications`. A fixed path keeps TCC grants [docs-only: D/platforms/mac/permissions.md].
2. **Do not open the app from Finder yet.** The app takes its profile only from `OPENCLAW_PROFILE` in its environment [verified: GH/apps/macos/Sources/OpenClaw/AppProfile.swift lines 15 to 22, 82 to 83]. A Finder launch is therefore the default profile, port 18789, state `~/.openclaw`. On a fresh profile the app hosts its own Gateway [docs-only: D/platforms/mac/bundled-gateway.md]. That would be a second, unhardened Gateway beside Jorah [inference]. Start it with `open --env OPENCLAW_PROFILE=jorah /Applications/OpenClaw.app` [inference; `--env` confirmed in `man open`]. `openclaw-mac --profile jorah status --json` also selects the profile and can start the app [docs-only: D/platforms/mac/remote.md], but whether the app it launches runs as `jorah` is [unverified]. Under that profile the app's default port is 43181, matching the Gateway [verified: computed with the hash in AppProfile.swift]. Login items will not carry the variable unless this is solved [inference]. T1 checks it.
3. **Named-profile question.** The Gateway is profile `jorah` on port 43181 in a foreground terminal. Docs say named profiles still require the listener to belong to that profile's Gateway service, and attach-only mode does not permit attaching another process or profile [docs-only: D/platforms/mac/bundled-gateway.md]. So **expect the terminal process to be refused and plan on a LaunchAgent**, for example `openclaw --profile jorah gateway install --port 43181` [docs-only: D/gateway/multiple-gateways.md]. That is a persistent service change: preview it and get Adam's yes. Docs name `primary set --local` for a Gateway on this Mac; `--direct-url` is documented for LAN or Tailnet endpoints [docs-only: D/platforms/mac/remote.md]. So `openclaw-mac --profile jorah primary set --direct-url ws://127.0.0.1:43181 --token-file <path>` is an off-label fallback only, and whether it works is [unverified].
4. **Dashboard → Settings → Talk → This Mac**: enable Voice Wake, language English (US). A native confirm appears with Cancel as default [docs-only]. Trigger words on the same page: replace defaults `openclaw`, `claude`, `computer` with `jorah`, `hey jorah`. The list is global across nodes [docs-only: D/nodes/voicewake.md].
5. Decide "wake starts Talk Mode". With it on, a command in the same breath is not forwarded [verified by sibling: `openclaw-fit.md` 3.3].
6. Run the wake test in `openclaw-fit.md` 3.3.

### 5.3 iPhone app

1. **Reachability, needs Adam's yes:** Tailscale Serve on a loopback bind so the phone gets `wss://` on the tailnet. Docs example adapted: `openclaw --profile jorah gateway --port 43181 --tailscale serve` [docs-only: D/platforms/ios.md]. Mobile pairing fails closed for Tailscale `ws://`, and plain LAN `ws://` auto-limits access [docs-only: D/cli/qr.md]. Tailscale must be on the phone too.
2. **Pair Full first:** `openclaw --profile jorah qr`. In app: **Settings → Gateway**, scan. Review role and scopes, then approve on the Gateway host with `openclaw --profile jorah devices list` and `openclaw --profile jorah devices approve <requestId>` [docs-only: D/platforms/ios.md]. Check `openclaw --profile jorah nodes status`, not the app's label, because of [#182723](https://github.com/openclaw/openclaw/issues/182723). Full comes first because Talk, notification, camera and permission pages are Dashboard pages needing `operator.admin` [docs-only].
3. **Push:** **Settings → This iPhone → Notifications** on. Accept "Enable OpenClaw Hosted Push Relay?" if you accept A9 [verified: review notes]. Then `openclaw --profile jorah nodes push --node <id> --title Test --body Test`. Expected: JSON with `transport: relay` and a banner on the phone. If no registration appears, toggle Notifications off and on [secondary: #178927]. A first `410 Unregistered` can be a stale registration, so retry after a few minutes [secondary: #178927, #120241]. If the Dashboard page shows browser Web Push as "not supported", that is the embedded page bug [#164557](https://github.com/openclaw/openclaw/issues/164557), not T18's installed app. If no banner, see T5.
4. **Talk:** **Settings → Talk → This iPhone**: turn on "Talk in the background". Leave Voice Wake **off** (2.4). Leave camera commands unapproved until needed.
5. **Shortcut:** **Shortcuts** app → **+** → add OpenClaw **Start Live Voice** → name it **Jorah**. Check it runs.
6. **Action Button:** **Settings → Action Button** → swipe to **Shortcut** → choose **Jorah**.
7. **Vocal Shortcut:** **Settings → Accessibility → Vocal Shortcuts → Set Up → Continue** → choose Shortcut **Jorah** → type "Hey Jorah" → say it three times. Decline the prompt to share recordings with Apple. Expected: a microphone indicator in the status bar. Run T8 before keeping it on.
8. **Siri fallback:** say "Hey Siri, Jorah" [inference: shortcut names work as Siri phrases; T7]. Documented fallback: "Start live voice with OpenClaw" [docs-only].
9. **Lock Screen and Control Center:** add the Jorah shortcut as a control if iOS offers it [inference: T7].
10. **Try Limited after T5, T6, T9:** `openclaw --profile jorah qr --limited`, scan, then re-run. Check Talk in the background survives, since it is a device preference [verified: `talk.background.enabled` in NodeAppModel.swift]. Check approvals still arrive, since docs say a paired `operator.approvals` connection must be "explicitly targeted by the Gateway" [docs-only]. If either fails, stay Full with the lost-phone runbook. Record the result.

---

## 6. Status, progress and notices without native code

- **Finish notice:** Telegram (A8). Job ends with a short message. Keep text generic where it would show on a lock screen.
- **AirPods trick:** Announce Notifications reads notifications from supported third-party apps when you wear compatible AirPods and the phone is locked; time-sensitive and direct messages are announced automatically [verified: https://support.apple.com/102536]. Telegram might qualify as direct messages, so Jorah could be heard with no code [inference: T13].
- **Progress:** agent uses `show_widget` to render a job card inline in iOS, Android and macOS chat [docs-only: D/tools/show-widget.md]. `sendPrompt` handles "Pause" or "Show me".
- **Mac HUD:** a hosted page in the Mac's floating panel, the cheapest Jarvis-style HUD [docs-only: D/platforms/mac/canvas.md]. Use the state vocabulary from `ux.md`, and never draw status the system cannot confirm.
- **Second client, and the first fallback.** The Control UI gets browser push, sent directly to the browser vendor and not through the OpenClaw relay. Approval notices are on by default. Agent finished and agent questions are opt-in. The Private detail level sends generic text, and excerpts, prompts, arguments and output never enter the payload. On iPhone it works only from the Home Screen install: **Share → Add to Home Screen**, then enable it inside that app [docs-only: all D/web/notifications.md]. This avoids Telegram's content exposure and the #146791 registration bug, so it is the next step for notices (A8) and for locked approval alerts (A9, H4) [inference]. Docs recommend an HTTPS origin per Gateway, which Tailscale Serve should provide; opening the result needs the tailnet [inference]. Nothing here has run on Adam's phone: T18. Bug [#164557](https://github.com/openclaw/openclaw/issues/164557) concerns the page embedded in the native app.

---

## 7. Video review (the concrete artifact case)

Adam's flagship job, "edit my raw video and present it", breaks the chat path:

- 20 MB default chat attachment ceiling, `agents.defaults.mediaMaxMb` [docs-only: D/gateway/protocol/versioning.md]
- 16 MB shared default for video passthrough [docs-only: D/nodes/images.md]
- 100 MB document download on iOS [docs-only: D/platforms/ios.md]
- Transcode only for sources up to 20 minutes, at most 1080p, and it "never raises" the byte cap [docs-only: D/nodes/media-playback.md]

Exactly which cap applies on the `MEDIA:` path is unconfirmed; T14 measures it.

**Pick: the review page in `ux.md` section 18 and `creative.md`, served over Tailscale only.** One column on a phone, video on top, transcript below, cut list with reasons. Master stays on disk.

What this track adds:

- **Open it in Safari**, not the chat's isolated web view, unless T14 shows the web view can reach tailnet URLs. Tailscale must be on [inference].
- **Consequence:** in Safari, `sendPrompt` does not exist, so Approve, Change and time-coded notes need their own authenticated route on the Gateway host [inference]. The creative track owns that route. Without it, fall back to Adam typing "cut at 2:10" in chat.
- **Short proxies can still go inline:** a low-bitrate MP4 under the measured cap gives a quick look in chat [inference].
- **Upload to YouTube stays manual**, per `ux.md`.

**Accept test:** T14.

---

## 8. Fork, plugin or own app

### 8.1 Options

Effort is one learner with Claude Code [inference for all estimates; no data exists]. Adam knows Xcode and Transporter, which shortens signing work.

| Option | What it is | First delivery | Ongoing | Gains | Loses | Pick? |
|---|---|---|---|---|---|---|
| **P. Plugin and server side** | Skills, plugin tools, `show_widget`, node panel, tailnet pages. No new iOS native surface | 1 to 3 days per surface | Low | HUD, job cards, review page, no signing | Lock screen, widgets, new background modes | **Yes, now** |
| **B. Own-signed upstream build** | Same code, Adam's team and IDs through `apps/ios/LocalSigning.xcconfig`. Install `xcodegen`, `rustup` with `nightly-2026-10-02`, `.p8` on Gateway | 1 to 2 days | About half a day per pull | Direct APNs, no hosted relay | Store updates; HealthKit capability needs care | **Only if** relay is rejected, or T5 and T18 both fail |
| **F. Patch fork** | B plus rename and patches | 2 to 4 weeks | About 1 day a week at 137 iOS commits a month | All official features plus patches | Time, merge conflicts, protocol tracking | **No** |
| **N. New thin app, "Jorah Remote"** | New SwiftUI target using `OpenClawProtocol` and `OpenClawKit` at the pinned tag. Official app stays for admin | Milestones in 8.3 | About half a day per Gateway bump | Exact UX, PTT, ActivityKit push, Face ID, BLE | Chat rendering stays out of scope | **Yes, if triggered** |

Notes:

- `OpenClawKit` is MIT, offers `OpenClawProtocol`, `OpenClawKit`, `OpenClawChatUI`, `OpenClawNativeState`, and targets iOS 18, macOS 15, watchOS 11 [verified: GH/apps/shared/OpenClawKit/Package.swift]. It sits in a subfolder, so vendor it with `git subtree` at the pinned tag rather than a URL dependency [inference].
- Own builds **cannot** use the hosted relay: it requires App Attest and a StoreKit transaction from the official path [docs-only: D/platforms/ios.md]. Direct APNs uses `OPENCLAW_APNS_TEAM_ID`, `KEY_ID`, and `PRIVATE_KEY_PATH` on the Gateway [docs-only].
- **Plugins cannot add native iOS surfaces** such as Lock Screen widgets or background modes, because those need the app's signed binary and entitlements [inference].
- **Do not fork the Mac app.** TCC grants tie to signature and path [docs-only], it is the largest codebase, and it is M3 Beta.

### 8.2 Triggers to build

Measure after two weeks of daily use. Start spike S1 if **any hard trigger** fires, or **any two soft triggers**.

**Hard triggers**

- **H1.** Adam needs one-press talk with the phone locked and in a pocket, and Action Button plus Face ID is not acceptable.
- **H2.** Adam decides to commercialize, or the app must carry the Jorah name and privacy claims.
- **H3.** The safety review requires Face ID on phone approvals. `security.md` T3 rests on the phone's lock today (2.4).
- **H4.** T5 fails on Adam's phone, the upstream bug stays open after two more Store releases, **and** T18 also fails, so phone approvals do not arrive when locked. If T18 passes, approvals have a free path and this trigger does not fire.

**Soft triggers (thresholds are proposals [inference])**

- Action Button to "Listening" takes more than 3 s in over 20% of tries.
- Background Talk dies more than once per 30 minutes of walking.
- Jobs over 10 minutes are common and Telegram still leaves Adam opening the app to check status at least daily.
- Hosted push relay becomes unacceptable.
- Adam repeatedly wants live iPhone camera streaming that Continuity cannot give.

**Not triggers:** cosmetic preference alone, or wanting an always-on iPhone mic, because an own app does not solve that either.

### 8.3 Minimal scope, Jorah Remote

iPhone only, iOS 26 or later, English. Official app stays for settings, channels, skills and history. **Each milestone is useful alone, and Adam can stop after any of them.** Do not start N1 without the written A7 result (section 12).

| Milestone | Scope | Effort | Delivers |
|---|---|---|---|
| **S1 Spike** | See below. No OpenClaw code | 2 to 3 days | Yes or no on locked one-press talk |
| **N1 Status** | Pairing by setup code, Keychain, own device identity at the narrowest scope. Gateway-side `jorah-status` service holding the direct APNs key. Live Activity with `pushType: .token`, fields job, step, percent, state. Home Screen widget. Time-sensitive job-finished push | 1 to 2 weeks | Lock-screen progress, reliable notices |
| **N2 Approvals** | Approval card with canonical preview, Face ID before Allow, no Allow Always. Generic push text. Lost-phone revocation tested | About 1 week | H3 and H4 closed |
| **N3 Talk** | Large button, one status word, last transcript lines, stop. Talk over Gateway relay. App Intents with "Jorah" in the phrase, Control Center and Lock Screen controls. VoiceOver and Dynamic Type from day one | 2 to 3 weeks | Own voice surface |
| **N4 Locked press** | The path S1 proved, wired to N3. BLE button if useful | 1 to 2 weeks | H1 closed |
| **N5 Review** | AVPlayer on a tailnet URL, Approve, Change, timestamped note | About 1 week | Native review, if the page falls short |

**Total if all built: about 6 to 9 weeks, plus the spike. Far more likely: N1 and N2 only** [inference].

**Live Activity limits:** 8 hours active, up to 12 on the Lock Screen, 4 KB combined data [verified: https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities.md]. Hourly push budget, so use priority 5 for routine updates; `NSSupportsLiveActivitiesFrequentUpdates` exists; push-to-start exists [verified: https://developer.apple.com/documentation/activitykit/starting-and-updating-live-activities-with-activitykit-push-notifications.md]. Fine for a render job.

**Out of scope:** chat history rendering, settings, skills, sessions, camera streaming, Watch, CarPlay, Health, iPad layouts, localization.

**v2 candidates, each needing its own decision:** Watch complication, CarPlay voice category, BLE pendant, camera streaming for robots, glasses.

### 8.4 Spike S1: locked one-press talk

**Question:** on Adam's iPhone, locked, in a pocket, can one Action Button press get a live mic in under 1.5 s, without Face ID, and play a reply?

**Setup.** A throwaway app on the paid team with Development signing. No Gateway code. Registering an App ID and adding capabilities changes Adam's developer account, so it needs Adam's yes. The Push to Talk capability looks self-service: Apple's article lists no request step and a 2022 Apple reply names only accepting the licence agreement [verified: PushToTalk article, https://developer.apple.com/forums/thread/707980]. Could be different today [unconfirmed].

| Path | Build | Check |
|---|---|---|
| **A. PTT** | Push to Talk capability, `push-to-talk` background mode, Push Notifications. Join a channel in foreground. App Intent adopting `PushToTalkTransmissionIntent`; hold the result until `didBeginTransmittingFrom` per the Apple engineer's advice. Record after `didActivate`. Send a reply with a `pushtotalk` APNs push, topic `<bundle>.voip-ptt`, priority 10 | Works locked? Face ID asked? How intrusive is the system UI? Does a reply wake and play? |
| **B. AudioRecording** | Intent conforming to `AudioRecordingIntent` and `LiveActivityIntent`, placed on the Action Button. Start the Live Activity, then the audio session | Does it start at all from locked, or does it fail with "Target is not foreground" or `cannotStartRecording`? |

**Pass:** 9 of 10 tries per path, phone locked in a pocket, mic live under 1.5 s [inference on thresholds]. Record: time to mic, interruption by a call or Siri, battery over 30 minutes.

**Outcomes.**

- B works: prefer it, as it avoids walkie-talkie UI.
- Only A works: use it and accept the system UI and sounds.
- Neither works: H1 cannot be solved by an own app. Say so, and drop N4.

**Ties to robotics:** a pocket clicker is a small ESP32 BLE project, and Apple documents a CoreBluetooth characteristic change as a begin-transmission route [verified: PushToTalk article].

### 8.5 Signing, distribution, cost

| Item | Fact | Evidence |
|---|---|---|
| Apple Developer Program | $99 per year [verified: https://developer.apple.com/programs/]. €99 reported for the EU; Slovak price [unverified]. Adam ships Mizyun, so likely already paid [inference] | [secondary for EUR: https://www.cultofmac.com/news/apple-increases-dev-program-membership-prices-europe] |
| Free account | Profiles and App IDs expire after 7 days, 3 devices, 3 apps per device. Unusable here | [verified: https://developer.apple.com/support/compare-memberships/] |
| Personal install | "If you build an app that you just want to show to family and friends, the App Store isn't the best way"; Xcode or Ad Hoc suggested | [verified: https://developer.apple.com/app-store/review/guidelines/] |
| TestFlight | 100 internal, 10,000 external, builds expire at 90 days, first external build reviewed | [verified: https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview] |
| Pick | Ad Hoc IPA for Adam's devices, with no App Store upload. Transporter stays Adam's route for Mizyun | [inference] |
| APNs key | New team key dedicated to Jorah, stored in the Gateway credentials dir at `chmod 600`, never in the repo | [docs-only: D/platforms/ios.md] |
| Bundle IDs | Own prefix, separate from Mizyun. New App Group and widget IDs | [inference] |
| Mac own app, if ever | Developer ID signing and a stable path for TCC [docs-only: D/platforms/mac/signing.md, permissions.md]. Notarization for distribution [inference] | |

### 8.6 If it ever goes to the App Store

Guideline text verified today at https://developer.apple.com/app-store/review/guidelines/; risk ranking is inference.

1. **Review access and server dependence.** The app must work for reviewers. OpenClaw runs a live review Gateway with demo scripts [verified: GH/apps/ios/APP-REVIEW-NOTES-APPLE.md]. Jorah needs the same, which is real operating cost and effort. 4.2.3(i) also expects standalone function.
2. **2.5.4 background services**: intended purposes only. OpenClaw passes with an explicit Talk demo. Always-listening keyword gating would be far harder to defend. Developers report rejections for background recording [secondary, via `voice.md`: https://developer.apple.com/forums/thread/91872].
3. **2.5.14 recording indication**: explicit consent and a clear indicator when recording.
4. **5.1.2(i) third-party AI**: clear disclosure and explicit permission before sharing personal data with third-party AI. Anthropic, OpenAI and Google all count.
5. **1.2 and 4.7**: filtering, reporting and contact duties; developer responsible for chatbot and plug-in behaviour.
6. **2.5.2 code**: skills and tools must run on the Gateway, never on the device.
7. **4.2.7 remote desktop**: LAN only, user-owned host; thin clients for cloud apps are not appropriate. A hosted Jorah that mirrors a computer would have to stay clear of this.
8. **Push to Talk for an AI.** Apple built it for walkie-talkie style services. An AI as the other party may be questioned; I found no Apple statement either way [inference, unconfirmed].
9. **HealthKit.** Leave out. Adam knows these rules from Mizyun.
10. **EU trader status** applies if sold. Adam's Mizyun team likely already handled this [inference].

**Privacy labels.** Apple's "collect" means data leaving the device so that you or third-party partners can access it longer than needed to serve the request in real time. Data processed only on device is not collected [verified: https://developer.apple.com/app-store/app-privacy-details/]. OpenClaw's listing says data is not collected, self-declared and not verified by Apple [verified: listing].

- Self-hosted Jorah with no developer backend: "Data Not Collected" looks defensible, but check APNs, crash reporting and analytics, and write it down [inference].
- Hosted Jorah for customers: Audio Data, Photos or Videos, Precise Location, Contacts, Other User Content, Identifiers and Diagnostics, all Linked to You, at minimum [inference].
- Purpose strings must be true. Do not copy OpenClaw's "on-device" string unless `requiresOnDeviceRecognition = true` is set or `SpeechAnalyzer` guarantees it (2.4).

---

## 9. Other devices

- **AirPods.** A route, not a product. Talk works through them [inference from source]. Mute gesture is handled by iOS; apps only get a notification [verified: Apple page in section 3]. PTT does not map AirPods [verified: PushToTalk article]. "Hey Siri" through AirPods reaches the fallback Shortcut, then asks for unlock [inference]. Announce Notifications is the useful free extra (section 6).
- **Apple Watch.** Talk to Claw relays through iPhone, one turn at a time, spoken-reply wait 90 s, approvals allow-once or deny [docs-only: D/platforms/ios.md]. A good wrist approval device. Standalone Talk needs a `wss://` certificate watchOS trusts; tailnet-only fails away from the phone, there is no TURN or TCP fallback, and the provider must support `gateway-control-v1` with ICE-lite [docs-only]. Voice track's Gemini choice would fail visibly here [inference]. Apple allows low-level watch networking only while streaming audio or in a CallKit call [verified: https://developer.apple.com/documentation/technotes/tn3135-low-level-networking-on-watchos.md].
- **Wear OS.** Phone-proxied by design; the watch never holds Gateway credentials [docs-only: D/platforms/android.md]. Google's iPhone setup page says watches on Wear OS 3 are not compatible with the Wear OS app, and does not address newer versions [verified: https://support.google.com/wearos/answer/6056630?hl=en&co=GENIE.Platform%3DiOS]. Pixel and Galaxy statements come from a 2023 article and a third-party page [secondary: https://www.digitaltrends.com/wearables/does-the-google-pixel-watch-work-with-an-iphone/, https://en.androidayuda.com/android-wear-ios-iphone/]. Today's models are [unverified]; the decision does not hinge on it, because OpenClaw's path needs an Android phone anyway. **EU twist:** Apple is opening notification forwarding to one third-party wearable in the EU, tested through iOS 26.3 to 26.5, with the Commission saying 2026. Only one device at a time, and turning it on turns off notifications on an Apple Watch [secondary: https://www.macrumors.com/2026/03/30/apple-airpods-like-pairing-notification-forwarding/]. Amazfit announced support [secondary: https://www.macitynet.it/amazfit-offre-le-notifiche-interattive-su-ios-per-alcuni-tipi-di-smartwatch-in-europa/]. That would let a non-Apple watch show Jorah's notices, but it does not run OpenClaw's Wear app. Whether it has fully shipped in Slovakia is unconfirmed.
- **CarPlay.** Apple lists a voice-based conversational app type [verified: https://developer.apple.com/carplay/]; press says it arrived with iOS 26.4. Reported rules: entitlement required, voice control screen, no vehicle or iPhone control, no wake word, so the user opens the app manually [secondary: https://macrumors.com/2026/02/18/ios-26-4-carplay-support]. Claude reportedly shipped it [secondary: https://www.igeeksblog.com/carplay-five-chatbot-apps/]; that is the Claude app, not Jorah. Apple reviews each entitlement request against criteria, and its current entitlement table does not yet list this category [verified: https://developer.apple.com/documentation/carplay/requesting-carplay-entitlements.md]. The guide PDF is larger than my fetch limit. Approval for a personal one-user app seems doubtful [inference]. Skip.
- **Spare Android phone.** Useful utility node: foreground service keeps it connected, Talk runs under a microphone foreground service, wake on-device in foreground, `sms.*`, notification forwarding [docs-only: D/platforms/android.md, D/nodes/talk/client-ui.md]. Android live audio verification is still "pending" upstream [docs-only: D/nodes/talk.md]. Relevant if Adam wants SMS or notification reading, which iPhone cannot give. Messaging track should weigh this.
- **iPad.** Same app, sidebar at 800 pt and wider [verified: GH/apps/ios/README.md]. A docked iPad is a decent wall panel if one exists.
- **PC.** Windows Hub for tray, chat, node and `talk.ptt.*`. No wake word [verified by sibling: `voice.md`]. Later thin wake client.
- **After the Gateway moves to the PC.** The Mac app goes to Remote mode over Tailscale; Voice Wake forwards automatically in remote mode [docs-only: D/platforms/mac/remote.md]. The phone needs a new setup code; the app keeps several Gateways, each with its own credentials [docs-only: D/platforms/ios.md].
- **Robots.** `camera.*` and `talk.*` on phones are foreground only with 60 s clips. **Do not** mount an iPhone as the arm's eye through the node path [docs-only: D/nodes/camera.md].
- **Glasses.** Vision track, D10.

---

## 10. Security notes specific to apps

For the security track to adopt.

- A phone with `operator.admin` is a remote control for an agent running as Adam's Mac user. Aim for `--limited` as daily state (A10). **Write the lost-phone runbook before pairing**; revocation is T16 in `security.md`.
- Setup codes contain a short-lived bootstrap token. Treat as a password [docs-only].
- Tailnet only. No Funnel or public endpoint for the phone.
- **Approval text:** keep plugin approval titles and descriptions generic (2.4). Exec text is already generic.
- **Allow Always:** the app cannot biometric-gate it, so remove the option by policy for risky classes. Docs say prompts offer "only the decisions offered by that request" [docs-only]. Test that a policy can actually remove it.
- **Lock-screen settings:** set Show Previews to "When Unlocked" for OpenClaw and Telegram [inference].
- Keep privacy-heavy commands (`camera.snap`, `camera.clip`, `screen.record`, `health.summary`, `sms.*`) out of `gateway.nodes.commands.allow` until each has a stated use [docs-only: D/nodes/command-policy.md].
- Keep iPhone Voice Wake off until T17 answers the on-device question.
- **Telegram as the notice channel is not end-to-end encrypted** (`security.md`). Job notices should name a job, not its content.
- Hosted push relay exposure: when and how often, plus plugin approval text. It also holds the raw APNs token [docs-only: D/platforms/ios.md].

---

## 11. Acceptance tests (next session)

Evidence tier reached by each: **signed-in device**. Record date, versions, result, and what was seen on failure. Thresholds are proposals [inference].

| ID | Steps | Pass |
|---|---|---|
| T1 Mac launch | Start the app under profile `jorah` (5.2), then menu bar → **Connection…**. Run `lsof -nP -iTCP:18789 -sTCP:LISTEN` | Connected to profile `jorah`. About shows 2026.10.9. Nothing listens on 18789, so no default-profile Gateway started |
| T2 Mac wake | Set triggers. Say "Hey Jorah", pause, "what time is it" at 1 m. Then full test in `openclaw-fit.md` 3.3 | Overlay shows partial text, then a reply in chat |
| T3 Mac PTT | Hold Right Option, speak, release | Message sends within 2 s of release |
| T4 Pairing and path | Scan Full code; approve. Run `openclaw --profile jorah nodes status`. Wi-Fi off, Tailscale on, send "ping". Leave chat open 10 minutes | `nodes status` lists the iPhone as connected; reply arrives; note any drops |
| T5 Push works | Section 5.3 step 3, phone locked, no Focus | Banner on lock screen within 10 s. **If it fails: try the toggle, then T18, then H4** |
| T6 Approval | Phone locked. Ask Jorah to run something needing approval. Repeat with a Focus on. Repeat with a plugin approval | Push shows generic text; **Review** opens the card; first answer wins against Control UI. Note what Focus does and what plugin text shows |
| T7 Gestures | Locked and unlocked: Action Button, then "Hey Siri, Jorah", then Lock Screen control | Time 10 Action Button tries; target median under 3 s. Note exactly what Siri asks on iOS 27 in the EU |
| T8 Vocal Shortcut | Set up per 5.3 step 7. Say "Hey Jorah" 20 times unlocked, 5 locked, 5 through AirPods, 5 during Talk, 5 with Siri turned off. Leave on 8 hours of normal speech, with battery noted | At least 16 of 20 unlocked; under 2 false triggers in 8 hours; record battery cost and locked behaviour |
| T9 Locked Talk | Start Talk, background setting on, lock, say "Name one animal" | Spoken answer; Live Activity on lock screen; last words not dropped; speakerphone loud enough |
| T10 Relay on cellular | Record the Store app version first: the stall fix needs a build from Gateway 2026.10.9 or later, and 2026.10.70 predates it. With voice track's relay provider: 10 minutes of Talk on cellular with a slow agent consult. Run the same on the Mac app. Then force a Talk failure during a consult | Call does not end from latency, per #180426. Note whether the consult answer survives the failure; that fix is not in 2026.10.9 |
| T11 AirPods and interruptions | T9 with AirPods; press stem to mute; receive a call; trigger Siri; play Music | Note route and echo, whether mute stops capture, what ends the session, whether it recovers |
| T12 Battery | 30 minutes kept-alive Talk with AirPods, starting at 80% | Record % used and thermal state. No target yet |
| T13 Announce | AirPods on, phone locked, dark; Telegram message from the bot. Enable Announce for Telegram if listed | Note whether Siri reads it |
| T14 Video | Post a 720p proxy via `MEDIA:`; then a 200 MB file; open a tailnet review page in Safari on cellular; try it from a `show_widget` too | First plays inline with seek; second fails visibly; record real caps. Tailnet page seeks in under 2 s |
| T15 VoiceOver | VoiceOver on, approve via T6 | All controls read correctly |
| T16 Update drift | Before updating Gateway, compare Store app version | No `protocol mismatch` after update |
| T17 On-device check | Airplane mode, Tailscale off, foreground. Enable iPhone Voice Wake; say "Jorah test". Then turn it off | Logs whether recognition runs offline. Failure means network speech, so it stays off |
| T18 Web Push | Needs Adam's yes. Over Tailscale Serve HTTPS, in Safari: **Share → Add to Home Screen**, open that app, pair it, **Settings → Notifications → Enable notifications**, **Send test**. Turn on Agent finished, set detail to Private. Lock the phone. Run a short job, then trigger an approval | Test and Agent finished banners on the lock screen with generic text; the approval alert arrives; tapping opens the request. Note what a Focus does, and whether delivery works with Tailscale off |

---

## 12. Plan to execute

Bounded steps, in order. Each ends at a stated evidence tier and a stop point.

| Phase | Work | Time | Done when |
|---|---|---|---|
| A0 | Section 14 answers; iOS version check | 15 min | Inventory written in `docs/` |
| A1 | Harden, install Mac app, T1 to T3 | Half a day | Device acceptance on Mac |
| A2 | Tailscale Serve (explicit yes), pair phone, T4 to T6 | Half a day | Device acceptance on phone, including whether push works |
| A3 | Shortcut, Action Button, Vocal Shortcut, T7 to T9, T11, T13, T15 | 3 hours spread over a day | Gesture table proven |
| A4 | Job card widget, Mac HUD panel, Telegram notices, T18 | 2 to 3 days | Shown live in chat and panel; Web Push result recorded |
| A5 | Tailnet review page with creative track, T14 | 1 to 2 days | A real proxy reviewed from phone |
| A6 | Voice V1 relay, T10. Room device only after voice V1 (explicit yes to buy) | With voice track | Room wake reaches Jorah |
| A7 | Two-week daily log; check 8.2 triggers | 2 weeks | Written go or no-go |
| B | Only if triggered: spike S1 | 2 to 3 days | Written yes or no on locked talk |
| C | N1, then decide; N2, then decide; and so on | 1 to 2 weeks each | Section 8.3 scope accepted on device |

If Adam rejects a mobile UI from C, restore the previous layout rather than refining it, per Adam's stated preference.

---

## 13. What I could not confirm

- **Vocal Shortcuts details from Apple.** The article body would not load; only a search snippet confirmed purpose and the indicator. Locked behaviour, on-device claim, battery and language limits are secondary or unknown. T8 replaces all of these.
- **Whether `PushToTalkTransmissionIntent` on the Action Button runs while locked.** An Apple engineer lists it when asked about locked phones but does not state it flatly. S1.
- **Whether `AudioRecordingIntent` can cold-start from a locked phone.** Apple staff point to it; a non-Apple reply says no; no authoritative answer. S1.
- **Whether Push to Talk still needs nothing beyond the licence agreement today.** Latest evidence is 2022.
- **Apple's view of PTT for an AI** at App Review. Found nothing.
- **iOS 27 changes beyond what I cite.** I searched and did not read the release notes or all WWDC26 sessions. Reports of Siri Extensions come from beta code.
- **Classic Siri and Shortcuts behaviour in the EU on iOS 27.** Apple's statement covers Siri AI; it does not describe what stays.
- **CarPlay guide text.** PDF over my fetch limit, so rules and the entitlement name come from press and third-party pages.
- **Notification forwarding's shipped state in Slovakia**, and any Wear OS support for it.
- **Wear OS plus iPhone from Google directly.** Secondary only.
- **Why the Store listing requires iOS 26.2** while source sets deployment target 18.0. Go by the listing.
- **EU Apple Developer price in EUR for Slovakia.**
- **Actual video cap on the `MEDIA:` path**, and whether chat web views reach tailnet URLs. T14.
- **Battery, latency, survival numbers for anything.** None exist for Adam's devices; every threshold is a proposal.
- **Whether a Limited phone keeps device settings and approvals.** T6 repeated under Limited.
- **Mac app attaching to a foreground named-profile Gateway.** T1.
- **Whether the upstream push bug hits Adam.** T5.
- **Voice Control custom commands** as another phrase path. Not researched.
- **Web Push on an iPhone over a tailnet HTTPS origin.** Docs only. T18.
- **Whether `openclaw-mac --profile jorah` launches the app as that profile**, and how to keep the profile across login. T1.
- **Voice PE stock and shop price at the Slovak distributor.**
- **Which Store build first carries the Talk stall fix.** Tag `v2026.10.8` was not checked; the listing shows 2026.10.70 today.

---

## 14. Questions for Adam

1. Which iPhone and iOS version is your daily phone? Is `iPhone17,1` it?
2. Do you own AirPods, an Apple Watch, an Android phone, or a spare iPhone, iPad or Android device?
3. Away from home, is Action Button plus Face ID enough, or do you need truly locked one-press talk? This one answer most decides whether an own app is needed.
4. Is the hosted OpenClaw push relay acceptable, knowing plugin approval text passes through it?
5. Is Telegram acceptable as the job-finished channel, given it is not end-to-end encrypted, or do you prefer generic Web Push alerts if T18 passes?
6. Is Limited access acceptable for daily use, knowing Activity, Workboard and all Settings pages then need the Mac or a return to Full?
7. Are you willing to keep Vocal Shortcuts on, with an always-on microphone indicator, outside school?
8. Which Apple team should host any future Jorah app, and is its paid membership active? A possible business later might want a separate organization team.
9. Do you drive with CarPlay often enough to care?

---

## 15. Dependencies on other tracks

- **Voice:** realtime provider and relay choice, and #180426 on `gateway-relay`: stall fix only from client builds of 2026.10.9, consult-cancel fix only on `main`, Store app still 2026.10.70; Gemini excludes Watch standalone; "Jorah" wake model; satellite bridge; PC thin wake client.
- **Security:** lost-phone runbook, Limited validation, approval policy that can remove Allow Always, generic plugin approval text in the guard plugin, hosted relay stance, Tailscale grants, allowed node commands. This track answers its open question: no Face ID on approvals.
- **Topology:** Tailscale Serve config, stable `wss://` when the Gateway moves to the PC, Mac app Remote mode, named-profile service decision.
- **UX:** Action Button and "Hey Jorah" phone gestures in the arbitration table (`ux.md` section 11 says Voice Wake off, and that still holds; Vocal Shortcuts is a separate OS feature). U14 should add job-finished notices via Telegram, because the app lacks them.
- **Vision:** live camera path, Continuity Camera, glasses app, shared status vocabulary.
- **Creative:** review proxy spec, review page, authenticated route for notes when opened in Safari.
- **Robotics:** ESP32 BLE clicker shares firmware skills; no iPhone as arm camera through the node path.
- **Connectors:** whether a spare Android node for SMS and notifications is wanted.
- **Roadmap:** keep the A7 go or no-go before any native build.

---

## 16. Sources

**OpenClaw, local docs (`D/`):** `platforms/ios.md`, `ios-healthkit.md`, `macos.md`, `android.md`, `windows.md`, `platforms/mac/voicewake.md`, `permissions.md`, `signing.md`, `remote.md`, `bundled-gateway.md`, `canvas.md`, `nodes/talk.md`, `nodes/talk/client-ui.md`, `nodes/voicewake.md`, `nodes/camera.md`, `nodes/command-policy.md`, `nodes/media-playback.md`, `nodes/images.md`, `tools/show-widget.md`, `web/notifications.md`, `gateway/protocol/versioning.md`, `plugins/voice-call.md`, `cli/qr.md`, `cli/nodes.md`, `maturity/scorecard.md`.

**OpenClaw, source at v2026.10.9 (`GH/`):**

- `apps/ios/README.md`, `VERSIONING.md`, `project.yml`, `Signing.xcconfig`, `LocalSigning.xcconfig.example`, `APP-REVIEW-NOTES-APPLE.md`
- `apps/macos/Sources/OpenClaw/AppProfile.swift`, `apps/shared/OpenClawKit/Sources/OpenClawKit/RealtimeTalkRelaySession.swift` (also at `v2026.10.7` and `v2026.10.10-beta.5`), `src/agents/tools/nodes-tool.ts`
- `apps/ios/Sources/StartLiveVoiceIntent.swift`, `OpenClaw.entitlements`, `Voice/VoiceWakeManager.swift`, `Voice/TalkModeManager.swift`, `Model/NodeAppModel.swift`, `Push/ExecApprovalNotificationBridge.swift`, `Gateway/ExecApprovalPromptDialog.swift`, `LiveActivity/LiveActivityManager.swift`, `LiveActivity/OpenClawActivityAttributes.swift`
- `apps/ios/ActivityWidget/OpenClawActivityWidgetBundle.swift`, `apps/shared/OpenClawKit/Package.swift`
- `src/infra/push-apns.ts`, `src/infra/push-apns.relay.ts`, `src/gateway/exec-approval-ios-push.ts`, `src/gateway/server-methods/push.ts`, `src/gateway/server-methods/nodes.wake.ts`

**OpenClaw, web:** https://github.com/openclaw/openclaw/releases, https://apps.apple.com/app/openclaw-ai-that-does-things/id6780396132, https://github.com/openclaw/openclaw-windows-node/releases, issues linked in sections 2.5 and 3.

**Apple, documentation and newsroom:**

- https://developer.apple.com/documentation/appintents/audiorecordingintent.md
- https://developer.apple.com/documentation/appintents/liveactivityintent.md
- https://developer.apple.com/documentation/appintents/pushtotalktransmissionintent.md
- https://developer.apple.com/documentation/pushtotalk/creating-a-push-to-talk-app.md
- https://developer.apple.com/documentation/appintents/launching-your-voice-based-conversational-app-from-the-side-button-of-iphone.md
- https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities.md
- https://developer.apple.com/documentation/activitykit/starting-and-updating-live-activities-with-activitykit-push-notifications.md
- https://developer.apple.com/documentation/xcode/configuring-background-execution-modes.md
- https://developer.apple.com/documentation/avfaudio/avaudiosession/deactivationsource.md
- https://developer.apple.com/documentation/avfaudio/avaudioapplication/setinputmutestatechangehandler(_:).md
- https://developer.apple.com/documentation/speech/sfspeechrecognitionrequest/requiresondevicerecognition.md
- https://developer.apple.com/documentation/technotes/tn3135-low-level-networking-on-watchos.md
- https://developer.apple.com/documentation/carplay/requesting-carplay-entitlements.md
- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/app-store/app-privacy-details/
- https://developer.apple.com/support/compare-memberships/
- https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview
- https://support.apple.com/102536
- https://support.apple.com/en-hk/guide/iphone/iph7f242ea2c (title and search snippet only)
- https://www.apple.com/newsroom/2026/06/due-to-dma-siri-ai-delayed-in-eu-for-ios-27-and-ipados-27/
- https://www.apple.com/newsroom/2024/05/apple-announces-new-accessibility-features-including-eye-tracking/
- https://developer.apple.com/carplay/
- https://developer.apple.com/programs/

**Apple Developer Forums** (Apple staff where stated in the text, otherwise community):

- https://developer.apple.com/forums/thread/771457
- https://developer.apple.com/forums/thread/815725
- https://developer.apple.com/forums/thread/748430
- https://developer.apple.com/forums/thread/773981
- https://developer.apple.com/forums/thread/770491
- https://developer.apple.com/forums/thread/707980

**Press and third party:**

- https://mjtsai.com/blog/2026/06/10/no-siri-ai-in-eu/
- https://thenextweb.com/news/apple-siri-extensions-third-party-ai-missing-wwdc
- https://macrumors.com/2026/02/18/ios-26-4-carplay-support
- https://www.igeeksblog.com/carplay-five-chatbot-apps/
- https://www.macrumors.com/2026/03/30/apple-airpods-like-pairing-notification-forwarding/
- https://www.macitynet.it/amazfit-offre-le-notifiche-interattive-su-ios-per-alcuni-tipi-di-smartwatch-in-europa/
- https://mcmw.abilitynet.org.uk/how-to-perform-actions-on-your-device-using-vocal-shortcuts-in-ios-26-on-your-iphone-or-ipad
- https://ios.gadgethacks.com/how-to/unlock-power-vocal-shortcuts-iphone-for-custom-voice-commands-without-saying-siri-0385638/
- https://www.techradar.com/phones/this-new-ios-18-voice-control-feature-could-be-even-more-useful-than-the-new-siri
- https://www.digitaltrends.com/wearables/does-the-google-pixel-watch-work-with-an-iphone/
- https://en.androidayuda.com/android-wear-ios-iphone/
- https://support.google.com/wearos/answer/6056630?hl=en&co=GENIE.Platform%3DiOS (Google, primary)
- https://community.home-assistant.io/t/fyi-picovoice-confirmed-free-tier-accesskeys-will-stop-working-after-june-30-2026/1012744
- https://www.cultofmac.com/news/apple-increases-dev-program-membership-prices-europe

**Hardware and wake word:**

- https://www.home-assistant.io/voice-pe/
- https://esphome.io/components/micro_wake_word/
- https://github.com/kahrendt/microWakeWord
- https://github.com/BasedHardware/omi
- https://github.com/e-jung/voice-pe-openclaw
- https://github.com/FPS1024/OpenClaw

**Sibling research used:** `docs/plan/research/openclaw-fit.md`, `voice.md`, `ux.md`, `vision.md`, `topology.md`, `security.md`, `creative.md`.

---

## Verification

Independent skeptic pass, 2026-11-02, against the same OpenClaw 2026.10.9. I tried to refute the claims the plan leans on most, using the bundled docs, source fetched at the tag with `gh api`, and direct fetches of the cited pages.

**Limits of this pass.** No device, install, launch or account step was run, so everything stays at source and docs tier. The session's web search budget was already spent, so my single search returned nothing and I only opened known URLs. Anything needing discovery, such as a shop page or a new forum thread, could not be searched. Apple's `.md` documentation came back verbatim; other pages came through a summarizer, so short quotes from those were checked only against that output.

**Does the recommendation still hold? Yes, with three changes.** Official apps first, nothing native, no fork, Telegram first for notices, and the locked-press spike only on a trigger all survive.

1. **A cheaper step now sits in front of own-app work.** Web Push from the installed Control UI carries approval alerts and an Agent finished category, without the hosted relay. So hard trigger H4 now also requires T18 to fail, A8 and A9 changed runner-up, and T18 is new.
2. **Mac setup has a trap the earlier text missed.** A Finder launch uses the default profile and can start a second Gateway. The LaunchAgent is now the expected path for profile `jorah`, not a fallback. It still needs Adam's yes.
3. **Relay Talk evidence changed.** #180426 is half fixed in the pinned tag, but the phone's Store build predates the fix. T10 must record versions, and a phone failure today would not condemn the voice track's relay pick. `voice.md` does not mention this issue, so the voice track should pick it up.

### Corrected

| # | Claim as written | Finding | Evidence |
|---|---|---|---|
| 1 | #180426: relay Talk ends after 2 s and aborts the consult, stated as current | Stall fixed at `v2026.10.9`, still present at `v2026.10.7`. Consult-cancel fix on `main` only, absent from `v2026.10.9` and `v2026.10.10-beta.5`. Issue still open | Kit source at each tag; PRs #180572, #180571 |
| 2 | Mac: try `primary set --direct-url ws://127.0.0.1:43181` first, LaunchAgent if refused | Docs name `--local` for this Mac and `--direct-url` for LAN or Tailnet. Attach-only cannot attach another process, so expect a LaunchAgent | D/platforms/mac/remote.md, bundled-gateway.md lines 273 to 274 |
| 3 | T1: just open `/Applications/OpenClaw.app` | Profile comes only from `OPENCLAW_PROFILE`; Finder launch means default profile, and a fresh profile hosts its own Gateway | `AppProfile.swift`; bundled-gateway.md line 24 |
| 4 | Web Push is a possible phone fallback, in passing | It is documented to carry approvals and Agent finished, with a Private level and no relay. Decisions A8, A9, H4 and option B updated | D/web/notifications.md |
| 5 | `voice-pe-openclaw` has no declared licence | It has an MIT `LICENSE`; the API reports `Other` | Repo file via `gh api` |
| 6 | Store version mapping was an inference | Now confirmed, with the consequence for client fixes | GH/apps/ios/VERSIONING.md |
| 7 | Live Activity state has status and tool name only | Also a free-text `verbatimDetail`. Still no progress value | OpenClawActivityAttributes.swift |
| 8 | #178927 "closed as duplicate" | Closed by a bot as duplicate, state reason `not_planned`, no fix. Added related open #120241 | `gh api` |
| 9 | "You'll have to unlock" attributed to the Apple thread | Those are the poster's words; Apple's reply does not address Siri | Forum 748430 |
| 10 | Wear OS: current watches do not pair with iPhone | Google states this only for Wear OS 3; the rest is a 2023 article. Marked [unverified]; decision unaffected | Google support page |
| 11 | No iPhone notification path from the agent, implied | `nodes notify` exists but is foreground only; `push.test` takes custom text. Noted as near misses, not as a supported feature | nodes-tool.ts, README line 320 |

### Could not confirm, marked [unverified]

- Vocal Shortcuts locked behaviour. The TechRadar body was unreadable and Apple's guide body would not load. Apple's 2024 announcement confirms the feature and links it to Siri, so a Siri dependency in the EU on iOS 27 is also open. **A5 therefore rests on T8.**
- Current Picovoice free tier state. Only a forum poster's quotes; Picovoice pages returned nothing.
- Voice PE stock and shop price at SmarterHOME.
- EUR price of the Apple Developer Program for Slovakia.
- Whether `openclaw-mac --profile jorah` launches the app as that profile, and whether `--direct-url` accepts loopback.
- EU notification forwarding's shipped state. Apple's Accessory Notifications page exists, but its body was empty in my fetch.

### Checked and held up

| Claim | Evidence I opened |
|---|---|
| Store app 2026.10.70, free, OpenClaw Foundation, 3.4 from 71 ratings, iOS 26.2, watchOS 11, 22 languages with no Slovak or Czech, privacy label self-declared | App Store listing |
| Mac DMG exists for 2026.10.9; macOS 15, voice needs macOS 26; updates limited under a named profile | Release assets; D/platforms/macos.md |
| Windows Hub latest stable `v2026.9.8-1`, 2026-10-07 (newer tags are alpha) | `gh api` releases |
| Churn: 137, 182 and 157 commits in 30 days | `gh api` commit pages |
| iPhone wake suppressed on background; sends text only; `requiresOnDeviceRecognition` only under `apps/macos`; "on-device" usage string | NodeAppModel.swift, project.yml, code search, Apple property page |
| Background Talk is real and in App Review script; push-to-talk and start blocked in background; README "Foreground-first" | Review notes, TalkModeManager.swift, README lines 362 to 368 |
| Live Activity `pushType: nil`; bundle holds only the Live Activity; one App Intent with `openAppWhenRun` | Source at tag |
| `sendApnsAlert` called only from `push.ts` and `nodes.wake.ts`, so no job-finished native push | Source at tag, code search |
| Exec alert text fixed; plugin title and description sent; whole payload POSTed to relay; no `interruption-level` | push-apns.ts, push-apns.relay.ts lines 241 to 245 |
| No Face ID, PTT, AudioRecording or CarPlay in iOS code; `.foreground` Review action; background modes list | Code search, bridge source, project.yml |
| Store build locked to hosted relay; own builds blocked by App Attest and StoreKit; relay holds raw APNs token | D/platforms/ios.md |
| Maturity scores M4 80%, M3 66%, M2 61%, M1 41% | D/maturity/scorecard.md |
| Background recording generally blocked; `AudioRecordingIntent` iOS 18 with Live Activity rule; `LiveActivityIntent` iOS 17; conflicting non-Apple reply | Forums 771457, 815725; Apple docs |
| PTT background activation, foreground join, one channel, no custom sounds, wired and CarPlay only, CoreBluetooth route; intent iOS 17.4; UI cannot be hidden; licence-only capability in 2022 | PTT article; forums 748430, 773981, 770491, 707980 |
| Side button Japan only; Siri AI excluded on EU iPhone, iPad and Watch, included on Mac | Apple article; Apple newsroom |
| Mute handler macOS only; Live Activity 8 h, 12 h, 4 KB, push budget; Announce Notifications rules; TN3135 | Apple docs |
| Free account limits; TestFlight 100, 10,000, 90 days; guideline text for 2.5.2, 2.5.4, 2.5.14, 4.2.3, 5.1.2(i) and the family-and-friends line | Apple pages |
| CarPlay voice category listed; entitlement table omits it; press rules; Claude on CarPlay reported 2026-09-07 | developer.apple.com/carplay, entitlement doc, MacRumors, iGeeksBlog |
| Voice PE hardware, €59 MSRP, three wake words, training warning; ESPHome custom model by URL or path; trainer licence | home-assistant.io, esphome.io, `gh api` |
| All other issue states in 2.5 and section 3 | `gh api` |
| Local: macOS 27.0.1, Xcode 27.2, `xcodegen`, `rustup`, `cargo` missing, no OpenClaw.app, camera `iPhone17,1` | Read-only commands here |

### Not re-checked

Omi's `Info.plist`, Meta's glasses country list (owned by `vision.md`), `deactivationSource`, the privacy-details page, the Siri Extensions press report, the Amazfit report, `en.androidayuda.com`, and every effort estimate and threshold, which remain proposals. Sibling-sourced facts from `openclaw-fit.md`, `voice.md` and `ux.md` were taken as written.
