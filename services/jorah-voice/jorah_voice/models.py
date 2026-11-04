"""Fetch the speech models once, checking each download against its published SHA-256."""

import hashlib
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path.home() / ".cache" / "jorah-voice" / "models"
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

FILES = {
    "vad": ("asr-models/silero_vad_v5.onnx", None),
    "stt": ("asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2", "5793d0fd397c5778d2cf2126994d58e9d56b1be7c04d13c7a15bb1b4eafb16bf"),
    "tts": ("tts-models/kokoro-int8-multi-lang-v1_0.tar.bz2", "72c347230107ef8a31098ec4d468a605244beef5f1ed00db97efa13518800653"),
}

STT_DIR = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
TTS_DIR = "kokoro-int8-multi-lang-v1_0"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetch(relative, expected, root):
    target = root / Path(relative).name
    if target.exists() and expected in (None, _sha256(target)):
        return target
    print(f"Downloading {target.name}")
    partial = target.with_suffix(target.suffix + ".part")
    urllib.request.urlretrieve(f"{BASE}/{relative}", partial)
    actual = _sha256(partial)
    if expected is None:
        print(f"{target.name} has no published checksum. Got {actual}. Pin it in models.py")
    elif actual != expected:
        partial.unlink()
        raise RuntimeError(f"{target.name} failed its checksum: got {actual}, expected {expected}")
    partial.rename(target)
    return target


def ensure(root=ROOT):
    root.mkdir(parents=True, exist_ok=True)
    for key, (relative, expected) in FILES.items():
        archive = _fetch(relative, expected, root)
        folder = {"stt": STT_DIR, "tts": TTS_DIR}.get(key)
        if folder and not (root / folder).exists():
            print(f"Unpacking {archive.name}")
            with tarfile.open(archive) as tar:
                tar.extractall(root, filter="data")
    return root
