import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.brain import BrainError, JorahBrain, build_request, read_gateway_token, sse_text


def chunk(text):
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]})


class Request(unittest.TestCase):
    def test_only_the_latest_words_go_to_jorahs_main_session(self):
        headers, body = build_request("What's on today?", "t0ken")
        sent = json.loads(body)
        self.assertEqual(headers["x-openclaw-session-key"], "agent:main:main")
        self.assertEqual(headers["Authorization"], "Bearer t0ken")
        self.assertTrue(sent["stream"])
        self.assertEqual(sent["model"], "openclaw/main")
        self.assertEqual(sent["messages"][-1], {"role": "user", "content": "What's on today?"})
        self.assertEqual([m["role"] for m in sent["messages"]], ["system", "user"])


class Parsing(unittest.TestCase):
    def test_text(self):
        self.assertEqual(sse_text(chunk("Hi")), "Hi")

    def test_role_only_chunks_done_and_other_lines(self):
        self.assertIsNone(sse_text('data: {"choices": [{"delta": {"role": "assistant"}}]}'))
        self.assertIsNone(sse_text("data: [DONE]"))
        self.assertIsNone(sse_text(": keep-alive"))
        self.assertIsNone(sse_text("data: not json"))

    def test_a_streamed_error_is_raised(self):
        with self.assertRaises(BrainError):
            sse_text('data: {"error": {"message": "agent run failed"}}')


class Token(unittest.TestCase):
    def test_must_be_private_and_present(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "token"
            with self.assertRaises(BrainError):
                read_gateway_token(path)
            path.write_text("secret\n")
            os.chmod(path, 0o644)
            with self.assertRaises(BrainError):
                read_gateway_token(path)
            os.chmod(path, 0o600)
            self.assertEqual(read_gateway_token(path), "secret")


class FakeGateway:
    """A local stand-in for the Gateway's streaming endpoint."""

    def __init__(self, lines, status=200, hold=None):
        outer = self
        self.requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                outer.requests.append((dict(self.headers), json.loads(self.rfile.read(length))))
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    for line in lines:
                        self.wfile.write((line + "\n\n").encode())
                        self.wfile.flush()
                    if hold:
                        hold.wait(5)
                        self.wfile.write((chunk("too late") + "\n\n").encode())
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/chat/completions"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Streaming(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.token = Path(self.folder.name) / "token"
        self.token.write_text("t0ken")
        os.chmod(self.token, 0o600)

    def tearDown(self):
        self.folder.cleanup()

    def test_reply_streams_from_the_gateway(self):
        gateway = FakeGateway([chunk("Morning, "), chunk("Adam."), "data: [DONE]"])
        try:
            brain = JorahBrain(gateway.url, self.token)
            self.assertEqual(list(brain.stream("Morning")), ["Morning, ", "Adam."])
            headers, body = gateway.requests[0]
            self.assertEqual(headers["Authorization"], "Bearer t0ken")
            self.assertEqual(body["messages"][-1]["content"], "Morning")
        finally:
            gateway.close()

    def test_a_refusal_is_an_error(self):
        gateway = FakeGateway([], status=401)
        try:
            with self.assertRaises(BrainError):
                list(JorahBrain(gateway.url, self.token).stream("hi"))
        finally:
            gateway.close()

    def test_no_gateway_is_an_error_not_silence(self):
        with self.assertRaises(BrainError):
            list(JorahBrain("http://127.0.0.1:9/v1/chat/completions", self.token).stream("hi"))

    def test_cancel_stops_the_stream(self):
        hold = threading.Event()
        gateway = FakeGateway([chunk("Let me check. ")], hold=hold)
        try:
            brain = JorahBrain(gateway.url, self.token)
            got = []
            for part in brain.stream("Check the calendar"):
                got.append(part)
                brain.cancel()
            hold.set()
            self.assertEqual(got, ["Let me check. "])
        finally:
            gateway.close()


if __name__ == "__main__":
    unittest.main()
