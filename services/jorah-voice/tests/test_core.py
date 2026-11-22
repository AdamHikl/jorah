import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.core import (IdleClock, SentenceChunker, TurnEnd, classify, clean_for_speech, percentile,
                             resolve_session_key, session_log_label, sounds_finished)


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
        # The end of a line ends the sentence, so it is spoken with a full stop.
        self.assertEqual(chunker.flush(), ["How are."])

    def test_abbreviation_does_not_end_a_sentence(self):
        chunker = SentenceChunker()
        self.assertEqual(chunker.feed("Ask Dr. Novak today. Then rest. "), ["Ask Dr. Novak today.", "Then rest."])

    def test_long_text_with_no_stop_is_cut_at_a_space(self):
        chunker = SentenceChunker(max_chars=20)
        out = chunker.feed("one two three four five six seven")
        self.assertEqual(out, ["one two three four"])
        self.assertEqual(chunker.flush(), ["five six seven."])

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


class JoinWaitingTest(unittest.TestCase):
    def queue(self, *items):
        import asyncio
        q = asyncio.Queue()
        for item in items:
            q.put_nowait(item)
        return q

    def test_joins_what_is_waiting(self):
        from jorah_voice.core import join_waiting
        q = self.queue("Two.", "Three.")
        self.assertEqual(join_waiting("One.", q, 300), ("One. Two. Three.", False))
        self.assertTrue(q.empty())

    def test_stops_at_the_end_marker(self):
        from jorah_voice.core import join_waiting
        q = self.queue("Two.", None)
        self.assertEqual(join_waiting("One.", q, 300), ("One. Two.", True))

    def test_keeps_order_when_too_long(self):
        from jorah_voice.core import join_waiting
        q = self.queue("x" * 20, "Next.", None)
        self.assertEqual(join_waiting("One.", q, 10), ("One.", False))
        self.assertEqual([q.get_nowait() for _ in range(3)], ["x" * 20, "Next.", None])


class Speakable(unittest.TestCase):
    def test_links_hashes_paths_and_code_become_short_words(self):
        from jorah_voice.core import speakable
        self.assertEqual(speakable("See https://github.com/astral-sh/uv/releases for it."), "See a link for it.")
        self.assertEqual(speakable("[the release page](https://x.y/z) is blocked"), "the release page is blocked")
        self.assertEqual(speakable("SHA-256 3b1f0c9e8d7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0 is needed."),
                         "SHA-256 a long code is needed.")
        self.assertEqual(speakable("Pushed 8874bcf to main."), "Pushed a long code to main.")
        self.assertEqual(speakable("It's in /home/jorah/work/uv/SHA256SUMS now."), "It's in a file path now.")
        self.assertEqual(speakable("Run `just check` then `sha256sum ~/work/uv-0.9.1-x86_64.tar.gz`."),
                         "Run just check then a long code.")

    def test_ordinary_words_and_numbers_stay(self):
        from jorah_voice.core import speakable
        for text in ("Call 1234567 after the decade ends.", "The 2026 plan has 3 steps.", "A uv-0.9.1 toolbox."):
            self.assertEqual(speakable(text), text)

    def test_list_marks_and_rules_go(self):
        from jorah_voice.core import speakable
        self.assertEqual(speakable("- Option A: wait"), "Option A: wait")
        self.assertEqual(speakable("|---|:---:|"), "")


class ChunkerLines(unittest.TestCase):
    TEXT = "## Status\n- Card is waiting\n1. Option A: paste the hash\n2. Option B: skip it\n| a | b |\n|---|---|\n```bash\nsha256sum x\n```\nDone."

    def test_each_line_is_a_sentence_and_code_is_named_not_read(self):
        from jorah_voice.core import speakable_sentences
        self.assertEqual(speakable_sentences(self.TEXT), [
            "Status.", "Card is waiting.", "Option A: paste the hash.", "Option B: skip it.", "a b.",
            "A code block.", "Done."])

    def test_the_same_when_it_arrives_in_small_pieces(self):
        from jorah_voice.core import speakable_sentences
        for size in (1, 2, 3, 7):
            chunker = SentenceChunker()
            out = []
            for start in range(0, len(self.TEXT), size):
                out += chunker.feed(self.TEXT[start : start + size])
            out += chunker.flush()
            self.assertEqual(out, speakable_sentences(self.TEXT), size)


