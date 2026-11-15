"""jorah-phone: Ask Jorah from Siri, and typed phone events, on loopback behind Tailscale Serve.

The contract is docs/contracts/jorah-phone-v1.md; requests and answers are checked against the
schemas in packages/contracts/phone/. Logs say what happened and how long it took, never what was
asked, answered or reported.
"""

import argparse
import json
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from . import schema
from .ask import GATEWAY_URL, SESSION_KEY, SHARE_NOTE, SHARE_SESSION_KEY, TOKEN_FILE, AskRun, gateway_stream, share_message, spoken
from .compute import summarize
from .store import DEFAULT_DB, Store
from .tokens import DEFAULT_FILE, Tokens

PORT = 43212
LOOPBACK = {"127.0.0.1", "::1"}
# Any of these means the request came through Tailscale Serve or another proxy, not from this PC.
FORWARDED = ("X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "Forwarded",
             "Tailscale-User-Login", "Tailscale-User-Name", "Tailscale-User-Profile-Pic", "Tailscale-Headers-Info")
BODY_MAX = {"/ask": 8192, "/share": 32768, "/ingest/event": 8192, "/ingest/health": 65536}
SAY = {
    "bad": "That request didn't make sense to Jorah.",
    "token": "Jorah doesn't know this phone.",
    "busy": "I'm still answering the last one.",
    "many": "That's a lot of questions. Try again in a minute.",
    "sent": "Sent to Jorah. The reply is in the Shared chat.",
    "share_many": "That's a lot of shares. Try again later.",
    "share_down": "Jorah couldn't take that right now.",
}
PLACE_KINDS = ("arrive", "leave")
FOCUS_KINDS = ("focus_on", "focus_off")


def log(line):
    print(f"jorah-phone: {line}", flush=True)


class Window:
    """At most `limit` uses in any `seconds`."""

    def __init__(self, limit, seconds, now=time.monotonic):
        self._limit, self._seconds, self._now = limit, seconds, now
        self._times = deque()
        self._lock = threading.Lock()

    def _drop_old(self):
        edge = self._now() - self._seconds
        while self._times and self._times[0] < edge:
            self._times.popleft()

    def full(self):
        with self._lock:
            self._drop_old()
            return len(self._times) >= self._limit

    def use(self):
        """Record one use; False (and nothing recorded) if the window is full."""
        with self._lock:
            self._drop_old()
            if len(self._times) >= self._limit:
                return False
            self._times.append(self._now())
            return True


class Phone:
    """What every request needs, shared by the handler threads."""

    def __init__(self, args, stream=None, now=None, share_stream=None):
        self.args = args
        if args.share_session_key in (args.session_key, "agent:main:main"):
            raise ValueError("--share-session-key must be its own chat, never Adam's main one")
        self.tz = ZoneInfo(args.tz)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.tokens = Tokens(args.tokens)
        self.store = Store(args.db, self.tz, args.keep_events_days, args.keep_health_days, now=self.now)
        self.schemas = {name: schema.load(name, args.contracts)
                        for name in ("ask-request", "ask-response", "share-request", "share-response", "event", "health", "today", "events")}
        self.stream = stream or gateway_stream(args.gateway_url, args.gateway_token_file, args.session_key)
        self.share_stream = share_stream or gateway_stream(args.gateway_url, args.gateway_token_file, args.share_session_key,
                                                           reply_seconds=args.reply_seconds, note=SHARE_NOTE)
        self.shares = Window(30, 3600)
        self.ask_lock = threading.Lock()
        self.asks = Window(args.asks_per_10_min, 600)
        self.ingests = Window(120, 3600)
        self.failures = Window(20, 600)


