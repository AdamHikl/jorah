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


def join_waiting(sentence, queue, max_chars):
    """Join sentences already waiting in an asyncio queue onto this one, up to max_chars.

    Returns the joined text and whether the end marker (None) was reached.
    """
    while not queue.empty():
        nxt = queue.get_nowait()
        if nxt is None:
            return sentence, True
        if len(sentence) + 1 + len(nxt) > max_chars:
            # Too long to join: put it back at the front by rebuilding the queue.
            rest = [nxt]
            while not queue.empty():
                rest.append(queue.get_nowait())
            for item in rest:
                queue.put_nowait(item)
            return sentence, False
        sentence = f"{sentence} {nxt}"
    return sentence, False


# A sentence ending in one of these is still open, however it is punctuated. English, then Slovak.
OPEN_ENDINGS = frozenset("""
    a an the and or but so because cause then if that than to of for with about from into in on at by as
    my your his her our their its this these those some
    um uh er erm hmm mm like i we you is are was were
    ale alebo že lebo aby keď či ani
""".split())


def sounds_finished(text):
    """True when a transcript reads as a whole turn: it ends in . ? or ! and not on a word that leaves it open.

    Parakeet punctuates even a fragment, so the full stop alone isn't enough.
    """
    text = text.strip()
    if not text or text[-1] not in ".?!" or text.endswith(".."):
        return False
    words = normalize_command(text).split()
    return bool(words) and words[-1] not in OPEN_ENDINGS


class TurnEnd:
    """Decides when a pause ends Adam's turn.

    A sentence that sounds finished ends after `finished` seconds of quiet. Anything else waits
    `unfinished` seconds, so a pause to think after "and" or "the" doesn't cut him off.
    """

    def __init__(self, finished, unfinished):
        if not 0 < finished <= unfinished:
            raise ValueError("need 0 < finished <= unfinished")
        self.finished = finished
        self.unfinished = unfinished

    def wait_for(self, text):
        return self.finished if sounds_finished(text) else self.unfinished

    def done(self, text, quiet, speaking):
        """`text` is the transcript of everything held so far, or None while it is still being made."""
        return text is not None and not speaking and quiet >= self.wait_for(text)


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
