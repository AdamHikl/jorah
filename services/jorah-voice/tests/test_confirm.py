from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.confirm import (
    ALLOWED_LINE,
    DENIED_LINE,
    GIVE_UP_LINE,
    LOCKED_LINE,
    PHRASE_MISSING_LINE,
    PHRASE_RETRY_LINES,
    RETRY_LINES,
    UNAVAILABLE_LINE,
    decide,
    is_leaving_pc,
)


def call(**overrides):
    base = dict(
        leaves_pc=False,
        seconds_since_asked=3.0,
        transcript="Yes, go ahead.",
        verdict_kind="adam",
        speech_seconds=2.0,
        phrase_set=False,
        phrase_matches=False,
        phrase_locked=False,
        attempts=0,
    )
    base.update(overrides)
    return decide(**base)


class ConfirmRules(unittest.TestCase):
    def test_severity_to_leaves_pc_fails_closed(self):
        self.assertFalse(is_leaving_pc("warning"))
        self.assertFalse(is_leaving_pc("info"))
        for sev in ("critical", None, "", "high", "unknown"):
            self.assertTrue(is_leaving_pc(sev), repr(sev))

    def test_all_yes_words_and_phrases(self):
        for phrase in (
            "Yes.", "Yeah, do it.", "Yep, confirm.", "Confirmed.", "Go ahead.",
            "Do it.", "Allow it.", "Sure.", "Approve.", "Ano.", "Áno, potvrď.",
            "Pokračuj.",
        ):
            r = call(transcript=phrase)
            self.assertEqual(r.outcome, "allow", phrase)
            self.assertEqual(r.line, ALLOWED_LINE)

    def test_no_wins_over_yes_and_honoured_from_anyone(self):
        for phrase in ("No.", "Nope.", "Don't.", "Deny.", "Cancel.", "Stop.", "Not now.", "Nie.", "Zruš.", "Yes, wait no, don't do it."):
            r = call(
                transcript=phrase,
                verdict_kind="someone_else",
                speech_seconds=0.4,
                phrase_locked=True,
                seconds_since_asked=50.0,
            )
            self.assertEqual(r.outcome, "deny", phrase)
            self.assertEqual(r.line, DENIED_LINE)

    def test_unrelated_turn_is_not_an_answer(self):
        for phrase in ("What is the weather in Bratislava?", "Are you sure about that?", "How do I do it?", "Read my email."):
            r = call(transcript=phrase)
            self.assertEqual(r.outcome, "not_an_answer", phrase)

    def test_window_over_20s_gives_up(self):
        r = call(seconds_since_asked=20.1)
        self.assertEqual(r.outcome, "give_up")
        self.assertEqual(r.line, GIVE_UP_LINE)

    def test_too_short_unsure_and_someone_else_retry_then_give_up(self):
        for kwargs in (
            {"speech_seconds": 1.49},
            {"verdict_kind": "unsure"},
            {"verdict_kind": "someone_else"},
        ):
            r0 = call(attempts=0, **kwargs)
            r1 = call(attempts=1, **kwargs)
            r2 = call(attempts=2, **kwargs)
            self.assertEqual(r0.outcome, "retry")
            self.assertEqual(r1.outcome, "retry")
            self.assertNotEqual(r0.line, r1.line)
            self.assertNotIn("say it a bit longer", r0.line.lower())
            self.assertNotIn("say it a bit longer", r1.line.lower())
            self.assertEqual(r2.outcome, "give_up")
            self.assertEqual(r2.line, GIVE_UP_LINE)

    def test_retry_lines_never_repeat_twice_in_a_row(self):
        lines = [call(verdict_kind="unsure", retry_index=i).line for i in range(8)]
        self.assertGreaterEqual(len(RETRY_LINES), 4)
        for prev, curr in zip(lines, lines[1:]):
            self.assertNotEqual(prev, curr)

    def test_leaves_pc_requires_phrase_set_and_matching(self):
        missing = call(leaves_pc=True, phrase_set=False, phrase_matches=False)
        self.assertEqual(missing.outcome, "give_up")
        self.assertEqual(missing.line, PHRASE_MISSING_LINE)

        wrong = call(leaves_pc=True, phrase_set=True, phrase_matches=False, attempts=0)
        self.assertEqual(wrong.outcome, "retry")
        self.assertTrue(wrong.phrase_failed)
        self.assertIn("phrase", wrong.line.lower())
        self.assertIn(wrong.line, PHRASE_RETRY_LINES)

        wrong1 = call(leaves_pc=True, phrase_set=True, phrase_matches=False, attempts=1)
        self.assertEqual(wrong1.outcome, "retry")
        self.assertNotEqual(wrong.line, wrong1.line)
        self.assertIn("phrase", wrong1.line.lower())

        wrong_speaker = call(leaves_pc=True, phrase_set=True, phrase_matches=False, verdict_kind="unsure", attempts=0)
        self.assertEqual(wrong_speaker.outcome, "retry")
        self.assertFalse(wrong_speaker.phrase_failed)
        self.assertIn(wrong_speaker.line, RETRY_LINES)

        phrase_only_leaves = call(leaves_pc=True, phrase_set=True, phrase_matches=True, transcript="copper river oak")
        self.assertEqual(phrase_only_leaves.outcome, "allow")

        phrase_only_local = call(leaves_pc=False, phrase_set=True, phrase_matches=True, transcript="copper river oak")
        self.assertEqual(phrase_only_local.outcome, "allow")

        no_with_phrase = call(leaves_pc=True, phrase_set=True, phrase_matches=True, transcript="no, copper river oak")
        self.assertEqual(no_with_phrase.outcome, "deny")

        ok = call(leaves_pc=True, phrase_set=True, phrase_matches=True)
        self.assertEqual(ok.outcome, "allow")
        self.assertFalse(ok.phrase_failed)

    def test_phrase_retry_lines_varied_and_never_repeat_twice_in_a_row(self):
        lines = [
            call(leaves_pc=True, phrase_set=True, phrase_matches=False, retry_index=i).line
            for i in range(8)
        ]
        self.assertGreaterEqual(len(PHRASE_RETRY_LINES), 2)
        for line in PHRASE_RETRY_LINES:
            self.assertIn("phrase", line.lower())
        for prev, curr in zip(lines, lines[1:]):
            self.assertNotEqual(prev, curr)

    def test_locked_and_unavailable_give_up_with_specific_lines(self):
        locked = call(phrase_locked=True)
        self.assertEqual(locked.outcome, "give_up")
        self.assertEqual(locked.line, LOCKED_LINE)

        unavail = call(verdict_kind="unavailable")
        self.assertEqual(unavail.outcome, "give_up")
        self.assertEqual(unavail.line, UNAVAILABLE_LINE)


if __name__ == "__main__":
    unittest.main()
