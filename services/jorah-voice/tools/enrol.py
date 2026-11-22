"""Audio loading and voiceprint enrolment CLI (docs/plan/12-voice-identity.md section 4)."""

import argparse
from array import array
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice import models
from jorah_voice.identity import (
    CENTROIDS_FILE,
    DEFAULT_VOICEPRINT_DIR,
    SherpaExtractor,
    load_centroids,
    normalize_vector,
    resample_float,
    save_centroids,
)

SILENCE_RMS = 0.001
FRAME_SECONDS = 0.02
MIN_CHUNK_SECONDS = 3.0
MAX_CHUNK_SECONDS = 5.0
TARGET_CHUNK_SECONDS = 4.0


def _pcm16_to_float_mono(raw, channels):
    samples = array("h")
    usable = len(raw) - (len(raw) % (2 * channels))
    samples.frombytes(raw[:usable])
    if sys.byteorder != "little":
        samples.byteswap()
    if channels == 1:
        return [s / 32768.0 for s in samples]
    out = []
    for i in range(0, len(samples), channels):
        out.append(sum(samples[i : i + channels]) / (channels * 32768.0))
    return out


def read_wav_16bit(path):
    """Read a 16-bit PCM WAV file into (mono float samples in [-1, 1], sample_rate)."""
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"{path}: expected 16-bit PCM WAV (got {wf.getsampwidth() * 8}-bit)")
        channels = wf.getnchannels()
        if channels < 1:
            raise ValueError(f"{path}: invalid channel count {channels}")
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    return _pcm16_to_float_mono(frames, channels), rate


def decode_audio(path, target_rate=16000):
    """Load WAV directly or decode m4a/mp3 via ffmpeg if available on PATH."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"audio file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".wav":
        samples, rate = read_wav_16bit(path)
        return resample_float(samples, rate, target_rate), target_rate

    if suffix in (".m4a", ".mp3", ".ogg", ".opus", ".flac", ".aac"):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(f"ffmpeg is required to decode {suffix} files, but was not found on PATH")
        result = subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(path), "-ac", "1", "-ar", str(target_rate), "-f", "s16le", "pipe:1",
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", "replace").strip() or f"exit {result.returncode}"
            raise RuntimeError(f"ffmpeg failed to decode {path.name}: {detail}")
        return _pcm16_to_float_mono(result.stdout, 1), target_rate

    raise ValueError(f"unsupported audio format: {path.suffix or path.name}")


def strip_silence(samples, sample_rate, *, rms_threshold=SILENCE_RMS):
    """Keep 20 ms frames whose RMS exceeds `rms_threshold`."""
    frame = max(1, int(sample_rate * FRAME_SECONDS))
    voiced = []
    for start in range(0, len(samples), frame):
        window = samples[start : start + frame]
        if not window:
            continue
        rms = math.sqrt(sum(x * x for x in window) / len(window))
        if rms >= rms_threshold:
            voiced.extend(window)
    return voiced


def speech_chunks(samples, sample_rate, *, min_seconds=MIN_CHUNK_SECONDS, max_seconds=MAX_CHUNK_SECONDS):
    """Split voiced audio into chunks of `min_seconds` to `max_seconds`."""
    voiced = strip_silence(samples, sample_rate)
    total_seconds = len(voiced) / sample_rate if sample_rate > 0 else 0.0
    if total_seconds < min_seconds:
        return [], total_seconds

    if total_seconds <= max_seconds:
        return [voiced], total_seconds

    if total_seconds < 2 * min_seconds:
        end = int(max_seconds * sample_rate)
        return [voiced[:end]], total_seconds

    k = max(2, round(total_seconds / TARGET_CHUNK_SECONDS))
    while total_seconds / k > max_seconds:
        k += 1
    while k > 1 and total_seconds / k < min_seconds:
        k -= 1

    step = len(voiced) // k
    chunks = []
    for i in range(k):
        start = i * step
        end = len(voiced) if i == k - 1 else (i + 1) * step
        chunk = voiced[start:end]
        if len(chunk) / sample_rate > max_seconds:
            chunk = chunk[: int(max_seconds * sample_rate)]
        if len(chunk) / sample_rate >= min_seconds:
            chunks.append(chunk)
    return chunks, total_seconds


def enrol_device(
    device,
    files,
    *,
    voiceprint_dir=DEFAULT_VOICEPRINT_DIR,
    extractor=None,
    model_path=None,
    reset=False,
):
    device = str(device).strip()
    if not device:
        raise ValueError("device name is required")
    if not files:
        raise ValueError("at least one audio file is required")

    if extractor is None:
        if model_path is None:
            model_path = models.ensure_speaker()
        if models.EXPECTED_SHA256 is None:
            raise RuntimeError("speaker model SHA-256 is not pinned in jorah_voice/models.py")
        extractor = SherpaExtractor(model_path, expected_sha256=models.EXPECTED_SHA256)

    rate = int(getattr(extractor, "sample_rate", 16000))
    all_samples = []
    for file_path in files:
        audio, _ = decode_audio(file_path, target_rate=rate)
        all_samples.extend(audio)

    chunks, speech_seconds = speech_chunks(all_samples, rate)
    if not chunks:
        raise ValueError(f"not enough speech for {device}: {speech_seconds:.2f}s (need at least {MIN_CHUNK_SECONDS:.1f}s)")

    embeddings = [normalize_vector(extractor.embed(chunk, rate)) for chunk in chunks]
    dim = len(embeddings[0])
    mean_vec = [sum(emb[i] for emb in embeddings) / len(embeddings) for i in range(dim)]
    centroid = normalize_vector(mean_vec)

    model_name = getattr(extractor, "model_name", models.SPEAKER_MODEL)
    model_sha256 = getattr(extractor, "model_sha256", None)
    if not model_sha256:
        raise RuntimeError("extractor did not provide model_sha256")

    vp_dir = Path(voiceprint_dir)
    centroids = {}
    if not reset and (vp_dir / CENTROIDS_FILE).exists():
        existing = load_centroids(vp_dir)
        if existing["model_sha256"] != model_sha256 or existing["model"] != model_name:
            raise RuntimeError("existing voiceprint uses a different model hash; pass --reset to rebuild")
        centroids = dict(existing["centroids"])

    centroids[device] = centroid
    save_centroids(vp_dir, centroids, model_name, model_sha256)
    return {
        "device": device,
        "files": len(files),
        "speech_seconds": round(speech_seconds, 2),
        "chunks": len(chunks),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Enrol Adam's voice for one device.")
    parser.add_argument("--device", required=True, help="device name, e.g. mac or airpods")
    parser.add_argument("--voiceprint-dir", default=str(DEFAULT_VOICEPRINT_DIR))
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--reset", action="store_true", help="discard existing device centroids")
    parser.add_argument("files", nargs="+", metavar="FILE", help="16-bit WAV, m4a, or mp3 files")
    args = parser.parse_args(argv)

    try:
        stats = enrol_device(
            args.device,
            args.files,
            voiceprint_dir=args.voiceprint_dir,
            model_path=args.model_path,
            reset=args.reset,
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"enrolled device={stats['device']} files={stats['files']} "
        f"speech_seconds={stats['speech_seconds']:.2f} chunks={stats['chunks']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
