import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.core import IdleClock, SentenceChunker, TurnEnd, classify, clean_for_speech, percentile, sounds_finished


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



class Finished(unittest.TestCase):
    def test_a_punctuated_sentence_sounds_finished(self):
        for text in ("Turn off the lights.", "What time is it?", "Do it now!", "Okay.", "That's it."):
            self.assertTrue(sounds_finished(text), text)

    def test_no_closing_punctuation_is_open(self):
        for text in ("", "   ", "Turn off the lights", "Well,", "So I was thinking...", "Hmm.."):
            self.assertFalse(sounds_finished(text), text)

    def test_a_full_stop_after_an_open_word_is_still_open(self):
        # Parakeet puts a full stop on a fragment as readily as on a sentence.
        for text in ("I went to the park and.", "Can you check the.", "So I need to, um.", "So.",
                     "Tell her that I.", "Pozri sa na to, ale."):
            self.assertFalse(sounds_finished(text), text)

    def test_case_and_trailing_space_do_not_matter(self):
        self.assertFalse(sounds_finished("Buy milk AND. "))
        self.assertTrue(sounds_finished(" Buy milk. "))


class TurnEnding(unittest.TestCase):
    def setUp(self):
        self.end = TurnEnd(0.3, 0.9)

    def test_a_finished_sentence_ends_after_the_short_pause(self):
        self.assertFalse(self.end.done("Turn off the lights.", 0.25, False))
        self.assertTrue(self.end.done("Turn off the lights.", 0.3, False))

    def test_an_open_sentence_waits_for_the_long_pause(self):
        self.assertFalse(self.end.done("I want to book a table for.", 0.5, False))
        self.assertTrue(self.end.done("I want to book a table for.", 0.9, False))
        self.assertEqual(self.end.wait_for("Lights on"), 0.9)

    def test_nothing_ends_while_the_transcript_is_being_made_or_he_is_talking(self):
        self.assertFalse(self.end.done(None, 5, False))
        self.assertFalse(self.end.done("Turn off the lights.", 5, True))

    def test_equal_pauses_behave_like_one_fixed_pause(self):
        fixed = TurnEnd(0.6, 0.6)
        for text in ("Done.", "and"):
            self.assertFalse(fixed.done(text, 0.59, False))
            self.assertTrue(fixed.done(text, 0.6, False))

    def test_the_finished_pause_must_be_the_shorter_one(self):
        for finished, unfinished in ((0.9, 0.3), (0, 0.5), (-1, 1)):
            with self.assertRaises(ValueError):
                TurnEnd(finished, unfinished)


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


class Percentile(unittest.TestCase):
    def test_no_samples_is_unknown_not_zero(self):
        self.assertIsNone(percentile([], 0.5))

    def test_values(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertEqual(percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9), 9)


if __name__ == "__main__":
    unittest.main()
