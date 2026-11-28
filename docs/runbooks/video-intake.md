# Video intake: SD card to spool (jorah-ingestd)

Issue #25, ADR 0013 points 1 to 3. The service is `services/jorah-ingestd` (its README lists the
parts). It runs on the PC as `jorah-media`, a system user with no network, no login and no sudo.

```text
SD card ── Explorer ──> \\wsl.localhost\jorah\srv\jorah-media\incoming\<take>\
                          │  30 s with no change
                          v
          spool/<take>/media/   read-only copies, SHA-256 in take.json
          spool/<take>/take.json  report, color, sound pairs, questions
          proxies/<take>/*.proxy.mp4   1080p H.264, Rec.709
          state/status.json     what the HUD and Jorah read
```

Below, `<pc>` stands for the ssh command and target in `docs/runbooks/jorah-on-pc.md`. Run root
steps in a Terminal attached to no agent.

## 1. Install (Adam, once)

A build session first deploys the reviewed files from `main`:

```bash
scripts/pc/deploy_reviewed.py deploy services/jorah-ingestd deploy/jorah-ingestd.service scripts/pc/install-ingestd.sh config/video/tools.lock
```

1. Dry run:

   ```bash
   ssh -t <pc> wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-ingestd.sh --dry-run
   ```

   Expected:
   - `files, tools and uid 1104: ok (numpy 1.26.4, ffmpeg version 6.1.1...)`;
   - `systemd-analyze verify: ok`;
   - a line on the NVENC test encode;
   - the `would:` lines;
   - `Dry run: nothing written.`

   A `MISSING:` line stops it. `setfacl` comes from the `acl` package, so `apt-get install acl`
   fixes that one, on Adam's yes.
2. Install: the same command without `--dry-run`. Expected:
   - the two `incoming acl:` lines (`user:jorah-media:rwx`, and the default);
   - the `check` lines, with no `FAIL`. Expected `WARN`s: the root folder isn't writable to
     jorah-media, the LUT is missing, and maybe free space;
   - `active`;
   - `Done. Status as jorah:`, then a line with `updated` and the free space.

   A `FAIL` in the check stops it before the service is installed.

## 2. The Apple Log LUT (Adam, once)

Apple Log proxies wait until a LUT is pinned. Rec.709 clips don't need one.

1. Download Apple's Apple Log LUT package (Apple's developer downloads, signed in with Adam's
   Apple ID) and unpack it on the Mac or Windows.
2. In Explorer, copy the Apple Log to Rec.709 `.cube` file to `\\wsl.localhost\jorah\tmp\`.
3. Pin it:

   ```bash
   ssh -t <pc> wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-ingestd.sh --pin-lut /tmp/<file>.cube
   ```

   Expected:
   - the file and its SHA-256;
   - while `config/video/tools.lock` has no LUT hash, a line to record there;
   - `Pinned.`, then the check with `ok   Apple Log LUT (ok)`.

   It stops on a link, a file that isn't a 3D `.cube`, or a hash other than the one in the lock.
4. Send the printed lock line to a build session, which commits it. From then on, only that file
   can be pinned. Any Apple Log proxies that were waiting are made within a minute.

The LUT lives at `/srv/jorah-media/luts/apple-log-to-rec709.cube`, owned by root. Its hash is in
`/etc/jorah-media/ingest.json` (`lut_sha256`) and in the lock.

## 3. Recording and bringing in a take

1. **Blackmagic Camera on the iPhone:** HEVC, Apple Log, 30 fps, 4K. Keep the iPhone's own sound
   on. The scratch audio is what syncs the Mac's WAV.
2. **Mac:** record the external mic to a 48 kHz WAV, started before the iPhone and stopped after
   it. Until the HUD teleprompter (ADR 0013 point 2a) exists, any recorder that writes WAV works. A
   clap at the start helps but isn't needed.
3. Put the clip and its WAV in one folder on the SD card, named for the take (`openclaw-security-1`).
   A sidecar next to the WAV (`take-1.json` for `take-1.wav`) is read too; see "Sidecar" below.
4. On the PC, in Explorer, copy that folder into
   `\\wsl.localhost\jorah\srv\jorah-media\incoming\`. One folder is one take. Loose files there
   form a take of their own, named `loose-<UTC time>`.
5. About 30 s after the copy ends, the folder disappears from `incoming\` and appears under
   `spool\`. The proxy follows a little later.

Check it as jorah:

```bash
ssh -t <pc> wsl -d jorah -u jorah -- python3 -I /opt/jorah/services/jorah-ingestd/bin/jorah-ingestd status
```

Expected for a good take:

```text
updated 2026-11-28T..., free 812.3 GB
  openclaw-security-1: ready, 1 clip(s)
