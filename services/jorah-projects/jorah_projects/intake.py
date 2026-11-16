"""Take in Adam's words (plan 11, section 4.1 step 4). The only writer of `answer` and `result`.

The plugin `jorah-projects` appends answers to `inbox/answers.jsonl` and drops results in
`inbox/results/`. Formats: the WS2 hand-over note, repeated in services/jorah-projects/README.md.
Each answer and result is applied once (ids kept in `inbox/applied.json`); the inbox is never
truncated, so the plugin can append while a run reads.

Defaults: an open question whose `decide_by` has passed gets its `default_if_silent`, but only if
the runner first saw that question, with that same default and deadline, at least
`default_hold_hours` earlier. A run can't add a question with a default and yesterday's deadline
and have it applied at once: it has to sit in the digest first.
"""

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from . import contract, fsio
from .protect import FILES, LISTS, items, rel

QUESTION_ID = re.compile(r"^Q-\d{4}$")
TASK_ID = re.compile(r"^A-\d{4}$")
FILE_EXT = {"jpg", "jpeg", "png", "heic", "webp", "gif", "pdf", "txt", "csv", "json", "md", "mp4", "mov", "m4a", "wav", "ogg"}
MAX_FILE = 25 * 1024 * 1024
MAX_TEXT = 4000
MAX_NOTE = 2000


def _uuid_ok(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _text(value, limit):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("not text")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"longer than {limit} characters")
    return value or None


VIA = {"telegram", "voice", "phone", "chat"}  # the contract's answer.via, apart from "default"


def _via(value):
    return value if value in VIA else "chat"


def _at(pc, value, now):
    """The plugin's time if the contract accepts it as a date-time, otherwise the runner's."""
    ok = isinstance(value, str) and len(value) <= 40 and pc.parse_date_time(value) is not None
    return value if ok else now.isoformat(timespec="seconds")


class Inbox:
    def __init__(self, state_dir):
        self.dir = Path(state_dir) / "inbox"
        self.applied_file = self.dir / "applied.json"
        self.applied = fsio.read_private_json(self.applied_file, {"v": 1, "answers": [], "results": []})

    def save(self):
        fsio.write_private_json(self.applied_file, self.applied)

    def answers(self):
        """[(id, dict)] not yet applied, plus [(where, why)] for lines that can't be read."""
        path = self.dir / "answers.jsonl"
        out, bad = [], []
        try:
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().split("\n")
        except FileNotFoundError:
            return out, bad
        done = set(self.applied.get("answers", []))
        # The last element is "" for a file ending in a newline, or a line still being written.
        for n, line in enumerate(lines[:-1], 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                bad.append((f"answers.jsonl line {n}", "isn't JSON"))
                continue
            if not isinstance(entry, dict) or entry.get("v") != 1 or not _uuid_ok(entry.get("id")):
                bad.append((f"answers.jsonl line {n}", "has no v 1 or no uuid id"))
                continue
            if entry["id"] in done:
                continue
            out.append((entry["id"], entry))
        return out, bad

    def results(self):
        folder = self.dir / "results"
        out, bad = [], []
        if not folder.is_dir():
            return out, bad
        for path in sorted(folder.glob("*.json")):
            if path.is_symlink():
                bad.append((path.name, "is a link"))
                continue
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                bad.append((path.name, "isn't JSON"))
                continue
            if not isinstance(entry, dict) or entry.get("v") != 1 or not _uuid_ok(entry.get("id")):
                bad.append((path.name, "has no v 1 or no uuid id"))
                continue
            out.append((path, entry))
        return out, bad

    def mark_result(self, path, entry_id):
        self.applied.setdefault("results", []).append(entry_id)
        done = path.parent / "applied"
        done.mkdir(exist_ok=True, mode=0o700)
        os.replace(path, done / path.name)


def _load(pc, project, kind):
    """The parsed file, or None if it's missing or unreadable (then nothing for it is consumed)."""
    try:
        data = fsio.read_bytes(project.work_dir, rel(project, FILES[kind]))
        doc = contract.parse(pc, data) if data is not None else None
    except (ValueError, fsio.Unsafe):
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get(LISTS[kind]), list) else None


