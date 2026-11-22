"""Speaker verification for jorah-voice (docs/plan/12-voice-identity.md section 3).

Runs NeMo TitaNet-Large via sherpa-onnx's SpeakerEmbeddingExtractor on the CPU.
Embeddings and exact similarity scores stay in memory for one turn only and are never kept or logged;
logs carry the verdict and a coarse score bucket only.
"""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import tempfile

from . import models

DEFAULT_VOICEPRINT_DIR = Path.home() / ".config" / "jorah-voice" / "voiceprint"
CENTROIDS_FILE = "centroids.json"
THRESHOLDS_FILE = "thresholds.json"
MIN_SPEECH_SECONDS = 1.2
SCORE_BUCKETS = ("<0.3", "0.3-0.5", "0.5-0.7", ">=0.7")


@dataclass(frozen=True)
class Verdict:
    kind: str  # "adam", "someone_else", "unsure", "unavailable"
    speech_seconds: float
    bucket: str | None = None


def score_bucket(score):
    if score < 0.3:
        return "<0.3"
    if score < 0.5:
        return "0.3-0.5"
    if score < 0.7:
        return "0.5-0.7"
    return ">=0.7"


def ensure_private_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_private_json(path, payload):
    path = Path(path)
    ensure_private_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        os.chmod(tmp_name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def normalize_vector(vec):
    vals = [float(x) for x in vec]
    if not vals or not all(math.isfinite(x) for x in vals):
        raise ValueError("embedding must be a non-empty finite vector")
    norm = math.sqrt(sum(x * x for x in vals))
    if norm <= 0.0 or not math.isfinite(norm):
        raise ValueError("embedding norm must be positive")
    return [x / norm for x in vals]


def cosine_similarity(a, b):
    if len(a) != len(b) or not a:
        raise ValueError("vectors must have the same non-empty dimension")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        fx = float(x)
        fy = float(y)
        if not (math.isfinite(fx) and math.isfinite(fy)):
            raise ValueError("vector contains non-finite value")
        dot += fx * fy
        norm_a += fx * fx
        norm_b += fy * fy
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    if denom <= 0.0 or not math.isfinite(denom):
        raise ValueError("zero-norm vector")
    return dot / denom


def resample_float(samples, source_rate, target_rate):
    """Linearly resample float mono audio to `target_rate`."""
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("sample rates must be positive")
    vals = [float(x) for x in samples]
    if source_rate == target_rate or len(vals) <= 1:
        return vals
    step = source_rate / target_rate
    out = []
    pos = 0.0
    limit = len(vals) - 1
    while pos < limit:
        base = int(pos)
        frac = pos - base
        out.append(vals[base] + (vals[base + 1] - vals[base]) * frac)
        pos += step
    return out


def save_centroids(voiceprint_dir, centroids, model_name, model_sha256):
    if not centroids:
        raise ValueError("at least one device centroid is required")
    if not isinstance(model_name, str) or not model_name:
        raise ValueError("model_name is required")
    if not isinstance(model_sha256, str) or not model_sha256:
        raise ValueError("model_sha256 is required")
    normalized = {}
    dim = None
    for device, vec in centroids.items():
        if not isinstance(device, str) or not device.strip():
            raise ValueError("device name must be non-empty")
        unit = normalize_vector(vec)
        if dim is None:
            dim = len(unit)
        elif len(unit) != dim:
            raise ValueError("all centroids must share one dimension")
        normalized[device] = unit
    payload = {
        "version": 1,
        "model": model_name,
        "model_sha256": model_sha256,
        "centroids": normalized,
    }
    write_private_json(Path(voiceprint_dir) / CENTROIDS_FILE, payload)
    return payload


def load_centroids(voiceprint_dir):
    path = Path(voiceprint_dir) / CENTROIDS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("invalid centroids version")
    model_name = data.get("model")
    model_sha256 = data.get("model_sha256")
    raw_centroids = data.get("centroids")
    if not isinstance(model_name, str) or not model_name:
        raise ValueError("missing model name")
    if not isinstance(model_sha256, str) or not model_sha256:
        raise ValueError("missing model sha256")
    if not isinstance(raw_centroids, dict) or not raw_centroids:
        raise ValueError("missing centroids")
    centroids = {}
    dim = None
    for device, vec in raw_centroids.items():
        if not isinstance(device, str) or not device:
            raise ValueError("invalid device key")
        unit = normalize_vector(vec)
        if dim is None:
            dim = len(unit)
        elif len(unit) != dim:
            raise ValueError("inconsistent centroid dimension")
        centroids[device] = unit
    return {
        "version": 1,
        "model": model_name,
        "model_sha256": model_sha256,
        "centroids": centroids,
    }


def save_thresholds(voiceprint_dir, high, low, calibrated_at, counts):
    high_f = float(high)
    low_f = float(low)
    if not (math.isfinite(high_f) and math.isfinite(low_f)) or low_f > high_f:
        raise ValueError("thresholds must be finite with low <= high")
    if not isinstance(calibrated_at, str) or not calibrated_at:
        raise ValueError("calibrated_at is required")
    if not isinstance(counts, dict):
        raise ValueError("counts must be a dict")
    payload = {
        "version": 1,
        "high": high_f,
        "low": low_f,
        "calibrated_at": calibrated_at,
        "counts": counts,
    }
    write_private_json(Path(voiceprint_dir) / THRESHOLDS_FILE, payload)
    return payload


def load_thresholds(voiceprint_dir):
    path = Path(voiceprint_dir) / THRESHOLDS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("invalid thresholds version")
    high = float(data["high"])
    low = float(data["low"])
    if not (math.isfinite(high) and math.isfinite(low)) or low > high:
        raise ValueError("invalid threshold bounds")
    if not isinstance(data.get("calibrated_at"), str) or not isinstance(data.get("counts"), dict):
        raise ValueError("missing calibration metadata")
    return {
        "version": 1,
        "high": high,
        "low": low,
        "calibrated_at": data["calibrated_at"],
        "counts": data["counts"],
    }


class SherpaExtractor:
    """Wrapper around sherpa-onnx's SpeakerEmbeddingExtractor on the CPU."""

    def __init__(self, model_path, *, threads=4, provider="cpu", expected_sha256=None):
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"speaker model not found: {model_path}")
        actual_sha256 = models.sha256_file(model_path)
        if expected_sha256 is not None and actual_sha256 != expected_sha256:
            raise RuntimeError(f"{model_path.name} failed its checksum: got {actual_sha256}, expected {expected_sha256}")
        import sherpa_onnx
        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(model_path),
            num_threads=threads,
            debug=False,
            provider=provider,
        )
        self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        self.model_name = model_path.name
        self.model_sha256 = actual_sha256
        rate = getattr(self._extractor, "sample_rate", 16000)
        self.sample_rate = int(rate() if callable(rate) else rate)

    def embed(self, samples, sample_rate):
        if sample_rate != self.sample_rate:
            samples = resample_float(samples, sample_rate, self.sample_rate)
            sample_rate = self.sample_rate
        stream = self._extractor.create_stream()
        stream.accept_waveform(sample_rate, samples)
        stream.input_finished()
        if not self._extractor.is_ready(stream):
            raise RuntimeError("speaker extractor stream not ready")
        return normalize_vector(self._extractor.compute(stream))


