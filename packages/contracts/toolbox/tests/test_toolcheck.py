"""Contract jorah-tool-v1: the checker takes the good examples and refuses each bad one for its reason."""

import json
import sys
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import toolcheck  # noqa: E402

EXPECTED = json.loads((HERE / "examples" / "expected.json").read_text())
TODAY = date.fromisoformat(EXPECTED["today"])


def load(kind, name):
    return json.loads((HERE / "examples" / kind / name).read_text())


class Examples(unittest.TestCase):
    def test_good_examples_pass(self):
        names = sorted(p.name for p in (HERE / "examples" / "good").glob("*.json"))
        self.assertGreaterEqual(len(names), 3)
        for name in names:
            with self.subTest(name):
                self.assertEqual(toolcheck.check(load("good", name), TODAY), [])

    def test_every_bad_example_is_refused_for_its_reason(self):
        names = sorted(p.name for p in (HERE / "examples" / "bad").glob("*.json"))
        self.assertEqual(names, sorted(EXPECTED["bad"]), "every bad example needs an expected reason, and back")
        for name in names:
            with self.subTest(name):
                problems = toolcheck.check(load("bad", name), TODAY)
                self.assertTrue(any(EXPECTED["bad"][name] in p for p in problems), problems)


class Rules(unittest.TestCase):
    def setUp(self):
        self.m = load("good", "uv.json")

    def test_the_seven_day_rule_counts_whole_days(self):
        self.m["released"] = "2026-11-10"
        self.assertEqual(toolcheck.check(self.m, TODAY), [])
        self.m["released"] = "2026-11-11"
        self.assertTrue(toolcheck.check(self.m, TODAY))

    def test_not_an_object(self):
        self.assertEqual(toolcheck.check(["uv"], TODAY), ["the request must be a JSON object"])

    def test_placeholders_are_the_only_dollar_signs(self):
        self.m["env"] = {"UV_CACHE_DIR": "${STATE}/cache", "UV_PYTHON_INSTALL_DIR": "${TOOL}/python"}
        self.assertEqual(toolcheck.check(self.m, TODAY), [])
        self.m["env"] = {"UV_CACHE_DIR": "${HOME}/cache"}
        self.assertTrue(toolcheck.check(self.m, TODAY))

    def test_a_single_file_tool_has_one_command(self):
        self.m.update(format="file", strip=0, commands={"uv": "uv", "uvx": "uvx"})
        self.assertIn("commands: a single-file tool has exactly one command", toolcheck.check(self.m, TODAY))

    def test_private_hosts_are_refused(self):
        for url in ("https://nas.local/x.tar.gz", "https://[::1]/x.tar.gz", "https://user:pw@example.com/x.tar.gz",
                    "https://example.com:8443/x.tar.gz", "https://localhost/x.tar.gz"):
            with self.subTest(url):
                self.m["url"] = url
                self.assertTrue(any(p.startswith("url:") for p in toolcheck.check(self.m, TODAY)))

    def test_digest_and_id_are_stable_and_follow_every_field(self):
        a = toolcheck.digest(self.m)
        self.assertEqual(a, toolcheck.digest(json.loads(json.dumps(self.m))))
        self.assertTrue(toolcheck.proposal_id(self.m).startswith("tb-"))
        self.m["purpose"] += " Also for scripts."
        self.assertNotEqual(a, toolcheck.digest(self.m))

    def test_card_fields(self):
        f = toolcheck.card_fields(self.m, "tb-0123456789")
        self.assertEqual(f["source"], self.m["url"])
        self.assertEqual(f["sha256"], "0" * 16)
        self.assertEqual(f["size"], "21 MB download, 55 MB installed")
        apt = toolcheck.card_fields(load("good", "java.json"), "tb-x")
        self.assertEqual(apt["source"], "Ubuntu archive: openjdk-21-jre-headless")

    def test_load_file_caps_size(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write(" " * (toolcheck.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            toolcheck.load_file(handle.name)
        Path(handle.name).unlink()


if __name__ == "__main__":
    unittest.main()
