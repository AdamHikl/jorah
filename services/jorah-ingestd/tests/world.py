"""Shared test helpers: a scratch media root, fixture ffprobe reports, and speech-like audio."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))

from jorah_ingestd import config  # noqa: E402

try:
    import numpy as np
except ImportError:
    np = None

RATE = 4000


class Root:
    """A temporary /srv/jorah-media with the folders the installer makes."""

    def __init__(self, **overrides):
        self.dir = Path(tempfile.mkdtemp(prefix="ingest-"))
        for d in ("incoming", "spool", "proxies", "state", "luts"):
            (self.dir / d).mkdir()
        values = {"root": str(self.dir), "lut_path": str(self.dir / "luts" / "log.cube"),
                  "proxy_encoder": "libx264"}
        values.update(overrides)
        self.cfg = config.load(overrides=values)

    def take(self, name, files):
        folder = self.dir / "incoming" / name if name else self.dir / "incoming"
        folder.mkdir(parents=True, exist_ok=True)
        for rel, data in files.items():
            p = folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return folder

    def cleanup(self):
        for dirpath, dirnames, filenames in os.walk(self.dir):
            os.chmod(dirpath, 0o755)
            for f in filenames:
                p = os.path.join(dirpath, f)
                if not os.path.islink(p):
                    os.chmod(p, 0o644)
        shutil.rmtree(self.dir, ignore_errors=True)


def video_report(duration=60.0, creation="2026-11-28T10:00:00.000000Z", audio=True, **video):
    v = {"index": 0, "codec_type": "video", "codec_name": "hevc", "profile": "Main 10",
         "width": 3840, "height": 2160, "avg_frame_rate": "30/1", "pix_fmt": "yuv420p10le",
         "color_primaries": "bt2020", "color_transfer": "unknown", "color_space": "bt2020nc",
         "color_range": "tv"}
    v.update(video)
    streams = [v]
    if audio:
        streams.append({"index": 1, "codec_type": "audio", "codec_name": "aac",
                        "sample_rate": "48000", "channels": 2, "duration": str(duration)})
    return {"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": str(duration),
                       "bit_rate": "120000000",
                       "tags": {"creation_time": creation,
                                "com.apple.quicktime.location.ISO6709": "+48.1+017.1/"}},
            "streams": streams}


def wav_report(duration=90.0, date="2026-11-28", time_="10-59-50"):
    return {"format": {"format_name": "wav", "duration": str(duration),
                       "tags": {"origination_date": date, "origination_time": time_}},
            "streams": [{"index": 0, "codec_type": "audio", "codec_name": "pcm_s24le",
                         "sample_rate": "48000", "channels": 1, "duration": str(duration)}]}


def speech(seconds, seed=1, rate=RATE):
    """Noise shaped into syllables and pauses, which correlates like a voice does."""
    rng = np.random.default_rng(seed)
    n = int(seconds * rate)
    x = rng.standard_normal(n)
    env = np.zeros(n)
    i = 0
    while i < n:
        length = int(rng.uniform(0.08, 0.35) * rate)
        env[i:i + length] = rng.uniform(0.3, 1.0)
        i += length + int(rng.uniform(0.02, 0.4) * rate)
    k = int(0.01 * rate)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    return x * env


def other_mic(x, seed=2, noise=0.3, echo=0.4, rate=RATE):
    """The same sound through a different mic and room: low-passed, with an echo and noise."""
    rng = np.random.default_rng(seed)
    y = np.convolve(x, np.ones(3) / 3, mode="same")
    d = int(0.023 * rate)
    y[d:] += echo * y[:-d]
    return y + noise * rng.standard_normal(len(y)) * float(np.std(y))
