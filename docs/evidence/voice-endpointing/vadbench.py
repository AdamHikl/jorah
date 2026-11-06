"""End-of-turn benchmark: synthetic utterances with spliced pauses, run through Ears + TurnEnd + Listener.

gen: synthesize the test set with Kokoro.   run: measure each setting.
"""

import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from jorah_voice import models
from jorah_voice.core import TurnEnd, sounds_finished
from jorah_voice.speech import MIC_RATE, VAD_WINDOW, VOICES, Ears, Listener, Speaker

HERE = Path(__file__).resolve().parent
SET = HERE / ("set-long" if "--long" in sys.argv else "set")
PAUSES = [0.8, 1.0, 1.2] if "--long" in sys.argv else [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]

UTTERANCES = {
    # A: one sentence, no pause inside.
    "A": [
        "What's the weather like tomorrow morning?",
        "Turn off the lights in the living room.",
        "Remind me to buy milk on the way home.",
        "How long does it take to drive to the city?",
        "Add eggs and butter to the shopping list.",
        "What time is my first meeting on Monday?",
        "Tell me a short joke.",
        "Can you read me the last message from Peter?",
        "Set a timer for twenty minutes.",
        "I think that's all for now, thanks.",
        "Did the package arrive yesterday?",
        "Play something calm while I work.",
    ],
    # B: a pause after a word that leaves the sentence open.
    "B": [
        "I was thinking we could go to the park and | maybe grab lunch after.",
        "Can you check the | the train times for Saturday?",
        "So I need to, um | figure out what to cook tonight.",
        "Send a message to Peter and | tell him I'll be late.",
        "What's the best way to | get to the airport from here?",
        "I want to book a table for | four people on Friday.",
        "Remind me tomorrow to call the | dentist about my appointment.",
        "So | what do you think about the new plan?",
        "Could you look up the, uh | opening hours of the pharmacy?",
        "I've been meaning to ask you about the | budget for next month.",
        "Let's move the meeting to Thursday because | Wednesday is already full.",
        "Find me a recipe with chicken and | something green, like spinach.",
        "I'm not sure if I should take the bus or | just walk today.",
        "Um | how many steps did I walk yesterday?",
        "Write down that the | car needs new tires before winter.",
        "Tell Anna that I | can't make it to dinner, but | I'll call her later.",
        "I need you to, um | check my calendar and | find a free hour on Tuesday.",
        "What was the name of the | restaurant we went to last week?",
        "Turn the heating up a bit, but | not too much.",
        "Can you, uh | remind me what I was supposed to do today?",
        "Okay so the plan is to | leave at nine and | be back by noon.",
        "I'd like to hear the news about the | election results.",
    ],
    # C: a pause where the words so far could be a whole sentence.
    "C": [
        "Remind me to call my mom | about Sunday's dinner.",
        "I need to buy a new phone | before the trip next month.",
        "Play some music | from the nineties.",
        "Check the weather | for the weekend in Vienna.",
        "Set an alarm for seven | on weekdays only.",
        "Tell me about the meeting | I have with Lucy this afternoon.",
        "Add a note | that the rent is due on the first.",
        "Read me my emails | from this morning.",
        "Book a taxi | to the station at six.",
        "Turn on the lights | in the kitchen and the hallway.",
        "Find a good coffee place | near the office.",
        "Send Peter the photos | from yesterday's walk.",
        "Remind me to water the plants | every Sunday evening.",
        "I want to go running | after work today.",
    ],
    # D: a whole sentence, a pause, then more of the same turn.
    "D": [
        "Okay. | Can you check if it's going to rain tomorrow?",
        "Wait. | Actually, make that two tickets instead of one.",
        "I'm back home now. | Can you turn on the heating?",
        "Thanks for that. | Now what's on my calendar for tomorrow?",
        "Hmm, let me think. | Let's go with the second option.",
        "That sounds good. | Book it for seven thirty.",
        "No. | I meant the other Peter, from work.",
        "Right. | And what about the weekend?",
    ],
}


def resample(samples, rate_in, rate_out):
    spectrum = np.fft.rfft(samples)
    count = int(round(len(samples) * rate_out / rate_in))
    keep = count // 2 + 1
    out = np.fft.irfft(spectrum[:keep], count) * (count / len(samples))
    return out.astype(np.float32)


def trim(samples, frame=320):
    """Cut leading and trailing quiet: frames 30 dB below the loudest one."""
    frames = len(samples) // frame
    rms = np.sqrt(np.mean(samples[: frames * frame].reshape(frames, frame) ** 2, axis=1))
    loud = np.nonzero(rms > rms.max() * 10 ** (-30 / 20))[0]
    start, end = loud[0] * frame, (loud[-1] + 1) * frame
    return samples[start:end]


