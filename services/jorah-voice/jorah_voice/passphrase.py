"""Adam's permanent confirmation phrase store and matcher (ADR 0010 D2).

The plaintext phrase or anything derived from it other than the salted scrypt hash is never
logged, never sent to the Gateway, and never spoken.
"""

import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata
from pathlib import Path

from . import confirm, core
from .identity import DEFAULT_VOICEPRINT_DIR, write_private_json

PASSPHRASE_FILE = "passphrase.json"
PHRASE_ERROR_MESSAGE = "Use at least 3 words or 6 digits."
PHRASE_FORBIDDEN_WORD_MESSAGE = "Leave out words like no, stop or cancel."
MAX_FAILURES = 3

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_MAXMEM = 64 * 1024 * 1024

_NUMBER_WORDS = {
    # English
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    # Slovak (with and without diacritics)
    "nula": "0",
    "jeden": "1",
    "jedna": "1",
    "jedno": "1",
    "dva": "2",
    "dve": "2",
    "tri": "3",
    "štyri": "4",
    "styri": "4",
    "päť": "5",
    "pat": "5",
    "šesť": "6",
    "sest": "6",
    "sedem": "7",
    "osem": "8",
    "deväť": "9",
    "devat": "9",
}


def _strip_punctuation(text):
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "S") or ch == "_":
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def normalise(text):
    """Normalise a spoken or typed phrase for hashing and window matching."""
    cleaned = _strip_punctuation(unicodedata.normalize("NFKC", str(text)).lower())
    split_digits = re.sub(r"\d", lambda m: f" {m.group(0)} ", cleaned)
    tokens = [_NUMBER_WORDS.get(tok, tok) for tok in split_digits.split()]
    return " ".join(tokens)


def _scrypt_hash(norm_phrase, salt, *, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P):
    return hashlib.scrypt(
        norm_phrase.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=SCRYPT_DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )


def _contains_forbidden_word(phrase):
    cleaned = unicodedata.normalize("NFKC", phrase).replace("\u2019", "'")
    if confirm.classify_answer(cleaned) == "deny":
        return True
    if core.classify(cleaned) not in ("talk", "empty"):
        return True
    for word in core.normalize_command(cleaned).split():
        if core.classify(word) not in ("talk", "empty"):
            return True
    return False


def _parse_set_fields(data, default_n):
    k = int(data["words"])
    salt = bytes.fromhex(data["salt"])
    expected = bytes.fromhex(data["hash"])
    n = int(data.get("n", default_n))
    r = int(data.get("r", SCRYPT_R))
    p = int(data.get("p", SCRYPT_P))
    if k <= 0 or len(salt) != 32 or len(expected) != SCRYPT_DKLEN:
        raise ValueError("invalid phrase record")
    return k, salt, expected, n, r, p


class PhraseStore:
    """Salted scrypt phrase store with 3-strike lockout persisted in passphrase.json (mode 600)."""

    def __init__(self, voiceprint_dir=DEFAULT_VOICEPRINT_DIR, *, scrypt_n=SCRYPT_N, date_fn=None):
        self._path = Path(voiceprint_dir) / PASSPHRASE_FILE
        self._n = scrypt_n
        self._date_fn = date_fn or (lambda: time.strftime("%Y-%m-%d", time.gmtime()))

    def _read(self):
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"version": 1, "set": False, "words": None, "failures": 0, "locked": False}, True
        except OSError:
            return None, False
        try:
            data = json.loads(raw)
        except ValueError:
            return None, False
        if not isinstance(data, dict) or data.get("version") != 1:
            return None, False
        return data, True

    def is_healthy(self):
        """Return True if passphrase.json is absent or valid, False if unreadable or corrupt."""
        data, ok = self._read()
        if not ok:
            return False
        if not data.get("set"):
            return True
        try:
            _parse_set_fields(data, self._n)
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def _write(self, record):
        write_private_json(self._path, record)

    def status(self):
        data, ok = self._read()
        if not ok:
            return {"set": False, "words": None, "locked": True}
        is_set = bool(data.get("set") and data.get("hash") and data.get("salt") and isinstance(data.get("words"), int))
        return {
            "set": is_set,
            "words": data["words"] if is_set else None,
            "locked": bool(data.get("locked", False)),
        }

    def is_set(self):
        return self.status()["set"]

    @property
    def locked(self):
        return self.status()["locked"]

    def set(self, phrase):
        if not isinstance(phrase, str):
            raise ValueError(PHRASE_ERROR_MESSAGE)
        pre_cleaned = _strip_punctuation(unicodedata.normalize("NFKC", phrase).lower())
        pre_words = pre_cleaned.split()
        norm = normalise(phrase)
        tokens = norm.split()
        if not tokens:
            raise ValueError(PHRASE_ERROR_MESSAGE)
        has_letters = any(ch.isalpha() for ch in norm)
        if has_letters:
            if len(pre_words) < 3:
                raise ValueError(PHRASE_ERROR_MESSAGE)
        else:
            if len(tokens) < 6 or not all(len(t) == 1 and t.isdigit() for t in tokens):
                raise ValueError(PHRASE_ERROR_MESSAGE)
        if _contains_forbidden_word(phrase):
            raise ValueError(PHRASE_FORBIDDEN_WORD_MESSAGE)

        prev, ok = self._read()
        failures = int(prev.get("failures", 0)) if ok else 0
        locked = bool(prev.get("locked", False)) if ok else True

        salt = secrets.token_bytes(32)
        digest = _scrypt_hash(norm, salt, n=self._n)
        record = {
            "version": 1,
            "set": True,
            "salt": salt.hex(),
            "hash": digest.hex(),
            "n": self._n,
            "r": SCRYPT_R,
            "p": SCRYPT_P,
            "words": len(tokens),
            "created_at": self._date_fn(),
            "failures": failures,
            "locked": locked,
        }
        self._write(record)
        return self.status()

    def clear(self):
        prev, ok = self._read()
        failures = int(prev.get("failures", 0)) if ok else 0
        locked = bool(prev.get("locked", False)) if ok else True
        if not locked and failures == 0:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            return self.status()
        self._write({
            "version": 1,
            "set": False,
            "words": None,
            "failures": failures,
            "locked": locked,
        })
        return self.status()

    def matches_within(self, transcript):
        if not isinstance(transcript, str):
            return False
        data, ok = self._read()
        if not ok or not data.get("set"):
            return False
        try:
            k, salt, expected, n, r, p = _parse_set_fields(data, self._n)
        except (KeyError, TypeError, ValueError):
            return False
        words = normalise(transcript).split()
        if len(words) < k:
            return False
        matched = False
        for start in range(len(words) - k + 1):
            candidate = " ".join(words[start : start + k])
            digest = _scrypt_hash(candidate, salt, n=n, r=r, p=p)
            if hmac.compare_digest(digest, expected):
                matched = True
        return matched

    def record_failure(self):
        data, ok = self._read()
        if not ok:
            data = {"version": 1, "set": False, "words": None, "failures": MAX_FAILURES, "locked": True}
        else:
            failures = int(data.get("failures", 0)) + 1
            data["failures"] = failures
            if failures >= MAX_FAILURES:
                data["locked"] = True
        self._write(data)
        return bool(data.get("locked", False))

    def record_success(self):
        data, ok = self._read()
        if not ok:
            return
        if not data.get("locked") and int(data.get("failures", 0)) > 0:
            data["failures"] = 0
            self._write(data)

    def unlock(self):
        data, ok = self._read()
        if not ok:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            return
        if data.get("set"):
            data["failures"] = 0
            data["locked"] = False
            self._write(data)
        else:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
