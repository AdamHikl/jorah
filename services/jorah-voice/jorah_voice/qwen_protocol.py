"""The small protocol between jorah-voice and its Qwen3-TTS service, plus the client side.

Request: one JSON line, {"text": "..."} or {"ping": true}.
Reply: 4-byte big-endian sample rate, 4-byte big-endian length, then that many bytes of 16-bit mono PCM.
An empty reply (length 0) means it couldn't speak; callers fall back to Kokoro.
"""

import json
import socket
import struct
from pathlib import Path

SOCKET = Path.home() / ".cache" / "jorah-voice" / "qwen.sock"
VOICE = Path.home() / ".config" / "jorah-voice" / "voice"


def read_request(stream):
    line = stream.readline(8192)
    if not line:
        return None
    try:
        request = json.loads(line)
    except ValueError:
        return None
    return request if isinstance(request, dict) else None


def write_reply(stream, rate, pcm):
    stream.write(struct.pack(">II", rate, len(pcm)) + pcm)
    stream.flush()


def _read_exact(sock, count):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("Qwen3-TTS service closed the connection")
        data += chunk
    return data


def ask(request, path=SOCKET, timeout=120):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall(json.dumps(request).encode() + b"\n")
        rate, length = struct.unpack(">II", _read_exact(sock, 8))
        return rate, _read_exact(sock, length)


class QwenSpeaker:
    """Same interface as speech.Speaker, backed by the Qwen3-TTS service."""

    # Faster than real time with faster-qwen3-tts, so waiting sentences are spoken together, like Kokoro.
    chunk_chars = 300

    def __init__(self, path=SOCKET, timeout=120):
        self._path = path
        self._timeout = timeout
        self._rate, _ = ask({"ping": True}, path, timeout=10)

    @property
    def sample_rate(self):
        return self._rate

    def synthesize(self, text):
        rate, pcm = ask({"text": text}, self._path, self._timeout)
        if not pcm:
            raise RuntimeError("Qwen3-TTS returned no audio")
        self._rate = rate
        return pcm