def gen():
    SET.mkdir(exist_ok=True)
    root = models.ROOT
    speaker = Speaker(root, "cuda")
    voices = ["michael", "adam", "eric", "liam", "onyx", "george", "lewis", "daniel"]
    rng = np.random.default_rng(7)
    index, pause_i, meta = 0, 0, []
    for kind, lines in UTTERANCES.items():
        if "--long" in sys.argv and kind not in "BC":
            continue
        for line in lines:
            voice = voices[index % len(voices)]
            speaker._voice = VOICES[voice]
            speaker._speed = [1.0, 1.1, 0.9][index % 3]
            parts = [part.strip() for part in line.split("|")]
            audio = [np.zeros(int(0.6 * MIC_RATE), dtype=np.float32)]
            pauses, ends = [], []
            cursor = len(audio[0])
            for n, part in enumerate(parts):
                pcm = np.frombuffer(speaker.synthesize(part), dtype=np.int16).astype(np.float32) / 32768
                piece = trim(resample(pcm, speaker.sample_rate, MIC_RATE))
                piece *= 0.1 / max(1e-6, np.sqrt(np.mean(piece**2)))
                audio.append(piece)
                cursor += len(piece)
                ends.append(cursor)
                if n < len(parts) - 1:
                    pause = PAUSES[pause_i % len(PAUSES)]
                    pause_i += 1
                    pauses.append(pause)
                    gap = np.zeros(int(pause * MIC_RATE), dtype=np.float32)
                    audio.append(gap)
                    cursor += len(gap)
            audio.append(np.zeros(int(2.5 * MIC_RATE), dtype=np.float32))
            full = np.concatenate(audio)
            # Room noise about 55 dB below full scale, 35 dB under the speech.
            full += rng.normal(0, 10 ** (-55 / 20), len(full)).astype(np.float32)
            full = np.clip(full, -1, 1)
            name = f"{kind}{index:02d}"
            np.save(SET / f"{name}.npy", (full * 32767).astype(np.int16))
            meta.append({"name": name, "kind": kind, "text": " ".join(parts), "parts": parts, "voice": voice,
                         "pauses": pauses, "part_ends": [e / MIC_RATE for e in ends],
                         "speech_end": ends[-1] / MIC_RATE, "seconds": len(full) / MIC_RATE})
            print(name, voice, pauses, " / ".join(parts), flush=True)
            index += 1
    (SET / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(meta)} utterances, {sum(len(m['pauses']) for m in meta)} pauses inside")


