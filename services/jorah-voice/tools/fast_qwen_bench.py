"""Benchmark faster-qwen3-tts with Jorah's locked voice, streaming. Written 2026-11-08, not yet run.

Install on Adam's yes, in its own environment (it conflicts with upstream qwen-tts):
  mkdir -p ~/apps/fast-qwen && cd ~/apps/fast-qwen && ~/.local/bin/uv venv --python 3.12 .venv
  ~/.local/bin/uv pip install --python .venv/bin/python --exclude-newer 2026-11-01 --index-strategy unsafe-best-match \
    --extra-index-url https://download.pytorch.org/whl/cu128 faster-qwen3-tts==0.5.4 transformers==5.15.1 torch torchaudio
Run: .venv/bin/python /opt/jorah/services/jorah-voice/tools/fast_qwen_bench.py
"""
import os
import time

import numpy as np
import soundfile as sf
import torch
from faster_qwen3_tts import FasterQwen3TTS

V = os.path.expanduser("~/.config/jorah-voice/voice")
REF = f"{V}/jorah-ref.wav"
REF_TEXT = open(f"{V}/jorah-ref.txt").read().strip()
TEXT = ("I had a look at that power supply. The fan's on its way out, I'm afraid, but it's still under warranty, "
        "so Alza ought to swap it. Shall I draft the claim for you?")
OUT = os.path.expanduser("~/voice-samples/fast")
os.makedirs(OUT, exist_ok=True)

for repo in ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"):
    model = FasterQwen3TTS.from_pretrained(repo)
    list(model.generate_voice_clone_streaming(text="Warm up, please.", language="English",
                                              ref_audio=REF, ref_text=REF_TEXT, chunk_size=8))
    for run in range(2):
        start = time.time()
        first = None
        parts = []
        rate = 24000
        for chunk, rate, _timing in model.generate_voice_clone_streaming(
                text=TEXT, language="English", ref_audio=REF, ref_text=REF_TEXT, chunk_size=8):
            if first is None:
                first = time.time() - start
            parts.append(np.asarray(chunk, dtype=np.float32).reshape(-1))
        took = time.time() - start
        audio = np.concatenate(parts)
        seconds = len(audio) / rate
        print(f"{repo.split('/')[1]} run{run}: {seconds:.1f}s audio in {took:.1f}s, first audio {first * 1000:.0f} ms, "
              f"compute per audio second {took / seconds:.2f}", flush=True)
    sf.write(f"{OUT}/{repo.split('-')[2]}.wav", audio, rate)
    print("peak VRAM GB", round(torch.cuda.max_memory_allocated() / 1e9, 1), flush=True)
    del model
    torch.cuda.empty_cache()
