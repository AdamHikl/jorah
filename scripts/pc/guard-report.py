#!/usr/bin/env python3
"""Summarise jorah-guard's decision log for the review after a week of real use (P5.5/P5.6).

Runs as jorah on the PC and prints to the terminal only. It shows counts and the guard's own
reasons (URLs in them are already <url>); never arguments, addresses or message text. What to look
for: unknown tools (the permission list needs them), cards Adam didn't expect, guard errors, and
whether Adam's Telegram turns count as "adam-typed" (they need a sender id).

  python3 guard-report.py [--log ~/.jorah-guard/decisions.jsonl] [--days 7]
"""

import argparse, collections, datetime as dt, hashlib, json, sys
from pathlib import Path


def chain_ok(rows_raw):
    prev = "genesis"
    for i, line in enumerate(rows_raw, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return i
        h = row.pop("hash", None)
        body = json.dumps(row, separators=(",", ":"), ensure_ascii=False)
        if row.get("prev") != prev or hashlib.sha256(body.encode()).hexdigest() != h:
            return i
        prev = h
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(Path.home() / ".jorah-guard/decisions.jsonl"))
    ap.add_argument("--days", type=float, default=7)
    a = ap.parse_args()
    path = Path(a.log)
    if not path.exists():
        print(f"No log at {path}: unknown, not zero.")
        return 1
    raw = [l for l in path.read_text().splitlines() if l.strip()]
    broken = chain_ok(raw)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)
    rows = []
    for l in raw:
        try:
            r = json.loads(l)
            if dt.datetime.fromisoformat(r["t"].replace("Z", "+00:00")) >= since:
                rows.append(r)
        except (ValueError, KeyError):
            continue

    print(f"jorah-guard log: {path}, last {a.days:g} days, {len(rows)} decisions of {len(raw)} in all")
    print(f"Hash chain: {'intact' if broken == 0 else f'BROKEN at line {broken}'}")
    if not rows:
        return 0
    print(f"From {rows[0]['t'][:16]} to {rows[-1]['t'][:16]} UTC\n")

    verdicts = collections.Counter(r.get("verdict") for r in rows)
    print("Verdicts:", ", ".join(f"{k} {v}" for k, v in verdicts.most_common()))

    days = collections.Counter(r["t"][:10] for r in rows)
    print("Per day:", ", ".join(f"{d} {n}" for d, n in sorted(days.items())))

    who = collections.Counter((r.get("from") or "?", r.get("channel") or "-") for r in rows if r.get("tool") not in ("before_reset", "message_sending"))
    print("\nWho asked (class, channel):")
    for (f, c), n in who.most_common():
        print(f"  {n:5}  {f:11} {c}")
    tele = sum(n for (f, c), n in who.items() if c == "telegram")
    tele_typed = sum(n for (f, c), n in who.items() if c == "telegram" and f == "adam-typed")
    if tele:
        print(f"  Telegram counted as Adam typing: {tele_typed} of {tele}" + ("" if tele_typed == tele else "  <- check: sender id missing?"))

    def group(pred):
        c = collections.Counter((r.get("tool"), (r.get("reason") or "")[:110]) for r in rows if pred(r))
        return c.most_common(40)

    sections = [
        ("Blocked: tool not in the permission list (add it, or keep it blocked)", lambda r: r.get("verdict") == "block" and "permission list" in (r.get("reason") or "")),
        ("Guard errors (fail closed)", lambda r: (r.get("reason") or "").startswith("guard error")),
        ("Other blocks", lambda r: r.get("verdict") == "block" and "permission list" not in (r.get("reason") or "") and not (r.get("reason") or "").startswith("guard error")),
        ("Cards shown to Adam", lambda r: r.get("verdict") == "confirm"),
        ("Allowed because Adam's own words covered it", lambda r: r.get("reason") == "Adam's own words"),
        ("Links removed from Telegram replies", lambda r: r.get("verdict") == "rewrite"),
        ("Freezes", lambda r: r.get("verdict") == "freeze"),
    ]
    for title, pred in sections:
        items = group(pred)
        print(f"\n{title}: {sum(n for _, n in items)}")
        for (tool, reason), n in items:
            print(f"  {n:5}  {tool}: {reason}")

    resets = sum(1 for r in rows if r.get("tool") == "before_reset")
    sessions = len({r.get("session") for r in rows if r.get("session")})
    print(f"\nResets seen: {resets}; chats and jobs seen: {sessions}")

    state = path.parent / "taint.json"
    try:
        data = json.loads(state.read_text())
        srcs = collections.Counter((v.get("source") or "?").split(" ")[0] for v in data.get("sessions", {}).values() if v.get("tainted"))
        print("Chats marked as having read outside text, by first source tool:", ", ".join(f"{k} {v}" for k, v in srcs.most_common()) or "none")
    except (OSError, json.JSONDecodeError):
        print("taint.json unreadable: unknown")
    print(f"Frozen now: {'YES' if (path.parent / 'FROZEN').exists() else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
