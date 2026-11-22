import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.passphrase import (
    MAX_FAILURES,
    PASSPHRASE_FILE,
    PHRASE_FORBIDDEN_WORD_MESSAGE,
    PhraseStore,
    normalise,
)


class Normalisation(unittest.TestCase):
    def test_digits_and_english_and_slovak_number_words_match(self):
        self.assertEqual(normalise("Four, seven, one nine."), "4 7 1 9")
        self.assertEqual(normalise("4719"), "4 7 1 9")
        self.assertEqual(normalise("four seven one nine"), "4 7 1 9")
        self.assertEqual(normalise("Štyri, sedem, jedna, deväť!"), "4 7 1 9")
        self.assertEqual(normalise("styri sedem jeden devat"), "4 7 1 9")
        self.assertEqual(normalise("nula dva tri päť šesť osem"), "0 2 3 5 6 8")
        self.assertEqual(normalise("zero two three five six eight"), "0 2 3 5 6 8")

    def test_nfkc_and_punctuation_and_whitespace(self):
        # Full-width digits and punctuation collapse identically.
        self.assertEqual(normalise("４７１９"), "4 7 1 9")
        self.assertEqual(normalise("  Copper,   River — Oak! "), "copper river oak")


class StoreAndLockout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vp = Path(self.tmp.name) / "voiceprint"
        self.store = PhraseStore(self.vp)

    def tearDown(self):
        self.tmp.cleanup()

    def test_set_validation_refuses_too_short(self):
        for bad in ("", "   ", "one two", "copper river", "copper 42", "12345", "four seven one nine"):
            with self.assertRaises(ValueError, msg=bad):
                self.store.set(bad)

    def test_scrypt_store_modes_and_windows_and_no_plaintext(self):
        status = self.store.set("Copper River Oak")
        self.assertEqual(status, {"set": True, "words": 3, "locked": False})
        self.assertEqual(stat.S_IMODE(self.vp.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.vp / PASSPHRASE_FILE).stat().st_mode), 0o600)

        raw = (self.vp / PASSPHRASE_FILE).read_text(encoding="utf-8")
        self.assertNotIn("copper", raw.lower())
        self.assertNotIn("river", raw.lower())
        self.assertNotIn("oak", raw.lower())
        parsed = json.loads(raw)
        self.assertEqual(parsed["n"], 2**15)
        self.assertEqual(parsed["r"], 8)
        self.assertEqual(parsed["p"], 1)

        self.assertTrue(self.store.matches_within("Yes, go ahead, copper, river, oak, please."))
        self.assertTrue(self.store.matches_within("COPPER river oak"))
        self.assertFalse(self.store.matches_within("copper river pine"))
        self.assertFalse(self.store.matches_within("copper oak"))

    def test_six_digit_pin_works_with_spoken_words(self):
        status = self.store.set("471923")
        self.assertEqual(status, {"set": True, "words": 6, "locked": False})
        self.assertTrue(self.store.matches_within("Yes, go ahead, four seven one nine two three."))
        self.assertTrue(self.store.matches_within("Potvrď štyri sedem jedna deväť dva tri."))
        self.assertFalse(self.store.matches_within("Yes, go ahead, 471924."))

    def test_lockout_after_three_failures_and_unlock(self):
        self.store.set("copper river oak")
        self.assertFalse(self.store.record_failure())
        self.assertFalse(self.store.record_failure())
        self.assertTrue(self.store.record_failure())
        self.assertTrue(self.store.locked)
        # Persists across re-instantiation.
        reloaded = PhraseStore(self.vp)
        self.assertTrue(reloaded.locked)
        self.assertEqual(reloaded.status(), {"set": True, "words": 3, "locked": True})
        # Unlock clears lockout and failure counter.
        reloaded.unlock()
        self.assertFalse(reloaded.locked)
        self.assertFalse(reloaded.record_failure())
        self.assertEqual(MAX_FAILURES, 3)

    def test_clear_removes_phrase(self):
        self.store.set("copper river oak")
        self.assertEqual(self.store.clear(), {"set": False, "words": None, "locked": False})
        self.assertFalse(self.store.matches_within("copper river oak"))

    def test_set_refuses_no_words_and_commands(self):
        forbidden = (
            "no copper oak",
            "nope copper oak",
            "don't copper oak",
            "don\u2019t copper oak",
            "do not copper",
            "deny copper oak",
            "cancel copper oak",
            "stop copper oak",
            "copper not now",
            "nie copper oak",
            "zruš copper oak",
            "zrus copper oak",
            "stay with me",
            "go to sleep",
            "thank you jorah",
            "read the rest",
            "that is all",
            "quiet river oak",
            "thanks river oak",
            "goodbye river oak",
            "enough river oak",
            "nevermind river oak",
        )
        for bad in forbidden:
            with self.assertRaises(ValueError, msg=bad) as ctx:
                self.store.set(bad)
            self.assertEqual(str(ctx.exception), PHRASE_FORBIDDEN_WORD_MESSAGE, bad)

        # Words that merely share a prefix are still accepted.
        status = self.store.set("know note canon")
        self.assertTrue(status["set"])

    def test_is_healthy_detects_corrupt_or_unreadable_file(self):
        self.assertTrue(self.store.is_healthy())
        self.store.set("copper river oak")
        self.assertTrue(self.store.is_healthy())

        path = self.vp / PASSPHRASE_FILE
        path.chmod(0o000)
        try:
            self.assertFalse(self.store.is_healthy())
        finally:
            path.chmod(0o600)

        path.write_text("{not valid json", encoding="utf-8")
        self.assertFalse(self.store.is_healthy())


if __name__ == "__main__":
    unittest.main()
