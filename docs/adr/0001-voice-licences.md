# ADR 0001: licences outside the allowlist for jorah-voice

**Decision:** accept these, for personal use now, and re-check before anything is published or sold.

| Item | Licence | Why it's acceptable |
|---|---|---|
| Parakeet TDT 0.6B v3 weights | CC-BY-4.0 | Attribution only. Credit NVIDIA in any published notice. The weights are downloaded and never committed |
| NVIDIA CUDA 13.4 runtime, cuBLAS, cuRAND, cuFFT, cuDNN 9, NVRTC, nvJitLink pip packages | NVIDIA proprietary licence (redistributable runtime) | Needed to run Kokoro on the RTX 5070. Used as published, never modified or redistributed by us. Adam accepted it on 2026-11-06 by approving the GPU speech setup. `scripts/check-licenses.sh` accepts this one licence by name |
| `numpy` bundled parts | 0BSD, Zlib | Permissive, and no stricter than the allowlist |

`just licenses` reads `config/licenses.tsv`, which lists each Python package with its licence.
