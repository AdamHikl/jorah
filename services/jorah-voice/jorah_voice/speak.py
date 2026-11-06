"""Speak one reply into a WAV file, for OpenClaw's local CLI text-to-speech (Telegram voice replies).

Usage: python -m jorah_voice.speak <output.wav> <text>

Kokoro runs on the CPU, so a voice reply doesn't compete with the live voice service on the GPU.
The voice is the live service's default, so Jorah sounds the same everywhere. Text is cleaned of
markup and cut into sentences, which is how Kokoro is configured here. Long replies are capped.
"""

import sys
import wave

from . import models
from .core import SentenceChunker, clean_for_speech
from .speech import Speaker

MAX_CHARS = 4000
PAUSE_SECONDS = 0.15


def sentences(text):
    chunker = SentenceChunker()
    return chunker.feed(clean_for_speech(text[:MAX_CHARS]) + " ") + chunker.flush()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m jorah_voice.speak <output.wav> <text>", file=sys.stderr)
        return 2
    target, text = argv
    parts = sentences(text)
    if not parts:
        return 1
    speaker = Speaker(root=models.ROOT, provider="cpu")
    pause = b"\x00\x00" * int(speaker.sample_rate * PAUSE_SECONDS)
    with wave.open(target, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(speaker.sample_rate)
        for part in parts:
            out.writeframes(speaker.synthesize(part) + pause)
    return 0


if __name__ == "__main__":
    sys.exit(main())
