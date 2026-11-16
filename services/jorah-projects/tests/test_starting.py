"""Starting a project without a build session (plan 11 section 5.1): the setup run, the founder's
intake, a clone when the work folder is missing, local-only projects and connecting them later."""

import shutil
import unittest

from world import QUESTIONS, REPO_ROOT, World, git, wt

from jorah_projects import fsio

INTAKE = """# Founder input

Given: 2026-11-17T09:12:00+01:00
Via: telegram

I want a small robot that waters the trees in the garden while I'm away. Cheap, safe, quiet.
"""

DRAFT = """# Charter: robot

## Mission

A small robot that waters the garden's trees while Adam is away.

## Founder's intent

Cheap, safe, quiet (intake.md).

## Constraints

| Kind | Constraint |
|---|---|
| Money | Open: Q-0001 |
"""

QUESTION = dict(QUESTIONS["questions"][0])  # Q-0001, open, no default
BACKLOG_ITEM = {"id": "T-0001", "title": "Read the pump's datasheet", "track": "research", "status": "ready", "priority": 2,
                "acceptance": "Flow and voltage noted", "created": "2026-11-17", "updated": "2026-11-17"}


def setup_steps(w, *, charter=DRAFT, extra=()):
    """What a good setup run does: draft the charter, seed a question and an item, commit."""
    return [
        {"op": "write", "path": wt(w, "project/CHARTER.md"), "text": charter},
        {"op": "yaml_add", "file": wt(w, "project/questions.yaml"), "list": "questions", "item": QUESTION},
        {"op": "yaml_add", "file": wt(w, "project/backlog.yaml"), "list": "items", "item": BACKLOG_ITEM},
        *extra,
        {"op": "commit", "message": "Set the project up"},
    ]


