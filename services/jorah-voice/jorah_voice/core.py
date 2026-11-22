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
# Read aloud the last long reply, of which only an overview was spoken. No model call.
READ_ALL = {
    "read the whole message", "read me the whole message", "read the full message", "read me the full message",
    "read it all", "read me it all", "read all of it", "read me all of it", "read me everything", "read everything",
    "read the whole thing", "read me the whole thing", "read the rest", "read me the rest",
}

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
    """Return "stop", "cancel", "end", "end_quietly", "stay", "read_all" or "talk" for a transcript.

    Only an exact phrase is a command, so none of these reach the model.
    """
    command = normalize_command(text)
    if not command:
        return "empty"
    unnamed = re.sub(r"^(?:hey |ok |okay )?jorah |(?: jorah)$", "", command)
    if command in READ_ALL or unnamed in READ_ALL or unnamed.removesuffix(" please") in READ_ALL:
        return "read_all"
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


_FENCED = re.compile(r"(```|~~~).*?(?:\1|$)", re.DOTALL)
_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>()\]]+", re.IGNORECASE)
_INLINE_CODE = re.compile(r"`([^`\n]*)`")
# Keys, tokens, UUIDs: long runs mixing letters and digits.
_LONG_TOKEN = re.compile(r"(?<![\w/])(?=[\w+/=-]*\d)(?=[\w+/=-]*[A-Za-z])[\w+/=-]{16,}")
# Hashes and commit ids: 7 or more hex characters with at least one digit and one letter, so
# "1234567" and "decade" stay as they are.
_HEX = re.compile(r"\b(?:sha256:)?(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{7,}\b")
_PATH = re.compile(r"(?<![\w/:.])(?:~|\.{1,2})?/(?:[\w.@+-]+/)+(?:[\w.@+-]*[\w@+-])?")
_SPACE_BEFORE_STOP = re.compile(r"\s+([.,!?;:])")
_LIST_MARK = re.compile(r"^\s*(?:[-*•+]|\d{1,2}[.)])\s+")
_RULE = re.compile(r"^[\s|:=_*~-]*$")


