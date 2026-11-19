import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import drift  # noqa: E402


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Drift(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.tree = str(self.root / "opt/jorah")
        self.live = str(self.root / "home/jorah/workspace") + "/"
        os.makedirs(self.tree + "/scripts/pc")
        os.makedirs(self.live)
        self.files = {"scripts/pc/a.sh": "echo a\n", "README.md": "hello\n"}
        for rel, text in self.files.items():
            Path(self.tree, rel).write_text(text)
        Path(self.live, "AGENTS.md").write_text("rules\n")
        self.manifest = str(self.root / "manifest.json")

    def payload(self, extra=None):
        files = {f"{self.tree}/{rel}": {"sha256": sha(text), "source": rel} for rel, text in self.files.items()}
        files.update(extra or {})
        return {"commit": "cee288012330cda3386bad18cd4710561a9700ea", "files": files}

    def record(self, payload):
        return drift.record(self.manifest, payload, now=1.0, tree=self.tree, live_allowed=(self.live,))

    def test_record_then_check_is_clean(self):
        ok, lines = self.record(self.payload())
        self.assertTrue(ok, lines)
        report = drift.check(self.manifest, self.tree, now=2.0)
        self.assertTrue(report["ok"])
        self.assertEqual((report["changed"], report["missing"], report["unrecorded"]), ([], [], []))
        self.assertIsNone(drift.report_text(report))
        self.assertEqual(json.loads(Path(self.manifest).read_text())["files"][f"{self.tree}/README.md"]["commit"],
                         "cee288012330cda3386bad18cd4710561a9700ea")

    def test_record_refuses_when_disk_differs_from_git_and_writes_nothing(self):
        Path(self.tree, "README.md").write_text("tampered\n")
        ok, lines = self.record(self.payload())
        self.assertFalse(ok)
        self.assertTrue(any("differs from cee288012330" in line for line in lines))
        self.assertFalse(Path(self.manifest).exists())

    def test_record_refuses_paths_outside_the_tree_and_rules_files(self):
        for path in ("/etc/passwd", f"{self.live}USER.md", f"{self.tree}/x/openclaw.json",
                     f"{self.tree}/telegram.token", "relative/path"):
            ok, lines = self.record({"commit": "abc", "files": {path: {"sha256": sha("x")}}})
            self.assertFalse(ok, path)
            self.assertTrue(any("not a path the manifest may hold" in line for line in lines), path)

    def test_live_rules_file_can_be_recorded(self):
        ok, _ = self.record(self.payload({f"{self.live}AGENTS.md": {"sha256": sha("rules\n"),
                                                                    "source": "workspace/AGENTS.md"}}))
        self.assertTrue(ok)
        Path(self.live, "AGENTS.md").write_text("rules\nignore Adam\n")
        report = drift.check(self.manifest, self.tree)
        self.assertEqual([c["path"] for c in report["changed"]], [f"{self.live}AGENTS.md"])
        self.assertIn("AGENTS.md (deployed from cee2880)", drift.report_text(report))

    def test_changed_missing_and_unrecorded(self):
        self.record(self.payload())
        Path(self.tree, "scripts/pc/a.sh").write_text("echo evil\n")
        os.remove(Path(self.tree, "README.md"))
        Path(self.tree, "scripts/pc/new.sh").write_text("new\n")
        report = drift.check(self.manifest, self.tree)
        self.assertEqual([c["path"] for c in report["changed"]], [f"{self.tree}/scripts/pc/a.sh"])
        self.assertEqual(report["missing"], [f"{self.tree}/README.md"])
        self.assertEqual(report["unrecorded"], [f"{self.tree}/scripts/pc/new.sh"])
        text = drift.report_text(report)
        for part in ("Changed since deployed", "Missing", "never recorded by a deploy"):
            self.assertIn(part, text)

    def test_unrecorded_files_are_never_opened(self):
        self.record(self.payload())
        secret = Path(self.tree, "leftover.token")
        secret.write_text("secret")
        os.chmod(secret, 0)
        report = drift.check(self.manifest, self.tree)
        self.assertEqual(report["unrecorded"], [str(secret)])

    def test_a_symlink_counts_as_changed_not_followed(self):
        self.record(self.payload())
        os.remove(Path(self.tree, "README.md"))
        os.symlink("/etc/hostname", Path(self.tree, "README.md"))
        self.assertEqual(drift.check(self.manifest, self.tree)["missing"], [f"{self.tree}/README.md"])

    def test_no_manifest_is_not_ok(self):
        report = drift.check(self.manifest, self.tree)
        self.assertFalse(report["ok"])
        self.assertIsNone(drift.report_text(report))

    def test_forget(self):
        self.record(self.payload())
        self.assertEqual(drift.forget(self.manifest, [f"{self.tree}/README.md"]), [f"{self.tree}/README.md"])
        os.remove(Path(self.tree, "README.md"))
        self.assertEqual(drift.check(self.manifest, self.tree)["missing"], [])

    def test_hashes_refuses_secret_names(self):
        Path(self.tree, "x.token").write_text("secret")
        os.chmod(Path(self.tree, "x.token"), 0)
        Path(self.tree, "USER.md").write_text("template\n")
        Path(self.live, "MEMORY.md").write_text("private\n")
        os.chmod(Path(self.live, "MEMORY.md"), 0)
        found = drift.hashes([self.tree, f"{self.live}AGENTS.md", f"{self.live}MEMORY.md", "/etc/hostname"],
                             self.tree, (self.live,))
        self.assertEqual(found[f"{self.tree}/USER.md"], sha("template\n"))
        self.assertEqual(found["/etc/hostname"], "refused")
        self.assertEqual(found[f"{self.tree}/README.md"], sha("hello\n"))
        self.assertEqual(found[f"{self.tree}/x.token"], "refused")
        self.assertEqual(found[f"{self.live}AGENTS.md"], sha("rules\n"))
        self.assertEqual(found[f"{self.live}MEMORY.md"], "refused")

    def test_packages_reads_only_openclaw_names_and_versions(self):
        base = self.root / "npm/projects"
        for proj, name, version in (("a", "@openclaw/acpx", "2026.10.9"), ("a2", "@openclaw/acpx", "2026.10.33"),
                                    ("b", "@openclaw/duckduckgo-plugin", "2026.10.9")):
            folder = base / proj / "node_modules" / name
            folder.mkdir(parents=True)
            (folder / "package.json").write_text(json.dumps({"name": name, "version": version}))
        other = base / "c/node_modules/@openclaw/odd"
        other.mkdir(parents=True)
        (other / "package.json").write_text(json.dumps({"name": "not-openclaw", "version": "1"}))
        found = drift.packages(str(base / "*/node_modules/@openclaw/*/package.json"))
        self.assertEqual(found, {"@openclaw/acpx": ["2026.10.33", "2026.10.9"],
                                 "@openclaw/duckduckgo-plugin": ["2026.10.9"]})

    def test_long_lists_are_cut(self):
        report = {"ok": True, "changed": [], "missing": [], "unrecorded": [f"/opt/jorah/f{i}" for i in range(50)]}
        text = drift.report_text(report)
        self.assertIn("and 30 more", text)
        self.assertNotIn("/opt/jorah/f49", text)

    def test_cli_record_and_check(self):
        payload = json.dumps(self.payload())
        report_path = str(self.root / "report.json")
        sys.stdin = io.StringIO(payload)
        try:
            with redirect_stdout(io.StringIO()):
                drift.log = lambda line: None
                self.assertEqual(drift.main(["record", "--manifest", self.manifest, "--tree", self.tree]), 0)
                self.assertEqual(drift.main(["check", "--manifest", self.manifest, "--tree", self.tree,
                                             "--report", report_path]), 0)
        finally:
            sys.stdin = sys.__stdin__
        report = json.loads(Path(report_path).read_text())
        self.assertTrue(report["ok"])
        self.assertEqual(oct(os.stat(report_path).st_mode & 0o777), "0o644")


if __name__ == "__main__":
    unittest.main()