def apply(pc, project, state_dir, now, seen_questions, *, hold_hours=48):
    """Apply the inbox and due defaults to the work tree. Returns the record's `intake` part.

    `seen_questions` is the runner's memory {qid: {at, default, decideBy}} (updated in place).
    Doesn't commit; the caller does, as "Founder input from Telegram".
    """
    inbox = Inbox(state_dir)
    report = {"answers": [], "results": [], "defaults": [], "refused": []}
    questions = _load(pc, project, "questions")
    tasks = _load(pc, project, "adam-tasks")
    q_by_id = {x["id"]: x for x in items(questions, "questions") if isinstance(x.get("id"), str)}
    t_by_id = {x["id"]: x for x in items(tasks, "adam-tasks") if isinstance(x.get("id"), str)}
    q_changed = t_changed = False

    answers, bad = inbox.answers()
    if questions is None and answers:
        report["refused"].append({"id": "answers", "why": "questions.yaml is missing or unreadable; answers kept for the next run"})
        answers = []
    for where, why in bad:
        report["refused"].append({"id": where, "why": why})
    for entry_id, entry in answers:
        qid = entry.get("question")
        why = None
        question = q_by_id.get(qid) if isinstance(qid, str) and QUESTION_ID.match(qid) else None
        try:
            note = _text(entry.get("note"), MAX_NOTE)
        except ValueError as error:
            note, why = None, f"note {error}"
        key = entry.get("key")
        if why:
            pass
        elif question is None:
            why = "no such question"
        elif question.get("status") == "withdrawn":
            why = "the question was withdrawn"
        elif key is not None and (not isinstance(key, str) or key not in [o.get("key") for o in question.get("options") or [] if isinstance(o, dict)]):
            why = "the key isn't one of the question's options"
        elif key is None and note is None:
            why = "neither a key nor a note"
        if why:
            report["refused"].append({"id": entry_id, "question": qid if isinstance(qid, str) else None, "why": why})
        else:
            question["answer"] = {"key": key, "note": note, "by": "adam", "via": _via(entry.get("via")), "at": _at(pc, entry.get("at"), now)}
            question["status"] = "answered"
            q_changed = True
            report["answers"].append(qid)
        inbox.applied.setdefault("answers", []).append(entry_id)

    results, bad = inbox.results()
    if tasks is None and results:
        report["refused"].append({"id": "results", "why": "adam-tasks.yaml is missing or unreadable; results kept for the next run"})
        results = []
    for where, why in bad:
        report["refused"].append({"id": where, "why": why})
    for path, entry in results:
        tid = entry.get("task")
        task = t_by_id.get(tid) if isinstance(tid, str) and TASK_ID.match(tid) else None
        why = None
        try:
            text = _text(entry.get("text"), MAX_TEXT)
        except ValueError as error:
            text, why = None, f"text {error}"
        names = entry.get("files") or []
        if why:
            pass
        elif task is None:
            why = "no such task"
        elif not isinstance(names, list) or len(names) > 20:
            why = "files must be a list of at most 20 names"
        elif text is None and not names:
            why = "neither text nor files"
        stored = []
        if not why:
            try:
                stored = _store_files(project, inbox.dir / "results" / "files", tid, names, task)
            except fsio.Unsafe:
                raise  # the run stops; Adam's result stays in the inbox
            except ValueError as error:
                why = str(error)
        if why:
            report["refused"].append({"id": entry["id"], "task": tid if isinstance(tid, str) else None, "why": why})
        else:
            task["result"] = {"text": text, "files": stored, "at": _at(pc, entry.get("at"), now)}
            task["status"] = "done"
            t_changed = True
            report["results"].append(tid)
        inbox.mark_result(path, entry["id"])

    # Defaults, only after the hold (see the module text).
    today = now.date().isoformat()
    for qid, question in q_by_id.items():
        if question.get("status") != "open":
            seen_questions.pop(qid, None)
            continue
        default, decide_by = question.get("default_if_silent"), question.get("decide_by")
        mark = {"default": default, "decideBy": decide_by}
        seen = seen_questions.get(qid)
        if not seen or {"default": seen.get("default"), "decideBy": seen.get("decideBy")} != mark:
            seen_questions[qid] = {"at": now.isoformat(timespec="seconds"), **mark}
            continue
        if default is None or not isinstance(decide_by, str) or decide_by >= today:
            continue
        if now - datetime.fromisoformat(seen["at"]) < timedelta(hours=hold_hours):
            continue
        if default not in [o.get("key") for o in question.get("options") or [] if isinstance(o, dict)]:
            report["refused"].append({"id": qid, "why": "its default isn't one of its options"})
            continue
        question["answer"] = {"key": default, "note": None, "by": "default", "via": "default", "at": now.isoformat(timespec="seconds")}
        question["status"] = "defaulted"
        q_changed = True
        report["defaults"].append(qid)
        seen_questions.pop(qid, None)

    if q_changed:
        fsio.write_bytes(project.work_dir, rel(project, FILES["questions"]), fsio.dump_yaml(questions))
    if t_changed:
        fsio.write_bytes(project.work_dir, rel(project, FILES["adam-tasks"]), fsio.dump_yaml(tasks))
    inbox.save()
    return report


def _store_files(project, folder, tid, names, task):
    existing = (task.get("result") or {}).get("files") or []
    n = len(existing)
    plans = []
    for name in names:
        if not isinstance(name, str) or "/" in name or name.startswith(".") or len(name) > 120:
            raise ValueError("a file name isn't a plain name")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in FILE_EXT:
            raise ValueError(f"file type .{ext[:10]} isn't allowed")
        src = folder / name
        if src.is_symlink() or not src.is_file():
            raise ValueError("an attached file is missing")
        if src.stat().st_size > MAX_FILE:
            raise ValueError("an attached file is over 25 MB")
        n += 1
        plans.append((src, f"field-data/{tid}-{n}.{ext}"))
    stored = []
    for src, dest in plans:
        fsio.write_bytes(project.work_dir, rel(project, dest), src.read_bytes())
        stored.append(dest)
        done = folder / "applied"
        done.mkdir(exist_ok=True, mode=0o700)
        shutil.move(str(src), done / src.name)
    return stored
