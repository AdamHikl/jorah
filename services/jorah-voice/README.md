# jorah-voice

The sound layer for Jorah, running in the `jorah` WSL distro on the PC: speech recognition (Parakeet TDT 0.6B v3, int8, on the CPU) and speech (Kokoro v1.0, fp32, on the RTX 5070). It doesn't think for itself: each thing you say goes to Jorah's main session through the Gateway's Chat Completions endpoint, the same session Telegram uses, and Jorah's reply is spoken as it streams in. Audio never leaves the PC. The text of what you said goes to the Gateway, and from there to Anthropic like any other message. The Mac runs `clients/mac-ear`, which does nothing but capture the mic and play sound.

```
Mac: mac-ear ──tailnet──> Windows: tailscale serve ──> WSL jorah: 127.0.0.1:43210
     mic, speaker                                      as Linux user jorah
```

This is the first working piece of P3 (`docs/plan/10-roadmap.md` section 2a). It is smaller than M20.1's stack: no Pipecat or Smart Turn yet. See "When your turn ends" below.

## CPU and GPU

Measured on the PC on 2026-11-06, with a stand-in Gateway that answers at once:

| | Choice | Speed | GPU memory |
|---|---|---|---|
| Speech recognition | Parakeet v3 int8 on the CPU | 123 ms median a sentence | none |
| (compared) | Parakeet v2 fp16 on the GPU | 97 ms | 2,480 MiB |
| (compared) | Parakeet v3 int8 on the GPU | 177 ms, as int8 is slow on this GPU | 444 MiB |
| Speech | Kokoro fp32 on the GPU | 153 ms median, 190 ms P90 a sentence | about 1.3 GB, steady over a 5-minute soak |
| (before) | Kokoro int8 on the CPU | 2.3 s | none |

All three recognisers made the same 2.9% word errors on 10 test clips. v3 on the CPU was chosen for keeping GPU memory free and understanding Slovak, at a cost of about 26 ms. End of speech to first audio was 1.1 s with Kokoro on the GPU, against 2.4 s on the CPU, and 0.6 s of it is the pause that ends your turn.

The CUDA libraries come from NVIDIA's pip packages in the venv, and `speech.load_cuda()` loads them before sherpa-onnx needs them, so no library path is needed. Each model runs a few times at startup, because the GPU's first run is slow. `--stt-provider` and `--tts-provider` pick `cpu` or `cuda` for each.

## When your turn ends

Speech is transcribed after a 0.3 s pause, while the service waits to see whether you carry on. The turn ends after 0.65 s of quiet if the transcript sounds finished: it ends in `.`, `?` or `!`, and not on a word such as "and", "the" or "um". Otherwise it waits 1.2 s. If you start talking again first, the new words join the same turn. `--early-pause`, `--finished-pause` and `--unfinished-pause` change the three times. On synthetic speech this cut mid-sentence splits from 6 to 0 out of 56 turns, and the median wait from the end of speech to text ready from 0.82 s to 0.76 s: `docs/evidence/voice-endpointing/README.md`. Session summaries log `end_pause`, the pause that ended each turn, and never what was said.

## Speed

Measured 2026-11-14 in `docs/evidence/voice-latency/`: about 3 to 3.5 s from your last word to Jorah's first sound on a simple turn. That's 0.72 s of pause, about 0.6 s in the Gateway, a 1.7 s model call, and the first sentence's speech. Three things keep it there:

- **Warm-up.** The first chat request after each Gateway start waits about 7 s while OpenClaw loads its plugins, once per Gateway process. Every 20 s the service reads the Gateway's uptime from `GET /readyz` on loopback, and after each start it sends one short turn on `agent:main:voice-warmup`, never Adam's session. That's about $0.003 per start. It checks again whenever a voice session opens. The log says `warmed the Gateway in …`. `--warm-every 0` turns it off.
- **Streamed speech.** Qwen3-TTS sends each sentence's audio in pieces as it is made, so speech starts about 0.3 s after the text instead of after the whole sentence. `--no-stream-speech` goes back to whole sentences.
- **Timing per turn.** One `turn:` line per turn in `journalctl -u jorah-voice`, in seconds from the transcript being ready: `first_token`, `first_sentence`, `reply_done`, `first_audio`, and `filler` when "One moment." was said. Never words.

`tools/latency_probe.py` times the brain the way a spoken turn reaches it, on `agent:main:voice-probe`.

## What it needs from the Gateway

- `gateway.http.endpoints.chatCompletions.enabled: true`. The endpoint stays on loopback, and Tailscale Serve exposes only the speech port, 43210.
- The Gateway token in `~/.config/jorah-voice/gateway-token`, mode 600, placed by Adam. That token is full operator access, so this service is as trusted as the Gateway itself. It runs as the same `jorah` user in the same sandbox.
- If the Gateway is down, Jorah says "I can't reach my brain right now" rather than going silent.

Unverified until the Gateway runs on the PC: that `x-openclaw-session-key: agent:main:main` lands in the same session as Telegram, and how the Gateway treats the short system note about speaking aloud. Logs hold timings, never what was said.

## What Kokoro can't say

Kokoro silently drops any word missing from its word list, and the list lacks names, numbers, acronyms and many ordinary forms such as "opened". `spoken.py` rewrites text first: numbers become words, acronyms get spelled, missing `-s` and `-ed` forms are generated from the base word's sounds, and anything else is split into known parts or spelled out. Names go in `lexicon-names.txt`.

## The mic

The mic is open only while `mac-ear` runs, and its terminal shows `● MIC OPEN`. It closes on "goodbye", after 60 s of quiet, at 30 minutes in any case, on Ctrl-C, or if the connection drops.

## Setup

See `docs/runbooks/jorah-on-pc.md`.

## Tests

`just unit` needs no install, model or network; a local stand-in plays the Gateway. `jorah_voice.check` runs one real turn on the PC with no client, so it needs the Gateway running.
