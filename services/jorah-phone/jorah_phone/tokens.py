"""The phone's tokens: stored as SHA-256 hashes with an id and scopes, never as the token itself.

The file is ~/.config/jorah-phone/tokens.json, mode 600 in a mode-700 folder. The service re-reads
it whenever it changes, so a revoke works at once. A file anyone else can read, or one that won't
parse, makes every request fail rather than letting any through.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

SCOPES = ("ask", "ingest", "read")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_FILE = Path.home() / ".config" / "jorah-phone" / "tokens.json"


class TokenError(RuntimeError):
    pass


def digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _read(path):
    """Return the entries in the file, [] if it doesn't exist. Raises TokenError if unsafe or broken."""
    path = Path(path)
    try:
        info = path.stat()
    except FileNotFoundError:
        return []
    if info.st_mode & 0o077:
        raise TokenError(f"{path} must be readable by its owner only")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TokenError(f"can't read {path}: {type(error).__name__}") from None
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("tokens"), list):
        raise TokenError(f"{path} isn't a v1 token file")
    entries = []
    for entry in data["tokens"]:
        if not (isinstance(entry, dict) and ID.match(str(entry.get("id", ""))) and HEX.match(str(entry.get("sha256", "")))
                and isinstance(entry.get("scopes"), list) and entry["scopes"] and all(s in SCOPES for s in entry["scopes"])):
            raise TokenError(f"{path} has a malformed entry")
        entries.append(entry)
    return entries


def _write(path, entries):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tokens.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"v": 1, "tokens": entries}, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def new_token(path, token_id, scopes, replace=False):
    """Add a token and return it. It is shown or written once and never stored."""
    if not ID.match(token_id):
        raise TokenError("an id is 1 to 32 of a-z, 0-9 and '-', starting with a letter or digit")
    scopes = sorted(set(scopes))
    if not scopes or any(s not in SCOPES for s in scopes):
        raise TokenError(f"scopes must be some of: {', '.join(SCOPES)}")
    entries = _read(path)
    if any(e["id"] == token_id for e in entries):
        if not replace:
            raise TokenError(f"{token_id} exists already; revoke it first or use --replace")
        entries = [e for e in entries if e["id"] != token_id]
    token = secrets.token_urlsafe(32)
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    entries.append({"id": token_id, "sha256": digest(token), "scopes": scopes, "created": created})
    _write(path, entries)
    return token


def revoke(path, token_id):
    entries = _read(path)
    kept = [e for e in entries if e["id"] != token_id]
    if len(kept) == len(entries):
        return False
    _write(path, kept)
    return True


def listing(path):
    return [{"id": e["id"], "scopes": e["scopes"], "created": e.get("created")} for e in _read(path)]


def write_token_file(path, token):
    """Write a token for a local reader (the Gateway plugin): mode 600, never printed."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(token + "\n")


class Tokens:
    """Checks bearer tokens against the file, re-reading it when its modification time changes."""

    def __init__(self, path=DEFAULT_FILE):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._stamp = None
        self._entries = []
        self.problem = None

    def _refresh(self):
        try:
            info = self._path.stat()
            stamp = (info.st_mtime_ns, info.st_size, info.st_ino)
        except FileNotFoundError:
            stamp = None
        if stamp == self._stamp and self._stamp is not None:
            return
        try:
            self._entries, self.problem = _read(self._path), None
        except TokenError as error:
            self._entries, self.problem = [], str(error)
        self._stamp = stamp

    def check(self, header, scope):
        """Return the token's id if the Authorization header holds a token with this scope, else None."""
        if not isinstance(header, str) or not header.startswith("Bearer "):
            return None
        token = header[7:].strip()
        if not token or len(token) > 200:
            return None
        wanted = digest(token)
        with self._lock:
            self._refresh()
            entries = list(self._entries)
        found = None
        for entry in entries:
            if hmac.compare_digest(wanted, entry["sha256"]):
                found = entry
        if found is None or scope not in found["scopes"]:
            return None
        return found["id"]
