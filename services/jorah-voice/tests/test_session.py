import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.brain import BrainError
from jorah_voice.core import TurnEnd, parse_hello
from jorah_voice.session import FAILURE_LINE, VoiceSession


class FakeEars:
    def __init__(self):
        self.accepted = []
        self.pending = []
        self.speech = False
        self.quiet = 10.0

    def accept(self, pcm):
        self.accepted.append(pcm)

    def speech_now(self):
        return self.speech

    def quiet_seconds(self):
        return self.quiet

    def segments(self):
        found, self.pending = self.pending, []
        return found


class FakeListener:
    def __init__(self, text):
        self.text = text
        self.heard = []

    def transcribe(self, *pieces):
        self.heard.append(pieces)
        return self.text(pieces) if callable(self.text) else self.text


class FakeSpeaker:
    sample_rate = 24000

    def __init__(self):
        self.lines = []

    def synthesize(self, text):
        self.lines.append(text)
        return b"\0\0" * 4800


class FakeBrain:
    def __init__(self, deltas=(), error=None, hold=None):
        self.deltas, self.error, self.hold = deltas, error, hold
        self.prompts = []
        self.cancelled = False

    def stream(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        for delta in self.deltas:
            yield delta
        if self.hold:
            self.hold.wait(5)

    def cancel(self):
        self.cancelled = True
        if self.hold:
            self.hold.set()


class Harness:
    def __init__(self, text="Hello there", brain=None, **options):
        self.sent = []
        self.audio = []
        self.close_count = 0
        self.ears = FakeEars()
        self.speaker = FakeSpeaker()
        self.brain = brain or FakeBrain(["Hi Adam. ", "All good."])

        async def send_json(message):
            self.sent.append(message)

        async def send_audio(data):
            self.audio.append(data)

        async def on_close():
            self.close_count += 1

        async def no_wait(_seconds):
            await asyncio.sleep(0)

        self.listener = FakeListener(text)
        self.session = VoiceSession(
            self.ears, self.listener, self.speaker, self.brain,
            send_json, send_audio, on_close, sleep=no_wait, **options,
        )

    async def say(self, segment="segment"):
        self.ears.pending = [segment]
        await self.session.feed(b"\0\0")

    async def settle(self):
        if self.session._hearing:
            await asyncio.gather(self.session._hearing, return_exceptions=True)
        if self.session._turn:
            await asyncio.gather(self.session._turn, return_exceptions=True)

    def kinds(self):
        return [m["type"] for m in self.sent]

    def states(self):
        return [m["state"] for m in self.sent if m["type"] == "state"]


class Turns(unittest.IsolatedAsyncioTestCase):
    async def test_a_turn_speaks_each_sentence_and_ends_listening(self):
        h = Harness()
        await h.say()
        await h.settle()
        self.assertEqual(h.speaker.lines, ["Hi Adam.", "All good."])
        self.assertEqual(h.states(), ["thinking", "speaking", "listening"])
        self.assertIn({"type": "heard", "text": "Hello there"}, h.sent)
        self.assertEqual(len(h.audio), 4)
        self.assertEqual(h.brain.prompts[0], "Hello there")
        for name in ("transcribe", "end_pause", "first_token", "first_audio"):
            self.assertEqual(len(h.session.numbers[name]), 1)

    async def test_each_turn_sends_only_the_new_words_because_jorah_keeps_the_conversation(self):
        h = Harness()
        await h.say()
        await h.settle()
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, ["Hello there", "Hello there"])

    async def test_silence_transcribed_as_nothing_never_reaches_the_brain(self):
        h = Harness(text="  ...  ")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        self.assertEqual(h.states(), ["thinking", "listening"])

    async def test_stop_never_reaches_the_brain(self):
        h = Harness(text="Stop.")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        self.assertEqual(h.speaker.lines, [])

    async def test_goodbye_closes_the_session(self):
        h = Harness(text="Goodbye, Jorah.")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        self.assertEqual(h.speaker.lines, ["Talk soon."])
        self.assertTrue(h.session.closed)
        self.assertEqual(h.close_count, 1)
        self.assertEqual([m for m in h.sent if m["type"] == "closed"][0]["reason"], "said goodbye")

    async def test_a_failed_brain_is_said_out_loud(self):
        h = Harness(brain=FakeBrain(error=BrainError("down")))
        await h.say()
        await h.settle()
        self.assertEqual(h.speaker.lines, [FAILURE_LINE])
        self.assertEqual(h.session.numbers["first_token"], [])


