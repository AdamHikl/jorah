#!/usr/bin/env python3
"""Check a project folder (contract jorah-project-v1) against its schemas and cross-file rules.

The schemas next to this file are the source of truth. This checker understands only the JSON
Schema keywords in KNOWN and refuses a schema that uses any other, so a schema can't quietly ask for
a check this code doesn't make. Objects never accept unknown fields.

YAML is read with PyYAML's safe loader, narrowed further: dates stay strings (so a date is checked
as text, the same in YAML and JSON), duplicate keys and anchors/aliases are refused, and a state
file over 2 MB is refused.

Messages name the file, the place and the rule, never the value, so they can go into run records.

    python3 packages/contracts/project/projectcheck.py <project dir> [...]
    python3 packages/contracts/project/projectcheck.py --registry <projects.json>

Exit 0 when everything passes, 1 when there are problems (printed one per line), 2 on bad usage.
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MAX_BYTES = 2 * 1024 * 1024

KNOWN = {
    "$schema", "$id", "title", "description", "type", "properties", "required", "additionalProperties",
    "enum", "const", "minLength", "maxLength", "pattern", "minItems", "maxItems", "items", "minimum",
    "maximum", "format", "uniqueItems",
}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
FORMATS = {"date", "date-time"}

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})$")
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
LOG_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

STATE_FILES = {"backlog.yaml": "backlog", "questions.yaml": "questions", "adam-tasks.yaml": "adam-tasks"}
REQUIRED_FILES = ("CHARTER.md", "DECISIONS.md", "backlog.yaml", "questions.yaml", "adam-tasks.yaml")


class SchemaError(ValueError):
    """The schema itself is broken or uses something this checker doesn't do."""


class LoadError(ValueError):
    """A state file can't be read as the narrowed YAML this contract uses."""


# ---------------------------------------------------------------- YAML

