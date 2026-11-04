"""The parts of a voice turn that need no audio, model or network."""

import hmac
import json
import math
import re
import time

STOP_SPEECH = {"stop", "stop it", "be quiet", "quiet"}
CANCEL = {"cancel", "cancel that", "never mind", "nevermind"}
END_SESSION = {"goodbye", "goodbye jorah", "bye jorah", "stop listening", "go to sleep"}

_MARKUP = re.compile(r"[*_`#>|]+")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SPACES = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+")
_ABBREVIATION = re.compile(r"\b(?:mr|mrs|ms|dr|st|vs|etc|e\.g|i\.e)\.$", re.IGNORECASE)


def normalize_command(text):
    """Lower-case a transcript and drop punctuation, for matching spoken commands."""
    return _SPACES.sub(" ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def classify(text):
    """Return "stop", "cancel", "end" or "talk" for a transcript. Only an exact phrase is a command."""
    command = normalize_command(text)
    if not command:
        return "empty"
    if command in STOP_SPEECH:
        return "stop"
    if command in CANCEL:
        return "cancel"
    if command in END_SESSION:
        return "end"
    return "talk"


def clean_for_speech(text):
    """Remove markup a speech engine would read aloud."""
    return _SPACES.sub(" ", _MARKUP.sub("", _LINK.sub(r"\1", text))).strip()


class SentenceChunker:
    """Turn streamed text into whole sentences, so speech can start before the reply ends."""

    def __init__(self, max_chars=220):
        self._buffer = ""
        self._max_chars = max_chars

    def feed(self, delta):
        self._buffer += delta
        sentences = []
        start = 0
        for match in _SENTENCE_END.finditer(self._buffer):
            candidate = self._buffer[start : match.start()] + match.group(0).rstrip()
            if _ABBREVIATION.search(candidate.strip()):
                continue
            sentences.append(candidate)
            start = match.end()
        self._buffer = self._buffer[start:]
        if len(self._buffer) > self._max_chars:
            cut = self._buffer.rfind(" ", 0, self._max_chars)
            cut = cut if cut > 0 else self._max_chars
            sentences.append(self._buffer[:cut])
            self._buffer = self._buffer[cut:].lstrip()
        return [s for s in (clean_for_speech(s) for s in sentences) if s]

    def flush(self):
        rest = clean_for_speech(self._buffer)
        self._buffer = ""
        return [rest] if rest else []


class IdleClock:
    """Closes the session after a stretch with nobody talking, so the mic never stays open by accident."""

    def __init__(self, limit_seconds, now=time.monotonic):
        self._limit = limit_seconds
        self._now = now
        self._last = now()

    def touch(self):
        self._last = self._now()

    def expired(self):
        return self._now() - self._last >= self._limit


class History:
    """The current conversation, in memory only. It is gone when the session ends."""

    def __init__(self, max_turns=12):
        self._turns = []
        self._max = max_turns

    def add(self, who, text):
        self._turns.append((who, text))
        self._turns = self._turns[-self._max :]

    def drop_last(self):
        if self._turns:
            self._turns.pop()

    def as_prompt(self):
        return "\n".join(f"{who}: {text}" for who, text in self._turns) + "\nJorah:"


def percentile(values, share):
    """Nearest-rank percentile. Returns None with no samples, so a missing number never reads as 0."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def parse_hello(message, expected_token):
    """Check a client's first message. Returns its options, or None if it isn't allowed in."""
    if not isinstance(message, str):
        return None
    try:
        hello = json.loads(message)
    except ValueError:
        return None
    if not isinstance(hello, dict) or hello.get("type") != "hello":
        return None
    token = hello.get("token")
    if not isinstance(token, str) or not hmac.compare_digest(token, expected_token):
        return None
    return {"barge_in": hello.get("barge_in") is True}
