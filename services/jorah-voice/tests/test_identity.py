from array import array
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice import models
from jorah_voice.identity import (
    CENTROIDS_FILE,
    THRESHOLDS_FILE,
    SpeakerCheck,
    load_centroids,
    load_thresholds,
    save_centroids,
    save_thresholds,
)
from tools import calibrate, enrol


def write_wav(path, seconds, *, rate=16000, amplitude=0.25):
    total = int(seconds * rate)
    samples = array("h", [int(amplitude * 32767) if i % 2 == 0 else -int(amplitude * 32767) for i in range(total)])
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(samples.tobytes())


class FakeExtractor:
    sample_rate = 16000
    model_name = models.SPEAKER_MODEL

    def __init__(self, mapping, *, model_sha256="abc123", broken=False):
        self._mapping = mapping
        self.model_sha256 = model_sha256
        self._broken = broken

    def embed(self, samples, sample_rate):
        if self._broken:
            raise RuntimeError("boom")
        if callable(self._mapping):
            return self._mapping(samples, sample_rate)
        # Pick embedding by average absolute amplitude for clip differentiation.
        avg = sum(abs(x) for x in samples) / max(1, len(samples))
        for threshold, vec in self._mapping:
            if avg <= threshold:
                return vec
        return self._mapping[-1][1]


class ModelPinning(unittest.TestCase):
    def test_ensure_refuses_unpinned_speaker_model_even_if_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / models.SPEAKER_MODEL).write_bytes(b"fake-onnx")
            self.assertIsNone(models.EXPECTED_SHA256)
            with self.assertRaises(RuntimeError):
                models.ensure(root)
            with self.assertRaises(RuntimeError):
                models.ensure_speaker(root)


class IdentityVerdicts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vp = Path(self.tmp.name) / "voiceprint"
        self.sha = "deadbeef"
        save_centroids(self.vp, {"mac": [1.0, 0.0], "airpods": [0.0, 1.0]}, models.SPEAKER_MODEL, self.sha)
        save_thresholds(self.vp, 0.8, 0.4, "2026-11-22T00:00:00Z", {"genuine": 20, "impostor": 300})

    def tearDown(self):
        self.tmp.cleanup()

    def test_modes_are_700_and_600(self):
        self.assertEqual(stat.S_IMODE(self.vp.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.vp / CENTROIDS_FILE).stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.vp / THRESHOLDS_FILE).stat().st_mode), 0o600)

    def test_cosine_against_multiple_devices_highest_counts(self):
        # AirPods centroid [0, 1] matches [0.1, 0.995] (~0.995 >= 0.8 -> adam)
        ext = FakeExtractor(lambda _s, _r: [0.1, 0.995], model_sha256=self.sha)
        chk = SpeakerCheck(self.vp, extractor=ext)
        v = chk.verdict([0.1] * 24000, 16000)  # 1.5s
        self.assertEqual(v.kind, "adam")
        self.assertAlmostEqual(v.speech_seconds, 1.5)
        self.assertEqual(v.bucket, ">=0.7")
        self.assertFalse(hasattr(v, "score"))
        self.assertFalse(hasattr(v, "embedding"))

    def test_thresholds_between_and_low_and_short_speech(self):
        # Between 0.4 and 0.8 -> unsure (cos([0.6, 0.8], [1, 0]) = 0.6)
        ext_mid = FakeExtractor(lambda _s, _r: [0.6, 0.8] if False else [0.6, 0.0], model_sha256=self.sha)
        # Note: [0.6, 0.0] normalizes to [1, 0], so use [0.6, 0.8] vs [1, 0] and [0, 1]: max(0.6, 0.8)=0.8.
        # Use [0.65, 0.65] -> unit [0.707, 0.707] -> max cos ~0.707 (between 0.4 and 0.8), >=0.7 bucket.
        ext_mid = FakeExtractor(lambda _s, _r: [0.65, 0.65], model_sha256=self.sha)
        v_mid = SpeakerCheck(self.vp, extractor=ext_mid).verdict([0.1] * 24000, 16000)
        self.assertEqual(v_mid.kind, "unsure")
        self.assertEqual(v_mid.bucket, ">=0.7")

        # 3D-like vector orthogonal / negative to both -> <= 0.4 -> someone_else
        save_centroids(self.vp, {"mac": [1.0, 0.0, 0.0]}, models.SPEAKER_MODEL, self.sha)
        ext_low = FakeExtractor(lambda _s, _r: [0.2, 0.98, 0.0], model_sha256=self.sha)  # cos ~0.2 -> <0.3
        v_low = SpeakerCheck(self.vp, extractor=ext_low).verdict([0.1] * 24000, 16000)
        self.assertEqual(v_low.kind, "someone_else")
        self.assertEqual(v_low.bucket, "<0.3")

        # Under 1.2 s -> unsure even if embedding would match Adam
        ext_adam = FakeExtractor(lambda _s, _r: [1.0, 0.0, 0.0], model_sha256=self.sha)
        v_short = SpeakerCheck(self.vp, extractor=ext_adam).verdict([0.1] * 16000, 16000)  # 1.0s
        self.assertEqual(v_short.kind, "unsure")
        self.assertIsNone(v_short.bucket)

    def test_missing_corrupt_hash_mismatch_or_exception_are_unavailable(self):
        ext_ok = FakeExtractor(lambda _s, _r: [1.0, 0.0], model_sha256=self.sha)
        # Missing extractor
        self.assertEqual(SpeakerCheck(self.vp, extractor=None).verdict([0.1] * 24000, 16000).kind, "unavailable")
        # Model hash mismatch
        ext_wrong = FakeExtractor(lambda _s, _r: [1.0, 0.0], model_sha256="otherhash")
        self.assertEqual(SpeakerCheck(self.vp, extractor=ext_wrong).verdict([0.1] * 24000, 16000).kind, "unavailable")
        # Extractor throws
        ext_err = FakeExtractor(lambda _s, _r: [1.0, 0.0], model_sha256=self.sha, broken=True)
        self.assertEqual(SpeakerCheck(self.vp, extractor=ext_err).verdict([0.1] * 24000, 16000).kind, "unavailable")
        # Corrupt thresholds
        (self.vp / THRESHOLDS_FILE).write_text("{bad json")
        self.assertEqual(SpeakerCheck(self.vp, extractor=ext_ok).verdict([0.1] * 24000, 16000).kind, "unavailable")
        # Missing centroids
        (self.vp / CENTROIDS_FILE).unlink()
        self.assertEqual(SpeakerCheck(self.vp, extractor=ext_ok).verdict([0.1] * 24000, 16000).kind, "unavailable")


