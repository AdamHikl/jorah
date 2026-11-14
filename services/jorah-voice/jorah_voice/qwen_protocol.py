"""The small protocol between jorah-voice and its Qwen3-TTS service, plus the client side.

Request: one JSON line, {"text": "..."} or {"ping": true}, or {"text": "...", "stream": true}.
Reply: 4-byte big-endian sample rate, 4-byte big-endian length, then that many bytes of 16-bit mono PCM.
An empty reply (length 0) means it couldn't speak; callers fall back to Kokoro.
A stream reply is a run of such frames, each a piece of the sentence as soon as it's made, ended by an
empty frame. A service that predates streaming answers with one frame and hangs up, which reads the same.
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


def _read_exact(sock, count, eof_ok=False):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            if eof_ok and not data:
                return None
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


def wait_for_qwen(make, wait_seconds, sleep=None, clock=None):
    """Build a QwenSpeaker, retrying while the service loads.

    At boot jorah-voice starts before the Qwen service has loaded its model (about 30 s, measured
    2026-11-09), and a speaker chosen then stays for the life of the process. Returns None if the
    service is still down after `wait_seconds`.
    """
    import time
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    deadline = clock() + wait_seconds
    while True:
        try:
            return make()
        except OSError:
            if clock() >= deadline:
                return None
            sleep(3)


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

    def stream(self, text):
        """Yield the sentence's audio in pieces as the service makes them. Stopping early hangs up,
        which stops the service too."""
        got_audio = False
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self._timeout)
            sock.connect(str(self._path))
            sock.sendall(json.dumps({"text": text, "stream": True}).encode() + b"\n")
            while True:
                header = _read_exact(sock, 8, eof_ok=got_audio)
                if header is None:
                    break
                rate, length = struct.unpack(">II", header)
                if not length:
                    break
                self._rate = rate
                got_audio = True
                yield _read_exact(sock, length)
        if not got_audio:
            raise RuntimeError("Qwen3-TTS returned no audio")
