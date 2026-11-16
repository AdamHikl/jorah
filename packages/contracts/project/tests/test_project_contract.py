"""Contract jorah-project-v1: the schemas take the examples and the templates, and refuse the bad ones."""

import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import projectcheck as pc  # noqa: E402

GOOD = HERE / "examples" / "good"
BAD = HERE / "examples" / "bad"
TEMPLATES = REPO / "templates" / "project"
SCHEMAS = ("backlog", "questions", "adam-tasks", "project-config")

# Every bad example and the reason it must be refused for, so a file can't fail by accident.
EXPECTED = {
    "adam-tasks.done-without-result.yaml": "a done task needs result",
    "adam-tasks.file-climbs-out.yaml": "files[0]: has the wrong form",
    "adam-tasks.file-of-another-task.yaml": "isn't named for this task",
    "adam-tasks.file-outside-field-data.yaml": "files[0]: has the wrong form",
    "adam-tasks.id-letter-t.yaml": ".id: has the wrong form",
    "adam-tasks.no-send-back.yaml": "is missing 'send_back'",
    "adam-tasks.no-steps.yaml": "steps: has fewer than 1 items",
    "adam-tasks.open-with-result.yaml": "an open task has no result",
    "adam-tasks.result-empty.yaml": "result needs text or files",
    "adam-tasks.result-extra-field.yaml": "unknown field 'by'",
    "adam-tasks.unknown-status.yaml": "status: isn't one of the allowed values",
    "backlog.adam-task-on-eng-track.yaml": "adam_task is only for track adam",
    "backlog.adam-track-without-task.yaml": "track adam needs adam_task",
    "backlog.alias.yaml": "anchors and aliases aren't allowed",
    "backlog.blocked-on-a-task.yaml": "blocked_on: has the wrong form",
    "backlog.blocked-on-nothing.yaml": "names no blocked_on and no depends_on",
    "backlog.date-in-words.yaml": "created: must be a date",
    "backlog.dependency-cycle.yaml": "dependency cycle",
    "backlog.depends-on-itself.yaml": "depends on itself",
    "backlog.depends-on-missing.yaml": "isn't in the backlog",
    "backlog.done-without-evidence.yaml": "done without evidence",
    "backlog.dropped-without-reason.yaml": "dropped without a reason",
    "backlog.duplicate-id.yaml": "is used twice",
    "backlog.duplicate-key.yaml": "duplicate key",
    "backlog.id-three-digits.yaml": ".id: has the wrong form",
    "backlog.impossible-date.yaml": "updated: must be a date",
    "backlog.not-yaml.yaml": "not valid YAML",
    "backlog.priority-zero.yaml": "priority: is below 1",
    "backlog.unknown-field.yaml": "unknown field 'owner'",
    "backlog.unknown-track.yaml": "track: isn't one of the allowed values",
    "backlog.updated-before-created.yaml": "updated is before created",
    "backlog.version-2.yaml": "version: has the wrong value",
    "intake.given-no-offset.md": "line 3 must be 'Given: '",
    "intake.no-blank-line.md": "lines 2 and 5 must be blank",
    "intake.no-given.md": "line 3 must be 'Given: '",
    "intake.no-title.md": "line 1 must be '# Founder input'",
    "intake.no-words.md": "has no founder words after the header",
    "intake.via-email.md": "line 4 must be 'Via: '",
    "project-config.bench-unknown.json": "bench: isn't one of the allowed values",
    "project-config.branch-main.json": "branch: has the wrong form",
    "project-config.branch-outside-jorah.json": "branch: has the wrong form",
    "project-config.level-3.json": "level: is above 2",
    "project-config.level-true.json": "level: must be integer",
    "project-config.minutes-missing.json": "is missing 'minutesPerRun'",
    "project-config.no-paused.json": "is missing 'paused'",
    "project-config.repo-empty.json": "repo: has the wrong form",
    "project-config.repo-missing.json": "is missing 'repo'",
    "project-config.repo-number.json": "repo: must be string or null",
    "project-config.repo-url.json": "repo: has the wrong form",
    "project-config.runs-too-many.json": "runsPerDay: is above 8",
    "project-config.schedule-bad-time.json": "schedule[0]: has the wrong form",
    "project-config.schedule-repeated.json": "schedule: has repeated items",
    "project-config.statedir-absolute.json": "stateDir: has the wrong form",
    "project-config.statedir-git.json": "stateDir: has the wrong form",
    "project-config.unknown-field.json": "unknown field 'token'",
    "project-config.workdir-dotdot.json": "workDir: has the wrong form",
    "project-config.workdir-relative.json": "workDir: has the wrong form",
    "questions.answer-by-jorah.yaml": "answer.by: isn't one of the allowed values",
    "questions.answer-empty.yaml": "answer needs a key or a note",
    "questions.answer-key-not-an-option.yaml": "answer.key isn't one of the option keys",
    "questions.answer-without-offset.yaml": "answer.at: must be an ISO 8601",
    "questions.answered-by-default.yaml": "answered by adam",
    "questions.answered-without-answer.yaml": "an answered question needs answer",
    "questions.decide-by-before-asked.yaml": "decide_by is before asked",
    "questions.default-without-decide-by.yaml": "a default needs decide_by",
    "questions.defaulted-to-other-key.yaml": "the default, by default",
    "questions.id-five-digits.yaml": ".id: has the wrong form",
    "questions.missing-default-field.yaml": "is missing 'default_if_silent'",
    "questions.one-option.yaml": "options: has fewer than 2 items",
    "questions.open-with-answer.yaml": "an open question has no answer",
    "questions.option-key-lowercase.yaml": "key: has the wrong form",
    "questions.recommendation-not-an-option.yaml": "recommendation isn't one of the option keys",
    "questions.repeated-option-key.yaml": "option keys repeat",
    "questions.unknown-status.yaml": "status: isn't one of the allowed values",
    "questions.unquoted-commas.yaml": "unknown field 'low price'",
}

