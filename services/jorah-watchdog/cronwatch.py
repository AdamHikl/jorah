#!/usr/bin/env python3
"""Cron watch: does the live Gateway's cron scheduler still run jobs?

Why: on 2026-11-21 OpenClaw 2026.10.9's cron failed to start at every Gateway start from 02:13
("[cron] failed to start: Error: Cron receipt authority is unavailable"), after Windows Update had
restarted the PC. /readyz still said ready with nothing failing, so the watchdog stayed quiet. The
three hourly heartbeats and the 03:00 Memory Dreaming Promotion silently stopped until the Gateway
start at 07:43.

  check   (root, no network, read-only; jorah-cron-watch.service, which every jorah-watchdog.service
          run pulls in first) Reads two sources and writes the report for the watchdog:
          - the newest finished heartbeat in cron_run_receipts of the Gateway's SQLite state, opened
            read-only. Heartbeats run every hour, so they are the scheduler's pulse;
          - the Gateway's journal since its current start (its systemd invocation), for the lines
            in FAILURE_PATTERN.
          `--report -` prints the report instead of writing it.
  show    Print the report.

Status in the report:
  failing  the journal has such a line from this start, and no heartbeat finished after the newest
           one; or no heartbeat finished for 2.5 hours while the Gateway has been up longer than that.
  pending  too early to tell: the Gateway isn't running (the watchdog's Gateway check covers that),
           started less than 2 minutes ago, or has been up less than 2.5 hours while no heartbeat
           finished in the last 2.5 hours. The watchdog keeps what it had.
  unknown  a source couldn't be read. The watchdog counts that as down, never as fine.
  ok       a heartbeat finished in the last 2.5 hours, and no such journal line came after it.

It reads only times and statuses of receipts and the names of heartbeat jobs: no prompt, output or
error text from the state. From the journal it keeps only the matching lines, cut to 160 characters.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

REPORT = "/var/lib/jorah-cron-watch/report.json"
STATE_DB = "/home/jorah/.openclaw-jorah/state/openclaw.sqlite"
GATEWAY = "openclaw-gateway.service"
STALE_AFTER = 2.5 * 3600
SETTLE = 120
# The three lines OpenClaw 2026.10.9 logs when cron can't run: the scheduler's start, its
# once-a-minute maintenance, and the authority error every cron caller gets (memory-core's dreaming
# reconcile too). PCRE, matched case-sensitively by journalctl --grep.
FAILURE_PATTERN = r"\[cron\] failed to start|Cron maintenance failed|Cron receipt authority is unavailable"
EXCERPT = 160
HEARTBEATS_SQL = """
SELECT j.name, r.status, MAX(r.finished_at_ms)
FROM cron_jobs j
LEFT JOIN cron_run_receipts r
  ON r.store_key = j.store_key AND r.job_id = j.job_id AND r.finished_at_ms IS NOT NULL
WHERE j.enabled = 1
  AND (j.payload_kind = 'heartbeat' OR (j.payload_kind = 'agentTurn' AND j.name GLOB 'heartbeat-*'))
GROUP BY j.name
"""
# OpenClaw 2026.11.6's doctor retires heartbeat settings into ordinary automations: the jobs keep
# their id and name (heartbeat-main, ...) and their receipts, but payload_kind becomes 'agentTurn'
# (measured on the PC, 2026-11-22). So a heartbeat is either kind, and the agentTurn ones are known
# by the name OpenClaw gives them.


def log(line):
    print(line, flush=True)


def clock(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def span(seconds):
    minutes = int(seconds // 60)
    if minutes < 90:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"


def systemd_show(unit, props):
    """A unit's properties from systemd, or None if systemd didn't answer. Times as @<unix seconds>."""
    try:
        out = subprocess.run(["systemctl", "show", "--timestamp=unix", unit, "-p", ",".join(props)],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


def gateway_state(show=systemd_show, mono=lambda: time.clock_gettime(time.CLOCK_MONOTONIC)):
    """{active, invocation, up_s, started_at} of the Gateway's unit, or None if systemd didn't answer.
    up_s is on the monotonic clock, so time the PC spent asleep doesn't count as up. In this WSL that
    clock runs about 3 % slow against the wall clock, which only makes the 2.5-hour rule a little
    later, so messages show started_at, systemd's wall-clock start."""
    props = show(GATEWAY, ["ActiveState", "SubState", "InvocationID", "ActiveEnterTimestampMonotonic",
                           "ActiveEnterTimestamp"])
    if props is None:
        return None
    try:
        entered = int(props.get("ActiveEnterTimestampMonotonic") or 0) / 1e6
    except ValueError:
        entered = 0
    try:
        started_at = float((props.get("ActiveEnterTimestamp") or "").lstrip("@")) or None
    except ValueError:
        started_at = None
    return {"active": props.get("ActiveState") or "unknown", "sub": props.get("SubState") or "",
            "invocation": props.get("InvocationID") or None,
            "up_s": max(0.0, mono() - entered) if entered else None, "started_at": started_at}


