"""A take from incoming/ to a ready spool entry, with ffprobe, the audio decoder and the encoder faked."""
import hashlib
import json
import os
import stat
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from world import RATE, Root, np, other_mic, speech, video_report, wav_report

from jorah_ingestd import cli, proxy, scan, spool

CLIP, WAV = b"iphone hevc bytes", b"mac wav bytes"


class Fakes:
    """ffprobe answers by file name; the decoder hands back synthetic audio; ffmpeg writes a file."""

    def __init__(self, reports):
        self.reports = reports
        self.encodes = []
        wav = speech(120, seed=7) if np is not None else None
        self.audio = {"A001.mov": other_mic(wav[4 * RATE:99 * RATE]) if np is not None else None,
                      "A001.wav": wav}

    def ffprobe(self, ffprobe, path, timeout=120):
        rep = self.reports.get(Path(path).name)
        return (rep, None) if rep else (None, "ffprobe: Invalid data found when processing input")

    def decode(self, path):
        return self.audio.get(Path(path).name)

    def run(self, cmd, **kw):
        self.encodes.append(cmd)
        Path(cmd[-1]).write_bytes(b"proxy")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Root(default_color="rec709")
        self.addCleanup(self.root.cleanup)
        self.cfg = self.root.cfg
        self.fakes = Fakes({"A001.mov": video_report(95.0, "2026-11-28T10:00:04Z",
                                                     color_transfer="bt709", color_primaries="bt709"),
                            "A001.wav": wav_report(120.0, "2026-11-28", "11-00-00")})
        p = mock.patch.object(spool.probe, "run_ffprobe", self.fakes.ffprobe)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(proxy.subprocess, "run", self.fakes.run)
        p.start()
        self.addCleanup(p.stop)

    def ingest(self, name="Take 1", key=None):
        key = key or f"dir:{name}"
        folder, entries = scan.groups(self.cfg.incoming)[key]
        return spool.ingest_group(self.cfg, key, folder, entries, log=lambda m: None,
                                  decode=self.fakes.decode)

    def manifest(self, tid="take-1"):
        return spool.read_manifest(self.cfg.spool / tid)


