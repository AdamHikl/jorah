import os
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from jorah_voice.qwen_protocol import QwenSpeaker, read_request, write_reply


class FakeService:
    def __init__(self, reply_pcm):
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "q.sock"
        pcm = reply_pcm

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = read_request(self.rfile)
                write_reply(self.wfile, 24000, b"" if request.get("ping") else pcm)

        self.server = socketserver.ThreadingUnixStreamServer(str(self.path), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        os.unlink(self.path)
        os.rmdir(self.dir)


class QwenProtocolTest(unittest.TestCase):
    def test_speaks_through_the_service(self):
        service = FakeService(b"\x01\x00" * 10)
        try:
            speaker = QwenSpeaker(path=service.path, timeout=5)
            self.assertEqual(speaker.sample_rate, 24000)
            self.assertEqual(speaker.synthesize("Hello."), b"\x01\x00" * 10)
            self.assertEqual(speaker.chunk_chars, 300)
        finally:
            service.close()

    def test_empty_audio_is_an_error(self):
        service = FakeService(b"")
        try:
            with self.assertRaises(RuntimeError):
                QwenSpeaker(path=service.path, timeout=5).synthesize("Hello.")
        finally:
            service.close()

    def test_no_service_raises_oserror(self):
        with self.assertRaises(OSError):
            QwenSpeaker(path=Path(tempfile.gettempdir()) / "no-such-jorah.sock", timeout=1)
