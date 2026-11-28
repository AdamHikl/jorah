"""Settings for the intake. The live file is /etc/jorah-media/ingest.json, root-owned, so the
ingest user can't change its own LUT pin. Unknown keys are refused, so a typo can't pass silently."""
import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULTS = {
    "root": "/srv/jorah-media",
    # A take is ready once nothing in it has changed for this long (ADR 0013, point 1).
    "settle_s": 30,
    "poll_s": 10,
    # Ingest refuses a take when free space is below this many times the take's size.
    "space_factor": 3.0,
    # Adam, 2026-11-28: "HEVC, apple log, 30fps". Used when a clip's metadata doesn't say.
    "default_color": "apple_log",
    "lut_path": "/srv/jorah-media/luts/apple-log-to-rec709.cube",
    # The LUT's SHA-256, pinned by `install-ingestd.sh --pin-lut`. Until it is set, Apple Log
    # proxies wait: an unpinned LUT is never used.
    "lut_sha256": None,
    # Clocks on the iPhone and the Mac may differ by this much when pairing by start time.
    "pair_skew_s": 60,
    "sync_rate": 4000,
    "sync_min_ratio": 1.5,
    "sync_min_z": 10.0,
    "drift_warn_ms": 33.0,
    # Used to read a BWF time, which has no time zone.
    "local_tz": "Europe/Bratislava",
    "proxy_height": 1080,
    "proxy_encoder": "h264_nvenc",
    "ffmpeg": "/usr/bin/ffmpeg",
    "ffprobe": "/usr/bin/ffprobe",
}


@dataclass
class Config:
    values: dict = field(default_factory=lambda: dict(DEFAULTS))

    def __getattr__(self, name):
        try:
            return self.__dict__["values"][name]
        except KeyError:
            raise AttributeError(name) from None

    @property
    def root_path(self) -> Path:
        return Path(self.values["root"])

    @property
    def incoming(self) -> Path:
        return self.root_path / "incoming"

    @property
    def spool(self) -> Path:
        return self.root_path / "spool"

    @property
    def proxies(self) -> Path:
        return self.root_path / "proxies"

    @property
    def state(self) -> Path:
        return self.root_path / "state"


def load(path=None, overrides=None) -> Config:
    values = dict(DEFAULTS)
    if path:
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError(f"{path}: not a JSON object")
        unknown = sorted(set(data) - set(DEFAULTS))
        if unknown:
            raise ValueError(f"{path}: unknown keys {', '.join(unknown)}")
        values.update(data)
    if overrides:
        values.update(overrides)
    if values["default_color"] not in ("apple_log", "rec709"):
        raise ValueError("default_color must be apple_log or rec709")
    if values["settle_s"] < 5 or values["space_factor"] < 1:
        raise ValueError("settle_s must be at least 5 and space_factor at least 1")
    return Config(values)
