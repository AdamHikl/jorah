# Voice latency, 2026-11-14: where the time goes

From Adam's last word to Jorah's first audio, for `jorah-voice` (used by `mac-ear` and the HUD). No transcript or reply text is in this file.

Sources:

- `jorah-voice`'s session summaries in `journalctl -u jorah-voice` (per session: medians and P90s, never words).
- The Gateway's log, `~/.openclaw-jorah/logs/openclaw.log`, read for timestamps and subsystem names only.
- OpenClaw's per-run records, `trajectory_runtime_events` in each agent's database, read for event times and token counts only. `runs.py` here prints them.
- 49 probe turns on Adam's yes, 15:53 to 15:58, with `services/jorah-voice/tools/latency_probe.py` on the PC: the request jorah-voice sends, on session `agent:main:voice-probe`, never Adam's. Probe sessions are sandboxed (31 tools) where Adam's `agent:main:main` is not (62 tools), so their prompt is a little shorter.

## Before: the voice turns on record

Three voice sessions reached Jorah's brain, with 8 turns. Each session made the first Chat Completions request after a Gateway start.

| Session | Turns to the brain | First token median / P90 | First audio median / P90 | What the turns were |
|---|---|---|---|---|
| 2026-11-11 16:37 (`mac-ear`) | 5 | 7.10 / 16.26 s | 8.65 / 21.43 s | All with tools: GitHub clones, misheard names |
| 2026-11-11 20:03 (iPhone Talk through `jorah-voice`) | 2 | 1.98 / 12.11 s | 2.40 / 12.64 s | Short questions, no tools |
| 2026-11-14 15:36 (`mac-ear`) | 1 | 10.54 s | 11.11 s | A short question, no tools |

First token and first audio are timed from when the transcript is ready, so the pause that ends the turn comes on top.

## Before: per stage

| Stage | Simple turn, Gateway warm | First turn after a Gateway start | Turn with tools |
|---|---|---|---|
| End of speech to end of turn | 0.65 s if the words sound finished, 1.2 s if not, plus about 0.07 s before the detector starts counting | same | same |
| Transcription (Parakeet) | 0.04 to 0.19 s median, done during the pause, so off the path unless it runs late (P90 0.65 s on 11-11) | same | same |
| Gateway, before the model call | about 0.6 s (probe) | **about 7.2 s more** (below) | about 0.6 s, plus 2.6 to 3.0 s when Active Memory runs (below) |
| Model call (Haiku 5.5, thinking `medium`) | 1.70 s median, 1.11 to 3.13 s (39 probe calls) | about 2.3 s (prompt cache empty) | 8 to 16 s: tool search, tools, 3 to 5 model calls |
| Reply text to first audio (first sentence, Qwen3-TTS, whole sentence) | 0.42 s | 0.53 to 0.57 s | 1.55 s |
| Network and playback on the Mac | not measured, about 0.1 s expected | same | same |
| **Last word to first audio** | **about 3 to 3.5 s** | **about 12 s** | **about 9 s median, 22 s P90** |

Probe, request to first text, simple questions on a warm Gateway: **median 2.33 s, P90 3.08 s** (14 turns). The first turn on a new session took 5.13 s, because its 22,299-token prompt wasn't cached yet.

### The 7 seconds before the first turn

On 2026-11-14 the Gateway started at 15:04:56 and nothing used the Chat Completions endpoint until Adam spoke at 15:36. That turn, from the Gateway's records:

| Time | What |
|---|---|
| about 28.1 | Transcript ready in `jorah-voice`, request sent |
| 28.415 | `jorah-guard: matrix loaded`: the guard's `register()` ran, so the plugins were being loaded for this request |
| 35.660 | Tool catalog built (62 tools) |
| 36.101 | Run started |
| 36.555 | Prompt sent to Anthropic (25,511 tokens, none from cache: 25,450 written) |
| about 38.6 | First text back, 10.54 s after the transcript was ready |
| 38.885 | Model call done: 167 tokens out, thinking included, for a reply of about 35 words |
| 39.2 | First audio, 11.11 s after the transcript was ready |

The guard logs `matrix loaded` only when OpenClaw registers the plugins. Since the guard went live on 2026-11-13, that has happened at each Gateway start and once more: here, on the first HTTP chat request after the start. It is **once per Gateway process, not per session or per idle spell** [measured]: heartbeats after 37 quiet minutes (2026-11-13 19:13) didn't cause it, and the probe's first request on a brand-new session at 15:53 didn't either. The 2026-11-11 20:03 session shows the same: the Gateway had started at 19:56:37, the first turn waited about 7.6 s before its tool catalog and got its first token at 12.1 s, and the second turn, 2 s later, waited about 0.2 s and got its first token at 2.0 s. Which of that session's two turns was the slow one is read from the Gateway's timeline, because the voice summary gives only a median and a P90.

The Gateway started 25 times between 2026-11-06 and 2026-11-14 (config changes, boots), and voice is used less often than that, so in practice nearly every voice session started on a cold endpoint.

### Thinking makes no difference

`main` runs Haiku 5.5 with thinking `medium`. The probe put an inline `/think:low` or `/think:off` in front of the same questions, which OpenClaw documents as applying to that message only:

| Thinking | Turns | Request to first text, median | P90 | Range |
|---|---|---|---|---|
| as configured (`medium`) | 14 | 2.33 s | 3.08 s | 1.78 to 3.29 s |
| `/think:low` | 10 | 2.35 s | 2.84 s | 1.85 to 2.86 s |
| `/think:off` | 10 | 2.48 s | 2.70 s | 1.85 to 2.85 s |