class Handler(BaseHTTPRequestHandler):
    server_version = "jorah-phone/1"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 30  # a client that stops mid-request can't hold a thread for ever

    def log_message(self, *_args):
        """The default line holds paths and addresses; this service logs outcomes only."""

    @property
    def phone(self):
        return self.server.phone

    # --- replies ------------------------------------------------------------------------------

    def _send(self, status, body, close=False):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(data)

    def _share_reply(self, http_status, status, say, close=False):
        body = {"v": 1, "status": status, "say": say}
        schema.validate(self.phone.schemas["share-response"], body)
        self._send(http_status, body, close)

    def _ask_reply(self, http_status, status, say, in_app=False, close=False):
        body = {"v": 1, "status": status, "say": say, "in_app": in_app}
        schema.validate(self.phone.schemas["ask-response"], body)
        self._send(http_status, body, close)

    def _refuse(self, path, http_status, error, say="bad"):
        """An error answer: for /ask and /share always something the phone can say."""
        if path == "/share":
            status = "busy" if http_status == 429 else "refused"
            self._share_reply(http_status, status, SAY["share_many" if http_status == 429 else say], close=True)
        elif path == "/ask":
            status = "busy" if http_status == 429 else "refused"
            self._ask_reply(http_status, status, SAY["many" if http_status == 429 else say], close=True)
        else:
            self._send(http_status, {"ok": False, "error": error}, close=True)

    # --- checks -------------------------------------------------------------------------------

    def _local_only(self):
        if self.client_address[0] not in LOOPBACK or any(self.headers.get(h) for h in FORWARDED):
            return False
        port = self.server.server_address[1]
        return (self.headers.get("Host") or "").lower() in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    def _authorised(self, path, scope):
        if self.phone.failures.full():
            self._refuse(path, 429, "too many failed attempts; wait 10 minutes")
            return None
        who = self.phone.tokens.check(self.headers.get("Authorization"), scope)
        if who is None:
            self.phone.failures.use()
            if self.phone.tokens.problem:
                log(f"token file problem: {self.phone.tokens.problem}")
            log(f"{path}: refused, no valid token for {scope}")
            self._refuse(path, 401, "no valid token", say="token")
        return who

    def _json_body(self, path):
        kind = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if kind != "application/json":
            self._refuse(path, 415, "send JSON with Content-Type: application/json")
            return None
        length = self.headers.get("Content-Length", "")
        if not length.isdigit():
            self._refuse(path, 400, "Content-Length is required")
            return None
        if int(length) > BODY_MAX[path]:
            self._refuse(path, 413, f"body over {BODY_MAX[path]} bytes")
            return None
        try:
            return json.loads(self.rfile.read(int(length)).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._refuse(path, 400, "body isn't JSON")
            return None

    def _valid(self, path, name, value):
        try:
            schema.validate(self.phone.schemas[name], value)
            return True
        except schema.Invalid as error:
            log(f"{path}: refused, schema ({error.path})")
            self._refuse(path, 400, str(error))
            return False

    # --- routes -------------------------------------------------------------------------------

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/healthz":
            return self._send(200, {"ok": True, "v": 1})
        if url.path not in ("/today", "/events"):
            return self._send(404, {"ok": False, "error": "not found"}, close=True)
        if not self._local_only():
            log(f"{url.path}: refused, not a local caller")
            return self._send(403, {"ok": False, "error": "local callers only"}, close=True)
        if self._authorised(url.path, "read") is None:
            return None
        if url.path == "/today":
            body = self.phone.store.today(self.phone.args.health == "on", self.phone.args.tz)
            name = "today"
        else:
            query = parse_qs(url.query)
            since = schema.parse_date_time((query.get("since") or [""])[0])
            limit = (query.get("limit") or ["50"])[0]
            if since is None or not limit.isdigit() or not 1 <= int(limit) <= 200:
                return self._send(400, {"ok": False, "error": "need since=<ISO 8601 with offset> and limit 1-200"}, close=True)
            body, name = self.phone.store.events_since(since, int(limit)), "events"
        try:
            schema.validate(self.phone.schemas[name], body)
        except schema.Invalid as error:
            log(f"{url.path}: own answer failed its schema ({error.path})")
            return self._send(500, {"ok": False, "error": "internal error"}, close=True)
        return self._send(200, body)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in BODY_MAX:
            return self._send(404, {"ok": False, "error": "not found"}, close=True)
        scope = "ask" if path in ("/ask", "/share") else "ingest"
        if self._authorised(path, scope) is None:
            return None
        if path.startswith("/ingest/"):
            if self.phone.args.ingest != "on":
                return self._refuse(path, 403, "phone events are off")
            if path == "/ingest/health" and self.phone.args.health != "on":
                return self._refuse(path, 403, "health upload is off")
            if not self.phone.ingests.use():
                return self._refuse(path, 429, "too many uploads this hour")
        body = self._json_body(path)
        if body is None:
            return None
        if path == "/ask":
            return self._ask(body)
        if path == "/share":
            return self._share(body)
        if path == "/ingest/event":
            return self._event(body)
        return self._health(body)

    def _ask(self, body):
        if not self._valid("/ask", "ask-request", body):
            return None
        if not self.phone.asks.use():
            log("/ask: busy, rate limit")
            return self._ask_reply(200, "busy", SAY["many"])
        if not self.phone.ask_lock.acquire(blocking=False):
            log("/ask: busy, another question running")
            return self._ask_reply(200, "busy", SAY["busy"])
        run = AskRun(body["text"], self.phone.stream).start()

        def release():
            run.join(self.phone.args.reply_seconds + 10)
            self.phone.ask_lock.release()
            if run.finished_at is not None:
                log(f"/ask: run ended after {run.finished_at - run.started_at:.1f}s{f' with an error ({run.error})' if run.error else ''}")

        threading.Thread(target=release, name="ask-release", daemon=True).start()
        finished, text, error = run.wait(self.phone.args.ask_deadline)
        status, say, in_app = spoken(text, finished, error)
        first = f"{run.first_piece_at - run.started_at:.1f}s" if run.first_piece_at else "none"
        log(f"/ask: {status}, first text {first}, answered at {time.monotonic() - run.started_at:.1f}s")
        return self._ask_reply(200, status, say, in_app)

    def _share(self, body):
        """Shared text goes to its own chat (agent:main:shared), never Adam's main one, so the guard
        treats that chat as outside text. The phone gets "sent" as soon as the turn is under way; the
        reply is read to the end in the background and lands in the Shared chat."""
        if not self._valid("/share", "share-request", body):
            return None
        if not self.phone.shares.use():
            log("/share: busy, rate limit")
            return self._share_reply(200, "busy", SAY["share_many"])
        message = share_message(body["text"], body.get("note", ""), body.get("source", "other"))
        run = AskRun(message, self.phone.share_stream).start()
        finished, _text, error = run.wait(self.phone.args.share_wait)
        if finished and error:
            log(f"/share: unavailable ({error})")
            return self._share_reply(200, "unavailable", SAY["share_down"])

        def report():
            run.join(self.phone.args.reply_seconds + 10)
            if run.finished_at is not None:
                log(f"/share: run ended after {run.finished_at - run.started_at:.1f}s{f' with an error ({run.error})' if run.error else ''}")

        threading.Thread(target=report, name="share-report", daemon=True).start()
        log("/share: sent")
        return self._share_reply(200, "sent", SAY["sent"])

    def _event(self, body):
        if not self._valid("/ingest/event", "event", body):
            return None
        kind, place, focus = body["kind"], body.get("place"), body.get("focus")
        if (kind in PLACE_KINDS) != (place is not None) or (kind in FOCUS_KINDS) != (focus is not None):
            log("/ingest/event: refused, place or focus doesn't fit the kind")
            return self._refuse("/ingest/event", 400, "arrive/leave need place; focus_on/focus_off need focus; nothing else takes either")
        at = schema.parse_date_time(body["at"])
        now = self.phone.now()
        if not now - timedelta(hours=24) <= at <= now + timedelta(minutes=5):
            log("/ingest/event: refused, time out of range")
            return self._refuse("/ingest/event", 400, "at must be within the last 24 hours")
        event_id = self.phone.store.add_event(kind, place, focus, at)
        log("/ingest/event: stored")
        return self._send(200, {"ok": True, "id": event_id})

    def _health(self, body):
        if not self._valid("/ingest/health", "health", body):
            return None
        sent = schema.parse_date_time(body["sent_at"])
        now = self.phone.now()
        if not now - timedelta(hours=36) <= sent <= now + timedelta(minutes=5):
            log("/ingest/health: refused, sent_at out of range")
            return self._refuse("/ingest/health", 400, "sent_at must be within the last 36 hours")
        row = summarize(body, self.phone.tz)
        self.phone.store.put_health_day(row)
        log("/ingest/health: stored one day")
        return self._send(200, {"ok": True, "date": row["day"]})


class PhoneServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, phone):
        if ":" in address[0]:
            import socket
            self.address_family = socket.AF_INET6
        super().__init__(address, Handler)
        self.phone = phone


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="jorah-phone", description="Ask Jorah from Siri, and typed phone events (docs/contracts/jorah-phone-v1.md)")
    p.add_argument("--host", default="127.0.0.1", choices=sorted(LOOPBACK), help="loopback only: Tailscale Serve is the way in")
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--gateway-url", default=GATEWAY_URL)
    p.add_argument("--gateway-token-file", default=str(TOKEN_FILE), help="the Gateway token, shared with jorah-voice (rotate-gateway-token.sh updates it)")
    p.add_argument("--session-key", default=SESSION_KEY)
    p.add_argument("--share-session-key", default=SHARE_SESSION_KEY, help="the Shared chat; never Adam's main one")
    p.add_argument("--tokens", default=str(DEFAULT_FILE))
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--contracts", default=str(schema.CONTRACTS))
    p.add_argument("--tz", default="Europe/Bratislava")
    p.add_argument("--ingest", choices=("on", "off"), default="off", help="phone events and uploads (off until the P5 gate passes)")
    p.add_argument("--health", choices=("on", "off"), default="off", help="the daily health upload (Adam's decision H)")
    p.add_argument("--ask-deadline", type=float, default=20.0, help="seconds before the phone gets what is ready")
    p.add_argument("--reply-seconds", type=float, default=300.0, help="how long a reply is read in the background")
    p.add_argument("--share-wait", type=float, default=3.0, help="seconds to wait for an early failure before saying a share was sent")
    p.add_argument("--asks-per-10-min", type=int, default=20)
    p.add_argument("--keep-events-days", type=int, default=30)
    p.add_argument("--keep-health-days", type=int, default=90)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    args.reply_seconds = max(30.0, args.reply_seconds)
    stream = gateway_stream(args.gateway_url, args.gateway_token_file, args.session_key, reply_seconds=args.reply_seconds)
    share_stream = gateway_stream(args.gateway_url, args.gateway_token_file, args.share_session_key, reply_seconds=args.reply_seconds, note=SHARE_NOTE)
    phone = Phone(args, stream=stream, share_stream=share_stream)
    if phone.tokens.check("Bearer x", "ask") is None and phone.tokens.problem:
        log(f"token file problem: {phone.tokens.problem}; every request will be refused")
    server = PhoneServer((args.host, args.port), phone)
    log(f"listening on {args.host}:{args.port}; phone events {args.ingest}, health {args.health}; contracts {Path(args.contracts)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        phone.store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
