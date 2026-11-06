# Voice endpointing, 2026-11-06

Tier: tests on the PC, with the real models (Silero VAD v5, Parakeet TDT 0.6B v3 int8 on the CPU with 4 threads) driving `Ears`, `TurnEnd` and `Listener` from the branch. **Synthetic speech only.** Kokoro voices with pauses spliced in only approximate a person hesitating. Each piece was synthesized on its own, so it ends with falling, sentence-final intonation where a real speaker would trail off, and no real speech or the full service was tested. Nothing ran in `/opt/jorah`, and no Gateway was running.

## The test set

56 utterances, 8 Kokoro voices, speeds 0.9 to 1.1, room noise 55 dB below full scale, 2.5 s of quiet after each. 47 pauses inside utterances, each 0.2, 0.3, 0.4, 0.5, 0.6 or 0.7 s, about 8 of each.

| Kind | Count | Example |
|---|---|---|
| A: no pause inside | 12 | "Set a timer for twenty minutes." |
| B: pause after an open word | 22 | "I want to book a table for / four people on Friday." |
| C: pause where the words so far read as a sentence | 14 | "Play some music / from the nineties." |
| D: a whole sentence, a pause, more of the same turn | 8 | "Okay. / Can you check if it's going to rain tomorrow?" |

A split is a turn handed to Jorah before the last word. B and C splits are mid-sentence. D splits fall between two sentences. The close time is end of speech, the last frame within 30 dB of the loudest, to the moment the text is ready for Jorah, so transcription is included in every row. Today's code closes on the detector, then transcribes. The new code transcribes during the pause.

A stress set of 36 B and C utterances has longer pauses: 0.8, 1.0 and 1.2 s.

## Results

Settings are early / finished / unfinished pause, in seconds. "One pause" is the new code with a single pause, where the only change from today is that speech starting again during transcription stops the turn.

| Setting | Utterances split | Mid-sentence (B, C) | Between sentences (D) | Median close s | P90 close s | Transcriptions | Transcribe CPU s |
|---|---|---|---|---|---|---|---|
| today's code, 0.25 | 35/56 | 28 | 7 | 0.43 | 0.51 | 95 | 8.5 |
| today's code, 0.35 | 27/56 | 21 | 6 | 0.52 | 0.60 | 85 | 7.9 |
| today's code, 0.45 | 18/56 | 14 | 4 | 0.67 | 0.74 | 76 | 7.8 |
| today's code, 0.50 | 13/56 | 10 | 3 | 0.72 | 0.77 | 70 | 8.0 |
| **today's code, 0.60 (current)** | **7/56** | **6** | **1** | **0.82** | **0.88** | 63 | 8.0 |
| today's code, 0.70 | 3/56 | 2 | 1 | 0.92 | 0.98 | 59 | 8.0 |
| today's code, 0.80 | 1/56 | 1 | 0 | 1.01 | 1.10 | 57 | 8.2 |
| one pause 0.45 | 10/56 | 8 | 2 | 0.68 | 0.75 | 76 | 8.4 |
| one pause 0.55 | 4/56 | 3 | 1 | 0.79 | 0.85 | 67 | 8.7 |
| one pause 0.60 | 3/56 | 2 | 1 | 0.83 | 0.87 | 63 | 8.4 |
| one pause 0.65 | 0/56 and 1/56 in two runs | 0 to 1 | 0 | 0.89 | 0.96 | 60 | 8.2 |
| one pause 0.70 | 0/56 | 0 | 0 | 0.92 | 0.99 | 59 | 8.4 |
| 0.25 / 0.25 / 1.0 | 14/56 | 9 | 5 | 0.45 | 0.53 | 95 | 9.8 |
| 0.35 / 0.35 / 1.0 | 10/56 | 6 | 4 | 0.55 | 0.62 | 85 | 9.3 |
| 0.30 / 0.45 / 1.0 | 8/56 | 5 | 3 | 0.56 | 0.60 | 87 | 9.8 |
| 0.30 / 0.50 / 1.0 | 6/56 | 4 | 2 | 0.59 | 0.63 | 87 | 9.8 |
| 0.30 / 0.55 / 1.0 | 4/56 | 3 | 1 | 0.65 | 0.69 | 87 | 10.2 |
| 0.30 / 0.60 / 0.6 | 7/56 | 6 | 1 | 0.69 | 0.72 | 87 | 9.8 |
| 0.30 / 0.60 / 1.0 | 3/56 | 2 | 1 | 0.69 | 0.73 | 87 | 10.9 |
| 0.30 / 0.65 / 1.0 | 1/56 | 0 | 1 | 0.76 | 0.80 | 87 | 10.7 |
| **0.30 / 0.65 / 1.2 (chosen)** | **1/56** | **0** | **1** | **0.76** | **0.80** | 87 | 10.6 |
| 0.30 / 0.70 / 1.0 | 1/56 | 0 | 1 | 0.79 | 0.83 | 87 | 10.7 |
| 0.60 / 0.60 / 1.0 | 1/56 | 0 | 1 | 0.83 | 0.89 | 63 | 8.6 |

