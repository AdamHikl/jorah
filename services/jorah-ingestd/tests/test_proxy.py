"""Proxy commands, the LUT pin, the NVENC fallback, and (where ffmpeg exists) a real encode."""
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from world import Root

from jorah_ingestd import config, probe, proxy

IDENTITY_LUT = "LUT_3D_SIZE 2\n" + "".join(
    f"{r} {g} {b}\n" for b in (0, 1) for g in (0, 1) for r in (0, 1))


class LutTest(unittest.TestCase):
    def setUp(self):
        self.root = Root()
        self.addCleanup(self.root.cleanup)
        self.lut = Path(self.root.cfg.lut_path)

    def state(self, **kw):
        values = dict(self.root.cfg.values, **kw)
        return proxy.lut_state(config.load(overrides=values))[0]

    def test_states(self):
        self.assertEqual(self.state(), "missing")
        self.lut.write_text(IDENTITY_LUT)
        self.assertEqual(self.state(), "unpinned")
        sha = hashlib.sha256(IDENTITY_LUT.encode()).hexdigest()
        self.assertEqual(self.state(lut_sha256=sha), "ok")
        self.assertEqual(self.state(lut_sha256="0" * 64), "mismatch")
        self.assertEqual(self.state(lut_path="/srv/a b.cube"), "bad_path")
        self.assertEqual(self.state(lut_path="/srv/a:b.cube"), "bad_path")
        self.lut.write_text("TITLE x\n")
        self.assertEqual(self.state(lut_sha256=hashlib.sha256(b"TITLE x\n").hexdigest()), "bad_file")


class CommandTest(unittest.TestCase):
    video = {"color_space": "bt2020nc", "color_range": "tv"}

    def test_apple_log_goes_through_the_lut_into_rec709(self):
        cmd = proxy.build_cmd("/usr/bin/ffmpeg", "/s/a.mov", "/p/a.mp4", "apple_log", self.video,
                              1080, "h264_nvenc", "/srv/jorah-media/luts/x.cube")
        vf = cmd[cmd.index("-vf") + 1]
        self.assertIn("in_color_matrix=bt2020", vf)
        self.assertIn("lut3d=file=/srv/jorah-media/luts/x.cube:interp=tetrahedral", vf)
        self.assertLess(vf.index("lut3d"), vf.index("out_color_matrix=bt709"))
        self.assertIn("h264_nvenc", cmd)
        self.assertEqual(cmd[cmd.index("-colorspace") + 1], "bt709")
        self.assertIn("-nostdin", cmd)
        with self.assertRaises(ValueError):
            proxy.build_cmd("ffmpeg", "a", "b", "apple_log", self.video, 1080, "h264_nvenc")

    def test_rec709_has_no_lut(self):
        cmd = proxy.build_cmd("ffmpeg", "a", "b", "rec709", {}, 1080, "libx264")
        self.assertNotIn("lut3d", cmd[cmd.index("-vf") + 1])
        self.assertIn("libx264", cmd)


class MakeTest(unittest.TestCase):
    def setUp(self):
        self.root = Root(proxy_encoder="h264_nvenc")
        self.addCleanup(self.root.cleanup)
        self.dst = self.root.dir / "proxies" / "t" / "a.proxy.mp4"

    def test_waits_for_the_lut(self):
        rec = proxy.make(self.root.cfg, Path("/x.mov"), self.dst, "apple_log", {}, 10.0)
        self.assertEqual(rec["status"], "waiting")
        self.assertIn("no LUT", rec["reason"])

    def test_falls_back_to_libx264_and_says_why(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if "h264_nvenc" in cmd:
                return subprocess.CompletedProcess(cmd, 1, b"", b"No NVENC capable devices found")
            Path(cmd[-1]).write_bytes(b"mp4")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        with mock.patch.object(proxy.subprocess, "run", fake_run):
            rec = proxy.make(self.root.cfg, Path("/x.mov"), self.dst, "rec709", {}, 10.0)
        self.assertEqual(rec["status"], "done")
        self.assertEqual(rec["encoder"], "libx264")
        self.assertIn("No NVENC", rec["fallback_because"][0])
        self.assertEqual(self.dst.read_bytes(), b"mp4")
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(p.name.startswith(".") for p in self.dst.parent.iterdir()))

    def test_both_failing_is_failed(self):
        bad = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, b"", b"boom")  # noqa: E731
        with mock.patch.object(proxy.subprocess, "run", bad):
            rec = proxy.make(self.root.cfg, Path("/x.mov"), self.dst, "rec709", {}, 10.0)
        self.assertEqual(rec["status"], "failed")
        self.assertFalse(self.dst.exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is not installed")
class RealFfmpegTest(unittest.TestCase):
    """Runs on the PC: a 10-bit BT.2020 clip through the real filter chain and an identity LUT."""

    def test_apple_log_proxy_encodes(self):
        root = Root(ffmpeg=shutil.which("ffmpeg"), ffprobe=shutil.which("ffprobe"),
                    proxy_encoder="h264_nvenc")
        self.addCleanup(root.cleanup)
        Path(root.cfg.lut_path).write_text(IDENTITY_LUT)
        cfg = config.load(overrides=dict(root.cfg.values, lut_sha256=hashlib.sha256(
            IDENTITY_LUT.encode()).hexdigest()))
        src = root.dir / "src.mov"
        codec = ["-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-x265-params", "log-level=error"]
        probe_enc = subprocess.run([cfg.ffmpeg, "-hide_banner", "-encoders"], capture_output=True)
        if b"libx265" not in probe_enc.stdout:
            codec = ["-c:v", "libx264", "-pix_fmt", "yuv420p10le"]
        subprocess.run([cfg.ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=s=1280x720:r=30:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2",
                        *codec, "-color_primaries", "bt2020", "-colorspace", "bt2020nc",
                        "-color_trc", "bt709", "-c:a", "aac", "-shortest", str(src)], check=True)
        data, err = probe.run_ffprobe(cfg.ffprobe, src)
        rep = probe.summarize(data)
        dst = root.dir / "proxies" / "t" / "src.proxy.mp4"
        rec = proxy.make(cfg, src, dst, "apple_log", rep["video"], rep["duration_s"])
        self.assertEqual(rec["status"], "done", rec)
        out = probe.summarize(probe.run_ffprobe(cfg.ffprobe, dst)[0])
        self.assertEqual((out["video"]["height"], out["video"]["codec"]), (1080, "h264"))
        self.assertEqual(out["video"]["color_primaries"], "bt709")
        self.assertEqual(out["audio"][0]["codec"], "aac")
        print(json.dumps({"encoder": rec["encoder"], "fallback": rec.get("fallback_because")}))


if __name__ == "__main__":
    unittest.main()
