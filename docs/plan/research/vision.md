# Jorah research track: vision and presence

Date: 2026-11-02. Status: research only. Nothing was installed, enabled or configured, and the gateway was not touched.

## How to read the evidence labels

| Label | Meaning |
|---|---|
| `[verified: URL]` | I read that source, or its search excerpt, this session. If the source is not the vendor, it says "third-party". Third-party prices and benchmarks are one source's claim, so recheck before spending money. |
| `[docs-only: path or URL]` | The vendor documents the feature, but nobody has run it on Adam's setup. Treat it as a promise, not a fact. |
| `[measured: this Mac]` | I timed it on this M1 Max this session with a throwaway script. Still images only, no camera was opened. |
| `[inference]` | My own reasoning or arithmetic. May be wrong. Test it. |
| `[source check: file]` | A reviewer read the packaged OpenClaw 2026.10.9 code. Nothing was run, so the behaviour still needs a live test. |
| `[unverified]` | A reviewer tried to confirm this and could not. Do not spend money or set a gate on it. |

Evidence tiers for later sessions follow Adam's rule: source check, then install, then launch, then signed-in device acceptance. **Everything in this file is at or below the source-check tier, except the Apple Vision timings and the local camera listing.**

**Research limit:** the shared web search budget for this run ran out partway through. Section 15 lists exactly what is therefore unconfirmed. An independent review then opened the primary sources directly, changed this file where they disagreed, and logged that in the Verification section at the end. Web search was also used up for that review, so it relied on direct page fetches. A second independent review had search again, and it changed the file further; see the end of the Verification section.

---

## 1. Recommendation in one page

**Jorah should not watch continuously with an expensive model. It should have cheap local eyes that are always ready, and it should only spend cloud money when you ask it to look or when a local detector finds something that matters.**

Four modes, in order of how often they run:

| Mode | Trigger | What runs | Cost | Ships in |
|---|---|---|---|---|
| **Off** (default at boot) | Nothing | No capture at all | Free | V1 |
| **Look** | "Jorah, look at this" | Grab the freshest frame from memory, send it to Jorah's normal brain | Included in Max, within its usage limits [inference]. By API on Opus 5.5, about $0.008 for the image and answer alone, and about $0.01 to $0.09 for a full Jorah turn (section 4.2) | V1 |
| **Watch** (local timeline) | You switch it on for a period | Local motion and person detection, local or Haiku captions on events only, bounded retention | About $3/month for 500 events a day | V2 |
| **Live** | "Jorah, stay with me" | Gemini Live, 1 frame per second, with a hard time limit | About $0.42/hour on headline prices; the true bill must be measured | V0 browser demo, expect about 2 minutes per session. Longer sessions need our own client, after V1 |

Five findings that shape this:

