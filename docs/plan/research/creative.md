# Creative tools: video and 3D

Research track for Jorah. Checked 2026-11-02. Nothing was installed or changed. An independent check the same day corrected this file; see "Verification" at the end.

Evidence labels:

- `[verified: URL or path]`: read in the primary source or directly measured today.
- `[secondary: URL]`: read in a third-party page. Treat as probably true, not as proof.
- `[docs-only]`: documented, but nobody here ran it on Adam's hardware.
- `[inference]`: my reasoning or arithmetic. Must be measured before anyone relies on it.
- `[unverified]`: looked for it and could not confirm it.

Research limit: the shared web search budget ran out late in this track, so Suno's terms, Pixabay's music-specific terms, FFmpeg encode benchmarks on Windows and Apple's ProRes data rates were not searched. Those gaps are marked where they matter. The verifier hit the same search limit near the end and used direct page reads after that.

---

## 1. Recommendation

**Video.** Build a transcript-first, code-rendered pipeline. The source of truth is a JSON edit decision list (EDL), rendered by ffmpeg. Transcription runs locally. Export the same EDL as Final Cut Pro 7 XML so Adam can finish in Resolve when they want to; Shotcut needs a separate MLT file. Do not make DaVinci Resolve or computer use the core. Jorah never publishes: the MVP stops at `final.mp4` plus metadata, and API upload (private only) comes after that works.

**Changed after verification: where it runs.** The Claude Code macOS sandbox this design relies on blocked both Metal and VideoToolbox in a local probe (section 4.2). So the bounded MVP runs CPU-only inside the sandbox (`faster-whisper`, `libx264`) on a 5 to 15 minute clip, with no config change. The 1-hour job needs one decision from Adam and the security track first: a narrow media worker with GPU rights, or accepting slow CPU runs. Native Windows has no Claude Code sandbox at all, so the PC path needs WSL2 or its own answer.

**3D.** Start with code CAD (build123d), not Fusion. Add Fusion second, as an optional target, and put every engine's output through the same independent measuring gate. The reasons are licence uncertainty, the need for Fusion's GUI, and the fact that every Fusion MCP route is arbitrary Python running as Adam's user outside the sandbox. Autodesk's sample add-in has no authentication as shipped, so it must be patched before use (section 6.1).

**Computer use.** Last resort only. Long desktop workflows still fully complete well under half the time (section 9). Use it for one-off UI steps and visual checks, with Adam able to take over.

**Growth.** The first run of each skill is supervised and slow. It installs a pinned toolchain after a preview and yes, then saves the procedure, scripts and regression fixtures. The second run must reuse them with no install step and fewer questions. That is the concrete, testable meaning of "it grows" (section 10).

---

## 2. Decisions

| # | Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|---|
| V1 | Edit model | JSON EDL, ffmpeg render | Headless, cross-platform, testable, no GUI, no licence | Resolve Studio timeline as source of truth | Adam wants colour-critical or multicam work done by the agent | $0 |
| V2 | Starting code | Vendor `browser-use/video-use` at a pinned commit after reading it all, then replace transcription and strip auto-installs | Its rules and render order already encode the hard lessons; MIT | Own pipeline of about 1,000 lines of Python | The code read shows Scribe JSON is deeply assumed, or quality is poor | $0 |
| V3 | Transcription | Local. `faster-whisper` on CPU in the sandbox on both Mac and PC; `mlx-whisper` on Mac only through a media worker, because Metal is blocked in the sandbox; WhisperX for alignment on PC | Footage stays local, no per-hour fee, and it runs under the current sandbox | ElevenLabs Scribe v2 at $0.22/hour | Local word timing fails the cut gates on Adam's audio, or Whisper drops the false starts V1 has to cut | $0 |
| V4 | Resolve | Not in the MVP. Export FCP7 XML for manual finishing | Python scripting left the free edition in 21.1 | Buy Studio ($236 on sale until 20 November 2026 [secondary], $295 list) | Adam wants agent-driven grading, Resolve AI tools or `-nogui` renders | $0 now; $236 by 20 November or $295 later |
| V5 | Overlays | ffmpeg and PIL first, Remotion only when animation is needed | Fewer moving parts | HyperFrames, Manim | Adam's style needs motion graphics | $0 for an individual; Company licence above 3 employees |
| V6 | Music | A local "music shelf" of Audio Library tracks that Adam downloads, with a licence ledger | Google says these will not be claimed through Content ID | Epidemic Sound (subscription) | Adam wants a wider catalogue or a licence that covers other platforms | $0, or about $10 to $17/month [secondary] |
| V7 | Publish | Adam publishes in Studio. MVP has no upload | Irreversible, public, and the API default is public | API upload, private only, `youtube.upload` scope only | Adam asks for it after 3 good manual runs | $0 |
| C1 | First CAD engine | build123d with an independent verifier | Headless, sandboxable, diffable, STEP output | CadQuery 2.8 | CadQuery beats it in a 3-task bake-off | $0 |
| C2 | Agent interface | Plain Python scripts in the Claude Code sandbox, with `build123d-mcp` tried as a helper | The OS sandbox is a real boundary; the MCP's own sandbox says it is not | `build123d-mcp` as the main path | Scripts prove too slow to iterate compared with its session tools | $0 |
| C3 | Fusion route | Official local server if the checkbox exists on Adam's licence; otherwise a vendored copy of Autodesk's `FusionMCPSample` with a bearer token added and the CORS header removed | Vendor origin; small surface. Unpatched, the sample has no auth | `ndoo/fusion360-mcp-bridge` (loopback, bearer token, single commit), read in full first | Adam needs the CAM and sketch helpers in `faust-machines/fusion360-mcp-server` (93 tools, no auth) | $0 on personal use; $680/year commercial [secondary] |
| C4 | Text-to-3D | Deferred. Never for mechanical parts | Meshes without real dimensions; licence and hardware traps | TRELLIS.2 on Linux, or hosted Meshy/Tripo | Adam wants decorative or organic shapes | Unpriced |
| C5 | Printing | Slice and upload only. Adam starts every print | Heat and fire risk; Bambu blocks direct start without its own approved path | OctoPrint `print=true` | Never without Adam physically present and an explicit yes | $0 |

---

## 3. Video: facts that shaped the design

### 3.1 YouTube Data API

