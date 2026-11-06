"""Transcribe one audio file to plain text, for OpenClaw's CLI audio entry (Telegram voice notes).

Usage: python -m jorah_voice.transcribe <audio file>

ffmpeg decodes any format Telegram sends (Opus in Ogg, M4A, MP3) to 16 kHz mono. Parakeet runs on
the CPU, as in the live voice service, so a voice note doesn't compete with speech on the GPU.
Long notes are cut into pieces so memory stays bounded. Prints the transcript and exits 0, or
prints nothing and exits non-zero, so OpenClaw falls back to its own handling.
"""

import subprocess
import sys

import numpy as np

from . import models
from .speech import MIC_RATE, Listener

PIECE_SECONDS = 60
MAX_SECONDS = 15 * 60


def decode(path):
    """Decode the file to 16 kHz mono float32 with ffmpeg, never reading more than MAX_SECONDS."""
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path,
         "-t", str(MAX_SECONDS), "-ac", "1", "-ar", str(MIC_RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, check=True, timeout=120,
    )
    return np.frombuffer(result.stdout, dtype=np.float32)


def pieces(audio, size=PIECE_SECONDS * MIC_RATE):
    for start in range(0, len(audio), size):
        piece = audio[start:start + size]
        if len(piece) >= MIC_RATE // 4:
            yield piece


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m jorah_voice.transcribe <audio file>", file=sys.stderr)
        return 2
    audio = decode(argv[0])
    if not len(audio):
        return 1
    listener = Listener(root=models.ROOT, provider="cpu")
    text = " ".join(t for t in (listener.transcribe(p) for p in pieces(audio)) if t)
    if not text:
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
