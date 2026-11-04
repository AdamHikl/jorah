# jorah-voice

The PC side of talking to Jorah. It runs in its own WSL distro: speech recognition (Parakeet v3), speech (Kokoro) and thinking (Claude Haiku). Only the text of what you said leaves the PC, to Anthropic. The Mac runs `clients/mac-ear`, which does nothing but capture the mic and play sound.

```
Mac: mac-ear ──tailnet──> Windows: tailscale serve ──> WSL jorah-voice: 127.0.0.1:43210
     mic, speaker                                      as Linux user jorah-voice
```

This is the first working piece of P3 (`docs/plan/10-roadmap.md` section 2a). It is smaller than M20.1's stack: no Pipecat or Smart Turn yet, and a fixed 0.6 s pause ends your turn. Speech models start on the CPU. `--provider cuda` waits for P1.3's GPU spike.

## What it can't do

It has no tools, no memory of past sessions, and no access to mail, calendar, files or the web. It starts no jobs and isn't connected to the Gateway. The conversation lives in memory. Logs hold timings, never what was said.

## The mic

The mic is open only while `mac-ear` runs, and its terminal shows `● MIC OPEN`. It closes on "goodbye", after 60 s of quiet, at 30 minutes in any case, on Ctrl-C, or if the connection drops.

## Setup

See `docs/runbooks/voice-on-pc.md`.

## Tests

`just unit` needs no install, model or network. `jorah_voice.check` runs one turn on the PC with no client.
