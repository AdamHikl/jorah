"""Keep the Gateway's chat path warm, so Adam's first spoken turn after a Gateway start isn't the slow one.

Measured 2026-11-14 (docs/evidence/voice-latency/): the first Chat Completions request after each Gateway
start waits about 7 s while OpenClaw loads its plugins, once per Gateway process; later requests, on any
session, don't. The Gateway restarts several times a day, so this watches its uptime on /readyz (loopback,
no token, no session, no model) and, whenever it has started since the last warm-up, sends one short
turn on a session of its own. That turn is a real Haiku call, about $0.003, because the endpoint has
no cheaper way in: slash commands sent there go to the model too. Adam's conversation is never used,
and the warm-up session resets daily like every session.
"""

import http.client
import json
import threading
import time
from urllib.parse import urlsplit

WARMUP_SESSION = "agent:main:voice-warmup"
WARMUP_TEXT = "Automatic warm-up after a Gateway restart, not a message from Adam. Reply with one word: ready."
# Two readings of the same Gateway start differ only by clock drift; a restart moves it by far more.
SAME_START_SECONDS = 5
TRIES_PER_START = 2


def gateway_uptime(gateway_url, timeout=3):
    """Return the Gateway's uptime in seconds from /readyz, or None if it isn't up and ready."""
    url = urlsplit(gateway_url)
    connection = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=timeout)
    try:
        connection.request("GET", "/readyz")
        response = connection.getresponse()
        body = response.read(65536)
        if response.status != 200:
            return None
        state = json.loads(body)
        uptime = state.get("uptimeMs") if isinstance(state, dict) else None
        if state.get("ready") is not True or not isinstance(uptime, (int, float)):
            return None
        return uptime / 1000
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        connection.close()


class Warmer:
    """Sends one warm-up turn per Gateway start. `check` runs in a background thread."""

    def __init__(self, make_brain, uptime, every=20, clock=time.monotonic, log=print):
        self._make_brain = make_brain
        self._uptime = uptime
        self._every = every
        self._clock = clock
        self._log = log
        self._warmed_start = None
        self._tries = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()

    def _same(self, a, b):
        return a is not None and b is not None and abs(a - b) < SAME_START_SECONDS

    def check(self):
        """Warm the Gateway if it has started since the last warm-up. Returns True if this call warmed it."""
        with self._lock:
            uptime = self._uptime()
            if uptime is None:
                return False
            started = self._clock() - uptime
            if self._same(started, self._warmed_start):
                return False
            key = next((k for k in self._tries if self._same(k, started)), started)
            if self._tries.get(key, 0) >= TRIES_PER_START:
                return False
            self._tries = {key: self._tries.get(key, 0) + 1}
            begun = self._clock()
            try:
                for _ in self._make_brain().stream(WARMUP_TEXT):
                    pass
            except Exception as error:
                self._log(f"warm-up failed: {type(error).__name__}: {error}")
                return False
            self._warmed_start = started
            self._log(f"warmed the Gateway in {self._clock() - begun:.1f}s, {uptime:.0f}s after it started")
            return True

    def poke(self):
        """Check now rather than at the next tick, such as when a voice session opens."""
        self._wake.set()

    def run(self):
        while True:
            try:
                self.check()
            except Exception as error:  # never let the watcher die
                self._log(f"warm-up check failed: {type(error).__name__}")
            self._wake.wait(self._every)
            self._wake.clear()

    def start(self):
        threading.Thread(target=self.run, name="gateway-warmer", daemon=True).start()
