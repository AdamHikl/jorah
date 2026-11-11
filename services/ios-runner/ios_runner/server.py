"""HTTP front end (contract section 4): loopback only, JSON in and out, one
route per verb, signed requests, an unsigned GET /v1/health."""

from __future__ import annotations

import json
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .auth import Verifier
from .config import CONTRACT
from .core import Runner, envelope, error_dict

VERBS = ("sync", "build-sim", "build-device", "archive", "install-device", "status", "log", "devices")
MAX_BODY = 8 * 1024


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, runner: Runner, verifier: Verifier):
        self.runner = runner
        self.verifier = verifier
        host = runner.config.host
        self.address_family = socket.AF_INET6 if ":" in host else socket.AF_INET
        super().__init__((host, runner.config.port), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "jorah-ios-runner"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Method, route and status only. Never headers or bodies.
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")

    def send_json(self, status, obj):
        body = json.dumps(obj, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_401(self):
        self.send_response(401)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def bad(self, status, message):
        self.send_json(status, envelope(False, error_dict("BAD_ARGUMENT", message)))

    def do_GET(self):
        if self.path == "/v1/health":
            return self.send_json(200, self.server.runner.health())
        return self.bad(404, "Unknown route.")

    def do_POST(self):
        prefix = "/v1/"
        verb = self.path[len(prefix):] if self.path.startswith(prefix) else None
        if verb not in VERBS:
            self.close_connection = True
            return self.bad(404, "Unknown route.")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.close_connection = True
            return self.bad(411, "Content-Length is required.")
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            return self.bad(413, "The request body is over 8 KiB.")
        body = self.rfile.read(length)
        if not self.server.verifier.check(self.path, self.headers, body):
            return self.send_401()
        if self.headers.get("X-Jorah-Contract") != CONTRACT:
            return self.send_json(400, envelope(False, error_dict(
                "CONTRACT_MISMATCH", f"This runner speaks {CONTRACT}.")))
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            return self.bad(415, "Content-Type must be application/json.")
        try:
            request = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, ValueError):
            return self.bad(400, "The body is not JSON.")
        return self.send_json(200, self.server.runner.dispatch(verb, request))