def read_heartbeats(db=STATE_DB, timeout=5):
    """{job name: {"finished_at": seconds or None, "status": ...}} of the enabled heartbeat jobs.
    The state is opened read-only and never created. Raises OSError or sqlite3.Error."""
    if not os.path.isfile(db):
        raise OSError(f"no file {db}")
    uri = "file:" + urllib.parse.quote(db) + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=timeout)
    try:
        rows = connection.execute(HEARTBEATS_SQL).fetchall()
    finally:
        connection.close()
    if not rows:
        raise OSError("no enabled heartbeat job in cron_jobs")
    return {name: {"finished_at": None if ms is None else ms / 1000, "status": status}
            for name, status, ms in rows}


def _message(value):
    if isinstance(value, list):  # journald gives non-UTF-8 messages as a list of bytes
        value = bytes(v & 0xFF for v in value).decode("utf-8", "replace")
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(value or ""))
    text = re.sub(r"^\d{4}-\d\d-\d\dT\S+\s+", "", text.strip())  # OpenClaw's own timestamp
    return text[:EXCERPT]


def journal_failures(invocation, run=subprocess.run):
    """[(seconds, excerpt)] of the Gateway's failure lines since its current start, oldest first.
    Raises OSError when the journal can't be read or has nothing from this start."""
    base = ["journalctl", f"_SYSTEMD_INVOCATION_ID={invocation}", "--no-pager", "-o", "json",
            "--output-fields=MESSAGE"]
    try:
        probe = run(base + ["-n", "1"], capture_output=True, text=True, errors="replace", timeout=30)
        if probe.returncode != 0:
            raise OSError(f"journalctl exited with {probe.returncode}")
        if not probe.stdout.strip():
            raise OSError("the journal has no line from the Gateway's current start")
        out = run(base + ["--case-sensitive=yes", "-g", FAILURE_PATTERN],
                  capture_output=True, text=True, errors="replace", timeout=30)
    except subprocess.SubprocessError as error:
        raise OSError(f"journalctl: {type(error).__name__}") from error
    if out.returncode == 1 and not out.stdout.strip() and not out.stderr.strip():
        return []  # --grep found nothing
    if out.returncode != 0:
        raise OSError(f"journalctl --grep exited with {out.returncode}")
    found = []
    for raw in out.stdout.splitlines():
        try:
            entry = json.loads(raw)
            found.append((int(entry["__REALTIME_TIMESTAMP"]) / 1e6, _message(entry.get("MESSAGE"))))
        except (ValueError, KeyError, TypeError) as error:
            raise OSError("journalctl gave a line that isn't journal JSON") from error
    return sorted(found)


