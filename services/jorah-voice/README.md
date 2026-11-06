# jorah-voice

The sound layer for Jorah, running in the `jorah` WSL distro on the PC: speech recognition (Parakeet v3) and speech (Kokoro). **Thinking is still a stand-in:** `brain.py` calls Claude Haiku with no tools or memory, so this isn't Jorah yet. It gets replaced by Jorah's main session once the Gateway has moved to the PC. Only the text of what you said leaves the PC, to Anthropic. The Mac runs `clients/mac-ear`, which does nothing but capture the mic and play sound.

```
Mac: mac-ear ──tailnet──> Windows: tailscale serve ──> WSL jorah: 127.0.0.1:43210
     mic, speaker                                      as Linux user jorah
```

This is the first working piece of P3 (`docs/plan/10-roadmap.md` section 2a). It is smaller than M20.1's stack: no Pipecat or Smart Turn yet, and a fixed 0.6 s pause ends your turn. Speech models start on the CPU. `--provider cuda` waits for P1.3's GPU spike.

## What it can't do

It has no tools, no memory of past sessions, and no access to mail, calendar, files or the web. It starts no jobs and isn't connected to the Gateway. The conversation lives in memory. Logs hold timings, never what was said.

## What Kokoro can't say

Kokoro silently drops any word missing from its word list, and the list lacks names, numbers, acronyms and many ordinary forms such as "opened". `spoken.py` rewrites text first: numbers become words, acronyms get spelled, missing `-s` and `-ed` forms are generated from the base word's sounds, and anything else is split into known parts or spelled out. Names go in `lexicon-names.txt`.

## The mic

The mic is open only while `mac-ear` runs, and its terminal shows `● MIC OPEN`. It closes on "goodbye", after 60 s of quiet, at 30 minutes in any case, on Ctrl-C, or if the connection drops.

## Setup

See `docs/runbooks/jorah-on-pc.md`.

## Tests

`just unit` needs no install, model or network. `jorah_voice.check` runs one turn on the PC with no client.