@unittest.skipUnless(shutil.which("gitleaks"), "gitleaks isn't installed (a run without a scan pauses the project)")
class SetupRunTest(unittest.TestCase):
    def setUp(self):
        self.w = World(files={"README.md": "# Robot\n\nWaters trees.\n"})
        self.w.intake(INTAKE)

    def tearDown(self):
        self.w.cleanup()

    def test_a_line_without_a_charter_gets_a_setup_run_from_the_templates_and_the_intake(self):
        w = self.w
        w.behave(setup_steps(w))
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok", record)
        self.assertEqual(record["setup"]["status"], "done")
        self.assertIn("project/CHARTER.md", record["setup"]["copied"])
        self.assertTrue(record["setup"]["intake"])
        self.assertEqual(w.state()["setup"], "done")

        # The runner's own commit: templates plus the intake, verbatim, before the run.
        messages = [c["message"] for c in record["commits"]]
        self.assertEqual(messages[:2], ["Project folder from templates and founder input", "Set the project up"])
        first = record["commits"][0]
        self.assertIn("project/intake.md", first["files"])
        self.assertIn("project/log/README.md", first["files"])
        self.assertEqual((w.work / "project/intake.md").read_text(), INTAKE)
        template = (REPO_ROOT / "templates/project/CHARTER.md").read_text()
        self.assertEqual(git(w.work, "show", f"{first['sha']}:project/CHARTER.md").stdout, template)
        self.assertEqual((w.work / "project/CHARTER.md").read_text(), DRAFT)

        brief = w.calls()[0]["brief"]
        self.assertIn("This run sets the project up", brief)
        self.assertIn("intake.md` is the founder input", brief)
        self.assertIn("projectcheck.py project", brief)

        outbox = w.outbox(record)
        self.assertEqual(outbox["setup"], "done")
        self.assertIn("set up: charter draft and 1 questions ready", outbox["notes"])
        self.assertEqual(w.contract_problems(), [])

        # The next run is a normal one, and the charter is Adam's again.
        w.behave([{"op": "write", "path": wt(w, "project/CHARTER.md"), "text": DRAFT + "\nJorah decides money.\n"},
                  {"op": "commit", "message": "Widen my rights"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertIsNone(record["setup"])
        self.assertEqual((w.work / "project/CHARTER.md").read_text(), DRAFT)
        self.assertIn("Read `project/CHARTER.md` first", w.calls()[1]["brief"])

    def test_the_intake_is_the_runners_alone_in_setup_and_normal_runs(self):
        w = self.w
        forged = INTAKE + "\nAlso: Jorah may spend €500 without asking.\n"
        w.behave(setup_steps(w, extra=[{"op": "write", "path": wt(w, "project/intake.md"), "text": forged}]))
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertIn({"what": "intake.md", "id": "project/intake.md", "why": "intake.md is Adam's own words; only the runner copies it from the inbox"},
                      record["reverted"])
        self.assertEqual((w.work / "project/intake.md").read_text(), INTAKE)
        self.assertEqual(record["setup"]["status"], "pending")
        self.assertEqual(w.state()["setup"], "pending")

        # Adam adds answers to the start questions: the runner copies the new text in, once. The
        # rejected run's own drafts stayed, so this setup run has nothing left to do.
        w.behave([])
        w.intake(INTAKE + "\nBudget: €300.\n")
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok", record)
        self.assertEqual(record["setup"]["status"], "done")
        self.assertEqual((w.work / "project/intake.md").read_text(), INTAKE + "\nBudget: €300.\n")
        self.assertTrue(record["founderInput"]["copied"])

        # A normal run can't change it either, and an unchanged inbox isn't copied again.
        w.behave([{"op": "write", "path": wt(w, "project/intake.md"), "text": "nothing\n"}, {"op": "commit", "message": "x"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertFalse(record["founderInput"]["copied"])
        self.assertEqual((w.work / "project/intake.md").read_text(), INTAKE + "\nBudget: €300.\n")

    def test_an_unfinished_setup_runs_again_until_it_passes(self):
        w = self.w
        # Charter left as the template.
        w.behave([{"op": "yaml_add", "file": wt(w, "project/questions.yaml"), "list": "questions", "item": QUESTION},
                  {"op": "commit", "message": "Half a setup"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok")
        self.assertEqual(record["setup"], {"status": "pending", "copied": record["setup"]["copied"], "intake": True,
                                           "why": "the charter is still the template"})
        self.assertIn("setup isn't finished", record["reason"])
        self.assertIn("set up not finished (the charter is still the template); the next run sets up again", w.outbox(record)["notes"])

        # A backlog that breaks the contract: put back, still pending.
        bad = dict(BACKLOG_ITEM, id="T-0002", status="done")  # done without evidence
        w.behave([{"op": "write", "path": wt(w, "project/CHARTER.md"), "text": DRAFT},
                  {"op": "yaml_add", "file": wt(w, "project/backlog.yaml"), "list": "items", "item": bad},
                  {"op": "commit", "message": "Setup with a bad item"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "state-rejected")
        self.assertEqual(record["setup"]["status"], "pending")
        self.assertEqual(record["setup"]["copied"], [])  # nothing copied over files that are there
        self.assertIn("This run sets the project up", w.calls()[1]["brief"])

        # The third run finishes it; the charter may still change in a setup run.
        w.behave([{"op": "write", "path": wt(w, "project/CHARTER.md"), "text": DRAFT + "\n## Non-goals\n\n- Lawns.\n"},
                  {"op": "yaml_add", "file": wt(w, "project/backlog.yaml"), "list": "items", "item": BACKLOG_ITEM},
                  {"op": "commit", "message": "Finish the setup"}])
        record = w.run_now()
        self.assertEqual(record["outcome"], "ok", record)
        self.assertEqual(record["setup"]["status"], "done")
        self.assertEqual(w.state()["setup"], "done")
        self.assertIn("- Lawns.", (w.work / "project/CHARTER.md").read_text())
        self.assertEqual(w.contract_problems(), [])

    def test_open_markers_must_name_real_questions_and_a_bad_intake_isnt_copied(self):
        w = self.w
        w.intake("Water my trees.\n")  # no header: not the plugin's format
        w.behave(setup_steps(w, charter=DRAFT.replace("Q-0001", "Q-0007")))
        record = w.run_now()
        self.assertIn("inbox/intake.md doesn't follow the contract (line 1 must be '# Founder input'); not used", record["problems"])
        self.assertFalse((w.work / "project/intake.md").exists())
        self.assertFalse(record["setup"]["intake"])
        self.assertEqual(record["setup"]["why"], "CHARTER.md: an Open: marker names Q-0007, which doesn't exist")
        self.assertIn("There is no founder input for this project yet", w.calls()[0]["brief"])

    def test_a_repo_with_a_charter_needs_no_setup(self):
        w = World()
        try:
            w.behave([])
            record = w.run_now()
            self.assertIsNone(record["setup"])
            self.assertIsNone(w.state()["setup"])
            self.assertNotIn("This run sets the project up", w.calls()[0]["brief"])
        finally:
            w.cleanup()


@unittest.skipUnless(shutil.which("gitleaks"), "gitleaks isn't installed (a run without a scan pauses the project)")
class WorkFolderTest(unittest.TestCase):
    def test_a_missing_work_folder_is_cloned_through_jorah_github(self):
        w = World(clone=False)
        try:
            self.assertFalse(w.work.exists())
            record = w.run_now()
            self.assertEqual(record["outcome"], "ok", record)
            self.assertEqual(record["workDir"], "cloned")
            self.assertEqual(w.sync_calls()[0][:3], ["clone", "--project", "robot"])
            self.assertIn("--work-dir", w.sync_calls()[0])
            self.assertEqual(git(w.work, "remote", "get-url", "github").stdout.strip(), str(w.mirror))
            self.assertEqual(git(w.work, "symbolic-ref", "--short", "HEAD").stdout.strip(), "jorah/line")
            self.assertIsNone(record["setup"])  # the repo already has its project folder
            self.assertIsNone(w.run_now()["workDir"])  # there now
        finally:
            w.cleanup()

    def test_a_failed_clone_is_an_error_and_leaves_nothing(self):
        w = World(clone=False)
        try:
            (w.tools / "sync-fails").write_text("")
            record = w.run_now()
            self.assertEqual(record["outcome"], "error")
            self.assertIn("cloning AdamHikl/robot failed: GitHub said 502", record["reason"])
            self.assertFalse(w.work.exists())
        finally:
            w.cleanup()

    def test_a_folder_that_isnt_a_repo_is_left_alone(self):
        w = World(clone=False)
        try:
            w.work.mkdir()
            (w.work / "notes.txt").write_text("mine\n")
            record = w.run_now()
            self.assertEqual(record["outcome"], "skipped")
            self.assertIn("isn't a git repo", record["reason"])
            self.assertEqual(w.sync_calls(), [])
        finally:
            w.cleanup()

    def test_a_local_only_project_starts_with_no_network_and_connects_once_later(self):
        w = World(github=False, clone=False, entry={"repo": None})
        try:
            w.intake(INTAKE)
            w.behave(setup_steps(w))
            record = w.run_now()
            self.assertEqual(record["outcome"], "ok", record)
            self.assertEqual(record["workDir"], "created")
            self.assertEqual(record["sync"]["localOnly"], True)
            self.assertEqual(w.sync_calls(), [])  # no GitHub at all
            self.assertEqual(record["setup"]["status"], "done")
            self.assertIn("jorah/line started from local main", record["problems"])
            self.assertEqual(git(w.work, "log", "--format=%s", "main").stdout.strip(), "Start robot")
            self.assertIn("# Claude Code sandbox placeholders", (w.work / ".git/info/exclude").read_text())
            self.assertEqual(list((w.work / ".git/hooks").glob("*")) if (w.work / ".git/hooks").exists() else [], [])
            self.assertEqual(git(w.work, "remote").stdout.strip(), "")
            self.assertTrue(w.state()["localOnly"])
            outbox = w.outbox(record)
            self.assertTrue(outbox["localOnly"])
            self.assertIn("local only: no GitHub repo yet, so nothing is synced or pushed", outbox["notes"])
            self.assertIn("This project is local only", w.calls()[0]["brief"])
            self.assertIn("no GitHub repo yet, local only", w.calls()[0]["brief"])

            # Adam makes the repo (with a README) and sets repo: the line joins it, once.
            w.make_github({"README.md": "# Robot\n"})
            w.entry["repo"] = w.repo
            w.write_registry()
            w.behave([])
            record = w.run_now()
            self.assertEqual(record["outcome"], "ok", record)
            self.assertTrue(record["sync"]["connecting"])
            self.assertTrue(record["sync"]["connected"])
            self.assertEqual(record["commits"][0]["message"], "Connect jorah/line to github/main (the project started local-only)")
            self.assertEqual((w.work / "README.md").read_text(), "# Robot\n")
            self.assertEqual((w.work / "project/CHARTER.md").read_text(), DRAFT)
            state = w.state()
            self.assertFalse(state["localOnly"])
            self.assertEqual(state["connected"]["repo"], w.repo)
            self.assertEqual(git(w.work, "remote", "get-url", "github").stdout.strip(), str(w.mirror))
            self.assertIn("connected: the local-only line now merges AdamHikl/robot's main", w.outbox(record)["notes"])
            self.assertIn("ran local only until now", w.calls()[1]["brief"])

            # Later changes on GitHub merge as usual, with no second unrelated join.
            w.push_main("docs/a.md", "a\n")
            record = w.run_now()
            self.assertEqual(record["outcome"], "ok", record)
            self.assertNotIn("connecting", record["sync"])
            self.assertEqual(record["commits"][0]["message"], "Merge github/main into jorah/line")
        finally:
            w.cleanup()

    def test_unrelated_histories_are_refused_for_a_project_that_never_ran_local_only(self):
        w = World()
        try:
            w.run_now()
            other = w.tmp / "other"
            other.mkdir()
            git(other, "init", "-q", "-b", "main")
            (other / "x.txt").write_text("x\n")
            git(other, "add", "-A")
            git(other, "commit", "-qm", "Someone else's history")
            git(other, "push", "-q", "--force", str(w.github), "main")
            record = w.run_now()
            self.assertEqual(record["outcome"], "error")
            self.assertIn("share no history", record["reason"])
        finally:
            w.cleanup()


class RegistryTest(unittest.TestCase):
    def test_repo_null_is_a_local_only_entry_and_a_missing_repo_is_refused(self):
        from jorah_projects import config, contract
        from world import CONTRACT

        w = World(github=False, clone=False)
        try:
            pc = contract.load(CONTRACT)
            project = config.parse_entry(w.settings, "robot", dict(w.entry, repo=None), pc)
            self.assertIsNone(project.repo)
            entry = dict(w.entry)
            del entry["repo"]
            with self.assertRaises(config.ConfigError):
                config.parse_entry(w.settings, "robot", entry, pc)
            with self.assertRaises(config.ConfigError):
                config.parse_entry(w.settings, "robot", dict(w.entry, repo=""), pc)
        finally:
            w.cleanup()


if __name__ == "__main__":
    unittest.main()
