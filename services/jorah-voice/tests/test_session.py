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
        sleep = options.pop("sleep", no_wait)
        self.session = VoiceSession(
            self.ears, self.listener, self.speaker, self.brain,
            send_json, send_audio, on_close, sleep=sleep, **options,
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


class SlowBrain(FakeBrain):
    """First text only after `delay` real seconds, as when Jorah uses a tool first."""

    def __init__(self, delay, deltas):
        super().__init__(deltas)
        self.delay = delay

    def stream(self, prompt):
        import time
        time.sleep(self.delay)
        yield from super().stream(prompt)


async def short_sleep(seconds):
    await asyncio.sleep(min(seconds, 0.05))


class OneMoment(unittest.IsolatedAsyncioTestCase):
    async def test_a_slow_reply_gets_one_moment_first(self):
        h = Harness(brain=SlowBrain(0.4, ["Done. ", "It's cloned."]), filler_seconds=2.5, sleep=short_sleep)
        await h.say()
        await h.settle()
        self.assertEqual(h.speaker.lines, ["One moment.", "Done.", "It's cloned."])
        # The filler isn't the reply: first audio is still timed from the real answer.
        self.assertEqual(len(h.session.numbers["first_audio"]), 1)

    async def test_a_quick_reply_gets_no_filler(self):
        h = Harness(filler_seconds=2.5, sleep=short_sleep)
        await h.say()
        await h.settle()
        self.assertEqual(h.speaker.lines, ["Hi Adam.", "All good."])

    async def test_off_by_default(self):
        h = Harness(brain=SlowBrain(0.2, ["Done."]), sleep=short_sleep)
        await h.say()
        await h.settle()
        self.assertEqual(h.speaker.lines, ["Done."])


class ShortWindows(unittest.IsolatedAsyncioTestCase):
    """Voice plan 04 5.3, for clients that open a session per conversation."""

    def harness(self, text="Hello there", **options):
        self.now = [0.0]
        return Harness(text=text, clock=lambda: self.now[0], follow_up=True, **options)

    async def watch_once(self, h):
        h.session.closed_before = h.session.closed
        task = asyncio.create_task(h.session.watch())
        for _ in range(5):
            await asyncio.sleep(0)
        if not h.session.closed:
            h.session.closed = True
        await asyncio.wait_for(task, 2)

    def reasons(self, h):
        return [m.get("reason") for m in h.sent if m["type"] == "closed"]

    async def test_nothing_said_closes_after_five_seconds(self):
        h = self.harness()
        self.now[0] = 5
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), ["nothing said"])

    async def test_four_seconds_is_not_enough(self):
        h = self.harness()
        self.now[0] = 4
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), [])

    async def test_eight_seconds_after_a_reply_closes(self):
        h = self.harness()
        await h.say()
        await h.settle()
        self.now[0] += 8
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), ["8s follow-up ended"])

    async def test_a_question_gets_twelve_seconds(self):
        h = self.harness(brain=FakeBrain(["Want the long version?"]))
        await h.say()
        await h.settle()
        self.now[0] += 8
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), [])
        h.session.closed = False
        self.now[0] += 4
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), ["12s follow-up ended"])

    async def test_thanks_closes_at_once_without_the_brain(self):
        h = self.harness(text="Thanks.")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        self.assertEqual(h.speaker.lines, [])
        self.assertEqual(self.reasons(h), ["said thanks"])

    async def test_stay_with_me_keeps_the_mic_open_for_two_minutes_of_quiet(self):
        h = self.harness(text="Stay with me.")
        await h.say()
        await h.settle()
        self.assertEqual(h.brain.prompts, [])
        self.assertEqual(h.speaker.lines, ["I'm here."])
        self.now[0] += 60
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), [])
        h.session.closed = False
        self.now[0] += 60
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), ["120s of quiet"])

    async def test_stay_warns_before_the_ten_minute_cap(self):
        h = self.harness(text="Stay with me.")
        await h.say()
        await h.settle()
        h.session._follow_up.stay_quiet = 10_000
        self.now[0] = 580
        await self.watch_once(h)
        await h.settle()
        self.assertIn("I'll stop listening in half a minute.", h.speaker.lines)
        h.session.closed = False
        self.now[0] = 601
        await self.watch_once(h)
        self.assertEqual(self.reasons(h), ["10 minute stay limit"])

    async def test_without_the_option_the_old_sixty_seconds_hold(self):
        now = [0.0]
        h = Harness(clock=lambda: now[0])
        now[0] = 30
        task = asyncio.create_task(h.session.watch())
        for _ in range(5):
            await asyncio.sleep(0)
        h.session.closed = True
        await task
        self.assertEqual([m for m in h.sent if m["type"] == "closed"], [])


