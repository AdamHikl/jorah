# ADR 0013: Video studio in the HUD, and Jorah on YouTube

**Status:** decided on 2026-11-28. Adam: "you have my yes", which covers every choice marked **(yes needed)** below as design. Each install, service, config change, schedule and sign-in is still previewed for its own yes when it is built.

The inputs are Adam's own asks:

- **2026-11-27:** "give jorah tools to create edit and upload videos for my youtube channel". About 8 minutes per video, with Adam on camera reading a script.
- **2026-11-28:**
  - 4K.
  - Video and sound files come by SD card onto the PC.
  - A UI mode in the HUD instead of a separate studio page.
  - Recording with the Blackmagic Camera app on iPhone.
  - Jorah manages YouTube Studio and analyzes each video's analytics.
- **2026-11-28, later:** "HEVC, apple log, 30fps, the sound will be recorded on mac, I will connect an external mic to it, you can make integration into hud so that it works together with the teleprompter".

A silent 2-minute 4K mock was rendered on the PC the same day. It used h264_nvenc and took 95 s for 3,600 frames. Adam's verdict on its quality: "it's good".

**Question:** M12 and `05` section 8 planned an edit pipeline with an SFTP inbox, a review web page and no upload path. Adam now wants:

- 4K footage from an SD card.
- A Studio mode in the HUD.
- Jorah running the channel: uploads, Studio edits and analytics.

This ADR answers:

- What replaces those three rules?
- Which open-source parts do we build on?
- Where does each permission sit?

## Decision

### What stays from M12 and `05` §8

- **The pipeline shape from `browser-use/video-use`.** It is MIT-licensed, has 31.7k stars, and its last commit was on 2026-10-08 [verified: GitHub API, 2026-11-28]. The steps are:
  1. Transcribe.
  2. Pack.
  3. The model reasons over the transcript.
  4. A phrase-ID EDL.
  5. Compile.
  6. Render.
  7. Self-check.

  We read every file at a pinned commit and port it (roadmap 12.2). The port drops its ElevenLabs Scribe call, its `.env` key prompt and its `npx --yes`.
- **Audio stays on the PC.** Transcription uses local faster-whisper. WhisperX comes in only if the word timing isn't good enough.
- **Kept as planned:**
  - the tool lock (`05` §8.3);
  - the gates (§8.7);
  - the `jorah-media` worker with `PrivateNetwork=yes`;
  - the OpenTimelineIO handoff to Resolve;
  - the AI-disclosure checklist (§8.10).

### What changes