SINGLE = {"backlog": pc.check_backlog, "questions": pc.check_questions, "adam-tasks": pc.check_adam_tasks}


def problems_of_bad_file(path):
    kind = path.name.split(".")[0]
    if kind == "intake":
        return pc.check_intake_text(path.read_text())
    if kind == "project-config":
        return pc.validate(pc.load_schema(kind), json.loads(path.read_text()))
    try:
        data = pc.load_yaml(path)
    except pc.LoadError as error:
        return [str(error)]
    return pc.check_file(kind, data) or SINGLE[kind](data)


class SchemaFilesTest(unittest.TestCase):
    def test_every_schema_loads_and_uses_only_known_keywords(self):
        for name in SCHEMAS:
            with self.subTest(name=name):
                schema = pc.load_schema(name)
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["$id"], f"jorah-project/{name}/v1")

    def test_a_keyword_the_checker_doesnt_do_is_refused(self):
        for bad in ({"type": "object", "oneOf": []}, {"type": "object", "additionalProperties": True},
                    {"type": "object", "properties": {"a": {"type": "string"}}},
                    {"type": "string", "format": "email"}, {"type": "thing"},
                    {"type": "object", "additionalProperties": False, "required": ["x"], "properties": {}}):
            with self.subTest(bad=bad), self.assertRaises(pc.SchemaError):
                pc.check_schema(bad)

    def test_state_files_say_version_1(self):
        for name in ("backlog", "questions", "adam-tasks"):
            self.assertEqual(pc.load_schema(name)["properties"]["version"], {"const": 1})


class GoodExamplesTest(unittest.TestCase):
    def test_the_example_project_passes(self):
        self.assertEqual(pc.check_project(GOOD / "project"), [])

    def test_the_example_registry_passes(self):
        self.assertEqual(pc.check_registry(json.loads((GOOD / "projects.json").read_text())), [])

    def test_the_templates_pass(self):
        self.assertTrue(TEMPLATES.is_dir(), "templates/project is missing")
        self.assertEqual(pc.check_project(TEMPLATES), [])

    def test_every_file_in_the_plans_table_has_a_template(self):
        # intake.md has none on purpose: only the runner writes it, from the founder's chat message.
        self.assertFalse((TEMPLATES / "intake.md").exists())
        for name in ("CHARTER.md", "backlog.yaml", "questions.yaml", "adam-tasks.yaml", "DECISIONS.md",
                     "log/README.md", "research/README.md", "field-data/README.md"):
            with self.subTest(name=name):
                self.assertTrue((TEMPLATES / name).is_file())

    def test_the_cli_exits_0_1_and_2(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pc.main([str(GOOD / "project")]), 0)
            self.assertEqual(pc.main(["--registry", str(GOOD / "projects.json")]), 0)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(pc.main([]), 2)
            with tempfile.TemporaryDirectory() as empty:
                self.assertEqual(pc.main([empty]), 1)
        self.assertIn("CHARTER.md: is missing", out.getvalue())


