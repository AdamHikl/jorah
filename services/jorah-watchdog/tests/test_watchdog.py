import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import watchdog  # noqa: E402

TOKEN = "123456:TEST-token-not-real-ABCDEFGHIJKLMNOPQRSTUV"


class Systemd:
    """Stand-in for `systemctl show`: everything up unless a test changes it."""

    def __init__(self):
        self.units = {
            "openclaw-gateway.service": {"ActiveState": "active", "SubState": "running"},
            "jorah-projects.timer": {"LoadState": "loaded", "ActiveState": "active"},
            "jorah-projects.service": {"Result": "success"},
        }

    def __call__(self, unit, props):
        found = self.units.get(unit)
        return None if found is None else {p: found.get(p, "") for p in props}


class Telegram:
    def __init__(self):
        self.sent = []
        self.fail = False

    def __call__(self, request, timeout):
        if self.fail:
            raise urllib.error.URLError("network down")
        self.sent.append({k: v[0] for k, v in urllib.parse.parse_qs(request.data.decode()).items()})
        self.urls = getattr(self, "urls", []) + [request.full_url]
        return io.BytesIO(json.dumps({"ok": True}).encode())


class Watchdog(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "conf").write_text(json.dumps({"chat_id": "42", "gateway_port": 43181}))
        (self.dir / "token").write_text(TOKEN + "\n")
        self.systemd = Systemd()
        self.telegram = Telegram()
        self.ready = True
        self.now = 1_800_000_000.0
        self.lines = []
        watchdog.log = self.lines.append
        watchdog.readyz = lambda port, timeout=5: self.ready

    def run_check(self, minutes_later=5, command="check", token=True):
        self.now += minutes_later * 60
        args = [command, "--conf", str(self.dir / "conf"), "--state", str(self.dir / "state.json"),
                "--token-file", str(self.dir / ("token" if token else "missing"))]
        return watchdog.main(args, now=self.now, show=self.systemd, opener=self.telegram)

    def texts(self):
        return [m["text"] for m in self.telegram.sent]

    def test_all_fine_sends_nothing(self):
        for _ in range(12):
            self.run_check()
        self.assertEqual(self.telegram.sent, [])

    def test_gateway_down_alerts_once_after_ten_minutes_then_says_back(self):
        self.run_check()
        self.systemd.units["openclaw-gateway.service"] = {"ActiveState": "failed", "SubState": "failed"}
        self.run_check()  # 0 min down
        self.run_check()  # 5 min
        self.assertEqual(self.telegram.sent, [])
        self.run_check()  # 10 min
        self.run_check()  # 15 min
        self.assertEqual(len(self.telegram.sent), 1)
        self.assertIn("Jorah (the Gateway) has been down", self.texts()[0])
        self.assertIn("failed (failed)", self.texts()[0])
        self.assertEqual(self.telegram.sent[0]["chat_id"], "42")
        self.systemd.units["openclaw-gateway.service"] = {"ActiveState": "active", "SubState": "running"}
        self.run_check()
        self.assertEqual(len(self.telegram.sent), 2)
        self.assertIn("Back: Jorah (the Gateway) is up again, after 20 min down", self.texts()[1])
        self.run_check()
        self.assertEqual(len(self.telegram.sent), 2)

    def test_a_restart_shorter_than_the_threshold_is_quiet(self):
        self.run_check()
        self.ready = False  # the 6-hourly restart: up again within a minute
        self.run_check(minutes_later=1)
        self.ready = True
        self.run_check(minutes_later=4)
        self.ready = False
        self.run_check(minutes_later=5)
        self.ready = True
        self.run_check(minutes_later=5)
        self.assertEqual(self.telegram.sent, [])

    def test_not_ready_counts_as_down(self):
        self.ready = False
        for _ in range(4):
            self.run_check()
        self.assertEqual(len(self.telegram.sent), 1)
        self.assertIn("doesn't say ready", self.texts()[0])

    def test_reminds_every_six_hours_while_down(self):
        self.systemd.units["jorah-projects.service"] = {"Result": "exit-code"}
        for _ in range(int(13 * 60 / 5)):
            self.run_check()
        alerts = [t for t in self.texts() if "project runner" in t]
        self.assertEqual(len(alerts), 3)  # at 20 min, then 6 h and 12 h later
        self.assertIn("ended with exit-code", alerts[0])
        self.assertIn("still", alerts[1])

    def test_unreadable_systemd_counts_as_down(self):
        del self.systemd.units["openclaw-gateway.service"]
        for _ in range(4):
            self.run_check()
        self.assertIn("systemd didn't answer", self.texts()[0])

    def test_no_runner_installed_is_not_watched(self):
        self.systemd.units["jorah-projects.timer"] = {"LoadState": "not-found", "ActiveState": "inactive"}
        for _ in range(8):
            self.run_check()
        self.assertEqual(self.telegram.sent, [])

    def test_a_long_gap_is_reported_afterwards(self):
        self.run_check()
        self.run_check(minutes_later=8 * 60)
        self.assertEqual(len(self.telegram.sent), 1)
        self.assertIn("no check ran from", self.texts()[0])
        self.assertIn("(8 h 00 min)", self.texts()[0])

    def test_a_failed_send_is_retried_at_the_next_check(self):
        self.systemd.units["openclaw-gateway.service"] = {"ActiveState": "inactive", "SubState": "dead"}
        self.telegram.fail = True
        for _ in range(4):
            self.run_check()
        self.assertEqual(self.telegram.sent, [])
        self.assertIn("Telegram unreachable: URLError", self.lines)
        self.telegram.fail = False
        self.run_check()
        self.assertEqual(len(self.telegram.sent), 1)

    def test_without_a_token_it_watches_but_sends_nothing(self):
        self.systemd.units["openclaw-gateway.service"] = {"ActiveState": "failed", "SubState": "failed"}
        for _ in range(4):
            self.assertEqual(self.run_check(token=False), 0)
        self.assertEqual(self.telegram.sent, [])
        self.assertTrue(any("no bot token yet" in line for line in self.lines))
        self.assertEqual(self.run_check(command="test", token=False), 3)

    def test_the_token_never_reaches_the_log_or_the_state(self):
        self.systemd.units["openclaw-gateway.service"] = {"ActiveState": "failed", "SubState": "failed"}
        self.telegram.fail = True
        for _ in range(4):
            self.run_check()
        self.telegram.fail = False
        self.run_check()
        self.run_check(command="test")
        everything = "\n".join(self.lines) + (self.dir / "state.json").read_text()
        self.assertNotIn(TOKEN, everything)
        self.assertNotIn(TOKEN.split(":")[1], everything)

    def test_test_command_sends_one_message(self):
        self.assertEqual(self.run_check(command="test"), 0)
        self.assertEqual(len(self.telegram.sent), 1)
        self.assertIn("Test from Jorah's watchdog", self.texts()[0])


if __name__ == "__main__":
    unittest.main()
