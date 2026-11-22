import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parents[1]

spec = importlib.util.spec_from_file_location("toolbox_drill", HERE / "toolbox-drill.py")
drill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drill)

sys.path.insert(0, str(REPO_ROOT / "packages" / "contracts" / "toolbox"))
import toolcheck  # noqa: E402


class ToolboxDrillCasesTest(unittest.TestCase):
    def test_cases_file_has_expected_shape_and_valid_requests(self):
        cases = drill.load_cases()
        self.assertGreaterEqual(len(cases), 8)
        names = [c["name"] for c in cases]
        self.assertEqual(len(names), len(set(names)), "case names must be unique")

        today = date(2026, 11, 22)
        for c in cases:
            req = drill.prepare_request(c["request"], today=today)
            exp = c["expect"]
            self.assertIn(exp["propose"], ("proposed", "refused"))
            self.assertIn(exp["install"], ("installed", "needs-root", None))
            self.assertIsInstance(exp["commandsFoundByName"], bool)
            if req["kind"] == "archive" and c["name"] != "non-github-too-new":
                self.assertEqual(toolcheck.check_request(req, today), [], c["name"])
            elif c["name"] == "non-github-too-new":
                probs = toolcheck.check_request(req, today)
                self.assertTrue(any("less than 7 days ago" in p for p in probs), probs)
            else:
                # apt requests omit fields filled from Ubuntu's archive by toolbox_propose.
                for key in ("contract", "name", "title", "kind", "purpose", "packages", "sandbox", "smoke"):
                    self.assertIn(key, req, c["name"])
                for key in ("version", "released", "licence", "licence_source", "homepage", "release_page"):
                    self.assertNotIn(key, req, c["name"])