class SetupSkeletonTest(unittest.TestCase):
    """A setup run starts from a copy of templates/project plus the runner's intake.md."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "project"
        shutil.copytree(TEMPLATES, self.project)
        shutil.copy(GOOD / "project" / "intake.md", self.project / "intake.md")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_the_copied_skeleton_passes_as_it_is(self):
        self.assertEqual(pc.check_project(self.project), [])

    def test_an_open_marker_must_name_a_question_the_setup_run_added(self):
        charter = self.project / "CHARTER.md"
        charter.write_text(charter.read_text().replace(
            "<One or two sentences: what this project makes, for whom, and why it matters.>", "Open: Q-0001"))
        self.assertEqual(pc.check_project(self.project), ["CHARTER.md: an Open: marker names Q-0001, which doesn't exist"])
        (self.project / "questions.yaml").write_text('''version: 1
questions:
  - id: Q-0001
    asked: 2026-11-16
    question: What is the mission?
    why_it_matters: Everything else follows from it
    options:
      - key: A
        text: Water trees
        consequence: A robot
      - key: B
        text: Teach watering
        consequence: A guide
    recommendation: null
    default_if_silent: null
    decide_by: null
    status: open
    answer: null
''')
        self.assertEqual(pc.check_project(self.project), [])


class PlanExamplesTest(unittest.TestCase):
    """docs/plan/11-project-mode.md section 3 shows the contract to the other sessions; it must pass too."""

    def blocks(self, language):
        plan = (REPO / "docs" / "plan" / "11-project-mode.md").read_text()
        section = plan.split("## 3. The project folder", 1)[1].split("\n## 4. ", 1)[0]
        return [b.split("\n", 1)[1] for b in section.split("```")[1::2] if b.startswith(language + "\n")]

    def test_the_yaml_examples_pass_their_schemas(self):
        kinds = []
        for text in self.blocks("yaml"):
            data = pc.load_yaml_text(text)
            kind = {"items": "backlog", "questions": "questions", "tasks": "adam-tasks"}[next(k for k in data if k != "version")]
            kinds.append(kind)
            with self.subTest(kind=kind):
                self.assertEqual(pc.check_file(kind, data), [])
        self.assertEqual(sorted(kinds), ["adam-tasks", "backlog", "questions"])

    def test_the_registry_example_passes(self):
        (text,) = self.blocks("json")
        self.assertEqual(pc.check_registry(json.loads(text)), [])


class BadExamplesTest(unittest.TestCase):
    def test_every_bad_example_is_listed(self):
        self.assertEqual(sorted(p.name for p in BAD.iterdir()), sorted(EXPECTED))

    def test_every_bad_example_is_refused_for_its_reason(self):
        for name, reason in EXPECTED.items():
            with self.subTest(name=name):
                problems = problems_of_bad_file(BAD / name)
                self.assertTrue(problems, "was accepted")
                self.assertTrue(any(reason in p for p in problems), problems)


class ProjectFolderTest(unittest.TestCase):
    """Rules that need the whole folder: links between files, field data on disk, file names."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "project"
        shutil.copytree(GOOD / "project", self.project)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit(self, name, change):
        path = self.project / name
        path.write_text(change(path.read_text()))

    def assertProblem(self, fragment):
        problems = pc.check_project(self.project)
        self.assertTrue(any(fragment in p for p in problems), problems)

    def test_blocked_on_a_question_that_doesnt_exist(self):
        self.edit("backlog.yaml", lambda s: s.replace("blocked_on: Q-0001", "blocked_on: Q-0099"))
        self.assertProblem("backlog.yaml: items[1] T-0002: blocked on Q-0099, which doesn't exist")

    def test_blocked_on_a_task_that_doesnt_exist(self):
        self.edit("backlog.yaml", lambda s: s.replace("blocked_on: Q-0001", "blocked_on: A-0099"))
        self.assertProblem("blocked on A-0099, which doesn't exist")

    def test_mirror_of_a_task_that_doesnt_exist(self):
        self.edit("backlog.yaml", lambda s: s.replace("adam_task: A-0001", "adam_task: A-0042"))
        self.assertProblem("mirrors A-0042, which doesn't exist")

    def test_field_data_file_missing(self):
        (self.project / "field-data" / "A-0001-1.jpg").unlink()
        self.assertProblem("result file field-data/A-0001-1.jpg is missing")

    def test_missing_files(self):
        (self.project / "CHARTER.md").unlink()
        (self.project / "questions.yaml").unlink()
        problems = pc.check_project(self.project)
        self.assertIn("CHARTER.md: is missing", problems)
        self.assertIn("questions.yaml: is missing", problems)
        # Without questions.yaml, links to questions can't be checked, and aren't reported.
        self.assertFalse(any("Q-0001, which doesn't exist" in p for p in problems), problems)

    def test_log_names(self):
        (self.project / "log" / "notes.md").write_text("x")
        (self.project / "log" / "2026-02-30.md").write_text("x")
        problems = pc.check_project(self.project)
        self.assertIn("log/notes.md: log files are named YYYY-MM-DD.md", problems)
        self.assertIn("log/2026-02-30.md: log files are named YYYY-MM-DD.md", problems)

    def test_a_schema_failure_is_named_by_file(self):
        self.edit("questions.yaml", lambda s: s.replace("status: open", "status: closed", 1))
        self.assertProblem("questions.yaml: $.questions[0].status: isn't one of the allowed values")

    def test_messages_never_carry_values(self):
        self.edit("backlog.yaml", lambda s: s.replace("track: biz", "track: secret-token-123"))
        self.edit("intake.md", lambda s: s.replace("Via: telegram", "Via: secret-token-456"))
        problems = pc.check_project(self.project)
        self.assertIn("intake.md: line 4 must be 'Via: ' and one of telegram, voice, app", problems)
        self.assertFalse(any("secret-token-" in p for p in problems), problems)

    def test_intake_is_optional_and_checked_when_present(self):
        (self.project / "intake.md").unlink()
        self.assertEqual(pc.check_project(self.project), [])
        (self.project / "intake.md").write_bytes(b"# Founder input\n\n\xff\n")
        self.assertEqual(pc.check_project(self.project), ["intake.md: isn't UTF-8 text"])

    def test_charter_open_markers_name_existing_questions(self):
        self.edit("CHARTER.md", lambda s: s + "\n## Budget\n\nOpen: Q-0001, Q-0099 and Q-0098\n")
        problems = pc.check_project(self.project)
        self.assertIn("CHARTER.md: an Open: marker names Q-0099, which doesn't exist", problems)
        self.assertIn("CHARTER.md: an Open: marker names Q-0098, which doesn't exist", problems)
        self.assertFalse(any("Q-0001" in p for p in problems), problems)

    def test_charter_markers_and_placeholders(self):
        text = "Open: Q-0002, Q-0003\nMoney: Open: Q-0002\nSee Q-0007 later\nOpen: Q-xxxx\n"
        self.assertEqual(pc.charter_open_questions(text), ["Q-0002", "Q-0003"])
        self.assertEqual(pc.check_charter_text(text, None), [])


