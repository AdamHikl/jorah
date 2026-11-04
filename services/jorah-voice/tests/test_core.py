import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.core import History, IdleClock, SentenceChunker, classify, clean_for_speech, percentile


class Classify(unittest.TestCase):
    def test_exact_commands(self):
        self.assertEqual(classify("Stop."), "stop")
        self.assertEqual(classify("cancel that"), "cancel")
        self.assertEqual(classify("Goodbye, Jorah!"), "end")

    def test_a_command_word_inside_a_sentence_is_just_talk(self):
        self.assertEqual(classify("How do I stop a robot arm?"), "talk")
        self.assertEqual(classify("Should I cancel that meeting?"), "talk")

    def test_empty(self):
        self.assertEqual(classify("  ... "), "empty")


class Chunker(unittest.TestCase):
    def test_sentences_come_out_as_soon_as_they_end(self):
        chunker = SentenceChunker()
        self.assertEqual(chunker.feed("Hello there"), [])
        self.assertEqual(chunker.feed(". How are"), ["Hello there."])
        self.assertEqual(chunker.flush(), ["How are"])

    def test_abbreviation_does_not_end_a_sentence(self):
        chunker = SentenceChunker()
        self.assertEqual(chunker.feed("Ask Dr. Novak today. Then rest. "), ["Ask Dr. Novak today.", "Then rest."])

    def test_long_text_with_no_stop_is_cut_at_a_space(self):
        chunker = SentenceChunker(max_chars=20)
        out = chunker.feed("one two three four five six seven")
        self.assertEqual(out, ["one two three four"])
        self.assertEqual(chunker.flush(), ["five six seven"])

    def test_markup_is_not_read_aloud(self):
        self.assertEqual(clean_for_speech("**Bold** and [a link](http://x.y) `code`"), "Bold and a link code")

    def test_flush_on_nothing(self):
        self.assertEqual(SentenceChunker().flush(), [])


class Idle(unittest.TestCase):
    def test_expires_only_after_the_limit_and_touch_resets_it(self):
        now = [0.0]
        clock = IdleClock(60, now=lambda: now[0])
        now[0] = 59
        self.assertFalse(clock.expired())
        clock.touch()
        now[0] = 118
        self.assertFalse(clock.expired())
        now[0] = 119
        self.assertTrue(clock.expired())


class Memory(unittest.TestCase):
    def test_keeps_only_recent_turns(self):
        history = History(max_turns=2)
        for text in ("one", "two", "three"):
            history.add("Adam", text)
        self.assertEqual(history.as_prompt(), "Adam: two\nAdam: three\nJorah:")

    def test_drop_last(self):
        history = History()
        history.add("Adam", "hi")
        history.drop_last()
        history.drop_last()
        self.assertEqual(history.as_prompt(), "\nJorah:")


class Percentile(unittest.TestCase):
    def test_no_samples_is_unknown_not_zero(self):
        self.assertIsNone(percentile([], 0.5))

    def test_values(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertEqual(percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9), 9)


if __name__ == "__main__":
    unittest.main()
