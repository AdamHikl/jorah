"""Sound sync on speech-like audio through two different mics, drift, and pairing clips to WAVs."""
import unittest

from world import RATE, Root, np, other_mic, speech, video_report, wav_report

from jorah_ingestd import pair, probe, sync


@unittest.skipIf(np is None, "numpy is missing")
class SyncTest(unittest.TestCase):
    def setUp(self):
        self.wav = speech(120, seed=7)

    def clip_at(self, offset_s, seconds=40, seed=3):
        """The iPhone's scratch audio of the same speech, starting offset_s into the WAV."""
        a = int(round(offset_s * RATE))
        n = int(seconds * RATE)
        if a >= 0:
            src = self.wav[a:a + n]
        else:
            src = np.concatenate([speech(-offset_s, seed=11) * 0.2, self.wav[:n + a]])
        return other_mic(src, seed=seed)

    def test_finds_the_offset_within_a_millisecond(self):
        for offset in (0.5, 3.0, 47.25, -0.5):
            r = sync.correlate(self.clip_at(offset), self.wav, RATE)
            self.assertAlmostEqual(r["offset_s"], offset, delta=0.001, msg=offset)
            self.assertTrue(sync.trusted(r, 1.5, 10.0), (offset, r))

    def test_unrelated_audio_is_not_trusted(self):
        r = sync.correlate(other_mic(speech(40, seed=99)), self.wav, RATE)
        self.assertFalse(sync.trusted(r, 1.5, 10.0), r)

    def test_too_short_or_outside_the_window(self):
        self.assertIsNone(sync.correlate(np.zeros(100), self.wav, RATE)["offset_s"])
        r = sync.correlate(self.clip_at(3.0), self.wav, RATE, lag_min_s=200, lag_max_s=300)
        self.assertIsNone(r["offset_s"])

    def test_drift(self):
        clip = self.clip_at(2.0, seconds=100)
        self.assertLess(abs(sync.drift_ms(clip, self.wav, RATE, 2.0)), 1.0)
        # A clock 100 ppm fast: over the 90 s between the 10 s windows' starts, 9 ms.
        t = 2.0 + np.arange(100 * RATE) / RATE * (1 + 1e-4)
        fast = other_mic(np.interp(t * RATE, np.arange(len(self.wav)), self.wav))
        r = sync.correlate(fast, self.wav, RATE)
        d = sync.drift_ms(fast, self.wav, RATE, r["offset_s"])
        self.assertAlmostEqual(d, 9.0, delta=1.0)
        self.assertIsNone(sync.drift_ms(clip[:RATE * 25], self.wav, RATE, 2.0))  # under 30 s


@unittest.skipIf(np is None, "numpy is missing")
class PairTest(unittest.TestCase):
    def setUp(self):
        self.root = Root()
        self.addCleanup(self.root.cleanup)
        self.wav_a = speech(90, seed=7)
        self.wav_b = speech(90, seed=8)
        self.audio = {"A001.mov": other_mic(self.wav_a[4 * RATE:44 * RATE]),
                      "mac-1.wav": self.wav_a, "mac-2.wav": self.wav_b}

    def entry(self, name, report, mtime=None):
        return {"name": name, "probe": probe.summarize(report), "source_mtime": mtime}

    def pair(self, videos, audios, sidecars=None):
        return pair.pair_take(videos, audios, sidecars or {}, self.root.cfg,
                              lambda p: self.audio.get(p), lambda r: r)

    def test_picks_the_right_wav_by_time_then_peak(self):
        clip = self.entry("A001.mov", video_report(40.0, "2026-11-28T10:00:04Z"))
        a = self.entry("mac-1.wav", wav_report(90.0, "2026-11-28", "11-00-00"))  # local time, CET
        b = self.entry("mac-2.wav", wav_report(90.0, "2026-11-28", "11-30-00"))
        [res] = self.pair([clip], [b, a])
        self.assertEqual(res["status"], "ok", res)
        self.assertEqual(res["wav"], "mac-1.wav")
        self.assertAlmostEqual(res["offset_s"], 4.0, delta=0.001)
        self.assertTrue(res["picked_by_time"])
        self.assertEqual(res["time_basis"], {"clip": "metadata", "wav": "bwf"})
        self.assertAlmostEqual(res["time_offset_s"], 4.0, delta=0.01)
        self.assertLess(abs(res["drift_ms"]), 1.0)

    def test_sidecar_start_time_wins(self):
        a = self.entry("mac-1.wav", wav_report(90.0, "2026-11-28", "08-00-00"))
        side = {"mac-1.json": {"audio_file": "mac-1.wav", "start_time": "2026-11-28T10:00:00Z"}}
        self.assertEqual(pair.wav_start(a, side, "Europe/Bratislava")[1], "sidecar")

    def test_questions_instead_of_guesses(self):
        clip = self.entry("A001.mov", video_report(40.0))
        self.assertIn("no WAV", self.pair([clip], [])[0]["reason"])
        silent = self.entry("A001.mov", video_report(40.0, audio=False))
        self.assertIn("no scratch audio", self.pair([silent], [self.entry("mac-1.wav", wav_report())])[0]["reason"])
        wrong = self.entry("mac-2.wav", wav_report(90.0, "2026-11-28", "11-00-00"))
        res = self.pair([clip], [wrong])[0]
        self.assertEqual(res["status"], "ask")
        self.assertIn("low sync confidence", res["reason"])


if __name__ == "__main__":
    unittest.main()
