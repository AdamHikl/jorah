import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import advisories  # noqa: E402
import watchdog  # noqa: E402

TOKEN = "123456:TEST-token-not-real-ABCDEFGHIJKLMNOPQRSTUV"
DAY = 24 * 3600


def advisory(ghsa, ranges, updated="2026-11-19T02:01:59Z", package="openclaw", severity="high",
             published="2026-11-19T02:01:59Z"):
    return {"ghsa_id": ghsa, "severity": severity, "summary": f"Summary of {ghsa}",
            "html_url": f"https://github.com/openclaw/openclaw/security/advisories/{ghsa}",
            "updated_at": updated, "published_at": published,
            "vulnerabilities": [{"package": {"ecosystem": "npm", "name": package},
                                 "vulnerable_version_range": r, "patched_versions": p} for r, p in ranges]}


PW3X = advisory("GHSA-pw3x-g8v8-fvj2", [(">= 2026.9.2, < 2026.10.33", "2026.10.33"),
                                        (">= 2026.11.1, < 2026.11.4", "2026.11.4")])
OLD = advisory("GHSA-xx9p-hc9w-6p5h", [("< 2026.8.1", "2026.8.1")], updated="2026-09-11T00:58:59Z",
               severity="medium", published="2026-09-11T00:58:59Z")


class Response(io.BytesIO):
    def __init__(self, body, link=None):
        super().__init__(json.dumps(body).encode())
        self.headers = {"Link": link} if link else {}