def legacy(pcm, pause, listener):
    """Today's code: a turn starts the moment the one detector closes a segment."""
    import sherpa_onnx
    from jorah_voice.speech import _vad_config
    vad = sherpa_onnx.VoiceActivityDetector(_vad_config(sherpa_onnx, models.ROOT, pause, 0.25), buffer_size_in_seconds=60)
    samples = pcm.astype(np.float32) / 32768
    commits, asr = [], []
    for k in range(len(pcm) // VAD_WINDOW):
        t = (k + 1) * VAD_WINDOW / MIC_RATE
        vad.accept_waveform(samples[k * VAD_WINDOW : (k + 1) * VAD_WINDOW])
        while not vad.empty():
            segment = np.array(vad.front.samples, dtype=np.float32)
            vad.pop()
            started = time.perf_counter()
            text = listener.transcribe(segment)
            took = time.perf_counter() - started
            asr.append(took)
            # Cut off if the segment closed before he finished; text is ready `took` later.
            commits.append((t, text, took))
    return commits, asr


def simulate(pcm, early, finished, unfinished, listener):
    """Feed audio in VAD windows as the service would and return each commit as (time, text, transcribe s)."""
    if early < 0:
        return legacy(pcm, finished, listener)
    ears = Ears(models.ROOT, pauses=(early, finished, unfinished))
    turn_end = TurnEnd(finished, unfinished)
    held, heard, job = [], None, None
    commits, asr = [], []
    for k in range(len(pcm) // VAD_WINDOW):
        t = (k + 1) * VAD_WINDOW / MIC_RATE
        ears.accept(pcm[k * VAD_WINDOW : (k + 1) * VAD_WINDOW].tobytes())
        found = ears.segments()
        if found:
            held.extend(found)
            started = time.perf_counter()
            text = listener.transcribe(*held)
            took = time.perf_counter() - started
            asr.append(took)
            job, heard = (t + took, text, took), None
        if job and t >= job[0]:
            heard, job = job, None
        if heard and turn_end.done(heard[1], ears.quiet_seconds(), ears.speech_now()):
            commits.append((heard[0] if heard[0] > t - VAD_WINDOW / MIC_RATE else t, heard[1], heard[2]))
            held, heard = [], None
    return commits, asr


def run(configs):
    meta = json.loads((SET / "meta.json").read_text())
    listener = Listener(models.ROOT, "cpu")
    listener.transcribe(np.zeros(MIC_RATE, dtype=np.float32))
    audio = {m["name"]: np.load(SET / f"{m['name']}.npy") for m in meta}
    results = []
    for listen, finished, unfinished in configs:
        rows = []
        started = time.perf_counter()
        for m in meta:
            commits, asr = simulate(audio[m["name"]], listen, finished, unfinished, listener)
            end = m["speech_end"]
            early = [c for c in commits if c[0] < end]
            late = [c for c in commits if c[0] >= end]
            rows.append({
                "name": m["name"], "kind": m["kind"], "pauses": m["pauses"], "text": m["text"],
                "early": len(early), "early_texts": [c[1] for c in early],
                "split_after": [([p for p, e in zip(m["pauses"], m["part_ends"]) if e <= c[0]] or [None])[-1] for c in early],
                "split_at": [c[0] for c in early],
                "latency": (late[0][0] + (late[0][2] if listen < 0 else 0) - end) if late else None,
                "final_text": late[0][1] if late else None,
                "asr_calls": len(asr), "asr_total": sum(asr), "asr_each": asr,
            })
        took = time.perf_counter() - started
        results.append({"early": listen, "finished": finished, "unfinished": unfinished, "rows": rows, "wall": took})
        summarize(results[-1])
    return results


def pct(values, share):
    ordered = sorted(values)
    return ordered[max(0, int(np.ceil(share * len(ordered))) - 1)] if ordered else None


def summarize(result):
    rows = result["rows"]
    split = [r for r in rows if r["early"]]
    lat = [r["latency"] for r in rows if r["latency"] is not None]
    missing = sum(r["latency"] is None for r in rows)
    by_kind = {k: sum(1 for r in split if r["kind"] == k) for k in "ABCD"}
    print(f"early {result['early']:.2f} finished {result['finished']:.2f} unfinished {result['unfinished']:.2f}: "
          f"splits {len(split)}/{len(rows)} {by_kind} median {statistics.median(lat):.3f} p90 {pct(lat, 0.9):.3f} "
          f"no-close {missing} asr calls {sum(r['asr_calls'] for r in rows)} asr s {sum(r['asr_total'] for r in rows):.2f} "
          f"wall {result['wall']:.1f}s", flush=True)


def cost(seconds=60):
    """Time per 32 ms window: the old Ears (one detector) against the new one (two)."""
    rng = np.random.default_rng(1)
    pcm = (rng.normal(0, 0.05, MIC_RATE * seconds) * 32767).astype(np.int16)
    def per_window(ears):
        started = time.perf_counter()
        for k in range(len(pcm) // VAD_WINDOW):
            ears.accept(pcm[k * VAD_WINDOW : (k + 1) * VAD_WINDOW].tobytes())
        return (time.perf_counter() - started) / (len(pcm) // VAD_WINDOW)

    one = per_window(Ears(models.ROOT, pauses=(0.6,)))
    both = per_window(Ears(models.ROOT, pauses=(0.3, 0.6, 1.0)))
    print(f"per 32 ms window: one detector {one * 1000:.3f} ms, three {both * 1000:.3f} ms")
    listener = Listener(models.ROOT, "cpu")
    for length in (1, 2, 3, 5):
        clip = np.zeros(MIC_RATE * length, dtype=np.float32)
        clip[:] = rng.normal(0, 0.02, len(clip))
        listener.transcribe(clip)
        times = []
        for _ in range(5):
            started = time.perf_counter()
            listener.transcribe(clip)
            times.append(time.perf_counter() - started)
        print(f"transcribe {length} s of audio: median {statistics.median(times) * 1000:.0f} ms")


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen()
    elif sys.argv[1] == "cost":
        cost()
    else:
        pairs = [(-1.0, float(arg[1:]), float(arg[1:])) if arg.startswith("L") else tuple(float(x) for x in arg.split(":"))
                 for arg in sys.argv[2:] if not arg.startswith("--")]
        out = run(pairs)
        name = HERE / f"results-{'long-' if '--long' in sys.argv else ''}{int(time.time())}.json"
        name.write_text(json.dumps(out, indent=1))
        print(f"wrote {name}")