No gain, so that change was dropped. Answers of 8 output tokens still took about 1.8 s, so the floor is the model call itself on a 22k to 29k token cached prompt, not thinking. Slash commands don't seem to be processed on this endpoint at all: `/jorah-status` sent there was answered by the model as an ordinary turn (3.7 s, 174 tokens), so the inline directive probably never applied.

### Reply text arrives in one piece

A five-sentence answer (about 500 characters) reached `jorah-voice` 0.07 s before the stream ended, in every one of 4 tries, and short answers the same. The Chat Completions endpoint sends the reply when the model call is done, not as it is written, so Jorah can't start speaking until the whole answer exists. `jorah-voice` already speaks the first sentence on its own, but here that only starts once the full reply is in. **[inference]** On a five-sentence answer that costs about 1 to 1.5 s against true streaming (about 250 output tokens at the measured 120 a second).

### Tool turns and Active Memory

Two probe turns that asked Jorah to check his notes took 14.6 s and 8.0 s to the first text. In each, Active Memory (`mode: escalate`) ran its blocking recall first, for 3.0 s and 2.6 s, and returned nothing (`status=unavailable reason=search-unavailable`). Then 3 to 5 model calls ran, with `tool_search` and `tool_call` steps before the memory tools. Active Memory has run only on these two probe turns in the whole log, so it may behave differently, or not run, in Adam's unsandboxed session. Not checked there.

### Speaking

Qwen3-TTS made the whole sentence before any of it was sent, at about 0.35 s of compute per second of speech (measured 2026-11-08), so a 3-second first sentence took about 1 s. `faster-qwen3-tts` can stream, with first audio at 0.29 s on the same model (`tools/fast_qwen_bench.py`, 2026-11-08).

## What was built (Adam's yes, 2026-11-14: "Yes, build 1–4")

| # | Change | Expected saving |
|---|---|---|
| 1 | **Warm-up.** `jorah_voice/warm.py`: every 20 s `jorah-voice` reads the Gateway's uptime from `GET /readyz` (loopback, no token, no session, no model). When the Gateway has started since the last warm-up, it sends one short turn on `agent:main:voice-warmup`: a real Haiku call, about $0.003 per Gateway start, because slash commands on this endpoint go to the model anyway. It also checks at once when a voice session opens. At most 2 tries per Gateway start. `--warm-every 0` turns it off | 5 to 7.5 s on the first turn after each Gateway start |
| 2 | ~~Less thinking on spoken turns~~ | Dropped: no gain measured (above) |
| 3 | **Streamed speech.** A `{"stream": true}` request to the Qwen service returns the sentence in pieces as `faster-qwen3-tts` makes them (`chunk_size` 8), ended by an empty frame. `jorah-voice` sends each piece on as it comes. Hanging up stops the GPU work. Telegram replies (`speak.py`) keep the whole-sentence request. A service without streaming answers with one frame, which reads the same. `--no-stream-speech` turns it off | 0.2 to 0.7 s on every turn |
| 4 | **One timing line a turn** in `journalctl -u jorah-voice`: `turn: {"end_pause", "transcribe", "first_token", "first_sentence", "reply_done", "first_audio", "filler", "reply_chars", "cut", "brain_failed"}`, seconds from the transcript being ready, never words | none by itself |

Expected after: about 3 to 3.3 s from the last word to first audio on a simple turn, whether or not the Gateway just started (from 3 to 3.5 s on a warm Gateway and about 12 s right after a start). Streaming saves about 0.2 s on a short first sentence and up to about 0.7 s on a long one. **[inference]**, measured below once deployed. The big win is the first turn after a Gateway start. What's left on a warm turn is mostly the model call (1.7 s median) and the pause that ends the turn (0.72 s).

## Next, each needing Adam's yes

| Change | Where | Expected saving | Note |
|---|---|---|---|
| Make the Chat Completions endpoint stream reply text as it's written | Live Gateway config, if OpenClaw has a setting for it (not found yet) | 0.5 to 1.5 s on replies longer than one sentence | Needs a look at OpenClaw's streaming settings first |
| Check Active Memory on Adam's own session, and turn its blocking recall off for voice if it costs seconds and finds nothing | Live Gateway config | 2.6 to 3.0 s on turns that ask Jorah to remember | Only seen on probe sessions so far |
| Keep the tools voice uses most outside tool search | Live Gateway config | about 1 to 2 s per tool turn | One model call fewer when a tool is needed |
| One-hour prompt cache for `main` (`cacheRetention: "long"`) | Live Gateway config | 0.2 to 0.6 s on the first turn after 5 to 60 quiet minutes **[inference]** | One-hour cache writes cost twice the base price, against 1.25 times |

Not proposed: a shorter end-of-turn pause. The 2026-11-06 benchmark (`docs/evidence/voice-endpointing/`) split sentences at every finished pause below 0.65 s, and the most it could save is about 0.1 s.

## After

To be filled in once deployed.

## Rerun

On the PC as `jorah`, from `/opt/jorah/services/jorah-voice`:

- `python3 tools/latency_probe.py --repeat 2` (simple), `--long`, `--tool`. Add `--think default low off` to compare thinking levels. Each turn is one Haiku call on `agent:main:voice-probe`.
- `python3 /opt/jorah/docs/evidence/voice-latency/runs.py 2` for the Gateway's side of the last 2 hours.
- `journalctl -u jorah-voice | grep -E "turn:|warmed|warm-up"` for real voice turns and warm-ups.
