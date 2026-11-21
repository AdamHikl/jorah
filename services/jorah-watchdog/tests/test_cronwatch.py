import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cronwatch  # noqa: E402

NOW = 1_800_000_000.0
HOUR = 3600
LIVE = "/home/jorah/.openclaw-jorah/cron/jobs.json"
OLD = "/Users/adam/.openclaw-jorah/cron/jobs.json"


def gateway(up=5 * HOUR, active="active", invocation="7d20ef9aca294026b82519dd91f039a8"):
    return {"active": active, "sub": "running", "invocation": invocation, "up_s": up}


def beats(*hours_ago):
    """Heartbeats that finished that many hours before NOW; None for one that never did."""
    return {f"heartbeat-{i}": {"finished_at": None if h is None else NOW - h * HOUR, "status": "ok"}
            for i, h in enumerate(hours_ago)}


def line(hours_ago, text="[cron] failed to start: Error: Cron receipt authority is unavailable"):
    return (NOW - hours_ago * HOUR, text)


class Evaluate(unittest.TestCase):
    def test_a_recent_heartbeat_and_a_clean_journal_is_ok(self):
        report = cronwatch.evaluate(NOW, gateway(), beats(0.5, 0.6, 3), [])
        self.assertEqual(report["status"], "ok", report["summary"])
        self.assertIn("heartbeat-0", report["summary"])
        self.assertEqual(report["newest_heartbeat_at"], NOW - 0.5 * HOUR)

    def test_the_failure_line_fails_at_once(self):
        # 2026-11-21: the Gateway started at 02:13, cron failed to start 25 s later, last heartbeat 01:11.
        report = cronwatch.evaluate(NOW, gateway(up=0.1 * HOUR), beats(1.1, 1.1, 1.1),
                                    [line(0.09), line(0.05, "[cron/maintenance] Cron maintenance failed")])
        self.assertEqual(report["status"], "failing")
        self.assertIn('logged "[cron] failed to start', report["summary"])
        self.assertIn("2 such lines", report["summary"])
        self.assertIn("no heartbeat has finished since", report["summary"])
        self.assertEqual(report["journal"]["count"], 2)

    def test_a_heartbeat_after_the_last_failure_line_is_ok(self):
        report = cronwatch.evaluate(NOW, gateway(), beats(0.2), [line(2), line(1)])
        self.assertEqual(report["status"], "ok", report["summary"])
        self.assertIn("but a heartbeat finished after", report["summary"])

    def test_no_heartbeat_for_hours_fails_once_the_gateway_has_been_up_that_long(self):
        report = cronwatch.evaluate(NOW, gateway(up=4 * HOUR), beats(3, 3.2, None), [])
        self.assertEqual(report["status"], "failing")
        self.assertIn("3 h 00 min ago", report["summary"])
        self.assertIn("though the Gateway has been up since", report["summary"])

    def test_old_heartbeats_after_a_recent_start_are_pending(self):
        # The PC was off overnight, or the 6-hourly restart: too early to tell, not ok.
        report = cronwatch.evaluate(NOW, gateway(up=1 * HOUR), beats(9), [])
        self.assertEqual(report["status"], "pending")

    def test_no_heartbeat_ever_fails_only_after_the_threshold(self):
        self.assertEqual(cronwatch.evaluate(NOW, gateway(up=1 * HOUR), beats(None), [])["status"], "pending")
        report = cronwatch.evaluate(NOW, gateway(up=3 * HOUR), beats(None), [])
        self.assertEqual(report["status"], "failing")
        self.assertIn("no heartbeat has ever finished", report["summary"])

    def test_just_after_a_start_is_pending(self):
        self.assertEqual(cronwatch.evaluate(NOW, gateway(up=30), beats(9), [])["status"], "pending")

    def test_a_stopped_gateway_is_pending(self):
        report = cronwatch.evaluate(NOW, gateway(active="inactive", invocation=None, up=None), None, None)
        self.assertEqual(report["status"], "pending")
        self.assertIn("Gateway check covers it", report["summary"])

    def test_systemd_not_answering_is_unknown(self):
        self.assertEqual(cronwatch.evaluate(NOW, None, None, None)["status"], "unknown")
        self.assertEqual(cronwatch.evaluate(NOW, gateway(invocation=None), beats(0.1), [])["status"], "unknown")

    def test_unreadable_receipts_are_unknown_never_ok(self):
        report = cronwatch.evaluate(NOW, gateway(), sqlite3.OperationalError("database is locked"), [])
        self.assertEqual(report["status"], "unknown")
        self.assertIn("database is locked", report["summary"])

    def test_an_unreadable_journal_is_unknown_even_with_fresh_heartbeats(self):
        report = cronwatch.evaluate(NOW, gateway(), beats(0.1), OSError("journalctl exited with 1"))
        self.assertEqual(report["status"], "unknown")
        self.assertIn("journal", report["summary"])

    def test_messages_show_systemds_wall_clock_start_not_the_monotonic_one(self):
        started = NOW - 4 * HOUR - 7 * 60  # the monotonic clock ran slow: up_s says 4 h only
        report = cronwatch.evaluate(NOW, {**gateway(up=4 * HOUR), "started_at": started}, beats(3), [])
        self.assertEqual(report["gateway"]["since"], started)
        self.assertIn(f"up since {cronwatch.clock(started)}", report["summary"])

    def test_a_failure_line_still_fails_when_the_receipts_are_unreadable(self):
        report = cronwatch.evaluate(NOW, gateway(), OSError("no file"), [line(0.5)])
        self.assertEqual(report["status"], "failing")
        self.assertIn("couldn't be read", report["summary"])


