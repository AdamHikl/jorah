"""The runner's parts on their own: stream reading, schemas, registry, safe paths, the sync CLI."""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from world import CONTRACT, REPO_ROOT, World, git

from jorah_projects import claude, config, contract, fsio


class StreamTest(unittest.TestCase):
    def feed(self, *messages):
        reader = claude.StreamReader()
        for m in messages:
            reader.feed(m if isinstance(m, str) else json.dumps(m))
        return reader

    def test_a_rejected_rate_limit_event_is_the_usage_limit_with_its_reset(self):
        r = self.feed({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 1795000000, "rateLimitType": "five_hour", "utilization": 1.0}})
        self.assertTrue(r.limited)
        self.assertEqual(r.limit_reset, "2026-11-18T11:06:40+00:00")
        self.assertEqual(r.limit_type, "five_hour")
        self.assertEqual(r.windows["fiveHour"]["utilization"], 1.0)

    def test_allowed_events_only_record_usage(self):
        r = self.feed({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning", "resetsAt": 1795000000, "rateLimitType": "seven_day", "utilization": 0.8,
                                                                       "unifiedWindows": {"five_hour": {"utilization": 0.2, "resetsAt": 1794000000}}}})
        self.assertFalse(r.limited)
        self.assertEqual(r.windows["sevenDay"]["utilization"], 0.8)
        self.assertEqual(r.windows["fiveHour"]["utilization"], 0.2)

    def test_limit_text_counts_only_from_the_cli_itself(self):
        self.assertTrue(self.feed({"type": "result", "is_error": True, "result": "Claude AI usage limit reached|1795000000"}).limited)
        self.assertTrue(self.feed({"type": "assistant", "error": "rate_limit", "message": {"content": [{"type": "text", "text": "You've hit your limit · resets 3pm"}]}}).limited)
        # The model talking about limits, or a long page quoting them, isn't a limit.
        self.assertFalse(self.feed({"type": "assistant", "message": {"content": [{"type": "text", "text": "The usage limit reached its cap in the docs"}]}}).limited)
        self.assertFalse(self.feed({"type": "result", "is_error": False, "result": "usage limit reached"}).limited)
        self.assertFalse(self.feed({"type": "result", "is_error": True, "result": "usage limit reached " + "x" * 500}).limited)

    def test_the_result_message_is_kept_without_its_text(self):
        r = self.feed("not json", {"type": "result", "subtype": "error_max_turns", "is_error": True, "num_turns": 200, "terminal_reason": "max_turns", "result": "secret plan"})
        self.assertEqual(r.result, {"subtype": "error_max_turns", "isError": True, "numTurns": 200, "terminalReason": "max_turns", "durationMs": None})
        self.assertEqual(r.bad_lines, 1)
        self.assertNotIn("secret plan", json.dumps(r.usage()))