- `videos.insert` now has its own bucket: 100 calls per day, 1 unit per call. Maximum file 256 GB. [verified: https://developers.google.com/youtube/v3/docs/videos/insert, direct read]
- Other quota: `thumbnails.set` about 50 units, `captions.insert` 400 units, 10,000 units per day for everything except search and upload. Resets at midnight Pacific. [verified: https://developers.google.com/youtube/v3/determine_quota_cost]
- History: about 1,600 units before 4 December 2025, about 100 after, granular buckets from 1 June 2026. [verified: https://developers.google.com/youtube/v3/revision_history] Most blogs still quote the old numbers.
- **Audit:** needed only to go above default quota. No exemption or special path for personal projects is mentioned. [verified: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits] Jorah will not need more than 100 uploads a day.
- **Default privacy is public** if `status.privacyStatus` is not set. Jorah's uploader must hardcode `private`. `notifySubscribers` defaults to true, so set it to false. [verified: same videos.insert page]
- **Private-lock conflict, unresolved.**
  - The current `videos.insert` page says uploads from unverified API projects are *not* restricted to private. [verified by direct read today]
  - The 2020 entry in the revision history says projects created after 28 July 2020 *are* restricted until audited, and I found no later entry that withdraws it. [verified: revision history]
  - A guide that read the reference on 29 September 2026 quoted the opposite wording to what the page says today. [secondary: https://www.upload-post.com/youtube-api/] Either the docs changed in the last five weeks or they disagree with each other.
  - Do not assume either way. Test with one short video: upload private, then try to set it to unlisted in Studio. If it is locked, Adam uploads the final file by hand or applies for the audit. Because Jorah only ever uploads private and Adam publishes, this only affects the last click.
- **OAuth trap:** an External app in "Testing" status gets refresh tokens that expire in 7 days. Tokens also die after six months unused. [verified: https://developers.google.com/identity/protocols/oauth2] Move the client to "In production" for a stable token. Expect an unverified-app warning for a single-user app [inference].
- **Scopes:**
  - `youtube.upload` covers `thumbnails.set`. [verified: https://developers.google.com/youtube/v3/docs/thumbnails/set]
  - `captions.insert` needs `youtube.force-ssl` or `youtubepartner`. [verified: https://developers.google.com/youtube/v3/docs/captions/insert]
  - Pick: grant only `youtube.upload`. `videos.update` does not accept that scope, so the token cannot flip an existing video to public. [verified: https://developers.google.com/youtube/v3/docs/videos/update] `videos.insert` does accept it, and the privacy value is whatever the caller sends, so the same token could upload a new public video [verified: videos.insert page; conclusion is inference]. The private-only rule therefore lives in the uploader, not in Google's scope. Keep the token readable only by the uploader.
  - Adam adds the SRT in Studio.
- **Terms:** API clients must publish a privacy policy, and upload clients have required screen wording in section 9.1. [verified: https://developers.google.com/youtube/terms/api-services-terms-of-service] Whether this matters for a one-person client is unclear; keep a short privacy page ready [inference].
- **Custom thumbnails:** 16:9, JPG or PNG, recommended 3840x2160, 50 MB on desktop, account must be verified. [verified: https://support.google.com/youtube/answer/72431]
- **Encoding target for 4K SDR:** MP4 with fast start, H.264 High, 4:2:0, closed GOP of half the frame rate, 35 to 45 Mbps at 24/25/30 fps, 53 to 68 Mbps at 48/50/60 fps, AAC-LC 48 kHz, stereo 384 kbps. [verified: https://support.google.com/youtube/answer/1722171]
- **AI disclosure:** required for realistic altered or generated content, and for AI music that is the main focus. Not required for captions, colour, background blur, audio repair, script or title help, or cloning your own voice. [verified: https://support.google.com/youtube/answer/14328491] Set `containsSyntheticMedia` from a checklist, default false for plain cuts of Adam's own footage. Adam confirms.
- **EU:** AI Act Article 50(4) requires deployers to disclose deepfakes. It has applied since 2 August 2026. The Digital Omnibus (Regulation (EU) 2026/1744) moved the high-risk dates, and the only Article 50 deferral it gave is until 2 December 2026, for marking by providers of generative systems already on the market. [secondary: https://www.goodwinlaw.com/en/insights/publications/2026/08/alerts-technology-dpc-eu-ai-act-transparency-obligations-now-in-force, a law-firm summary; the Official Journal text was not read] Cutting your own footage is not a deepfake [inference]. Generated realistic scenes could be. Not legal advice.

### 3.2 DaVinci Resolve

- Blackmagic moved Python scripting to Studio in 21.1 and says advanced scripting now requires Studio. [verified: https://www.blackmagicdesign.com/support/content/readme/59dd4eef1f4941c29fb8dc48b33f5c87]
- 21.1 shipped 8 September 2026 [secondary: https://basic-tutorials.de/news/davinci-resolve-21-1/]. Puget dropped free-edition benchmark support and sees no simple workaround other than staying on 21.0 or buying Studio. [verified: https://www.pugetsystems.com/blog/2026/09/10/how-davinci-resolve-free-v21-1-scripting-changes-affect-puget-bench/]
- External scripting was already Studio-only. On free editions up to 21.0.x, a script started from the Workspace menu gets a live `resolve` object, and that is how a community bridge reaches it; the same README says free 21.1 no longer offers this. [verified, as that project's claim: https://github.com/samuelgursky/davinci-resolve-mcp] A free 21.1 Lua path is claimed by one project and undocumented. [secondary: https://glama.ai/mcp/servers/saadk408/davinci-resolve-lua-mcp/tree] Do not build on either.
- **Price:** Studio 21 listed at $236, down from $295. [verified: https://www.blackmagicdesign.com/products/davinciresolve/studio] This is a 20% sale through resellers worldwide, ending Friday 20 November 2026. [secondary: https://www.newsshooter.com/2026/10/20/blackmagic-davinci-resolve-studio-20-off/] EU price [unverified].
- **Free caps:** output to UHD, 60 fps, 8-bit formats. Studio adds hardware H.264/HEVC decode and encode. [verified: same page] Free is fine for 4K30 8-bit, but Adam will feel the missing hardware decode.
- **API (Studio):** `ImportTimelineFromFile` (AAF, EDL, XML, FCPXML, DRT, ADL), `CreateTimelineFromClips`, `AppendToTimeline`, `AddRenderJob`, `StartRendering`, `CreateSubtitlesFromAudio`, `DetectSceneCuts`, and `-nogui` headless launch. [docs-only: https://wiki.dvresolve.com/developer-docs/scripting-api, which says it is imported from the docs bundled with Studio; whether the host is official is unverified] That list does not name OTIO, but it does name XML, so FCP7 XML from OTIO is the handoff. Check the README bundled with the installed version.
- **Limits:** static property values only through the API, no animated keyframes, per one MCP README. [secondary: https://github.com/hiteshK03/davinci-resolve-mcp] `samuelgursky/davinci-resolve-mcp` (about 3.9k stars, MIT, v4.18.5, 37 compound tools, 338 of 361 API methods live-tested) says itself that it does first-pass assembly and does not judge whether a cut is good. [secondary: its README]
- **Runs on:** macOS 15+ on Apple Silicon with 8 GB RAM (16 GB when using Resolve's Fusion page). Windows 10 Creators Update or later with 16 GB (32 GB with that page). GPU integrated, or discrete with at least 4 GB VRAM. The "32 GB for 4K" wording applies only to Windows on Arm. [verified: same readme]

### 3.3 Everything else considered

| Tool | Status today | Verdict |
|---|---|---|
| ffmpeg | 9.0.2 latest; Homebrew `ffmpeg` and `ffmpeg-full` both at 9.0.2. `ffmpeg` has no libass, freetype or harfbuzz dependency. `ffmpeg-full` has all three plus whisper.cpp, and is keg-only [verified: ffmpeg.org/download.html, formulae.brew.sh JSON] | Core. Use `ffmpeg-full` by its full path, because `subtitles` and `drawtext` need those libraries [inference from the dependency list; the check in section 5.1 proves it]. Its dependency tree is large, so preview the install size |
| ffmpeg `whisper` filter | Added in 8.0, needs `--enable-whisper` and a model [secondary: https://heise.de/-10522091]. `ffmpeg-full` depends on whisper.cpp [verified: formulae.brew.sh] | Not primary. Separate tools give easier word-level control [inference] |
| mlx-whisper | 0.4.3, released August 2025 [verified: PyPI] | Mac transcriber only where Metal is available, which excludes the sandbox (section 4.2). About twice as fast as whisper.cpp in one informal test [secondary: https://notes.billmill.org/link_blog/2024/08/mlx-whisper.html] |
| faster-whisper | 1.2.1 [verified: PyPI]. CTranslate2 publishes macOS arm64 wheels [verified: PyPI] | Default transcriber in the sandbox on Mac and on PC. CPU speed on the M1 Max is not measured. One report of a crash with PyAV 19, so pin `av<19` if seen [secondary: laozhang] |
| WhisperX | About 25k stars, BSD-2. Word alignment by wav2vec2. README says CPU mode on macOS. Diarization needs a Hugging Face token and accepting a model agreement [verified: https://github.com/m-bain/whisperX] | PC aligner. Has a Slovak model, `comodoro/wav2vec2-xls-r-300m-sk-cv8` [verified: whisperx/alignment.py line 97]. Slovak quality is untested |
| ElevenLabs Scribe v2 | $0.22/hour; keyterm prompting $0.05/hour extra [verified: https://elevenlabs.io/pricing/api] | Backup only, because audio leaves the machine |
| auto-editor | 31.8.0, 30 October 2026, on GitHub and Homebrew; PyPI is stale at 29.3.1 from November 2025. About 5.7k stars, Unlicense, written in Nim. Cuts by loudness or motion. Exports to Premiere, Resolve, Final Cut, Shotcut, Kdenlive [verified: https://github.com/WyattBlue/auto-editor, formulae.brew.sh, PyPI] | Useful first pass and baseline. Install from Homebrew, not pip. Cannot tell a retake from a good take [secondary: laozhang] |
| PySceneDetect | v0.7.2 (11 Oct 2026), BSD-3 [verified: https://github.com/Breakthrough/PySceneDetect] | Use `AdaptiveDetector` on proxies for multi-shot footage. Skip on single-shot talking heads |
| OpenTimelineIO | 0.18.1, Apache-2. `OpenTimelineIO-Plugins` 0.18.1 pulls `otio-fcp-adapter`, which reads and writes Final Cut Pro 7 XML, and the CMX 3600 EDL adapter. The FCPX adapter, `otio-fcpx-xml-adapter`, is separate, 1.0.0 from 2023, and not in that bundle [verified: PyPI metadata and both adapter READMEs] | EDL to FCP7 XML export layer. Resolve lists XML as an import format. Round trip untested. FCPXML only if Adam moves to Final Cut |
| MoviePy | 2.2.1 [verified: PyPI] | Rejected for 4K long form. It processes frames in Python, which is slow next to ffmpeg filters [inference, not benchmarked] |
| Remotion | Free for individuals and for-profits up to 3 employees; Company licence above that; terms change in 5.0 [verified: https://github.com/remotion-dev/remotion/blob/main/LICENSE.md] | Good for code-made titles and graphics. Watch this if Jorah becomes a business |
| Shotcut / MLT | Native project format is MLT XML. Forum replies say it cannot import EDL, and I found nothing showing FCP XML or FCPXML import [secondary: https://forum.shotcut.org/t/how-to-import-edl-file/592, https://forum.shotcut.org/t/fcp-xml-import-ist-es-moglich-is-it-possible/12024; current manual not read, so unverified]. auto-editor exports to it directly [verified above]. `melt` CLI behaviour not re-checked | Free GUI for Adam's finishing only through an MLT file, not the XML handoff. Add an MLT writer only if Adam picks Shotcut |
| CapCut | No official editing API found. Community projects write drafts you open in the app. One guide says the terms ban scripted access; draft files are reportedly encrypted in some JianYing versions [secondary: https://www.wireflow.ai/blog/capcut-api] | Rejected. Terms not read directly |

### 3.4 Real open-source projects and how good they are

No independent evaluation against human editors exists that I could find. All quality claims below come from authors, vendors or reviewers. [secondary: https://cutback.video/blog/claude-for-video-editing-in-2026-what-works-what-breaks-and-the-real-pipeline is from a vendor]

| Project | Numbers | What it does | Honest read |
|---|---|---|---|
| `browser-use/video-use` | 30.4k stars, MIT, last push 2026-10-08, 23 commits on main [verified: GitHub API and repo page] | Scribe transcript, packed phrase file, LLM edit list, ffmpeg render, self-evaluation up to three times | Best design to borrow. Young and small. Requires ElevenLabs; local transcription PRs #231, #223 and #151 were all still open on 2 November [verified: GitHub API]. Read #231 before writing the adapter. Good on talking heads |
| `barefootford/buttercut` | 614 stars, PolyForm Noncommercial with commercial-output exception, Apple Silicon focus, multi-track and preview are Pro at $49/year [verified: https://github.com/barefootford/buttercut] | WhisperX, frame analysis, XML export to Final Cut, Premiere, Resolve | Good idea for NLE handoff. Licence blocks bundling it into a product, and no public Windows support. Do not base Jorah on it |
| `samuelgursky/davinci-resolve-mcp` | About 3.9k stars, MIT | Drives Resolve | Use later if Adam buys Studio |
| Hasan's Claude Code guide and repo | MIT, tested only on Windows 11, talking head plus screen content [secondary: https://learnwithhasan.com/guide/claude-code-video-editing/] | Remotion shots, AssemblyAI, private YouTube draft, a cut verifier, a stop before the mix | Useful as a review-gate example |
| VectCutAPI (formerly CapCutAPI) | About 2.2k stars [secondary: https://aituber.app/blog/capcut-mcp-claude/] | CapCut drafts, no video export | Rejected |

### 3.5 What goes wrong when an LLM cuts

One vendor's test: asked for a 5-minute cut from a 30-minute interview, Opus returned cuts totalling 578 s while stating 299 s, and all 11 cuts broke a sentence. [secondary: Cutback, a single run by a seller of a competing tool] It has an interest in the result, but it matches the failure that matters: **models do not do timing arithmetic and do not hear audio.**

Rules that follow, all enforced in code and not left to the prompt:

1. The LLM selects phrase IDs. It never writes timestamps.
2. Code maps IDs to word boundaries, snaps edges to silence, adds padding, and computes the duration. The model is told the real number and iterates.
3. Timestamps drift. Reports range from 50 to 100 ms for Scribe [secondary: video-use SKILL.md], about 120 ms in one test [secondary: Cutback], 100 to 300 ms in another [secondary: https://motionbox.io/blog/llm-video-editing-workflow], and Whisper clipping word endings by about half a second [secondary: laozhang]. So padding of 30 to 200 ms and silence snapping are mandatory, and the Whisper case needs testing on Adam's audio.
4. After render, measure rather than trust: re-transcribe the output, check loudness and boundaries.
5. Whisper may hide what needs cutting. video-use's SKILL.md rejects local CPU Whisper, saying it is "slow and it normalizes fillers". [verified: its SKILL.md, from a project built around a hosted rival] If false starts vanish from the transcript, retake logic cannot see them. Hand-check fillers on a 2-minute sample of Adam's audio, and use the silence map as a second signal [inference]. Scribe is the fallback only with Adam's yes (question 6).

---

## 4. Video: pipeline design

### 4.1 Stages and gates

```
G0  tools check / install preview -> Adam yes (first run only)
1   ingest: clone source, ffprobe, checksum, disk check
2   audio: 16 kHz mono WAV, silence map, loudness map
3   transcribe: word-level JSON, cached by source checksum
4   proxy: 720p H.264 for preview and frame sampling
5   visuals: scene cuts if multi-shot, contact sheets, optional bulk labels
6   pack: phrase-level transcript with IDs and retake clusters
G1  strategy: 4 to 8 sentences on shape, length, must keep, must cut -> Adam yes
7   select: LLM picks phrase IDs and beat order
8   compile: code validates and computes EDL (frames, padding, snapping)
9   preview: 720p render with captions
10  self-check: gates in 4.4, up to 3 fix passes, then report what remains
G2  review: paper edit plus preview -> Adam approves or gives notes
11  final render at source resolution, captions, music, chapters, 3 thumbnails, titles
12  self-check on the final file
G3  Adam gets final.mp4, FCP7 XML, SRT, metadata, licence ledger
13  (phase 2) upload private -> Adam publishes in Studio
```

Scripts should run as one deterministic pipeline with the LLM only at steps 5, 6, 7 and 11. For the MVP that is a plain Python driver inside the sandbox, with approvals as chat messages.

OpenClaw's Lobster has resumable approval checkpoints, timeouts and output caps, and is an optional plugin, not installed now. It runs in-process in the Gateway, each step can call any CLI, and the tool is disabled in sandboxed tool contexts. [docs-only: /opt/homebrew/lib/node_modules/openclaw/docs/tools/lobster.md lines 25-31, 69-70, 121] So its steps would sit outside Claude Code's sandbox, the same exposure as the known `exec` gap [inference]. It is a later option after the security track decides, not the MVP driver.

Long jobs differ by path:

- **Jorah's own `exec`** (unsandboxed): default timeout 1800 s, set `timeoutSeconds` per call, and a subagent gets no automatic wake on background completion. [docs-only: tools/exec.md lines 33-44, 99-110] A 1-hour job without an explicit timeout is killed at 30 minutes.
- **Delegated Claude Code** (sandboxed): a foreground Bash command defaults to 2 minutes and is capped at 10 unless `BASH_MAX_TIMEOUT_MS` is raised. [verified: https://code.claude.com/docs/en/env-vars] So long stages run in the background or are split, and they must resume from caches. ACP turns use OpenClaw's agent and run timeouts, and `sessions_spawn` has no per-call override; the operator setting is `agents.defaults.subagents.runTimeoutSeconds`. [docs-only: tools/acp-agents-setup.md lines 382-386] That setting and `agents.defaults.timeoutSeconds` returned no value in the jorah profile today [verified locally]. What a 1-hour delegated run actually hits is [unverified]; V3 measures it.

### 4.2 Project layout

```
~/work/creative/
  tools/                      pinned venvs and tools.lock
  video/skill/                vendored code, gates, tests
  video/style/<channel>.md    Adam's learned preferences
  video/music/                shelf and licences.json
  video/projects/<slug>/
    source/                   APFS clones, read-only
    cache/                    wav, transcripts, proxies, sheets
    edit/   takes.md, edl.json, master.srt, preview.mp4, final.mp4, final.xml
    evidence/ gates.json, timings.json, decisions.md
```

Delegated Claude Code can write only in `sandbox/` and `~/work`, with no home reads and no network. So source footage must be brought in by a gated copy. On the same APFS volume `cp -c` makes a clone that costs no extra disk until modified [inference]. External disks need a read path added to the sandbox, which is a decision for the security track. A nice result of this design: once tools and model weights are installed, stages 1 to 12 need no network except the LLM call itself.

**GPU and hardware encoding are blocked in that sandbox.** Measured today with a small Swift probe on this Mac, macOS 27.0.1. Outside any sandbox it found the M1 Max, ran a Metal compute job, and encoded 5 frames with hardware H.264. Then I ran it under `sandbox-exec` with the static rules from Anthropic's public source (https://github.com/anthropic-experimental/sandbox-runtime, `macos-sandbox-utils.ts`): deny by default, `iokit-open` only for IOSurface and RootDomain, and a fixed `mach-lookup` list.

| Rules | Metal | VideoToolbox hardware H.264 |
|---|---|---|
| As published | No device | Fails, status -12908 |
| Plus all `iokit-open` | Device found; shader compile fails, MTLCompilerService lookup refused | Fails, status -12908 |
| Plus all `mach-lookup` | No device | Works |
| Plus both | Works | Works |

[verified: local probe] Limit: these are copied rules, not a run through Claude Code itself. The installed Claude Code 2.1.300 binary contains `IOSurfaceRootUserClient` and `allowMachLookup` and no string for `AGXDeviceUserClient` or `MTLCompilerService`, which fits. The first step of V3 is to repeat the probe inside a real delegated run.

What follows:

- `mlx-whisper` and Metal builds of whisper.cpp should not work in the sandbox, and `h264_videotoolbox` should fail [inference from the probe; neither tool is installed].
- `network.allowMachLookup` is a documented setting. [verified: https://code.claude.com/docs/en/sandboxing] It could open VideoToolbox, but I could not narrow the names (prefixes for coremedia and videotoolbox were not enough), and allowing every lookup weakens the sandbox. `iokit-open` is fixed in the source I read, so settings cannot open Metal [inference].
- `sandbox.excludedCommands` runs a matching command with full access, even with `allowUnsandboxedCommands: false`. [verified: same page]

**Pick.** V1 runs CPU-only in the sandbox: `faster-whisper` and `libx264`. No config change. Before V2, if CPU times are too slow, add one `media-worker` script:

- It takes only a validated EDL JSON, with no free-form filter strings.
- It wraps itself in its own Seatbelt profile: no network, project paths only, plus the GPU rights in the last table row.
- It is the single `excludedCommands` entry.

That is a security exception, so it needs the security track and Adam's explicit yes [inference]. `sandbox-exec` still worked on macOS 27.0.1, though Apple lists it as deprecated (from memory). Runner-up: open only `allowMachLookup` for VideoToolbox and keep CPU transcription. What would change this: V1 CPU times that Adam finds fine, which removes the need for any exception.

### 4.3 EDL schema (minimum)

```json
{
  "schema": 1,
  "fps": "30000/1001",
  "target_seconds": 720,
  "computed_seconds": 708.4,
  "segments": [
    {"id": "s012", "source": "cam-a", "phrase_ids": ["p0841", "p0842"],
     "in_frame": 90112, "out_frame": 90644, "pad_ms": [80, 120],
     "reason": "hook restated cleanly, take 2 of 3", "beat": "intro"}
  ],
  "chapters": [{"title": "Why this matters", "at": 0.0}],
  "captions": {"mode": "sidecar", "burn": false},
  "music": [{"track": "shelf:calm-01", "in": 0, "out": 42, "duck_db": -18}],
  "overlays": []
}
```

Compile rejects: an unknown phrase ID, a cut inside a word, overlap, a source missing or changed checksum, or a duration outside tolerance. `computed_seconds` is written only by code.

### 4.4 Quality gates

All automated gates write to `evidence/gates.json`. A failure blocks showing the preview as ready.

| Gate | Check | Pass |
|---|---|---|
| Duration | Sum of EDL against ffprobe of output | Within 1 frame per segment overall; target ±10% unless Adam set a hard length |
| Word integrity | Every cut edge at a word boundary | 0 violations |
| Sentence integrity | Segment starts or ends mid-sentence (from punctuation) | 0 unflagged |
| Content match | Re-transcribe the output, align with the expected kept text | ≥98% word match; list the differences |
| A/V sync | Compare word times in the re-transcript with expected, at start, middle and end | Drift ≤100 ms, no growing trend |
| Audio pops | Peak at each boundary against surrounding level | No spike above 6 dB over local RMS [inference, tune] |
| Loudness | `ebur128` integrated and true peak | About -14 LUFS ±1, true peak ≤ -1 dBTP [inference: common YouTube target, not checked in Google's docs] |
| Picture | `blackdetect`, `freezedetect` | None outside planned moments |
| Format | ffprobe | H.264 High, 4:2:0, source fps, AAC 48 kHz, fast start, target bitrate |
| Captions | SRT times inside output range, proper-noun list checked | No overlaps, Adam's names spelled right |
| Rights | Every music and overlay asset in `licences.json` with source and date | 100% |
| Boundary look | Filmstrip of each cut viewed by the model | No flash or wrong shot; capped by cost |

The gates cannot judge pacing, humour or whether the story works. Only Adam can. The final gate is human, and an honest report says what the model could not check, for example "I cannot hear this".

### 4.5 How the LLM picks cuts, and the cost

**Text pass (always).** Phrase-level transcript with IDs, breaking on silences of 0.5 s or more, plus retake clusters found by code (near-duplicate phrases within 60 to 120 s). The theme brief decides what stays: a "theme" is a selection and ordering rule, for example "only the parts about X, in the order problem, attempt, result".

**Vision pass (only where it changes a decision).** Video-use's rule is sound: read the transcript, and look at images only at decision points. Look at frames for:

- choosing between retakes
- phrases like "as you can see"
- screen recordings
- B-roll choice
- checks after a cut

**Image tokens.** Cost is `ceil(width/28) x ceil(height/28)`. Claude 4.7 and later accept up to 2576 px long edge and 4,784 visual tokens. Up to 600 images per request, 128 MB request. [verified: https://platform.claude.com/docs/en/build-with-claude/vision]

**Prices per million input tokens:** Opus 5.5 $4, Sonnet 5.5 $2, Haiku 5.5 $0.10 (prompts up to 100k tokens; $0.50 beyond). Output $20, $10, $0.50. Batch is half price. [verified: claude-api skill model table, cached 2026-10-06]

Frame cost for 1 hour of source, arithmetic from the above [inference]:

| Sampling | Tokens | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| 1 fps at 1080p (3,600 x 2,691) | 9.69M | $38.75 | $19.38 | $0.97 if chunked below 100k per prompt |
| 1 per 10 s at 640x360 (360 x 299) | 107,640 | $0.43 | $0.22 | $0.011 |
| 360 frames on 10 contact sheets of 6x6 at 1440x810 (10 x 1,508) | 15,080 | $0.06 | $0.03 | $0.002 |
| 60 cuts, 2 frames each at 640x360 (post-render check) | 35,880 | $0.14 | $0.07 | $0.004 |

The 1 fps line agrees with an independent figure of 1.61M tokens per 10 minutes. [secondary: laozhang] Never sample at 1 fps; contact sheets first, 640x360 at decision points.

Typical edit of 1 hour of source into a 12-minute video, at API rates [inference]:

| Step | Model | Approx. cost |
|---|---|---|
| Plan: 50k input, 3k output | Opus 5.5 | $0.26 |
| Bulk frame labels: 360 frames | Haiku 5.5 | $0.02 |
| Selection: 60k input, 8k output | Opus 5.5 | $0.40 |
| Boundary checks | Haiku 5.5 or Opus 5.5 | $0.01 to $0.14 |
| 3 revision rounds, cached input at $0.20/M, 8k output each | Opus 5.5 | About $0.55 |
| Titles, description, thumbnail ideas | Opus 5.5 | $0.05 |
| **Total** | | **About $1.30 to $1.40; plan for $1.50 to $5** because thinking is billed as output |

On the Max subscription this uses subscription allowance instead of dollars. Whether a 1-hour job fits in a session window is [unverified]; measure it. Thumbnail image generation depends on which provider is configured in OpenClaw and is not priced here.

**Non-speech footage** such as robot-build time-lapse or vlog with no talking: transcript logic has nothing to work with. This needs a visual-first mode (scene detection, per-scene labels from contact sheets). Expect noticeably lower quality. Keep it out of the MVP [inference].

### 4.6 Review UX

Compact, in the channel Adam already uses (Telegram now, companion app later), with exact steps:

**G1 strategy message.** Plain text, one screen:

> 58 min of source, 3 retake clusters, 1 long tangent about X. Plan: 12 min, problem, attempt, result. Keep the failed test at 31:10. Cut the tangent. Captions sidecar. Calm music on intro only. OK?

Buttons: Go, Change.

**G2 review.**
- Paper edit: a numbered list of kept segments with the first words, length and reason, plus a list of what was removed.
- Link to a 720p preview served only over Tailscale, because Telegram bots can send files only up to 50 MB (2000 MB through a self-hosted Bot API server). [verified: https://core.telegram.org/bots/api]
- A gate summary with any failures in plain words, such as "Audio spike at 04:12, could not remove".
- Notes in natural language, by text or voice: "bring back the bit about the battery", "tighter intro".
- Each note becomes an EDL change and a small diff: "Removed 2 segments, added 1, new length 11:48".

**Local review page** (phase 2). Video on top, transcript below with kept text normal and cut text struck through, click to toggle a segment, and one Approve button. Keyboard and screen-reader friendly, one column on a phone. A transcript-style view matches how Adam will think about the edit.

**G3 delivery.** `final.mp4` path, plus FCP7 XML for finishing, SRT, chapter list, 3 titles, 3 thumbnails, licence ledger. Nothing is posted.

**Upload (phase 2).** Message reads "Uploaded as private: <Studio link>". Adam checks Studio's copyright checks and publishes there. Jorah has no publish path in code, and the uploader rejects any privacy value other than `private`.

### 4.7 Hardware and time for 1 hour of 4K

The figures below were not measured here because ffmpeg is not installed and installing was out of scope. Benchmark V3 in section 8 replaces them with real timings. All of them assume Metal and hardware decode and encode, so they describe the media-worker path. Inside the sandbox everything is CPU; expect transcription, proxy and final render to be several times slower [inference, unmeasured].

Published numbers: Resolve UHD HEVC 50 Mbps encode, 91.64 fps on M1 Max, 130.72 fps on RTX 5070; the page does not state sample sizes for those two values. [verified: https://www.pugetsystems.com/pugetbench/results/compare/Puget%20Bench%20for%20DaVinci%20Resolve/27/GPU/Apple%20M1%20Max(32%20Cores)/NVIDIA%20GeForce%20RTX%205070/] These are Resolve figures, not ffmpeg. ffmpeg VideoToolbox on 4K: 40 to 60 fps on an M1 Pro, settings unknown. [secondary: https://spy.macrumors.com/threads/mac-mini-m1-h-265-encoding.2269815/page-4] Large-v3 about 10x realtime on M1 Max, method unstated. [secondary: https://www.promptquorum.com/ja/local-llms/apple-silicon-whisper-metal-benchmark]

Estimates for an M1 Max with 64 GB (10 CPU cores, 32 GPU cores, verified locally) [inference]:

| Stage | Time |
|---|---|
| Ingest (clone, ffprobe, checksum of about 45 GB) | 1 to 2 min |
| Audio extraction and silence map | 2 to 5 min |
| Transcription, large-v3-turbo | 4 to 8 min |
| 720p proxy, hardware decode and encode | 6 to 18 min |
| Scene detection on proxy, if multi-shot | 5 to 15 min |
| Contact sheets | 1 to 3 min |
| LLM stages | 5 to 20 min |
| Preview render, 12 to 15 min output | 2 to 5 min |
| Final 4K render, 15 min output (27,000 frames at 50 to 92 fps) | 5 to 9 min |
| Same for 60 min output (108,000 frames) | 20 to 36 min |
| **First pass total, 15 min output, hardware path** | **About 30 to 90 min unattended** |
| Revision after notes (caches reused) | 5 to 15 min |

Software x264 at 4K would be several times slower. Use hardware encoding at high bitrate for a YouTube master, since YouTube re-encodes anyway, and offer x264 as an overnight option [inference].

**Disk** (arithmetic):

| Item | Size |
|---|---|
| 4K source at 100 Mbps | 45 GB/hour |
| 720p proxy at 5 Mbps | 2.25 GB/hour |
| 16 kHz mono WAV | 115 MB/hour |
| Final at 40 Mbps, 15 min | 4.5 GB |
| ProRes source | Hundreds of GB/hour; exact rate not confirmed |

The Mac has 181 GiB free by `df`, checked today. Rule: check free space before ingest, refuse below 50 GB plus estimated needs, and list old caches for cleanup with Adam's yes. Never delete sources.

**PC tiers.** PC specs are unknown. Check: `dxdiag` GPU model and VRAM, CPU, RAM, free NVMe, Windows version, NVENC support in NVIDIA's matrix (https://www.developer.nvidia.com/video-encode-decode-gpu-support-matrix), network speed to the Mac.

| Tier | CPU | RAM | GPU | Storage | Notes |
|---|---|---|---|---|---|
| Minimum | 8 cores | 32 GB | NVIDIA with NVENC, 8 GB VRAM | 1 TB free NVMe | Resolve's stated Windows minimum is 16 GB, 32 GB with its Fusion page, and an integrated GPU or 4 GB VRAM [verified]; the 32 GB and 8 GB here are my margin [inference] |
| Recommended | 12 to 16 cores | 64 GB | RTX with 12 to 16 GB VRAM | 2 TB+ NVMe plus backup | Whisper and an editor at once without pain [inference] |
| TRELLIS.2 only | | | NVIDIA with 24 GB VRAM, Linux | | [verified: https://github.com/microsoft/TRELLIS.2] |

The pipeline has one abstraction per OS: an encoder profile (VideoToolbox or NVENC, libx264 as the fallback) and a transcriber. EDL, gates and tests stay the same [inference]. Windows path quoting and fonts for burned captions are the known cross-platform risks [inference].

**Windows has no sandbox here.** On native Windows, Claude Code runs commands unsandboxed; the sandbox needs WSL2. [verified: https://code.claude.com/docs/en/sandboxing] Whether NVENC or CUDA work under that WSL2 sandbox is [unverified]. So today's "delegated tasks are sandboxed" assumption does not carry over to the PC, and this belongs in the security track before any PC run.

Footage moves between PC and Mac by Tailscale file copy. OpenClaw's File Transfer tools are limited to 16 MB per binary. [docs-only: plugins/reference/file-transfer.md] They are for metadata and small results only.

### 4.8 Music, thumbnails, captions

**Music.**
- YouTube Audio Library: available only in YouTube Studio, royalty-free, monetizable, downloaded tracks will not be claimed through Content ID; Creative Commons tracks need credit in the description. Use outside YouTube is not addressed. [verified: https://support.google.com/youtube/answer/3376882]
- Since it is Studio-only, Adam downloads a small shelf once by hand. Jorah picks only from the shelf and logs the choice. No browsing or auto-download in the MVP [inference].
- Paid later: Epidemic Sound direct licence, prices not shown on the capture of its pricing page [verified: https://www.epidemicsound.com/pricing/]; third-party prices vary from $10 to $17 per month [secondary: https://www.creatorstackclub.com/software/epidemic-sound, https://www.artyfile.com/blog/artlist-vs-epidemic-sound-vs-artyfile-comparison-2026]. Artlist is about $199/year and reportedly keeps licences for published work after cancelling [secondary: https://www.creatorstackclub.com/software/artlist].
- Pixabay: free, no attribution in the summary, no mention of Content ID; the full terms bind. [verified: https://pixabay.com/service/license-summary/] Not a default.
- AI music: OpenClaw has `music_generate` once a provider is set. [docs-only: tools/media-overview.md] Suno's commercial terms are [unverified]. Off by default, and YouTube wants disclosure when it is the main focus.

**Captions.** Always produce a sidecar SRT with output-timeline offsets. Burning in is optional and is the last filter, after overlays. Keep a per-channel spelling list. Generate from the verbatim transcript, then remove fillers only where they were cut.

**Thumbnails.**
- Pick 5 to 8 sharp candidate frames: open eyes, high contrast, on-theme. Render 3 layouts with Adam's fonts by PIL at 3840x2160.
- AI-generated faces or scenes only on request, with the disclosure check applied.
- Do not rely on any claim about what thumbnails perform best; A/B testing lives in Studio. Check legibility at 320 px wide with a downscale test.

---

## 5. Video: exact steps for the next session

Each step lists its evidence tier. Nothing here has been done.

### 5.1 Tool install, after preview and Adam's yes

Tools lock (versions current today; pin exact versions at install time):

| Tool | Version | Source |
|---|---|---|
| ffmpeg-full | 9.0.2 | Homebrew, keg-only, call by full path |
| uv | Current | Homebrew (not installed today) |
| Python | 3.12 under uv | System Python is 3.13.3 |
| faster-whisper | 1.2.1 | PyPI |
| mlx-whisper | 0.4.3 | PyPI, media worker only |
| auto-editor | 31.8.0 | Homebrew, only if used. PyPI is stale |
| scenedetect | 0.7.x | PyPI |
| opentimelineio | 0.18.1 plus plugins | PyPI |
| google-api-python-client | Pin at install | Phase 2 only |

Checks after install:

```
"$(brew --prefix ffmpeg-full)/bin/ffmpeg" -hide_banner -filters | grep -E ' (subtitles|ass|loudnorm|ebur128|silencedetect|blackdetect|freezedetect) '
"$(brew --prefix ffmpeg-full)/bin/ffmpeg" -hide_banner -encoders | grep -E "videotoolbox|libx264"
```

Pre-download the Whisper model and check the size before fetching.

### 5.2 Build order

1. Read every file of `browser-use/video-use` at a pinned commit. Remove the parts that conflict with Jorah's rules: the instruction to install things on first use with `npx --yes`, asking the user to paste an API key into `.env`, and the "do not wait for permission" wording. [verified: its SKILL.md] Keep the correctness rules: subtitles last, per-segment extract then concat, 30 ms fades, no cut inside a word, padding, output-timeline captions, transcript cache, ask before cutting.
2. Write a local transcription adapter that outputs the same word-level JSON the rest of the code reads. Read open PR #231 first. Use `faster-whisper` on CPU.
3. Add the EDL compiler with phrase IDs and validation (section 4.3). Unit tests with a synthetic transcript, no video needed.
4. Add the gates (section 4.4) as a CLI: `gates.py final.mp4 edl.json` writes `gates.json` and exits non-zero on failure.
5. Add FCP7 XML export through OTIO. Open it once in Resolve by hand to prove it round-trips. Shotcut cannot be the proof, since it has no known import for this format.
6. Write `SKILL.md` for Jorah with the stage list and gates, then test via an ACP-delegated Claude Code run in the sandbox. Run the Metal and VideoToolbox probe in that same run and record the result.
7. Run V1, V2, V3 from section 8. Record evidence.
8. Phase 2: media-worker decision (section 4.2), review page, upload tool, Windows profile.

Effort: 2 to 3 focused sessions to pass V1 and V2 [inference].

---

## 6. 3D: facts that shaped the design

### 6.1 Autodesk Fusion

**Licence.**
- Personal use: home-based, non-commercial, under $1,000 a year in revenue, renewable every three years. [secondary: https://stacksheriff.com/3d-printing/fusion-360-free-personal-license/, which cites Autodesk's eligibility page; that page returned 403 here]
- Up to 10 active editable documents; an assembly counts as one. Local export of STEP, STL, OBJ, F3D and others stays available. Local rendering is included; cloud rendering, simulation, generative design and extensions are not. **Scripts, add-ins and API access are unchanged.** [verified: https://help.autodesk.com/view/fusion360/ENU/?caas=caas%2Fsfdcarticles%2Fsfdcarticles%2FFusion-360-Free-License-Changes.html, page stamped 2026-09-29; the changes it describes date from 2020 and 2021, so it predates MCP]
- Is agent automation allowed? I found no term forbidding it, and Autodesk promotes AI clients over its own MCP, but the full legal terms could not be read (403). [unverified]
- Autodesk staff have said developing apps for commercial use on a personal licence is not encouraged. [secondary: https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/legal-amp-license-questions-about-plugin-development/td-p/10084565]
- If Jorah becomes a business or designs anything sold, Adam needs the paid plan: $85/month or $680/year US list, checked 11 August. [secondary: https://vagon.io/blog/fusion-360-pricing] EU price [unverified].

**Official local MCP server.**
- Runs inside the desktop app. Enabled by Preferences > General > API > "Fusion MCP Server". Endpoint `http://127.0.0.1:27182/mcp` over Streamable HTTP, no sign-in. Only available while Fusion is open with a document. Tool list is discovered at connect time and can change between releases. [verified: https://help.autodesk.com/cloudhelp/ENU/ADSKMCP-FusionDesktopMcp/files/ADSKMCP_FusionDesktopMcp_connecting_to_the_fusion_mcp_server_html.html, https://help.autodesk.com/view/fusion360/ENU/?guid=FMCP-OVERVIEW]
- Tools reported by a third party: read, execute Python, undo/redo, electronics read. The toggle has no API, must be applied by hand, and on Mac must be set manually. The server acts only on the active document. [secondary: https://wiki.adom.inc/api/pages/adom/fusion-bridge/files/fusion-mcp-server.md, https://wiki.adom.inc/api/pages/adom/fusion-bridge-macos/files/skills/fusion-mcp-and-preferences/SKILL.md]
- **Does personal use get it?** Autodesk's launch post says "Fusion subscribers" [verified: https://aps.autodesk.com/blog/bringing-fusion-claude-creative-work]. Two guides could not confirm personal-use access. [secondary: https://makers101.com/chatgpt-fusion-360/, https://techdrawai.com/blog/connect-claude-to-fusion-360] One wiki says Autodesk gates it to subscribers. [secondary: Adom] Autodesk's overview and connection pages name no licence tier. [verified: both pages above] The evidence leans towards no, but it is [unverified]. The test is simple: install Fusion and look for the checkbox. The add-in routes use the plain API, which the licence page says is unaffected, so they should work on personal use [inference].
- **Reliability.** Autodesk says AI modelling is not yet reliable for complex models or full assemblies, as quoted by one guide. [secondary: makers101] It suits boxy, dimension-driven parts. Curved or measured parts still need a person; runs can be slow; token-burn complaints exist. [secondary: makers101] I found no published success rate for Claude with Fusion. [secondary: techdrawai confirms none in its review]

**Other Autodesk servers.**
- Fusion Data MCP: cloud, project and folder data, no live modelling. [verified: FMCP-OVERVIEW]
- Fusion Compute MCP: headless Fusion in the cloud, public beta with application, needs an active licence and a Team hub. [verified for existence: https://feedback.autodesk.com/key/FusionAutomationMCP; requirements: secondary, makers101] Not for now.

**Community and sample servers.**

| Server | Stars / state | Tools | Security | Read |
|---|---|---|---|---|
| `AutodeskFusion360/FusionMCPSample` | Autodesk sample, MIT, 27 stars, last push 2026-01-06; its tips call it a functional sample, not a product [verified: repo and tips.md] | `execute_api_script`, `get_screenshot`, `get_api_documentation` | Binds localhost:9100. No auth check in `do_POST`, no Content-Type check, and it sends `Access-Control-Allow-Origin: *` [verified: `server/mcp_server.py`]. Its "secure HTTP" wording has nothing behind it in that file | Best fallback only after patching: small, official origin, about 10 lines to add a bearer token [inference] |
| `faust-machines/fusion360-mcp-server` | 142 stars, MIT, last push 2026-10-06, 363 tests, beta, tested on Fusion 2705 macOS arm64 [verified] | 93, with `execute_code` | TCP 9876, no authentication by its own README | Most complete. One operation per call, 30 s main-thread limit, all units centimetres. Never expose beyond loopback |
| `ndoo/fusion360-mcp-bridge` | 27 stars, single commit, MIT; states a free personal licence is enough [verified: https://github.com/ndoo/fusion360-mcp-bridge] | `fusion_execute`, `fusion_screenshot` | Loopback plus bearer token in a 0600 file | Best auth model, least tested. Good pattern to copy |
| `AuraFriday/Fusion-360-MCP-Server` | Proprietary per techdrawai [secondary] | Generic API call | | Skip |

**Fusion security.** Every route gives `execute Python as Adam inside Fusion`, outside the Claude Code sandbox. Fusion's Python has normal OS access [inference]. Any local process can reach the official server while the box is ticked [secondary: techdrawai]. Consequences:

- Enable it only for a Fusion session and untick afterwards.
- Do not run Autodesk's sample unpatched. As shipped, a web page open in Adam's browser could send a `text/plain` POST to it and run Python, unless the browser's local-network protection stops that. [inference from the code; not attempted] Add a bearer token from a 0600 file, as `ndoo/fusion360-mcp-bridge` does, and remove the CORS header.
- Test the official server the same way in F1. Autodesk says it needs no authentication because it is local only. [verified: FMCP-OVERVIEW] Whether it checks `Origin` is [unverified].
- Do not feed it instructions from web pages or email.
- Keep it on its own Fusion account and project.
- Treat Fusion access as equal to the known `exec` gap in the Jorah setup.

**Platform.** Native on macOS arm64 per faust's testing, and Windows is supported. [verified: faust repo] No Linux desktop build that I know of [inference, from memory]. Autodesk's requirements page returned 403, so macOS 27 support is [unverified]. Fusion must run in a logged-in desktop session, so on the always-on PC it needs an interactive session, not a service. Running `adsk.core` outside Fusion is fragile and unsupported. [secondary: https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/unable-to-run-any-scripts-module-not-found-error-adsk-core/td-p/12946004]

**OpenClaw wiring.** MCP servers go under `mcp.servers`, and `openclaw mcp doctor <name> --probe` proves reachability. [docs-only: docs/tools/mcp.md] On Claude CLI managed turns, OpenClaw serves those tools through its loopback bridge as `<safe-server>__<safe-tool>`. [docs-only: docs/gateway/cli-backends.md lines 214-216] If Fusion runs on a machine other than the gateway, the loopback endpoint means the server must be hosted on that node through `nodeHost.mcp.servers`, which the docs describe for the headless node host. [docs-only: docs/nodes/mcp-and-skills.md] Whether node-published tools reach a Claude CLI agent, and whether the macOS app node does this, are [unverified]; try it first.

### 6.2 Code CAD

| Engine | State | For | Against |
|---|---|---|---|
| **build123d** | 0.13.0, Apache-2, Python 3.11 to 3.14, about 3.6k stars, last push 2026-10-30 [verified: PyPI, GitHub API] | BREP solids, STEP output, plain Python with `with` blocks, OCCT kernel | OCCT fillets and booleans can fail |
| CadQuery | 2.8.0, about 6k stars [verified: PyPI, GitHub API] | Larger community and research corpus (Text-to-CadQuery) [secondary: https://arxiv.org/abs/2505.06507] | Method chaining is harder to debug [secondary] |
| OpenSCAD | Last tagged release 2021.01; development snapshots in real use, such as 2026.06.12 [verified: GitHub releases; secondary: ModelRift] | Very fast recompute (about 16 ms vs 1.9 s), robust CSG | Meshes only, no STEP-class solids; silent failures; Manifold export open-edge report in February 2026 [secondary: lists.openscad.org] |
| FreeCAD | 1.1.4, 2026-09-28, LGPL [verified: GitHub] | Real GUI for Adam, TechDraw drawings, free for commercial use | Heavier to drive. `neka-nat/freecad-mcp` has about 3.2k stars, MIT, needs the GUI addon, and headless was an open request in one snapshot [verified stars; secondary: https://github.com/neka-nat/freecad-mcp/issues] |
| Onshape API | Free tiers around 2,500 calls a year; Professional 5,000 per user; one developer used a year's allowance in under a month [verified: https://onshape-public.github.io/docs/auth/limits; secondary: forum] | Cloud, Featurescript, Linux and browser | Caps are hopeless for an agent loop. Rejected |
| Blender | Official Lab MCP v1.0.3, needs Blender 5.1+, runs LLM code without guards and recommends a VM [verified: https://www.blender.org/lab/mcp-server/]. Community `ahujasid/mcp-for-blender` (renamed from `blender-mcp`) about 33k stars [verified: GitHub API]; one competitor reports 4 CVEs and a hang [secondary: https://www.strayspark.studio/blog/official-blender-mcp-server-comparison-2026] | Rendering, organic shapes | Mesh modelling, no reliable dimensions. Use `blender -b` for good renders if needed, no MCP |

**The best evidence available:** ModelRift, 12 September 2026, six agents on Claude Opus 5, three printable parts, CadQuery 2.8.0 and OpenSCAD 2026.06.12, checked by an independent STL parser. [secondary: https://modelrift.com/blog/cadquery-vs-openscad/, from a vendor in this space, small sample]

- Both reached watertight final meshes. Both tools produced silently wrong geometry mid-run: 5 cases for OpenSCAD, 4 for CadQuery. Of 16 failures, 9 were never reported by the tool.
- CadQuery once silently dropped a core cylinder while reporting `valid=True`, caught only by a volume check of 7,065 mm³ against 10,323 expected.
- Renders caught only coarse errors. Numeric checks caught the rest.

The lesson is more important than the tool choice: **never trust the CAD tool's own success signal; measure.** build123d was not in that test. It shares OCCT with CadQuery, so assume the same class of failure [inference].

Research: Text2CAD-Bench (600 examples) finds LLMs do reasonably on basic geometry and degrade on complex topology. [verified: https://arxiv.org/abs/2605.18430] Simpler APIs may raise early success at some cost in geometric accuracy. [secondary summary: https://arxiv.org/pdf/2508.01031] A test-based feedback loop improves pass rate by about 10% per a self-reported post. [secondary, paper not read: https://gr.linkedin.com/in/ioanna-malli]

**`pzfreo/build123d-mcp`.** 138 stars, Apache-2, 0.3.91, last push 2026-10-15. Persistent session, render PNG/SVG/DXF, measure volume, area, bounding box, topology, holes, printability, fit, export validation. [verified: https://github.com/pzfreo/build123d-mcp, PyPI] Its `security.md` says its namespace defences (AST check, restricted builtins, 30 s timeout) are not a hard boundary and recommends a container for untrusted input. [verified: security.md] Run it inside the OS sandbox, or borrow its measuring code. `Casys-AI/mcp-build123d` runs arbitrary Python by design and pins older versions. [secondary: https://jsr.io/@casys/mcp-build123d]

**Text-to-3D.**
- **Hunyuan3D 2.0 and 2.1 licences exclude the EU, UK and South Korea**, and the 2.0 text also bars using its output outside that territory. [verified: https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/LICENSE, https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE] Do not run it locally in Slovakia. Other versions and hosted API terms are [unverified].
- TRELLIS.2: MIT, image input, Linux only, NVIDIA 24 GB VRAM, tested on A100 and H100. [verified: https://github.com/microsoft/TRELLIS.2]
- Meshy and Tripo: hosted, prices not confirmed from vendor pages, rankings come from vendor or affiliate blogs. [secondary]
- All produce meshes with no meaningful tolerances [inference]. Use only for decorative shells, then boolean them onto a CAD core.

### 6.3 Verification

The same gate for every engine, independent of the CAD tool. Input is the exported STEP and STL plus `spec.yaml`.

| Check | Tool | Pass |
|---|---|---|
| Solid count | OCP on STEP | Exactly as specified |
| Volume | OCP and mesh agree | Within 1% of each other; within spec tolerance, 2% by default |
| Bounding box | OCP | ±0.1 mm |
| Named features | Hole diameter and position, from face queries | ±0.1 mm |
| Mesh health | `trimesh`: watertight, Euler number, components [verified capabilities: https://github.com/mikedh/trimesh] | Watertight, one component per part |
| Mesh edges | Parse for non-manifold, zero-area, flipped faces | 0 |
| Wall thickness | Ray or sectional check, or `build123d-mcp` printability; trimesh's README does not list this | Min wall ≥ 1.2 mm for a 0.4 mm nozzle [inference] |
| Overhang | Face normal against print direction | Over 45° flagged, needs a support decision |
| Clearances | Boolean intersect of assembled parts | 0 mm³ interference; clearance 0.2 to 0.3 mm on fits [inference, tune per printer] |
| Parametric | Change each key parameter, regenerate | All gates still pass |
| Slice | Slicer CLI | Slices, returns time and material |
| Images | 4 views plus a section, with feature edges | Model reviews; Adam reviews |
| **Physical** | Print, calipers, test fit | Adam reports |

Evidence tiers for 3D must stay separate: script ran, gates pass, slicer passes, printed, fits, works in the robot. Fusion's API works in centimetres [verified for faust's tools; a general API trait from memory], so every Fusion check must convert units; a 10x error is the expected bug.

Prefer in-model assertions where possible, like `assert abs(part.volume - expected) < tol`, as ModelRift recommends.

### 6.4 Printing

Adam's printer is unknown, and the path depends on it.

| Printer type | Route | Note |
|---|---|---|
| Klipper | Moonraker API | Open, documented [verified: https://github.com/Arksine/moonraker] |
| Marlin or similar with a Pi | OctoPrint 1.11.8. `POST /api/files/local` with `print=false` [verified: https://docs.octoprint.org/en/master/api/files.html, GitHub] | Keep `print` at false |
| Prusa | PrusaSlicer 2.9.7 [verified: GitHub] CLI; a forum user notes `-g` is needed for G-code [secondary: https://forum.prusa3d.com/forum/prusaslicer/slicer-command-line-usage/] | Exact flags from `--help` on the installed version |
| Bambu | Starting prints, moving axes and changing temperatures need approved software, including on LAN. Bambu Connect is the path. Developer Mode opens MQTT and FTP but cuts cloud and is unsupported [verified: https://wiki.bambulab.com/en/software/third-party-integration] | Slice with OrcaSlicer 2.4.2 or Bambu Studio, Adam sends. Bambu pressed a fork that restored direct cloud print to be removed in May 2026 [secondary] |

OrcaSlicer CLI: `--slice`, `--load-settings "machine.json;process.json"`, `--load-filaments`, `--export-3mf`. Output is a `.gcode.3mf`. Flags change between releases and are not in official docs, so pin the version and rerun `--help` on upgrades. [secondary: https://printago.io/blog/orca-slicer-cli-reference]

**Safety rule.** Jorah slices, reports time and material, and can upload the file. Adam starts the print. A printer is a heater with moving parts, and a sliced file can still be wrong for the installed filament or nozzle.

---

## 7. 3D: exact steps for the next session

1. Preview and Adam's yes, then install via uv in `~/work/creative/tools/cad`: Python 3.12, build123d 0.13.0, cadquery 2.8.0 (bake-off only), trimesh, manifold3d, a slicer, and `build123d-mcp` 0.3.91. Weights and downloads happen before going into the no-network sandbox. Check if VTK or `cadquery-ocp` wheels exist for arm64 on the chosen Python before committing to it.
2. Write `verify.py spec.yaml part.step part.stl` (section 6.3). Test it with deliberately broken parts: a fused tangent cylinder, an open mesh, a wrong hole. A verifier that has never failed proves nothing.
3. Write `SKILL.md`: restate the spec with numbers; ask about missing dimensions instead of guessing (a named failure in OSWorld 2.0); write the script with named parameters; run; verify; render; show Adam.
4. Run C1 and C2 with build123d. Run the same C1 with CadQuery for a small comparison.
5. Save the learned skill and any verified parts into a small library, `~/work/creative/cad/parts/`.
6. Only then install Fusion. Look for the checkbox. Run F1, F2, F3, with Fusion's add-in reachable by the agent only during those tests.

Effort: 1 to 2 focused sessions for C1 and C2, 1 for Fusion [inference].

---

## 8. Test tasks and acceptance criteria

Use real work wherever possible. "Passed" means the listed evidence exists on disk. Tiers: **S** script ran, **G** automated gates pass, **R** rendered output viewed, **H** human accepted, **P** physically proven.

### Video

**V1, tight cut (bounded MVP).** Adam gives one real talking or screen recording, 5 to 15 minutes. Goal: remove silences, retakes and false starts.
- All gates in section 4.4 pass.
- Adam spots at most 2 bad cuts in a full watch.
- Fewer than 15 minutes unattended on the Mac, CPU-only in the sandbox. If this fails, the recorded time is the evidence for the media-worker decision in section 4.2, not a reason to widen the sandbox quietly.
- Tier H.

**V2, themed long-form edit (the actual goal).** 30 to 60 minutes of raw footage, plus "a video about X with theme Y", target 8 to 15 minutes.
- Strategy confirmed before any cut.
- Output includes final, SRT, chapters, 3 titles, 3 thumbnails, FCP7 XML, licence ledger.
- All gates pass.
- Adam rates it "publishable with at most 10 minutes of my tweaks" within 3 rounds of notes.
- Wall time at most 1x source length on the Mac, excluding Adam's review, on whichever path section 4.2 settles. Record which path it was.
- LLM cost or allowance recorded.
- Tier H.

**V3, benchmark.** First run the Metal and VideoToolbox probe inside a real delegated Claude Code run and record the result. Then a real or concatenated 1-hour 4K file on the Mac, CPU in the sandbox, then on the media-worker path if approved, then on the PC. Record the time per stage in `timings.json`, then replace the estimates in section 4.7. Pass means numbers exist and the run finished with no crash and no timeout. Tier S.

**V4, private upload (phase 2).**
- Upload a 30 s test to a test channel. The response must show `status.privacyStatus=private`.
- Try setting it to unlisted in Studio to resolve the lock question in section 3.1.
- A test must prove the uploader refuses `public` and `unlisted`, and that the token file cannot be read from the sandbox or by Jorah's tools. The token alone can insert a public video, so "no publish path" holds only while nothing else can read it.
- Delete the test video after Adam confirms; Adam does this.
- Tier H.

**V5, reuse (the growth test).** A second, different video in a new session.
- No install step.
- At most 1 clarifying question beyond the theme.
- At least one earlier correction visibly applied, such as "keep pauses after punchlines".
- Cost lower than V2's by 25%, or a stated reason.
- Tier H.

### 3D

Use parts the robotics track actually needs. Confirm exact parts and dimensions with Adam and that track. Default examples below.

**C1, servo bracket.** A bracket for Adam's chosen servo (for example MG996R, from calipers or its datasheet).
- All gates pass; named parameters; STEP, STL and source script in the project folder.
- Parametric check on hole spacing and wall.
- Slices.
- Printed part fits the servo with no reprint or at most one.
- Tier P.

**C2, enclosure.** Two-part snap-fit case for the ESP32 board in use, with camera and USB openings and standoffs. Interference 0 mm³, snap clearance within the spec, assembly images shown, prints and closes. Tier P. ModelRift's tasks are good extra regression tests: an L-bracket and a threaded adapter whose threads are verified as true helices.

**C3, edit by voice or text.** "Make the walls 0.5 mm thicker and the screw holes M4." The changed script passes gates with a clear before and after table. No other dimension moved. Tier G. This proves it is a usable design tool and not a one-shot.

**F1, Fusion access.** Find the checkbox, or install the patched sample add-in. "Create a 10 mm cube". Export STEP. The verifier reads 10.00 mm. Send one request with a foreign `Origin` header and one with no token where a token applies, and record whether each is refused. This resolves the personal-use question. Tier G.

**F2, Fusion same part.** Rebuild C1 in Fusion with named user parameters and a live timeline. Same verifier and same spec. Record time and token use against build123d. Tier G.

**F3, Fusion edit.** Change one user parameter in an existing design, re-export, re-verify, without touching unrelated documents. The active document count must stay at or below Adam's cap. Tier G.

**Decision after F2.** Keep Fusion as main only if it matches C1 on first-pass gates and needs no more than 1.5x the tokens, and Adam prefers its timeline. Otherwise, keep code CAD as main, and use Fusion for Adam's own manual finishing by importing STEP.

---

## 9. Computer use reliability today

- **OSWorld 2.0** (108 long workflows, median 1.6 human-hours, about 318 tool calls for Opus 4.7): Opus 4.8 completed 20.6% with a 54.8% partial score, best at publication. Failure patterns: losing constraints, missing mid-task information, guessing instead of asking, skipping verification. [verified: https://arxiv.org/abs/2606.29537]
- **Later scores:** Opus 5 at 70.6% partial self-reported. An independent Snorkel run of Opus 5 got 68.31% partial and 31.43% strict. Fable 5.1 at 77.9% partial and 41.7% strict, with modified tasks and grading. Opus 5.5 not listed; last updated 30 September. [secondary: https://leaderboard.steel.dev/leaderboards/osworld-2.md]
- **Short-task suite (OSWorld-Verified):** leaders around 85%, with a human baseline near 72% as stated by one tracker. [secondary: https://benchlm.ai/benchmarks/osWorldVerified] Not applicable to a long Resolve or Fusion session.
- **For Fusion:** Qt panels render lazily and some do not appear in the accessibility tree, so reaching them needs pixel clicks that steal focus. [secondary: Adom wiki] Resolve probably behaves the same way [inference]. Guides agree MCP suits repeatable operations and computer use suits visual navigation. [secondary: https://vagon.io/blog/how-to-use-fusion-with-codex-mcp-and-computer-use-guide]
- **In OpenClaw:**
  - The `computer` tool needs a node with `computer.act` or the `cua-computer` plugin. Peekaboo is the macOS default.
  - On the MCP tool path, recording and file transfer are unavailable and control ends with the run.
  - The CUA daemon runs unrestricted, with authorization done at the Gateway.
  - OpenClaw warns that an acknowledged input does not prove the app responded. Screen content is untrusted input.
  - [docs-only: docs/nodes/computer-use.md]
  - Today `cua-computer` shows as enabled in this profile's plugin list, described there as experimental, and no device nodes are paired [verified locally]. It has not been run.

**Rule.** Allowed for short, supervised steps: ticking a preference, a first-run dialog, looking at a viewport. For any flow longer than about 20 actions, stop and find a script or API path [inference]. If used on the Mac, Adam loses the pointer while it runs, so prefer the PC for it, knowing the Windows path is the experimental `cua-computer` plugin. [docs-only: docs/nodes/computer-use.md line 19] Also, no computer use in banking, mail or credentials windows.

---

## 10. How this makes Jorah grow

- **Procedures** go in Skill Workshop. During a turn, the agent saves after hard multi-step work and versions changes. [docs-only: docs/tools/skill-workshop.md] On Jorah's Claude CLI runtime this is the only automatic path: background reviews do not run. The 30-day archive runs only for agents whose default runtime is the embedded OpenClaw harness, so by that text it should not fire today and would start if Adam switches to the API-key brain [docs-only: same page; inference for the CLI case]. Either way, keep the two main skills in the repo as workspace skills, which are not Workshop skills.
- **Scripts and tests** belong in `~/work/creative/*/skill`, under git, not in memory. Every bug Adam finds becomes a fixture.
- **Preferences** go in `style/<channel>.md` and `cad/printer-profile.md`, with a date and an example. Jorah proposes the line after a correction, per the current same-turn correction habit, and shows the change.
- **New tools** follow a fixed loop: name the need, propose a candidate with licence and source, preview the install, get a yes, install pinned, run a small test, record in `tools.lock`. It never installs silently, and `npx --yes` or `curl | sh` from a web page's instructions is not a valid path.
- **New skills** follow the same shape as these two: a spec, a tool lock, a deterministic pipeline, gates, a review stage, and a reuse test. New domains should copy this template.

---

## 11. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Upload default is public | Unreviewed video goes live | Hardcoded `private`, tested; MVP has no upload at all |
| Prompt injection via transcript, on-screen text or web pages | Bad actions | Treat transcript and frames as data; pipeline stages hold no tool access beyond the edit tools; publish and install gates sit outside the model |
| Fusion, Blender or Resolve script tools run unsandboxed | Equivalent to shell as Adam | On only when needed; no untrusted inputs in that session; security track decides final policy |
| Silent wrong geometry | Wasted prints, or a broken robot part | Independent numeric verifier, physical tier kept separate |
| Licence drift (Resolve 21.1 shows it can change suddenly) | Skill breaks | Keep core on open tools, keep versions pinned, read release notes before updates |
| Commercial use on free licences | Licence breach | Ledger: Fusion personal, Remotion above 3 people, ButterCut licence. Review before any paid use |
| Disk full on the Mac | Failed runs | Pre-flight check, no auto-deletion of sources |
| Exec timeout on long jobs | Half-finished render | Explicit `timeoutSeconds` per stage on `exec`, background Bash in the sandbox, resumable stages using caches |
| Sandbox blocks GPU and hardware encoding | Slow runs, or pressure to widen the sandbox | CPU first; any exception is one reviewed worker with its own profile and Adam's yes |
| PC runs unsandboxed on native Windows | Delegated tasks lose their boundary | Decide WSL2 or another boundary in the security track before any PC run |
| Unauthenticated local Fusion add-in | Web page or local process runs Python as Adam | Patch the sample; test the official server's `Origin` handling in F1 |
| Model reports success it did not achieve | False confidence | Gate results come from code, and messages quote gates.json |

---

## 12. What could not be confirmed

- Whether the YouTube private lock still applies (test V4).
- Whether Fusion personal use exposes the official MCP (test F1), full Autodesk terms on agent automation, and macOS 27 support.
- Real pipeline timings on this Mac (test V3) and anything on Adam's PC.
- Resolve Studio's EU price and whether the sale reaches EU buyers, and OTIO import in the current version.
- Slovak transcription quality and whether Adam will edit in Slovak or English.
- Suno commercial terms, Pixabay music terms, Epidemic and Artlist list prices from vendor pages, Fusion prices from an Autodesk page (403).
- Any independent quality measure for LLM video cuts or for Claude in Fusion. None found.
- Whether a 1-hour edit fits within Max allowance limits.
- Whether the sandbox probe result repeats inside a real Claude Code run, CPU speeds on this Mac, the exact `mach-lookup` names VideoToolbox needs, and NVENC or CUDA under the WSL2 sandbox.
- Whether the official Fusion server checks `Origin`, and whether node-published MCP tools reach a Claude CLI agent.
- Shotcut's current import formats from its own manual.

## 13. Questions for Adam

1. What raw footage will this mostly be: talking head, screen recording, gaming, vlog, robot builds? In what language, from what camera or OBS settings? One sample would settle most of this.
2. Is there a test YouTube channel, and should API upload exist at all, even private only?
3. Fusion: personal use or paid? Is the business aim near enough to need commercial licensing now?
4. Is a one-time Resolve Studio purchase worthwhile, or is manual Resolve free enough for finishing? The $236 sale reportedly ends 20 November 2026. Does anything make Shotcut preferable, given it needs its own export?
5. Which 3D printer, and which servos and ESP32 boards for the first parts?
6. May audio ever leave the machine for transcription if local quality is poor?
7. Which music source: Audio Library shelf or a paid licence?
8. If CPU runs on the Mac are too slow, may one reviewed media worker run outside Claude Code's sandbox under its own stricter profile?

---

## Verification

Independent check on 2026-11-02. I read primary sources and bundled docs directly rather than following this file's links on trust, and ran read-only commands on this Mac. The only thing built was a small probe binary in the session scratchpad. Nothing was installed, and no config or gateway was touched. The shared search budget ran out late on, so the last checks were direct page reads.

### Recommendation after corrections

The core holds: EDL plus ffmpeg, local transcription, no Resolve or computer use at the core, no publishing in the MVP, code CAD before Fusion, one independent CAD gate. Five parts changed:

1. **Execution on the Mac.** The sandbox blocks Metal and VideoToolbox, so the MVP is CPU-only and the 1-hour case needs a decision (section 4.2).
2. **V3 transcriber.** `faster-whisper` on CPU is the default on both machines. `mlx-whisper` moves to the worker path.
3. **NLE handoff.** FCP7 XML for Resolve, not FCPXML for Resolve and Shotcut.
4. **C3 Fusion fallback.** Patched sample only, with `ndoo` as runner-up.
5. **Pipeline driver.** Plain Python, not Lobster, for the MVP.

### Checked

| # | Claim | Result | Source |
|---|---|---|---|
| 1 | Resolve 21.1 moved Python scripting to Studio | Held | Blackmagic readme; Puget blog |
| 2 | Studio $236, promotion status unknown | Corrected: 20% sale to 20 November 2026 | Blackmagic page; Newsshooter (secondary) |
| 3 | Resolve Windows minimum "32 GB for 4K" | Wrong for x64: 16 GB, 32 GB with Fusion page. 4K wording is Windows on Arm only | Blackmagic readme, read raw |
| 4 | Resolve API names and `-nogui` | Held, host of the docs copy unconfirmed | wiki.dvresolve.com |
| 5 | `videos.insert` quota, 256 GB, public default, notify default | Held | YouTube docs |
| 6 | Quota table, buckets, history | Held | YouTube docs |
| 7 | Private-lock conflict | Reproduced, still unresolved | `videos.insert`; revision history (first 100k characters) |
| 8 | `youtube.upload` cannot edit existing videos | Now verified. Added: it can still insert public | `videos.update` page |
| 9 | OAuth 7-day and six-month token rules | Held | Google OAuth docs |
| 10 | AI Act Article 50(4) date unknown | Resolved: applies since 2 August 2026 (secondary; Official Journal not read) | Goodwin alert |
| 11 | Homebrew ffmpeg may lack subtitles, check and fall back | Corrected: dependency list shows no libass or freetype, so pick `ffmpeg-full`; keg-only | formulae.brew.sh JSON |
| 12 | Versions of mlx-whisper, faster-whisper, scenedetect, OTIO, MoviePy, build123d, CadQuery, build123d-mcp | Held | PyPI, GitHub API |
| 13 | auto-editor 29.3.1 is current | Wrong: 31.8.0; PyPI is stale | GitHub releases, Homebrew |
| 14 | OTIO is the FCPXML export layer | Wrong: bundled adapter is FCP7 XML; FCPX adapter is separate, from 2023 | PyPI metadata, adapter READMEs |
| 15 | FCPXML lets Adam finish in Shotcut | No support found; forum says no EDL import either (secondary) | forum.shotcut.org |
| 16 | video-use stars, licence, commits, Scribe need, rules to remove | Held; PRs confirm no merged local path; filler warning added | GitHub API, its SKILL.md |
| 17 | Scribe v2 $0.22/hour | Held | ElevenLabs |
| 18 | Remotion free up to 3 employees, 5.0 change | Held | Its LICENSE.md |
| 19 | Claude prices and image tokens, and the arithmetic | Held, cache read $0.20/M confirmed; source now primary | platform.claude.com pricing and vision |
| 20 | Pipeline runs with hardware acceleration in delegated sandbox | **Refuted by probe**, with the limit stated in section 4.2 | Local probe; sandbox-runtime source; Claude Code 2.1.300 binary strings |
| 21 | Native PC path keeps the same boundary | Refuted: native Windows runs unsandboxed | Claude Code sandboxing docs |
| 22 | `exec` timeout advice covers long jobs | Partly: true for `exec`, wrong tool for the sandbox path | exec.md; env-vars docs; acp-agents-setup.md |
| 23 | Lobster fits the pipeline | Corrected: in-process in Gateway, disabled in sandboxed contexts | lobster.md |
| 24 | Workshop would archive a monthly skill | Corrected: cleanup is embedded-harness only | skill-workshop.md; self-learning.md |
| 25 | MCP on the Claude CLI runtime is untested guesswork | Upgraded to documented for `mcp.servers`; node path still open | cli-backends.md |
| 26 | File Transfer 16 MB, `mcp doctor`, `nodeHost.mcp.servers`, `music_generate`, exec 1800 s | Held | Bundled docs |
| 27 | Telegram 50 MB from memory | Verified; 2000 MB with local server | Bot API docs |
| 28 | Puget M1 Max 91.6, RTX 5070 132.4 fps | Corrected: 91.64 and 130.72, read directly | Puget compare page |
| 29 | Fusion personal terms and API unaffected | Held; page predates MCP. Revenue cap and renewal remain secondary (Autodesk eligibility pages 403) | Autodesk help |
| 30 | Official MCP endpoint, preference path, no sign-in, subscriber wording | Held; personal use remains unverified | Autodesk help and APS blog; Adom wiki |
| 31 | `FusionMCPSample` is the best fallback | **Refuted as shipped**: no auth, wildcard CORS, no Content-Type check | Its `server/mcp_server.py` |
| 32 | faust and ndoo details | Held; faust now 142 stars | READMEs, GitHub API |
| 33 | `build123d-mcp` security wording | AST check, restricted builtins, 30 s timeout and the container advice confirmed. "Not a hard boundary" is this file's paraphrase of its sandbox-escape section | Its security.md |
| 34 | Hunyuan3D licence exclusion | Held, and extended to 2.1 and to output | LICENSE files |
| 35 | TRELLIS.2 MIT, Linux, 24 GB | Held | Its README |
| 36 | Blender Lab MCP; community server stars | Lab held; stars corrected to about 33k, repo renamed | blender.org, GitHub API |
| 37 | Bambu Connect requirement and Developer Mode | Held | wiki.bambulab.com, read raw |
| 38 | OSWorld 2.0 and later scores | Held; no Opus 5.5 entry | arXiv; Steel leaderboard (secondary) |
| 39 | ModelRift numbers, Text2CAD-Bench, Onshape caps | Held | Their pages |
| 40 | Audio Library Content ID wording | Held | YouTube Help |
| 41 | Computer use details in OpenClaw | Held; Windows and Linux plugin is experimental | computer-use.md, plugin list |
| 42 | Release versions: FreeCAD, OrcaSlicer, PrusaSlicer, OctoPrint, OpenSCAD, ffmpeg | Held | GitHub API, ffmpeg.org |
| 43 | Mac facts: 10 CPU cores, 32 GPU cores, Python 3.13.3, no ffmpeg or uv, free disk | Held; disk now 181 GiB | Local commands |

### Could not confirm

Marked `[unverified]` in place: Fusion MCP on personal use; Autodesk's legal terms on agent automation and macOS 27 support (403 on those pages); Fusion and Resolve EU prices; the private-upload lock; everything in section 12.

### Not re-checked

Left as written, with their original labels: thumbnail specs, encoding table, API terms section 9.1, the audit page, Epidemic, Artlist, Pixabay, CapCut, ButterCut pricing, Moonraker, OctoPrint endpoint, PrusaSlicer and OrcaSlicer CLI flags, trimesh capabilities, Text-to-CadQuery and the other papers named only as secondary, drift figures from Cutback, motionbox and laozhang, and all time estimates in section 4.7, which remain inference until V3.