def evaluate(now, gateway, heartbeats, journal, stale_after=STALE_AFTER, settle=SETTLE):
    """The report. heartbeats and journal are each a value, or an exception when unreadable."""
    report = {"checked_at": now, "gateway": None, "heartbeats": None, "journal": None, "errors": {}}

    def done(status, summary):
        report.update({"status": status, "summary": summary})
        return report

    if gateway is None:
        return done("unknown", "systemd didn't answer for the Gateway")
    up = gateway.get("up_s")
    report["gateway"] = {"active": gateway["active"], "up_s": up,
                         "since": gateway.get("started_at") or (None if up is None else now - up)}
    if gateway["active"] != "active":
        return done("pending", f"the Gateway is {gateway['active']}, so there is nothing to check "
                               f"(the watchdog's Gateway check covers it)")
    if up is None or not gateway.get("invocation"):
        return done("unknown", "systemd gave no start time or invocation for the Gateway")
    since = report["gateway"]["since"]
    if up < settle:
        return done("pending", f"the Gateway started {int(up)} s ago")

    newest = None
    if isinstance(heartbeats, Exception):
        report["errors"]["receipts"] = _error_text(heartbeats)
    else:
        report["heartbeats"] = heartbeats
        times = [h["finished_at"] for h in heartbeats.values() if h["finished_at"] is not None]
        newest = max(times) if times else None
    report["newest_heartbeat_at"] = newest
    if isinstance(journal, Exception):
        report["errors"]["journal"] = _error_text(journal)
    elif journal:
        report["journal"] = {"count": len(journal), "first_at": journal[0][0], "first": journal[0][1],
                             "last_at": journal[-1][0], "last": journal[-1][1]}

    last_line = report["journal"]["last_at"] if report["journal"] else None
    if last_line is not None and (newest is None or newest < last_line):
        first = report["journal"]
        text = f'the Gateway logged "{first["first"]}" at {clock(first["first_at"])}'
        if first["count"] > 1:
            text += f" ({first['count']} such lines since it started at {clock(since)})"
        if "receipts" in report["errors"]:
            text += f", and the cron receipts couldn't be read ({report['errors']['receipts']})"
        elif newest is None:
            text += ", and no heartbeat has ever finished"
        else:
            text += f", and no heartbeat has finished since {clock(newest)}"
        return done("failing", text)
    if "receipts" in report["errors"]:
        return done("unknown", f"couldn't read the cron receipts ({report['errors']['receipts']})")
    if "journal" in report["errors"]:
        return done("unknown", f"couldn't read the Gateway's journal ({report['errors']['journal']})")

    if newest is None or now - newest > stale_after:
        last = "no heartbeat has ever finished" if newest is None else \
            f"no heartbeat has finished since {clock(newest)} ({span(now - newest)} ago)"
        if up > stale_after:
            return done("failing", f"{last}, though the Gateway has been up since {clock(since)}")
        return done("pending", f"{last}, and the Gateway has been up only since {clock(since)}")
    name = max((h["finished_at"] or 0, n) for n, h in heartbeats.items())[1]
    text = f"newest heartbeat: {name} at {clock(newest)}"
    if report["journal"]:
        text += f"; cron errors in the journal until {clock(last_line)}, but a heartbeat finished after"
    else:
        text += f"; no cron error in the journal since the Gateway started at {clock(since)}"
    return done("ok", text)


def _error_text(error):
    return f"{type(error).__name__}: {error}"[:EXCERPT]


def check(now=None, show=systemd_show, db=STATE_DB, run=subprocess.run,
          mono=lambda: time.clock_gettime(time.CLOCK_MONOTONIC)):
    now = time.time() if now is None else now
    gateway = gateway_state(show, mono)
    heartbeats = journal = None
    if gateway is not None and gateway["active"] == "active" and gateway.get("invocation"):
        try:
            heartbeats = read_heartbeats(db)
        except (OSError, sqlite3.Error) as error:
            heartbeats = error
        try:
            journal = journal_failures(gateway["invocation"], run)
        except OSError as error:
            journal = error
    return evaluate(now, gateway, heartbeats, journal)


def write_report(path, report):
    if path == "-":
        print(json.dumps(report, indent=1, sort_keys=True))
        return
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=1, sort_keys=True))
    os.chmod(tmp, 0o644)
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    tmp.replace(path)


def main(argv=None, **check_args):
    parser = argparse.ArgumentParser(prog="jorah-cron-watch")
    parser.add_argument("command", choices=["check", "show"])
    parser.add_argument("--report", default=REPORT, help="where to write it; - prints it")
    parser.add_argument("--db", default=STATE_DB)
    args = parser.parse_args(argv)
    if args.command == "show":
        try:
            print(Path(args.report).read_text())
        except OSError:
            print("{}")
        return 0
    report = check(db=args.db, **check_args)
    write_report(args.report, report)
    out = sys.stderr if args.report == "-" else sys.stdout
    print(f"cron: {report['status']}: {report['summary']}", file=out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