class Overview(unittest.TestCase):
    def split(self, text, size=None):
        from jorah_voice.core import OverviewSplit
        split = OverviewSplit()
        size = size or len(text)
        spoken = "".join(split.feed(text[i : i + size]) for i in range(0, len(text), size)) + split.finish()
        return spoken, split.full

    def test_the_line_splits_overview_from_full_message(self):
        text = "It's blocked. Pick A or B?\n\nFull message:\n- A: paste the hash\n- B: skip it"
        for size in (None, 1, 4, 9):
            spoken, full = self.split(text, size)
            self.assertEqual(spoken.strip(), "It's blocked. Pick A or B?")
            self.assertEqual(full, "- A: paste the hash\n- B: skip it")

    def test_markup_around_the_line_and_the_line_after_a_sentence(self):
        self.assertEqual(self.split("Done.\n**Full message:**\nAll of it.")[1], "All of it.")
        spoken, full = self.split("Done. Full message:\nAll of it.", 3)
        self.assertEqual((spoken.strip(), full), ("Done.", "All of it."))

    def test_words_that_only_start_like_the_line_are_spoken(self):
        text = "The full message is on screen. Full messages are long.\nBye."
        self.assertEqual(self.split(text, 2), (text, None))

    def test_text_is_released_before_the_line_arrives(self):
        from jorah_voice.core import OverviewSplit
        split = OverviewSplit()
        self.assertEqual(split.feed("It worked. Full mes"), "It worked.")
        self.assertEqual(split.feed("sage:\nRest."), "")
        self.assertEqual(split.full, "Rest.")

    def test_no_line_means_no_full_message(self):
        self.assertEqual(self.split("Just a short answer."), ("Just a short answer.", None))


class ReadAll(unittest.TestCase):
    def test_phrases(self):
        for text in ("Read the whole message.", "Jorah, read the whole message.", "Read it all, please.",
                     "Read me everything.", "read the full message jorah", "Read the rest."):
            self.assertEqual(classify(text), "read_all", text)
        for text in ("Read my email.", "Read the whole message from Peter.", "Can you read it all to Peter?"):
            self.assertEqual(classify(text), "talk", text)

    def test_the_last_full_message_is_kept_for_half_an_hour_only(self):
        from jorah_voice.core import LastFullMessage
        now = [0.0]
        store = LastFullMessage(clock=lambda: now[0])
        self.assertIsNone(store.get())
        store.keep("All of it.")
        now[0] = 1799
        self.assertEqual(store.get(), "All of it.")
        now[0] = 1801
        self.assertIsNone(store.get())


class SessionKey(unittest.TestCase):
    def test_allows_main_and_lowercase_dashboard_uuid_only(self):
        dash1 = "agent:main:dashboard:01234567-89ab-cdef-0123-456789abcdef"
        dash2 = "agent:main:dashboard:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.assertEqual(resolve_session_key("agent:main:main"), "agent:main:main")
        self.assertEqual(resolve_session_key(dash1), dash1)
        self.assertEqual(resolve_session_key(dash2), dash2)
        self.assertEqual(session_log_label("agent:main:main"), "main")
        self.assertEqual(session_log_label(dash1), "hud-conversation")

        bad = (
            None,
            "",
            123,
            {},
            True,
            "agent:main:dashboard:x",
            "agent:main:dashboard:",
            "agent:main:dashboard:0123456789abcdef0123456789abcdef",
            "agent:main:dashboard:01234567-89ab-cdef-0123-456789abcde",
            "agent:main:dashboard:01234567-89ab-cdef-0123-456789abcdef0",
            "agent:main:dashboard:01234567-89ab-cdef-0123-456789abcdeg",
            "agent:main:dashboard:01234567-89AB-CDEF-0123-456789ABCDEF",
            "AGENT:main:main",
            "agent:other:main",
            "agent:other:dashboard:01234567-89ab-cdef-0123-456789abcdef",
            "agent:main:subagent:01234567-89ab-cdef-0123-456789abcdef",
            "agent:main:telegram:123",
            dash1 + "-extra",
            dash1 + " ",
            dash1 + "\n",
            " " + dash1,
            "agent:main:main\n",
            "agent:main:main:extra",
        )
        for candidate in bad:
            self.assertEqual(resolve_session_key(candidate), "agent:main:main", repr(candidate))