class GitHub:
    """Stand-in for the advisory list: pages of advisories, a Link header to the next page."""

    def __init__(self, items, page=2):
        self.items, self.page, self.calls, self.fail = items, page, [], None

    def __call__(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        if self.fail:
            raise self.fail
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        start = int(query.get("after", ["0"])[0])
        chunk = self.items[start:start + self.page]
        link = None
        if start + self.page < len(self.items):
            link = f'<{advisories.API}?after={start + self.page}>; rel="next", <{advisories.API}>; rel="last"'
        return Response(chunk, link)


class Comparator(unittest.TestCase):
    def test_calendar_versions_compare_as_numbers(self):
        self.assertLess(advisories.parse_version("2026.10.9"), advisories.parse_version("2026.10.33"))
        self.assertLess(advisories.parse_version("2026.9.30"), advisories.parse_version("2026.10.1"))
        self.assertEqual(advisories.parse_version("v2026.10.9"), advisories.parse_version("2026.10.9"))

    def test_prerelease_sorts_before_its_release(self):
        self.assertLess(advisories.parse_version("2026.11.1-beta.2"), advisories.parse_version("2026.11.1"))
        self.assertLess(advisories.parse_version("2026.11.1-beta.2"), advisories.parse_version("2026.11.1-beta.10"))
        self.assertGreater(advisories.parse_version("2026.11.1-beta.1"), advisories.parse_version("2026.10.33"))

    def test_live_version_against_todays_advisory(self):
        rng = ">= 2026.9.2, < 2026.10.33"
        self.assertTrue(advisories.in_range("2026.10.9", rng))
        self.assertTrue(advisories.in_range("2026.9.2", rng))
        self.assertFalse(advisories.in_range("2026.10.33", rng))
        self.assertFalse(advisories.in_range("2026.9.1", rng))
        self.assertFalse(advisories.in_range("2026.11.4", ">= 2026.11.1, < 2026.11.4"))
        self.assertTrue(advisories.in_range("2026.11.3", ">= 2026.11.1, < 2026.11.4"))

    def test_other_operators(self):
        self.assertTrue(advisories.in_range("2026.3.28", "<= 2026.3.28"))
        self.assertFalse(advisories.in_range("2026.3.29", "<= 2026.3.28"))
        self.assertTrue(advisories.in_range("2026.1.29", "= 2026.1.29"))
        self.assertTrue(advisories.in_range("2026.1.29", "2026.1.29"))
        self.assertFalse(advisories.in_range("2026.1.30", "2026.1.29"))
        self.assertTrue(advisories.in_range("2026.5.0", "> 2026.4.9"))

    def test_npm_space_and_or_ranges(self):
        # Forms seen in OpenClaw's own advisory list on 2026-11-20.
        self.assertFalse(advisories.in_range("2026.10.9", ">=2026.1.14-1 <2026.2.12"))
        self.assertTrue(advisories.in_range("2026.2.1", ">=2026.1.14-1 <2026.2.12"))
        self.assertFalse(advisories.in_range("2026.10.9", ">= 2026.1.21 <= 2026.2.17"))
        self.assertTrue(advisories.in_range("2026.2.17", ">= 2026.1.21 <= 2026.2.17"))
        self.assertFalse(advisories.in_range("2026.10.9", "<=2026.2.19-2 || =2026.2.19"))
        self.assertTrue(advisories.in_range("2026.2.19", "<=2026.2.19-2 || =2026.2.19"))
        self.assertTrue(advisories.in_range("2026.1.1", "<=2026.2.19-2 || =2026.2.19"))
        self.assertFalse(advisories.in_range("2026.10.9", "<= 2026.2.21 || =2026.2.21-1 || =2026.2.21-2"))
        self.assertTrue(advisories.in_range("2026.10.9", ">= 2026.9.2 || < 1.0"))

    def test_unreadable_is_unknown_not_false(self):
        self.assertIsNone(advisories.in_range("2026.10.9", None))
        self.assertIsNone(advisories.in_range("2026.10.9", ""))
        self.assertIsNone(advisories.in_range("2026.10.9", ">= 2026.9.2 ||"))
        self.assertIsNone(advisories.in_range("2026.10.9", ">= 2026.9.2 - 2026.10.1"))
        self.assertIsNone(advisories.in_range("2026.10.9", "^2026.9.0"))
        self.assertIsNone(advisories.in_range("2026.10.9", "~> latest"))
        self.assertIsNone(advisories.in_range("not-a-version", "< 2026.8.1"))


class Fetch(unittest.TestCase):
    def test_first_run_reads_every_page(self):
        items = [advisory(f"GHSA-{i:04d}", [("< 1.0", "1.0")]) for i in range(5)]
        github = GitHub(items)
        found = advisories.fetch({}, github)
        self.assertEqual([a["id"] for a in found], [f"GHSA-{i:04d}" for i in range(5)])
        self.assertEqual(len(github.calls), 3)
        self.assertIn("state=published", github.calls[0])
        self.assertIn("sort=updated", github.calls[0])
        self.assertIn("direction=desc", github.calls[0])

    def test_stops_at_the_first_known_advisory(self):
        items = [PW3X, OLD] + [advisory(f"GHSA-{i:04d}", [("< 1.0", "1.0")]) for i in range(10)]
        github = GitHub(items)
        found = advisories.fetch({OLD["ghsa_id"]: OLD["updated_at"]}, github)
        self.assertEqual([a["id"] for a in found], [PW3X["ghsa_id"]])
        self.assertEqual(len(github.calls), 1)

    def test_an_edited_advisory_is_read_again(self):
        edited = dict(OLD, updated_at="2026-11-19T09:00:00Z")
        found = advisories.fetch({OLD["ghsa_id"]: OLD["updated_at"]}, GitHub([edited, PW3X]))
        self.assertEqual([a["id"] for a in found], [OLD["ghsa_id"], PW3X["ghsa_id"]])

    def test_errors_are_raised_never_an_empty_list(self):
        for failure in (urllib.error.URLError("down"), TimeoutError(),
                        urllib.error.HTTPError(advisories.API, 403, "rate limited", {}, None)):
            github = GitHub([PW3X])
            github.fail = failure
            with self.assertRaises(OSError):
                advisories.fetch({}, github)

    def test_too_many_pages_is_an_error(self):
        items = [advisory(f"GHSA-{i:04d}", [("< 1.0", "1.0")]) for i in range(10)]
        with self.assertRaises(OSError):
            advisories.fetch({}, GitHub(items), max_pages=3)

    def test_a_next_link_off_github_is_not_followed(self):
        class Evil(GitHub):
            def __call__(self, request, timeout):
                self.calls.append(request.full_url)
                return Response([PW3X], '<https://evil.example/x>; rel="next"')
        evil = Evil([])
        self.assertEqual(len(advisories.fetch({}, evil)), 1)
        self.assertEqual(len(evil.calls), 1)

    def test_only_openclaw_packages_are_kept(self):
        mixed = advisory("GHSA-mix", [("< 2026.1.29", "2026.1.29")])
        mixed["vulnerabilities"].append({"package": {"name": "clawdbot"}, "vulnerable_version_range": "< 9",
                                         "patched_versions": "9"})
        mixed["vulnerabilities"].append({"package": {"name": "@openclaw/voice-call"},
                                         "vulnerable_version_range": "< 2026.11.2", "patched_versions": "2026.11.2"})
        kept = advisories.summarize(mixed)["vulns"]
        self.assertEqual([v["package"] for v in kept], ["openclaw", "@openclaw/voice-call"])


class Installed(unittest.TestCase):
    def test_reads_openclaw_and_openclaw_plugins(self):
        root = Path(tempfile.mkdtemp())
        oc = root / "openclaw"
        (oc / "dist/extensions/voice-call").mkdir(parents=True)
        (oc / "package.json").write_text(json.dumps({"name": "openclaw", "version": "2026.10.9"}))
        (oc / "dist/extensions/voice-call/package.json").write_text(
            json.dumps({"name": "@openclaw/voice-call", "version": "2026.10.9"}))
        (root / "@openclaw/extra").mkdir(parents=True)
        (root / "@openclaw/extra/package.json").write_text(json.dumps({"name": "@openclaw/extra", "version": "1.2.3"}))
        found = advisories.installed_packages(oc, root)
        self.assertEqual(found, {"openclaw": "2026.10.9", "@openclaw/voice-call": "2026.10.9",
                                 "@openclaw/extra": "1.2.3"})

    def test_missing_openclaw_raises(self):
        with self.assertRaises(OSError):
            advisories.installed_packages(Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()))


