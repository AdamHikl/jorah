"""The project folder's state files, their schemas, and the fields only the runner may write.

PM-T2 (forged answers) and PM-T3 (charter drift), plan 11 section 9:
- `CHARTER.md` is Adam's. A run's change to it is reverted, except in a setup run, which drafts
  it from the template (plan 11 section 5.1).
- `intake.md` is Adam's own words, copied by the runner from the inbox. A run's change to it is
  reverted, setup runs included.
- `answer` in questions.yaml and `result` in adam-tasks.yaml are written only by the runner, from
  the inbox (Adam's words through the plugin). So are the statuses that mean "has an answer"
  (`answered`, `defaulted`) and "has a result" (`done`).
- A state file that doesn't parse or doesn't validate is put back as it was.

"As it was" is a trusted snapshot: the files at the last commit the runner made or checked itself.
Changes may come into protected fields only from the runner's intake, or from Adam's own default
branch on GitHub through the merge (Adam editing the charter or answering on GitHub is his word).
"""

import copy

from . import contract, fsio

FILES = {"backlog": "backlog.yaml", "questions": "questions.yaml", "adam-tasks": "adam-tasks.yaml"}
LISTS = {"backlog": "items", "questions": "questions", "adam-tasks": "tasks"}
CHARTER = "CHARTER.md"
INTAKE = "intake.md"

ANSWER_STATUSES = {"answered", "defaulted"}
RESULT_STATUSES = {"done"}


def rel(project, name):
    return f"{project.state_dir}/{name}"


class Snapshot:
    """Bytes of the charter and the three state files, from a commit or from the work tree."""

    def __init__(self, pc, charter, files, intake=None):
        self.pc = pc  # the contract's checker (contract.load)
        self.charter = charter
        self.files = files  # kind -> bytes or None
        self.intake = intake

    @classmethod
    def from_commit(cls, pc, repo, project, rev):
        files = {kind: repo.show(rev, rel(project, name)) for kind, name in FILES.items()} if rev else dict.fromkeys(FILES)
        charter = repo.show(rev, rel(project, CHARTER)) if rev else None
        intake = repo.show(rev, rel(project, INTAKE)) if rev else None
        return cls(pc, charter, files, intake)

    @classmethod
    def from_tree(cls, pc, project):
        root = project.work_dir
        files = {}
        for kind, name in FILES.items():
            try:
                files[kind] = fsio.read_bytes(root, rel(project, name))
            except fsio.Unsafe:
                files[kind] = b"\0unsafe"
        def whole(name):
            try:
                return fsio.read_bytes(root, rel(project, name))
            except fsio.Unsafe:
                return b"\0unsafe"

        return cls(pc, whole(CHARTER), files, whole(INTAKE))

    def parsed(self, kind):
        """Parsed document or None. Raises ValueError if present but unreadable."""
        data = self.files.get(kind)
        if data is None:
            return None
        if data == b"\0unsafe":
            raise ValueError("is a link or not a regular file")
        if len(data) > fsio.MAX_STATE_BYTES:
            raise ValueError("is over 2 MB")
        doc = contract.parse(self.pc, data)
        if not fsio.json_safe(doc):
            raise ValueError("holds values JSON can't carry")
        return doc


def items(doc, kind):
    if not isinstance(doc, dict):
        return []
    out = doc.get(LISTS[kind])
    return [x for x in out if isinstance(x, dict)] if isinstance(out, list) else []


def by_id(doc, kind):
    return {x["id"]: x for x in items(doc, kind) if isinstance(x.get("id"), str)}


def validate(snapshot, field_data_dir=None):
    """{kind: [problems]} for each state file present that fails to parse, its schema, or the
    contract's cross-file rules."""
    docs = {}
    for kind in FILES:
        try:
            docs[kind] = snapshot.parsed(kind)
        except ValueError as error:
            docs[kind] = error
    return contract.state_problems(snapshot.pc, docs, field_data_dir)


def _protected(kind):
    return ("answer", ANSWER_STATUSES) if kind == "questions" else ("result", RESULT_STATUSES)


def _expected_item(kind, item_id, trusted, theirs, base):
    """The trusted version of one item, or Adam's from his branch when he changed it there."""
    if theirs is not None and base is not None:
        mine_t, mine_b = theirs.get(item_id), base.get(item_id)
        field, _ = _protected(kind)
        if mine_t is not None and (mine_b is None or mine_t.get(field) != mine_b.get(field) or mine_t.get("status") != mine_b.get("status")):
            return mine_t
    return trusted.get(item_id)


def _whole_file(project, name, current, trusted, theirs, base, why):
    """Put one whole file back to `trusted`, or to Adam's branch where he changed it. [] or [{...}]."""
    want = getattr(trusted, name)
    if theirs is not None and base is not None and getattr(theirs, name) != getattr(base, name):
        want = getattr(theirs, name)
    if getattr(current, name) == want:
        return []
    path = rel(project, CHARTER if name == "charter" else INTAKE)
    if want is None:
        fsio.remove(project.work_dir, path)
    else:
        fsio.write_bytes(project.work_dir, path, want)
    return [{"what": path.rsplit("/", 1)[-1], "id": path, "why": why}]


