"""The phone's store: typed events and one health row per day, in SQLite, with retention.

Only what the contract names is kept: no question, no answer, no health sample, no coordinate.
Everything returned is built by code from these rows (today.schema.json, events.schema.json).
"""

import json
import os
import sqlite3
import threading
import time as clock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

DEFAULT_DB = Path.home() / ".local" / "share" / "jorah-phone" / "phone.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  place TEXT,
  focus TEXT,
  at_ts REAL NOT NULL,
  received_ts REAL NOT NULL,
  dedupe TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS events_at ON events (at_ts);
CREATE TABLE IF NOT EXISTS health_days (
  day TEXT PRIMARY KEY,
  bed TEXT,
  wake TEXT,
  asleep_min INTEGER,
  hrv_ms INTEGER,
  resting_bpm INTEGER,
  workouts TEXT NOT NULL,
  received_ts REAL NOT NULL
);
"""

ARRIVE_LEAVE = ("arrive", "leave")
WAKE = ("alarm_stopped", "wake")


def _median_or_none(values):
    values = [v for v in values if v is not None]
    return round(median(values)) if len(values) >= 3 else None


class Store:
    def __init__(self, path=DEFAULT_DB, tz=timezone.utc, keep_events_days=30, keep_health_days=90, now=None):
        self._path = Path(path)
        self._tz = tz
        self._keep_events = keep_events_days
        self._keep_health = keep_health_days
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._pruned_at = 0.0
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        new = not self._path.exists()
        if new:
            os.close(os.open(self._path, os.O_WRONLY | os.O_CREAT, 0o600))
        os.chmod(self._path, 0o600)
        self._db = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=DELETE")
        self._db.executescript(SCHEMA)

    def close(self):
        with self._lock:
            self._db.close()

    def _local(self, ts):
        return datetime.fromtimestamp(ts, timezone.utc).astimezone(self._tz).isoformat(timespec="seconds")

    def prune(self, force=False):
        now = self._now()
        if not force and clock.monotonic() - self._pruned_at < 3600:
            return
        self._pruned_at = clock.monotonic()
        events_before = (now - timedelta(days=self._keep_events)).timestamp()
        health_before = (now.astimezone(self._tz).date() - timedelta(days=self._keep_health)).isoformat()
        with self._lock:
            self._db.execute("DELETE FROM events WHERE at_ts < ?", (events_before,))
            self._db.execute("DELETE FROM health_days WHERE day < ?", (health_before,))

    # --- writes -------------------------------------------------------------------------------

    def add_event(self, kind, place, focus, at):
        """Store one event; the same event sent twice is stored once. Returns its id."""
        at_ts = at.timestamp()
        dedupe = f"{kind}|{place or ''}|{focus or ''}|{at_ts:.0f}"
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO events (kind, place, focus, at_ts, received_ts, dedupe) VALUES (?, ?, ?, ?, ?, ?)",
                (kind, place, focus, at_ts, self._now().timestamp(), dedupe))
            (event_id,) = self._db.execute("SELECT id FROM events WHERE dedupe = ?", (dedupe,)).fetchone()
        self.prune(force=True)
        return event_id

    def put_health_day(self, row):
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO health_days (day, bed, wake, asleep_min, hrv_ms, resting_bpm, workouts, received_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row["day"], row["bed"], row["wake"], row["asleep_min"], row["hrv_ms"], row["resting_bpm"],
                 json.dumps(row["workouts"]), self._now().timestamp()))
        self.prune(force=True)

    # --- reads --------------------------------------------------------------------------------

    def events_since(self, since, limit=50):
        with self._lock:
            rows = self._db.execute(
                "SELECT id, kind, place, focus, at_ts, received_ts FROM events WHERE received_ts > ? ORDER BY received_ts, id LIMIT ?",
                (since.timestamp(), max(1, min(200, limit)))).fetchall()
        return {"v": 1, "events": [
            {"id": r[0], "kind": r[1], "place": r[2], "focus": r[3], "at": self._local(r[4]), "received_at": self._local(r[5])}
            for r in rows]}

    def _phone(self, now):
        since = (now - timedelta(days=self._keep_events)).timestamp()
        day_start = datetime.combine(now.astimezone(self._tz).date(), datetime.min.time(), tzinfo=self._tz).timestamp()
        recent = (now - timedelta(hours=24)).timestamp()
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, place, focus, at_ts FROM events WHERE at_ts >= ? AND at_ts <= ? ORDER BY at_ts, id",
                (since, now.timestamp() + 300)).fetchall()
        last = rows[-1] if rows else None
        moves = [r for r in rows if r[0] in ARRIVE_LEAVE and r[3] >= recent]
        woke = [r for r in rows if r[0] in WAKE and r[3] >= day_start]
        focus_value = focus_since = None
        for kind, _place, focus, at_ts in rows:
            if at_ts < recent:
                continue
            if kind == "focus_on":
                focus_value, focus_since = focus, at_ts
            elif kind == "focus_off" and focus == focus_value:
                focus_value = focus_since = None
        location = {"state": "unknown", "place": None, "since": None}
        if moves:
            kind, place, _focus, at_ts = moves[-1]
            location = {"state": "at" if kind == "arrive" else "left", "place": place, "since": self._local(at_ts)}
        return {
            "status": "ok" if rows else "no_data",
            "last_event": {"kind": last[0], "place": last[1], "focus": last[2], "at": self._local(last[3])} if last else None,
            "location": location,
            "woke_at": self._local(woke[0][3]) if woke else None,
            "focus": {"value": focus_value, "since": self._local(focus_since) if focus_since else None},
        }

    def _health(self, now, enabled):
        off = {"status": "off", "received_at": None, "night": None, "hrv_ms": None, "resting_bpm": None, "workouts": []}
        if not enabled:
            return off
        with self._lock:
            row = self._db.execute(
                "SELECT day, bed, wake, asleep_min, hrv_ms, resting_bpm, workouts, received_ts FROM health_days ORDER BY day DESC LIMIT 1").fetchone()
            if row is None:
                return {**off, "status": "no_data"}
            day = datetime.fromisoformat(row[0]).date()
            before = self._db.execute(
                "SELECT asleep_min, hrv_ms, resting_bpm FROM health_days WHERE day >= ? AND day < ?",
                ((day - timedelta(days=14)).isoformat(), row[0])).fetchall()
        today = now.astimezone(self._tz).date().isoformat()
        night = None
        if row[1] and row[2] and row[3] is not None:
            night = {"date": row[0], "bed": row[1], "wake": row[2], "asleep_min": row[3],
                     "median_14d_min": _median_or_none([b[0] for b in before])}
        return {
            "status": "ok" if row[0] == today else "stale",
            "received_at": self._local(row[7]),
            "night": night,
            "hrv_ms": {"value": row[4], "median_14d": _median_or_none([b[1] for b in before])} if row[4] is not None else None,
            "resting_bpm": {"value": row[5], "median_14d": _median_or_none([b[2] for b in before])} if row[5] is not None else None,
            "workouts": json.loads(row[6]) if row[0] == today else [],
        }

    def today(self, health_enabled, tz_name):
        self.prune()
        now = self._now()
        return {
            "v": 1,
            "generated_at": now.astimezone(self._tz).isoformat(timespec="seconds"),
            "tz": tz_name,
            "date": now.astimezone(self._tz).date().isoformat(),
            "phone": self._phone(now),
            "health": self._health(now, health_enabled),
        }