1. **None of the three main model providers takes true live video.** Gemini Live is capped at 1 frame per second and takes individual images such as JPEG or PNG, not a video stream [verified: https://ai.google.dev/gemini-api/docs/live-api/capabilities]. OpenAI Realtime takes images but does not list video [verified: https://developers.openai.com/api/docs/models/gpt-realtime-2.1]; LiveKit does feed it repeated frames, each as an image message that costs tokens and stays in the context [verified third-party: https://docs.livekit.io/agents/multimodality/vision/video.md]. Claude takes images, not video [verified: https://platform.claude.com/docs/en/build-with-claude/vision]. From these three, "Jarvis sees in real time" is really "about 1 frame per second from the cloud, plus fast local detectors". Others, not exhaustive: Alibaba's Qwen-Omni-Realtime also takes JPEG frames and recommends 1 per second, with Singapore and Beijing regions only [verified: https://www.alibabacloud.com/help/en/model-studio/realtime]. xAI's voice API appears to take no images [verified third-party, search excerpt: https://pydantic.dev/docs/ai/realtime/xai/; provisional]. Overshoot, a startup, does ingest a continuous live feed through LiveKit and lets you query it through chat completions, but its overview page gives no frame rate, latency, price or data-use terms [verified: https://docs.overshoot.ai/]. That would send a continuous home video feed to a small vendor, so it is not a pick.
2. **OpenClaw already has a zero-code live vision demo.** Video Talk in the Control UI sends 1 fps JPEGs from the browser straight to Google Live, and the frames bypass the gateway [docs-only: `web/control-ui/chat.md`, `nodes/talk/realtime-sessions.md`]. **Expect it to stop after about 2 minutes:** Google limits audio plus video to 2 minutes without context compression, and the packaged browser path does not request compression or resumption [source check: section 4.3]. So this is a short V0 demo, not the Live mode. Name `gemini-3.8-live` explicitly: OpenClaw's default model has an earliest shutdown date of 17 November 2026 [verified: https://aistudio.google.com/docs/deprecations].
3. **OpenClaw's node camera commands may be too slow to feel real-time.** On macOS `camera.snap` waits 2 seconds by default for exposure, and `camera.clip` defaults to 3 seconds. iOS and Android camera commands only work in the foreground [docs-only: `nodes/camera.md`]. The 2 seconds is only a default: `delayMs` goes down to 0 and the agent `nodes` tool accepts it [docs-only: `nodes/camera.md`; source check: `dist/openclaw-tools-CSSYZDKR.mjs`], and the remaining warm-up is unmeasured. So measure `delayMs: 0` first (test T0). A capture sidecar is still needed for anything that looks backwards, such as the ring buffer.
4. **Local detection is effectively free on this Mac.** Apple Vision took about 10 ms per frame for person and face detection, 8 ms for a scene fingerprint and 4 ms for JPEG encoding, with other work running on the machine [measured: this Mac]. No install needed.
5. **The law draws the line at the walls of your home.** The Slovak regulator's guidance says a camera on your own enclosed property can fall under the household exemption, but if it catches even part of a street, a shared corridor or a neighbour's property, GDPR applies [verified: https://dataprotection.gov.sk/files/metod-urad/1/metodicke_usmernenie_c-1_2023.pdf]. Indoor cameras, off by default, with visible indicators, keep this simple.

**Buy nothing for V0 to V2.** The FaceTime camera and iPhone are already enough. The iPhone already appears to macOS as a camera via Continuity [measured: this Mac, `system_profiler SPCameraDataType` lists "iPhone17,1"]. The first worthwhile purchase is a pan-tilt USB webcam, because OpenClaw can already move one if it exposes UVC absolute pan and tilt (section 3). OBSBOT's own store lists the Tiny 2 Lite at €199 with VAT [verified: https://www.obsbot.com/store/products/tiny-2-lite]. Cheaper retailer prices may exist, but the earlier €166 to €189 listings could not be reopened [unverified].

---

## 2. Decisions

| # | Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|---|
| D1 | Default vision behaviour | On demand "Look", plus opt-in Watch | Cheapest, most private, easiest to explain to bystanders | Continuous Gemini Live | A provider offering real video at a flat price | Pennies a day |
| D2 | Model for "Look" | Jorah's own brain (Opus 5.5 by Claude CLI) | Same memory and tools, already paid for by Max; the CLI backend passes image paths | Sonnet 5.5 by API if Max retention terms are unacceptable. Use a small dedicated vision call rather than a full agent turn, because a full turn carries the whole prompt | Latency above 3 s in testing | $0 on Max within its limits, or about $0.01 to $0.09 each as a full Opus turn by API (section 4.2) |
| D3 | Model for automatic captions | Claude Haiku 5.5 by API, using the Console credits | $0.10 per million input tokens; commercial terms | Moondream 3.1 locally, once benchmarked | Local Moondream under 2 s and within 10% of Haiku, which removes cloud upload of home scenes | About $3/month at 500 events a day |
| D4 | Live session model | `gemini-3.8-live`, 1 fps, set explicitly because OpenClaw otherwise uses a legacy preview whose earliest shutdown is 17 Nov 2026. V0 is a short browser demo. Long sessions need our own client with compression, resumption and a hard cap | The only one of the three providers with a documented frame stream and per-minute prices. OpenAI Realtime can be fed repeated frames, but at per-token image cost and with growing context. OpenClaw's Gemini browser support exists, but has no compression, resumption or media resolution setting | OpenAI Realtime 2.1 single frame on `describe_view` | Measured bill far above headline, latency spikes, or OpenClaw adding compression to the browser path | Headline about $0.42/hour |
| D5 | Local gate on Mac | Apple Vision framework | Already on the Mac, no licence question, measured about 10 ms | RF-DETR Nano. Not YOLOv9, whose original repo is GPL-3.0 | Needing more object classes | Free |
| D6 | Local gate on PC | RF-DETR Nano (Apache 2.0 code and COCO weights) in our sidecar; Frigate if RTSP cameras are added | Licence is safe for a possible business. Frigate lists about 4 to 12 ms on consumer RTX cards (section 5.1) | YOLO26n, which needs an Ultralytics enterprise licence for a commercial or closed product | Business plan dropped, which makes AGPL acceptable. Also retest if the PC has no NVIDIA GPU: the only non-NVIDIA figure found is 33 ms on Iris XE, and no CPU figure was found | Free |
| D7 | Capture architecture | First measure node `camera.snap` with `delayMs: 0` (T0). Then our own small sidecar `jorah-eyes`, exposing tools through an OpenClaw plugin, for the ring buffer and Watch | Nodes keep no frame history, have foreground limits on phones and a 25 MiB cap. Their 2 s delay is only a default | Node commands only | T0 under about 1 s moves the sidecar from V1 to V2. OpenClaw shipping continuous frame streaming on nodes removes it for good | Build time |
| D8 | Ring buffer | RAM frames for 120 s, disk video segments for 6 hours at first, then keyframes for 7 days, then text for 30 days | Makes "what did I just do" work while limiting what can leak | Disk-free, RAM only | Adam finds 120 s is enough for everything | About 2 to 11 GB of disk |
| D9 | Person memory | No biometrics until V3, then only people enrolled with consent | GDPR special category data; bystanders never consented | Frigate Face Library on the PC | Adam decides face recognition is not needed at all | Free |
| D10 | Glasses | Do not buy, and take glasses off the committed roadmap. Slovakia is not on Meta's supported-country list, and the toolkit's full capabilities depend on that list. Use the iPhone as the portable camera until this changes | Meta is the only open path with a proven OpenClaw integration (VisionClaw), but access is uncertain here, and VisionClaw's phone mode needs no glasses | Android XR once hardware reaches Slovakia and Adam has an Android phone. The glasses pair with iPhones for consumers, but the third-party camera API found is Android only | Slovakia appearing on Meta's list, or a unit bought in Austria being confirmed to work from Slovakia in Developer Mode | No official EU Gen 2 price found; one German deal listing showed €335 plus shipping [verified third-party, search excerpt: https://www.mydealz.de/deals/ray-ban-meta-gen-2-verschiedene-grossen-ab-335eur-zzgl-versand-2812317]. Gen 3 is $449 but not on the toolkit's device list |
| D11 | First hardware purchase | OBSBOT Tiny 2 Lite | Physical 2-axis gimbal and a vendor SDK. OpenClaw can drive it on Mac only if it exposes UVC absolute pan and tilt. The vendor page does not state this; one developer reports it for the larger Tiny 2, not the Lite (section 3) | Plain webcam | Testing shows the Mac node PTZ does not work with it, so buy where returns are easy | €199 with VAT at OBSBOT's store [verified: https://www.obsbot.com/store/products/tiny-2-lite] |
| D12 | Robot and wrist camera | USB camera when tethered, ESP32-S3 only for low-rate remote views, ESP32-P4 later | S3 has no hardware H.264; reflexes must stay local | Raspberry Pi with a camera | Robotics track picks a different compute board | About €15 for the S3 board |

---

## 3. Sources: what actually works for an open agent

| Source | How to capture | Limits | Verdict |
|---|---|---|---|
| **Mac FaceTime camera** | AVFoundation in the sidecar, or OpenClaw `camera.snap` / `camera.clip` | Node: **Allow Camera** defaults off; `camera.snap` waits 2000 ms by default, adjustable 0 to 10000; `camera.snap` and `camera.clip` need `gateway.nodes.commands.allow` [docs-only: `nodes/camera.md`, `nodes/command-policy.md`]. macOS shows its camera indicator whenever capture is on [inference] | **V1** |
| **iPhone by Continuity Camera** | Appears as a Mac camera [measured: this Mac]; OpenClaw says Continuity formats are left unchanged [docs-only: `nodes/camera.md`]. Our sidecar needs `NSCameraUseContinuityCameraDeviceType` in its Info.plist; without it the camera reports as built-in wide-angle [verified third-party mirror of Apple's API text: https://docs.rs/objc2-av-foundation/0.3.2/objc2_av_foundation/static.AVCaptureDeviceTypeContinuityCamera.html], and one app without the key got zero frames [verified third-party, search excerpt: https://forum.obsidian.md/t/macos-continuity-camera-is-detected-by-getusermedia-but-delivers-zero-video-frames-in-obsidian/116834] | Apple's rules: iPhone XR or later on iOS 16+, same Apple Account with two-factor, Bluetooth and Wi-Fi on, iPhone near the Mac, **locked and stable, with rear cameras facing you**. The iPhone cannot share its cellular connection and the Mac cannot share its internet. Wireless use excludes AirPlay and Sidecar; USB needs trust [verified: https://support.apple.com/en-us/102546] | **V1**: free, good-quality camera when docked. You cannot use the phone or carry it while it is the camera, so hold the object up to it [inference] |
| **iPhone by own app** | OpenClaw iOS node `camera.snap`/`clip`; foreground only [docs-only: `nodes/camera.md`] | Apple allows camera use **while multitasking** only on an iPad with Stage Manager and an extended display, or an app linked to iOS 18+ using `voip` background mode, or with a special entitlement [verified: https://developer.apple.com/documentation/avfoundation/avcapturesession/ismultitaskingcameraaccesssupported.md]. That page does not say this covers a locked phone or an app left in the background, so test it [inference]. Forums report failures [verified third-party: https://developer.apple.com/forums/thread/710193] | **V3**: only foreground at first |
| **Screen, Mac** | `screen.snapshot`, `screen.record` (25 MiB cap, about 18.75 MiB of MP4), or ScreenCaptureKit in the sidecar [docs-only: `nodes/device-commands.md`, `nodes/computer-use.md`]. `screen.snapshot` comes with an approved pairing, and `screen.record` needs the allow list. `desktop.stream` is an RFB remote desktop for the Control UI, not a frame feed for the agent [docs-only: `nodes/command-policy.md`, `gateway/config-browser-ui-desktop.md`] | macOS Sequoia added a monthly re-consent prompt with no permanent grant [verified: https://9to5mac.com/2024/08/14/macos-sequoia-screen-recording-prompt-monthly/, a report from the 2024 beta]. **Not confirmed for macOS 26 or 27**; searches on the second review found only 2024 coverage [unverified]. Apple describes its persistent-capture entitlement as for VNC apps, on request, so do not plan on it [verified: https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.persistent-content-capture.md] | **V1** on demand; **V3** timeline |
| **Screen, Windows** | OpenClaw Windows node: `screen.snapshot`; `screen.record` requires opt-in [docs-only: `platforms/windows.md`] | Windows Graphics Capture details not confirmed this session | PC port |
| **PC webcam** | Windows: `camera.list`, with `snap`/`clip` by opt-in [docs-only: `platforms/windows.md`]. Linux: FFmpeg with V4L2, off by default [docs-only: `nodes/camera.md`] | Same latency limits as above | PC port, through the sidecar |
| **USB pan-tilt camera** | OpenClaw `camera_ptz`: status, set, move, home. `camera.ptz.control` must be added to the allow list and re-approved; status is a default Mac command. Explicit `deviceId` required. **macOS app only**, only for cameras with UVC absolute controls, and on-camera AI tracking can override commands. Every PTZ call, even status, briefly opens the stream and turns on the camera indicator [docs-only: `nodes/camera.md`, `nodes/command-policy.md`] | Windows nodes do not advertise it [docs-only: `nodes/camera.md`], so the PC needs our own control code, through UVC or OBSBOT's SDK or OSC interface [inference] | **V3**: gives Jorah a head that turns. OBSBOT Tiny 2 Lite: 4K30 and 1080p60, 1/2-inch sensor, 2-axis gimbal, Windows 10+ and macOS 11+, SDK and OSC for developers; that page does not state UVC controls [verified: https://www.obsbot.com/obsbot-tiny-2-lite-4k-webcam]. €199 with VAT at OBSBOT's store; the store page names no UVC control either [verified: https://www.obsbot.com/store/products/tiny-2-lite]. One developer reports that the larger **Tiny 2** uses standard `CT_PANTILT_ABSOLUTE`, with position readback working on macOS and Windows, while AI tracking, presets and sleep or wake need the vendor protocol [verified third-party: https://dev.to/michael_jordan_87eaf96f24/i-reverse-engineered-a-webcam-so-claude-could-point-it-at-things-2h3]. **The Lite is not confirmed** [unverified], so buy where returns are easy and run `camera.ptz.status` first |
| **RTSP cameras** | Frigate on the PC, Docker on Linux. Apple Silicon detection needs a host-side detector because it cannot run in a container [verified: https://docs.frigate.video/frigate/hardware/] | Indoors only (section 11). **Camera models and EU prices not confirmed this session** | **V4**, only if room coverage is wanted. Expect roughly €30 to €60 per camera [inference, unconfirmed] |
| **ESP32-S3 camera** | XIAO ESP32S3 Sense, MJPEG over HTTP [verified: https://components.espressif.com/components/giuuuug/xiao-esp32-camera-stream/versions/1.0.1/readme]. About £13.50 [verified third-party: https://thepihut.com/collections/seeed/products/seeed-studio-xiao-esp32s3-sense] | OV2640 is discontinued, newer boards use OV3660, which is harder to bring up [verified third-party: https://medium.com/@manjotkhangura/getting-esp32-s3-sense-ov3660-camera-working-a-weekend-deep-dive-941d9c1a05d8]. Espressif states about 20 fps for its esp-rtsp example at 720p MJPEG on the S3, and 25 fps at 1600x1200 JPEG with an OV5640 [verified: https://docs.espressif.com/projects/esp-techpedia/en/latest/esp-friends/solution-introduction/camera/dvp-mipi-csi-camera-solution.html]. **No figure was found for the XIAO over Wi-Fi at VGA**, so measure it. Original ESP32 boards report about 10 to 15 fps at VGA with JPEG over Wi-Fi [verified third-party: https://basic-starter-kit-for-esp32-s3-wroom.readthedocs.io/en/latest/1.C_Tutorial/17_camera_web_server.html]. S3 software H.264 only manages 320x240 at about 11 fps [verified third-party: https://docs.espressif.com/projects/esp-techpedia/en/latest/esp-friends/solution-introduction/multimedia/component-description/esp-h264.html] | **V5**: plan on 5 to 10 fps for "what does the arm see" until measured; not for fine control |
| **ESP32-P4** | Hardware H.264, officially up to 1080p30 with MIPI-CSI [verified: https://www.espressif.com/en/node/7617]. One forum user got 25 to 27 fps at 1080p [verified third-party: https://esp32.com/viewtopic.php?p=154181]. No built-in Wi-Fi is described; Espressif says wireless comes from a companion ESP32-C or ESP32-S chip [verified: same page] | More work than the S3 | V6 if the S3 is too limiting |
| **Robot wrist camera** | USB camera when the arm is tethered to a PC, S3 when wireless [inference] | Latency budget in section 8 | See robotics track |

### Smart glasses, as of November 2026

| Product | Camera | Third-party access | Status | Verdict |
|---|---|---|---|---|
| **Ray-Ban Meta Gen 1/2, Display, Oakley Meta HSTN and Vanguard** | Yes | Meta Wearables Device Access Toolkit: camera, mic, audio, motion, IMU. Version 1.0 stable began rolling out 30 September 2026. **Store publishing not open**, but Developer Mode lets your own unpublished app work [verified: https://developers.meta.com/wearables/faq, https://wearables.developer.meta.com/docs/develop/dat/getting-started-toolkit/] | Full capability, including the developer center, is limited to "AI glasses supported countries" [verified: FAQ above]. **Slovakia is not on Meta's list; neighbouring Austria is** [verified: https://www.meta.com/help/ai-glasses/4961066940605960/] | **Blocked for now.** Best open path only if this changes |
| **Ray-Ban Meta Gen 3** | Yes, 12 MP [verified third-party: vr.org article in this row] | **Not on the SDK device list** in Meta's FAQ on 2 Nov 2026 [verified: https://developers.meta.com/wearables/faq], and likewise on 23 Sept [verified third-party: https://vr.org/articles/meta-glasses-three-tiers-wearables-toolkit-publishing-connect-2026] | $449 [verified: https://www.meta.com/ai-glasses/ray-ban-meta/] | Check the list again before buying |
| **Ray-Ban Meta Audio** | **None** | Not on the toolkit list | $349 [verified third-party: vr.org article above; Meta's product page shows no Audio price] | Avoid for vision |
| **Android XR glasses (Samsung, Gentle Monster, Warby Parker)** | Yes on some models, query at runtime | Clean CameraX API through a projected context. Google's own example table says 1024x768 at 1 fps for AI streaming, or 1080p at 1 fps for OCR. Frame rate drops when warm [verified: https://developer.android.com/develop/xr/jetpack-xr-sdk/access-hardware-projected-context] | Reports conflict. A 1 Oct report gave a November window [verified third-party: https://letsdatascience.com/news/samsung-confirms-november-launch-window-for-ai-glasses-db47e242]. A 2 Nov report says mid-December in the US and South Korea, citing ChoSun Biz, and that Samsung has not confirmed the date or a price [verified third-party: https://tbreak.com/samsung-smart-glasses-december-launch/]. No European market was found. Google says the glasses pair with Android and iOS phones [verified: https://blog.google/products-and-platforms/platforms/android/android-xr-io-2026/], but the camera API documented for developers is Android only, and Adam's phone is an iPhone. No iOS developer path was found [unverified] | **Wait** |
| **Even Realities G2** | **None, no speaker** | Web plugins through the Even Hub SDK; 4-mic array, 16 kHz; green display; can reach the phone camera with permission [verified: https://hub.evenrealities.com/docs/get-started/overview] | $599 without prescription lenses [verified third-party, search excerpt: https://idevice.com/smart-glasses/even-realities/roadmap?view=price] | Maybe later as a **display** for Jorah, not as eyes |
| **Brilliant Labs Halo** | Yes | Open SDK and Flutter tooling, phone apps can use mic, speakers and image sensor [verified, search excerpt only because the direct fetch returned HTTP 429: https://www.brilliant.xyz/products/halo] | $299 at launch, later listed $349. A user-edited wiki says $399 with shipments from early August 2026, and that it missed earlier dates [verified third-party, search excerpt: https://aiwiki.ai/wiki/brilliant_labs]. Conflicting shipping dates, with one source saying the official page still said Q1 2026 in August 2026 [verified third-party: https://yespress.io/brilliant-labs]. **The official page returned HTTP 429 again on review, so this is [unverified]** | **Do not order until Adam can confirm units are shipping** |
| **Snap Specs** | Yes | Developer-focused | $2,195; US, UK, France [verified: https://techcrunch.com/2026/06/16/snap-finally-debuts-its-long-awaited-ar-glasses-specs-and-oof-they-arent-cheap/] | No |

**Meta details that matter for the build:**

- Streams are 720x1280, 504x896 or 360x640 at 2, 7, 15, 24 or 30 fps. The link is constrained, so resolution drops first and then frame rate, never below 15 fps, and compression can make images look worse than the stated size. **Asking for less gives better image quality** [verified: https://wearables.developer.meta.com/docs/develop/dat/streaming/].
- **Conflict in Meta's own docs:** the streaming page says Bluetooth Classic, while the iOS integration page describes Wi-Fi streaming through a network hosted by the glasses [verified: https://wearables.developer.meta.com/docs/develop/dat/build-integration-ios/]. Read the current SDK at implementation time.
- Closing the hinges stops the session and it does not restart by itself [verified: https://wearables.developer.meta.com/docs/develop/dat/lifecycle-events/].
- Glasses mic audio comes over the phone Bluetooth profile at **8 kHz mono** [verified: https://wearables.developer.meta.com/docs/build-overview/]. That is poor for wake word and speech recognition compared with the 16 kHz on Android XR, so test before trusting it [inference].
- Developer Mode is switched on in the Meta AI app and lets an unpublished app register without publishing review. That page does not mention country limits, while the FAQ does, so whether it works from Slovakia is [unverified] [verified: https://wearables.developer.meta.com/docs/develop/dat/getting-started-toolkit/].
- Meta AI itself stays first-party. You get sensors, not the assistant [verified third-party: vr.org article above].
- iOS background behaviour is not documented beyond `bluetooth-central` [verified: integration page above]. Assume the app must stay active until tested.

**Proof that this works:** VisionClaw connects Meta glasses or a phone camera to Gemini Live, with frames throttled to about 1 fps at JPEG quality 50, 16 kHz audio up, 24 kHz down, and a single `execute` tool routed to an OpenClaw gateway [verified: https://github.com/Intent-Lab/VisionClaw]. In a 12-person study tasks were 13 to 37% faster, but success fell to about 58% on note-taking because the camera could not read small items such as receipts. The study was small, and its authors included the field testers and Google researchers [verified third-party: https://the-decoder.com/always-on-ray-ban-meta-glasses-powered-by-openclaw-speed-up-everyday-tasks-in-new-study/]. **Its LICENSE file is not an open-source licence:** it binds you to Meta's Wearables Developer Terms and Acceptable Use Policy, and it names no permission to reuse the code in a product [verified: https://raw.githubusercontent.com/Intent-Lab/VisionClaw/main/LICENSE]. Treat it as a reference for a personal build, and read those terms before any business use [inference]. Do not copy its gateway setup: it asks for `bind: "lan"` with the `chatCompletions` endpoint enabled, which conflicts with Jorah's loopback-only gateway. Its phone mode works without glasses, so the idea can be tried with no purchase [verified: same repo].

---

## 4. Cloud models

### 4.1 Prices

| Model | Image or video input | Audio in / out | How vision is delivered |
|---|---|---|---|
| `gemini-3.8-live` | $1.00 per 1M tokens, or **$0.002/min** | $0.005/min / $0.018/min | JPEG frames, max 1 fps |
| `gemini-robotics-er-2-streaming-preview` | $1.00 per 1M through 31 Dec 2026, then $2.00; output $5, then $10 | Same flat rate for audio; text output only | Live API, function calling |
| `gemini-2.5-flash-lite` | $0.10 per 1M | n/a | Request-response |
| `gemini-3.8-flash` | $0.75 per 1M through 31 Dec 2026, then $1.50 | n/a | Request-response, accepts video |
| `gpt-realtime-2.1` | $5.00 per 1M | $32 / $64 per 1M | Single images |
| Claude Haiku 5.5 | $0.10 per 1M (prompts up to 100k tokens); output $0.50 | n/a | Images in messages |
| Claude Sonnet 5.5 | $2 per 1M; output $10 | n/a | Images in messages |
| Claude Opus 5.5 | $4 per 1M; output $20 | n/a | Images in messages |
| Moondream 3.1 Cloud | $0.30 per 1M; output $1.00 | n/a | Request-response |

Sources: [verified: https://ai.google.dev/gemini-api/docs/pricing], [verified: https://developers.openai.com/api/docs/models/gpt-realtime-2.1], [verified: https://platform.claude.com/docs/en/about-claude/pricing], [verified: https://moondream.ai/pricing].

### 4.2 Image token arithmetic for Claude

The rule is `ceil(width/28) x ceil(height/28)` tokens [verified: https://platform.claude.com/docs/en/build-with-claude/vision]. All of these follow from that rule [inference]:

| Frame | Tokens | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|---|
| 640x360 | 299 | $0.00003 | $0.0006 | $0.0012 |
| 1024x768 | 1,036 | $0.0001 | $0.0021 | $0.0041 |
| 1280x720 | 1,196 | $0.00012 | $0.0024 | $0.0048 |
| 1920x1080 | 2,691 | $0.00027 | $0.0054 | $0.0108 |

Add text and output. A Haiku event caption with 1280x720, a 200-token prompt and 60-token answer costs about $0.00017. 500 of those a day is about **$2.60/month**. Your $100/month Console credit covers this many times over. A 20-a-day Opus "Look" with a 150-token answer costs about $0.16/day by API, **for the image and answer alone**. A real Jorah turn also carries the system prompt, memory and history. As an illustration, 20,000 such tokens at Opus 5.5 rates add $0.08 uncached, or $0.004 as cache hits at $0.20 per million, so a full look is about $0.01 to $0.09, or about $7 to $54 a month. Jorah's real prompt size is unmeasured, so log it in T3 [inference].

Do not resend images in long conversations. Each new request carries the whole history, and the docs warn that this inflates size and latency [verified: Claude vision doc]. Keep old frames out of the transcript and store a short text description instead.

### 4.3 Gemini Live: real limits and open cost question

- **2-minute session limit with audio and video unless context compression is on**; about 10 minutes per connection; resumption handles last 2 hours; a GoAway message warns before disconnect [verified: https://aistudio.google.com/docs/live-api/session-management]. So the client must always enable compression and resumption.
- **Headline cost:** $0.002 + $0.005 per minute with mic on, plus $0.018 per minute Gemini is speaking. One hour with 10 minutes of speech is $0.12 + $0.30 + $0.18 = **about $0.60**. With the mic and camera both on but nearly no speech, about $0.42 [inference].
- **The true bill is uncertain.** Google's token page gives about 100 tokens/s at low resolution and 300 at high resolution for 1 fps video [verified: https://ai.google.dev/gemini-api/docs/tokens]. At $1 per million that is $0.36 to $1.08 per hour for video alone, which does not match $0.12. The same page also gives 263 tokens/s for static processing without explaining the gap, and none of these figures is stated for Live specifically, so applying them here is my reading [inference]. A developer on an older model saw about 1M tokens/hour in AI Studio and about 9M/hour in Cloud billing, and asked staff about it without getting a clear answer [verified third-party: https://discuss.ai.google.dev/t/gemini-live-2-5-token-counting-what-is-the-expected-cost-of-long-running-video-session/99245]. Google's media resolution guide adds a fourth figure: 70 tokens per video frame at low and medium, 280 at high, for Gemini 3 and 4, also not stated for Live [verified: https://aistudio.google.com/docs/media-resolution]. At 1 fps, 70 tokens is $0.25/hour, while $0.002/min works out to about 33 tokens/s [inference]. Gemini 3.8 Live also counts all video by default, so idle camera frames are not free [verified: https://aistudio.google.com/docs/models/gemini-3.8-live]. Treat $0.42/hour as a floor; at 70 to 100 tokens/s it would be about $0.55 to $0.66/hour with the mic on, before any speech [inference]. **Measure 10 minutes of Live, across several sessions if V0 cuts off, and read the invoice before allowing longer ones.** Set a billing alert and a hard session cap first.
- **Continuous 24/7 costs at least $216/month** for audio input, plus $86 for video on headline rates [inference]. That rules it out.
- **Latency is not stable.** A developer reported 9 to 15 s to first audio on `gemini-3.1-flash-live-preview` from 5 Sept 2026, up from about 1 s, with `gemini-2.5-flash-native-audio-latest` at 1.9 to 2.4 s in the same test; no staff response in the thread [verified third-party: https://discuss.ai.google.dev/t/gemini-3-1-flash-live-preview-9-15-s-time-to-first-audio-since-2026-09-05-09-00-utc-was-1-s-some-turns-never-answer-reproduced-from-two-projects-two-networks/180918]. LiveKit users reported about 3 s end to end [verified third-party: https://community.livekit.io/t/how-to-fix-latency-3-secs-of-gemini-3-1-flash-live/766]. None of these tests used video, and none was on `gemini-3.8-live`, so its latency is unmeasured here.
- **OpenClaw's Google Live default is `gemini-3.1-flash-live-preview`**, for Voice Call [docs-only: `providers/google.md`] and for browser Talk sessions [source check: `dist/extensions/google/.setup/realtime-voice-provider-DPZahQjh.mjs`]. Google calls it a legacy preview and recommends migrating to `gemini-3.8-live`, which it lists as stable, although the Live API as a whole is still described as preview [verified: https://aistudio.google.com/docs/models/gemini-3.1-flash-live-preview, https://aistudio.google.com/docs/models/gemini-3.8-live, Live capabilities page]. **Its earliest shutdown date is 17 November 2026, 15 days from now, and the same date applies to `gemini-2.5-flash-native-audio-preview-12-2025`** [verified: https://aistudio.google.com/docs/deprecations]. Google will announce the exact date. So no Jorah path may rely on OpenClaw's default, including voice. Choose the model explicitly with `talk.realtime.model` [docs-only: `nodes/talk.md`]. OpenClaw sends no thinking config for 3.8 Live [docs-only: `providers/google.md`; source check: same file]. Leave `enableAffectiveDialog` unset, because the code passes it to 3.8 and Google says to remove it [source check; verified: 3.8 Live page]. Proactive audio is always on, so it may choose when to speak; note that in V0.
- **The OpenClaw browser path probably stops at about 2 minutes.** Compression and resumption are sent only on the Gateway-relay connection. `buildGoogleLiveConnectConfig`, which builds the browser token's constraints, sets neither, nor does the browser's setup message. The Control UI bundle only has a `supportsSessionResumption` capability flag in a schema, and no client logic for compression, resumption or `goAway`. Neither path has a media resolution setting. The token allows one use, a 60-second window to start and a 30-minute session, so a dropped connection cannot simply reconnect with it [source check: same file and `dist/control-ui/`]. Video Talk is documented only for the browser path, so the relay does not help [docs-only: `nodes/talk/realtime-sessions.md`]. This was read, not run, so V0 must time it. Any longer session needs our own client or an upstream fix.
- **EU rule:** in the EEA, UK and Switzerland, apps for users can only be built on **Paid Services**, and paid data terms apply. Paid data is not used to improve products but is logged for a limited, unspecified period. The terms also require you to be **18 or older**, and bar use in a client directed at or likely to be accessed by under-18s [verified: https://ai.google.dev/gemini-api/terms]. The pricing page lists a free tier for `gemini-3.8-live`, but ignore it in any cost plan. Whether one person's own tool counts as making a client available to EEA users is unclear, so staying paid is the cautious reading [inference]. Confirm the account holder meets the age rule.

### 4.4 Which model does what

| Job | Pick |
|---|---|
| "Look at this", single frame | Claude brain. Opus 5.5 is default today; a later setting could use Sonnet 5.5 for speed |
| Reading small text, labels or a whiteboard | Capture from iPhone at full resolution, crop first, then Opus. Do not rely on 1 fps Live, which failed on receipts in VisionClaw's study |
| Motion event captions | Haiku 5.5 by API, or Moondream locally after benchmarking |
| Hands-free back-and-forth while cooking or fixing something | Gemini Live, capped |
| Analysing the last few minutes as a clip | `gemini-3.8-flash` with video, or keyframe montage to Claude. Claude has no video input, so montage is the default [inference] |
| Robot supervision | `gemini-robotics-er-2-streaming-preview` to evaluate later: text output, function calling, Live API [verified: https://ai.google.dev/gemini-api/docs/models/gemini-robotics-er-2-streaming-preview]. Preview only. Its guide limits camera input to 1 JPEG frame per second, frames need a paired prompt to get a response, physical actions must be blocking calls, and it gives no latency figures or motor-safety guidance [verified: https://ai.google.dev/gemini-api/docs/robotics-streaming] |

**Privacy route for frames:** Claude CLI on Max falls under consumer terms: if "model improvement" is on, de-identified chats may be kept for up to 5 years in training pipelines; off means not used for future training [verified: https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data]. Commercial API data is deleted within 30 days, with exceptions [verified: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data]. Anthropic's commercial terms say it may not train models on Customer Content from the Services [verified: https://www.anthropic.com/legal/commercial-terms, effective 17 June 2025]. With model improvement off, the consumer page gives no retention number beyond the general standard of as long as reasonably necessary, and deleted chats leave back-end storage within 30 days [verified: first page above]. So:

1. Adam checks the model-improvement setting on the `~/.claude-jorah` account **before any home frame goes through Max**.
2. Automatic captions always use the API, never Max.

---

## 5. Local models

**Rule: detectors run per frame, language models run per event.** No local language model here can caption every frame.

### 5.1 Fast detectors

| Model | Hardware | Speed | Licence | Evidence |
|---|---|---|---|---|
| Apple Vision person rectangle | M1 Max | **10.1 ms median, 11.4 ms p95**, 1280x1280 still | OS framework | [measured: this Mac] |
| Apple Vision face rectangle | M1 Max | **10.0 ms median** | OS framework | [measured: this Mac] |
| Apple Vision feature print (scene change) | M1 Max | **8.3 ms median** | OS framework | [measured: this Mac] |
| Apple Vision OCR, fast / accurate | M1 Max | **16.8 ms / 130 ms** on an image with no text; expect slower on real text [inference] | OS framework | [measured: this Mac] |
| JPEG encode, CIContext | M1 Max | **4.1 ms** | OS | [measured: this Mac] |
| YOLOv9 small, 320 px, Frigate detector | M1 | about 9 ms | Original repo is GPL-3.0 [verified: https://github.com/WongKinYiu/yolov9]. Licence of the weights Frigate uses is unchecked | [verified: https://docs.frigate.video/frigate/hardware/] |
| YOLOv9 tiny / small / small 640 | RTX 3050 | about 8 / 10 / 28 ms | | [verified: same] |
| YOLOv9 tiny / small / small 640 | RTX 5060 Ti | about 5 / 7 / 22 ms | | [verified: same] |
| YOLOv9 small, 320 | GTX 1070 | about 16 ms | | [verified: same] |
| YOLOv9 small, 320 | Intel N100 | 30 ms | | [verified: same] |
| YOLO26n | M4 Pro, MLX community port | about 170 fps | AGPL | [verified third-party: https://pypi.org/project/yolo-mlx/] |
| YOLO26n | CPU ONNX / T4 TensorRT | 38.9 / 1.7 ms, 40.9 mAP, vendor-reported | AGPL or paid enterprise | [verified, search excerpt: https://docs.ultralytics.com/compare/yolo26-vs-rtdetr and sibling compare pages; the excerpt did not say which page] |
| RF-DETR Nano | T4 | 2.3 ms on TensorRT FP16 at 384x384 in the package table, "100 FPS" in Roboflow's blog; the two do not match. Vendor-reported, 48.4 AP, 30.5M parameters, version 1.11.2. **No CPU figure found** | Apache 2.0 for Nano. XL and 2XL are under a different licence, PML 1.0 | [verified: https://pypi.org/project/rfdetr/, https://blog.roboflow.com/rf-detr-nano-small-medium/amp] |
| RF-DETR Nano, 320 px, Frigate detector | RTX 3050 / RTX 5060 Ti / Iris XE | about 12 / 4 / 33 ms. Column read from a flattened table, so check it. No Apple Silicon or N100 figure | as above | [verified: https://docs.frigate.video/frigate/hardware/] |

Bench notes: 40 runs with 5 discarded, on a blank-looking macOS wallpaper at 1280x1280, machine load average about 8 to 10 because other agents were running. Treat these as rough figures: this is **not a camera test and not a real scene**. Person detection accuracy was not tested. An independent re-run on a synthetic 1280x720 noise image, at load average about 8, agreed: median 8.8 ms person, 9.4 ms face, 8.3 ms feature print. The first call in a process was slower, 115 ms for person and 38 ms for feature print, so warm the requests when arming. One JPEG encode of that noise image took 15 ms and 618 KB, a worst case [measured: this Mac].

**Licence warning:** Ultralytics says an enterprise licence is needed for closed-source commercial use, for embedded use in robots or cameras, and even for internal business tools; AGPL obligations can apply to custom training and internal use. No public price [verified: https://www.ultralytics.com/license]. Since Jorah may become a business, **avoid building on it** and start with RF-DETR.

### 5.2 Local vision language models

| Model | Machine | Result | Licence | Evidence |
|---|---|---|---|---|
| **Moondream 3.1 (9B total, about 2B active)** | Runs on Photon, native Apple Silicon and NVIDIA Ampere or newer, no API key for local use since Photon 1.3.0, except finetunes and telemetry. The vendor names no Apple Silicon generation, so M1 support is not stated [unverified]. Has query, detect, point and caption | **No M1 Max numbers exist.** B200: about 30 ms single request for Moondream 3 (vendor) | Moondream Model License 1.0. Commercial use and use as a product component are allowed, with no revenue threshold. Offering general-purpose hosted inference needs a separate licence, and your product cannot be named after Moondream [verified: https://moondream.ai/license] | [verified: https://huggingface.co/moondream/moondream3.1-9B-A2B, https://moondream.ai/pricing, https://moondream.ai/blog/photon-1-2-0-update, https://moondream.ai/blog/photon-1-3-0-update] |
| Moondream 2, 4-bit, MLX | M4 Pro | 95 ms encode, 78 tok/s, **0.7 s** per 50-token answer | as above | [verified third-party: https://contracollective.com/blog/local-vision-llm-apple-silicon-mlx-qwen-vl-moondream-2026] |
| Qwen2.5-VL 7B, 4-bit, MLX | M4 Pro / M5 Pro | **2.4 s / 1.7 s** per 50 tokens | not checked | [same] |
| Qwen2.5-VL 3B, 4-bit, MLX | M5 Pro | **0.9 s** | not checked | [same] |
| Gemma 4 26B A4B, 4-bit, oMLX | **M1 Max 64 GB** | 54 to 57 tok/s. 0.8 to 0.9 s to first token only when asking again about an image already encoded. **About 85 s to first token for each unseen image**, as the source describes it, which rules this stack out for captioning new frames unless retested | not checked here | [verified third-party: https://lilting.ch/en/articles/omlx-039-dev2-m1-max-tested] |
| Gemma 4 31B, 4-bit, oMLX | **M1 Max 64 GB** | about 15 tok/s, 4.4 s to first token | | [same] |
| Qwen2.5-VL 7B, Ollama | **M1 Max 64 GB** | **25 to 31 s per image** for a 200-token answer | | [same] |
| FastVLM with Qwen2 0.5B / 7B, 1024 px | **M1 Max** | **166 ms / 641 ms** estimated time to first token, encoder plus prefill rather than measured end to end, on a 32 GB M1 Max; image encoder 116 ms on the Neural Engine | **Research only, no commercial use or product development** | [verified: https://arxiv.org/html/2412.13303, https://raw.githubusercontent.com/apple/ml-fastvlm/main/LICENSE_MODEL] |
| LLaVA 1.5 7B, vLLM, batched | RTX 4090 / 3090 | 217 / 147 images per minute under load; not single-frame latency | | [verified third-party: https://james19.trooper.ai/benchmarks-compare-RTX-3090-with-RTX-4090] |
| SAM 3.1 video segmentation | H100 | 32 fps at medium object count, doubled from 16 | | [verified: https://ai.meta.com/blog/segment-anything-model-3] |
| SAM 3 image with text prompts | M1 to M4, MLX port | No speed published; no video tracking listed | | [verified third-party: https://huggingface.co/mlx-community/sam3-image] |

Other points:

- **Not found:** any Moondream 3, Qwen3.5 small, Gemma 4 E2B/E4B vision, SmolVLM measured figures on an M1 Max. Calculator sites like willitrunai are estimates and gave implausible numbers, so I do not use them.
- **Florence-2 and MediaPipe:** not confirmed this session because search ran out. Moondream covers Florence's caption, detection and point jobs, and Apple Vision covers MediaPipe's on the Mac, so neither is on the plan. Check them only if those picks fail.
- **Encoder start-up is the trap on this Mac.** One test saw about 85 seconds for each unseen image, plus about 20 seconds to load and warm the model. Keeping the model loaded would not fix a per-image cost, and retesting the same image hides it. **Every benchmark must use images the model has not seen** [inference].

**Expected on this Mac:** Moondream 3.1 captions probably take 1 to 2 s, roughly half the speed of an M4 Pro [inference]. **Run benchmark B1 in section 13 before believing this.**

**Pick:** Moondream 3.1 by Photon, loaded only during Watch mode. **Runner-up:** small Gemma 4 or Qwen3.5 by mlx-vlm [verified: https://pypi.org/project/mlx-vlm/0.6.15/]. The 85 s result was on oMLX with the 26B model, so test small Gemma on unseen images before trusting it [inference]. Do not build on FastVLM even though it is the fastest published, because of the licence.

### 5.3 PC hardware tiers

PC specs are unknown. These tiers are my reasoning from the numbers above [inference], so check them against the PC:

| Tier | GPU | What works |
|---|---|---|
| **Minimum** | None, or integrated Intel with OpenVINO (Iris XE about 6 to 16 ms, UHD 770 about 16 to 40 ms [verified: Frigate hardware page]). 16 GB RAM, 500 GB free SSD | Ring buffer, cloud captions. The detector speeds here are for YOLOv9, which is GPL-3.0; the business-safe pick, RF-DETR Nano, is listed at 33 ms on Iris XE, with no UHD 770 or CPU figure, so benchmark it. Local language model is slow |
| **Recommended** | NVIDIA Ampere or newer, which is Photon's floor and means RTX 30 series onward [inference], with at least 12 GB VRAM. 32 GB RAM, 1 TB SSD, USB 3 | Detectors at about 4 to 12 ms, Moondream and small Qwen locally, NVENC for several streams, Frigate |
| **Strong** | 24 GB VRAM or more | Larger vision models, SAM 3.1 for arm grasping (speed on consumer GPUs unmeasured) |

**To check on the PC:** `nvidia-smi` for model, VRAM and driver (Frigate needs driver 545+ and CUDA 12 [verified: same page]); `dxdiag` or `lspci`; free SSD; Windows or Linux; Ethernet; whether it sleeps; whether it has a webcam and USB ports near the desk.

---

## 6. Architecture

```
 FaceTime / iPhone / screen / USB / RTSP / ESP32 / glasses app
                      |
              capture adapters
                      |
        RAM ring: 120 s JPEG at 2 to 5 fps ---------> "Look" (grab latest)
                      |                                       |
      gate: scene change (8 ms) -> person/object (10 ms)      |
                      |                                       |
    event? ---------> event log (SQLite)                      |
                      |                                       |
     Watch mode: caption (Haiku or Moondream)                 |
                      |                                       v
     disk: H.264 segments, keyframes, text ---> plugin tools ---> OpenClaw agent
                                                                       |
                                       Live mode: browser or app -> Gemini Live
```

**`jorah-eyes` sidecar**

- Runs outside the gateway. If it crashes, Jorah still talks, and if the gateway restarts, the indicator and the capture state stay correct.
- **Mac:** small Swift binary using AVFoundation, ScreenCaptureKit, Vision and VideoToolbox. No FFmpeg needed; this Mac has none, and it would be an install. **Ship it as a signed app bundle**, with camera and Continuity keys in its Info.plist, so the permission belongs to it and not to whatever terminal launched it [inference]. One developer reports that on macOS 26.1 plain executables no longer appear in the Screen Recording list [verified third-party, search excerpt: https://origin-devforums.apple.com/forums/profile/SadCat]. That adds packaging work to V1.
- **PC:** Python with PyAV or OpenCV, onnxruntime with CUDA, NVENC. Same HTTP contract.
- API on `127.0.0.1` with a bearer token. Never on the LAN or Tailscale without the auth decision from the security track.

**OpenClaw plugin `jorah-vision`** registers tools with `api.registerTool` [docs-only: `plugins/building-plugins.md`]:

| Tool | What it does | Confirmation |
|---|---|---|
| `vision_look(source?, question, detail?)` | Saves the freshest frame to workspace, returns the path and timestamp | Allowed when Look mode is armed |
| `vision_recall(from, to, query?)` | Returns event captions and keyframe paths | Allowed |
| `vision_status()` | Sources, mode, retention, what is recording | Allowed |
| `vision_pause(minutes)` | Immediate stop | Always allowed, never blocked |
| `vision_arm(mode, source, until)` | Starts Watch | **Spoken or chat yes from Adam. The agent may not turn on Watch by itself** |
| `vision_remember(event_id, label)` | Promotes to long-term memory | Preview first |
| `vision_forget(from, to)` | Deletes a range | Confirm for ranges over 1 hour |
| `camera_ptz` | Existing OpenClaw action | Opt-in plus pairing approval [docs-only: `nodes/camera.md`] |

**How the image reaches the Claude CLI brain:** the bundled `claude-cli` backend uses `imageArg: "@"` and `imagePathScope: "workspace"`, so images go in as paths in the workspace [docs-only: `gateway/cli-backends.md`]. Whether a **plugin tool result** can inject an image on this runtime is **not confirmed**. Test T2 in section 13 settles it. Reading by path is not a simple fallback: the backend's `--allowedTools` is `mcp__openclaw__*` and managed turns expose no Claude-native tools by default [docs-only: `gateway/cli-backends.md`], so Claude's own Read tool is not available. Try OpenClaw's `view_image` through the MCP bridge next [docs-only: `tools/index.md`]. If that also fails, `vision_look` can call the Claude API itself and return a text answer, which spends Console credits [inference].

**Event record**

```json
{"id":"ev_...","t":"2026-11-02T17:30:02+01:00","source":"mac-facetime",
 "kind":"person_entered","objects":["person","mug"],"scene_delta":0.31,
 "keyframe":"kf/2026-11-02/173002.jpg","clip":"seg/20261102-1730.mp4#t=2",
 "caption":"...","caption_model":"haiku-5.5","cost_usd":0.00017,
 "untrusted_text":"OCR text, if any","retain_until":"2026-11-09","faces_blurred":true}
```

Store in SQLite with FTS5 for text search. Vector search can reuse Jorah's EmbeddingGemma on captions, so there is no new embedding model for V2 [inference].

---

## 7. Modes in detail

### Look (on demand)

1. Wake word ends. The voice track gives a timestamp.
2. Sidecar picks the sharpest frame in the 500 ms after that moment, so it shows what you are pointing at. No camera warm-up, because the camera is already running while armed.
3. Blur unenrolled faces if bystander mode is on (about 10 ms).
4. Save at 1280 wide, or 1920 if text is detected.
5. Jorah says a short "Looking" within 300 ms if the answer is not ready, and answers.

**The catch:** keeping the camera running to avoid the 2 s warm-up means the camera light stays on while armed. That is an honest signal, and a good one. Arming is explicit, and it times out after 30 minutes by default [inference: the timeout needs Adam's input].

### Watch (event-driven)

The cost ladder:

| Step | Rate | Cost |
|---|---|---|
| Scene-change check | 2 to 5 fps | CPU only |
| Person and object detection, on change | Same | CPU, Neural Engine or GPU |
| Event rule fires, at most once per 10 s per source | Rare | Local |
| Caption | Events only | About $0.00017, or local |
| Expensive model | Only when a rule asks or Adam asks | About $0.008 for image and answer; more with Jorah's full prompt (section 4.2) |

Starter rules: person enters or leaves, object appears or disappears on the desk, screen app changes, more than 60 s without change ends an "activity". No alerts or schedules until Adam approves each one.

### Live

V0 uses Control UI Video Talk, expected to end at about 2 minutes (section 4.3). Anything longer needs our own client, a small local page or the companion app, holding the WebSocket directly with an ephemeral token and turning on compression and resumption. That client must enforce a duration limit (default 15 minutes), a spoken warning before the end, and the spend counter from Section 4.3. Gemini calls Jorah through a tool for anything real, the pattern used by both VisionClaw and OpenClaw's `openclaw_agent_consult` [docs-only: `nodes/talk.md`].

### "What did I just do?"

1. Take events in the requested window, default 10 minutes.
2. Choose up to 8 keyframes by scene distance, not evenly spaced.
3. Add app names and any OCR, labelled as untrusted.
4. Send a montage with timestamps to Sonnet or Opus.
5. If more detail is needed, send the matching clip from disk to `gemini-3.8-flash`. At about 100 tok/s low resolution, 60 s is 6,000 tokens or about $0.0045 [inference].
6. Say "I can only see from when Watch was on". **Never guess what happened outside the recorded window.** That is the no-fabrication rule applied to memory.

---

## 8. Latency budget

Targets are my proposal [inference]. They need measurement.

**Voice "Look": from end of speech to first spoken word**

| Stage | Target | Basis |
|---|---|---|
| End-of-speech detection | 300 to 600 ms | Voice track |
| Choose and encode frame | Under 30 ms | [measured: this Mac] 4 to 10 ms parts |
| Upload 100 to 200 KB | 50 to 200 ms | [inference] |
| Model first token | 500 to 1,500 ms | **Unmeasured for Haiku, Sonnet and Opus with images** |
| TTS first audio | 200 to 400 ms | Voice track |
| **Total p50 / p95** | **under 2.0 s / under 3.5 s** | |
| Spoken filler if still waiting | At 700 ms | Hides nothing, just says "Looking" |

The Claude CLI path may add overhead. OpenClaw keeps one Claude Code process warm across compatible turns, but a changed system prompt restarts it [docs-only: `gateway/cli-backends.md`], which might break this budget. Measure with test T3, including one restart.

**Other paths**

| Path | Target | Note |
|---|---|---|
| Gate on a frame | Under 25 ms | Measured close to that |
| Local caption | Under 2 s | B1 |
| Live model reacting to a scene | 1 to 3 s when healthy | Includes up to 1 s of frame interval. Outliers of 9 to 15 s reported without video |
| Pan-tilt camera move | Under 500 ms | Separate pan and zoom writes, not atomic [docs-only: `nodes/camera.md`] |
| Robot visual reflex, stop or track | **Under 100 ms, local only** | **Never put a cloud model in a safety or reflex loop** [inference] |
| Robot arm visual servoing | Under 50 ms per frame on tethered USB | Do not plan it on S3 Wi-Fi: even 20 fps is a 50 ms frame interval before encoding, Wi-Fi and detection [inference] |
| Cloud robot supervision | Under 1 Hz | Goals, not motor commands [inference] |

---

## 9. Bandwidth

All [inference]; JPEG sizes vary a lot by scene. My one measurement (125,941 bytes at 1280x1280, quality 0.7) was on a smooth wallpaper and does not represent a real room.

| Stream | Rate | Bandwidth |
|---|---|---|
| Gemini Live, 1 fps at 1024x768 (about 100 KB) | Upload | About 0.8 Mbps |
| Same at 640x360 (about 35 KB) | Upload | About 0.3 Mbps |
| OpenClaw Video Talk, capped at 1280x720 and JPEG quality 0.8, lowered only if oversized [source check: `dist/control-ui/assets/transport.runtime-Cfond1RX.js`] | Upload | Likely above 0.8 Mbps, not measured |
| Event captions, 500 a day at 100 KB | Upload | 50 MB/day |
| ESP32 MJPEG, VGA at 12 fps | LAN | About 3 to 6 Mbps per camera. Espressif assumes 30 to 50 KB per frame even at 480x320 |
| WebRTC glasses view, 24 fps | LAN or upload | Up to 2.5 Mbps [verified: VisionClaw repo] |
| H.264 720p at 15 fps | LAN | 0.5 to 1.5 Mbps |
| PC to Mac camera forward over Tailscale | Tailnet | Send JPEG events only, not a stream |

At 1 fps, video is light for home internet. Battery and heat on the phone and glasses matter more. Android's docs recommend the lowest usable resolution and warn about thermal frame-rate drops [verified: Android XR page].

---

## 10. Storage and retention

Free disk today: 181 GB [measured: this Mac].

| Tier | Contents | Default keep | Size per source | Location |
|---|---|---|---|---|
| **RAM ring** | JPEG at 2 to 5 fps | 120 s | 10 to 75 MB, from 240 to 600 frames at about 40 to 125 KB [inference] | Memory only, wiped on pause |
| **Video** | H.264 or H.265 segments, 60 s each, motion only | 6 h, optional 24 h | 0.45 GB/h at 1 Mbps; 24 h continuous is 10.8 GB, or about 2 GB at 20% activity | Encrypted volume |
| **Keyframes** | JPEG events | 7 days | 40 MB/day at 500 events | Encrypted volume |
| **Text** | Captions, labels, app names | 30 days | Small | SQLite |
| **Promoted** | Only what Adam said to remember | Until deleted | Small | Memory system, with a link to the image |
| **Screen** | Change-based only | 24 h, then text only | Prior art reports 5 to 30+ GB/month at about 1 fps; figures conflict [verified third-party: https://www.mintlify.com/screenpipe/screenpipe/advanced/performance, https://docs.screenpi.pe/architecture] | Encrypted volume, excluded apps never captured |

Rules:

- **Exclude from Time Machine and any cloud sync.**
- **The purge job is a schedule, so Adam approves it explicitly**, with a preview of what it deletes. Nothing is scheduled silently.
- **Dreaming and Active Memory must not auto-ingest raw visual events** [inference: check config]. Only promoted items reach `MEMORY.md`.
- **Largest known gap:** Jorah's own `exec` tool runs as Adam's macOS user. It can read anything Adam's user can, including the capture archive, unless that is fixed. Encryption with a key held by the sidecar helps little against same-user processes, and OpenClaw says the same about its CUA socket [docs-only: `nodes/computer-use.md`]. **Do not enable disk retention beyond the RAM ring until the security track closes this**, for example by running capture under a separate macOS user and exposing frames only by tool call.

---

## 11. Privacy, bystanders and law

Not legal advice. The Slovak points below should be checked by a lawyer if Jorah becomes a business.

### What the law says

- **Household exemption is narrow.** The Slovak Data Protection Office lists: A) your own enclosed property, including interior, where the exemption may apply; B) third-party areas such as a neighbour's plot; C) public space; D) shared parts of a residential building such as a corridor. If a camera catches **even part** of B, C or D, GDPR applies, and you must change the camera's angle, mask or blur that area. Monitoring a neighbour's area is not compliant; public and shared areas are allowed only in exceptional, minimal cases against a real threat. Handing footage to police or publishing it online is new processing to which GDPR applies, even if the camera only saw your own property. Falling under GDPR also means a proportionality test, retention limits, informing people and record keeping [verified: https://dataprotection.gov.sk/files/metod-urad/1/metodicke_usmernenie_c-1_2023.pdf].
- **Ryneš (C-212/13):** a home camera filming public space is not purely personal activity [verified: https://www.thomashelbing.com/en/wissen/dsgvo-hub/rechtsprechung/1.4.20-eugh-rynes]. It was a **Czech** case with a fixed camera; a search summary I saw called the authority Slovak, which was wrong.
- **Slovak Civil Code § 12:** images and audio-visual recordings of a person may be made or used only with their consent, with exceptions, and consent may be implied [verified third-party: https://www.zakonypreludi.sk/zz/1964-40/znenie-20050801, https://ficek.sk/vybrane-pravne-aspekty-vyhotovovania-fotografii-inych-osob-69]. The current text, in force from 31 July 2026, keeps the consent rule, with exceptions for official use under a law and for appropriate scientific, artistic and news use that does not conflict with the person's legitimate interests [verified third-party: https://www.zakonypreludi.sk/zz/1964-40]. Slov-Lex itself was not opened.
- **Wearables in public are unsettled.** Hamburg's commissioner announced plans to ban Meta glasses in public spaces; Sweden treats them like phones unless widely shared; France generally applies GDPR [verified third-party: https://www.noerr.com/en/insights/private-video-recordings-made-using-wearables-in-public-spaces].
- **EU AI Act:** Article 2(10) excludes deployer duties for individuals in purely personal, non-professional use [verified: https://artificialintelligenceact.eu/article/2/]. Emotion inference at workplaces and in education is prohibited, with medical and safety carve-outs [verified: https://artificialintelligenceact.eu/article/5/, point 1(f)]. **Consequence: never build emotion inference into Jorah**, especially since it touches EduPage and school.
- **If it becomes a business,** the household exemption does not apply to customers' deployments in the same way, and biometrics become much harder [inference]. Keep biometric features off by default and modular.
- **Slovak Criminal Code § 377:** it is an offence to intercept a confidential, non-public spoken or personal expression with a recording device without authorization, then pass the recording to a third party or otherwise use it, causing another person serious harm to their rights. The base penalty is up to 2 years [verified third-party: https://www.zakonypreludi.sk/zz/2005-300, version of 18 Aug 2026]. Recording alone may not complete the offence, but never pass on what guests said, and treat any clip with audio with care. A lawyer should confirm this reading [inference].

### Product rules that follow

1. **Off at boot.** Reboot never resumes capture without Adam re-arming it.
2. **Physical truth beats software.** Use the Mac's own camera indicator. Add a physical shutter on any webcam. On ESP32 cameras, wire the LED to the camera power rail so firmware cannot hide it [inference]. Meta glasses have their own LED, whose toolkit behaviour I could not confirm.
3. **Announce state changes aloud:** "I'm watching the desk until six." Short and honest.
4. **Kill phrases work always, without cloud:** "Jorah, stop looking" and "Jorah, close your eyes". Local handling, RAM ring wiped.
5. **Guest mode:** when an unenrolled person is detected in Watch, stop disk retention, blur unenrolled faces in anything sent to the cloud, and tell Adam. **Blurring is cheap at about 10 ms** [measured: this Mac for the detection step].
6. **No face recognition of unenrolled people, ever.** No embeddings stored for strangers, and no cloud identification.
7. **Do not use at school.** Classmates and staff have not consented and it is not a household setting. Add a location rule that disables vision away from home by default [inference, Adam to confirm].
8. **Excluded rooms and screens:** bathroom and bedroom never get cameras. Screen capture excludes password managers, banking, private browsing, Messages and Mail by default.
9. **Sending to the cloud is logged**, with source, frame, model, cost and retention. A simple "what did you send today?" answers from the log.
10. **No sound in vision capture.** `camera.clip` includes audio by default on iOS, Android and Linux, so always pass `includeAudio: false` or `--no-audio` unless Adam asked for sound [docs-only: `nodes/camera.md`].

### Vision is an attack surface

- Text in view can carry instructions: a sign, a web page, a QR code, a label. OpenClaw already warns the model about on-screen instructions [docs-only: `nodes/computer-use.md`].
- OCR and captions go into a field marked `untrusted_text`, and **nothing seen can trigger sends, purchases, deletions or tool changes without a confirmation from Adam.**
- QR codes are displayed and described, never followed automatically.
- Screen captures may contain secrets, so never send them on Watch without asking.

---

## 12. Person and object memory

| Feature | Tier | How | Note |
|---|---|---|---|
| "Is someone there?" | V2 | Apple Vision person rectangle | Not identity |
| "Is Adam at the Mac?" | V2 | OpenClaw presence signal [docs-only: `nodes/presence.md`], which is explicitly a hint, not proof | No biometrics |
| "Where did I leave my keys?" | V3 | Say "remember these are my keys"; store crop, caption and location text. Later, search captions and offer the keyframe and time | Say how old the sighting is. Never claim the keys are still there |
| Named objects | V3 | Moondream `detect` and `point` by name | Depends on B1 |
| Image-based search | Later | Add an image embedding model if caption search is not enough | Not needed yet |
| **Enrolled faces** | V4, only if Adam wants it | Sidecar with **AuraFace (Apache 2.0, trained for commercial use per its card, LFW 0.9965 self-reported) plus YuNet (MIT per a third-party repo)** [verified third-party: https://huggingface.co/fal/AuraFace-v1, https://huggingface.co/blog/isidentical/auraface]. Check both licence files at source | Written consent, preview, local only, one-command delete |
| Enrolled faces on PC with cameras | V4 alternative | Frigate Face Library: local, FaceNet small on CPU, ArcFace large with GPU or NPU; names assigned only after consistent matches [verified: https://docs.frigate.video/configuration/face_recognition/] | Fits if Frigate is running anyway |
| **Avoid** | | InsightFace `buffalo_l`: pretrained models are non-commercial research only [verified third-party: https://github.com/zengxs/insightface] | |

**Apple Vision gives no identity embeddings**, so it cannot do enrolled recognition by itself [inference from the API list].

**UX for correcting memory:** "That's not my mug" must remove the label. Every remembered item needs a source frame, time and a way to delete it.

---

## 13. Roadmap and tests

Each step lists its acceptance evidence. Native and device steps need signed-in acceptance by Adam, per Adam's evidence tiers.

### V0: Prove live vision, no code (half a day, under $2)

Needs Adam's explicit yes for: paid Gemini API key, OpenClaw config, gateway restart.

1. Create a key on a paid project with a spending alert.
2. Set `talk.realtime.provider` to Google and `talk.realtime.model` to `gemini-3.8-live`; without the model setting OpenClaw uses the legacy preview. Confirm the exact paths from `nodes/talk.md` and `talk.catalog` on 2026.10.9 at implementation time. `talk.realtime.provider` is currently unset on the `jorah` profile [measured: this Mac].
3. Open the Control UI on localhost, start Talk, click the camera button. The preview requires a secure context, and localhost qualifies [docs-only: `web/control-ui.md`].
4. Note: the gateway runs on 43181, not the 18789 used in docs.

**Acceptance:** Adam holds up three objects and it names them; stop releases the camera and the indicator goes off; **the time until a session ends on its own is recorded, expected about 2 minutes**; cost of sessions adding up to 10 minutes read from Google billing a day later.

### V1: "Look" with ring buffer (2 to 4 days, about $0)

Start with T0. It needs the Mac companion app paired as a node, **Allow Camera** on and `camera.snap` allowed, each with Adam's yes. No node is paired today.

1. Swift `eyes-mac` sidecar: FaceTime, Continuity iPhone, screen on demand. RAM ring only. **No disk retention.**
2. Plugin with `vision_look`, `vision_status`, `vision_pause`, `vision_arm`.
3. Menu-bar indicator and the kill phrase with the voice track.
4. Confirm the Max model-improvement setting with Adam first.

**Tests:**
- **T0:** 20 `camera.snap` calls with `delayMs: 0`. Record time to returned file and whether frames are well exposed. Under about 1 s means a node-only Look can ship first, and the sidecar waits for V2.
- **T1:** capture to frame in RAM under 50 ms, sidecar uses under 5% of one core at 2 fps, measured on a real camera.
- **T2:** can a plugin tool return an image to `claude-cli`, or only a path? Record which. If only a path, test `view_image` through the MCP bridge.
- **T3:** 20 "Look" turns, timestamps at each stage, report p50 and p95 against section 8. Log the input tokens of each turn too, so the API cost in section 4.2 can be replaced with a real figure.
- **T1b:** the signed sidecar app lists and streams the Continuity iPhone, and a camera prompt names the app itself.
- **T4:** text legibility at 1280 wide versus 1920 on a real label, receipt and screen.

**Acceptance on device:** Adam says "Jorah, what am I holding?" and gets a correct answer in under 3.5 s, 9 times out of 10. "Stop looking" turns the camera light off in under 1 s.

### V2: Event timeline (about 1 week, about $3/month)

Blocked on the `exec` gap decision. Adds gate, event log, captions, retention tiers, `vision_recall`, cost counters, guest mode.

**B1, local benchmark on this Mac (run before choosing Haiku vs local):**

| Model | Runtime | Record |
|---|---|---|
| Moondream 3.1 | Photon | Cold start, warm time, memory, tok/s, with real room frames |
| Gemma 4 E2B or E4B | mlx-vlm | Same |
| Qwen3.5 2B or 4B | mlx-vlm | Same |

Use 50 frames with known contents. Score correct or not, and compare with Haiku 5.5. Decide by accuracy first, then latency; a **local model that is under 2 s and within 10% of Haiku wins, for privacy.**

**Installs need approval:** these runtimes and weights are not on this Mac.

**Acceptance:** after 30 minutes of real desk use, "what did I just do?" gets the sequence right and says plainly what it did not see; retention previews and deletes correctly; a battery test shows the drain with Watch on. Rule: pause Watch on battery unless told otherwise.

### V3: Presence and object memory (about 2 weeks, about €200)

OBSBOT, `camera_ptz` opt-in with pairing approval, look-toward-speaker if the audio track provides direction. Object memory. Screen timeline with exclusions. iPhone capture in the companion app.

### V4: PC port and rooms (about 2 to 3 weeks, cost depends on PC)

Check PC specs. Python sidecar, RF-DETR, NVENC, same API. Decide where the sidecar runs for each camera: **each camera's frames stay on the machine it is connected to, and only events cross Tailscale** [inference]. Frigate only if RTSP cameras are wanted. Enrolled faces only if Adam says yes.

### V5: Robot eyes (with robotics track, about €15 to €60 per camera)

XIAO ESP32S3 Sense for overview. USB camera for tethered wrist. Local detection on PC. Calibrate with printed markers. Cloud only for goal-level reasoning. Evaluate Robotics-ER 2 in Preview.

**Acceptance:** arm reacts to a stop gesture or object with a local loop, cloud unplugged.

### V6: Glasses (not committed; about 2 weeks plus hardware, price unconfirmed)

**Gate: Slovakia on Meta's supported-country list, or Adam accepts the risk of a unit bought in Austria that may not work here.** Try VisionClaw's phone mode first, with no purchase. Check the SDK device list: Gen 3 at $449 is not on it today. Read VisionClaw and the Meta terms its LICENSE points to. Own iOS app in Developer Mode. Test the 8 kHz mic. Use phone mic for wake word if needed. Test `voip` background mode.

**Acceptance:** one hour of real use, with battery, heat and reconnect after hinge close recorded.

### Monthly cost estimate [inference]

| Setup | Assumption | Monthly |
|---|---|---|
| V1 | 20 looks a day on Max | $0 extra within Max limits, or about $7 to $54 by API, depending on prompt size and caching (section 4.2) |
| V2 | 500 Haiku captions a day | About $3 |
| Live | 30 minutes a day, 5 minutes of speech, on our own client | About $9 on headline rates; **could be higher** |
| Total, typical, with Look on Max | | **About $5 to $20**, inside the $100 Console credit for Claude but **Gemini is billed separately** |
| Continuous Live 24/7 | Do not do this | At least $300 |

---

## 14. UX notes

Keep it compact, per Adam's preference.

- **Single status word**, always visible in the menu bar and companion app: `Off`, `Armed`, `Watching desk until 18:00`, `Live 12:04`. Same words spoken and on screen.
- **Spoken replies short.** State what it saw, and the confidence only when low. "It looks like a 10 mm socket, but the label is blurry. Can you bring it closer?"
- **Show the frame.** In any app or chat, a "Look" answer has a small thumbnail of what was actually sent, so a mistake can be seen. This also shows honestly what left the machine.
- **Say when it cannot see.** "It's too dark" or "The camera is off" rather than guessing.
- **Accessibility:** every state must also exist as spoken text and non-colour icons. The indicator must not rely only on colour.
- **Testing steps for Adam** must be exact, with navigation and expected result, per Adam's preference. V0 and V1 above are written in this form; each session should expand them.

---

## 15. Not confirmed

Web search ran out for the first pass. A second review searched again and narrowed this list, and these items remain open:

| Item | Why it matters |
|---|---|
| Slovakia was not on Meta's list on 2 Nov 2026. Recheck before V6. Whether Developer Mode works from Slovakia is still open | Blocks V6 |
| Official EU price of Ray-Ban Meta Gen 2. Meta's page prices only Gen 3, and the Slovak Ray-Ban page returned 403. Search excerpts gave about €419 at launch and €449 for Gen 3, from reports not opened one by one | V6 cost |
| Halo actual shipping status (official page returned 429 twice more on review) | Alternative glasses |
| Samsung Android XR launch date, price and any EU market. November and mid-December reports conflict. iPhone pairing is stated by Google, but no iOS developer path was found | D10 |
| Screen Recording monthly prompt on macOS 26 and 27. Searches found only 2024 coverage | V3 UX |
| Windows Graphics Capture permissions and border | PC screen capture |
| RTSP camera models and EU prices | V4 |
| First-token latency for Haiku 5.5, Sonnet 5.5, Opus 5.5 with images | Measure in T3 |
| Moondream 3.1 on M1 Max and consumer NVIDIA. The vendor does not name M1 as supported | Measure in B1 |
| Gemini Live cost with long-running video | Measure in V0 |
| Slovak Civil Code § 12 and Criminal Code § 377 were read on a legal database, not Slov-Lex, and need a lawyer's reading | Legal |
| How long OpenClaw Video Talk on Google Live really lasts | V0 |
| The exact shutdown date of `gemini-3.1-flash-live-preview`; 17 Nov 2026 is only the earliest | Voice and V0 |
| Latency of `gemini-3.8-live`, with or without video | V0 |
| OBSBOT Tiny 2 Lite UVC absolute pan and tilt. Reported only for the larger Tiny 2. The €199 store price is confirmed | D11 |
| Overshoot's frame rate, latency, price and data terms; xAI's voice API from its own docs. Vendors beyond those named in section 1 were not surveyed | D4 |
| Whether Video Talk works with the Claude CLI brain as the consult model | V0 |
| Whether Control UI camera works at the gateway's port and origin settings | V0 |
| Whether an agent on OpenClaw 2026.10.9 can receive images in a tool result on `claude-cli`. Reading the MCP loopback code on the second review did not settle it | V1 T2 |
| Qwen and Gemma licences, and the weights Frigate uses. FastVLM research-only, Moondream 1.0 and the YOLOv9 repo's GPL-3.0 are confirmed | Business option |

## 16. Questions only Adam can answer

1. Is face recognition wanted at all, and if so, who gets enrolled?
2. May home frames go through Max, once the model-improvement setting is confirmed off? Or API only?
3. Who else lives in or visits the home, and do they consent to an armed camera in shared rooms?
4. Which rooms may have cameras, and is a screen timeline wanted?
5. Is vision allowed away from home, for example on the phone or glasses? Default proposal is no at school.
6. Default arming timeout: 30 minutes, or something else?
7. Budget ceiling for Gemini Live per month?
8. Is business use serious enough to exclude AGPL and research-only models now? This plan assumes yes.
9. Does the Gemini API account holder meet Google's 18+ requirement? The terms also bar clients likely to be accessed by under-18s.

---

## Verification

Independent review, 2 Nov 2026. I opened the sources myself and read the bundled docs and packaged code of OpenClaw 2026.10.9. Nothing was installed, no setting or service was touched, and the gateway was not touched. One throwaway timing script ran on a synthetic image, with no camera. Web search was used up before this review, so everything comes from direct page fetches, which limits what could be found.

### What I checked

| # | Claim | Result | Source |
|---|---|---|---|
| 1 | Gemini Live max 1 fps, image frames | Holds. Wording corrected: JPEG or PNG | Google Live capabilities |
| 2 | `gemini-3.8-live`, Robotics-ER, Flash and Flash-Lite prices | Holds | Google pricing |
| 3 | 2 min audio plus video, 10 min connection, 2 h resumption | Holds | Google session management |
| 4 | Headline $0.42/hour and the token mismatch | Holds. Added the 263 tokens/s conflict | Google tokens page |
| 5 | Video Talk is a usable V0 for capped sessions | **Refuted in part.** The browser path sends no compression or resumption, so expect about 2 minutes | Packaged provider and Control UI |
| 6 | OpenClaw's legacy default applies to Voice Call | **Understated.** It is also the browser Talk default | Packaged provider |
| 7 | `camera.snap` 2 s makes nodes too slow | **Overstated.** 2 s is a default, `delayMs` reaches 0 and the agent tool accepts it | `nodes/camera.md`, packaged tools |
| 8 | PTZ rules | Mostly holds. Only control needs the allow list; every PTZ call lights the indicator | `nodes/camera.md`, `nodes/command-policy.md` |
| 9 | Plugin fallback of reading a file by path | **Weakened.** No Claude-native tools by default on managed turns | `gateway/cli-backends.md` |
| 10 | Claude Haiku, Sonnet and Opus 5.5 prices | Holds | Anthropic pricing |
| 11 | Claude image token rule and table | Holds. High-resolution tier applies to these models, so 1920x1080 stays 2,691 tokens | Anthropic vision |
| 12 | OpenAI Realtime 2.1 prices, no video | Holds | OpenAI model page |
| 13 | Meta toolkit: streaming, 8 kHz mic, publishing closed, Gen 3 missing | Holds. The Bluetooth versus Wi-Fi conflict is real | Meta docs |
| 14 | Slovakia support unknown | **Resolved against the plan.** Not on Meta's list | Meta help page |
| 15 | Gen 2 about $349 | **Unsupported.** That source gives $349 for the camera-less Audio model and no Gen 2 price | vr.org, Meta product page |
| 16 | VisionClaw details and study | Holds. Added that its LAN gateway setup conflicts with Jorah's | Repo, The Decoder |
| 17 | Gemma 4 on M1 Max | **Misread.** 85 s is per unseen image, not a one-time cold start, and the fast figures are repeat questions | lilting.ch, third-party |
| 18 | FastVLM on M1 Max and licence | Licence holds. 167 ms was 166 ms, and the figures are estimated, on 32 GB | arXiv, Apple licence |
| 19 | Moondream licence and Photon | Holds and improved: commercial product use is allowed. Added the Ampere floor | moondream.ai, Hugging Face |
| 20 | RF-DETR Nano licence and speed | Holds. Added no CPU figure | PyPI |
| 21 | Ultralytics enterprise licence terms | Holds | Ultralytics |
| 22 | YOLOv9 as a runner-up, licence unchecked | **Changed.** Original repo is GPL-3.0, so it is no longer the D5 runner-up | GitHub |
| 23 | Frigate speeds, driver and container limits | Holds | Frigate docs |
| 24 | Apple Vision timings | Holds on re-run. Added first-call cost | Re-measured here |
| 25 | iOS camera while multitasking | Holds, but it says multitasking, not background | Apple docs |
| 26 | Continuity Camera rules not checked | **Filled in.** The phone must be locked and mounted, which limits use | Apple support |
| 27 | Slovak regulator's camera guidance | Holds. I extracted and read the Slovak text | dataprotection.gov.sk PDF |
| 28 | AI Act Article 2(10) and emotion ban | Holds | Articles 2 and 5 |
| 29 | Civil Code § 12 and Criminal Code § 377 | **Filled in** from current consolidated text | zakonypreludi.sk, third-party |
| 30 | Google EEA paid-only rule and 18+ | Holds. Added the under-18 access rule | Google API terms |
| 31 | Claude retention and training terms | Holds. Commercial no-training position now confirmed | Anthropic privacy and commercial terms |
| 32 | ESP32-P4 and S3 H.264 | Holds. P4 radio point is now sourced | Espressif |
| 33 | Robotics live guide unreadable | **Resolved.** Guide read, limits added | Google |
| 34 | RAM ring of 10 to 40 MB | **Arithmetic corrected** to 10 to 75 MB | This file's own figures |
| 35 | Arithmetic for image costs, Live hourly and monthly, video storage, bandwidth | Holds | Recalculated |

### Could not confirm

Marked in place, and listed in section 15:

- Actual length of a Video Talk session. I read the code but did not run it.
- OBSBOT UVC absolute pan and tilt, and its EU price. The two retailer pages now return 410 and 403.
- Brilliant Halo price and shipping. The official page keeps returning HTTP 429.
- Android XR launch status today, and Screen Recording prompts on macOS 27.
- Whether Developer Mode works from Slovakia, and any EU price for Gen 2.
- Whether other providers offer live video.

### Not rechecked

Lower impact, so left as written with their original labels: Even Realities, Snap beyond price and markets, XIAO price and sensor notes, YOLO26 figures, Qwen benchmarks on newer Macs, SAM 3, LLaVA, AuraFace, InsightFace, Frigate faces, screenpipe, the Hamburg and wearables summary, the Ryneš summary, and the developer forum latency reports.

### Does the recommendation still hold?

**The core does:** local detectors per frame, cloud models only on request or on an event, off at boot, and buying nothing for the first stages. Four parts changed:

1. **Live is smaller at V0.** Treat Video Talk as a demo of about 2 minutes. A real Live mode needs our own client, so it should come after V1 rather than be counted as already available.
2. **Glasses are off the committed roadmap.** Slovakia is not on Meta's list, and Gen 3 is not on the device list. Use the iPhone and VisionClaw's phone mode first.
3. **V1 starts with a measurement.** T0 tests `camera.snap` at `delayMs: 0` before the Swift sidecar is built. This could make the first Look much cheaper, in line with Adam's preference for a bounded MVP.
4. **The local model runner-up is weaker,** and every benchmark must use unseen images.

### Second independent review

Second review, 2 Nov 2026, done after the first. I tried to refute the claims a plan would lean on, using live searches, direct page fetches, the bundled docs and the packaged code of OpenClaw 2026.10.9. Nothing was installed or configured, and the gateway was not touched. The only local actions were read-only commands and a throwaway PDF text extractor. I did not re-run the Apple Vision timings. Older `ai.google.dev` links now redirect to `aistudio.google.com/docs`; they still work, so I changed them only where a claim changed.

| # | Claim | Result | Source |
|---|---|---|---|
| 1 | Gemini Live 1 fps, individual frames | Holds | Google Live capabilities |
| 2 | Gemini prices, including Live, Robotics-ER, Flash and promo end dates | Holds | Google pricing |
| 3 | 2 min audio plus video, 10 min connection, 2 h resumption | Holds | Google session management |
| 4 | Video Talk has no compression or resumption | Holds. **Corrected the statement that no Control UI file mentions them:** one capability flag does, with no client logic. Added the single-use token limits | Packaged provider and Control UI |
| 5 | The capabilities page calls 3.1 Live legacy | **Wrong citation.** That page does not use the word; the 3.1 model page does | Google model pages |
| 6 | OpenClaw's default model is only legacy | **Understated.** Earliest shutdown is 17 Nov 2026, in 15 days | Google deprecations |
| 7 | Token mismatch for Live | Holds, and widened: 70 tokens per frame in another guide, and all video counts by default on 3.8 Live | Google media resolution, 3.8 Live page |
| 8 | Gemini is the only provider with a streaming frame path | **Overstated.** LiveKit feeds OpenAI Realtime repeated frames. Reworded D4; the pick stands on documented limits and price | LiveKit docs, OpenAI model page |
| 9 | Other vendors unknown | **Partly filled in:** Alibaba, xAI (provisional), Overshoot | Alibaba, Overshoot, Pydantic docs |
| 10 | Claude prices and image token rule | Holds | Anthropic pricing, vision |
| 11 | About $0.005 to $0.008 per Look by API | **Misleading.** It leaves out the system prompt, memory and history. Now about $0.01 to $0.09 as an illustration | Anthropic pricing; arithmetic |
| 12 | OpenClaw camera, PTZ and command rules | Holds. Added `screen.snapshot` and `desktop.stream` notes | `nodes/camera.md`, `nodes/command-policy.md`, `gateway/config-browser-ui-desktop.md` |
| 13 | `claude-cli` image route and no native tools | Holds. T2 stays open | `gateway/cli-backends.md`, packaged MCP code |
| 14 | Slovakia blocked by Meta's country list | Holds. The FAQ links "AI glasses supported countries" to the same help page, so the chain is direct. That page does not define what "supported" covers | Meta FAQ and help page |
| 15 | Meta streaming, 8 kHz mic, publishing closed | Holds | Meta docs |
| 16 | Gen 3 and Audio prices and camera | Numbers hold. **Citation corrected:** Meta's page prices only Gen 3 | Meta, vr.org |
| 17 | VisionClaw licence unknown | **Resolved.** It points to Meta's developer terms and is not an open-source licence | VisionClaw LICENSE |
| 18 | VisionClaw design and study | Holds | Repo, The Decoder |
| 19 | Android XR November window, iPhone unknown | **Updated.** A mid-December US and Korea report conflicts with it, and Google states iOS pairing | tbreak, Google blog, Android docs |
| 20 | OBSBOT about €166 to €189, UVC unknown | **Price corrected** to €199 with VAT at the vendor store. UVC reported for Tiny 2 only | OBSBOT store, dev.to |
| 21 | Moondream licence, prices, Photon | Holds. Added that M1 is not named | moondream.ai, Hugging Face |
| 22 | RF-DETR has no integrated GPU figure | **Refuted.** Frigate lists 33 ms on Iris XE, and 12 and 4 ms on RTX cards. No CPU figure remains true | Frigate, PyPI |
| 23 | Frigate figures | Holds. Recommended tier changed from under 10 ms to about 4 to 12 ms, since the business-safe detector is RF-DETR | Frigate |
| 24 | Gemma 4 and Ollama on M1 Max | Holds | lilting.ch, third-party |
| 25 | No S3 fps measurement exists | **Refuted in part.** Espressif states about 20 fps at 720p MJPEG, though not for the XIAO over Wi-Fi. Bandwidth estimate raised | Espressif |
| 26 | ESP32-P4 and S3 H.264 | Holds | Espressif |
| 27 | Continuity Camera rules | Holds. **Added the Info.plist key** | Apple support, API text mirror |
| 28 | Sidecar gets TCC permission for the binary itself | **Unsupported as written.** Changed to a signed app bundle; this is my inference, backed by one forum report | Forum excerpt |
| 29 | iOS multitasking camera rule | Holds | Apple docs |
| 30 | Slovak regulator's camera guidance | Holds. I extracted and read the Slovak text | dataprotection.gov.sk PDF |
| 31 | AI Act emotion ban | Holds. Article 2(10) was not reopened | Article 5 |
| 32 | Google EEA paid-only rule and 18+ | Holds | Google terms |
| 33 | Claude consumer retention, including Max and Claude Code | Holds. Commercial terms were not reopened | Anthropic privacy |
| 34 | Ultralytics enterprise terms | Holds | Ultralytics |
| 35 | Robotics-ER streaming limits | Holds | Google |

**Still could not confirm:** the real length of a Video Talk session; UVC on the Tiny 2 Lite; Halo price and shipping (the official page still returns HTTP 429); Screen Recording prompts on macOS 26 and 27; Android XR date, price and EU markets; Developer Mode from Slovakia; official EU Gen 2 price; `gemini-3.8-live` latency; images in `claude-cli` tool results; Moondream on M1.

**Not rechecked on this review:** Even Realities, Snap, XIAO price, YOLO26 figures, Qwen on newer Macs, SAM 3, LLaVA, AuraFace, InsightFace, Frigate faces, screenpipe, Hamburg and wearables, Ryneš, Civil Code § 12, Criminal Code § 377, and the forum latency reports.

**Does the recommendation still hold? Yes, the core does:** local detectors per frame, cloud only on request or on an event, off at boot, Gemini Live for a short V0 only, glasses off the committed roadmap, and no purchase before V3. Five things changed:

1. **Do V0 with `gemini-3.8-live` explicitly, and treat this as urgent for other tracks.** OpenClaw's default Live model could disappear from 17 November, which also affects any voice plan that relies on the default.
2. **The API fallback for Look is dearer than stated.** This strengthens the case for Look on Max, or for a small dedicated vision call if retention terms force API use.
3. **D4's reason is now price and documented limits,** not that Gemini is the only frame path.
4. **The first purchase is about €200, not €170,** and the Lite's UVC support is still only inferred from its larger sibling. Buy with easy returns, or compare the Tiny 2, which is the model that report covers. Its price was not checked.
5. **The Mac sidecar must be a signed app bundle,** which adds some V1 work. T0 at `delayMs: 0` becomes a little more valuable because of this.
