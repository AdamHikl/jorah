"""Fetch the speech models once, checking each download against its published SHA-256."""

import hashlib
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path.home() / ".cache" / "jorah-voice" / "models"
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

# Parakeet TDT 0.6B v3 int8 runs on the CPU: as fast as the GPU would make it (about 120 ms a
# sentence), no GPU memory, and it understands 25 European languages, Slovak included.
STT_DIR = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"

# Kokoro v1.0 at full precision on the GPU, because int8 runs slower than fp32 there.
TTS_DIR = "kokoro-multi-lang-v1_0"

FILES = {
    "vad": ("asr-models/silero_vad_v5.onnx", "6b99cbfd39246b6706f98ec13c7c50c6b299181f2474fa05cbc8046acc274396"),
    "stt": ("asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2", "5793d0fd397c5778d2cf2126994d58e9d56b1be7c04d13c7a15bb1b4eafb16bf"),
    "tts": ("tts-models/kokoro-multi-lang-v1_0.tar.bz2", "60703707bc05ccd48d60e1eb723f38b07d6e474795a0b6a588d7220400e0f7a4"),
}
FOLDERS = {"stt": STT_DIR, "tts": TTS_DIR}


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url, target, tries=6, wait=30):
    """GitHub's release downloads fail with a 5xx now and then, so try again before giving up."""
    for attempt in range(1, tries + 1):
        try:
            urllib.request.urlretrieve(url, target)
            return
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == tries:
                raise
        except urllib.error.URLError:
            if attempt == tries:
                raise
        print(f"Download failed, trying again in {wait} s")
        time.sleep(wait)


def _fetch(relative, expected, root):
    target = root / Path(relative).name
    if target.exists() and expected in (None, _sha256(target)):
        return target
    print(f"Downloading {target.name}")
    partial = target.with_suffix(target.suffix + ".part")
    _download(f"{BASE}/{relative}", partial)
    actual = _sha256(partial)
    if expected is not None and actual != expected:
        partial.unlink()
        raise RuntimeError(f"{target.name} failed its checksum: got {actual}, expected {expected}")
    partial.rename(target)
    return target


def ensure(root=ROOT):
    root.mkdir(parents=True, exist_ok=True)
    for key, (relative, expected) in FILES.items():
        folder = FOLDERS.get(key)
        if folder and (root / folder).exists():
            continue
        archive = _fetch(relative, expected, root)
        if folder:
            print(f"Unpacking {archive.name}")
            with tarfile.open(archive) as tar:
                tar.extractall(root, filter="data")
            archive.unlink()
    return root
