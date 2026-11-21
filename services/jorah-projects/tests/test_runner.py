"""The project runner end to end, against a stand-in claude and a local bare repo as GitHub."""

import fcntl
import json
import os
import shutil
import time
import unittest
from datetime import datetime, timedelta, timezone

from world import TZ, World, git, utc, wt

from jorah_projects import fsio


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.w = World()

    def tearDown(self):
        self.w.cleanup()

    # ---- a normal run ----------------------------------------------------------------------------

    def test_a_run_starts_the_line_runs_claude_and_records_it(self):
        w = self.w
        w.behave([
            {"op": "yaml", "file": wt(w, "project/backlog.yaml"), "list": "items", "id": "T-0001", "set": {"status": "done", "evidence": ["docs/motors.md"]}},
            {"op": "yaml_add", "file": wt(w, "project/questions.yaml"), "list": "questions", "item": {
                "id": "Q-0003", "asked": "2026-11-17", "question": "Which motor?", "why_it_matters": "Cost", "options": [{"key": "A", "text": "Hub", "consequence": "Simple"}, {"key": "B", "text": "Geared", "consequence": "Torque"}],
                "recommendation": "B", "default_if_silent": None, "decide_by": "2026-11-18", "status": "open", "answer": None}},
            {"op": "write", "path": wt(w, "docs/motors.md"), "text": "Two candidates\n"},
            {"op": "commit", "message": "Size the drive motors"},
        ])
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok", record)
        self.assertEqual(git(w.work, "symbolic-ref", "--short", "HEAD").stdout.strip(), "jorah/line")
        self.assertEqual([c["message"] for c in record["commits"]], ["Size the drive motors"])
        self.assertIn("project/backlog.yaml", record["commits"][0]["files"])
        self.assertEqual(record["backlog"]["changed"], [{"id": "T-0001", "from": "ready", "to": "done"}])
        self.assertEqual(record["questions"]["new"], ["Q-0003"])
        self.assertTrue(record["gitleaks"]["ran"] or record["gitleaks"]["error"])
        self.assertNotIn("brief", json.dumps(record))  # no prompt in the record

        call = w.calls()[0]
        argv = call["argv"]
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-5-5")
        self.assertEqual(argv[argv.index("--effort") + 1], "high")
        self.assertEqual(argv[argv.index("--max-turns") + 1], "200")
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "")
        self.assertTrue(argv[argv.index("--settings") + 1].endswith("project-settings-web.json"))
        self.assertNotIn("--disallowedTools", argv)
        self.assertEqual(call["env"]["CLAUDE_CONFIG_DIR"], str(w.settings.claude_config_dir))
        self.assertEqual(call["cwd"], os.path.realpath(w.work))
        self.assertIn("CHARTER.md", call["brief"])
        self.assertIn("1 backlog items ready", call["brief"])

        # Record and outbox, private.
        runs = list((w.state_dir / "runs").glob("*.json"))
        self.assertEqual(len(runs), 1)
        self.assertEqual(oct(runs[0].stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(w.state_dir.stat().st_mode & 0o777), "0o700")
        outbox = json.loads((w.state_dir / "outbox" / runs[0].name).read_text())
        self.assertEqual(outbox["done"][0]["id"], "T-0001")
        self.assertEqual(outbox["questions"][0]["id"], "Q-0003")
        self.assertEqual(outbox["urgent"][0]["kind"], "question-due")  # Q-0003: tomorrow, no default
        self.assertEqual(w.state()["trustedHead"], record["endHead"])
        self.assertEqual(w.contract_problems(), [])

    def test_without_web_the_run_gets_the_no_web_settings_and_web_tools_are_disallowed(self):
        w = self.w
        w.entry["web"] = False
        w.write_registry()
        w.run_now()
        argv = w.calls()[0]["argv"]
        self.assertTrue(argv[argv.index("--settings") + 1].endswith("project-settings.json"))
        self.assertEqual(argv[argv.index("--disallowedTools") + 1:], ["WebFetch", "WebSearch"])

    def test_the_bench_environment_reaches_the_run(self):
        w = self.w
        (w.tools / "bench-env.sh").write_text("export BENCH_MARK=ros-jazzy\nexport PATH=/opt/ros/jazzy/bin:$PATH\n")
        w.entry["bench"] = "robotics"
        w.write_registry()
        w.run_now()
        env = w.calls()[0]["env"]
        self.assertEqual(env["BENCH_MARK"], "ros-jazzy")
        self.assertTrue(env["PATH"].startswith("/opt/ros/jazzy/bin:"))

    def test_uncommitted_work_is_committed_by_the_runner_and_checked(self):
        w = self.w
        w.behave([{"op": "write", "path": wt(w, "notes.md"), "text": "forgot to commit\n"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok")
        self.assertIn("Runner: changes the run left uncommitted", [c["message"] for c in record["commits"]])
        self.assertEqual(git(w.work, "status", "--porcelain").stdout, "")

    def test_someone_elses_uncommitted_work_on_another_branch_is_left_alone(self):
        w = self.w
        (w.work / "wip.txt").write_text("Adam's work in progress\n")
        record = w.run_now()
        self.assertEqual(record["outcome"], "error")
        self.assertIn("uncommitted changes on main", record["reason"])
        self.assertTrue((w.work / "wip.txt").exists())
        self.assertEqual(w.calls(), [])

    # ---- inbox -----------------------------------------------------------------------------------

    def test_inbox_answers_and_results_are_merged_once_and_committed(self):
        w = self.w
        good = w.answer("Q-0001", key="B", note="Landscapers first")
        w.answer("Q-0001", key="Z")              # not an option
        w.answer("Q-0099", key="A")              # no such question
        with open(w.state_dir / "inbox/answers.jsonl", "a") as handle:
            handle.write('{"v": 1, "id": "half-writ')  # a line still being written
        w.result("A-0001", text="31 s, 29 s, 30 s", files={"tap.jpg": b"\xff\xd8 photo"})
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok", record)
        self.assertEqual(record["intake"]["answers"], ["Q-0001"])
        self.assertEqual(record["intake"]["results"], ["A-0001"])
        self.assertEqual(len(record["intake"]["refused"]), 2)

        q = w.item("project/questions.yaml", "questions", "Q-0001")
        self.assertEqual(q["status"], "answered")
        self.assertEqual(q["answer"], {"key": "B", "note": "Landscapers first", "by": "adam", "via": "telegram", "at": "2026-11-17T10:00:00+01:00"})
        t = w.item("project/adam-tasks.yaml", "tasks", "A-0001")
        self.assertEqual(t["status"], "done")
        self.assertEqual(t["result"]["files"], ["field-data/A-0001-1.jpg"])
        self.assertEqual((w.work / "project/field-data/A-0001-1.jpg").read_bytes(), b"\xff\xd8 photo")
        self.assertIn("Founder input from Telegram", w.log("--format=%s"))
        self.assertIn("answers to Q-0001", w.calls()[0]["brief"])
        self.assertEqual(w.contract_problems(), [])
        applied = json.loads((w.state_dir / "inbox/applied.json").read_text())
        self.assertIn(good, applied["answers"])

        # The next run applies nothing again.
        second = w.run_now()
        self.assertEqual(second["intake"]["answers"], [])
        self.assertEqual(second["intake"]["results"], [])

    def test_a_default_applies_only_after_the_question_sat_in_the_digest(self):
        w = self.w
        w.clock.at = datetime(2026, 11, 19, 9, 0, tzinfo=TZ)  # Q-0002's decide_by (11-18) has passed
        first = w.run_now()
        self.assertEqual(first["intake"]["defaults"], [])     # first seen now
        w.clock.advance(hours=47)
        self.assertEqual(w.run_now()["intake"]["defaults"], [])
        w.clock.advance(hours=2)
        third = w.run_now()
        self.assertEqual(third["intake"]["defaults"], ["Q-0002"])
        q = w.item("project/questions.yaml", "questions", "Q-0002")
        self.assertEqual((q["status"], q["answer"]["key"], q["answer"]["by"], q["answer"]["via"]), ("defaulted", "A", "default", "default"))
        self.assertEqual(w.contract_problems(), [])

    # ---- PM-T2, PM-T3: forged answers, charter edits, invalid state -------------------------------

    def test_a_forged_answer_is_reverted_and_the_run_rejected(self):
        w = self.w
        w.behave([
            {"op": "yaml", "file": wt(w, "project/questions.yaml"), "list": "questions", "id": "Q-0002",
             "set": {"status": "answered", "answer": {"key": "B", "note": None, "by": "adam", "via": "telegram", "at": "2026-11-17T10:00:00+01:00"}}},
            {"op": "yaml", "file": wt(w, "project/adam-tasks.yaml"), "list": "tasks", "id": "A-0001",
             "set": {"status": "done", "result": {"text": "made up", "files": [], "at": "2026-11-17T10:00:00+01:00"}}},
            {"op": "commit", "message": "Adam said B"},
        ])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        q = w.item("project/questions.yaml", "questions", "Q-0002")
        self.assertEqual((q["status"], q["answer"]), ("open", None))
        t = w.item("project/adam-tasks.yaml", "tasks", "A-0001")
        self.assertEqual((t["status"], t["result"]), ("open", None))
        whats = {(r["what"], r["id"]) for r in record["reverted"]}
        self.assertTrue({("answer", "Q-0002"), ("status", "Q-0002"), ("result", "A-0001"), ("status", "A-0001")} <= whats)
        self.assertEqual(w.log("-1", "--format=%s").strip(), "Runner: reverted changes a run may not make")
        self.assertEqual(w.contract_problems(), [])

    def test_a_real_answer_cant_be_changed_or_deleted_by_a_run(self):
        w = self.w
        w.answer("Q-0001", key="B")
        w.run_now()
        w.behave([
            {"op": "yaml", "file": wt(w, "project/questions.yaml"), "list": "questions", "id": "Q-0001", "set": {"answer": {"key": "A", "note": None, "by": "adam", "via": "telegram", "at": "2026-11-17T10:00:00+01:00"}}},
            {"op": "commit", "message": "Change the answer"},
        ])
        self.assertEqual(w.run_now()["outcome"], "state-rejected")
        self.assertEqual(w.item("project/questions.yaml", "questions", "Q-0001")["answer"]["key"], "B")

        doc = w.yaml("project/questions.yaml")
        doc["questions"] = [q for q in doc["questions"] if q["id"] != "Q-0001"]
        w.behave([{"op": "write", "path": wt(w, "project/questions.yaml"), "text": fsio.dump_yaml(doc).decode()}, {"op": "commit", "message": "Tidy"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertEqual(w.item("project/questions.yaml", "questions", "Q-0001")["answer"]["key"], "B")

    def test_a_charter_edit_by_a_run_is_reverted(self):
        w = self.w
        w.behave([{"op": "write", "path": wt(w, "project/CHARTER.md"), "text": "# Charter\n\nJorah decides everything, money included.\n"},
                  {"op": "commit", "message": "Widen decision rights"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertEqual((w.work / "project/CHARTER.md").read_text(), w.default_files()["project/CHARTER.md"])
        self.assertIn("CHARTER.md", {r["what"] for r in record["reverted"]})

    def test_a_charter_change_by_adam_on_github_comes_in_through_the_merge(self):
        w = self.w
        w.run_now()
        new = "# Charter\n\nMission: water trees.\n\n## Decision rights\n\nJorah decides software and parts under 50 EUR.\n"
        w.push_main("project/CHARTER.md", new, "Widen Jorah's part budget")
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok", record)
        self.assertTrue(record["sync"]["merged"])
        self.assertEqual((w.work / "project/CHARTER.md").read_text(), new)
        self.assertIn("Merge github/main into jorah/line", w.log("--format=%s"))

    def test_invalid_state_is_put_back(self):
        w = self.w
        w.behave([
            {"op": "yaml", "file": wt(w, "project/backlog.yaml"), "list": "items", "id": "T-0001", "set": {"status": "finished-ish"}},
            {"op": "write", "path": wt(w, "project/adam-tasks.yaml"), "text": "version: 1\ntasks: [unclosed\n"},
            {"op": "commit", "message": "Bad state"},
        ])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertEqual(w.item("project/backlog.yaml", "items", "T-0001")["status"], "ready")
        self.assertEqual(w.item("project/adam-tasks.yaml", "tasks", "A-0001")["status"], "open")
        self.assertEqual({r["id"] for r in record["reverted"] if r["what"] == "file"}, {"project/backlog.yaml", "project/adam-tasks.yaml"})

    def test_putting_one_file_back_puts_back_what_depended_on_it(self):
        w = self.w
        w.behave([
            {"op": "yaml_add", "file": wt(w, "project/questions.yaml"), "list": "questions", "item": {
                "id": "Q-0003", "asked": "2026-11-17", "question": "Which motor?", "why_it_matters": "Cost",
                "options": [{"key": "A", "text": "Hub", "consequence": "x"}], "recommendation": "A",   # one option: invalid
                "default_if_silent": None, "decide_by": "2026-11-20", "status": "open", "answer": None}},
            {"op": "yaml", "file": wt(w, "project/backlog.yaml"), "list": "items", "id": "T-0001", "set": {"status": "blocked", "blocked_on": "Q-0003"}},
            {"op": "commit", "message": "Ask about motors"},
        ])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertEqual([r["id"] for r in record["reverted"]], ["project/questions.yaml", "project/backlog.yaml"])
        self.assertEqual(w.contract_problems(), [])

    def test_changes_to_adams_fields_between_runs_are_reverted_before_the_next(self):
        w = self.w
        w.run_now()
        doc = w.yaml("project/questions.yaml")
        doc["questions"][0].update(status="answered", answer={"key": "A", "note": None, "by": "adam", "via": "telegram", "at": "2026-11-17T10:00:00+01:00"})
        (w.work / "project/questions.yaml").write_bytes(fsio.dump_yaml(doc))
        git(w.work, "commit", "-qam", "A coding job answered for Adam")
        record = w.run_now()
        self.assertEqual([r["when"] for r in record["reverted"]], ["before the run", "before the run"])
        self.assertEqual(w.item("project/questions.yaml", "questions", "Q-0001")["answer"], None)

    def test_a_link_in_the_project_folder_is_never_written_through(self):
        w = self.w
        w.run_now()
        outside = w.tmp / "outside"
        outside.mkdir()
        os.symlink(outside, w.work / "project/field-data")
        git(w.work, "add", "-A")
        git(w.work, "commit", "-qm", "A link out of the repo")
        w.result("A-0001", text="x", files={"p.jpg": b"data"})
        record = w.run_now()
        self.assertEqual(record["outcome"], "error")
        self.assertIn("is a link", record["reason"])
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(len(list((w.state_dir / "inbox/results").glob("*.json"))), 1)  # Adam's result is kept

    # ---- the repo's own git setup ----------------------------------------------------------------

    def test_a_work_repo_with_a_dangerous_git_config_is_refused(self):
        w = self.w
        git(w.work, "config", "core.fsmonitor", "touch /tmp/pwned")
        record = w.run_now()
        self.assertEqual(record["outcome"], "error")
        self.assertIn("core.fsmonitor", record["reason"])
        self.assertEqual(w.calls(), [])

    def test_the_sandbox_s_empty_config_worktree_is_accepted_but_not_a_filled_or_linked_one(self):
        w = self.w
        cfg = w.work / ".git" / "config.worktree"
        cfg.write_text("")  # what Claude Code's sandbox leaves behind after a run
        self.assertNotEqual(w.run_now()["outcome"], "error")
        cfg.write_text("[core]\n\tfsmonitor = touch /tmp/pwned\n")
        record = w.run_now()
        self.assertEqual(record["outcome"], "error")
        self.assertIn(".git/config.worktree exists", record["reason"])
        cfg.unlink()
        os.symlink(w.tmp / "elsewhere", cfg)
        record = w.run_now()
        self.assertEqual(record["outcome"], "error")
        self.assertIn(".git/config.worktree is a link", record["reason"])

    def test_a_github_remote_pointing_elsewhere_is_refused(self):
        w = self.w
        git(w.work, "remote", "set-url", "github", "https://example.invalid/x.git")
        record = w.run_now()
        self.assertEqual(record["outcome"], "error")
        self.assertIn("remote.github.url", record["reason"])

    # ---- merge conflicts ---------------------------------------------------------------------------

    def _conflict(self):
        w = self.w
        w.behave([{"op": "write", "path": wt(w, "README.md"), "text": "# Robot\n\nJorah's line.\n"}, {"op": "commit", "message": "README on the line"}])
        w.run_now()
        w.push_main("README.md", "# Robot\n\nAdam's main.\n")

    def test_a_merge_conflict_is_left_for_the_run_as_its_first_task(self):
        self._conflict()
        w = self.w
        w.answer("Q-0001", key="B")
        w.behave([{"op": "write", "path": wt(w, "README.md"), "text": "# Robot\n\nAdam's main.\nJorah's line.\n"},
                  {"op": "git", "args": ["add", "-A"]}, {"op": "git", "args": ["commit", "-q", "--no-edit"]}])
        record = w.run_now()
        self.assertTrue(record["sync"]["conflict"])
        self.assertEqual(record["outcome"], "ok", record)
        self.assertIn("FIRST: merging github's default branch", w.calls()[-1]["brief"])
        self.assertIn("README.md", w.calls()[-1]["brief"])
        self.assertEqual(record["intake"]["waiting"], "merge conflict first")
        self.assertEqual(git(w.work, "rev-list", "--count", "refs/remotes/github/main..HEAD").stdout.strip() != "0", True)
        self.assertEqual(git(w.work, "merge-base", "--is-ancestor", "refs/remotes/github/main", "HEAD", check=False).returncode, 0)
        # The answer waited, and goes in next time.
        self.assertEqual(w.run_now()["intake"]["answers"], ["Q-0001"])

    def test_an_unresolved_conflict_is_undone_and_tried_again(self):
        self._conflict()
        w = self.w
        w.behave([])
        record = w.run_now()
        self.assertIn("the merge conflict wasn't resolved; the merge was undone and is tried again next run", record["problems"])
        self.assertFalse((w.work / ".git/MERGE_HEAD").exists())
        self.assertEqual(git(w.work, "status", "--porcelain").stdout, "")

    # ---- PM-T6: limits, backoff, freeze, lock ------------------------------------------------------

    def test_a_usage_limit_backs_off_every_run_until_the_reset(self):
        w = self.w
        reset = int((w.clock.at + timedelta(hours=2)).timestamp())
        w.behave([{"op": "emit", "line": {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "rateLimitType": "seven_day", "utilization": 0.6, "resetsAt": reset + 86400}}},
                  {"op": "emit", "line": {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour", "utilization": 1.0, "resetsAt": reset}}},
                  {"op": "result", "set": {"is_error": True, "subtype": "error_during_execution", "result": "You've hit your limit"}}, {"op": "exit", "code": 1}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "usage-limit")
        self.assertEqual(datetime.fromisoformat(w.usage()["backoffUntil"]), datetime.fromtimestamp(reset, tz=timezone.utc))
        self.assertEqual(w.usage()["lastSeen"]["sevenDay"]["utilization"], 0.6)
        w.behave([])
        w.clock.advance(hours=1)
        skipped = w.run_now()
        self.assertEqual(skipped["outcome"], "skipped")
        self.assertIn("usage limit", skipped["reason"])
        self.assertEqual(w.usage()["skipped"], 1)
        self.assertEqual(len(w.calls()), 1)
        w.clock.advance(hours=1, minutes=1)
        self.assertEqual(w.run_now()["outcome"], "ok")

    def test_a_usage_limit_without_a_reset_time_backs_off_an_hour(self):
        w = self.w
        w.behave([{"op": "result", "set": {"is_error": True, "result": "Claude AI usage limit reached"}}, {"op": "exit", "code": 1}])
        self.assertEqual(w.run_now()["outcome"], "usage-limit")
        self.assertEqual(datetime.fromisoformat(w.usage()["backoffUntil"]), w.clock.at + timedelta(hours=1))

    def test_runs_stop_while_the_weekly_limit_is_over_85_percent(self):
        w = self.w
        reset = int((w.clock.at + timedelta(days=2)).timestamp())
        w.behave([{"op": "emit", "line": {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning", "rateLimitType": "seven_day", "utilization": 0.9, "resetsAt": reset}}}])
        self.assertEqual(w.run_now()["outcome"], "ok")
        skipped = w.run_now()
        self.assertEqual(skipped["outcome"], "skipped")
        self.assertIn("weekly limit", skipped["reason"])

    def test_freeze_is_honoured_and_an_unreadable_guard_counts_as_frozen(self):
        w = self.w
        (w.home / ".jorah-guard/FROZEN").write_text("frozen\n")
        record = w.run_now()
        self.assertEqual((record["outcome"], w.calls()), ("skipped", []))
        self.assertIn("frozen", record["reason"])
        os.unlink(w.home / ".jorah-guard/FROZEN")
        shutil.rmtree(w.home / ".jorah-guard")
        self.assertEqual(w.run_now()["outcome"], "skipped")
        (w.home / ".jorah-guard").mkdir()
        self.assertEqual(w.run_now()["outcome"], "ok")

    def test_runs_a_day_are_capped(self):
        w = self.w
        w.entry["limits"]["runsPerDay"] = 2
        w.write_registry()
        self.assertEqual(w.run_now()["outcome"], "ok")
        self.assertEqual(w.run_now()["outcome"], "ok")
        third = w.run_now()
        self.assertEqual(third["outcome"], "skipped")
        self.assertIn("today's 2 runs are used", third["reason"])
        w.clock.advance(days=1)
        self.assertEqual(w.run_now()["outcome"], "ok")

    def test_low_disk_and_paused_projects_skip(self):
        w = self.w
        w.free = 4 * 1024**3
        self.assertIn("GB free", w.run_now()["reason"])
        w.free = 100 * 1024**3
        w.request("pause")
        self.assertIn("Adam paused it", w.run_now()["reason"])
        w.request("resume")
        self.assertEqual(w.run_now()["outcome"], "ok")

    def test_a_locked_project_waits_and_keeps_its_request(self):
        w = self.w
        w.state_dir.mkdir(parents=True, exist_ok=True)
        with open(w.state_dir / "lock", "a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            w.request()
            self.assertEqual(w.tick(), [])
            self.assertIn("a run is already going", w.logs[-1])
        self.assertEqual(w.calls(), [])
        records = w.tick()  # the request waited
        self.assertEqual([r["outcome"] for r in records], ["ok"])

    def test_the_wall_clock_kills_a_run_that_runs_too_long(self):
        w = self.w
        w.minutes = 0.02
        w.behave([{"op": "write", "path": wt(w, "half.md"), "text": "half done\n"}, {"op": "sleep", "seconds": 30}])
        started = time.monotonic()
        record = w.run_now()
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(record["outcome"], "timeout")
        self.assertTrue(record["exit"]["timedOut"])
        self.assertIn("Runner: changes the run left uncommitted", [c["message"] for c in record["commits"]])

    def test_three_failures_in_a_row_are_urgent(self):
        w = self.w
        w.behave([{"op": "result", "set": {"is_error": True, "subtype": "error_during_execution", "terminal_reason": "model_error"}}, {"op": "exit", "code": 1}])
        for _ in range(3):
            record = w.run_now()
        self.assertEqual(record["outcome"], "failed")
        outbox = json.loads((w.state_dir / "outbox" / f"{record['id']}.json").read_text())
        self.assertIn("failures", [u["kind"] for u in outbox["urgent"]])

    # ---- schedule ----------------------------------------------------------------------------------

    def test_level_0_runs_only_on_request_and_level_1_on_the_schedule(self):
        w = self.w
        self.assertEqual(w.tick(), [])                      # 10:30 is due, but level 0
        w.entry["level"] = 1
        w.write_registry()
        records = w.tick()
        self.assertEqual([(r["trigger"], r["slot"]) for r in records], [("schedule", "2026-11-17 10:30")])
        self.assertEqual(w.tick(), [])                      # the same slot runs once
        w.clock.at = datetime(2026, 11, 17, 21, 0, tzinfo=TZ)
        self.assertEqual(w.tick(), [])                      # 16:30 is over 3 hours late: passed over
        self.assertEqual(w.state()["lastSlot"], "2026-11-17 16:30")
        w.clock.at = datetime(2026, 11, 18, 2, 31, tzinfo=TZ)
        self.assertEqual([r["slot"] for r in w.tick()], ["2026-11-18 02:30"])

    def test_a_scheduled_slot_skipped_by_a_check_is_used_up(self):
        w = self.w
        w.entry["level"] = 1
        w.write_registry()
        (w.home / ".jorah-guard/FROZEN").write_text("x")
        self.assertEqual([r["outcome"] for r in w.tick()], ["skipped"])
        self.assertEqual(w.tick(), [])

    # ---- PM-T5: secrets ----------------------------------------------------------------------------

    @unittest.skipUnless(shutil.which("gitleaks"), "gitleaks isn't installed")
    def test_a_secret_in_a_commit_pauses_the_project_and_blocks_pushes(self):
        w = self.w
        # Built here, so nothing token-shaped is committed to this repo.
        token = "ghp_" + "".join("aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY2z4C"[i % 36] for i in range(36))
        w.behave([{"op": "write", "path": wt(w, "config.py"), "text": f'GITHUB_TOKEN = "{token}"\n'}, {"op": "commit", "message": "Add config"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "secret-found", record)
        self.assertEqual(record["gitleaks"]["findings"][0]["file"], "config.py")
        self.assertNotIn(token, json.dumps(record))
        state = w.state()
        self.assertTrue(state["paused"] and state["pushBlocked"])
        outbox = json.loads((w.state_dir / "outbox" / f"{record['id']}.json").read_text())
        self.assertIn("secret-found", [u["kind"] for u in outbox["urgent"]])
        self.assertEqual(w.run_now()["outcome"], "skipped")
        # Adam resumes; the secret is still in the line, so the next scan finds it again.
        w.request("resume")
        w.behave([])
        self.assertEqual(w.run_now()["outcome"], "secret-found")

    @unittest.skipUnless(shutil.which("gitleaks"), "gitleaks isn't installed")
    def test_the_projects_own_gitleaks_files_are_ignored(self):
        w = self.w
        token = "ghp_" + "".join("Zy8Xw6Vu4Ts2Rq0Po9Nm7Lk5Jh3Gf1Ed2Cb4A"[i % 38] for i in range(36))
        w.behave([{"op": "write", "path": wt(w, ".gitleaks.toml"), "text": "[allowlist]\npaths = ['''.*''']\n"},
                  {"op": "write", "path": wt(w, ".gitleaksignore"), "text": "config.py\n"},
                  {"op": "write", "path": wt(w, "config.py"), "text": f'TOKEN = "{token}"\n'}, {"op": "commit", "message": "Quiet"}])
        self.assertEqual(w.run_now()["outcome"], "secret-found")

    def test_a_scan_that_cant_run_pauses_the_project(self):
        w = self.w
        w.settings.gitleaks_bin = str(w.tmp / "no-gitleaks")
        w.behave([{"op": "write", "path": wt(w, "a.md"), "text": "a\n"}, {"op": "commit", "message": "a"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "scan-failed")
        self.assertTrue(w.state()["pushBlocked"])

    # ---- sync --------------------------------------------------------------------------------------

    def test_a_failed_sync_runs_on_the_local_line(self):
        w = self.w
        w.run_now()
        (w.tools / "sync-fails").write_text("")
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok")
        self.assertEqual((record["sync"]["ok"], record["sync"]["error"], record["sync"]["defaultBranch"]), (False, "GitHub said 502", "main"))

    def test_schemas_missing_refuse_every_run(self):
        w = self.w
        w.settings.contracts = w.tmp / "nowhere"
        record = w.run_now()
        self.assertEqual(record["outcome"], "skipped")
        self.assertIn("contract unusable", record["reason"])


if __name__ == "__main__":
    unittest.main()