class Step(unittest.TestCase):
    def setUp(self):
        self.state = {}
        self.now = 1_800_000_000.0
        self.listing = [PW3X, OLD]
        self.installed = {"openclaw": "2026.10.9"}

    def run_step(self, fail=None, days=1):
        self.now += days * DAY

        def read_list(known):
            if fail:
                raise OSError(fail)
            return [advisories.summarize(a) for a in self.listing if known.get(a["ghsa_id"]) != a["updated_at"]]
        due = advisories.step(self.state, self.now, read_list, lambda: dict(self.installed))
        for kind, key, _ in due:
            advisories.mark_sent(self.state, kind, key, self.now)
        return due

    def test_tells_once_about_an_affecting_advisory(self):
        due = self.run_step()
        self.assertEqual([(k, key) for k, key, _ in due], [("advisory", "GHSA-pw3x-g8v8-fvj2")])
        text = due[0][2]
        for part in ("GHSA-pw3x-g8v8-fvj2", "high", "openclaw 2026.10.9", "2026.10.33, 2026.11.4",
                     "https://github.com/openclaw/openclaw/security/advisories/GHSA-pw3x-g8v8-fvj2",
                     "Summary of GHSA-pw3x-g8v8-fvj2"):
            self.assertIn(part, text)
        self.assertEqual(self.run_step(), [])

    def test_after_the_upgrade_nothing_is_said(self):
        self.installed = {"openclaw": "2026.10.33"}
        self.assertEqual(self.run_step(), [])

    def test_an_upgrade_into_an_old_range_is_caught(self):
        self.installed = {"openclaw": "2026.10.33"}
        self.run_step()
        self.installed = {"openclaw": "2026.11.2"}
        due = self.run_step()
        self.assertEqual([key for _, key, _ in due], ["GHSA-pw3x-g8v8-fvj2"])

    def test_an_unreadable_range_is_reported_as_possible(self):
        self.listing = [advisory("GHSA-odd", [("between 1 and 2", None)])]
        due = self.run_step()
        self.assertEqual(len(due), 1)
        self.assertIn("Couldn't read the range", due[0][2])
        self.assertIn("no fixed version listed", due[0][2])

    def test_plugins_are_checked_when_installed(self):
        self.listing = [advisory("GHSA-plug", [("< 2026.11.2", "2026.11.2")], package="@openclaw/voice-call")]
        self.assertEqual(self.run_step(), [])
        self.state.pop("notified", None)
        self.installed["@openclaw/voice-call"] = "2026.10.9"
        due = self.run_step()
        self.assertIn("@openclaw/voice-call 2026.10.9", due[0][2])

    def test_unknown_after_a_day_never_no_advisories(self):
        self.run_step()
        self.assertEqual(self.run_step(fail="GitHub answered 503", days=0.5), [])
        due = self.run_step(fail="GitHub answered 503", days=0.6)
        self.assertEqual([k for k, _, _ in due], ["unknown"])
        self.assertIn("unknown", due[0][2])
        self.assertIn("GitHub answered 503", due[0][2])
        self.assertEqual(self.run_step(fail="GitHub answered 503"), [])
        self.assertEqual([k for k, _, _ in self.run_step()], ["readable"])

    def test_unknown_from_the_very_first_run(self):
        self.assertEqual(self.run_step(fail="down", days=0), [])
        due = self.run_step(fail="down", days=1.1)
        self.assertEqual([k for k, _, _ in due], ["unknown"])
        self.assertIn("last good read: never", due[0][2])

    def test_unreadable_version_is_unknown(self):
        def broken():
            raise OSError("no package.json")
        self.now += 2 * DAY
        self.state["source"] = {"last_ok": self.now - 2 * DAY, "problem": None, "since": None, "alerted": False}
        due = advisories.step(self.state, self.now, lambda known: [], broken)
        self.assertEqual([k for k, _, _ in due], ["unknown"])
        self.assertIn("installed version", due[0][2])

    def test_a_flood_is_one_message(self):
        self.listing = [advisory(f"GHSA-{i}", [("< 2027.1.1", "2027.1.1")]) for i in range(8)]
        due = self.run_step()
        self.assertEqual([k for k, _, _ in due], ["many"])
        self.assertIn("8 OpenClaw advisories", due[0][2])
        self.assertIn("(openclaw 2026.10.9)", due[0][2])
        self.assertEqual(self.run_step(), [])