def speakable(text):
    """Turn one piece of reply text into words worth hearing: links, hashes, keys, file paths and code
    become "a link", "a long code", "a file path" and "a code block", and list marks and markup go."""
    if _RULE.match(text):
        return ""
    text = _FENCED.sub(" a code block. ", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("a link", text)
    text = _INLINE_CODE.sub(lambda m: m.group(1) if len(m.group(1)) <= 24 and "/" not in m.group(1) else "a long code", text)
    text = _PATH.sub("a file path", text)
    text = _LONG_TOKEN.sub("a long code", text)
    text = _HEX.sub("a long code", text)
    text = _LIST_MARK.sub("", text)
    return _SPACE_BEFORE_STOP.sub(r"\1", clean_for_speech(text))


_FENCE_LINE = re.compile(r"^\s*(?:```|~~~)")
CODE_BLOCK_LINE = "A code block."


class SentenceChunker:
    """Turn streamed text into speakable sentences, so speech can start before the reply ends.

    A line break ends a sentence too, so list items and headings are spoken one at a time, and a
    fenced code block is spoken as "A code block." Each piece goes through `speakable`.
    """

    def __init__(self, max_chars=220):
        self._buffer = ""
        self._max_chars = max_chars
        self._in_fence = False
        # The buffer starts a line, so a list mark there ("1. ", "- ") isn't read as a sentence end.
        self._line_start = True

    def feed(self, delta):
        self._buffer += delta
        pieces = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            pieces.extend(self._line(line))
            self._line_start = True
        if not self._in_fence:
            if self._line_start:
                self._buffer = _LIST_MARK.sub("", self._buffer, count=1)
            done, self._buffer = self._split(self._buffer, final=False)
            if done:
                self._line_start = False
            pieces.extend(done)
        return self._speakable(pieces)

    def flush(self):
        rest, self._buffer = self._buffer, ""
        pieces = [] if self._in_fence or _FENCE_LINE.match(rest) else self._line(rest)
        self._in_fence = False
        self._line_start = True
        return self._speakable(pieces)

    def _line(self, line):
        if _FENCE_LINE.match(line):
            self._in_fence = not self._in_fence
            return [CODE_BLOCK_LINE] if self._in_fence else []
        if self._in_fence or _RULE.match(line):
            return []  # inside code, or a blank line, rule or table border
        if self._line_start:
            line = _LIST_MARK.sub("", line, count=1)
        pieces, _ = self._split(line, final=True)
        # A line that ends without a full stop, such as a list item, still ends where the line does.
        if pieces and pieces[-1].rstrip()[-1:] not in (".", "?", "!", ":", ";", ""):
            pieces[-1] = pieces[-1].rstrip() + "."
        return pieces

    def _split(self, text, final):
        """Whole sentences in `text`, and what's left. With `final`, what's left is a sentence too."""
        sentences = []
        start = 0
        for match in _SENTENCE_END.finditer(text):
            candidate = text[start : match.start()] + match.group(0).rstrip()
            if _ABBREVIATION.search(candidate.strip()):
                continue
            sentences.append(candidate)
            start = match.end()
        rest = text[start:]
        while len(rest) > self._max_chars:
            cut = rest.rfind(" ", 0, self._max_chars)
            cut = cut if cut > 0 else self._max_chars
            sentences.append(rest[:cut])
            rest = rest[cut:].lstrip()
            if not final:
                break
        if final:
            sentences.append(rest)
            rest = ""
        return sentences, rest

    @staticmethod
    def _speakable(pieces):
        return [s for s in (speakable(p) for p in pieces) if s]


def speakable_sentences(text):
    """All of `text` as speakable sentences, such as a full message read on request."""
    chunker = SentenceChunker()
    return chunker.feed(text + "\n") + chunker.flush()


# The line between the spoken overview and the full message (brain.VOICE_NOTE asks for it).
_MARK_LINE = re.compile(r"^[ \t>*_#-]*full message:?[ \t*_]*$", re.IGNORECASE)
_MARK_AFTER_SENTENCE = re.compile(r"(?<=[.!?])[ \t]+[*_]*full message:[ \t*_]*$", re.IGNORECASE)
_MARK_TEXT = "full message:"
_MARK_START = re.compile(r"(?:^|(?<=[.!?])[ \t]+)[ \t>*_#-]*")


class OverviewSplit:
    """Splits a streamed reply at the line reading "Full message:".

    `feed` returns the text before that line as soon as it can't be the start of the line itself,
    so speech isn't held up. After the line, everything goes to `full` and nothing more is returned.
    A reply without the line is all overview, and `full` stays None.
    """

    def __init__(self):
        self._tail = ""
        self.full = None

    def feed(self, delta):
        if self.full is not None:
            self.full += delta
            return ""
        text = self._tail + delta
        out = ""
        while "\n" in text:
            line, rest = text.split("\n", 1)
            before = self._overview_before_mark(line)
            if before is not None:
                self.full, self._tail = rest, ""
                return out + before
            out += line + "\n"
            text = rest
        hold = self._hold_from(text)
        self._tail = text[hold:]
        return out + text[:hold]

    def finish(self):
        """The rest of the overview once the reply has ended."""
        if self.full is not None:
            return ""
        tail, self._tail = self._tail, ""
        before = self._overview_before_mark(tail)
        if before is not None:
            self.full = ""
            return before
        return tail

    @staticmethod
    def _overview_before_mark(line):
        """The overview text on a line that is, or ends with, the mark; None if it isn't one."""
        if _MARK_LINE.match(line):
            return ""
        found = _MARK_AFTER_SENTENCE.search(line)
        return line[: found.start()] if found else None

    @staticmethod
    def _hold_from(tail):
        """Where in an unfinished line the mark could be starting, or its end if nowhere."""
        for found in _MARK_START.finditer(tail):
            rest = tail[found.end():].lower()
            if rest and _MARK_TEXT.startswith(rest[: len(_MARK_TEXT)]) and len(rest) <= len(_MARK_TEXT) + 4:
                return found.start()
        return len(tail)


class LastFullMessage:
    """The full text of the last long reply, for "read the whole message". Memory only: never logged or
    written to disk, gone after `keep_seconds` or a restart."""

    def __init__(self, keep_seconds=1800, clock=time.monotonic):
        self._keep = keep_seconds
        self._clock = clock
        self._text = None
        self._at = 0.0

    def keep(self, text):
        self._text, self._at = text, self._clock()

    def get(self):
        if self._text and self._clock() - self._at <= self._keep:
            return self._text
        self._text = None
        return None


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
    if hello.get("purpose") == "settings":
        return {"purpose": "settings"}
    rate = hello.get("input_rate", MIC_RATE)
    if rate not in INPUT_RATES:
        return None
    return {
        "barge_in": hello.get("barge_in") is True,
        "input_rate": rate,
        # Short windows (04 5.3) for clients that open per conversation, such as the iPhone's Talk.
        "follow_up": hello.get("follow_up") is True,
        # The client shows `full_reply` messages, so a long reply's rest is on Adam's screen.
        "shows_full": hello.get("shows_full") is True,
        # Only the client ends the session, apart from the hard limit: the iPhone's Talk takes a
        # session closed from here for a dropped line, retries, then falls back to Apple speech
        # and the system voice (2026-11-11). Windows and goodbyes put it on standby instead.
        "client_ends": hello.get("client_ends") is True,
    }
