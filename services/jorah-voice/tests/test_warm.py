import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.brain import BrainError
from jorah_voice.warm import TRIES_PER_START, WARMUP_SESSION, WARMUP_TEXT, Warmer


class FakeBrain:
    def __init__(self, fail=False):
        self.prompts = []
        self.fail = fail

    def stream(self, text):
        self.prompts.append(text)
        if self.fail:
            raise BrainError("Gateway answered 500")
        yield "ready"


class Gateway:
    """A Gateway that started at `started` on the test clock, or is down when that is None."""

    def __init__(self):
        self.now = 1000.0
        self.started = 900.0

    def uptime(self):
        return None if self.started is None else self.now - self.started


class Warming(unittest.TestCase):
    def setUp(self):
        self.gateway = Gateway()
        self.brain = FakeBrain()
        self.lines = []
        self.warmer = Warmer(lambda: self.brain, self.gateway.uptime, clock=lambda: self.gateway.now, log=self.lines.append)

    def test_warms_once_per_gateway_start(self):
        self.assertTrue(self.warmer.check())
        self.gateway.now += 20
        self.assertFalse(self.warmer.check())
        self.gateway.now += 3600
        self.assertFalse(self.warmer.check())
        self.assertEqual(self.brain.prompts, [WARMUP_TEXT])

    def test_warms_again_after_a_restart(self):
        self.warmer.check()
        self.gateway.now += 600
        self.gateway.started = self.gateway.now - 15
        self.assertTrue(self.warmer.check())
        self.assertEqual(len(self.brain.prompts), 2)

    def test_does_nothing_while_the_gateway_is_down(self):
        self.gateway.started = None
        self.assertFalse(self.warmer.check())
        self.assertEqual(self.brain.prompts, [])

    def test_a_failing_warm_up_is_retried_only_a_little(self):
        self.brain.fail = True
        for _ in range(5):
            self.assertFalse(self.warmer.check())
            self.gateway.now += 20
        self.assertEqual(len(self.brain.prompts), TRIES_PER_START)
        self.assertIn("warm-up failed: BrainError: Gateway answered 500", self.lines)

    def test_never_uses_adams_session(self):
        self.assertNotEqual(WARMUP_SESSION, "agent:main:main")
        self.assertTrue(WARMUP_SESSION.startswith("agent:main:"))


if __name__ == "__main__":
    unittest.main()