class ContractTest(unittest.TestCase):
    def setUp(self):
        self.pc = contract.load(CONTRACT)

    def test_the_test_state_passes_the_real_contract(self):
        files = World.default_files()
        docs = {kind: contract.parse(self.pc, files[f"project/{name}"].encode()) for kind, name in contract.KINDS.items()}
        self.assertEqual(contract.state_problems(self.pc, docs), {})

    def test_cross_file_rules_and_bad_yaml_are_problems(self):
        files = World.default_files()
        docs = {kind: contract.parse(self.pc, files[f"project/{name}"].encode()) for kind, name in contract.KINDS.items()}
        docs["backlog"]["items"][0].update(status="done", evidence=[])           # done without evidence
        docs["questions"]["questions"][0].update(status="answered")              # answered without answer
        try:
            contract.parse(self.pc, b"a: &x 1\nb: *x\n")                       # aliases are refused
        except ValueError as error:
            docs["adam-tasks"] = error
        problems = contract.state_problems(self.pc, docs)
        self.assertEqual(set(problems), {"backlog", "questions", "adam-tasks"})

    def test_a_missing_or_broken_contract_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(contract.ContractError):
                contract.load(tmp)
            Path(tmp, "projectcheck.py").write_text("raise SystemExit('no')\n")
            with self.assertRaises(contract.ContractError):
                contract.load(tmp)

    def test_registry_entries_follow_the_contract(self):
        good = {"repo": "AdamHikl/robot", "workDir": "/home/jorah/work/robot", "branch": "jorah/line", "level": 0, "schedule": [],
                "limits": {"runsPerDay": 1, "minutesPerRun": 30, "maxTurns": 100}, "paused": False}
        self.assertEqual(contract.entry_problems(self.pc, "robot", good), [])
        self.assertTrue(contract.entry_problems(self.pc, "Robot", good))
        self.assertTrue(contract.entry_problems(self.pc, "robot", {**good, "limits": {"runsPerDay": 9, "minutesPerRun": 30, "maxTurns": 100}}))


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "work").mkdir()
        self.s = config.Settings(registry=self.tmp / "projects.json", work_root=self.tmp / "work", github_owner="AdamHikl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, data, mode=0o600):
        self.s.registry.write_text(json.dumps(data))
        self.s.registry.chmod(mode)

    def test_a_good_entry_and_its_defaults(self):
        self.write({"robot": {"repo": "AdamHikl/robot"}})
        p = config.load_registry(self.s)["robot"]
        self.assertEqual((p.branch, p.state_dir, p.level, p.limits, p.web, p.schedule), ("jorah/line", "project", 0, config.DEFAULT_LIMITS, False, []))
        self.assertEqual(p.work_dir, self.tmp / "work/robot")

    def test_bad_entries_are_refused_one_by_one(self):
        bad = {
            "a": {"repo": "AdamHikl/a", "limits": {"runsPerDay": 9}},
            "b": {"repo": "AdamHikl/b", "workDir": "/home/jorah/.ssh"},
            "c": {"repo": "AdamHikl/c", "branch": "main"},
            "d": {"repo": "someone/d"},
            "e": {"repo": "AdamHikl/e", "stateDir": "../x"},
            "f": {"repo": "AdamHikl/f", "schedule": ["25:00"]},
            "g": {"repo": "AdamHikl/g", "level": 3},
            "h": {"repo": "AdamHikl/h", "limits": {"maxTurns": 501}},
            "Upper": {"repo": "AdamHikl/upper"},
        }
        self.write({**bad, "ok": {"repo": "AdamHikl/ok"}})
        projects = config.load_registry(self.s)
        for name in bad:
            self.assertIsInstance(projects[name], config.ConfigError, name)
        self.assertIsInstance(projects["ok"], config.Project)

    def test_a_registry_others_can_read_is_refused(self):
        self.write({"robot": {"repo": "AdamHikl/robot"}}, mode=0o644)
        with self.assertRaises(config.ConfigError):
            config.load_registry(self.s)


class PathTest(unittest.TestCase):
    def test_links_and_escapes_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            (root / "project").mkdir(parents=True)
            os.symlink("/etc", root / "project/link")
            for rel in ("../x", "/etc/passwd", "project/link/passwd", "project/link"):
                with self.assertRaises(fsio.Unsafe, msg=rel):
                    fsio.read_bytes(root, rel)
            fsio.write_bytes(root, "project/new/deep.txt", b"ok")
            self.assertEqual(fsio.read_bytes(root, "project/new/deep.txt"), b"ok")
            self.assertIsNone(fsio.read_bytes(root, "project/missing.yaml"))

    def test_yaml_keeps_dates_as_text(self):
        doc = fsio.parse_yaml(b"created: 2026-11-16\nat: 2026-11-16T10:00:00+01:00\n")
        self.assertEqual(doc, {"created": "2026-11-16", "at": "2026-11-16T10:00:00+01:00"})
        self.assertEqual(fsio.parse_yaml(fsio.dump_yaml(doc)), doc)
        with self.assertRaises(ValueError):
            fsio.parse_yaml(b"a: [unclosed\n")
        with self.assertRaises(ValueError):
            fsio.parse_yaml(b"!!python/object/apply:os.system ['true']\n")


@unittest.skipUnless(shutil.which("node"), "node isn't installed")
class SyncCliTest(unittest.TestCase):
    """plugins/jorah-github/bin/jorah-github-sync.mjs against a stand-in GitHub API and a bare repo."""

    def test_it_syncs_into_the_mirror_and_prints_only_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            seed = tmp / "seed"
            seed.mkdir()
            git(seed, "init", "-q", "-b", "main")
            (seed / "a.txt").write_text("a\n")
            git(seed, "add", "-A")
            git(seed, "commit", "-qm", "a")
            git(tmp, "clone", "-q", "--bare", str(seed), str(tmp / "gh/AdamHikl/robot.git"))
            harness = tmp / "harness.mjs"
            cli = (REPO_ROOT / "plugins/jorah-github/bin/jorah-github-sync.mjs").as_uri()
            harness.write_text(textwrap.dedent(f"""\
                import {{ generateKeyPairSync }} from "node:crypto";
                import {{ writeFileSync }} from "node:fs";
                import {{ main }} from "{cli}";
                const key = generateKeyPairSync("rsa", {{ modulusLength: 2048 }}).privateKey.export({{ type: "pkcs8", format: "pem" }});
                writeFileSync(process.argv[2], key, {{ mode: 0o600 }});
                const calls = [];
                const fetchImpl = async (url, init = {{}}) => {{
                  calls.push(`${{init.method ?? "GET"}} ${{url}}`);
                  const body = url.endsWith("/installation") ? {{ id: 7 }} : {{ token: "ghs_standin", expires_at: new Date(Date.now() + 3600e3).toISOString() }};
                  return {{ ok: true, status: 200, json: async () => body }};
                }};
                const argv = process.argv.slice(3);
                const lines = [];
                const code = await main(argv, {{ fetchImpl, remoteBase: "file://{tmp}/gh/", write: (l) => lines.push(l) }});
                const bad = await main(["--project", "robot"], {{ fetchImpl, write: (l) => lines.push(l) }});
                console.log(JSON.stringify({{ code, bad, lines, calls }}));
            """))
            mirrors = tmp / "mirrors"
            out = subprocess.run(["node", str(harness), str(tmp / "app.pem"), "--project", "robot", "--repo", "AdamHikl/robot",
                                  "--app-id", "5686503", "--owner", "AdamHikl", "--key-file", str(tmp / "app.pem"), "--mirror-dir", str(mirrors)],
                                 capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(out.returncode, 0, out.stderr)
            got = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertEqual(got["code"], 0)
            first = json.loads(got["lines"][0])
            self.assertEqual((first["ok"], first["defaultBranch"], first["branches"], first["repo"]), (True, "main", 1, "AdamHikl/robot"))
            self.assertNotIn("ghs_standin", out.stdout)
            self.assertEqual(got["calls"][1], "POST https://api.github.com/app/installations/7/access_tokens")
            self.assertEqual(got["bad"], 1)
            self.assertFalse(json.loads(got["lines"][1])["ok"])
            refs = subprocess.run(["git", "--git-dir", str(mirrors / "robot.git"), "for-each-ref", "--format=%(refname)"], capture_output=True, text=True, check=True).stdout
            self.assertIn("refs/remotes/github/main", refs)
            self.assertEqual(subprocess.run(["git", "--git-dir", str(mirrors / "robot.git"), "config", "jorah.defaultBranch"], capture_output=True, text=True).stdout.strip(), "main")

    def test_a_repo_of_another_owner_is_refused(self):
        out = subprocess.run(["node", str(REPO_ROOT / "plugins/jorah-github/bin/jorah-github-sync.mjs"), "--project", "x", "--repo", "someone/x",
                              "--app-id", "1", "--owner", "AdamHikl"], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(out.returncode, 1)
        self.assertIn("isn't AdamHikl's", json.loads(out.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
