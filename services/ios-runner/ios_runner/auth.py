"""Signed requests (contract section 4, "Signature").

sig = hex(HMAC-SHA256(key, "POST\\n" + path + "\\n" + time + "\\n" + nonce + "\\n" + hex(SHA-256(body))))
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import stat
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from .config import CONTRACT

MAX_SKEW = 60
NONCE_WINDOW = 600
MAX_NONCES = 100_000
NONCE_RE = re.compile(r"^[0-9a-f]{32}$")
SIG_RE = re.compile(r"^[0-9a-f]{64}$")
TIME_RE = re.compile(r"^[0-9]{1,12}$")


def signature(key: bytes, method: str, path: str, ts: str, nonce: str, body: bytes) -> str:
    message = f"{method}\n{path}\n{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def sign_headers(key: bytes, path: str, body: bytes, now: Optional[float] = None) -> Dict[str, str]:
    """For clients and tests. The plugin (issue 9) does the same in JavaScript."""
    ts = str(int(time.time() if now is None else now))
    nonce = secrets.token_hex(16)
    return {
        "X-Jorah-Contract": CONTRACT,
        "X-Jorah-Time": ts,
        "X-Jorah-Nonce": nonce,
        "X-Jorah-Sig": signature(key, "POST", path, ts, nonce, body),
    }


def read_key(path: Path) -> Optional[bytes]:
    """The shared key, or None if it is missing or anyone else could read it."""
    try:
        st = path.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or st.st_uid != os.getuid():
            return None
        key = path.read_bytes()
    except OSError:
        return None
    return key if 32 <= len(key) <= 1024 else None


class Verifier:
    def __init__(self, key_file: Path):
        self.key_file = key_file
        self.seen: Dict[str, float] = {}
        self.lock = threading.Lock()

    def check(self, path: str, headers, body: bytes) -> bool:
        """True only for a well-formed, fresh, correctly signed, unseen request."""
        ts = headers.get("X-Jorah-Time") or ""
        nonce = headers.get("X-Jorah-Nonce") or ""
        sig = headers.get("X-Jorah-Sig") or ""
        if not headers.get("X-Jorah-Contract"):
            return False
        if not (TIME_RE.match(ts) and NONCE_RE.match(nonce) and SIG_RE.match(sig)):
            return False
        now = time.time()
        if abs(now - int(ts)) > MAX_SKEW:
            return False
        key = read_key(self.key_file)  # read per request, so a new key needs no restart
        if key is None:
            return False
        if not hmac.compare_digest(signature(key, "POST", path, ts, nonce, body), sig):
            return False
        with self.lock:
            for old, seen_at in list(self.seen.items()):
                if now - seen_at > NONCE_WINDOW:
                    del self.seen[old]
            if nonce in self.seen or len(self.seen) >= MAX_NONCES:
                return False
            self.seen[nonce] = now
        return True