class ToolboxDrillCompareTest(unittest.TestCase):
    def test_installed_with_expected_smoke_passes(self):
        expect = {
            "propose": "proposed",
            "match": None,
            "install": "installed",
            "commandsFoundByName": False,
            "smoke_contains": "ripgrep 15.2.0",
        }
        problems = drill.compare_outcome(
            expect,
            {"status": "proposed", "id": "tb-0123456789"},
            {"status": "approved"},
            {"status": "installed", "checks": {"downloadBytes": 2265718}},
            {"ok": True, "exit": 0, "output": "ripgrep 15.2.0\n"},
        )
        self.assertEqual(problems, [])

    def test_commands_found_by_name_mismatch_fails(self):
        expect = {
            "propose": "proposed",
            "match": None,
            "install": "installed",
            "commandsFoundByName": True,
            "smoke_contains": "uv 0.13.8",
        }
        problems = drill.compare_outcome(
            expect,
            {"status": "proposed"},
            {"status": "approved"},
            {"status": "installed", "checks": {}},
            {"ok": True, "exit": 0, "output": "uv 0.13.8\n"},
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("commandsFoundByName", problems[0])

    def test_commands_found_by_name_passes_when_present(self):
        expect = {
            "propose": "proposed",
            "match": None,
            "install": "installed",
            "commandsFoundByName": True,
            "smoke_contains": "0.12.6",
        }
        problems = drill.compare_outcome(
            expect,
            {"status": "proposed"},
            {"status": "approved"},
            {"status": "installed", "checks": {"commandsFoundByName": {"nvim": "usr/bin/nvim"}}},
            {"ok": True, "exit": 0, "output": "NVIM v0.12.6\n"},
        )
        self.assertEqual(problems, [])

    def test_needs_root_passes_without_smoke(self):
        expect = {
            "propose": "proposed",
            "match": None,
            "install": "needs-root",
            "commandsFoundByName": False,
            "smoke_contains": None,
        }
        problems = drill.compare_outcome(
            expect,
            {"status": "proposed"},
            {"status": "approved"},
            {"status": "needs-root", "checks": {"root": "needs root"}},
            None,
        )
        self.assertEqual(problems, [])

    def test_refusal_match_passes_and_mismatch_fails(self):
        expect = {
            "propose": "refused",
            "match": "publishes no package named",
            "install": None,
            "commandsFoundByName": False,
            "smoke_contains": None,
        }
        self.assertEqual(
            drill.compare_outcome(
                expect,
                {"status": "refused", "problems": ["packages: Ubuntu noble publishes no package named foo"]},
                None,
                None,
                None,
            ),
            [],
        )
        bad = drill.compare_outcome(
            expect,
            {"status": "refused", "problems": ["something else"]},
            None,
            None,
            None,
        )
        self.assertTrue(any("did not match" in p for p in bad))

    def test_smoke_failure_or_missing_text_fails(self):
        expect = {
            "propose": "proposed",
            "match": None,
            "install": "installed",
            "commandsFoundByName": False,
            "smoke_contains": "0.17.1",
        }
        failed = drill.compare_outcome(
            expect,
            {"status": "proposed"},
            {"status": "approved"},
            {"status": "installed", "checks": {}},
            {"ok": False, "exit": 127, "error": None, "output": "not found"},
        )
        self.assertTrue(any("smoke: failed" in p for p in failed))
        wrong_out = drill.compare_outcome(
            expect,
            {"status": "proposed"},
            {"status": "approved"},
            {"status": "installed", "checks": {}},
            {"ok": True, "exit": 0, "output": "0.17.0\n"},
        )
        self.assertTrue(any("output missing" in p for p in wrong_out))


class ToolboxDrillReportAndCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_build_and_write_report_world_readable(self):
        t0 = datetime(2026, 11, 22, 4, 10, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 22, 4, 10, 42, tzinfo=timezone.utc)
        c1 = drill.summarize_case(
            "ripgrep",
            [],
            {"status": "proposed", "id": "tb-1111111111"},
            {"status": "installed", "checks": {"downloadBytes": 2000}},
            {"ok": True, "exit": 0, "seconds": 0.2, "expectFound": True, "error": None, "output": "ripgrep 15.2.0"},
        )
        c2 = drill.summarize_case(
            "zig",
            ["smoke: failed"],
            {"status": "proposed", "id": "tb-2222222222"},
            {"status": "installed", "checks": {"downloadBytes": 5000}},
            {"ok": False, "exit": 1, "seconds": 0.1, "expectFound": False, "error": None, "output": "err"},
        )
        report = drill.build_report([c1, c2], t0, t1)
        self.assertFalse(report["ok"])
        self.assertEqual(report["failed"], ["zig"])
        self.assertEqual(report["total_download_bytes"], 7000)
        self.assertEqual(report["duration_seconds"], 42.0)

        out_path = self.tmp / "sub" / "last.json"
        drill.write_report(out_path, report)
        self.assertEqual(stat.S_IMODE(out_path.stat().st_mode), 0o644)
        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["failed"], ["zig"])

    def test_main_writes_report_cleans_scratch_and_returns_exit_code(self):
        cases = [
            {"name": "a-ok", "request": {"kind": "apt"}, "expect": {"propose": "proposed"}},
            {"name": "b-fail", "request": {"kind": "apt"}, "expect": {"propose": "refused"}},
        ]
        cases_path = self.tmp / "cases.json"
        cases_path.write_text(json.dumps(cases), encoding="utf-8")
        scratch = self.tmp / "scratch"
        report_path = self.tmp / "report.json"

        orig_run_case = drill.run_case

        def fake_run_case(case, sroot, **kw):
            (Path(sroot) / case["name"]).mkdir(parents=True, exist_ok=True)
            if case["name"] == "a-ok":
                return drill.summarize_case("a-ok", [], {"status": "proposed"}, {"status": "needs-root", "checks": {}}, None)
            return drill.summarize_case("b-fail", ["propose: got 'proposed'"], {"status": "proposed"}, None, None)

        drill.run_case = fake_run_case
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = drill.main(["--cases", str(cases_path), "--scratch-root", str(scratch), "--report", str(report_path)])
        finally:
            drill.run_case = orig_run_case

        self.assertEqual(rc, 1)
        self.assertFalse(scratch.exists(), "scratch root should be deleted unless --keep")
        out = buf.getvalue().splitlines()
        self.assertEqual(out, ["a-ok: ok", "b-fail: FAIL: propose: got 'proposed'"])
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["failed"], ["b-fail"])

    def test_main_keep_and_case_filter_and_dry_run(self):
        cases = [
            {"name": "one", "request": {"kind": "apt", "name": "cowsay", "packages": ["cowsay"]}, "expect": {"propose": "proposed", "install": "needs-root"}},
            {"name": "two", "request": {"kind": "apt", "name": "other", "packages": ["other"]}, "expect": {"propose": "refused"}},
        ]
        cases_path = self.tmp / "cases.json"
        cases_path.write_text(json.dumps(cases), encoding="utf-8")
        scratch = self.tmp / "scratch-keep"
        report_path = self.tmp / "report-keep.json"

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = drill.main(["--cases", str(cases_path), "--case", "one", "--dry-run", "--scratch-root", str(scratch), "--report", str(report_path)])
        self.assertEqual(rc, 0)
        self.assertIn("- one:", buf.getvalue())
        self.assertNotIn("- two:", buf.getvalue())
        self.assertFalse(report_path.exists())

        orig_run_case = drill.run_case
        drill.run_case = lambda case, sroot, **kw: (
            (Path(sroot) / case["name"]).mkdir(parents=True, exist_ok=True),
            drill.summarize_case(case["name"], [], {"status": "proposed"}, None, None),
        )[1]
        try:
            with redirect_stdout(io.StringIO()):
                rc = drill.main(["--cases", str(cases_path), "--case", "one", "--keep", "--scratch-root", str(scratch), "--report", str(report_path)])
        finally:
            drill.run_case = orig_run_case
        self.assertEqual(rc, 0)
        self.assertTrue((scratch / "one").is_dir())
        self.assertTrue(json.loads(report_path.read_text())["ok"])

        with redirect_stderr(io.StringIO()):
            self.assertEqual(drill.main(["--cases", str(cases_path), "--case", "missing"]), 2)


if __name__ == "__main__":
    unittest.main()
