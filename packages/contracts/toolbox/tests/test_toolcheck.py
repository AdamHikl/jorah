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
        self.assertEqual(f["sha256"], "c2def3db178ade63")
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


GH = EXPECTED["github"]


def github_case(case):
    """Request, release and today for one of expected.json's GitHub cases."""
    request = dict(load("github", GH["request"]), **case.get("request", {}))
    release = json.loads(json.dumps(load("github", GH["release"])))
    release.update(case.get("release", {}))
    name = toolcheck.github_asset(request["url"])["asset"]
    for asset in release["assets"]:
        if asset["name"] == name:
            asset.update(case.get("asset", {}))
    return request, release, date.fromisoformat(case.get("today", GH["today"]))


class GitHubLookup(unittest.TestCase):
    def test_the_request_passes_without_the_fields_github_fills_in(self):
        request = load("github", GH["request"])
        self.assertEqual(toolcheck.check_request(request, TODAY), [])
        self.assertIn("sha256: missing" + toolcheck.MISSING_HINT, toolcheck.check(request, TODAY))

    def test_other_hosts_still_need_the_publishers_checksum(self):
        request = dict(load("github", GH["request"]), url="https://downloads.example.org/uv-0.13.8.tar.gz")
        problems = toolcheck.check_request(request, TODAY)
        self.assertIn("sha256: missing" + toolcheck.MISSING_HINT, problems)
        self.assertIn("released: missing" + toolcheck.MISSING_HINT, problems)

    def test_the_asset_url_names_the_release_and_its_api_path(self):
        request = load("github", GH["request"])
        where = toolcheck.github_asset(request["url"])
        self.assertEqual(where["path"], GH["path"])
        self.assertEqual(where["asset"], "uv-x86_64-unknown-linux-gnu.tar.gz")
        self.assertIsNone(toolcheck.github_asset("https://github.com/astral-sh/../releases/download/x/y"))
        self.assertIsNone(toolcheck.github_asset("https://example.org/astral-sh/uv/releases/download/x/y"))
        odd = toolcheck.github_asset("https://github.com/o/r/releases/download/v1.0%2Bbuild%2F2/a.zip")
        self.assertEqual((odd["tag"], odd["path"]), ("v1.0+build/2", "/repos/o/r/releases/tags/v1.0%2Bbuild%2F2"))

    def test_github_fills_in_hash_date_and_size(self):
        request, release, today = github_case({})
        m, record, problems = toolcheck.apply_github(request, release)
        self.assertEqual(problems, [])
        self.assertEqual({k: m[k] for k in GH["filled"]}, GH["filled"])
        self.assertEqual(record, GH["record"])
        self.assertEqual(toolcheck.check(m, today), [])
        self.assertEqual(toolcheck.digest(m), GH["digest"])
        self.assertNotIn("sha256", request, "the request itself is left alone")

    def test_every_case(self):
        for case in GH["cases"]:
            with self.subTest(case["about"]):
                request, release, today = github_case(case)
                m, _record, problems = toolcheck.apply_github(request, release)
                problems = problems or toolcheck.check(m, today)
                if case["problem"] is None:
                    self.assertEqual(problems, [])
                else:
                    self.assertTrue(any(case["problem"] in p for p in problems), problems)

    def test_the_newest_release_old_enough_is_named_with_its_asset(self):
        older = GH["older"]
        today = date.fromisoformat(older["today"])
        self.assertEqual(toolcheck.older_release(older["list"], toolcheck.github_asset(older["url"]), today), older["expect"])
        v = older["versioned"]
        self.assertEqual(toolcheck.older_release(v["list"], toolcheck.github_asset(v["url"]), today), v["expect"])
        self.assertIsNone(toolcheck.older_release(older["list"][:2], toolcheck.github_asset(older["url"]), today))
        self.assertEqual(toolcheck.github_asset(older["url"])["list"], "/repos/astral-sh/uv/releases?per_page=10")