def enforce(project, current, trusted, *, theirs=None, base=None, setup=False):
    """Put protected content back to `trusted` (or Adam's branch where he changed it).

    Writes the work tree. Returns a list of {what, id, why}. `theirs` and `base` are Snapshots of
    the default branch and the merge base, used only when a merge brought Adam's changes in.
    `setup`: a setup run, which may write the charter (the founder's input stays protected).
    """
    reverted = []
    root = project.work_dir

    if not setup:
        reverted += _whole_file(project, "charter", current, trusted, theirs, base,
                                "the charter is Adam's; changes come only as founder questions")
    reverted += _whole_file(project, "intake", current, trusted, theirs, base,
                            "intake.md is Adam's own words; only the runner copies it from the inbox")

    for kind in ("questions", "adam-tasks"):
        field, statuses = _protected(kind)
        try:
            doc = current.parsed(kind)
        except ValueError:
            continue  # handled by restore_invalid
        if doc is None:
            continue
        try:
            t_doc = trusted.parsed(kind)
        except ValueError:
            t_doc = None
        t_items = by_id(t_doc, kind)
        th_items = base_items = None
        if theirs is not None and base is not None:
            try:
                th_items = by_id(theirs.parsed(kind), kind)
                base_items = by_id(base.parsed(kind), kind)
            except ValueError:
                th_items = base_items = None
        changed = False
        seen = set()
        for item in items(doc, kind):
            item_id = item.get("id")
            if not isinstance(item_id, str):
                continue
            seen.add(item_id)
            expect = _expected_item(kind, item_id, t_items, th_items, base_items)
            want_field = copy.deepcopy(expect.get(field)) if expect else None
            if item.get(field) != want_field:
                item[field] = want_field
                changed = True
                reverted.append({"what": field, "id": item_id, "why": f"only the runner writes {field}, from Adam's words"})
            now, was = item.get("status"), (expect or {}).get("status")
            if (now in statuses or was in statuses) and now != was:
                item["status"] = was if expect else "open"
                changed = True
                reverted.append({"what": "status", "id": item_id, "why": f"status {now} needs Adam's {field}"})
        # An item that carried Adam's answer or result can't be deleted.
        lst = doc.get(LISTS[kind]) if isinstance(doc, dict) else None
        if isinstance(lst, list):
            for item_id, item in t_items.items():
                if item_id not in seen and item.get(field) is not None:
                    lst.append(copy.deepcopy(item))
                    changed = True
                    reverted.append({"what": "deleted", "id": item_id, "why": f"it holds Adam's {field}"})
        if changed:
            fsio.write_bytes(root, rel(project, FILES[kind]), fsio.dump_yaml(doc))
    return reverted


def restore_invalid(project, trusted):
    """Put back any state file that doesn't pass the contract, until all pass (a file put back can
    make another fail, e.g. a backlog item blocked on a question that was put back). Returns
    [{what, id, why}]."""
    reverted = []
    field_data = project.work_dir / project.state_dir / "field-data"
    for _ in range(len(FILES) + 1):
        current = Snapshot.from_tree(trusted.pc, project)
        problems = validate(current, field_data)
        bad = [kind for kind in problems if current.files.get(kind) != trusted.files.get(kind)]
        if not bad:
            break
        for kind in bad:
            path = rel(project, FILES[kind])
            old = trusted.files.get(kind)
            if old is None:
                fsio.remove(project.work_dir, path)
            else:
                fsio.write_bytes(project.work_dir, path, old)
            reverted.append({"what": "file", "id": path, "why": f"didn't pass the contract ({problems[kind][0][:160]})"})
    return reverted


# ---- what changed, for the run record -----------------------------------------------------------

def changes(before, after):
    """Backlog, question and task changes between two Snapshots, ids and statuses only."""
    def safe(snap, kind):
        try:
            return by_id(snap.parsed(kind), kind)
        except ValueError:
            return {}

    b0, b1 = safe(before, "backlog"), safe(after, "backlog")
    q0, q1 = safe(before, "questions"), safe(after, "questions")
    a0, a1 = safe(before, "adam-tasks"), safe(after, "adam-tasks")
    return {
        "backlog": {
            "added": sorted(set(b1) - set(b0)),
            "changed": [{"id": i, "from": _s(b0[i].get("status")), "to": _s(b1[i].get("status"))}
                        for i in sorted(set(b0) & set(b1)) if b0[i].get("status") != b1[i].get("status")],
        },
        "questions": {"new": sorted(set(q1) - set(q0))},
        "adamTasks": {"new": sorted(set(a1) - set(a0))},
    }


def _s(value):
    return value if isinstance(value, str) else None