class Telegram:
    def __init__(self, github):
        self.sent, self.github = [], github

    def __call__(self, request, timeout):
        if request.full_url.startswith("https://api.telegram.org/"):
            self.sent.append({k: v[0] for k, v in urllib.parse.parse_qs(request.data.decode()).items()})
            return io.BytesIO(json.dumps({"ok": True}).encode())
        return self.github(request, timeout)


class Daily(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "conf").write_text(json.dumps({"chat_id": "42", "gateway_port": 43181}))
        (self.dir / "token").write_text(TOKEN + "\n")
        self.lines = []
        watchdog.log = self.lines.append
        self.net = Telegram(GitHub([PW3X, OLD]))
        self.now = 1_800_000_000.0

    def run_daily(self, *extra, days=1):
        self.now += days * DAY
        args = ["daily", "--conf", str(self.dir / "conf"), "--token-file", str(self.dir / "token"),
                "--daily-state", str(self.dir / "daily.json"), "--drift-report", str(self.dir / "report.json"),
                "--drill-report", str(self.dir / "drill.json"), *extra]
        return watchdog.main(args, now=self.now, opener=self.net,
                             read_installed=lambda: {"openclaw": "2026.10.9"})

    def write_report(self, **fields):
        report = {"checked_at": self.now + DAY, "ok": True, "files": 3, "changed": [], "missing": [],
                  "unrecorded": [], "refused": [], "packages": {"@openclaw/acpx": ["2026.10.9"]}}
        report.update(fields)
        (self.dir / "report.json").write_text(json.dumps(report))

    def test_sends_the_advisory_once_and_never_the_token(self):
        self.write_report()
        self.assertEqual(self.run_daily(), 0)
        self.assertEqual(len(self.net.sent), 1)
        self.assertEqual(self.net.sent[0]["chat_id"], "42")
        self.assertIn("GHSA-pw3x-g8v8-fvj2", self.net.sent[0]["text"])
        self.write_report()
        self.run_daily()
        self.assertEqual(len(self.net.sent), 1)
        self.assertFalse(any(TOKEN in line for line in self.lines))
        self.assertNotIn(TOKEN, (self.dir / "daily.json").read_text())

    def test_dry_run_sends_and_saves_nothing(self):
        self.write_report(changed=[{"path": "/opt/jorah/x", "commit": "abcdef1234"}])
        self.run_daily("--dry-run")
        self.assertEqual(self.net.sent, [])
        self.assertFalse((self.dir / "daily.json").exists())
        self.assertTrue(any("would send (advisory)" in line for line in self.lines))
        self.assertTrue(any("would send (drift)" in line for line in self.lines))

    def test_drift_is_told_once_per_finding_and_when_it_clears(self):
        self.net.github.items = []
        self.write_report(changed=[{"path": "/home/jorah/workspace/AGENTS.md", "commit": "cee2880aaa"}])
        self.run_daily()
        self.assertEqual(len(self.net.sent), 1)
        self.assertIn("/home/jorah/workspace/AGENTS.md (deployed from cee2880)", self.net.sent[0]["text"])
        self.write_report(changed=[{"path": "/home/jorah/workspace/AGENTS.md", "commit": "cee2880aaa"}])
        self.run_daily()
        self.assertEqual(len(self.net.sent), 1)
        self.write_report()
        self.run_daily()
        self.assertEqual(len(self.net.sent), 2)
        self.assertIn("matches its deploy again", self.net.sent[1]["text"])

    def test_missing_drift_report_is_unknown_after_a_day(self):
        self.net.github.items = []
        self.run_daily(days=0)
        self.assertEqual(self.net.sent, [])
        self.run_daily(days=1.1)
        texts = sorted(m["text"] for m in self.net.sent)
        self.assertEqual(len(texts), 2)
        self.assertIn("advisory watch: unknown", texts[0])
        self.assertIn("plugins in Jorah's state folder", texts[0])
        self.assertIn("drift check: unknown", texts[1])
        self.run_daily()
        self.assertEqual(len(self.net.sent), 2)

    def test_npm_plugins_from_the_drift_report_are_checked(self):
        self.net.github.items = [advisory("GHSA-acpx", [("< 2026.10.33", "2026.10.33")], package="@openclaw/acpx")]
        self.write_report(packages={"@openclaw/acpx": ["2026.10.33", "2026.10.9"]})
        self.run_daily()
        self.assertEqual(len(self.net.sent), 1)
        self.assertIn("@openclaw/acpx 2026.10.9", self.net.sent[0]["text"])
        self.assertNotIn("2026.10.33,", self.net.sent[0]["text"].split("Fixed in")[0])

    def test_github_down_is_never_reported_as_no_advisories(self):
        self.net.github.fail = urllib.error.URLError("down")
        self.write_report()
        self.run_daily()
        self.assertTrue(any("advisories: unknown" in line for line in self.lines))
        self.assertEqual(self.net.sent, [])

    def test_toolbox_drill_alerts_only_when_failed_or_older_than_8_days(self):
        self.net.github.items = []
        self.write_report()
        # Missing report says nothing.
        self.run_daily()
        self.assertEqual(self.net.sent, [])

        # Fresh passing report says nothing.
        drill_path = self.dir / "drill.json"
        drill_path.write_text(json.dumps({"checked_at": self.now, "ok": True, "failed": []}))
        self.write_report()
        self.run_daily()
        self.assertEqual(self.net.sent, [])

        # Failed drill reports case names only, no paths, and once per failure report.
        drill_path.write_text(json.dumps({
            "checked_at": self.now + DAY,
            "ok": False,
            "failed": ["zig", "neovim-appimage"],
            "cases": [{"name": "zig", "ok": False, "problems": ["/home/jorah/sandbox/secret/path"]}],
        }))
        self.write_report()
        self.run_daily()
        self.assertEqual(len(self.net.sent), 1)
        msg = self.net.sent[0]["text"]
        self.assertIn("zig, neovim-appimage", msg)
        self.assertNotIn("/home/jorah", msg)
        self.write_report()
        self.run_daily()
        self.assertEqual(len(self.net.sent), 1)

        # Passing report older than 8 days says when it last ran.
        old_ts = self.now - 9 * DAY
        drill_path.write_text(json.dumps({"checked_at": old_ts, "ok": True, "failed": []}))
        self.write_report()
        self.run_daily()
        self.assertEqual(len(self.net.sent), 2)
        self.assertIn("toolbox drill hasn't run since", self.net.sent[1]["text"])


if __name__ == "__main__":
    unittest.main()