class ClientEnds(unittest.IsolatedAsyncioTestCase):
    """iPhone Talk: a session closed from the PC makes the app fall back to Apple speech (2026-11-11)."""

    def harness(self, text="Hello there", **options):
        self.now = [0.0]
        return Harness(text=text, clock=lambda: self.now[0], client_ends=True, **options)

    async def watch_once(self, h):
        task = asyncio.create_task(h.session.watch())
        for _ in range(5):
            await asyncio.sleep(0)
        if not h.session.closed:
            h.session.closed = True
        await asyncio.wait_for(task, 2)
        h.session.closed = False

    def closes(self, h):
        return [m for m in h.sent if m["type"] == "closed"]

    async def test_minutes_of_quiet_after_a_reply_keep_it_open(self):
        h = self.harness()
        await h.say()
        await h.settle()
        self.now[0] += 180
        await self.watch_once(h)
        self.assertEqual(self.closes(h), [])
        self.assertFalse(h.session.standby)

    async def test_a_question_three_minutes_later_is_answered(self):
        h = self.harness()
        await h.say()
        await h.settle()
        self.now[0] += 180
        await self.watch_once(h)
        await h.say()
        await h.settle()
        self.assertEqual(len(h.brain.prompts), 2)

    async def test_thanks_goes_on_standby_without_closing(self):
        h = self.harness(text="Thanks.")
        await h.say()
        await h.settle()
        self.assertTrue(h.session.standby)
        self.assertEqual(self.closes(h), [])
        self.assertEqual([m.get("reason") for m in h.sent if m["type"] == "standby"], ["said thanks"])

    async def test_on_standby_nothing_is_heard(self):
        h = self.harness(text="Goodbye.")
        await h.say()
        await h.settle()
        self.assertEqual(h.speaker.lines, ["Talk soon."])
        h.listener.text = "What's the weather?"
        heard = len(h.listener.heard)
        await h.say()
        await h.settle()
        self.assertEqual(len(h.listener.heard), heard)
        self.assertEqual(h.brain.prompts, [])

    async def test_the_hard_limit_still_closes(self):
        h = self.harness()
        self.now[0] = 1800
        await self.watch_once(h)
        self.assertEqual([m["reason"] for m in self.closes(h)], ["30 minute limit"])


class Rates(unittest.TestCase):
    def test_24_khz_becomes_16_khz(self):
        from array import array
        from jorah_voice.core import Resampler
        r = Resampler(24000)
        chunk = array("h", range(0, 4800, 10)).tobytes()  # 480 samples, 20 ms
        out = b"".join(r.convert(chunk) for _ in range(50))
        self.assertEqual(len(out) // 2, 16000)

    def test_16_khz_passes_through(self):
        from jorah_voice.core import Resampler
        self.assertEqual(Resampler(16000).convert(b"\1\2\3\4"), b"\1\2\3\4")


class Hello(unittest.TestCase):
    TOKEN = "t" * 40

    def hello(self, **fields):
        return json.dumps({"type": "hello", **fields})

    def test_right_token(self):
        plain = {"barge_in": False, "input_rate": 16000, "follow_up": False, "client_ends": False}
        self.assertEqual(parse_hello(self.hello(token=self.TOKEN), self.TOKEN), plain)
        self.assertEqual(parse_hello(self.hello(token=self.TOKEN, barge_in=True), self.TOKEN), {**plain, "barge_in": True})

    def test_the_talk_relay_options(self):
        hello = parse_hello(self.hello(token=self.TOKEN, input_rate=24000, client_ends=True), self.TOKEN)
        self.assertEqual(hello, {"barge_in": False, "input_rate": 24000, "follow_up": False, "client_ends": True})

    def test_an_unknown_rate_is_refused(self):
        self.assertIsNone(parse_hello(self.hello(token=self.TOKEN, input_rate=44100), self.TOKEN))

    def test_refused(self):
        for bad in (self.hello(token="wrong"), self.hello(), self.hello(token=5), "not json", "[]", b"\0\0"):
            self.assertIsNone(parse_hello(bad, self.TOKEN), bad)


if __name__ == "__main__":
    unittest.main()
