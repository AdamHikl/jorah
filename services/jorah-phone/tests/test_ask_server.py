import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_phone import schema  # noqa: E402
from jorah_phone import server as server_module  # noqa: E402
from jorah_phone.ask import SAY_MAX, AskError, AskRun, build_request, gateway_stream, spoken, sse_text  # noqa: E402
from jorah_phone.server import Phone, PhoneServer, parse_args  # noqa: E402
from jorah_phone.tokens import new_token  # noqa: E402

ASK_RESPONSE = schema.load("ask-response")
CANARY = "Zeltrova-7Q"
LOG = []
server_module.log = LOG.append   # the service's log lines, kept here instead of on the console


def stream_of(pieces, delay=0.0, gate=None, error=None):
    def stream(_text):
        for index, piece in enumerate(pieces):
            if gate is not None and index > 0:
                gate.wait(10)
            if delay:
                time.sleep(delay)
            yield piece
        if error:
            raise AskError(error)
    return stream


def checked(result):
    status, say, in_app = result
    schema.validate(ASK_RESPONSE, {"v": 1, "status": status, "say": say, "in_app": in_app})
    return result


class SpokenTest(unittest.TestCase):
    def test_a_plain_answer(self):
        self.assertEqual(checked(spoken("It's 12 degrees and dry.", True)), ("ok", "It's 12 degrees and dry.", False))

    def test_private_details_stay_in_the_app(self):
        reply = "It's in the app.\n[app]\nYou slept 6 h 10 min, HRV 41 ms."
        self.assertEqual(checked(spoken(reply, True)), ("ok", "It's in the app.", True))
        self.assertEqual(checked(spoken("[APP]\nsecret", True)), ("ok", "It's in the app.", True))
        # Once [app] has arrived, the spoken part is final even if the rest is still coming or fails.
        self.assertEqual(checked(spoken("Two things. [app] det", False)), ("ok", "Two things.", True))
        self.assertEqual(checked(spoken("Two things. [app] det", True, error="x")), ("ok", "Two things.", True))

    def test_markup_and_links_are_not_read_aloud(self):
        status, say, in_app = checked(spoken("**Yes.** See https://example.com/x?a=1 for more.", True))
        self.assertEqual(say, "Yes. See a link in the app for more.")
        self.assertTrue(in_app)

    def test_a_long_answer_is_cut_at_a_sentence(self):
        reply = " ".join(f"Sentence number {n} is here." for n in range(80))
        status, say, in_app = checked(spoken(reply, True))
        self.assertLessEqual(len(say), SAY_MAX)
        self.assertTrue(say.endswith("is here. The rest is in the app."))
        self.assertTrue(in_app)
        status, say, _ = checked(spoken("word " * 400, True))     # no sentence end at all
        self.assertLessEqual(len(say), SAY_MAX)

    def test_unfinished_answers(self):
        self.assertEqual(checked(spoken("First part is done. Second par", False)),
                         ("partial", "First part is done. I'm still on it. The answer will be in the app.", True))
        self.assertEqual(checked(spoken("Still writ", False)), ("partial", "Still thinking. The answer will be in the app.", True))
        self.assertEqual(checked(spoken("", False)), ("partial", "Still thinking. The answer will be in the app.", True))

    def test_failures(self):
        self.assertEqual(checked(spoken("", True, error="can't reach")), ("unavailable", "I can't reach Jorah right now.", False))
        self.assertEqual(checked(spoken("Done one. Then", True, error="dropped")),
                         ("partial", "Done one. I lost the rest of that. It may be in the app.", True))
        self.assertEqual(checked(spoken("", True)), ("ok", "It's in the app.", True))   # an empty reply