Stress set, 0.8 to 1.2 s pauses:

| Setting | Utterances split | B (open word) | C (reads as a sentence) | Median close s | P90 close s |
|---|---|---|---|---|---|
| today's code, 0.60 | 36/36 | 22 | 14 | 0.77 | 0.80 |
| one pause 0.65 | 31/36 | 19 | 12 | 0.87 | 0.94 |
| 0.30 / 0.65 / 1.0 | 23/36 | 10 | 13 | 0.76 | 1.10 |
| 0.30 / 0.65 / 1.2 | 19/36 | 6 | 13 | 0.76 | 1.28 |
| 0.30 / 0.60 / 1.5 | 16/36 | 3 | 13 | 0.69 | 0.73 |

The adaptive rows from 0.30 / 0.60 / 1.0 down, and the stress set, are from the last run, after held segments were joined with the real audio between them. The others are from the run before. Joining changes transcripts, not timing: rows run both ways match within 0.01 s and one split.

## What was chosen, and why

Early 0.3 s, finished 0.65 s, unfinished 1.2 s, the defaults of `--early-pause`, `--finished-pause` and `--unfinished-pause`.

- The rule was that a split costs more than up to 0.3 s of waiting. Against today's 0.6 s, the chosen setting splits 1 turn instead of 7, and no turn mid-sentence instead of 6, while the median close drops from 0.82 to 0.76 s and P90 from 0.88 to 0.80 s.
- 0.30 / 0.60 / 1.0 is 0.07 s faster again, but splits 2 C turns. A shorter finished pause can't avoid that: a fragment like "Play some music." reads as a whole sentence, so only the pause length protects it. Every setting with a finished pause below 0.65 s split C turns.
- The remaining split is "I'm back home now." then 0.7 s of quiet, then "Can you turn on the heating?" That is between two sentences, and a person might well answer there too.
- 1.2 s rather than 1.0 s for an open sentence costs nothing on the main set, and cuts stress-set splits after an open word from 10 to 6. It costs the 2 of 56 finished turns that Parakeet ended with "and" or a comma 0.2 s each.
- Stopping the turn when speech starts again during transcription is worth most of the gain on its own: one pause at 0.6 s splits 3 utterances, against 7 for today's code at 0.6 s.

## What the adaptive rule costs

- **Transcription.** Parakeet runs at each 0.3 s pause, not once per turn: 87 runs for 56 utterances, against 63 today, and 10.6 s of transcription CPU against 8.0 s, about a third more. A run takes 0.12 to 0.13 s median and under 0.19 s P90, on 4 threads. Clips of 1, 2, 3 and 5 s took 60, 88, 120 and 190 ms. When the turn ends, its transcript is already done, so none of this is on the way to Jorah's answer unless a run is still going when the pause is reached.
- **Detection.** One Silero detector per pause plus one with no hold time: 0.38 ms per 32 ms window, against 0.19 ms with one pause and the voice check. That is about 1% of one core.
- **Waiting.** A finished turn that Parakeet ends with "and" or a comma waits 1.2 s instead of 0.65 s. That was 2 of 56 here: "...tell him I'll be late and" and "...after work today,".
- **Words.** Word errors across the turns that weren't split were 3.9% for the chosen setting against 2.9% to 3.3% for single pauses. Most of the difference is one clip, "Send Peter the photos from yesterday's walk", which every setting garbled and this one returned in Cyrillic, plus the stray "and" above. Before the gap audio was kept, joined segments also dropped a word at the join.

## Untested

- Real speech: a real hesitation, a real room and a real mic through `mac-ear`. 0.65 s is only just under the longest pause in the main set, 0.7 s, so the margin for a pause after a whole-sounding fragment is thin. The detector starts counting quiet about 0.07 s after the last word.
- Slovak. `OPEN_ENDINGS` has a few Slovak conjunctions, untested.
- The full service with Jorah's Gateway, which isn't running yet. Unit tests cover the session's hold, join and stale-transcript logic with stand-ins.
- First-audio time end to end. Only end of speech to text ready was measured.

## Rerun

`vadbench.py` is the harness. On the PC, with `jorah_voice` from this branch next to it: `python vadbench.py gen` (and `gen --long`) synthesizes the set on the GPU, `python vadbench.py run L0.6 0.3:0.65:1.2` measures settings (`L` is today's code), `python vadbench.py cost` times the detectors and the recognizer.
