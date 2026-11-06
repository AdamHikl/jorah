import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.spoken import inflected, number_words, rewrite, say_numbers, write_inflections

KNOWN = set("""a b c d e f g h i j k l m n o p q r s t u v w x y z the is what on and at key your
rocket rockets jorah jorah's don't it's tail scale open claw git hub zero one two three four five
six seven eight nine ten eleven twelve thirty fifty oh hundred thousand million point percent
twenty dollars euros first second third fourth twentieth nineteen plus""".split())


class Numbers(unittest.TestCase):
    def test_words(self):
        self.assertEqual(number_words(0), "zero")
        self.assertEqual(number_words(42).split()[0], "forty")
        self.assertEqual(number_words(305), "three hundred five")
        self.assertEqual(number_words(12_000), "twelve thousand")
        self.assertEqual(number_words(2_000_019), "two million nineteen")
        self.assertEqual(number_words(1_234_567_890).split()[:2], ["one", "two"])

    def test_times(self):
        self.assertEqual(say_numbers("3:30").strip(), "three thirty")
        self.assertEqual(say_numbers("9:05").strip(), "nine oh five")
        self.assertEqual(say_numbers("9:00").strip(), "nine")

    def test_amounts(self):
        self.assertEqual(say_numbers("50%").strip(), "fifty percent")
        self.assertEqual(say_numbers("$5").strip(), "five dollars")
        self.assertEqual(say_numbers("1,200").strip(), "one thousand two hundred")
        self.assertEqual(say_numbers("3.5").strip(), "three point five")

    def test_ordinals(self):
        self.assertEqual(say_numbers("3rd").strip(), "third")
        self.assertEqual(say_numbers("20th").strip(), "twentieth")
        self.assertEqual(say_numbers("4th").strip(), "fourth")


class Words(unittest.TestCase):
    def test_known_words_are_untouched(self):
        self.assertEqual(rewrite("Your rocket, Jorah.", KNOWN), "Your rocket, Jorah.")
        self.assertEqual(rewrite("Don't. It's on.", KNOWN), "Don't. It's on.")

    def test_acronyms_are_spelled(self):
        self.assertEqual(rewrite("The SSH key", KNOWN), "The S S H key")

    def test_contractions_missing_from_the_list(self):
        self.assertEqual(rewrite("What's on", KNOWN), "what is on")

    def test_other_short_forms(self):
        self.assertEqual(rewrite("Rocket'll", KNOWN), "Rocket will")

    def test_possessives(self):
        self.assertEqual(rewrite("Jorah's key", KNOWN), "Jorah's key")
        self.assertEqual(rewrite("Rocket's key", KNOWN), "rockets key")

    def test_compounds_split_into_known_pieces(self):
        self.assertEqual(rewrite("Tailscale", KNOWN), "tail scale")
        self.assertEqual(rewrite("OpenClaw", KNOWN), "Open Claw")
        self.assertEqual(rewrite("GitHub", KNOWN), "Git Hub")

    def test_unknown_words_are_spelled_rather_than_dropped(self):
        self.assertEqual(rewrite("Zxq", KNOWN), "Z X Q")

    def test_accents_and_curly_apostrophes(self):
        self.assertEqual(rewrite("It’s Rocket", KNOWN), "It's Rocket")
        self.assertEqual(rewrite("Rócket", KNOWN), "Rocket")

    def test_joined_words_and_mixed_tokens(self):
        self.assertEqual(rewrite("open-claw", KNOWN), "open claw")
        self.assertEqual(rewrite("Tail-scale", KNOWN | {"tailscale"}), "Tailscale")
        self.assertEqual(rewrite("M3", KNOWN), "M three")

    def test_nothing_is_lost_from_a_real_sentence(self):
        self.assertEqual(rewrite("What's on at 3:30?", KNOWN), "what is on at three thirty?")


class Inflections(unittest.TestCase):
    def forms(self, word, sounds):
        return {form: " ".join(sound) for form, sound in inflected(word, sounds.split())}

    def test_endings_follow_the_last_sound(self):
        self.assertEqual(self.forms("return", "ɹ ə t ˈ ɜ ɹ n"), {"returns": "ɹ ə t ˈ ɜ ɹ n z", "returned": "ɹ ə t ˈ ɜ ɹ n d"})
        self.assertEqual(self.forms("walk", "w ˈ ɔ k"), {"walks": "w ˈ ɔ k s", "walked": "w ˈ ɔ k t"})
        self.assertEqual(self.forms("create", "k ɹ i ˈ A t"), {"creates": "k ɹ i ˈ A t s", "created": "k ɹ i ˈ A t ᵻ d"})
        self.assertEqual(self.forms("box", "b ˈ ɑ k s"), {"boxes": "b ˈ ɑ k s ᵻ z", "boxed": "b ˈ ɑ k s t"})
        self.assertEqual(self.forms("reply", "ɹ ə p l ˈ I"), {"replies": "ɹ ə p l ˈ I z", "replied": "ɹ ə p l ˈ I d"})

    def test_only_missing_forms_are_written(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "list.txt"
            source.write_text("open ˈ O p ᵊ n\nopened ˈ O p ᵊ n d\nme m i\n", encoding="utf-8")
            target = Path(folder) / "extra.txt"
            write_inflections(source, target)
            written = target.read_text(encoding="utf-8")
            self.assertIn("opens ˈ O p ᵊ n z\n", written)
            self.assertNotIn("opened ", written)
            self.assertNotIn("mes", written)


if __name__ == "__main__":
    unittest.main()