class SpoolTest(Base):
    @unittest.skipIf(np is None, "numpy is missing")
    def test_a_take_lands_read_only_hashed_paired_and_proxied(self):
        self.root.take("Take 1", {"A001.mov": CLIP, "A001.wav": WAV, ".DS_Store": b"j",
                                  "._A001.mov": b"j", "A001.mov:Zone.Identifier": b"j"})
        res = self.ingest()
        self.assertEqual(res["status"], "working", res)
        media = self.cfg.spool / "take-1" / "media"
        self.assertEqual(stat.S_IMODE(os.stat(media / "A001.mov").st_mode), 0o444)
        man = self.manifest()
        self.assertEqual(man["schema"], "jorah-media/take@1")
        self.assertEqual(man["files"]["A001.mov"]["sha256"], hashlib.sha256(CLIP).hexdigest())
        self.assertEqual(sorted(man["ignored"]), sorted([".DS_Store", "._A001.mov", "A001.mov:Zone.Identifier"]))
        self.assertFalse((self.cfg.incoming / "Take 1").exists())
        self.assertEqual(man["files"]["A001.mov"]["color"], {"value": "rec709", "basis": "metadata"})
        self.assertNotIn("com.apple.quicktime.location.ISO6709", json.dumps(man))
        [p] = man["pairs"]
        self.assertEqual((p["status"], p["wav"]), ("ok", "A001.wav"), p)
        self.assertAlmostEqual(p["offset_s"], 4.0, delta=0.001)
        self.assertIsInstance(p["drift_ms"], float)
        self.assertEqual(man["questions"], [])
        self.assertEqual(spool.next_proxy_job(self.cfg), (self.cfg.spool / "take-1", "A001.mov"))
        rec = spool.run_proxy(self.cfg, self.cfg.spool / "take-1", "A001.mov", log=lambda m: None)
        self.assertEqual(rec["status"], "done")
        self.assertEqual(self.manifest()["status"], "ready")
        self.assertIsNone(spool.next_proxy_job(self.cfg))
        self.assertTrue((self.cfg.proxies / "take-1" / "A001.proxy.mp4").exists())

    def test_low_disk_leaves_the_files_and_retries(self):
        self.root.take("Take 1", {"A001.mov": CLIP})
        with mock.patch.object(spool, "free_bytes", return_value=len(CLIP)):
            res = self.ingest()
        self.assertEqual(res["status"], "refused")
        self.assertIn("free space", res["message"])
        self.assertTrue((self.cfg.incoming / "Take 1" / "A001.mov").exists())
        self.assertFalse((self.cfg.spool / "take-1").exists())

    def test_same_name_new_bytes_is_a_question_and_same_bytes_is_dropped(self):
        self.root.take("Take 1", {"A001.wav": WAV})
        self.ingest()
        self.root.take("Take 1", {"A001.wav": WAV})
        self.ingest()
        self.assertFalse((self.cfg.incoming / "Take 1").exists())
        self.root.take("Take 1", {"A001.wav": b"different"})
        self.ingest()
        man = self.manifest()
        self.assertTrue(any("different content" in q for q in man["questions"]), man["questions"])
        self.assertTrue((self.cfg.incoming / "Take 1" / "A001.wav").exists())
        self.assertEqual(man["files"]["A001.wav"]["sha256"], hashlib.sha256(WAV).hexdigest())

    def test_a_file_that_changes_while_copied_is_not_taken(self):
        folder = self.root.take("Take 1", {"A001.wav": WAV})
        real = spool.copy_hash

        def copy_then_touch(src, dst, chunk=8 << 20):
            out = real(src, dst, chunk)
            with open(src, "ab") as f:
                f.write(b"more")
            return out

        with mock.patch.object(spool, "copy_hash", copy_then_touch):
            res = self.ingest()
        self.assertEqual(res["status"], "settling")
        self.assertTrue((folder / "A001.wav").exists())
        self.assertEqual(list((self.cfg.spool / "take-1" / "media").iterdir()), [])

    def test_originals_the_service_cannot_remove_are_reported(self):
        folder = self.root.take("Take 1", {"A001.wav": WAV})
        os.chmod(folder, 0o555)
        self.ingest()
        man = self.manifest()
        self.assertTrue(any(n.startswith("originals left") for n in man["notes"]), man["notes"])
        self.assertIn("A001.wav", man["files"])

    def test_symlinks_are_refused_and_unreadable_clips_ask(self):
        folder = self.root.take("Take 1", {"B002.mov": b"broken"})
        os.symlink("/etc/hosts", folder / "evil.mov")
        self.ingest()
        man = self.manifest()
        self.assertEqual(man["refused"], [{"name": "evil.mov", "kind": "symlink"}])
        self.assertFalse((self.cfg.spool / "take-1" / "media" / "evil.mov").exists())
        self.assertTrue(any("B002.mov: unreadable" in q for q in man["questions"]), man["questions"])
        # A fresh copy with different bytes replaces the unreadable one instead of conflicting.
        os.unlink(folder / "evil.mov")
        self.root.take("Take 1", {"B002.mov": b"fixed copy"})
        self.ingest()
        man = self.manifest()
        self.assertEqual(man["files"]["B002.mov"]["sha256"], hashlib.sha256(b"fixed copy").hexdigest())

    def test_apple_log_waits_for_a_pinned_lut(self):
        self.fakes.reports["A001.mov"] = video_report(70.0, audio=False)
        self.root.cfg.values["default_color"] = "apple_log"
        self.root.take("Take 1", {"A001.mov": CLIP})
        self.ingest()
        job = spool.next_proxy_job(self.cfg)
        rec = spool.run_proxy(self.cfg, *job, log=lambda m: None)
        self.assertEqual(rec["status"], "waiting")
        self.assertIsNone(spool.next_proxy_job(self.cfg))
        Path(self.cfg.lut_path).write_text("LUT_3D_SIZE 2\n" + "0 0 0\n" * 8)
        self.cfg.values["lut_sha256"] = proxy.sha256_file(self.cfg.lut_path)
        self.assertEqual(spool.next_proxy_job(self.cfg), job)
        rec = spool.run_proxy(self.cfg, *job, log=lambda m: None)
        self.assertEqual(rec["lut"], self.cfg.lut_path)
        self.assertIn("lut3d", " ".join(self.fakes.encodes[-1]))


class RunnerTest(Base):
    def test_the_loop_settles_ingests_and_writes_status(self):
        t = [0.0]
        quiet = mock.patch.object(cli, "log", lambda m: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        r = cli.Runner(self.cfg, clock=lambda: t[0], decode=self.fakes.decode)
        self.root.take("Take 1", {"A001.wav": WAV})
        r.write_status(r.ingest())
        status = json.loads((self.cfg.state / "status.json").read_text())
        self.assertEqual(status["incoming"], {"dir:Take 1": "settling"})
        t[0] += self.cfg.settle_s
        r.write_status(r.ingest())
        status = json.loads((self.cfg.state / "status.json").read_text())
        self.assertEqual(status["incoming"], {})
        self.assertEqual([x["take"] for x in status["takes"]], ["take-1"])
        self.assertIsInstance(status["free_bytes"], int)
        r.ingest()  # the folder is gone, so nothing is handled any more
        self.assertEqual(json.loads((self.cfg.state / "handled.json").read_text()), {})


if __name__ == "__main__":
    unittest.main()
