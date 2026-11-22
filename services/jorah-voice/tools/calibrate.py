"""Voiceprint threshold calibration CLI (docs/plan/12-voice-identity.md section 3.5)."""

import argparse
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice import models
from jorah_voice.core import percentile
from jorah_voice.identity import (
    DEFAULT_VOICEPRINT_DIR,
    SherpaExtractor,
    cosine_similarity,
    load_centroids,
    normalize_vector,
    save_thresholds,
)
from tools.enrol import decode_audio

AUDIO_SUFFIXES = frozenset((".wav", ".m4a", ".mp3", ".ogg", ".opus", ".flac", ".aac"))
MIN_MARGIN = 0.03
LOW_OFFSET = 0.01
MAX_FALSE_REJECT_RATE = 0.05


def _audio_files(directory):
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"directory not found: {root}")
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES)


def _score_clip(path, target_centroids, extractor, rate):
    samples, _ = decode_audio(path, target_rate=rate)
    if not samples:
        raise ValueError(f"empty audio clip: {path}")
    emb = normalize_vector(extractor.embed(samples, rate))
    return max(cosine_similarity(emb, centroid) for centroid in target_centroids.values())


def _pop_std(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def calibrate(
    genuine_dir,
    impostor_dir,
    *,
    device=None,
    voiceprint_dir=DEFAULT_VOICEPRINT_DIR,
    extractor=None,
    model_path=None,
    write_anyway=False,
    calibrated_at=None,
):
    vp_dir = Path(voiceprint_dir)
    centroids_data = load_centroids(vp_dir)
    all_centroids = centroids_data["centroids"]

    if device is not None:
        if device not in all_centroids:
            raise ValueError(f"device {device!r} is not enrolled in {vp_dir}")
        target_centroids = {device: all_centroids[device]}
    else:
        target_centroids = all_centroids

    if extractor is None:
        if model_path is None:
            model_path = models.ensure_speaker()
        if models.EXPECTED_SHA256 is None:
            raise RuntimeError("speaker model SHA-256 is not pinned in jorah_voice/models.py")
        extractor = SherpaExtractor(model_path, expected_sha256=models.EXPECTED_SHA256)

    model_sha256 = getattr(extractor, "model_sha256", None)
    if not model_sha256 or model_sha256 != centroids_data["model_sha256"]:
        raise RuntimeError("speaker model hash does not match enrolled voiceprint")

    rate = int(getattr(extractor, "sample_rate", 16000))
    genuine_files = _audio_files(genuine_dir)
    impostor_files = _audio_files(impostor_dir)
    if not genuine_files or not impostor_files:
        raise ValueError("both --genuine and --impostor directories must contain audio clips")

    genuine_root = Path(genuine_dir)
    genuine_scores = []
    per_device_scores = {}
    for path in genuine_files:
        rel_parts = path.relative_to(genuine_root).parts
        clip_device = device if device is not None else (rel_parts[0] if len(rel_parts) > 1 and rel_parts[0] in all_centroids else None)
        if clip_device and clip_device in all_centroids:
            score = _score_clip(path, {clip_device: all_centroids[clip_device]}, extractor, rate)
            per_device_scores.setdefault(clip_device, []).append(score)
        else:
            score = _score_clip(path, target_centroids, extractor, rate)
        genuine_scores.append(score)

    impostor_scores = [_score_clip(path, target_centroids, extractor, rate) for path in impostor_files]

    lowest_zero_fa = max(impostor_scores)
    top_count = max(1, math.ceil(0.01 * len(impostor_scores)))
    top_impostors = sorted(impostor_scores, reverse=True)[:top_count]
    margin = max(MIN_MARGIN, 2.0 * _pop_std(top_impostors))
    high = round(lowest_zero_fa + margin, 6)

    p5 = percentile(genuine_scores, 0.05)
    low = round(min(high, p5 - LOW_OFFSET), 6)

    false_accepts = sum(1 for s in impostor_scores if s >= high)
    false_rejects = sum(1 for s in genuine_scores if s < high)

    per_device_counts = {}
    per_device_pass = True
    for dev, scores in sorted(per_device_scores.items()):
        rej = sum(1 for s in scores if s < high)
        per_device_counts[dev] = {"genuine": len(scores), "false_rejects": rej}
        if rej / len(scores) > MAX_FALSE_REJECT_RATE:
            per_device_pass = False

    overall_pass = (false_accepts == 0) and (false_rejects / len(genuine_scores) <= MAX_FALSE_REJECT_RATE)
    passed = overall_pass and per_device_pass

    counts = {
        "genuine": len(genuine_scores),
        "impostor": len(impostor_scores),
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
    }
    if per_device_counts:
        counts["per_device"] = per_device_counts

    wrote = False
    if passed or write_anyway:
        stamp = calibrated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_thresholds(vp_dir, high, low, stamp, counts)
        wrote = True

    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "wrote": wrote,
        "high": high,
        "low": low,
        "counts": counts,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calibrate speaker verification thresholds.")
    parser.add_argument("--genuine", required=True, help="directory of Adam's clips")
    parser.add_argument("--impostor", required=True, help="directory of other voices' clips")
    parser.add_argument("--device", default=None, help="single enrolled device to calibrate")
    parser.add_argument("--voiceprint-dir", default=str(DEFAULT_VOICEPRINT_DIR))
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--write-anyway", action="store_true", help="write thresholds even when bar fails")
    args = parser.parse_args(argv)

    try:
        result = calibrate(
            args.genuine,
            args.impostor,
            device=args.device,
            voiceprint_dir=args.voiceprint_dir,
            model_path=args.model_path,
            write_anyway=args.write_anyway,
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    c = result["counts"]
    print(
        f"{result['status']}: genuine={c['genuine']} impostor={c['impostor']} "
        f"false_accepts={c['false_accepts']} false_rejects={c['false_rejects']} "
        f"high={result['high']:.4f} low={result['low']:.4f} wrote={result['wrote']}"
    )
    return 0 if result["passed"] or result["wrote"] else 1


if __name__ == "__main__":
    sys.exit(main())
