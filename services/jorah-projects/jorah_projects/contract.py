"""The project contract jorah-project-v1, from packages/contracts/project (WS1's projectcheck.py).

The checker and its schemas are the single source of truth; the runner imports the checker by path
from the reviewed copy in /opt/jorah and refuses to run any project if it's missing or broken (fail
closed). The runner reads every file itself, through fsio (no links, size cap), and hands the
checker text and parsed data only.
"""

import importlib.util
from pathlib import Path


class ContractError(RuntimeError):
    pass


KINDS = {"backlog": "backlog.yaml", "questions": "questions.yaml", "adam-tasks": "adam-tasks.yaml"}


def load(folder):
    """The projectcheck module from `folder`, with its four schemas loaded once to prove they work."""
    path = Path(folder) / "projectcheck.py"
    if not path.is_file():
        raise ContractError(f"the contract checker is missing ({path})")
    spec = importlib.util.spec_from_file_location("jorah_projectcheck", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        for name in ("backlog", "questions", "adam-tasks", "project-config"):
            module.load_schema(name)
    except (Exception, SystemExit) as error:  # noqa: BLE001 - any failure here means no runs
        raise ContractError(f"the contract can't be loaded: {type(error).__name__}: {str(error)[:200]}") from None
    return module


def parse(pc, data):
    """Parsed YAML through the contract's narrowed loader (no dates as objects, no aliases, no
    duplicate keys). Raises ValueError."""
    if data is None:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("isn't UTF-8") from None
    return pc.load_yaml_text(text)


def entry_problems(pc, name, entry):
    """Problems with one registry entry, from the contract's project-config schema."""
    if not pc.PROJECT_NAME.match(name):
        return [f"project name {name[:40]!r} has the wrong form"]
    return pc.validate(pc.load_schema("project-config"), entry)


def state_problems(pc, docs, field_data_dir=None):
    """{kind: [problems]} for parsed state documents {kind: doc or None or ValueError}.

    Schema first, then the cross-file rules for the files that passed (ids that must exist,
    evidence for done, answers that match statuses, result files that must exist).
    """
    problems = {}
    good = {}
    for kind, doc in docs.items():
        if isinstance(doc, Exception):
            problems[kind] = [str(doc) or "isn't valid YAML"]
        elif doc is not None:
            found = pc.check_file(kind, doc)
            if found:
                problems[kind] = found
            else:
                good[kind] = doc
    qids = {q.get("id") for q in good["questions"]["questions"]} if "questions" in good else None
    tids = {t.get("id") for t in good["adam-tasks"]["tasks"]} if "adam-tasks" in good else None
    if "backlog" in good:
        found = pc.check_backlog(good["backlog"], qids, tids)
        if found:
            problems["backlog"] = found
    if "questions" in good:
        found = pc.check_questions(good["questions"])
        if found:
            problems["questions"] = found
    if "adam-tasks" in good:
        found = pc.check_adam_tasks(good["adam-tasks"], field_data_dir)
        if found:
            problems["adam-tasks"] = found
    return problems