class EnrolAndCalibrate(unittest.TestCase):
    def test_enrol_chunks_resamples_and_writes_600_centroid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vp = root / "vp"
            wav = root / "mac.wav"
            # 10 s at 24 kHz -> resampled to 16 kHz, split into 3-5 s chunks.
            write_wav(wav, 10.0, rate=24000, amplitude=0.3)
            seen_lengths = []

            def embed(samples, rate):
                self.assertEqual(rate, 16000)
                seen_lengths.append(len(samples) / rate)
                return [3.0, 4.0]

            ext = FakeExtractor(embed, model_sha256="sha-model")
            stats = enrol.enrol_device("mac", [wav], voiceprint_dir=vp, extractor=ext)
            self.assertEqual(stats["device"], "mac")
            self.assertEqual(stats["files"], 1)
            self.assertGreaterEqual(len(seen_lengths), 2)
            for length in seen_lengths:
                self.assertGreaterEqual(length, 3.0)
                self.assertLessEqual(length, 5.0)
            loaded = load_centroids(vp)
            self.assertEqual(loaded["model_sha256"], "sha-model")
            self.assertAlmostEqual(loaded["centroids"]["mac"][0], 0.6, places=5)
            self.assertAlmostEqual(loaded["centroids"]["mac"][1], 0.8, places=5)

    def test_m4a_without_ffmpeg_gives_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            m4a = Path(tmp) / "clip.m4a"
            m4a.write_bytes(b"not-real")
            with patch("tools.enrol.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    enrol.decode_audio(m4a)
                self.assertIn("ffmpeg", str(ctx.exception))

    def test_calibrate_pass_writes_and_fail_does_not_unless_write_anyway(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vp = root / "vp"
            g_dir = root / "genuine"
            i_dir = root / "impostor"
            g_dir.mkdir()
            i_dir.mkdir()

            # Genuine clips have amplitude ~0.4 -> embedding [1.0, 0.0] (score 1.0)
            # Impostor clips have amplitude ~0.1 -> embedding [0.2, 0.98] (score ~0.2)
            for idx in range(20):
                write_wav(g_dir / f"g{idx}.wav", 2.0, amplitude=0.4)
            for idx in range(10):
                write_wav(i_dir / f"i{idx}.wav", 2.0, amplitude=0.1)

            save_centroids(vp, {"mac": [1.0, 0.0]}, models.SPEAKER_MODEL, "sha-cal")
            ext = FakeExtractor([(0.2, [0.2, 0.979795897]), (1.0, [1.0, 0.0])], model_sha256="sha-cal")

            res = calibrate.calibrate(g_dir, i_dir, voiceprint_dir=vp, extractor=ext)
            self.assertEqual(res["status"], "PASS")
            self.assertTrue(res["wrote"])
            self.assertEqual(res["counts"]["false_accepts"], 0)
            self.assertEqual(res["counts"]["false_rejects"], 0)
            loaded = load_thresholds(vp)
            self.assertGreater(loaded["high"], 0.2)
            self.assertLessEqual(loaded["low"], loaded["high"])

            # Now simulate high false-reject genuine clips -> FAIL, must not overwrite unless --write-anyway.
            (vp / THRESHOLDS_FILE).unlink()
            # Make 2 of 20 genuine clips score 0.1 (< high), exceeding 1/20 (5%)
            write_wav(g_dir / "g0.wav", 2.0, amplitude=0.1)
            write_wav(g_dir / "g1.wav", 2.0, amplitude=0.1)
            res_fail = calibrate.calibrate(g_dir, i_dir, voiceprint_dir=vp, extractor=ext)
            self.assertEqual(res_fail["status"], "FAIL")
            self.assertFalse(res_fail["wrote"])
            self.assertFalse((vp / THRESHOLDS_FILE).exists())

            res_forced = calibrate.calibrate(g_dir, i_dir, voiceprint_dir=vp, extractor=ext, write_anyway=True)
            self.assertEqual(res_forced["status"], "FAIL")
            self.assertTrue(res_forced["wrote"])
            self.assertTrue((vp / THRESHOLDS_FILE).exists())


if __name__ == "__main__":
    unittest.main()
