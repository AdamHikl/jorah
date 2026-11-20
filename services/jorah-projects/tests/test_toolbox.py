"""The runner's side of Jorah's toolbox: requests from runs, notes, the smoke test, the learning run."""

import json
import os
import subprocess
import unittest
from pathlib import Path

from world import REPO_ROOT, World, git

from jorah_projects import claude, runner, toolbox

EXAMPLES = REPO_ROOT / "packages/contracts/toolbox/examples/good"


def tool_entry(name="uv", tid="tb-0000000001", **extra):
    entry = {"id": tid, "name": name, "title": "uv", "version": "0.9.18", "kind": "archive", "purpose": "Make Python environments quickly.",
             "forProject": "robot", "homepage": "https://docs.astral.sh/uv/", "commands": ["uv", "uvx"], "licence": "Apache-2.0 OR MIT",
             "smoke": ["uv", "--version"], "smokeExpect": "uv 0.9.18", "path": "/opt/jorah-toolbox/tools/uv/0.9.18"}
    entry.update(extra)
    return entry


class ToolboxTest(unittest.TestCase):
    def setUp(self):
        self.w = World()
        w = self.w
        self.opt = w.tmp / "opt-toolbox"
        self.var = w.tmp / "var-toolbox"
        (self.opt / "bin").mkdir(parents=True)
        for sub in ("proposals", "tested"):
            (self.var / sub).mkdir(parents=True)
        self.bwrap = w.tools / "bwrap"
        self.bwrap.write_text("#!/bin/sh\nexit 0\n")
        self.bwrap.chmod(0o755)
        w.settings.toolbox_dir = self.opt
        w.settings.toolbox_var = self.var
        w.settings.toolbox_state = w.home / "sandbox/.cache/jorah-toolbox"
        w.settings.bwrap_bin = str(self.bwrap)
        self.smoke_calls = []
        self.smoke_answer = (0, b"uv 0.9.18 (x86_64-unknown-linux-gnu)\n")

    def tearDown(self):
        self.w.cleanup()

    def install(self, *tools):
        (self.opt / "installed.json").write_text(json.dumps({"v": 1, "tools": {t["name"]: t for t in tools}}))

    def smoke_run(self, cmd, **kw):
        self.smoke_calls.append(cmd)
        code, out = self.smoke_answer
        return subprocess.CompletedProcess(cmd, code, out, b"")

    def runner(self):
        w = self.w
        return runner.Runner(w.settings, now=w.clock, disk_free=lambda _p: w.free, log=w.logs.append, smoke_run=self.smoke_run, github_get=w.github_api,
                             claude_run=lambda s, p, b, *, minutes, setup=False: claude.run(s, p, b, minutes=minutes, setup=setup))

    @property
    def notes(self):
        return self.w.home / "work/.toolbox"

    # ---- project runs --------------------------------------------------------------------------------

    def test_a_runs_request_becomes_a_proposal_and_a_bad_one_comes_back_with_its_reason(self):
        w = self.w
        good = json.loads((EXAMPLES / "orca-slicer.json").read_text())
        bad = dict(good, released="2026-11-15", name="new-slicer")
        w.behave([
            {"op": "write", "path": str(self.notes / "requests/orca-slicer.json"), "text": json.dumps(good)},
            {"op": "write", "path": str(self.notes / "requests/new-slicer.json"), "text": json.dumps(bad)},
        ])
        w.request()
        [record] = self.runner().tick()
        self.assertEqual(record["outcome"], "ok", record)
        box = record["toolbox"]
        [proposed] = box["requests"]["proposed"]
        self.assertEqual(proposed["name"], "orca-slicer")
        proposal = json.loads((self.var / "proposals" / f"{proposed['id']}.json").read_text())
        self.assertEqual(proposal["from"], {"via": "run", "project": "robot", "run": record["id"]})
        self.assertEqual(proposal["manifest"], good)
        self.assertEqual(proposal["card"]["source"], good["url"])
        self.assertTrue((self.notes / "requests/done/orca-slicer.json").is_file())
        why = (self.notes / "requests/bad/new-slicer.json.why.txt").read_text()
        self.assertIn("less than 7 days ago", why)
        outbox = w.outbox(record)
        self.assertTrue(any("tool request: orca-slicer 2.3.1" in n for n in outbox["notes"]), outbox)
        self.assertTrue(any("new-slicer.json refused" in p for p in outbox["problems"]), outbox)
        # Requests aren't part of the notes history.
        self.assertNotIn("requests/", git(self.notes, "log", "--name-only", "--format=").stdout)

    def test_a_github_request_gets_githubs_hash_date_and_size(self):
        w = self.w
        gh_dir = REPO_ROOT / "packages/contracts/toolbox/examples/github"
        expected = json.loads((REPO_ROOT / "packages/contracts/toolbox/examples/expected.json").read_text())["github"]
        request = json.loads((gh_dir / expected["request"]).read_text())
        api = "https://api.github.com" + expected["path"]
        w.github_api.pages[api] = json.loads((gh_dir / expected["release"]).read_text())
        w.clock.advance(days=2)
        notes = toolbox.work_dir(w.settings) / "requests"
        toolbox.ensure_repo(w.settings, w.home)
        (notes / "uv.json").write_text(json.dumps(request))
        (notes / "uv-wrong.json").write_text(json.dumps(dict(request, sha256="0" * 64)))
        out = toolbox.collect_requests(w.settings, {"project": "robot", "run": "r"}, w.clock().date(), w.github_api)
        [proposed] = out["proposed"]
        self.assertEqual(proposed["id"], "tb-" + expected["digest"][:10])
        proposal = json.loads((self.var / "proposals" / f"{proposed['id']}.json").read_text())
        self.assertEqual(proposal["digest"], expected["digest"])
        self.assertEqual(proposal["card"]["sha256"], expected["filled"]["sha256"][:16])
        self.assertEqual(proposal["card"]["released"], "2026-11-12")
        self.assertEqual(proposal["github"]["immutable"], True)
        self.assertEqual(proposal["github"]["filled"], ["released", "sha256", "download_mb", "installed_mb"])
        self.assertEqual(proposal["card"]["size"], expected["card_size"])
        [bad] = out["refused"]
        self.assertIn("sha256: GitHub's digest for uv-x86_64-unknown-linux-gnu.tar.gz is 5acfd9177cfecf0b", bad["why"])
        self.assertTrue((notes / "bad/uv-wrong.json.why.txt").is_file())
        self.assertEqual(w.github_api.calls, [api, api])

    def test_a_request_from_another_host_needs_no_sizes_and_no_lookup(self):
        w = self.w
        zig = json.loads((REPO_ROOT / "packages/contracts/toolbox/examples/good/zig.json").read_text())
        notes = toolbox.work_dir(w.settings) / "requests"
        toolbox.ensure_repo(w.settings, w.home)
        (notes / "zig.json").write_text(json.dumps(zig))
        (notes / "zig-sized.json").write_text(json.dumps(dict(zig, name="zig-sized", download_mb=55)))
        out = toolbox.collect_requests(w.settings, {"project": "robot", "run": "r"}, w.clock().date(), w.github_api)
        self.assertEqual(out["refused"], [])
        self.assertEqual(w.github_api.calls, [])
        cards = {p["name"]: json.loads((self.var / "proposals" / f"{p['id']}.json").read_text())["card"] for p in out["proposed"]}
        self.assertEqual(cards["zig"]["size"], "up to 1024 MB download (measured at install), installed up to 16x it, min 64 MB")
        self.assertEqual(cards["zig-sized"]["size"], "55 MB download, up to 880 MB installed")

    def test_a_github_request_waits_while_github_cant_be_asked(self):
        w = self.w
        gh_dir = REPO_ROOT / "packages/contracts/toolbox/examples/github"
        expected = json.loads((REPO_ROOT / "packages/contracts/toolbox/examples/expected.json").read_text())["github"]
        w.github_api.pages["https://api.github.com" + expected["path"]] = toolbox.GitHubLookupError(
            "GitHub's API limit for this machine (60 lookups an hour, no sign-in) is used up until 11:07 UTC")
        notes = toolbox.work_dir(w.settings) / "requests"
        toolbox.ensure_repo(w.settings, w.home)
        (notes / "uv.json").write_text((gh_dir / expected["request"]).read_text())
        out = toolbox.collect_requests(w.settings, {"project": "robot", "run": "r"}, w.clock().date(), w.github_api)
        self.assertEqual((out["proposed"], out["refused"]), ([], []))
        self.assertIn("used up until 11:07 UTC", out["waiting"][0]["why"])
        self.assertTrue((notes / "uv.json").is_file(), "it stays for the next run's turn")
        self.assertEqual(list((self.var / "proposals").iterdir()), [])
        tag = dict(json.loads((gh_dir / expected["request"]).read_text()))
        tag["url"] = tag["url"].replace("0.13.8", "0.13.99")
        (notes / "uv.json").write_text(json.dumps(tag))
        out = toolbox.collect_requests(w.settings, {"project": "robot", "run": "r"}, w.clock().date(), w.github_api)
        self.assertIn("url: GitHub has no published release", out["refused"][0]["why"])

    def test_github_get_reads_only_api_github_com(self):
        with self.assertRaises(toolbox.GitHubLookupError) as caught:
            toolbox.github_get("https://evil.example/repos/x")
        self.assertTrue(caught.exception.final)

    def test_links_a_run_leaves_in_the_requests_folder_are_never_followed(self):
        w = self.w
        outside = w.home / ".claude-jorah"
        secret = outside / "settings.json"
        secret.write_text("{}")
        good = json.loads((EXAMPLES / "uv.json").read_text())
        bad = dict(good, released="2026-11-16")
        w.behave([
            {"op": "write", "path": str(self.notes / "requests/settings.json"), "text": json.dumps(bad)},
            {"op": "write", "path": str(self.notes / "requests/uv.json"), "text": json.dumps(good)},
        ])
        toolbox.ensure_repo(w.settings, w.home)
        (self.notes / "requests/bad").symlink_to(outside)
        (self.notes / "requests/done").symlink_to(outside)
        w.request()
        [record] = self.runner().tick()
        self.assertEqual(secret.read_text(), "{}", "nothing was moved or written into the link's target")
        self.assertFalse(any(p.name in ("uv.json", "settings.json.why.txt") for p in outside.iterdir()))
        self.assertFalse(os.path.islink(self.notes / "requests/bad"))
        self.assertTrue((self.notes / "requests/bad/settings.json.why.txt").is_file())
        self.assertTrue((self.notes / "requests/done/uv.json").is_file())
        self.assertEqual(len(record["toolbox"]["requests"]["proposed"]), 1)

    def test_a_why_file_link_is_replaced_not_written_through(self):
        w = self.w
        target = w.home / ".claude-jorah" / "keep.txt"
        target.write_text("keep")
        toolbox.ensure_repo(w.settings, w.home)
        (self.notes / "requests/bad").mkdir()
        (self.notes / "requests/bad/x.json.why.txt").symlink_to(target)
        (self.notes / "requests/x.json").write_text("{ not json")
        toolbox.collect_requests(w.settings, {"project": "robot", "run": "r"}, w.clock().date(), w.github_api)
        self.assertEqual(target.read_text(), "keep")
        self.assertFalse(os.path.islink(self.notes / "requests/bad/x.json.why.txt"))

    def test_the_smoke_tests_home_is_in_the_runners_own_state(self):
        self.install(tool_entry())
        self.runner().tick()
        cmd = self.smoke_calls[0]
        home_src = cmd[cmd.index("--bind") + 1]
        self.assertTrue(home_src.startswith(str(self.w.settings.state_root)), home_src)
        self.assertNotIn(str(self.w.home / "sandbox"), home_src)

    def test_notes_a_run_writes_are_committed_by_the_runner(self):
        w = self.w
        w.behave([{"op": "write", "path": str(self.notes / "notes/kicad-cli.md"), "text": "# kicad-cli\n\nERC: `kicad-cli sch erc x.kicad_sch`\n"}])
        w.request()
        [record] = self.runner().tick()
        notes = record["toolbox"]["notes"]
        self.assertEqual(notes["files"], ["notes/kicad-cli.md"])
        self.assertIn("Notes from robot run", git(self.notes, "log", "-1", "--format=%s").stdout)
        self.assertTrue(any("toolbox notes changed: notes/kicad-cli.md" in n for n in w.outbox(record)["notes"]))

    def test_the_brief_lists_tools_with_their_notes_and_how_to_ask_for_more(self):
        w = self.w
        self.install(tool_entry())
        toolbox.write_tested(w.settings, "uv", {"id": "tb-0000000001", "ok": True, "learn": {"run": "x"}})
        toolbox.ensure_repo(w.settings, w.home)
        (self.notes / "notes/uv.md").write_text("# uv\n")
        w.request()
        self.runner().tick()
        brief = w.calls()[-1]["brief"]
        self.assertIn("uv 0.9.18 (uv, uvx; passed its offline smoke test; notes: ~/work/.toolbox/notes/uv.md)", brief)
        self.assertIn("~/work/.toolbox/requests/<name>.json", brief)
        self.assertIn("at least 7 days old", brief)

    def test_toolbox_commands_come_last_on_the_runs_path(self):
        w = self.w
        w.request()
        self.runner().tick()
        path = w.calls()[-1]["env"]["PATH"].split(":")
        self.assertEqual(path[-1], str(self.opt / "bin"))

    def test_a_plain_folder_a_run_made_becomes_the_notes_repo(self):
        (self.notes / "notes").mkdir(parents=True)
        (self.notes / "notes/x.md").write_text("x\n")
        repo = toolbox.ensure_repo(self.w.settings, self.w.home)
        self.assertIsNotNone(repo)
        self.assertEqual(toolbox.commit_notes(self.w.settings, self.w.home, "first")["files"], [".gitignore", "notes/x.md"])

    # ---- installed tools: smoke test and learning run ------------------------------------------------

    def test_a_new_tool_is_smoke_tested_offline_then_learned_once(self):
        w = self.w
        self.install(tool_entry())
        w.behave([
            {"op": "write", "path": str(self.notes / "notes/uv.md"), "text": "# uv\n\n`uv venv` works offline.\n"},
            {"op": "commit", "message": "Notes on uv"},
        ])
        [record] = self.runner().tick()
        self.assertEqual(record["kind"], "learn")
        self.assertEqual(record["outcome"], "ok", record)
        [cmd] = self.smoke_calls
        self.assertEqual(cmd[0], str(self.bwrap))
        for flag in ("--unshare-all", "--die-with-parent", "--clearenv"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--ro-bind") + 1:cmd.index("--ro-bind") + 3], ["/", "/"])
        self.assertEqual(cmd[cmd.index("--") + 1:], ["uv", "--version"])
        self.assertIn(str(self.opt / "bin"), cmd[cmd.index("PATH") + 1])
        tested = toolbox.tested(w.settings, "uv")
        self.assertTrue(tested["ok"])
        self.assertTrue(tested["expectFound"])
        self.assertEqual(tested["learn"]["outcome"], "ok")
        self.assertTrue(tested["learn"]["notes"])

        call = w.calls()[-1]
        self.assertEqual(call["cwd"], str(self.notes.resolve()))
        self.assertIn("Make Python environments quickly.", call["brief"])
        self.assertIn("notes/uv.md", call["brief"])
        argv = call["argv"]
        self.assertEqual(argv[argv.index("--max-turns") + 1], "80")
        self.assertTrue(argv[argv.index("--settings") + 1].endswith("project-settings-web.json"))
        self.assertEqual(git(self.notes, "log", "-1", "--format=%s").stdout.strip(), "Notes on uv")
        self.assertTrue(list((w.settings.project_state("_toolbox") / "runs").glob("*.json")))

        # Nothing more to do on the next tick.
        self.assertEqual(self.runner().tick(), [])
        self.assertEqual(len(self.smoke_calls), 1)

    def test_a_failed_smoke_test_means_no_learning_run(self):
        self.install(tool_entry())
        self.smoke_answer = (127, b"uv: not found\n")
        self.assertEqual(self.runner().tick(), [])
        tested = toolbox.tested(self.w.settings, "uv")
        self.assertFalse(tested["ok"])
        self.assertEqual(tested["exit"], 127)
        self.assertEqual(self.w.calls(), [])

    def test_output_without_the_expected_text_fails(self):
        self.install(tool_entry())
        self.smoke_answer = (0, b"something else\n")
        self.runner().tick()
        self.assertFalse(toolbox.tested(self.w.settings, "uv")["ok"])

    def test_a_reinstall_is_tested_again(self):
        self.install(tool_entry())
        self.smoke_answer = (1, b"")
        self.runner().tick()
        self.install(tool_entry(tid="tb-0000000002", version="0.9.19"))
        self.runner().tick()
        self.assertEqual(len(self.smoke_calls), 2)

    def test_learning_waits_while_frozen(self):
        w = self.w
        self.install(tool_entry())
        Path(w.settings.freeze_file).write_text("frozen")
        self.assertEqual(self.runner().tick(), [])
        self.assertTrue(toolbox.tested(w.settings, "uv")["ok"], "the smoke test needs no model, so it still runs")
        self.assertEqual(w.calls(), [])
        self.assertTrue(any("waits: Jorah is frozen" in line for line in w.logs))

    def test_a_learning_run_writes_its_own_tool_request(self):
        w = self.w
        self.install(tool_entry())
        java = json.loads((EXAMPLES / "java.json").read_text())
        w.behave([{"op": "write", "path": str(self.notes / "requests/java.json"), "text": json.dumps(java)}])
        [record] = self.runner().tick()
        [proposed] = record["toolbox"]["requests"]["proposed"]
        proposal = json.loads((self.var / "proposals" / f"{proposed['id']}.json").read_text())
        self.assertEqual(proposal["from"], {"via": "run", "project": None, "run": record["id"], "learning": "uv"})

    def test_without_the_toolbox_installed_nothing_extra_happens(self):
        w = self.w
        w.settings.toolbox_dir = w.tmp / "missing"
        w.request()
        [record] = self.runner().tick()
        self.assertEqual(record["outcome"], "ok")
        self.assertEqual(self.smoke_calls, [])
        self.assertIn("- none yet", w.calls()[-1]["brief"])


if __name__ == "__main__":
    unittest.main()
