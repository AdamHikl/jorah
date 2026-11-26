"""Tests for scripts/mac/jorah_hud_drive.py against a fake HUD socket. No HUD or Gateway needed."""

import contextlib
import datetime
import importlib.util
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("jorah_hud_drive", HERE.parent / "jorah_hud_drive.py")
drive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drive)

# The HUD's DriveRequest.keys (clients/mac-hud/Sources/HUDCore/Drive.swift): the CLI may send nothing else.
HUD_KEYS = {
    "status": {"cmd"}, "send": {"cmd", "text"}, "read": {"cmd", "limit"}, "cards": {"cmd"},
    "deny": {"cmd", "id"}, "wait": {"cmd", "seconds", "sent"},
}


class FakeHUD:
    """Answers each request with the next scripted reply for its command, and records requests."""

    def __init__(self, folder, replies):
        self.path = os.path.join(folder, "drive.sock")
        self.replies = {k: list(v) for k, v in replies.items()}
        self.requests = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(4)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                request = json.loads(data)
                self.requests.append(request)
                queue = self.replies.get(request["cmd"]) or [{"ok": False, "error": "unscripted"}]
                conn.sendall(json.dumps(queue.pop(0) if len(queue) > 1 else queue[0]).encode() + b"\n")

    def close(self):
        self.server.close()


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = drive.main(argv)
    return code, out.getvalue(), err.getvalue()


class RequestShapeTest(unittest.TestCase):
    def test_every_request_uses_only_the_huds_keys(self):
        for argv in (["status"], ["send", "hi"], ["read", "-n", "5"], ["cards"], ["deny", "plugin:x"],
                     ["wait", "--timeout", "30", "--sent", "hi"], ["wait"]):
            request = drive.request_for(drive.parser().parse_args(argv))
            self.assertLessEqual(set(request), HUD_KEYS[request["cmd"]], argv)

    def test_there_is_no_allow(self):
        for word in ("allow", "allow-once", "approve", "resolve", "pair", "power", "model"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                drive.parser().parse_args([word, "plugin:x"])
        self.assertNotIn("allow", json.dumps(drive.request_for(drive.parser().parse_args(["deny", "x"]))))

    def test_socket_path_follows_the_profile(self):
        home = "/Users/someone"
        self.assertEqual(drive.socket_path({}, home), f"{home}/Library/Application Support/JorahHUD/drive.sock")
        self.assertEqual(drive.socket_path({"JORAH_HUD_PROFILE": "test"}, home),
                         f"{home}/Library/Application Support/JorahHUD-test/drive.sock")
        for bad in ("../x", "a b", "x" * 21, ""):
            self.assertTrue(drive.socket_path({"JORAH_HUD_PROFILE": bad}, home).endswith("/JorahHUD/drive.sock"), bad)

    def test_clock_is_local_time_with_the_date_when_not_today(self):
        old = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Bratislava"
        time.tzset()
        try:
            now = datetime.datetime(2026, 11, 26, 18, 0).astimezone()
            self.assertEqual(drive.clock("2026-11-26T16:48:00Z", now), "17:48")
            self.assertEqual(drive.clock("2026-11-25T18:46:00Z", now), "25 Nov 19:46")
            for bad in (None, "", "yesterday", 5):
                self.assertEqual(drive.clock(bad, now), "--:--")
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()

    def test_after_sent(self):
        lines = [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "old"},
                 {"role": "user", "text": "[Tue 21:30] hi"}, {"role": "assistant", "text": "new"}]
        self.assertEqual([l["text"] for l in drive.after_sent(lines, "hi")], ["new"])
        self.assertEqual(drive.after_sent(lines, "nothing"), [])


class SocketTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(dir="/tmp" if os.path.isdir("/tmp") else None)
        self.hud = None

    def tearDown(self):
        if self.hud:
            self.hud.close()
        self.dir.cleanup()

    def start(self, replies):
        self.hud = FakeHUD(self.dir.name, replies)
        return ["--socket", self.hud.path]

    def test_off_when_the_socket_is_missing(self):
        code, _, err = run(["--socket", os.path.join(self.dir.name, "none.sock"), "status"])
        self.assertEqual(code, drive.FAILED)
        self.assertIn("drive mode is off", err)

    def test_send_prints_the_answer(self):
        base = self.start({
            "send": [{"ok": True, "sessionKey": "agent:main:main", "runId": "r1"}],
            "wait": [{"ok": True, "result": "done"}],
            "read": [{"ok": True, "lines": [
                {"role": "user", "text": "/jorah-status", "at": "2026-11-25T21:30:00Z", "viaDrive": True},
                {"role": "assistant", "text": "Careful mode: off.", "at": "2026-11-25T21:30:04Z"}]}],
        })
        code, out, _ = run(base + ["send", " /jorah-status "])
        self.assertEqual(code, drive.DONE)
        self.assertIn("Careful mode: off.", out)
        self.assertNotIn("/jorah-status", out)
        self.assertEqual(self.hud.requests[0], {"cmd": "send", "text": " /jorah-status "})
        self.assertEqual(self.hud.requests[1]["sent"], "/jorah-status")

    def test_send_stops_on_a_card(self):
        base = self.start({
            "send": [{"ok": True, "sessionKey": "agent:main:main"}],
            "wait": [{"ok": True, "result": "card", "cards": [{"id": "plugin:c1", "title": "t"}]}],
            "read": [{"ok": True, "lines": []}],
            "cards": [{"ok": True, "cards": [{"id": "plugin:c1", "title": "Jorah wants to change its own rules",
                                              "description": "edit AGENTS.md", "allowedDecisions": ["allow-once", "deny"],
                                              "canDeny": True, "secondsLeft": 290, "fields": []}]}],
        })
        code, out, _ = run(base + ["send", "add a line"])
        self.assertEqual(code, drive.CARD)
        self.assertIn("deny with: jorah_hud_drive.py deny plugin:c1", out)
        self.assertIn("only Adam can allow", out)

    def test_refusal_is_an_error(self):
        base = self.start({"deny": [{"ok": False, "error": "That card is still in its hold time."}]})
        code, _, err = run(base + ["deny", "plugin:c1"])
        self.assertEqual(code, drive.FAILED)
        self.assertIn("hold time", err)

    def test_unknown_cards_are_not_shown_as_none(self):
        base = self.start({"cards": [{"ok": False, "error": "approvals unavailable"}]})
        code, out, err = run(base + ["cards"])
        self.assertEqual(code, drive.FAILED)
        self.assertNotIn("No cards waiting", out)

    def test_wait_timeout(self):
        base = self.start({"wait": [{"ok": True, "result": "timeout"}]})
        code, _, _ = run(base + ["wait", "--timeout", "5"])
        self.assertEqual(code, drive.TIMEOUT)


if __name__ == "__main__":
    unittest.main()
