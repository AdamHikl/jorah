"""Test the speech models on the PC with no client: a recording in, a recording out."""

import argparse
import time
import wave

import numpy as np

from . import models
from .brain import ClaudeBrain
from .core import History, SentenceChunker
from .speech import MIC_RATE, Listener, Speaker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="16 kHz mono WAV. Without it, the text below is used")
    parser.add_argument("--text", default="Say good morning to Adam in one short sentence.")
    parser.add_argument("--output", default="reply.wav")
    parser.add_argument("--provider", default="cpu")
    parser.add_argument("--voice", default="michael")
    args = parser.parse_args()

    root = models.ensure()
    text = args.text
    if args.input:
        with wave.open(args.input, "rb") as source:
            if source.getframerate() != MIC_RATE or source.getnchannels() != 1:
                raise SystemExit(f"{args.input} must be {MIC_RATE} Hz mono")
            samples = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        started = time.monotonic()
        text = Listener(root, args.provider).transcribe(samples)
        print(f"Heard in {time.monotonic() - started:.2f}s: {text}")

    speaker = Speaker(root, args.provider, voice=args.voice)
    history = History()
    history.add("Adam", text)
    chunker = SentenceChunker()
    audio = []
    started = time.monotonic()
    first_token = None
    for delta in ClaudeBrain().stream(history.as_prompt()):
        first_token = first_token or time.monotonic() - started
        for sentence in chunker.feed(delta):
            print(f"Jorah: {sentence}")
            audio.append(speaker.synthesize(sentence))
    for sentence in chunker.flush():
        print(f"Jorah: {sentence}")
        audio.append(speaker.synthesize(sentence))
    if first_token is None:
        raise SystemExit("The brain returned nothing")
    print(f"First token {first_token:.2f}s, whole reply {time.monotonic() - started:.2f}s")
    with wave.open(args.output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(speaker.sample_rate)
        target.writeframes(b"".join(audio))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