def _sample_count(samples):
    if samples is None:
        return 0
    if isinstance(samples, (bytes, bytearray)):
        return len(samples) // 2
    return len(samples)


class SpeakerCheck:
    """Verifies whether a turn's audio matches Adam's enrolled voiceprints.

    Fails closed to `unavailable` whenever the model, voiceprint, thresholds, or model hash check
    fails or raises.
    """

    def __init__(
        self,
        voiceprint_dir=DEFAULT_VOICEPRINT_DIR,
        *,
        extractor=None,
        model_path=None,
        model_sha256=None,
        min_speech_seconds=MIN_SPEECH_SECONDS,
    ):
        self._dir = Path(voiceprint_dir)
        self._extractor = extractor
        self._model_path = Path(model_path) if model_path is not None else None
        self._model_sha256 = model_sha256
        self._min_speech_seconds = float(min_speech_seconds)

    def _resolve_model_hash(self):
        if self._model_sha256:
            return self._model_sha256
        if self._extractor is not None and getattr(self._extractor, "model_sha256", None):
            return self._extractor.model_sha256
        if self._model_path is not None and self._model_path.is_file():
            return models.sha256_file(self._model_path)
        return None

    def _ready_state(self):
        if self._extractor is None:
            return None
        centroids_data = load_centroids(self._dir)
        thresholds_data = load_thresholds(self._dir)
        model_hash = self._resolve_model_hash()
        if not model_hash or model_hash != centroids_data["model_sha256"]:
            return None
        model_name = getattr(self._extractor, "model_name", None)
        if model_name is None and self._model_path is not None:
            model_name = self._model_path.name
        if model_name is not None and model_name != centroids_data["model"]:
            return None
        return centroids_data["centroids"], thresholds_data["high"], thresholds_data["low"]

    def is_ready(self):
        try:
            return self._ready_state() is not None
        except Exception:
            return False

    def verdict(self, samples, sample_rate):
        try:
            rate = float(sample_rate)
            speech_seconds = (_sample_count(samples) / rate) if rate > 0 else 0.0
        except Exception:
            return Verdict("unavailable", 0.0, None)

        if rate <= 0:
            return Verdict("unavailable", 0.0, None)

        try:
            state = self._ready_state()
            if state is None:
                return Verdict("unavailable", speech_seconds, None)
            if speech_seconds < self._min_speech_seconds:
                return Verdict("unsure", speech_seconds, None)
            centroids, high, low = state
            embedding = normalize_vector(self._extractor.embed(samples, int(rate)))
            best = max(cosine_similarity(embedding, centroid) for centroid in centroids.values())
            if not math.isfinite(best):
                return Verdict("unavailable", speech_seconds, None)
            bucket = score_bucket(best)
            if best >= high:
                kind = "adam"
            elif best <= low:
                kind = "someone_else"
            else:
                kind = "unsure"
            return Verdict(kind=kind, speech_seconds=speech_seconds, bucket=bucket)
        except Exception:
            return Verdict("unavailable", speech_seconds, None)
