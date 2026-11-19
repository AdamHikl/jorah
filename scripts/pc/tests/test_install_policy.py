import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_policy", HERE / "install-policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

CLAWHUB = {"protocolVersion": 1, "openclawVersion": "2026.10.9", "targetType": "skill", "targetName": "weather",
           "sourcePath": "/tmp/x/root", "sourcePathKind": "directory",
           "source": {"kind": "clawhub", "authority": "openclaw", "mutable": False, "network": True},
           "origin": {"type": "clawhub", "slug": "weather", "version": "1.0.0"},
           "request": {"kind": "skill-install", "mode": "install", "requestedSpecifier": "clawhub:weather@1.0.0"}}
LINKED = {"protocolVersion": 1, "targetType": "plugin", "targetName": "jorah-errands",
          "sourcePath": "/opt/jorah/plugins/jorah-errands", "source": {"kind": "local-path"},
          "request": {"kind": "plugin-install", "mode": "install"}}


class Policy(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "allow.json")

    def allow(self, entries):
        Path(self.path).write_text(json.dumps({"allow": entries}))
        os.chmod(self.path, 0o644)

    def decide(self, request):
        return policy.decide(request, self.path, check_owner=False)

    def test_repo_allowlist_is_empty_and_valid(self):
        data = json.loads((HERE.parents[1] / "config/security/install-allowlist.json").read_text())
        self.assertEqual(data["allow"], [])

    def test_empty_or_missing_list_blocks_everything(self):
        self.assertEqual(self.decide(CLAWHUB)["decision"], "block")
        self.allow([])
        for request in (CLAWHUB, LINKED):
            out = self.decide(request)
            self.assertEqual(out["decision"], "block")
            self.assertIn("not on", out["reason"])
            self.assertEqual(out["protocolVersion"], 1)

    def test_matching_entry_allows(self):
        self.allow([{"targetType": "plugin", "targetName": "jorah-errands", "sourceKind": "local-path",
                     "note": "Adam's yes, 2026-11-19"}])
        out = self.decide(LINKED)
        self.assertEqual(out["decision"], "allow")
        self.assertIn("Adam's yes", out["reason"])
        self.assertEqual(self.decide(CLAWHUB)["decision"], "block")

    def test_every_named_field_must_match(self):
        self.allow([{"targetType": "plugin", "targetName": "jorah-errands", "sourceKind": "npm"}])
        self.assertEqual(self.decide(LINKED)["decision"], "block")
        self.allow([{"targetType": "plugin", "targetName": "jorah-errands", "mode": "update"}])
        self.assertEqual(self.decide(LINKED)["decision"], "block")
        self.allow([{"targetType": "skill", "targetName": "jorah-errands"}])
        self.assertEqual(self.decide(LINKED)["decision"], "block")

    def test_bad_lists_block(self):
        for text in ("not json", json.dumps({"allow": "x"}), json.dumps({"allow": [{"targetType": "plugin"}]}),
                     json.dumps({"allow": [{"targetType": "plugin", "targetName": "x", "anything": True}]})):
            Path(self.path).write_text(text)
            self.assertEqual(self.decide(LINKED)["decision"], "block", text)

    def test_unsafe_owner_or_mode_blocks(self):
        self.allow([{"targetType": "plugin", "targetName": "jorah-errands"}])
        os.chmod(self.path, 0o666)
        out = policy.decide(LINKED, self.path, check_owner=True)
        self.assertEqual(out["decision"], "block")
        self.assertIn("root-owned", out["reason"])

    def test_symlinked_list_blocks(self):
        self.allow([{"targetType": "plugin", "targetName": "jorah-errands"}])
        link = os.path.join(self.dir, "link.json")
        os.symlink(self.path, link)
        self.assertEqual(policy.decide(LINKED, link, check_owner=False)["decision"], "block")

    def test_bad_requests_block(self):
        for request in (None, [], {"protocolVersion": 2, "targetType": "skill"}, {}):
            self.assertEqual(self.decide(request)["decision"], "block")

    def test_as_a_process_with_garbage_stdin(self):
        out = subprocess.run([sys.executable, "-I", str(HERE / "install-policy.py")], input=b"\xff garbage",
                             capture_output=True, check=True)
        decision = json.loads(out.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertTrue(decision["reason"])


if __name__ == "__main__":
    unittest.main()