class LoaderTest(unittest.TestCase):
    def test_dates_stay_text(self):
        data = pc.load_yaml_text("a: 2026-11-16\nb: 2026-11-16T10:00:00+01:00\n")
        self.assertEqual(data, {"a": "2026-11-16", "b": "2026-11-16T10:00:00+01:00"})

    def test_null_and_flow_style(self):
        self.assertEqual(pc.load_yaml_text("a: null\nb: [x, y]\nc: { k: A }\n"), {"a": None, "b": ["x", "y"], "c": {"k": "A"}})

    def test_python_tags_are_refused(self):
        with self.assertRaises(pc.LoadError):
            pc.load_yaml_text("a: !!python/object/apply:os.system ['true']\n")

    def test_too_large(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
            handle.write("x" * (pc.MAX_BYTES + 1))
        try:
            with self.assertRaises(pc.LoadError):
                pc.load_yaml(handle.name)
        finally:
            Path(handle.name).unlink()


class RegistryTest(unittest.TestCase):
    def test_names_and_entries(self):
        good = json.loads((GOOD / "projects.json").read_text())
        bad = copy.deepcopy(good)
        bad["Tree Robot"] = bad.pop("minimal")
        bad["tree-watering-robot"]["branch"] = "main"
        problems = pc.check_registry(bad)
        self.assertIn("registry: project name 'Tree Robot' has the wrong form", problems)
        self.assertIn("registry.tree-watering-robot.branch: has the wrong form", problems)
        self.assertIsNone(good["new-idea"]["repo"])  # a local-only project, accepted above
        self.assertEqual(pc.check_registry([]), ["registry: must be an object of projects"])


class FounderFieldsTest(unittest.TestCase):
    def test_lists_every_answer_and_result(self):
        questions = pc.load_yaml(GOOD / "project" / "questions.yaml")
        tasks = pc.load_yaml(GOOD / "project" / "adam-tasks.yaml")
        fields = pc.founder_fields(questions, tasks)
        self.assertEqual(sorted(fields), ["A-0001", "A-0002", "Q-0001", "Q-0003", "Q-0004"])
        self.assertIsNone(fields["Q-0001"])
        self.assertEqual(fields["Q-0003"]["key"], "B")
        self.assertEqual(fields["A-0001"]["files"], ["field-data/A-0001-1.jpg"])


if __name__ == "__main__":
    unittest.main()