class _Loader(yaml.SafeLoader):
    """SafeLoader without timestamps, duplicate keys or aliases."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()
            raise LoadError(f"line {event.start_mark.line + 1}: anchors and aliases aren't allowed")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise LoadError(f"line {key_node.start_mark.line + 1}: duplicate key {str(key)[:40]!r}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


_Loader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_constructor("tag:yaml.org,2002:timestamp", yaml.SafeLoader.construct_yaml_str)


def load_yaml_text(text):
    try:
        return yaml.load(text, Loader=_Loader)  # noqa: S506 - _Loader is a narrowed SafeLoader
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f"line {mark.line + 1}: " if mark is not None else ""
        raise LoadError(f"{where}not valid YAML") from None


def load_yaml(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise LoadError("file is over 2 MB")
    return load_yaml_text(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- schemas

def check_schema(schema, path="$"):
    if not isinstance(schema, dict):
        raise SchemaError(f"{path}: a schema must be an object")
    unknown = set(schema) - KNOWN
    if unknown:
        raise SchemaError(f"{path}: unsupported keyword(s): {', '.join(sorted(unknown))}")
    types = schema.get("type")
    if types is not None:
        for kind in types if isinstance(types, list) else [types]:
            if kind not in TYPES:
                raise SchemaError(f"{path}: unknown type {kind!r}")
    if "additionalProperties" in schema and schema["additionalProperties"] is not False:
        raise SchemaError(f"{path}: only additionalProperties: false is supported")
    if "properties" in schema and schema.get("additionalProperties") is not False:
        raise SchemaError(f"{path}: an object schema must say additionalProperties: false")
    if "format" in schema and schema["format"] not in FORMATS:
        raise SchemaError(f"{path}: unsupported format {schema['format']!r}")
    if "pattern" in schema:
        re.compile(schema["pattern"])
    for name, sub in (schema.get("properties") or {}).items():
        check_schema(sub, f"{path}.{name}")
    for name in schema.get("required") or []:
        if name not in (schema.get("properties") or {}):
            raise SchemaError(f"{path}: required field {name!r} has no schema")
    if "items" in schema:
        check_schema(schema["items"], f"{path}[]")
    return schema


def load_schema(name, directory=HERE):
    """Load and check <directory>/<name>.schema.json."""
    with open(Path(directory) / f"{name}.schema.json", encoding="utf-8") as handle:
        return check_schema(json.load(handle))


def _type_of(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _same(a, b):
    return _type_of(a) == _type_of(b) and a == b


def _type_ok(value, wanted):
    actual = _type_of(value)
    for kind in wanted if isinstance(wanted, list) else [wanted]:
        if kind == actual or (kind == "number" and actual == "integer"):
            return True
    return False


def parse_date(text):
    if not isinstance(text, str) or not DATE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_date_time(text):
    if not isinstance(text, str) or not DATE_TIME.match(text):
        return None
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None


def validate(schema, value, path="$"):
    """Return a list of problems, empty when the value matches."""
    problems = []
    if "const" in schema and not _same(value, schema["const"]):
        return [f"{path}: has the wrong value"]
    if "enum" in schema and not any(_same(value, option) for option in schema["enum"]):
        return [f"{path}: isn't one of the allowed values"]
    if "type" in schema and not _type_ok(value, schema["type"]):
        wanted = schema["type"] if isinstance(schema["type"], str) else " or ".join(schema["type"])
        return [f"{path}: must be {wanted}"]
    kind = _type_of(value)
    if kind in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: is above {schema['maximum']}")
    elif kind == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            problems.append(f"{path}: is shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{path}: is longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{path}: has the wrong form")
        if schema.get("format") == "date" and parse_date(value) is None:
            problems.append(f"{path}: must be a date, YYYY-MM-DD")
        if schema.get("format") == "date-time" and parse_date_time(value) is None:
            problems.append(f"{path}: must be an ISO 8601 date and time with an offset")
    elif kind == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            problems.append(f"{path}: has fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            problems.append(f"{path}: has more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = []
            for item in value:
                if any(_same(item, other) for other in seen):
                    problems.append(f"{path}: has repeated items")
                    break
                seen.append(item)
        if "items" in schema:
            for index, item in enumerate(value):
                problems += validate(schema["items"], item, f"{path}[{index}]")
    elif kind == "object":
        properties = schema.get("properties") or {}
        for name in value:
            if name not in properties:
                problems.append(f"{path}: has an unknown field {str(name)[:40]!r}")
        for name in schema.get("required") or []:
            if name not in value:
                problems.append(f"{path}: is missing {name!r}")
        for name, sub in properties.items():
            if name in value:
                problems += validate(sub, value[name], f"{path}.{name}")
    return problems


# ---------------------------------------------------------------- cross-file rules

def _ids(entries):
    return [entry.get("id") for entry in entries if isinstance(entry, dict)]


def _duplicates(entries, where):
    seen, problems = set(), []
    for index, entry_id in enumerate(_ids(entries)):
        if entry_id in seen:
            problems.append(f"{where}[{index}]: id {entry_id} is used twice")
        seen.add(entry_id)
    return problems


def check_backlog(data, question_ids=None, task_ids=None):
    """Rules a schema can't say. question_ids/task_ids are sets, or None when that file isn't known."""
    items = data["items"]
    problems = _duplicates(items, "items")
    known = set(_ids(items))
    for index, item in enumerate(items):
        where = f"items[{index}] {item['id']}"
        deps = item.get("depends_on") or []
        for dep in deps:
            if dep == item["id"]:
                problems.append(f"{where}: depends on itself")
            elif dep not in known:
                problems.append(f"{where}: depends on {dep}, which isn't in the backlog")
        blocked_on = item.get("blocked_on")
        if blocked_on:
            pool = question_ids if blocked_on.startswith("Q-") else task_ids
            if pool is not None and blocked_on not in pool:
                problems.append(f"{where}: blocked on {blocked_on}, which doesn't exist")
        if item["status"] == "blocked" and not blocked_on and not deps:
            problems.append(f"{where}: is blocked but names no blocked_on and no depends_on")
        if item["status"] == "done" and not item.get("evidence"):
            problems.append(f"{where}: is done without evidence")
        if item["status"] == "dropped" and not (item.get("note") or "").strip():
            problems.append(f"{where}: is dropped without a reason in note")
        if item["track"] == "adam":
            if "adam_task" not in item:
                problems.append(f"{where}: track adam needs adam_task")
            elif task_ids is not None and item["adam_task"] not in task_ids:
                problems.append(f"{where}: mirrors {item['adam_task']}, which doesn't exist")
        elif "adam_task" in item:
            problems.append(f"{where}: adam_task is only for track adam")
        if parse_date(item["updated"]) < parse_date(item["created"]):
            problems.append(f"{where}: updated is before created")
    problems += _cycles(items)
    return problems


def _cycles(items):
    graph = {item["id"]: [d for d in item.get("depends_on") or [] if d != item["id"]] for item in items}
    state, problems = {}, []

    def visit(node, trail):
        state[node] = "open"
        for dep in graph.get(node, []):
            if dep not in graph:
                continue
            if state.get(dep) == "open":
                problems.append(f"items: dependency cycle {' -> '.join(trail[trail.index(dep):] + [dep])}")
            elif dep not in state:
                visit(dep, trail + [dep])
        state[node] = "closed"

    for node in graph:
        if node not in state:
            visit(node, [node])
    return problems


def check_questions(data):
    questions = data["questions"]
    problems = _duplicates(questions, "questions")
    for index, question in enumerate(questions):
        where = f"questions[{index}] {question['id']}"
        keys = [option["key"] for option in question["options"]]
        if len(set(keys)) != len(keys):
            problems.append(f"{where}: option keys repeat")
        for field in ("recommendation", "default_if_silent"):
            if question[field] is not None and question[field] not in keys:
                problems.append(f"{where}: {field} isn't one of the option keys")
        if question["default_if_silent"] is not None and question["decide_by"] is None:
            problems.append(f"{where}: a default needs decide_by")
        if question["decide_by"] is not None and parse_date(question["decide_by"]) < parse_date(question["asked"]):
            problems.append(f"{where}: decide_by is before asked")
        status, answer = question["status"], question["answer"]
        if status in ("open", "withdrawn") and answer is not None:
            problems.append(f"{where}: an {status} question has no answer")
        if status in ("answered", "defaulted") and answer is None:
            problems.append(f"{where}: an {status} question needs answer")
        if answer is None:
            continue
        if answer["key"] is not None and answer["key"] not in keys:
            problems.append(f"{where}: answer.key isn't one of the option keys")
        if answer["key"] is None and not (answer["note"] or "").strip():
            problems.append(f"{where}: answer needs a key or a note")
        if (answer["by"] == "default") != (answer["via"] == "default"):
            problems.append(f"{where}: answer by default goes with via default, and only then")
        if status == "answered" and answer["by"] != "adam":
            problems.append(f"{where}: an answered question is answered by adam")
        if status == "defaulted" and (answer["by"] != "default" or answer["key"] != question["default_if_silent"]):
            problems.append(f"{where}: a defaulted question's answer is the default, by default")
    return problems


def check_adam_tasks(data, field_data_dir=None):
    tasks = data["tasks"]
    problems = _duplicates(tasks, "tasks")
    for index, task in enumerate(tasks):
        where = f"tasks[{index}] {task['id']}"
        status, result = task["status"], task["result"]
        if status == "open" and result is not None:
            problems.append(f"{where}: an open task has no result")
        if status == "done" and result is None:
            problems.append(f"{where}: a done task needs result")
        if result is None:
            continue
        if not (result["text"] or "").strip() and not result["files"]:
            problems.append(f"{where}: result needs text or files")
        for name in result["files"]:
            if not name.startswith(f"field-data/{task['id']}-"):
                problems.append(f"{where}: result file isn't named for this task")
            elif field_data_dir is not None and not (field_data_dir.parent / name).is_file():
                problems.append(f"{where}: result file {name} is missing")
    return problems


# ---------------------------------------------------------------- whole folder, registry

def check_file(kind, data):
    """Schema check of one state file's parsed content. kind: backlog, questions, adam-tasks."""
    return validate(load_schema(kind), data)


