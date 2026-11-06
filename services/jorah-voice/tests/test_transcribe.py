import unittest

import numpy as np

from jorah_voice import transcribe
from jorah_voice.speech import MIC_RATE


class Pieces(unittest.TestCase):
    def test_long_audio_is_cut_and_tiny_tails_dropped(self):
        audio = np.zeros(transcribe.PIECE_SECONDS * MIC_RATE * 2 + MIC_RATE // 10, dtype=np.float32)
        sizes = [len(p) for p in transcribe.pieces(audio)]
        self.assertEqual(sizes, [transcribe.PIECE_SECONDS * MIC_RATE] * 2)

    def test_short_audio_is_one_piece(self):
        audio = np.zeros(MIC_RATE * 5, dtype=np.float32)
        self.assertEqual(len(list(transcribe.pieces(audio))), 1)

    def test_usage_error_without_a_file(self):
        self.assertEqual(transcribe.main([]), 2)


if __name__ == "__main__":
    unittest.main()


class Speak(unittest.TestCase):
    def test_reply_is_cut_into_clean_sentences(self):
        from jorah_voice import speak
        parts = speak.sentences("**Done.** The backup ran at 04:30. See [the log](https://example.com).")
        self.assertEqual(parts, ["Done.", "The backup ran at 04:30.", "See the log."])

    def test_usage_error(self):
        from jorah_voice import speak
        self.assertEqual(speak.main(["only-one-arg"]), 2)
