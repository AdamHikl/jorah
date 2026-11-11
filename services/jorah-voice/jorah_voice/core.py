"""The parts of a voice turn that need no audio, model or network."""

import hmac
import json
import math
import re
import sys
import time
from array import array

STOP_SPEECH = {"stop", "stop it", "be quiet", "quiet", "enough"}
CANCEL = {"cancel", "cancel that", "never mind", "nevermind"}
END_SESSION = {"goodbye", "goodbye jorah", "bye jorah", "stop listening", "go to sleep"}
# Close at once, with nothing said back (04 5.3).
END_QUIETLY = {"thanks", "thank you", "thanks jorah", "thank you jorah", "that s all", "thats all", "that is all"}
STAY = {"stay with me", "stay with me jorah", "keep listening"}

# Audio rates a client may send. The recogniser wants 16 kHz; OpenClaw's Talk relay sends 24 kHz.
MIC_RATE = 16000
INPUT_RATES = (16000, 24000)

_MARKUP = re.compile(r"[*_`#>|]+")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SPACES = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+")
_ABBREVIATION = re.compile(r"\b(?:mr|mrs|ms|dr|st|vs|etc|e\.g|i\.e)\.$", re.IGNORECASE)


def normalize_command(text):
    """Lower-case a transcript and drop punctuation, for matching spoken commands."""
    return _SPACES.sub(" ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def classify(text):
    """Return "stop", "cancel", "end", "end_quietly", "stay" or "talk" for a transcript.

    Only an exact phrase is a command, so none of these reach the model.
    """
    command = normalize_command(text)
    if not command:
        return "empty"
    if command in STOP_SPEECH:
        return "stop"
    if command in CANCEL:
        return "cancel"
    if command in END_SESSION:
        return "end"
    if command in END_QUIETLY:
        return "end_quietly"
    if command in STAY:
        return "stay"
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


class FollowUp:
    """When a session closes by itself, from voice plan 04 5.3. All times in seconds, on one clock.

    - Opening: nothing said within `first` of the session opening closes it.
    - Follow-up: after a reply, `follow_up` of quiet closes it, or `question` if the reply asked one.
    - Stay ("stay with me"): `stay_quiet` of quiet, or `stay_cap` in all, with a warning
      `warn_before` the cap. "That's all" leaves it.
    Nothing closes while Jorah is busy: the caller asks only when he isn't.
    """

    def __init__(self, now, first=5.0, follow_up=8.0, question=12.0, stay_quiet=120.0, stay_cap=600.0, warn_before=30.0):
        self.first, self.follow_up, self.question = first, follow_up, question
        self.stay_quiet, self.stay_cap, self.warn_before = stay_quiet, stay_cap, warn_before
        self.state = "opening"
        self._since = now
        self._limit = first
        self._stay_started = None
        self._warned = False

    def heard(self, now):
        """Speech is coming in: the window restarts from now."""
        if self.state != "stay":
            self.state = "listening"
        self._since = now

    def replied(self, now, text=""):
        """Jorah finished speaking. A reply ending in a question gets the longer window."""
        if self.state == "stay":
            self._since = now
            return
        self.state = "follow_up"
        self._since = now
        self._limit = self.question if text.rstrip().endswith("?") else self.follow_up

    def stay(self, now):
        self.state = "stay"
        self._since = now
        self._stay_started = now
        self._warned = False

    def check(self, now):
        """Return ("close", reason), ("warn", seconds_left) once, or None."""
        if self.state == "stay":
            left = self._stay_started + self.stay_cap - now
            if left <= 0:
                return ("close", f"{int(self.stay_cap // 60)} minute stay limit")
            if now - self._since >= self.stay_quiet:
                return ("close", f"{int(self.stay_quiet)}s of quiet")
            if left <= self.warn_before and not self._warned:
                self._warned = True
                return ("warn", left)
            return None
        if self.state == "listening":
            # Mid-turn quiet is the turn ender's business, not a reason to close.
            return None
        if now - self._since >= self._limit:
            return ("close", "nothing said" if self.state == "opening" else f"{self._limit:g}s follow-up ended")
        return None


class Resampler:
    """Converts 16-bit mono PCM between rates by linear interpolation, chunk by chunk.

    Pure Python so the unit tests need no install. 24 kHz in, 16 kHz out, is about 2% of one core.
    """

    def __init__(self, source_rate, target_rate=MIC_RATE):
        if source_rate <= 0 or target_rate <= 0:
            raise ValueError("rates must be positive")
        self.source_rate, self.target_rate = source_rate, target_rate
        self._step = source_rate / target_rate
        self._position = 0.0
        self._last = None

    def convert(self, pcm):
        if self.source_rate == self.target_rate:
            return pcm
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return b""
        # Index -1 is the last sample of the previous chunk, so interpolation crosses chunk edges.
        source = ([self._last] if self._last is not None else [samples[0]]) + list(samples)
        out = array("h")
        position = self._position + 1
        limit = len(source) - 1
        while position < limit:
            base = int(position)
            frac = position - base
            value = source[base] + (source[base + 1] - source[base]) * frac
            out.append(max(-32768, min(32767, int(round(value)))))
            position += self._step
        self._position = position - 1 - len(samples)
        self._last = samples[-1]
        if sys.byteorder != "little":
            out.byteswap()
        return out.tobytes()


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
    rate = hello.get("input_rate", MIC_RATE)
    if rate not in INPUT_RATES:
        return None
    return {
        "barge_in": hello.get("barge_in") is True,
        "input_rate": rate,
        # Short windows (04 5.3) for clients that open per conversation, such as the iPhone's Talk.
        "follow_up": hello.get("follow_up") is True,
        # Only the client ends the session, apart from the hard limit: the iPhone's Talk takes a
        # session closed from here for a dropped line, retries, then falls back to Apple speech
        # and the system voice (2026-11-11). Windows and goodbyes put it on standby instead.
        "client_ends": hello.get("client_ends") is True,
    }
