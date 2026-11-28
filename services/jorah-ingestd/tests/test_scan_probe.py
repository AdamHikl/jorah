"""The scanner and settle check, take names, probe reports, color classes and times."""
import os
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from world import Root, video_report

from jorah_ingestd import config, probe, scan


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.root = Root()
        self.addCleanup(self.root.cleanup)

    def test_kinds_junk_and_links_are_never_followed(self):
        folder = self.root.take("Take 1", {"A001.mov": b"v", "A001.wav": b"a", "A001.json": b"{}",
                                           "notes.txt": b"n", ".DS_Store": b"j", "._A001.mov": b"j",
                                           ".Spotlight-V100/store.db": b"j",
                                           "A001.mov:Zone.Identifier": b"j"})
        os.symlink("/etc/passwd", folder / "link.mov")
        os.symlink("/etc", folder / "linkdir")
        kinds = {e.rel: e.kind for e in scan.walk(folder)}
        self.assertEqual(kinds["A001.mov"], "video")
        self.assertEqual(kinds["A001.wav"], "audio")
        self.assertEqual(kinds["A001.json"], "sidecar")
        self.assertEqual(kinds["notes.txt"], "other")
        for junk in (".DS_Store", "._A001.mov", ".Spotlight-V100/store.db", "A001.mov:Zone.Identifier"):
            self.assertEqual(kinds[junk], "junk", junk)
        self.assertEqual(kinds["link.mov"], "symlink")
        self.assertEqual(kinds["linkdir"], "symlink")
        self.assertNotIn("linkdir/passwd", kinds)

    def test_groups_folders_loose_files_and_a_copied_trash_folder(self):
        self.root.take("Take 1", {"a.mov": b"v"})
        self.root.take(None, {"b.mov": b"v"})
        self.root.take(".Trashes", {"501/old.mov": b"v"})
        g = scan.groups(self.root.cfg.incoming)
        self.assertEqual(set(g), {"dir:Take 1", "dir:.Trashes", "loose"})
        self.assertEqual([e.rel for e in g["loose"][1]], ["b.mov"])
        self.assertFalse(scan.has_content(g["dir:.Trashes"][1]))

    def test_settler_waits_for_files_to_hold_still(self):
        clock = Clock()
        s = scan.Settler(30, clock)
        folder = self.root.take("t", {"a.mov": b"1"})
        found = lambda: scan.groups(self.root.cfg.incoming)  # noqa: E731
        self.assertEqual(s.update(found()), [])
        clock.t += 29
        self.assertEqual(s.update(found()), [])
        (folder / "a.mov").write_bytes(b"12")  # still copying
        clock.t += 31
        self.assertEqual(s.update(found()), [])
        clock.t += 30
        g = found()
        self.assertEqual(s.update(g), ["dir:t"])
        s.mark_handled("dir:t", g["dir:t"][1])
        clock.t += 30
        self.assertEqual(s.update(found()), [])
        (folder / "a.mov").unlink()
        folder.rmdir()
        s.update(found())
        self.assertEqual(s.handled, {})

    def test_take_id(self):
        now = datetime(2026, 11, 28, 9, 5, 7, tzinfo=timezone.utc)
        self.assertEqual(scan.take_id("dir:OpenClaw Security / take 1!", now), "openclaw-security-take-1")
        self.assertEqual(scan.take_id("dir:...", now), "take")
        self.assertEqual(scan.take_id("loose", now), "loose-20261128-090507")


class ProbeTest(unittest.TestCase):
    def test_summary_drops_location_and_marks_unknowns(self):
        data = video_report(duration=12.5)
        data["streams"][0]["side_data_list"] = [{"rotation": -90}]
        data["format"]["bit_rate"] = "N/A"
        rep = probe.summarize(data)
        self.assertNotIn("com.apple.quicktime.location.ISO6709", rep["tags"])
        self.assertEqual(rep["duration_s"], 12.5)
        self.assertEqual(rep["bit_rate"], probe.UNKNOWN)
        v = rep["video"]
        self.assertEqual((v["codec"], v["width"], v["fps"], v["bit_depth"]), ("hevc", 3840, 30.0, 10))
        self.assertEqual(v["color_transfer"], probe.UNKNOWN)
        self.assertEqual(v["rotation"], -90)
        self.assertEqual(rep["audio"][0]["sample_rate"], 48000)
        empty = probe.summarize({})
        self.assertEqual((empty["duration_s"], empty["video"]), (probe.UNKNOWN, None))

    def test_color_classes(self):
        rep = probe.summarize(video_report())
        self.assertEqual(probe.classify_color(rep, "apple_log"), {"value": "apple_log", "basis": "assumed"})
        rep["tags"]["com.apple.proapps.image.colorspace"] = "Apple Log"
        self.assertEqual(probe.classify_color(rep, "rec709")["basis"], "tag")
        hlg = probe.summarize(video_report(color_transfer="arib-std-b67"))
        self.assertEqual(probe.classify_color(hlg, "apple_log"), {"value": "hlg", "basis": "metadata"})
        sdr = probe.summarize(video_report(color_transfer="bt709", color_primaries="bt709"))
        self.assertEqual(probe.classify_color(sdr, "apple_log")["value"], "rec709")

    def test_parse_time(self):
        utc = timezone.utc
        self.assertEqual(probe.parse_time("2026-11-28T10:00:00.000000Z"),
                         datetime(2026, 11, 28, 10, 0, tzinfo=utc))
        self.assertEqual(probe.parse_time("2026-11-28T11:00:00+0100"),
                         datetime(2026, 11, 28, 10, 0, tzinfo=utc))
        self.assertIsNone(probe.parse_time("2026-11-28T11:00:00"))
        self.assertEqual(probe.parse_time("2026-11-28T11:00:00", ZoneInfo("Europe/Bratislava")),
                         datetime(2026, 11, 28, 10, 0, tzinfo=utc))
        self.assertIsNone(probe.parse_time("yesterday"))


class ConfigTest(unittest.TestCase):
    def test_refuses_unknown_keys_and_bad_values(self):
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"settle": 30}, f)
        self.addCleanup(os.unlink, f.name)
        with self.assertRaises(ValueError):
            config.load(f.name)
        with self.assertRaises(ValueError):
            config.load(overrides={"default_color": "hdr"})
        with self.assertRaises(ValueError):
            config.load(overrides={"settle_s": 1})
        example = os.path.join(os.path.dirname(__file__), "..", "ingest.example.json")
        self.assertEqual(config.load(example).default_color, "apple_log")


if __name__ == "__main__":
    unittest.main()