1. **Intake by SD card, not SFTP.**
   - Adam puts the card in the PC. In Windows Explorer, they copy the take folder to `\\wsl.localhost\jorah\srv\jorah-media\incoming\`, which they can pin in Quick Access.
   - Nothing in WSL reads the card or `C:`. Automount stays off.
   - `jorah-ingestd` waits until the files stop growing. It then:
     - hashes each file (SHA-256);
     - moves the files read-only into the spool;
     - reports what it found.
   - The report lists each clip's length, codec, resolution, frame rate, color (Rec.709 or Apple Log) and audio tracks. A field it can't read shows as unknown.
   - Ingest refuses a take when free disk space is below three times the take's size.

2. **Blackmagic media.**
   - **Adam's format:** HEVC in `.mov`, Apple Log, 30 fps. Ingest also accepts ProRes and Rec.709, but they are not the planned path.
   - Apple Log is converted with Apple's published LUT through ffmpeg `lut3d`. Adam downloads the LUT, and its SHA-256 goes in the tool lock. A take tagged Apple Log with no LUT in place stops and says so.
   - When the clip's metadata doesn't say Apple Log or Rec.709, ingest uses Adam's stated default (Apple Log) and marks the color as assumed, not read.
   - **Sound comes from the Mac,** from an external mic, not from the card (point 2a).
   - The Mac WAV is synced to the iPhone's scratch audio by cross-correlation. This is our own numpy code, about 100 lines, with `bbc/audio-offset-finder` (Apache-2.0) as the reference.
   - A take is paired with its WAV by start time first, then by the correlation peak. A sync with low confidence, or a clip with no WAV, stops and asks Adam.

2a. **A teleprompter in the HUD records the sound.**
   - Studio mode has a teleprompter: the script scrolls at Adam's speed on the Mac, near the iPhone's lens.
   - While it runs, the HUD records the external mic to a 48 kHz WAV. The Mac's microphone permission already exists for voice.
   - The HUD saves the WAV with a sidecar that says:
     - the start time;
     - the mic's name;
     - which script line was on screen at each moment.
     The rough cut can use those line times, alongside the transcript.
   - The HUD sends the WAV and sidecar to the PC's intake over the tailnet, on the same tailnet-only endpoint as the proxies (point 4). This needs no copy to the card. Until that endpoint exists, Adam copies the WAV into the take folder by hand.
   - Adam presses record on the iPhone. The HUD doesn't control the Blackmagic app.

3. **4K output.**
   - 3840x2160 at 30 fps, unless the source says otherwise.
   - Encoded with h264_nvenc, which the mock proved on the RTX 5070, or with hevc_nvenc.
   - Tagged BT.709.
   - Review uses 1080p proxies.

4. **Studio mode in the Mac HUD, with no review web page.** This is a mode like Drive mode (ADR 0012), in `clients/mac-hud`. For each project it shows:
   - the intake status;
   - the script;
   - the transcript, with the cut marked phrase by phrase. Adam can untick a phrase to cut it, like `mli/autocut`'s transcript edit.
   - the proxy player, with time-coded notes;
   - the gate results;
   - the upload pack.

   How it works:
   - **Proxies** stream from a tailnet-only endpoint on the PC. This replaces `jorah-review` (roadmap 12.5) and has the same authentication need. Serving a new port is a config change **(yes needed)**.
   - **Approvals** are ordinary cards answered in the HUD (ADR 0007).
   - **Adam's hand edits** are saved apart from Jorah's EDL, so Jorah's next pass keeps them. The idea comes from OpenFilm's `overrides`.

5. **Graphics.**
   - HyperFrames (`heygen-com/hyperframes`) draws the animated overlays and explainer scenes. It is Apache-2.0, has 91.6k stars, and gets commits daily [verified: GitHub API, 2026-11-28].
   - Headless Chromium renders it inside `jorah-media`, with no network and `HYPERFRAMES_NO_TELEMETRY=1` set. Its CLI telemetry is on by default.
   - Its skills are read and vendored, never installed live with `npx skills add`.
   - **A spike comes first:** render the 2-minute mock in HyperFrames at 4K on the PC. Keep the PIL renderer from the mock if HyperFrames:
     - needs the network;
     - is not deterministic; or
     - is far slower than the 95 s the PIL renderer took.
   - The PIL renderer moves into the repo either way, for title cards and thumbnails.

6. **A leak gate before anything leaves the PC.**
   - **What gets checked:** OCR of frames, every 0.5 s and at each scene change, plus the transcript.
   - **What it is checked against:**
     - gitleaks (`--redact`);
     - a private denylist kept outside the repo, in `~/.jorah-private`, and never committed. It holds the tailnet name, IP addresses, account and user names, chat ids, emails and keys.
   - **On a hit:** the upload pack stops and shows the time code.
   - **OCR engine:** tesseract (an Ubuntu package) first. Switch to RapidOCR (Apache-2.0, ONNX weights) if the planted-secret fixtures show tesseract missing small terminal text.
   - **A failed gate is final for that render.** A failed gate stops what is behind it (`CLAUDE.md`).

7. **YouTube, in three phases.**

   A new plugin, `plugins/jorah-youtube`, built like `jorah-google`:
   - It calls a pinned CLI built on google-api-python-client (Apache-2.0), installed under `/opt/jorah-tools`.
   - The token file is readable only by the `jorah` user, never by the sandbox.
   - Every tool marks the chat for jorah-guard.
   - It gets its own Google Cloud project, so its audit and quota stand alone.
   - Adam does every sign-in in a Terminal attached to no agent.

   `gog` can't do this job: its YouTube commands are read-only Data API calls, with no upload and no Analytics API [verified: gogcli README, 2026-11-28].

   - **Phase A, read (yes needed).**
     - **Scopes:** `youtube.readonly` and `yt-analytics.readonly`.
     - **Reads:** the channel, its videos and per-video analytics: views, watch time, average view duration, average percentage viewed, the retention curve, traffic sources and subscribers gained.
     - **Impressions and click-through rate:** only if the Reporting API provides them. Until that is checked, they show as unknown.
     - **The upload pack:** Jorah builds it in an outbox that Adam opens from Windows Explorer. It holds:
       - the final file;
       - 3 title options;
       - a description with chapters;
       - tags;
       - captions as `.srt`;
       - 3 thumbnails;
       - the disclosure checklist.

       Adam uploads it in Studio, as M12 planned.
   - **Phase B, Studio edits (yes needed).**
     - **Scope added:** `youtube.force-ssl`.
     - **Edits:** title, description, tags, chapters, thumbnail, captions and playlists.
     - **On a private video:** an edit Adam typed in chat may pass the second check (`13-autonomy.md` 3a), as a new card kind.
     - **On a public, unlisted or scheduled video:** always a card, with a before/after diff.
     - **Visibility changes** (public, unlisted, scheduled) are always cards. The second check already refuses a publish before the model sees it.
   - **Phase C, upload (yes needed).**
     - **Scope added:** `youtube.upload`.
     - **The uploader** hardcodes `private` and `notifySubscribers=false`, and refuses any other value (tested), as in `05` §8.9.
     - **Each upload is a card,** at least until a later ADR says otherwise.
     - **A test comes first.** Before Jorah gets the upload tool, Adam runs the private-only uploader once, with a 30 s test to a test channel, then tries to set that video to unlisted in Studio. The question it answers: are uploads from an unaudited API project locked to private?
       - Google's own pages disagree [verified: the videos.insert reference pages, 2026-11-28].
       - Issue #86 on `porjo/youtubeuploader` reports such a lock.
     - **If uploads are locked,** Adam either applies for the YouTube API audit or keeps uploading by hand. Jorah never works around the lock.
   - **Never.**
     - Delete a video, comment, playlist or caption. No tool for it exists; Adam deletes in Studio.
     - Reply to comments.
     - Change channel settings, monetization or the account.

8. **Analytics and growth notes.**
   - **Daily snapshot:** every video's numbers go into a private store on the PC, not in the repo. The daily timer is a schedule, so it waits for Adam's yes.
   - **Per-video report** at 48 h, 7 days and 28 days. It covers:
     - retention against the EDL, showing which segment lost viewers;
     - the title and thumbnail;
     - traffic sources.
   - **Monthly growth notes** keep three things apart:
     - what the channel's own data shows [verified];
     - what YouTube's creator docs say [verified: with a link];
     - Jorah's guesses [inference].
   - Nobody outside YouTube knows the algorithm. Jorah learns from the channel's data, not from growth-hack posts.

## Open-source parts, checked 2026-11-28

| Part | Project | Licence | Use |
|---|---|---|---|
| Edit pipeline | `browser-use/video-use` | MIT | Port after reading every file |
| Transcription | `SYSTRAN/faster-whisper` | MIT | Default, local. WhisperX (BSD-2) for alignment only if needed |
| Transcript editing | `mli/autocut` | Apache-2.0 | Idea for the Studio transcript: untick a phrase to cut it |
| Silence baseline | `WyattBlue/auto-editor` | Unlicense | Optional comparison, already in the lock |
| NLE handoff | `AcademySoftwareFoundation/OpenTimelineIO` | Apache-2.0 | FCP7 XML for Resolve, already in the lock |
| Graphics | `heygen-com/hyperframes` | Apache-2.0 | Overlays and explainer scenes, after the spike |
| Audio sync | `bbc/audio-offset-finder` | Apache-2.0 | Reference for our cross-correlation |
| OCR | tesseract, then `RapidAI/RapidOCR` if needed | Apache-2.0 | Leak gate |
| YouTube | `googleapis/google-api-python-client` | Apache-2.0 | Analytics, Studio edits, upload |
| Analytics shapes | `parafoxia/analytix` | BSD-3 | Reference only |
| Inspiration | `openfilm/openfilm` | MIT | Hand edits kept apart from agent code. Its `frame(t)` contract matches the mock. Too young to adopt: created 2026-10-04, at v0.4.1 |

**Rejected:**

- **Remotion:** source-available, with a company licence above 3 employees. HyperFrames covers the same ground and can port Remotion projects.
- **MoviePy** for 4K long form (`05` §8.10).
- **BaoCut:** a source-available community licence.
- **whisper-timestamped:** AGPL.
- **Cloud transcription such as ElevenLabs Scribe:** audio stays on the PC.
- **OpenClaw YouTube skills on GitHub and ClawHub:** 1 to 120 stars and unvetted, so ideas only.
- **FFmpeg MCP servers:** the pipeline calls ffmpeg directly.

Every install follows the tool lock:

- wait 7 days after release;
- pinned versions and hashes;
- Adam's yes;
- model weights only in non-executable formats.

## Why this shape

- **The plan already existed and was researched.** The new asks change intake, review and upload, not the pipeline.
- **Copying from the SD card in Explorer adds no new hole.**
  - Adam's Windows account already reaches the distro's files through `\\wsl.localhost`.
  - Nothing in WSL gains access to Windows drives.
- **Studio mode in the HUD reuses what exists:** the paired, authenticated HUD and its card answers, instead of a second web app with its own login.
- **The phases put each scope behind evidence:** read first, edits next, upload last, and only after the lock question is answered.
- **HyperFrames over Remotion:**
  - it has an OSI licence;
  - it is already one of video-use's overlay engines;
  - it ships agent skills.

  The spike guards against speed and network surprises.

## Risks left

- **Disk.** 4K HEVC takes are far smaller than ProRes, which runs around 5 GB a minute for ProRes 422 HQ [inference, from Apple's published data rates]. The free-space check at ingest limits the damage either way.
- **Clocks.** Pairing a take with its WAV by start time assumes the iPhone's and the Mac's clocks agree within a minute. Both set their time from the network. The correlation peak decides the exact offset.
- **GPU transcription.** faster-whisper runs on CTranslate2, which is untested in WSL on an RTX 50-series card. The fallback is CPU, which is slower.
- **Fillers.** Whisper may drop fillers that need cutting (`05` §8.6 point 4). This gets tested on Adam's first real take.
- **HyperFrames moves fast.** The 7-day rule and a pinned version hold it still.
- **The `youtube.force-ssl` token can technically delete.** Only the tools refuse. The token stays unreadable from the sandbox and from Jorah's other tools.
- **OCR limits.** The leak gate checks only what OCR can read, so blurred or tiny text can slip through. Adam still watches the final cut before publishing.

## Undo

Undo goes phase by phase:

- Revoke the token in Google Account > Security > Third-party access.
- Remove the plugin from the config.
- Disable the worker and ingest services.

Only Adam deletes footage on the PC.

## Related

- M12 in `10-roadmap.md`, amended by this ADR.
- `05-growth-and-skills.md` §8.
- ADR 0007: the HUD answers cards.
- ADR 0012: Drive mode, the model for Studio mode.
- `13-autonomy.md` 3a: the second check.
