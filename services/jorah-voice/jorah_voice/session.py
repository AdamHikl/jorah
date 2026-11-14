"""One conversation, from audio arriving to audio going back. Knows nothing about the network."""

import asyncio
import json
import threading
import time
from contextlib import aclosing

from .brain import BrainError
from .core import FollowUp, IdleClock, Resampler, SentenceChunker, TurnEnd, classify, join_waiting, percentile

BLOCK_SECONDS = 0.1
BYTES_PER_SAMPLE = 2
FAILURE_LINE = "I can't reach my brain right now."
EMPTY_LINE = "I didn't get an answer. Try me again."
STAY_LINE = "I'm here."
# Said once when no reply text has come for a while, which mostly means Jorah is using a tool
# (2026-11-11: GitHub turns took 7 to 21 s to the first word), so the quiet isn't a dead line.
FILLER_LINE = "One moment."


class Filler(str):
    """A line Jorah says while waiting: not the reply, so it isn't timed or joined to it."""
STAY_WARNING = "I'll stop listening in half a minute."


# Longest piece of text spoken in one go, after the first sentence of a reply.
SPOKEN_CHUNK_CHARS = 300


class VoiceSession:
    def __init__(self, ears, listener, speaker, brain, send_json, send_audio, on_close, *,
                 barge_in=False, idle_seconds=60, max_seconds=1800,
                 clock=time.monotonic, sleep=asyncio.sleep, lead=0.2, turn_end=None,
                 follow_up=False, input_rate=16000, filler_seconds=None, client_ends=False,
                 stream_speech=True, log=None):
        self._ears = ears
        self._listener = listener
        self._speaker = speaker
        self._brain = brain
        self._send_json = send_json
        self._send_audio = send_audio
        self._on_close = on_close
        self._barge_in = barge_in
        self._idle_seconds = idle_seconds
        self._max_seconds = max_seconds
        self._clock = clock
        self._sleep = sleep
        self._lead = lead
        self._turn_end = turn_end or TurnEnd(0.6, 0.6)
        # Speech segments of the turn in progress, held until a long enough pause ends the turn.
        self._held = []
        self._heard = None
        self._hearing = None
        self._version = 0
        self._idle = IdleClock(idle_seconds, now=clock)
        self._started = clock()
        self._turn = None
        # Short windows from voice plan 04 5.3, for clients that open per conversation.
        self._follow_up = FollowUp(clock()) if follow_up else None
        self._resampler = Resampler(input_rate)
        self._filler_seconds = filler_seconds
        self._client_ends = client_ends
        # Speakers that can (Qwen3-TTS) send a sentence's audio as it's made, not when it's done.
        self._stream_speech = stream_speech
        self._log = log or (lambda line: print(line, flush=True))
        # On standby, audio is dropped unheard until the client hangs up.
        self.standby = False
        self.closed = False
        self.numbers = {"transcribe": [], "end_pause": [], "first_token": [], "first_sentence": [], "first_audio": []}

    def busy(self):
        return self._turn is not None and not self._turn.done()

    async def feed(self, pcm):
        """Take mic audio. While Jorah is busy it is ignored, unless talking over him is switched on."""
        if self.closed or self.standby:
            return
        if self.busy() and not self._barge_in:
            self._idle.touch()
            return
        self._ears.accept(self._resampler.convert(pcm))
        speaking = self._ears.speech_now()
        if self.busy() and speaking:
            await self.interrupt()
        segments = self._ears.segments()
        if self._follow_up and (speaking or segments):
            self._follow_up.heard(self._clock())
        if segments:
            self._held.extend(segments)
            self._listen()
        await self._maybe_end()

    def _listen(self):
        """Transcribe everything held so far. A newer segment makes an older transcript stale."""
        self._version += 1
        self._heard = None
        self._hearing = asyncio.create_task(self._hear(self._version, list(self._held)))

    async def _hear(self, version, held):
        started = self._clock()
        text = await asyncio.to_thread(self._listener.transcribe, *held)
        if version != self._version or self.closed:
            return
        self._heard = (text, self._clock() - started)
        await self._maybe_end()

    async def _maybe_end(self):
        """Start Jorah's turn once the transcript is in and the pause is long enough for it."""
        if self._heard is None:
            return
        text, seconds = self._heard
        quiet = self._ears.quiet_seconds()
        if not self._turn_end.done(text, quiet, self._ears.speech_now()):
            return
        self._held, self._heard = [], None
        self._version += 1
        self.numbers["transcribe"].append(seconds)
        self.numbers["end_pause"].append(quiet)
        await self.interrupt(quiet=True)
        marks = {"end_pause": round(quiet, 2), "transcribe": round(seconds, 2)}
        self._turn = asyncio.create_task(self._run_turn(text, marks))

    async def interrupt(self, quiet=False):
        """Stop thinking and speaking at once."""
        if not self.busy():
            return
        self._brain.cancel()
        self._turn.cancel()
        await asyncio.gather(self._turn, return_exceptions=True)
        self._idle.touch()
        if not quiet:
            await self._send_json({"type": "cut"})
            await self._state("listening")

    async def watch(self):
        """Close the session after a quiet stretch or at the hard limit, so the mic can't stay open."""
        while not self.closed:
            await self._sleep(1)
            if self._clock() - self._started >= self._max_seconds:
                await self.interrupt(quiet=True)
                await self.close(f"{self._max_seconds // 60} minute limit")
            elif self.busy() or self._held or self.standby or self._client_ends:
                # A client that ends the session itself keeps it open through quiet:
                # Adam ends Talk with its control, or by saying goodbye or thanks.
                continue
            elif self._follow_up:
                verdict = self._follow_up.check(self._clock())
                if verdict and verdict[0] == "close":
                    await self.end(verdict[1])
                elif verdict:
                    self._turn = asyncio.create_task(self._say_only(STAY_WARNING))
            elif self._idle.expired():
                await self.end(f"{self._idle_seconds}s of quiet")

    async def end(self, reason):
        """End the conversation: close it, or go on standby if only the client may close it."""
        if not self._client_ends:
            await self.close(reason)
            return
        if self.standby or self.closed:
            return
        self.standby = True
        self._held, self._heard = [], None
        self._version += 1
        await self._send_json({"type": "standby", "reason": reason})
        await self._state("standby")

    async def close(self, reason):
        if self.closed:
            return
        self.closed = True
        await self._send_json({"type": "closed", "reason": reason, "numbers": self.summary()})
        await self._on_close()

    def summary(self):
        out = {}
        for name, values in self.numbers.items():
            out[name] = {
                "median": percentile(values, 0.5),
                "p90": percentile(values, 0.9),
                "turns": len(values),
            }
        return out

    async def _state(self, state):
        await self._send_json({"type": "state", "state": state})

    async def _run_turn(self, text, marks=None):
        await self._state("thinking")
        heard_at = self._clock()
        kind = classify(text)
        if kind == "empty":
            await self._state("listening")
            return
        self._idle.touch()
        await self._send_json({"type": "heard", "text": text})
        if kind in ("stop", "cancel"):
            self._replied("")
            await self._state("listening")
            return
        if kind == "end":
            await self._speak_lines(["Talk soon."], heard_at, record=False)
            await self.end("said goodbye")
            return
        if kind == "end_quietly":
            await self.end("said thanks")
            return
        if kind == "stay":
            if self._follow_up:
                self._follow_up.stay(self._clock())
            await self._speak_lines([STAY_LINE], heard_at, record=False)
            self._replied("")
            await self._state("listening")
            return
        marks = dict(marks or {})
        try:
            reply = await self._reply(text, heard_at, marks)
        finally:
            # Timing only, one line a turn. What was said is never logged.
            self._log(f"turn: {json.dumps(marks)}")
        self._idle.touch()
        self._replied(reply)
        await self._state("listening")

    def _replied(self, text):
        if self._follow_up:
            self._follow_up.replied(self._clock(), text)

    async def _say_only(self, line):
        """Speak a line of Jorah's own, such as a warning, without a turn from Adam."""
        await self._speak_lines([line], self._clock(), record=False)
        self._idle.touch()
        self._replied("")
        await self._state("listening")

    async def _reply(self, text, heard_at, marks=None):
        """Stream Jorah's answer and speak it. Fills `marks` with seconds from `heard_at`."""
        marks = {} if marks is None else marks
        sentences = asyncio.Queue()
        speaking = asyncio.create_task(self._speak_queue(sentences, heard_at, record=True, marks=marks))
        chunker = SentenceChunker()
        reply = []
        got_text = asyncio.Event()

        def since_heard():
            return round(self._clock() - heard_at, 2)

        def queue_sentence(sentence):
            if "first_sentence" not in marks:
                marks["first_sentence"] = since_heard()
                self.numbers["first_sentence"].append(marks["first_sentence"])
            sentences.put_nowait(sentence)

        async def filler():
            await self._sleep(self._filler_seconds)
            if not got_text.is_set():
                marks["filler"] = since_heard()
                sentences.put_nowait(Filler(FILLER_LINE))

        waiting = asyncio.create_task(filler()) if self._filler_seconds else None
        try:
            first_token = None
            async for delta in self._stream(text):
                if first_token is None:
                    got_text.set()
                    if waiting:
                        waiting.cancel()
                    first_token = self._clock()
                    self.numbers["first_token"].append(first_token - heard_at)
                    marks["first_token"] = round(first_token - heard_at, 2)
                reply.append(delta)
                for sentence in chunker.feed(delta):
                    queue_sentence(sentence)
            marks["reply_done"] = since_heard()
            for sentence in chunker.flush():
                queue_sentence(sentence)
            if not reply:
                sentences.put_nowait(EMPTY_LINE)
            sentences.put_nowait(None)
            await speaking
            marks["reply_chars"] = sum(len(part) for part in reply)
            return "".join(reply)
        except BrainError as error:
            print(f"brain failed: {error}", flush=True)
            marks["brain_failed"] = since_heard()
            sentences.put_nowait(FAILURE_LINE)
            sentences.put_nowait(None)
            await speaking
            return FAILURE_LINE
        except asyncio.CancelledError:
            marks["cut"] = since_heard()
            if waiting:
                waiting.cancel()
            speaking.cancel()
            await asyncio.gather(speaking, return_exceptions=True)
            raise

    async def _stream(self, text):
        """Run the blocking brain call on a thread and hand its text to this loop."""
        loop = asyncio.get_running_loop()
        items = asyncio.Queue()

        def pump():
            try:
                for delta in self._brain.stream(text):
                    loop.call_soon_threadsafe(items.put_nowait, ("text", delta))
                loop.call_soon_threadsafe(items.put_nowait, ("end", None))
            except Exception as error:
                loop.call_soon_threadsafe(items.put_nowait, ("error", error))

        loop.run_in_executor(None, pump)
        while True:
            kind, value = await items.get()
            if kind == "text":
                yield value
            elif kind == "end":
                return
            else:
                raise BrainError(str(value))

    async def _speak_lines(self, lines, heard_at, record):
        sentences = asyncio.Queue()
        for line in lines:
            sentences.put_nowait(line)
        sentences.put_nowait(None)
        await self._speak_queue(sentences, heard_at, record)

    async def _speak_queue(self, sentences, heard_at, record, marks=None):
        first = True
        ended = False
        while not ended:
            sentence = await sentences.get()
            if sentence is None:
                break
            if isinstance(sentence, Filler):
                await self._send_json({"type": "reply", "text": str(sentence)})
                async with aclosing(self._sound(str(sentence))) as sound:
                    async for pcm in sound:
                        await self._send_paced(pcm)
                continue
            if not first:
                # Kokoro shapes tone within one piece of text only, so sentences that are already
                # waiting are spoken together. The first stays alone, to start speaking sooner.
                limit = getattr(self._speaker, "chunk_chars", SPOKEN_CHUNK_CHARS)
                sentence, ended = join_waiting(sentence, sentences, limit)
            await self._send_json({"type": "reply", "text": sentence})
            async with aclosing(self._sound(sentence)) as sound:
                async for pcm in sound:
                    if first:
                        first = False
                        if record:
                            self.numbers["first_audio"].append(self._clock() - heard_at)
                            if marks is not None:
                                marks["first_audio"] = round(self._clock() - heard_at, 2)
                        await self._state("speaking")
                    await self._send_paced(pcm)
        # What's already sent is still playing at the far end.
        await self._sleep(self._lead)

    async def _sound(self, text):
        """Yield the audio for one piece of text: in pieces as it's made when the speaker can stream,
        otherwise all at once. Stopping early (Adam talks over Jorah) stops the speaker too."""
        stream = getattr(self._speaker, "stream", None) if self._stream_speech else None
        if stream is None:
            yield await asyncio.to_thread(self._speaker.synthesize, text)
            return
        loop = asyncio.get_running_loop()
        pieces = asyncio.Queue()
        stop = threading.Event()

        def pump():
            source = stream(text)
            try:
                for pcm in source:
                    if stop.is_set():
                        break
                    loop.call_soon_threadsafe(pieces.put_nowait, ("audio", pcm))
                loop.call_soon_threadsafe(pieces.put_nowait, ("end", None))
            except Exception as error:
                loop.call_soon_threadsafe(pieces.put_nowait, ("error", error))
            finally:
                source.close()

        loop.run_in_executor(None, pump)
        try:
            while True:
                kind, value = await pieces.get()
                if kind == "audio":
                    yield value
                elif kind == "end":
                    return
                else:
                    raise value
        finally:
            stop.set()

    async def _send_paced(self, pcm):
        """Send at about playing speed, so a cut-off is heard straight away and the mic stays shut until he's done."""
        block = int(self._speaker.sample_rate * BLOCK_SECONDS) * BYTES_PER_SAMPLE
        started = self._clock()
        sent = 0.0
        for offset in range(0, len(pcm), block):
            await self._send_audio(pcm[offset : offset + block])
            sent += BLOCK_SECONDS
            delay = started + sent - self._lead - self._clock()
            if delay > 0:
                await self._sleep(delay)
