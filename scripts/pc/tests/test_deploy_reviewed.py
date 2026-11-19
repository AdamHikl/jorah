import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deploy_reviewed  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


class GitHashes(unittest.TestCase):
    """The manifest's hashes come from git objects; check them against the files' real bytes."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.repo)
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
        os.environ.update(env)
        subprocess.run(["git", "init", "-q", "-b", "main"], check=True)
        for key, value in (("user.email", "t@example.invalid"), ("user.name", "t"), ("commit.gpgsign", "false")):
            subprocess.run(["git", "config", key, value], check=True)
        os.makedirs("workspace")
        Path("workspace/AGENTS.md").write_bytes(b"rules v1\n")
        Path("bin.dat").write_bytes(bytes(range(256)) * 3 + b"\n\n")
        os.symlink("workspace/AGENTS.md", "link.md")
        self.commit("one")
        self.first = self.head()
        Path("workspace/AGENTS.md").write_bytes(b"rules v2\n")
        self.commit("two")

    def tearDown(self):
        os.chdir(self.cwd)

    def commit(self, message):
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], check=True)

    def head(self):
        return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    def test_blob_hashes_match_file_bytes_and_skip_symlinks(self):
        found = deploy_reviewed.blobs("HEAD", ["."])
        self.assertEqual(sorted(found), ["bin.dat", "workspace/AGENTS.md"])
        sums = deploy_reviewed.blob_sha256(found.values())
        self.assertEqual(sums[found["bin.dat"]], sha(Path("bin.dat").read_bytes()))
        self.assertEqual(sums[found["workspace/AGENTS.md"]], sha(b"rules v2\n"))

    def test_entries_map_to_targets(self):
        out = deploy_reviewed.entries("HEAD", {"workspace/AGENTS.md": "/home/jorah/workspace/AGENTS.md"})
        self.assertEqual(out, {"/home/jorah/workspace/AGENTS.md": {"sha256": sha(b"rules v2\n"),
                                                                    "source": "workspace/AGENTS.md"}})
        with self.assertRaises(SystemExit):
            deploy_reviewed.entries("HEAD", {"nope.md": "/opt/jorah/nope.md"})

    def test_history_match_finds_the_older_commit(self):
        def commits_for(path):
            return subprocess.run(["git", "log", "--format=%H", "--", path], check=True, capture_output=True,
                                  text=True).stdout.split()

        def sha_at(commit, path):
            blob = deploy_reviewed.blobs(commit, [path])[path]
            return deploy_reviewed.blob_sha256([blob])[blob]
        self.assertEqual(deploy_reviewed.history_match("workspace/AGENTS.md", sha(b"rules v1\n"), commits_for, sha_at),
                         self.first)
        self.assertIsNone(deploy_reviewed.history_match("workspace/AGENTS.md", sha(b"edited\n"), commits_for, sha_at))

    def test_quoting(self):
        self.assertEqual(deploy_reviewed._quote("/opt/jorah/a-b_c.py"), "/opt/jorah/a-b_c.py")
        self.assertEqual(deploy_reviewed._quote("a b'c"), "'a b'\\''c'")


if __name__ == "__main__":
    unittest.main()