class Heartbeats(unittest.TestCase):
    """Against a real WAL-mode database held open by a writer, as the Gateway holds it."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.db = str(self.dir / "openclaw.sqlite")
        self.writer = sqlite3.connect(self.db)
        self.writer.execute("PRAGMA journal_mode=wal")
        self.writer.executescript("""
            CREATE TABLE cron_jobs (store_key TEXT NOT NULL, job_id TEXT NOT NULL, name TEXT NOT NULL,
              enabled INTEGER NOT NULL, payload_kind TEXT NOT NULL, PRIMARY KEY (store_key, job_id));
            CREATE TABLE cron_run_receipts (receipt_id TEXT PRIMARY KEY, store_key TEXT NOT NULL,
              job_id TEXT NOT NULL, status TEXT NOT NULL, started_at_ms INTEGER NOT NULL,
              finished_at_ms INTEGER, error_text TEXT);
        """)
        jobs = [(LIVE, "m", "heartbeat-main", 1, "heartbeat"), (OLD, "old", "heartbeat-main", 1, "heartbeat"),
                (LIVE, "d", "heartbeat-deep", 1, "heartbeat"), (LIVE, "off", "heartbeat-old", 0, "heartbeat"),
                (LIVE, "dream", "Memory Dreaming Promotion", 1, "agentTurn"),
                (LIVE, "new", "heartbeat-background", 1, "heartbeat")]
        self.writer.executemany("INSERT INTO cron_jobs VALUES (?, ?, ?, ?, ?)", jobs)
        ms = lambda hours_ago: int((NOW - hours_ago * HOUR) * 1000)  # noqa: E731
        receipts = [("r1", LIVE, "m", "ok", ms(2), ms(2)), ("r2", LIVE, "m", "skipped", ms(1), ms(1)),
                    ("r3", OLD, "old", "ok", ms(400), ms(400)), ("r4", LIVE, "d", "error", ms(1.5), ms(1.5)),
                    ("r5", LIVE, "d", "running", ms(0.1), None), ("r6", LIVE, "off", "ok", ms(0), ms(0)),
                    ("r7", LIVE, "dream", "ok", ms(0), ms(0))]
        self.writer.executemany("INSERT INTO cron_run_receipts (receipt_id, store_key, job_id, status, "
                                "started_at_ms, finished_at_ms) VALUES (?, ?, ?, ?, ?, ?)", receipts)
        self.writer.commit()

    def tearDown(self):
        self.writer.close()

    def test_reads_the_newest_finished_receipt_of_each_enabled_heartbeat(self):
        found = cronwatch.read_heartbeats(self.db)
        self.assertEqual(set(found), {"heartbeat-main", "heartbeat-deep", "heartbeat-background"})
        self.assertEqual(found["heartbeat-main"], {"finished_at": NOW - HOUR, "status": "skipped"})
        self.assertEqual(found["heartbeat-deep"]["status"], "error")  # the running one has no finish
        self.assertIsNone(found["heartbeat-background"]["finished_at"])

    def test_sees_rows_still_in_the_writers_wal(self):
        self.writer.execute("INSERT INTO cron_run_receipts (receipt_id, store_key, job_id, status, "
                            "started_at_ms, finished_at_ms) VALUES ('r9', ?, 'new', 'ok', ?, ?)",
                            (LIVE, int(NOW * 1000), int(NOW * 1000)))
        self.writer.commit()
        self.assertTrue(Path(self.db + "-wal").exists())
        self.assertEqual(cronwatch.read_heartbeats(self.db)["heartbeat-background"]["finished_at"], NOW)

    def test_opens_read_only(self):
        before = Path(self.db).stat().st_mtime_ns, Path(self.db).read_bytes()
        cronwatch.read_heartbeats(self.db)
        self.assertEqual((Path(self.db).stat().st_mtime_ns, Path(self.db).read_bytes()), before)

    def test_a_missing_database_raises_and_is_never_created(self):
        missing = str(self.dir / "nothing.sqlite")
        with self.assertRaises(OSError):
            cronwatch.read_heartbeats(missing)
        self.assertFalse(os.path.exists(missing))

    def test_no_enabled_heartbeat_raises(self):
        self.writer.execute("UPDATE cron_jobs SET enabled = 0 WHERE payload_kind = 'heartbeat'")
        self.writer.commit()
        with self.assertRaises(OSError):
            cronwatch.read_heartbeats(self.db)

    def test_a_changed_schema_raises_a_sqlite_error(self):
        self.writer.execute("ALTER TABLE cron_run_receipts RENAME TO cron_receipts_v2")
        self.writer.commit()
        with self.assertRaises(sqlite3.Error):
            cronwatch.read_heartbeats(self.db)


class Journal:
    """Stand-in for journalctl: the probe (-n 1), then --grep."""

    def __init__(self, probe='{"MESSAGE": "hello"}\n', grep="", grep_rc=0, grep_err=""):
        self.probe, self.grep, self.grep_rc, self.grep_err = probe, grep, grep_rc, grep_err
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if "-g" in argv:
            return subprocess.CompletedProcess(argv, self.grep_rc, self.grep, self.grep_err)
        return subprocess.CompletedProcess(argv, 0, self.probe, "")


def entry(seconds, message):
    return json.dumps({"__REALTIME_TIMESTAMP": str(int(seconds * 1e6)), "MESSAGE": message}) + "\n"


class JournalFailures(unittest.TestCase):
    def test_parses_and_sorts_matching_lines_and_drops_openclaws_timestamp(self):
        out = entry(NOW, "2026-11-21T02:14:53.946+01:00 [cron/maintenance] Cron maintenance failed error=x") + \
            entry(NOW - 60, "2026-11-21T02:13:42.040+01:00 [cron] failed to start: Error: Cron receipt authority")
        run = Journal(grep=out)
        found = cronwatch.journal_failures("abc", run)
        self.assertEqual([t for t, _ in found], [NOW - 60, NOW])
        self.assertTrue(found[0][1].startswith("[cron] failed to start"))
        grep = run.calls[1]
        self.assertIn("_SYSTEMD_INVOCATION_ID=abc", grep)
        self.assertEqual(grep[grep.index("-g") + 1], cronwatch.FAILURE_PATTERN)
        self.assertIn("--case-sensitive=yes", grep)

    def test_binary_messages_and_long_lines_are_cut(self):
        raw = list(("[cron] failed to start: " + "x" * 400).encode()) + [0xFF]
        run = Journal(grep=json.dumps({"__REALTIME_TIMESTAMP": "1", "MESSAGE": raw}) + "\n")
        (_, text), = cronwatch.journal_failures("abc", run)
        self.assertEqual(len(text), cronwatch.EXCERPT)

    def test_grep_finding_nothing_is_an_empty_list(self):
        self.assertEqual(cronwatch.journal_failures("abc", Journal(grep_rc=1)), [])

    def test_grep_errors_raise(self):
        with self.assertRaises(OSError):
            cronwatch.journal_failures("abc", Journal(grep_rc=1, grep_err="Failed to compile pattern"))
        with self.assertRaises(OSError):
            cronwatch.journal_failures("abc", Journal(grep="not json\n"))

    def test_no_line_at_all_from_this_start_raises(self):
        # A wrong invocation id gives nothing rather than an error, so "no failure lines" would lie.
        with self.assertRaises(OSError):
            cronwatch.journal_failures("abc", Journal(probe=""))


class Main(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.show = lambda unit, props: {"ActiveState": "active", "SubState": "running",
                                         "InvocationID": "abc", "ActiveEnterTimestampMonotonic": "1000000",
                                         "ActiveEnterTimestamp": f"@{int(NOW - 4 * HOUR - 300)}"}

    def run_main(self, report, db="/nonexistent/openclaw.sqlite", run=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cronwatch.main(["check", "--report", report, "--db", db], now=NOW, show=self.show,
                                  run=run or Journal(), mono=lambda: 4 * HOUR)
        return code, out.getvalue(), err.getvalue()

    def test_writes_a_world_readable_report(self):
        path = self.dir / "report.json"
        code, out, _ = self.run_main(str(path))
        self.assertEqual(code, 0)
        report = json.loads(path.read_text())
        self.assertEqual(report["status"], "unknown")  # the database is missing: unknown, not ok
        self.assertEqual(report["checked_at"], NOW)
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        self.assertIn("cron: unknown: couldn't read the cron receipts", out)
        self.assertEqual(report["gateway"]["since"], int(NOW - 4 * HOUR - 300))

    def test_dash_prints_the_report_and_writes_nothing(self):
        code, out, err = self.run_main("-", run=Journal(grep=entry(NOW - 60, "[cron] failed to start: x")))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "failing")
        self.assertIn("cron: failing", err)
        self.assertEqual(list(self.dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
