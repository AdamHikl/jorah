# Making Qwen3-TTS faster than real time: research

Research by Antigravity (Gemini 4 Argon High), 2026-11-08. Claude checked: andimarafioti/faster-qwen3-tts exists (MIT, ~1,400 stars, created 2026-02-16, last push 2026-10-09), PyPI faster-qwen3-tts 0.5.4 from 2026-10-05, needs transformers 5.15.1 and conflicts with upstream qwen-tts in one environment; its README shows RTX 4090 at 4.78x real time and 156 ms to first audio with CUDA graphs (its RTF counts the other way round). RTX 5070 figures in this report are the worker's estimates, not measured.

# Research Report: Making Qwen3-TTS Faster Than Real-Time & Streaming on RTX 5070 (Blackwell `sm_120`, WSL2)

*Note on Real-Time Factor (RTF) convention:* Throughout this report, **RTF** is reported using your convention ($\text{RTF} = \frac{\text{compute time}}{\text{audio duration}}$, where **$\text{RTF} < 1.0$ is faster than real-time**). Where a source (such as `faster-qwen3-tts`) reports inverted speed multipliers ($\times$ real-time), both numbers are given.

---

## Why Your Current Setup Hits RTF ~1.3 Without Audio Streaming

`Qwen3-TTS-12Hz-1.7B-Base` (released **Jan 22, 2026**, [arXiv:2601.15621](https://arxiv.org/abs/2601.15621), [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)) uses a dual-stage architecture at 12.5 Hz (1 frame = 80 ms of audio):
1. **Stage 0 (Talker + CodePredictor / MTP):** A 28-layer Qwen3 autoregressive transformer predicts the first RVQ codebook token, followed by a multi-step autoregressive **CodePredictor** loop that predicts the remaining 15 residual codebooks (16 codebooks total per 80 ms frame).
2. **Stage 1 (Code2Wav / `Qwen3-TTS-Tokenizer-12Hz`):** A causal ConvNet/SEANet decoder reconstructs 24 kHz waveform audio from the 12.5 Hz RVQ frames.

In stock `qwen-tts` **0.1.1** (released **Jan 22, 2026**):
- **Why RTF is ~1.3:** In PyTorch eager mode with dynamic KV caches, every 80 ms audio frame dispatches **~500 small CUDA kernels** across the Talker and multi-step CodePredictor loop. On fast GPUs (RTX 4090/5070/5090), inference is **CPU kernel-launch bound**, leaving GPU utilization at 10–20%.
- **Why `non_streaming_mode=False` doesn't stream audio:** As noted in the upstream repo, the official `qwen-tts` Python package only released offline whole-utterance inference (`generate_voice_clone` waits for all codec tokens before running `Code2Wav`). `non_streaming_mode=False` only simulates text-token-by-text-token conditioning inside the Talker prefill schedule; it still returns a single completed waveform and was later defaulted to `True` in upstream issues/PRs (`#239`, `#362`) to prevent speaking-rate drift on long utterances.

---

## 1. Official & Community Ways to Run Qwen3-TTS Faster

### Summary Comparison Table

| Runtime / Method | Status & Date | True Audio Streaming? | Voice Clone Prompt Cache? | Reported RTF ($\text{compute}/\text{audio}$, $<1$ is faster) | Reported TTFA (Time-to-First-Audio) | Consumer GPU / Hardware Tested |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`andimarafioti/faster-qwen3-tts`** (CUDA Graphs + `StaticCache`) | Community PyPI/GitHub (Jan–Oct 2026) | Yes (chunked PCM/audio generator) | Yes (`voice_clone_prompt` / prefill cache) | **1.7B:** ~0.24 (4.22×) on 4090; ~0.55 (1.83×) on 4060<br>**0.6B:** ~0.18–0.21 (4.78–5.56×) on 4090; ~0.44 (2.26×) on 4060 | **1.7B:** 174 ms (4090), 460 ms (4060)<br>**0.6B:** 156 ms (4090), 413 ms (4060) | RTX 4090, RTX 4060, Jetson Orin, H100 |
| **`dffdeeq/Qwen3-TTS-streaming`** (`torch.compile` + CUDA Graphs) | Community Fork (Jan–mid 2026) | Yes (`stream_generate_voice_clone`) | Yes | **~0.17–0.25** (up to ~6× speedup over stock `qwen-tts`) | **~150–250 ms** (two-phase chunking) | RTX 3090, RTX 4090 |
| **vLLM-Omni** (`vllm-project/vllm-omni`) | Official Support (Jan–Aug 2026) | Yes (async chunking, WS / HTTP PCM) | Yes (speaker embedding & prefix caching) | **1.7B:** ~0.17 single-stream; ~0.45 (8 RPS) to ~0.75 (25 RPS) | **56.8 ms** (p95 @ 1 RPS on H100); **~23–50 ms** median reported on RTX 5090; **~97–150 ms** typical | H100, RTX 5090, RTX 4090 |
| **SGLang-Omni** (`sgl-project/sglang-omni`) | Official SGLang Subproject (Mid 2026) | Yes (`/v1/audio/speech` with `stream: true`) | Yes (RadixAttention prefix cache) | **1.7B:** ~0.25–0.55 | **~97–200 ms** (active tuning on chunk boundary jitter) | H100, A100, RTX 4090 |
| **TensorRT Edge-LLM / TRT** (`NVIDIA/TensorRT-Edge-LLM` & `X-Square-Robot/Qwen3TTS-Streaming`) | Official NVIDIA C++ & Community TRT (Mid–Aug 2026) | Yes (`--streaming --chunk-frames=N`) | Yes | **<0.20** on desktop GPUs; real-time (<1.0) on Jetson | **~16 ms TTFT / <150 ms TTFA** | Jetson Orin/Thor, Desktop RTX, H100 |
| **`llama.cpp` / GGUF** (PR `#26254`, `#26603` / `qwen3_tts_gguf`) | Mainline `llama.cpp` (Aug 2026) + Hybrid GGUF/ONNX | Yes in `llama-server` (`/tts` PR `#26603`) & Python wrappers | Yes (speaker JSON / prompt file) | **~0.25–0.50** on consumer CUDA GPUs (Q4_K_M / Q8_0 Talker) | Top-ranked single-stream TTFA (**~150–300 ms**) | Consumer CUDA GPUs, Apple Metal, Vulkan |
| **Pure ONNX Runtime** (`pltobing/Qwen3-TTS-Streaming-ONNX`) | Community (Apr–May 2026) | Yes (24 kHz chunked decoder) | Yes (ECAPA-TDNN ONNX) | **~0.3–0.6** on CUDA EP; ~1.0–4.5 on CPU (Int4) | **~200–350 ms** on GPU | CUDA GPUs & CPU |
| **FlashAttention-2 / FlashInfer alone** (without CUDA graphs) | Community `sm_120` wheels (2025–2026) | No (attention kernel only) | N/A | **Only ~10–20% faster than SDPA** for short TTS sequences (RTF ~1.05–1.15) | N/A | RTX 5070/5080/5090 (`sm_120`) |

### Detailed Breakdown by Technology

1. **Static KV Cache + CUDA Graphs + `torch.compile` (Biggest Single-Stream Win in Python):**
   - **Why it works:** Because Qwen3-TTS generates only 12.5 frames per second of audio (short sequence lengths, typically 25–200 tokens), attention FLOPs are tiny compared to Python/CUDA launch overhead. Allocating a `StaticCache` and capturing the Talker forward step and the 15-step CodePredictor loop into **CUDA Graphs** reduces ~500 kernel launches per frame to a single graph replay.
   - **[andimarafioti/faster-qwen3-tts](https://github.com/andimarafioti/faster-qwen3-tts)** (released Jan 2026, updated through v0.5.x in 2026): Wraps `qwen-tts` directly with `StaticCache` and dual CUDA graphs (Talker + CodePredictor) with zero `torch.compile` warmup delay. On an **RTX 4090**, 1.7B speed jumps from 0.82× real-time (RTF 1.22) to **4.22× real-time (RTF 0.24)** with **174 ms TTFA** (`chunk_size=8`). On a laptop/desktop **RTX 4060**, 1.7B reaches **1.83× real-time (RTF 0.55)** and **460 ms TTFA**. Given the RTX 5070 sits well above the 4060 and ~65–70% of a 4090 in memory bandwidth/compute, expected 1.7B performance on RTX 5070 is **RTF ~0.30–0.40** and **TTFA ~220–280 ms**.
   - **[dffdeeq/Qwen3-TTS-streaming](https://github.com/dffdeeq/Qwen3-TTS-streaming)** (Jan–mid 2026): Fork of `QwenLM/Qwen3-TTS` that applies `torch.compile(mode="reduce-overhead")` to the Talker and manual CUDA Graph capture to the CodePredictor loop, reporting a **~6× speedup (RTF ~0.20–0.25)** on RTX 3090/4090.
   - **Persistent CUDA Megakernels:** Experimental repos adapting [AlpinDale/qwen_megakernel](https://github.com/AlpinDale/qwen_megakernel) for Qwen3-TTS—such as [madhavdhuppe/qwen3tts-megakernel-pipecat](https://github.com/madhavdhuppe/qwen3tts-megakernel-pipecat) and [sk731/qwen3tts-megakernel](https://github.com/sk731/qwen3tts-megakernel) (2026)—fuse the decode step into a single persistent kernel on RTX 5090 (`sm_120a`), hitting <50 ms TTFA and RTF < 0.2, though they are brittle and model-size specific.

2. **vLLM-Omni ([vllm-project/vllm-omni](https://github.com/vllm-project/vllm-omni)):**
   - **Docs & Blog:** [vLLM-Omni Qwen3-TTS Docs](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/tts/), [vLLM Blog: Engineering TTS Inference in vLLM-Omni](https://vllm.ai/blog/) (**Jun 23, 2026**), and [Baseten Qwen3-TTS Benchmark Blog](https://www.baseten.co/blog/cost-efficient-high-performance-tts-with-qwen3-tts) (**May 14, 2026; updated Aug 27, 2026**).
   - **How it works:** Disaggregates Stage 0 (Talker + `code_predictor_prefix_graphs` CUDA graphs) and Stage 1 (`Code2Wav`) across processes using shared-memory IPC, speaker embedding caching, and async chunking (`codec_streaming: true`).
   - **Reported Numbers:** Single-stream 1.7B hits **56.8 ms p95 TTFA** and **RTF ~0.17** on H100; an October 2026 RTX 5090 study (*Stormin' The Castle*) measured **23–50 ms median TTFA** with `vllm-omni`.
   - **Caveat for a 12 GB RTX 5070:** `vllm-omni` spawns two separate engine stages (Stage 0 AR + Stage 1 Code2Wav), which adds process/IPC memory overhead on a single 12 GB GPU and requires tuning `gpu_memory_utilization` carefully.

3. **SGLang-Omni ([sgl-project/sglang-omni](https://github.com/sgl-project/sglang-omni)) & VoxServe ([vox-serve/vox-serve](https://github.com/vox-serve/vox-serve)):**
   - **SGLang-Omni** (mid-2026) supports `Qwen3-TTS-1.7B-Base` via `/v1/audio/speech` with RadixAttention prefix caching for repeated voice-clone prompts (RTF 0.25–0.55). However, GitHub issues note that under concurrent load, chunk scheduling between the AR worker and vocoder requires careful tuning to avoid inter-chunk stutters.
   - **VoxServe** ([arXiv:2602.00269](https://arxiv.org/abs/2602.00269), **Jan 30, 2026**, [vox-serve/vox-serve](https://github.com/vox-serve/vox-serve)) is a dedicated streaming-centric speech LM server supporting Qwen3-TTS with p95 audible TTFA of **50–90 ms** on H100.

4. **TensorRT / TensorRT Edge-LLM:**
   - **[NVIDIA/TensorRT-Edge-LLM](https://github.com/NVIDIA/TensorRT-Edge-LLM)** (2026) natively supports Qwen3-TTS by compiling three engines: Talker (FP16), CodePredictor (supports **FP8 / NVFP4** quantization), and Code2Wav (FP16), executed in C++ via `qwen3_tts_inference --streaming --chunk-frames=N`.
   - **[X-Square-Robot/Qwen3TTS-Streaming](https://github.com/X-Square-Robot/Qwen3TTS-Streaming)** & **[X2Streaming-TTS](https://github.com/X-Square-Robot/X2Streaming-TTS)** ([arXiv:2608.18661](https://arxiv.org/abs/2608.18661), **Aug 19, 2026**): Exports Qwen3-TTS to ONNX/TensorRT with causal speech-state inheritance, achieving **15.8 ms median TTFT** for single streams.

5. **`llama.cpp` / GGUF & ONNX:**
   - **Mainline `llama.cpp`:** Merged Qwen3-TTS support in **PR [#26254](https://github.com/ggml-org/llama.cpp/pull/26254)** (**Aug 2026**) for `llama-tts` and **PR [#26603](https://github.com/ggml-org/llama.cpp/pull/26603)** for `/tts` streaming in `llama-server` (weights at `ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF` and `Serveurperso/Qwen3-TTS-GGUF`). Fits in **4–6 GB VRAM** with Q4_K_M / Q8_0 quantization and ranks at the top of the HF Open TTS Leaderboard for single-stream TTFA.
   - **Hybrid GGUF + ONNX:** `Solidaxel/Qwen3-TTS-GGUF` (`qwen3_tts_gguf` Python wrapper) runs the Talker/Predictor in `llama.cpp` GGUF and the codec/speaker encoder in ONNX Runtime.
   - **Pure ONNX:** [pltobing/Qwen3-TTS-Streaming-ONNX](https://huggingface.co/pltobing/Qwen3-TTS-Streaming-ONNX) (**Apr–May 2026**) runs all four sub-modules in ONNX Runtime without PyTorch.

6. **FlashAttention 2/3/4 on Blackwell (`sm_120`) & Batching Tricks:**
   - **Why FA alone won't solve RTF ~1.3:** At 12.5 Hz, a 10-second utterance is only 125 Talker tokens (plus ~50–100 text/prompt tokens), and the CodePredictor context is only 16 tokens long. Switching from PyTorch `sdpa` to `flash_attention_2` without CUDA graphs only improves single-stream RTF by **~10–20%** because kernel launch overhead—not $O(N^2)$ attention compute—is the bottleneck.
   - **Prompt Caching / Batching Tricks:** Pre-computing `create_voice_clone_prompt()` (which you already do) saves the ECAPA-TDNN / reference-codec extraction pass, but in vanilla `qwen-tts` the Talker still re-prefills the reference tokens on every call unless prefix KV caching (used in `faster-qwen3-tts`, `vllm-omni`, and `sglang-omni`) is enabled.

---

## 2. True Streaming Audio Generation for Qwen3-TTS

To get true audio streaming, the runtime must pass groups of RVQ frames (e.g., every 4 to 8 frames = 320–640 ms of audio, or 1–2 frames for the very first chunk) into the causal `Qwen3-TTS-Tokenizer-12Hz` (`Code2Wav`) decoder **while** the Talker is still generating subsequent frames, preserving left-context convolutional/transformer state (or applying a Hann crossfade window across chunk boundaries).

### Mature Drop-In Python Libraries (Best for In-Process Voice Assistants)
1. **[andimarafioti/faster-qwen3-tts](https://github.com/andimarafioti/faster-qwen3-tts)** (**Maturity: High — Production-ready for single-user / local GPU**):
   - Installable via `pip install faster-qwen3-tts`, uses your existing Hugging Face weights (`Qwen/Qwen3-TTS-12Hz-1.7B-Base`) and supports `generate_voice_clone_streaming(..., chunk_size=8)` (or smaller initial chunks), yielding `(audio_chunk, sample_rate)` as frames arrive.
   - Preserves voice clone prompt caching and uses `StaticCache` + CUDA graphs out of the box.
2. **[dffdeeq/Qwen3-TTS-streaming](https://github.com/dffdeeq/Qwen3-TTS-streaming)** (**Maturity: Medium-High — Popular drop-in fork of `qwen-tts`**):
   - Adds `stream_generate_voice_clone()` and `stream_generate_pcm()` directly to the `Qwen3TTSModel` class.
   - Includes **two-phase streaming** (small initial `emit_every_frames` for sub-250 ms TTFA, then larger chunks for throughput), **Hann window crossfading** to eliminate inter-chunk clicks, and streaming repetition penalties.

### OpenAI-Compatible TTS Servers (`/v1/audio/speech` with `stream: true`)
1. **[groxaxo/Qwen3-TTS-Openai-Fastapi](https://github.com/groxaxo/Qwen3-TTS-Openai-Fastapi)** (**Jan 2026+, Maturity: Medium-High for local assistants**):
   - FastAPI server exposing `POST /v1/audio/speech` (`stream: true`, `response_format: "pcm" | "wav" | "opus"`) and `/v1/audio/voice-clone`.
2. **[alfonsodg/concurrent-faster-qwen3-server](https://github.com/alfonsodg/concurrent-faster-qwen3-server)** & **[second-state/qwen3_tts_rs](https://github.com/second-state/qwen3_tts_rs)** (**2026, Maturity: Medium**):
   - Rust/CUDA wrappers providing concurrent batched streaming and OpenAI-compatible HTTP endpoints.
3. **[vllm-project/vllm-omni](https://github.com/vllm-project/vllm-omni)** & **[ggml-org/llama.cpp (`llama-server`)](https://github.com/ggml-org/llama.cpp/pull/26603)** (**Maturity: High**):
   - `vllm-omni` supports OpenAI-compatible `/v1/audio/speech` chunked PCM streaming and WebSockets.
   - `llama-server` (since PR `#26603`, Aug 2026) supports streaming `/tts` with GGUF models.

---

## 3. Is `Qwen3-TTS-12Hz-0.6B-Base` Much Faster With Acceptable Voice Cloning Quality?

### Speed Comparison (0.6B vs. 1.7B)
- **Not 3× faster—about 15% to 35% faster once CUDA graphs are enabled:**
  - Why? Both `0.6B` and `1.7B` share the exact same 12.5 Hz frame rate, the 15-step autoregressive `CodePredictor` architecture, and the exact same `Qwen3-TTS-Tokenizer-12Hz` (`Code2Wav`) vocoder. Only the Talker LLM backbone shrinks.
  - In `faster-qwen3-tts` benchmarks on RTX 4090:
    - **1.7B:** RTF **0.237** (4.22× real-time), TTFA **174 ms**
    - **0.6B:** RTF **0.180–0.209** (4.78–5.56× real-time), TTFA **156 ms** (~10–24% faster)
  - On bandwidth/compute-constrained GPUs (RTX 4060):
    - **1.7B:** RTF **0.546** (1.83× real-time), TTFA **460 ms**
    - **0.6B:** RTF **0.442** (2.26× real-time), TTFA **413 ms** (~19% faster)
- **VRAM Footprint:** `0.6B` uses **~3.5–4.5 GB VRAM** (vs. **~7.5–9.5 GB VRAM** for `1.7B` with static caches and CUDA graphs). On a 12 GB RTX 5070, `0.6B` is critical if you also run an ASR model (e.g., Whisper/Qwen3-ASR) or LLM on the same GPU.

### Voice Cloning Quality Comparison (`arXiv:2601.15621` Table 5 & Community Reports)
- **Objective Intelligibility (Seed-TTS-Eval Zero-Shot Voice Cloning):**
  - `Qwen3-TTS-12Hz-1.7B-Base`: **`test-en` WER = 1.24%**, **`test-zh` CER = 0.77%**
  - `Qwen3-TTS-12Hz-0.6B-Base`: **`test-en` WER = 1.32%**, **`test-zh` CER = 0.92%**
  - Both models beat original Seed-TTS (`2.25%` EN WER) and F5-TTS (`1.83%` EN WER), and WavLM speaker similarity (SIM) is very close (~0.70–0.77).
- **Subjective / Practical Differences:**
  - For **short, conversational English assistant responses (1–3 sentences)** with a clean 3–10s reference clip, `0.6B-Base` timbre similarity is nearly indistinguishable from `1.7B-Base`.
  - Where `0.6B-Base` degrades compared to `1.7B-Base`: complex multi-sentence prosody/emphasis, emotional nuance, non-English/cross-lingual cloning, and higher risk of pacing/pitch drift on utterances longer than ~15–20 seconds.

---

## 4. Known Issues on Blackwell (`sm_120`) and WSL2

1. **FlashAttention-3 & FlashAttention-4 Do NOT Run on Consumer Blackwell (`sm_120`):**
   - Datacenter Blackwell (B200) is `sm_100` (with TMEM and `tcgen05` instructions), whereas Hopper (H100) is `sm_90` (with WGMMA). Consumer RTX 50-series cards (RTX 5070/5080/5090) are **`sm_120`**, which **lacks both Hopper's WGMMA and B200's TMEM/`tcgen05`**.
   - Attempting to run FA3 or FA4 kernels on RTX 5070 fails with `CUDA error: invalid argument` or architecture mismatch ([vLLM/SGLang sm_120 tracking issues](https://github.com/vllm-project/vllm)).
   - Standard `pip install flash-attn` often lacks prebuilt `sm_120` + CUDA 13.x (`cu132`) + Python 3.12 wheels, throwing `CUDA error: no kernel image is available for execution on the device`. You must either stay on PyTorch's native **`sdpa` (cuDNN FlashAttention backend in PyTorch 2.7+/2.15, which natively supports `sm_120`)**, use **FlashInfer**, or compile `flash-attn` from source with `TORCH_CUDA_ARCH_LIST="12.0"`.
2. **WSL2 CUDA Graph Capture Crashes / Hang Issues on Blackwell:**
   - Earlier WSL2 releases (< 2.6/2.7) had `dxgkrnl` paravirtualization bugs with Blackwell (`sm_120`) that caused `cudaErrorUnknown` or freezes during **CUDA Graph capture** (`torch.cuda.CUDAGraph`) and `torch.compile` autotuning.
   - **Fix:** Ensure Windows host has a recent NVIDIA Game Ready / Studio driver and run `wsl --update` (WSL2 **2.7.0+** resolves the `dxgkrnl` graph-capture race).
3. **12 GB VRAM Spillover into Shared System Memory on WSL2 (Silent 5–10× Slowdown):**
   - Unlike native Linux (which throws `OutOfMemoryError` at 12.0 GB), WSL2 uses Windows WDDM virtual memory and **silently spills CUDA allocations over 12 GB into PCIe host RAM**.
   - If you capture CUDA graphs for multiple batch sizes or run `1.7B` alongside another model on the 12 GB RTX 5070, pushing VRAM above ~11.2 GB will cause WDDM paging over PCIe, destroying RTF (spiking RTF from 0.3 to >2.0).
4. **Triton / `torch.compile` PTX Arch Support (`sm_120`):**
   - Older bundled `triton` packages fail when compiling kernels for `sm_120` (`ValueError: GPU arch sm_120 not supported by ptxas`). With PyTorch 2.15 (`cu132`), ensure the bundled `ptxas` from CUDA 13.x is on `PATH` (`TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas`).

---

## 5. Recommended Path for This Machine (In Order, With Main Risk of Each Step)

### Step 1: Switch to `faster-qwen3-tts` (Static KV Cache + CUDA Graphs) With Your Current `1.7B-Base` Model & `sdpa`
- **Action:** Keep your existing PyTorch 2.15 (`cu132`), `attn_implementation="sdpa"`, bfloat16, and `Qwen3-TTS-12Hz-1.7B-Base` weights, and run inference via [`andimarafioti/faster-qwen3-tts`](https://github.com/andimarafioti/faster-qwen3-tts) (or [`dffdeeq/Qwen3-TTS-streaming`](https://github.com/dffdeeq/Qwen3-TTS-streaming)) using its streaming generator (`chunk_size=6` or `8` frames, or two-phase chunking) and cached `voice_clone_prompt`.
- **Expected Result on RTX 5070:** Drops RTF from **~1.3 → ~0.30–0.40** (~2.5–3.3× faster than real-time) and delivers true streaming audio with **TTFA ~220–280 ms** (well under your 500 ms target) without needing `flash-attn` or leaving Python.
- **Main Risk:** **WSL2 CUDA Graph capture instability or WDDM 12 GB VRAM spillover.** If your WSL2 kernel is older than 2.7.0, CUDA graph capture on `sm_120` can fail; additionally, capturing graphs on the 1.7B model consumes ~8–9.5 GB VRAM, leaving only ~2.5 GB headroom on the RTX 5070 before WDDM silently pages to system RAM.

### Step 2: Benchmark `Qwen3-TTS-12Hz-0.6B-Base` in the Same CUDA-Graphed Streaming Pipeline
- **Action:** Swap the model ID to `Qwen/Qwen3-TTS-12Hz-0.6B-Base` with the exact same `voice_clone_prompt` reference audio (trimmed to a clean 3–6 second clip) and compare A/B voice similarity and latency.
- **Expected Result on RTX 5070:** Drops RTF further to **~0.22–0.30** and **TTFA to ~180–220 ms**, while cutting VRAM usage from ~8.5 GB to **~4 GB** (eliminating any risk of 12 GB WDDM spillover on WSL2).
- **Main Risk:** **Prosody flatness or speaking-rate drift on longer/expressive responses.** While English WER (`1.32%` vs `1.24%`) and short-utterance timbre are nearly identical to 1.7B, 0.6B has less expressive pitch contour on multi-sentence turns and non-English text.

### Step 3: Add Two-Phase Chunking + Hann Crossfading & Sentence-Prefix Pipelining
- **Action:** Emit the first audio chunk after **2–4 codec frames (160–320 ms of audio)** for immediate voice onset, then switch to **8–12 frames** for subsequent chunks with a short Hann crossfade window (as implemented in `dffdeeq/Qwen3-TTS-streaming`), and feed the LLM's first clause (split at the first comma/period) rather than waiting for the full LLM response.
- **Expected Result on RTX 5070:** Drives TTFA down to **~120–180 ms** from the moment the first clause is ready.
- **Main Risk:** **Boundary clicks or first-chunk acoustic artifacts.** Decoding very small initial chunks (1–2 frames) through `Code2Wav` without proper left-context carryover or Hann window crossfading produces audible pops at the chunk seam.

### Step 4: (Only If You Need Multi-Stream Serving or Even Lower Footprint) Move to `llama-server` (GGUF) or `vllm-omni`
- **Action:**
  - If you want a standalone C++ binary with minimal VRAM (~4–5 GB for 1.7B): use mainline **`llama.cpp` (`llama-server --tts`)** with `ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF` (PR `#26254` / `#26603`).
  - If you need high-concurrency OpenAI-compatible serving: deploy **`vllm-project/vllm-omni`** with `codec_streaming: true` and `code_predictor_prefix_graphs`.
- **Main Risk:**
  - For **`llama.cpp` GGUF**: Quantizing the Talker below `Q8_0` (e.g., `Q4_K_M`) can subtly degrade zero-shot voice clone similarity compared to BF16.
  - For **`vllm-omni`**: High memory and dependency complexity on a 12 GB WSL2 card (`sm_120` custom wheel builds + dual-stage Stage 0 / Stage 1 process memory overhead).

---
