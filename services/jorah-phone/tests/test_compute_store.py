import sqlite3
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_phone import schema  # noqa: E402
from jorah_phone.compute import summarize, workout_type  # noqa: E402
from jorah_phone.store import Store  # noqa: E402

TZ = ZoneInfo("Europe/Bratislava")


def local(text):
    """'2026-11-15 07:00' in Bratislava as an ISO string with its offset."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=TZ).isoformat()


def upload(sent, sleep=(), hrv=(), resting=(), workouts=()):
    return {
        "v": 1, "sent_at": local(sent),
        "sleep": [{"start": local(a), "end": local(b)} for a, b in sleep],
        "hrv": [{"at": local(a), "ms": v} for a, v in hrv],
        "resting_hr": [{"at": local(a), "bpm": v} for a, v in resting],
        "workouts": [{"start": local(a), "end": local(b), "type": t} for a, b, t in workouts],
    }


class ComputeTest(unittest.TestCase):
    def test_a_night_from_two_sources_is_counted_once(self):
        row = summarize(upload(
            "2026-11-15 07:30",
            sleep=[("2026-11-14 23:10", "2026-11-15 03:00"), ("2026-11-15 02:30", "2026-11-15 06:40"),   # phone and watch overlap
                   ("2026-11-14 13:00", "2026-11-14 14:00")],                                         # yesterday's nap: outside the night
            hrv=[("2026-11-15 02:00", 40), ("2026-11-15 04:00", 50), ("2026-11-15 05:00", 61), ("2026-11-14 12:00", 200)],
            resting=[("2026-11-14 07:00", 58), ("2026-11-15 06:00", 55)],
        ), TZ)
        self.assertEqual(row["day"], "2026-11-15")
        self.assertEqual(row["asleep_min"], 450)          # 23:10 to 06:40
        self.assertEqual(row["bed"], local("2026-11-14 23:10"))
        self.assertEqual(row["wake"], local("2026-11-15 06:40"))
        self.assertEqual(row["hrv_ms"], 50)               # median inside the night; the noon sample is out
        self.assertEqual(row["resting_bpm"], 55)          # the newest

    def test_no_data_stays_none_never_zero(self):
        row = summarize(upload("2026-11-15 07:30"), TZ)
        self.assertEqual(row, {"day": "2026-11-15", "bed": None, "wake": None, "asleep_min": None,
                               "hrv_ms": None, "resting_bpm": None, "workouts": []})

    def test_hrv_without_a_night_uses_the_last_day(self):
        row = summarize(upload("2026-11-15 07:30", hrv=[("2026-11-14 09:00", 30), ("2026-11-14 06:00", 99)]), TZ)
        self.assertEqual(row["hrv_ms"], 30)

    def test_a_night_across_the_clock_change_is_real_time(self):
        # 2026-10-25: Europe's clocks go back at 03:00, so 22:00 to 07:00 is ten hours asleep.
        row = summarize(upload("2026-10-25 08:00", sleep=[("2026-10-24 22:00", "2026-10-25 07:00")]), TZ)
        self.assertEqual(row["asleep_min"], 600)

    def test_broken_intervals_are_ignored(self):
        row = summarize(upload("2026-11-15 07:30", sleep=[("2026-11-15 06:00", "2026-11-15 05:00")]), TZ)
        self.assertIsNone(row["asleep_min"])

    def test_workouts(self):
        row = summarize(upload("2026-11-15 20:00", workouts=[
            ("2026-11-15 07:00", "2026-11-15 07:31", "Outdoor Run"),
            ("2026-11-15 17:00", "2026-11-15 17:45", "Traditional Strength Training"),
            ("2026-11-14 17:00", "2026-11-14 18:00", "Cycling"),                      # yesterday
        ]), TZ)
        self.assertEqual(row["workouts"], [{"type": "running", "minutes": 31}, {"type": "strength", "minutes": 45}])
        for name, kind in (("Chôdza", "walking"), ("Beh", "running"), ("Plávanie", "swimming"), ("HIIT", "hiit"),
                           ("High Intensity Interval Training", "hiit"), ("Indoor Walk", "walking"), ("Core Training", "other")):
            self.assertEqual(workout_type(name), kind, name)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 11, 15, 9, 0, tzinfo=TZ).astimezone(timezone.utc)
        self.store = Store(Path(self.dir.name) / "data" / "phone.db", TZ, now=lambda: self.now)
        self.today_schema = schema.load("today")
        self.events_schema = schema.load("events")

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def at(self, text):
        return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)

    def today(self, health=True):
        return schema.validate(self.today_schema, self.store.today(health, "Europe/Bratislava"))

    def test_file_modes(self):
        path = Path(self.dir.name) / "data" / "phone.db"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_nothing_stored_is_no_data(self):
        t = self.today()
        self.assertEqual(t["phone"]["status"], "no_data")
        self.assertEqual(t["phone"]["location"], {"state": "unknown", "place": None, "since": None})
        self.assertIsNone(t["phone"]["woke_at"])
        self.assertEqual(t["health"]["status"], "no_data")
        self.assertEqual(self.today(health=False)["health"]["status"], "off")

    def test_location_wake_and_focus(self):
        s = self.store
        s.add_event("alarm_stopped", None, None, self.at("2026-11-14 06:30"))     # yesterday's
        s.add_event("alarm_stopped", None, None, self.at("2026-11-15 06:45"))
        s.add_event("wake", None, None, self.at("2026-11-15 07:10"))
        s.add_event("leave", "home", None, self.at("2026-11-15 07:40"))
        s.add_event("arrive", "school", None, self.at("2026-11-15 07:58"))
        s.add_event("focus_on", None, "school", self.at("2026-11-15 08:00"))
        t = self.today()
        self.assertEqual(t["date"], "2026-11-15")
        self.assertEqual(t["phone"]["location"], {"state": "at", "place": "school", "since": self.at("2026-11-15 07:58").isoformat()})
        self.assertEqual(t["phone"]["woke_at"], self.at("2026-11-15 06:45").isoformat())
        self.assertEqual(t["phone"]["focus"], {"value": "school", "since": self.at("2026-11-15 08:00").isoformat()})
        self.assertEqual(t["phone"]["last_event"]["kind"], "focus_on")
        s.add_event("focus_off", None, "school", self.at("2026-11-15 08:30"))
        s.add_event("leave", "school", None, self.at("2026-11-15 08:40"))
        t = self.today()
        self.assertEqual(t["phone"]["focus"], {"value": None, "since": None})
        self.assertEqual(t["phone"]["location"]["state"], "left")

    def test_old_location_is_unknown(self):
        self.store.add_event("arrive", "home", None, self.at("2026-11-14 08:00"))   # 25 hours ago
        t = self.today()
        self.assertEqual(t["phone"]["status"], "ok")
        self.assertEqual(t["phone"]["location"]["state"], "unknown")

    def test_the_same_event_twice_is_stored_once(self):
        a = self.store.add_event("arrive", "home", None, self.at("2026-11-15 08:00"))
        b = self.store.add_event("arrive", "home", None, self.at("2026-11-15 08:00"))
        c = self.store.add_event("arrive", "school", None, self.at("2026-11-15 08:00"))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_events_since(self):
        first = self.store.add_event("arrive", "home", None, self.at("2026-11-15 08:00"))
        self.now += timedelta(minutes=5)
        self.store.add_event("leave", "home", None, self.at("2026-11-15 08:04"))
        got = schema.validate(self.events_schema, self.store.events_since(self.now - timedelta(minutes=10)))
        self.assertEqual([e["kind"] for e in got["events"]], ["arrive", "leave"])
        self.assertEqual(got["events"][0]["id"], first)
        later = self.store.events_since(self.now - timedelta(minutes=1))
        self.assertEqual([e["kind"] for e in later["events"]], ["leave"])
        self.assertEqual(len(self.store.events_since(self.now - timedelta(days=1), limit=1)["events"]), 1)

    def row(self, day, asleep=420, hrv=50, resting=55, workouts=()):
        return {"day": day, "bed": f"{day}T00:00:00+01:00", "wake": f"{day}T07:00:00+01:00", "asleep_min": asleep,
                "hrv_ms": hrv, "resting_bpm": resting, "workouts": list(workouts)}

    def test_health_today_with_medians(self):
        for day, asleep in (("2026-11-12", 400), ("2026-11-13", 440), ("2026-11-14", 480)):
            self.store.put_health_day(self.row(day, asleep=asleep, hrv=40))
        self.store.put_health_day(self.row("2026-11-15", asleep=300, hrv=None, workouts=[{"type": "running", "minutes": 30}]))
        h = self.today()["health"]
        self.assertEqual(h["status"], "ok")
        self.assertEqual(h["night"]["asleep_min"], 300)
        self.assertEqual(h["night"]["median_14d_min"], 440)
        self.assertIsNone(h["hrv_ms"])                       # none today: null, never 0
        self.assertEqual(h["resting_bpm"], {"value": 55, "median_14d": 55})
        self.assertEqual(h["workouts"], [{"type": "running", "minutes": 30}])

    def test_health_medians_need_three_nights(self):
        self.store.put_health_day(self.row("2026-11-14"))
        self.store.put_health_day(self.row("2026-11-15"))
        self.assertIsNone(self.today()["health"]["night"]["median_14d_min"])

    def test_health_from_an_earlier_day_is_stale(self):
        self.store.put_health_day(self.row("2026-11-13", workouts=[{"type": "yoga", "minutes": 20}]))
        h = self.today()["health"]
        self.assertEqual(h["status"], "stale")
        self.assertEqual(h["night"]["date"], "2026-11-13")
        self.assertEqual(h["workouts"], [])                  # not today's

    def test_a_later_upload_replaces_the_day(self):
        self.store.put_health_day(self.row("2026-11-15", asleep=100))
        self.store.put_health_day(self.row("2026-11-15", asleep=420))
        self.assertEqual(self.today()["health"]["night"]["asleep_min"], 420)

    def test_retention(self):
        self.store.add_event("arrive", "home", None, self.at("2026-10-10 08:00"))
        self.store.put_health_day(self.row("2026-08-01"))
        self.store.add_event("arrive", "home", None, self.at("2026-11-15 08:00"))   # a write prunes
        db = sqlite3.connect(Path(self.dir.name) / "data" / "phone.db")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM health_days").fetchone()[0], 0)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertEqual(tables, {"events", "health_days"})   # no samples, no questions, nothing else
        db.close()


if __name__ == "__main__":
    unittest.main()
