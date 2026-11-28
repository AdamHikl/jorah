# jorah-ingestd: Jorah's media intake

Takes in the takes Adam copies from the SD card into `/srv/jorah-media/incoming/`, as the system
user `jorah-media`. It has no network and never runs as root. Adam's steps, the install and the
test are in `docs/runbooks/video-intake.md`. The decision is ADR 0013, and the issue is #25.

- `jorah_ingestd/scan.py`: one take per top-level folder in `incoming/`, and one for all loose
  files together. A take waits until no file has changed size or time for `settle_s` (30 s).
  Links and special files are never followed, and Finder or Windows junk (`.DS_Store`, `._*`,
  `:Zone.Identifier`, `.Trashes`) is set aside.
- `jorah_ingestd/spool.py`: for each take:
  1. refuses it while free space is under three times its size (it tries again later);
  2. copies each file to `spool/<take>/media/`, hashing it (SHA-256) on the way, then makes the copy
     read-only;
  3. takes nothing that changed while it was copied, and deletes an original only after that;
  4. writes `spool/<take>/take.json` (`jorah-media/take@1`), with the files, their hashes, their
     `ffprobe` reports, the color, the sound pairs, and any questions or notes.

  A file with the same name and the same bytes as one already there is dropped. Different bytes
  are a question.
- `jorah_ingestd/probe.py`: the report on each file: length, codec, resolution, frame rate, bit
  depth, color and audio tracks. A field it can't read is `"unknown"`. The GPS location tag is
  never kept. Color is Apple Log, Rec.709, HLG or PQ, from a tag or the metadata, or else
  `default_color`, marked as assumed.
- `jorah_ingestd/pair.py` and `sync.py`: each clip is paired with a Mac WAV:
  - by start time first (the teleprompter's sidecar, then the BWF time, then the file time);
  - then by the cross-correlation peak of the two sounds (GCC-PHAT at 4 kHz).

  A weak peak, a missing WAV or drift over 33 ms is a question, never a guess.
- `jorah_ingestd/proxy.py`: a 1080p H.264 proxy for each clip, with `h264_nvenc`, falling back to
  `libx264`. Apple Log goes through the pinned LUT (`lut3d`) into Rec.709. With no LUT pinned, an
  Apple Log proxy waits.
- `jorah_ingestd/cli.py`: the commands below.

Each take ends up `ready`, `working`, `waiting` (on the LUT), `ask` (questions for Adam) or
`failed`. `state/status.json` (`jorah-media/status@1`) is what the HUD and Jorah read.

## Commands

Run as `python3 -I bin/jorah-ingestd [--config FILE] <command>`. The default config is
`/etc/jorah-media/ingest.json` where it exists. `ingest.example.json` holds every key.

| Command | What it does |
|---|---|
| `run` | the service loop |
| `once` | scans, waits `settle_s`, ingests and makes every proxy, then exits |
| `status [--json]` | the takes, their questions and notes, and free space |
| `check` | the folders, ffmpeg, numpy, one NVENC encode, the LUT and free space |
| `probe FILE` | one file's report |
| `sync CLIP WAV` | the offset and confidence of one pair |

## Tests

```bash
python3 -m unittest discover -s services/jorah-ingestd/tests
```

ffprobe, the audio decoder and the encoder are faked, except in `RealFfmpegTest`, which runs where
ffmpeg is installed (the PC) and encodes a 10-bit clip through the real LUT filter.