```

The proxies are at `\\wsl.localhost\jorah\srv\jorah-media\proxies\<take>\` and open in any player.

## 4. Statuses, questions and notes

| Status | Meaning |
|---|---|
| `incoming dir:<name>: settling` | still copying, or under 30 s since the last change |
| `incoming ...: free space ...` | under 3 x the take's size free. The files stay; it tries again each 10 s |
| `working` | proxies are being made |
| `waiting` | an Apple Log proxy needs the LUT (part 2) |
| `ask` | a question below needs Adam |
| `failed` | a proxy failed twice (NVENC, then libx264); the reason is in `take.json` |
| `ready` | every clip has a proxy, and there are no questions |

| Question (`?`) | What to do |
|---|---|
| `<clip>: unreadable (...)` | copy the clip again from the card, into the same folder name |
| `... has the same name as a file in this take but different content` | the folder name was used for another take: rename the folder and copy it again |
| `<clip>: tagged rec709, but the stated format is apple_log` | check the Blackmagic setting; tell Jorah which it is |
| `<clip>: no WAV in this take` | copy the Mac's WAV into the same folder name |
| `<clip>: low sync confidence (...)` | the WAV is likely from another take, or the scratch audio was off |
| `<clip>: the WAV drifts N ms ...` | the two clocks drift apart over the take; tell Jorah, since the edit has to stretch the WAV to match |
| `<clip>: the clip has no scratch audio to sync against` | turn the iPhone's sound on for the next take |

Notes (`-`) need nothing:
- a clip that isn't HEVC or 30 fps;
- an HLG or PQ clip, whose proxy isn't tone-mapped;
- `originals left in ...`: the service couldn't delete the card copies from `incoming\`. Delete the
  folder in Explorer once the take is `ready`.

Copying the same file again with the same bytes is harmless: it is dropped. A failed proxy is
tried again when the clip is copied in again.

## Sidecar

For the HUD teleprompter (ADR 0013 point 2a): a JSON file under 1 MB next to the WAV, named for it
(`take-1.json` or `take-1.wav.json`), or any `.json` in the take whose `audio_file` names it. Only
these keys are read:

```json
{
  "schema": "jorah-hud/take-audio@1",
  "audio_file": "take-1.wav",
  "start_time": "2026-11-28T10:00:00.250Z",
  "device": "the mic's name",
  "sample_rate": 48000,
  "take": "openclaw-security-1",
  "lines": [{"line": 1, "t": 0.0}, {"line": 2, "t": 4.8}]
}
```

`start_time` must carry a time zone. It wins over the WAV's own time. `lines` gives the moment each
script line came on screen, in seconds from the start of the WAV.

## 5. The test pass (once, after the install)

Each is a separate tier; passing one proves nothing about the next.

1. **Tests on the PC, as jorah:** `cd /opt/jorah && python3 -m unittest discover -s
   services/jorah-ingestd/tests`. Expected: `OK`, with `RealFfmpegTest` run, not skipped. It prints
   the encoder it used.
2. **NVENC under the unit's sandbox:** after a take, `take.json` shows `"encoder": "h264_nvenc"` and
   no `fallback_because`. If it fell back, the reason says which setting blocked CUDA.
3. **Explorer's writes:** copy a test folder in. Expected: the files are owned by `jorah`, the folder
   disappears from `incoming\` with no `originals left` note, and `getfacl` on the new folder shows
   `user:jorah-media:rwx` with an effective `rwx`.
4. **Adam's 30 s take (the #25 device gate):** the take ends `ready`. In `take.json`:
   - each file's `sha256` matches `sha256sum` of the card copy;
   - the clip's `color` is `apple_log` with basis `tag` or `metadata`, not `assumed`;
   - the pair is `ok`, with `offset_s` and `drift_ms`;
   - the proxy plays, with sound, and looks like normal Rec.709.
5. **creation_time:** compare the clip's `creation_time` with when recording started and stopped,
   and record whether the iPhone writes the start or the end. Pairing by time assumes the start.

## Undo and removal

```bash
ssh -t <pc> wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-ingestd.sh --undo
```

That removes the service only. The footage stays in `/srv/jorah-media`. Removing everything, on
Adam's yes only, since it deletes the footage: `rm -rf /srv/jorah-media /etc/jorah-media` and
`userdel jorah-media`.
