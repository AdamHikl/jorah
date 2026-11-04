"""One conversation, from audio arriving to audio going back. Knows nothing about the network."""

import asyncio
import time

from .brain import BrainError
from .core import History, IdleClock, SentenceChunker, classify, percentile

BLOCK_SECONDS = 0.1
BYTES_PER_SAMPLE = 2
FAILURE_LINE = "I can't reach my brain right now."
EMPTY_LINE = "I didn't get an answer. Try me again."


class VoiceSession:
    def __init__(self, ears, listener, speaker, brain, send_json, send_audio, on_close, *,
                 barge_in=False, idle_seconds=60, max_seconds=1800,
                 clock=time.monotonic, sleep=asyncio.sleep, lead=0.2):
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
        self._idle = IdleClock(idle_seconds, now=clock)
        self._started = clock()
        self._history = History()
        self._turn = None
        self.closed = False
        self.numbers = {"transcribe": [], "first_token": [], "first_audio": []}

    def busy(self):
        return self._turn is not None and not self._turn.done()

    async def feed(self, pcm):
        """Take mic audio. While Jorah is busy it is ignored, unless talking over him is switched on."""
        if self.closed:
            return
        if self.busy() and not self._barge_in:
            self._idle.touch()
            return
        self._ears.accept(pcm)
        if self.busy() and self._ears.speech_now():
            await self.interrupt()
        for segment in self._ears.segments():
            await self.interrupt(quiet=True)
            self._turn = asyncio.create_task(self._run_turn(segment))

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
            elif not self.busy() and self._idle.expired():
                await self.close(f"{self._idle_seconds}s of quiet")

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

    async def _run_turn(self, segment):
        await self._state("thinking")
        started = self._clock()
        text = await asyncio.to_thread(self._listener.transcribe, segment)
        heard_at = self._clock()
        self.numbers["transcribe"].append(heard_at - started)
        kind = classify(text)
        if kind == "empty":
            await self._state("listening")
            return
        self._idle.touch()
        await self._send_json({"type": "heard", "text": text})
        if kind in ("stop", "cancel"):
            await self._state("listening")
            return
        if kind == "end":
            await self._speak_lines(["Talk soon."], heard_at, record=False)
            await self.close("said goodbye")
            return
        self._history.add("Adam", text)
        await self._reply(heard_at)
        self._idle.touch()
        await self._state("listening")

    async def _reply(self, heard_at):
        sentences = asyncio.Queue()
        speaking = asyncio.create_task(self._speak_queue(sentences, heard_at, record=True))
        chunker = SentenceChunker()
        reply = []
        try:
            first_token = None
            async for delta in self._stream(self._history.as_prompt()):
                if first_token is None:
                    first_token = self._clock()
                    self.numbers["first_token"].append(first_token - heard_at)
                reply.append(delta)
                for sentence in chunker.feed(delta):
                    sentences.put_nowait(sentence)
            for sentence in chunker.flush():
                sentences.put_nowait(sentence)
            if not reply:
                sentences.put_nowait(EMPTY_LINE)
            sentences.put_nowait(None)
            await speaking
        except BrainError as error:
            print(f"brain failed: {error}", flush=True)
            self._history.drop_last()
            reply = []
            sentences.put_nowait(FAILURE_LINE)
            sentences.put_nowait(None)
            await speaking
        except asyncio.CancelledError:
            speaking.cancel()
            await asyncio.gather(speaking, return_exceptions=True)
            raise
        finally:
            if reply:
                self._history.add("Jorah", "".join(reply))

    async def _stream(self, prompt):
        """Run the blocking brain call on a thread and hand its text to this loop."""
        loop = asyncio.get_running_loop()
        items = asyncio.Queue()

        def pump():
            try:
                for delta in self._brain.stream(prompt):
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

    async def _speak_queue(self, sentences, heard_at, record):
        first = True
        while True:
            sentence = await sentences.get()
            if sentence is None:
                break
            await self._send_json({"type": "reply", "text": sentence})
            pcm = await asyncio.to_thread(self._speaker.synthesize, sentence)
            if first:
                first = False
                if record:
                    self.numbers["first_audio"].append(self._clock() - heard_at)
                await self._state("speaking")
            await self._send_paced(pcm)
        # What's already sent is still playing at the far end.
        await self._sleep(self._lead)

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