class EndOfTurn(unittest.IsolatedAsyncioTestCase):
    def harness(self, text):
        h = Harness(text=text, turn_end=TurnEnd(0.3, 0.9))
        h.ears.quiet = 0.3
        return h

    async def test_a_finished_sentence_goes_to_jorah_after_the_short_pause(self):
        h = self.harness("Turn off the lights.")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, ["Turn off the lights."])
        self.assertEqual(h.session.numbers["end_pause"], [0.3])

    async def test_an_open_sentence_is_held_until_the_long_pause(self):
        h = self.harness("I want to book a table for.")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        self.assertEqual(h.states(), [])
        h.ears.quiet = 0.9
        await h.session.feed(b"\0\0")
        await h.settle()
        self.assertEqual(h.brain.prompts, ["I want to book a table for."])

    async def test_speech_after_a_pause_joins_the_same_turn(self):
        h = self.harness(lambda pieces: "I want to book a table for." if len(pieces) == 1 else "I want to book a table for four.")
        await h.say("first")
        await h.settle()
        h.ears.quiet = 0.0
        await h.session.feed(b"\0\0")
        h.ears.quiet = 0.3
        await h.say("second")
        await h.settle()
        self.assertEqual(h.listener.heard[-1], ("first", "second"))
        self.assertEqual(h.brain.prompts, ["I want to book a table for four."])

    async def test_the_early_transcript_is_used_once_the_pause_is_long_enough(self):
        h = Harness(text="Turn off the lights.", turn_end=TurnEnd(0.6, 1.0))
        h.ears.quiet = 0.3
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        h.ears.quiet = 0.6
        await h.session.feed(b"\0\0")
        await h.settle()
        self.assertEqual(h.brain.prompts, ["Turn off the lights."])
        self.assertEqual(len(h.listener.heard), 1)

    async def test_nothing_is_sent_while_he_is_talking_again(self):
        h = self.harness("Turn off the lights.")
        h.ears.speech = True
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        h.ears.speech = False
        await h.session.feed(b"\0\0")
        await h.settle()
        self.assertEqual(h.brain.prompts, ["Turn off the lights."])

    async def test_a_transcript_of_older_audio_is_never_sent(self):
        import threading

        gate = threading.Event()

        def slow(pieces):
            if len(pieces) == 1:
                gate.wait(5)
                return "Stale."
            return "Both pieces."

        h = self.harness(slow)
        await h.say("first")
        h.ears.quiet = 0.0
        await h.say("second")
        h.ears.quiet = 0.3
        gate.set()
        for task in list(asyncio.all_tasks()):
            if task is not asyncio.current_task():
                await asyncio.gather(task, return_exceptions=True)
        await h.session.feed(b"\0\0")
        await h.settle()
        self.assertEqual(h.brain.prompts, ["Both pieces."])


class Mic(unittest.IsolatedAsyncioTestCase):
    async def held_turn(self, **options):
        import threading

        hold = threading.Event()
        h = Harness(brain=FakeBrain(["Thinking about it. "], hold=hold), **options)
        await h.say()
        for _ in range(200):
            if h.audio:
                break
            await asyncio.sleep(0.005)
        self.assertTrue(h.session.busy())
        return h

    async def test_mic_is_ignored_while_he_talks_by_default(self):
        h = await self.held_turn()
        before = len(h.ears.accepted)
        h.ears.speech = True
        await h.session.feed(b"\0\0")
        self.assertEqual(len(h.ears.accepted), before)
        self.assertTrue(h.session.busy())
        await h.session.interrupt()

    async def test_talking_over_him_cuts_him_off_when_switched_on(self):
        h = await self.held_turn(barge_in=True)
        h.ears.speech = True
        await h.session.feed(b"\0\0")
        self.assertFalse(h.session.busy())
        self.assertTrue(h.brain.cancelled)
        self.assertIn("cut", h.kinds())

    async def test_enter_cuts_him_off(self):
        h = await self.held_turn()
        await h.session.interrupt()
        self.assertFalse(h.session.busy())
        self.assertTrue(h.brain.cancelled)
        self.assertEqual(h.states()[-1], "listening")


class Closing(unittest.IsolatedAsyncioTestCase):
    async def test_quiet_closes_the_session(self):
        now = [0.0]
        h = Harness(clock=lambda: now[0], idle_seconds=60)
        now[0] = 61
        await asyncio.wait_for(h.session.watch(), 2)
        self.assertEqual(h.close_count, 1)
        self.assertIn("60s of quiet", [m.get("reason") for m in h.sent])

    async def test_the_hard_limit_closes_a_session_that_keeps_talking(self):
        now = [0.0]
        h = Harness(clock=lambda: now[0], max_seconds=1800)
        now[0] = 1800
        h.session._idle.touch()
        await asyncio.wait_for(h.session.watch(), 2)
        self.assertIn("30 minute limit", [m.get("reason") for m in h.sent])

    async def test_no_samples_read_as_none_not_zero(self):
        self.assertIsNone(Harness().session.summary()["first_audio"]["median"])


class Hello(unittest.TestCase):
    TOKEN = "t" * 40

    def hello(self, **fields):
        return json.dumps({"type": "hello", **fields})

    def test_right_token(self):
        self.assertEqual(parse_hello(self.hello(token=self.TOKEN), self.TOKEN), {"barge_in": False})
        self.assertEqual(parse_hello(self.hello(token=self.TOKEN, barge_in=True), self.TOKEN), {"barge_in": True})

    def test_refused(self):
        for bad in (self.hello(token="wrong"), self.hello(), self.hello(token=5), "not json", "[]", b"\0\0"):
            self.assertIsNone(parse_hello(bad, self.TOKEN), bad)


if __name__ == "__main__":
    unittest.main()