def check_project(project_dir):
    """Every problem in a project folder, as 'file: place: rule' strings. Empty means valid."""
    project_dir = Path(project_dir)
    problems = []
    if not project_dir.is_dir():
        return [f"{project_dir.name}: isn't a folder"]
    for name in REQUIRED_FILES:
        if not (project_dir / name).is_file():
            problems.append(f"{name}: is missing")
    parsed = {}
    for name, kind in STATE_FILES.items():
        path = project_dir / name
        if not path.is_file():
            continue
        try:
            data = load_yaml(path)
        except (LoadError, UnicodeDecodeError) as error:
            problems.append(f"{name}: {error}")
            continue
        schema_problems = check_file(kind, data)
        problems += [f"{name}: {problem}" for problem in schema_problems]
        if not schema_problems:
            parsed[kind] = data
    question_ids = set(_ids(parsed["questions"]["questions"])) if "questions" in parsed else None
    task_ids = set(_ids(parsed["adam-tasks"]["tasks"])) if "adam-tasks" in parsed else None
    if "backlog" in parsed:
        problems += [f"backlog.yaml: {p}" for p in check_backlog(parsed["backlog"], question_ids, task_ids)]
    if "questions" in parsed:
        problems += [f"questions.yaml: {p}" for p in check_questions(parsed["questions"])]
    if "adam-tasks" in parsed:
        problems += [f"adam-tasks.yaml: {p}" for p in check_adam_tasks(parsed["adam-tasks"], project_dir / "field-data")]
    log_dir = project_dir / "log"
    if log_dir.is_dir():
        for entry in sorted(log_dir.iterdir()):
            if entry.name != "README.md" and not (LOG_NAME.match(entry.name) and parse_date(entry.name[:-3])):
                problems.append(f"log/{entry.name[:60]}: log files are named YYYY-MM-DD.md")
    return problems


def check_registry(registry):
    """The runner's projects.json, parsed: {name: project-config}."""
    if not isinstance(registry, dict):
        return ["registry: must be an object of projects"]
    schema, problems = load_schema("project-config"), []
    for name, entry in registry.items():
        if not PROJECT_NAME.match(name):
            problems.append(f"registry: project name {name[:40]!r} has the wrong form")
            continue
        problems += [f"registry.{name}{p[1:]}" for p in validate(schema, entry)]
    return problems


def founder_fields(questions, tasks):
    """{id: answer or result} from parsed questions.yaml and adam-tasks.yaml: the fields only the runner writes."""
    fields = {q["id"]: q.get("answer") for q in questions.get("questions", []) if isinstance(q, dict)}
    fields.update({t["id"]: t.get("result") for t in tasks.get("tasks", []) if isinstance(t, dict)})
    return fields


def main(argv):
    if len(argv) == 2 and argv[0] == "--registry":
        try:
            problems = check_registry(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            problems = ["registry: can't be read as JSON"]
    elif argv and not argv[0].startswith("-"):
        problems = [f"{d}/{p}" for d in argv for p in check_project(d)]
    else:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: projectcheck.py <project dir> [...] | --registry <projects.json>", file=sys.stderr)
        return 2
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