class AskRunTest(unittest.TestCase):
    def test_the_run_is_read_to_the_end_after_the_phone_is_answered(self):
        gate = threading.Event()
        run = AskRun("q", stream_of(["One. ", "Two."], gate=gate)).start()
        finished, text, error = run.wait(0.2)
        self.assertFalse(finished)
        self.assertEqual(text, "One. ")
        gate.set()
        self.assertTrue(run.join(5))
        self.assertEqual(run.wait(0)[1], "One. Two.")
        self.assertIsNone(run.error)

    def test_errors_end_the_run(self):
        run = AskRun("q", stream_of(["Half."], error="the Gateway answered 500")).start()
        finished, text, error = run.wait(5)
        self.assertTrue(finished)
        self.assertEqual((text, error), ("Half.", "the Gateway answered 500"))

        def broken(_text):
            raise ValueError("bug")
            yield  # pragma: no cover
        run = AskRun("q", broken).start()
        self.assertEqual(run.wait(5)[2], "unexpected ValueError")


class FakeGateway(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeGateway.seen.append({"auth": self.headers.get("Authorization"), "session": self.headers.get("x-openclaw-session-key"), "body": body})
        if body["messages"][-1]["content"] == "fail":
            self.send_response(500)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ("Hello", " there."):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


class GatewayStreamTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.token = Path(self.dir.name) / "gateway-token"
        self.token.write_text("gw-token\n")
        os.chmod(self.token, 0o600)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGateway)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/chat/completions"
        FakeGateway.seen = []

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.dir.cleanup()

    def test_one_turn_into_the_main_session(self):
        stream = gateway_stream(self.url, self.token, "agent:main:main")
        self.assertEqual("".join(stream("what's the weather")), "Hello there.")
        seen = FakeGateway.seen[0]
        self.assertEqual(seen["auth"], "Bearer gw-token")
        self.assertEqual(seen["session"], "agent:main:main")
        self.assertEqual(seen["body"]["messages"][0]["role"], "system")
        self.assertIn("[app]", seen["body"]["messages"][0]["content"])
        self.assertEqual(seen["body"]["messages"][1], {"role": "user", "content": "what's the weather"})

    def test_gateway_failures(self):
        with self.assertRaises(AskError):
            list(gateway_stream(self.url, self.token)("fail"))
        with self.assertRaises(AskError):
            list(gateway_stream("http://127.0.0.1:9/v1/chat/completions", self.token)("x"))
        os.chmod(self.token, 0o644)
        with self.assertRaises(AskError):
            list(gateway_stream(self.url, self.token)("x"))

    def test_sse_lines(self):
        self.assertEqual(sse_text('data: {"choices": [{"delta": {"content": "hi"}}]}'), "hi")
        for line in ("", ": ping", "data: [DONE]", "data: {not json", 'data: {"choices": []}'):
            self.assertIsNone(sse_text(line))
        with self.assertRaises(AskError):
            sse_text('data: {"error": {"message": "boom"}}')
        headers, body = build_request("q", "tok")
        self.assertNotIn("tok", body.decode())


