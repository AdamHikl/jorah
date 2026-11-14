import os
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from jorah_voice.qwen_protocol import QwenSpeaker, read_request, write_reply


class FakeService:
    def __init__(self, reply_pcm, pieces=None):
        """`pieces`: what a streaming service sends for a stream request. Without it, the service
        predates streaming and answers every request with one frame."""
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "q.sock"
        pcm = reply_pcm

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = read_request(self.rfile)
                if request.get("stream") and pieces is not None:
                    for piece in pieces:
                        write_reply(self.wfile, 24000, piece)
                    write_reply(self.wfile, 24000, b"")
                    return
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


class Streaming(unittest.TestCase):
    def test_pieces_come_as_they_are_made(self):
        service = FakeService(b"", pieces=[b"\x01\x00" * 4, b"\x02\x00" * 4])
        try:
            speaker = QwenSpeaker(path=service.path, timeout=5)
            self.assertEqual(list(speaker.stream("Hello.")), [b"\x01\x00" * 4, b"\x02\x00" * 4])
        finally:
            service.close()

    def test_a_service_without_streaming_still_works(self):
        service = FakeService(b"\x03\x00" * 6)
        try:
            speaker = QwenSpeaker(path=service.path, timeout=5)
            self.assertEqual(list(speaker.stream("Hello.")), [b"\x03\x00" * 6])
        finally:
            service.close()

    def test_no_audio_is_an_error(self):
        service = FakeService(b"", pieces=[])
        try:
            with self.assertRaises(RuntimeError):
                list(QwenSpeaker(path=service.path, timeout=5).stream("Hello."))
        finally:
            service.close()


class WaitAtBoot(unittest.TestCase):
    def test_waits_until_the_service_is_up(self):
        from jorah_voice.qwen_protocol import wait_for_qwen
        tries, now = [], [0.0]

        def make():
            tries.append(now[0])
            if len(tries) < 4:
                raise ConnectionRefusedError()
            return "speaker"

        def sleep(seconds):
            now[0] += seconds

        self.assertEqual(wait_for_qwen(make, 120, sleep=sleep, clock=lambda: now[0]), "speaker")
        self.assertEqual(len(tries), 4)

    def test_gives_up_after_the_wait(self):
        from jorah_voice.qwen_protocol import wait_for_qwen
        now = [0.0]

        def make():
            raise ConnectionRefusedError()

        def sleep(seconds):
            now[0] += seconds

        self.assertIsNone(wait_for_qwen(make, 10, sleep=sleep, clock=lambda: now[0]))
        self.assertGreaterEqual(now[0], 10)