class Running:
    """A real jorah-phone on an ephemeral loopback port, with a stand-in for Jorah."""

    def __init__(self, folder, stream, ingest="on", health="on", deadline=2.0, asks=20):
        args = parse_args(["--port", "0", "--db", f"{folder}/data/phone.db", "--tokens", f"{folder}/cfg/tokens.json",
                           "--ingest", ingest, "--health", health, "--ask-deadline", str(deadline), "--asks-per-10-min", str(asks)])
        self.phone = Phone(args, stream=stream)
        self.server = PhoneServer(("127.0.0.1", 0), self.phone)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def call(self, method, path, body=None, token=None, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        sent = {"Authorization": f"Bearer {token}"} if token else {}
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None:
            sent["Content-Type"] = "application/json"
        sent.update(headers or {})
        connection.request(method, path, body=data, headers=sent)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response.status, json.loads(payload) if payload else None

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.phone.store.close()


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        tokens = f"{self.dir.name}/cfg/tokens.json"
        self.phone_token = new_token(tokens, "iphone", ["ask", "ingest"])
        self.read_token = new_token(tokens, "gateway", ["read"])
        self.running = []

    def tearDown(self):
        for r in self.running:
            r.close()
        self.dir.cleanup()

    def start(self, stream=None, **flags):
        r = Running(self.dir.name, stream or stream_of(["It's dry today."]), **flags)
        self.running.append(r)
        return r

    def now(self, minutes=0):
        return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).astimezone().isoformat(timespec="seconds")

    def ask(self, r, text="how's the weather", token=None):
        status, body = r.call("POST", "/ask", {"v": 1, "text": text}, token=token or self.phone_token)
        schema.validate(ASK_RESPONSE, body)
        return status, body

    def test_healthz_needs_nothing(self):
        r = self.start()
        self.assertEqual(r.call("GET", "/healthz"), (200, {"ok": True, "v": 1}))
        self.assertEqual(r.call("GET", "/nope")[0], 404)

    def test_ask(self):
        r = self.start()
        self.assertEqual(self.ask(r), (200, {"v": 1, "status": "ok", "say": "It's dry today.", "in_app": False}))

    def test_ask_refusals_can_always_be_spoken(self):
        r = self.start()
        self.assertEqual(self.ask(r, token="wrong")[1]["say"], "Jorah doesn't know this phone.")
        self.assertEqual(self.ask(r, token=self.read_token)[0], 401)
        for raw, headers, code in ((b"{nope", {}, 400), (b'{"v": 1, "text": "x", "extra": 1}', {}, 400),
                                   (b'{"v": 1, "text": ""}', {}, 400), (b'{"v": 1, "text": "x"}', {"Content-Type": "text/plain"}, 415),
                                   (json.dumps({"v": 1, "text": "x" * 9000}).encode(), {}, 413)):
            with self.subTest(code=code, raw=raw[:30]):
                status, body = r.call("POST", "/ask", raw=raw, token=self.phone_token, headers=headers)
                self.assertEqual(status, code)
                schema.validate(ASK_RESPONSE, body)
                self.assertEqual(body["status"], "refused")
                self.assertTrue(body["say"])

    def test_the_deadline_answers_the_phone_and_the_run_carries_on(self):
        gate = threading.Event()
        r = self.start(stream_of(["The first part is ready. ", "And the rest."], gate=gate), deadline=0.3)
        status, body = self.ask(r)
        self.assertEqual(body["status"], "partial")
        self.assertTrue(body["say"].startswith("The first part is ready."))
        self.assertEqual(self.ask(r)[1]["status"], "busy")       # the run still holds the session
        gate.set()
        for _ in range(50):
            if not r.phone.ask_lock.locked():
                break
            time.sleep(0.05)
        self.assertEqual(self.ask(r)[1]["status"], "ok")

    def test_ask_rate_limit(self):
        r = self.start(asks=2)
        self.ask(r)
        self.ask(r)
        self.assertEqual(self.ask(r)[1], {"v": 1, "status": "busy", "say": "That's a lot of questions. Try again in a minute.", "in_app": False})

    def test_unavailable_gateway(self):
        r = self.start(stream_of([], error="can't reach the Gateway: ConnectionRefusedError"))
        self.assertEqual(self.ask(r)[1]["status"], "unavailable")

    def test_logs_never_hold_what_was_asked_or_answered(self):
        LOG.clear()
        r = self.start(stream_of([f"The code is {CANARY}."]))
        self.ask(r, text=f"what is {CANARY}")
        self.ask(r, text=f"{CANARY}", token="bad")
        r.call("POST", "/ingest/event", {"v": 1, "kind": "arrive", "place": "home", "at": self.now(), "note": CANARY}, token=self.phone_token)
        time.sleep(0.1)
        lines = "\n".join(LOG)
        self.assertNotIn(CANARY, lines)
        self.assertIn("/ask: ok", lines)
        self.assertIn("/ingest/event: refused, schema", lines)

    def test_events(self):
        r = self.start()
        good = {"v": 1, "kind": "arrive", "place": "school", "at": self.now()}
        status, body = r.call("POST", "/ingest/event", good, token=self.phone_token)
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertEqual(r.call("POST", "/ingest/event", good, token=self.phone_token)[1]["id"], body["id"])
        for bad in ({**good, "place": None}, {"v": 1, "kind": "arrive", "at": self.now()}, {**good, "focus": "work"},
                    {"v": 1, "kind": "focus_on", "focus": "work", "place": "home", "at": self.now()},
                    {"v": 1, "kind": "wake", "place": "home", "at": self.now()},
                    {**good, "at": self.now(minutes=-60 * 25)}, {**good, "at": self.now(minutes=30)},
                    {**good, "lat": 48.14}):
            with self.subTest(bad=bad):
                self.assertEqual(r.call("POST", "/ingest/event", bad, token=self.phone_token)[0], 400)
        self.assertEqual(r.call("POST", "/ingest/event", good, token=self.read_token)[0], 401)

    def test_phone_events_and_health_start_off(self):
        r = self.start(ingest="off", health="off")
        event = {"v": 1, "kind": "wake", "at": self.now()}
        self.assertEqual(r.call("POST", "/ingest/event", event, token=self.phone_token), (403, {"ok": False, "error": "phone events are off"}))
        self.assertEqual(r.call("POST", "/ingest/event", event, token="bad")[0], 401)   # the switch isn't shown to strangers
        self.assertEqual(self.ask(r)[1]["status"], "ok")                               # Ask works with ingest off

    def test_health_upload(self):
        r = self.start(health="off")
        upload = {"v": 1, "sent_at": self.now(), "sleep": [], "hrv": [], "resting_hr": [], "workouts": []}
        self.assertEqual(r.call("POST", "/ingest/health", upload, token=self.phone_token)[1]["error"], "health upload is off")
        r.close()
        self.running.remove(r)
        r = self.start(health="on")
        status, body = r.call("POST", "/ingest/health", upload, token=self.phone_token)
        self.assertEqual((status, body["ok"]), (200, True))
        minimal = {"v": 1, "sent_at": self.now()}          # Shortcuts drops empty lists: still a valid upload
        self.assertEqual(r.call("POST", "/ingest/health", minimal, token=self.phone_token)[0], 200)
        stale = {**upload, "sent_at": self.now(minutes=-60 * 40)}
        self.assertEqual(r.call("POST", "/ingest/health", stale, token=self.phone_token)[0], 400)
        big = {**upload, "sleep": [{"start": self.now(), "end": self.now()}] * 401}
        self.assertEqual(r.call("POST", "/ingest/health", big, token=self.phone_token)[0], 400)

    def test_today_and_events_are_for_local_code_only(self):
        r = self.start()
        r.call("POST", "/ingest/event", {"v": 1, "kind": "wake", "at": self.now()}, token=self.phone_token)
        status, body = r.call("GET", "/today", token=self.read_token)
        self.assertEqual(status, 200)
        schema.validate(schema.load("today"), body)
        self.assertEqual(body["phone"]["last_event"]["kind"], "wake")
        self.assertEqual(r.call("GET", "/today", token=self.phone_token)[0], 401)
        for headers in ({"X-Forwarded-For": "100.64.0.5"}, {"Tailscale-User-Login": "someone@example.com"},
                        {"Host": "rocket.example.ts.net:43213"}, {"Forwarded": "for=100.64.0.5"}):
            with self.subTest(headers=headers):
                self.assertEqual(r.call("GET", "/today", token=self.read_token, headers=headers), (403, {"ok": False, "error": "local callers only"}))
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
        status, body = r.call("GET", f"/events?since={since.replace('+', '%2B')}&limit=10", token=self.read_token)
        self.assertEqual(status, 200)
        self.assertEqual([e["kind"] for e in body["events"]], ["wake"])
        self.assertEqual(r.call("GET", "/events?since=yesterday", token=self.read_token)[0], 400)

    def test_failed_tokens_are_throttled(self):
        r = self.start()
        for _ in range(20):
            self.ask(r, token="guess")
        status, body = self.ask(r, token=self.phone_token)
        self.assertEqual((status, body["status"]), (429, "busy"))


if __name__ == "__main__":
    unittest.main()
