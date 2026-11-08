# More natural voice for Jorah: TTS research

Research by Antigravity (Gemini 4 Argon High), 2026-11-08. Claude checked on Hugging Face: Qwen3-TTS 12Hz 0.6B and 1.7B (CustomVoice, Base, VoiceDesign) exist, created 2026-01-21, Apache-2.0; ResembleAI/chatterbox-turbo exists, 2025-12-02, MIT. Other figures (latency, VRAM, arena scores) are the worker's, unchecked. The multi-sentence chunking it recommends for Kokoro was done the same day.

# Research Report: Natural Text-to-Speech (TTS) Engines vs. Kokoro v1.0 (82M)

**Reference Date:** 2026-11-08  
**Target Hardware & Baseline:** Windows 11 + WSL2 (Ubuntu 24.04), Intel i7-14700K, NVIDIA RTX 5070 (12 GB GDDR7, Blackwell `sm_120`). Currently running `sherpa-onnx` with **Kokoro v1.0 (82M, voice `bm_daniel`, speed 1.2)** sentence-by-sentence over WebSocket alongside **NVIDIA Parakeet ASR** (`parakeet-tdt-0.6b-v2` / `1.1b`).

---

## Hardware & Co-Residency Baseline (RTX 5070 12 GB + Parakeet + WSL2)

Before evaluating individual models, three system-level constraints govern what fits and runs reliably on this machine:

1. **VRAM Budget with Parakeet Co-Residency:**
   * Running `parakeet-tdt-0.6b` via `sherpa-onnx` uses **~1.2–1.4 GB VRAM** (INT8) or **~1.8–2.8 GB VRAM** (FP16/FP32) including ONNX Runtime CUDA arena buffers ([sherpa-onnx docs](https://k2-fsa.github.io/sherpa/onnx/nemo/parakeet-tdt.html)). `parakeet-tdt-1.1b` uses **~2.0–2.5 GB** (INT8) or **~5.5 GB** (FP32).
   * Allowing ~1.0 GB for WSL2/CUDA context overhead and ~1.5–2.5 GB for Parakeet leaves **~8.5–9.5 GB of usable VRAM** for the TTS engine and its KV-cache.
2. **Blackwell (`sm_120`) Kernel Compatibility:**
   * The RTX 5070 uses compute capability `sm_120`. PyTorch builds compiled for CUDA $\le$ 12.6 fail with `RuntimeError: CUDA error: no kernel image is available for execution on the device`.
   * **Requirement:** WSL2 Ubuntu 24.04 must run **PyTorch $\ge$ 2.7 / CUDA 12.8 (`cu128`) or CUDA 12.9** ([PyTorch Forums](https://discuss.pytorch.org/t/nvidia-geforce-rtx-5070-with-cuda-capability-sm-120-is-not-compatible/216518)). Custom extensions (`flash-attn`, `triton`, `mamba-ssm`) frequently require building with `TORCH_CUDA_ARCH_LIST="12.0"` or falling back to PyTorch native `sdpa` (Scaled Dot-Product Attention).
   * `onnxruntime-gpu` wheels compiled against older CUDA versions silently fall back to `CPUExecutionProvider` on `sm_120` unless linked against CUDA 12.8+ `cublasLt` ([ONNX Runtime GitHub](https://github.com/microsoft/onnxruntime/issues)).
3. **Why Kokoro v1.0 Sounds Flat:**
   * Kokoro v1.0 (82M) is an encoder-decoder StyleTTS2 derivative without an autoregressive LLM backbone or cross-utterance acoustic memory, and its hard context ceiling is **510 phoneme tokens (~30–40 seconds of audio)** ([hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)). Synthesising one sentence at a time resets the prosodic contour on every sentence, producing uniform cadence.

---

## Part A: Local TTS Models for the RTX 5070 (12 GB)

Below are the 15 requested model families plus two 2026 open-weight listening-test leaders (**Qwen3-TTS** and **Fun-CosyVoice 3.0**). All ages are calculated relative to **2026-11-08**.

---

### 1. Chatterbox & Chatterbox Turbo (Resemble AI)
1. **Release & Licence:**
   * **Original Chatterbox (500M):** Released May 28, 2025 (~17 months old).
   * **Chatterbox Turbo (350M):** Released December 15, 2025 (~10.5 months old).
   * **Chatterbox Multilingual v3 (500M):** Released mid-2026 (~5 months old).
   * **Licence:** **MIT License** ([resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox), [Resemble AI HF](https://huggingface.co/ResembleAI/chatterbox-turbo)). Unrestricted personal and commercial use; no special voice-cloning prohibition beyond general legal compliance.
2. **Size, VRAM & Co-residency:**
   * **Turbo (350M):** ~1.5–2.2 GB VRAM for weights, **~3.5–4.5 GB active VRAM** in FP16/BF16.
   * **Original (500M):** **~5.0–6.0 GB active VRAM** in FP16.
   * **Fits with Parakeet in 12 GB?** **Yes, easily** (leaves 5–6 GB spare). Community ONNX/GGUF quantised exports exist (`onnx-community/chatterbox-onnx`), though native BF16 fits comfortably without quantisation.
3. **Streaming, TTFA & RTF:**
   * **Original Chatterbox** lacked native token streaming at launch (relied on community chunked wrappers).
   * **Chatterbox Turbo** distils the acoustic flow-matching decoder from 10 steps to **1 step**, achieving **<150 ms–200 ms TTFA** and **RTF ~0.16 (~6× real-time)** on consumer RTX 4090/5070-class GPUs ([Resemble AI HF](https://huggingface.co/ResembleAI/chatterbox-turbo)).
4. **Naturalness Evidence:**
   * In blind Podonos human preference tests at launch, testers preferred Chatterbox over ElevenLabs **63.75%** of the time ([Resemble AI GitHub](https://github.com/resemble-ai/chatterbox)). Consistently ranks in the **top 3 open-weight models** on Hugging Face **TTS Arena V2** and Artificial Analysis Speech Arena (Elo ~1,100–1,140 bracket, ahead of Kokoro-82M's ~1,060) ([TTS Arena V2](https://huggingface.co/spaces/TTS-AGI/TTS-Arena-V2)).
5. **Prosody Across Sentences & Style Control:**
   * Handles multi-sentence conversational turns (~40 seconds / 300–400 words per pass) with strong pitch variation.
   * **Original 500M** exposes first-of-its-kind `exaggeration` (0.0–1.0+) and `cfg_weight` sliders to dial emotional intensity from flat to dramatic.
   * **Turbo 350M** adds native inline paralinguistic tags: `[laugh]`, `[chuckle]`, `[cough]`, `[sigh]`, `[gasp]`, `[clear throat]`, `[groan]`, `[shush]` ([ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo)).
6. **Voices & Safety/Watermarking:**
   * Ships with a default conditioned voice and supports **zero-shot voice cloning** from a 5–10 second `.wav` reference.
   * **Watermark:** Embeds Resemble AI's imperceptible **PerTh (Perceptual Threshold)** neural watermark into all outputs by default ([resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox)). Because the code is MIT-licensed Python, the watermark step is visible in the inference pipeline.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch** (BF16/FP16) and **ONNX**. Works cleanly on RTX 5070 under WSL2 with PyTorch 2.7+ (`cu128`) using native PyTorch `sdpa` (no mandatory `mamba-ssm` compilation).

---

### 2. Qwen3-TTS (Alibaba Qwen Team) — *2026 Open-Weight Leader*
1. **Release & Licence:**
   * Released **January 21–22, 2026** (~9.5 months old). Latest checkpoints: `Qwen3-TTS-12Hz-1.7B` and `Qwen3-TTS-12Hz-0.6B` (`CustomVoice`, `VoiceDesign`, and `Base` variants).
   * **Licence:** **Apache 2.0** ([QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [arXiv:2601.15621](https://arxiv.org/abs/2601.15621)). Permissive commercial and personal use.
2. **Size, VRAM & Co-residency:**
   * **0.6B variant:** **~3.5–4.5 GB VRAM** in BF16.
   * **1.7B variant:** **~6.0–8.0 GB VRAM** in BF16 (with `Qwen3-TTS-Tokenizer-12Hz` loaded).
   * **Fits with Parakeet in 12 GB?** **0.6B fits with 6+ GB to spare; 1.7B fits comfortably alongside Parakeet INT8 (~8.5–9.5 GB combined).** Also supports GGUF/AWQ quantisation.
3. **Streaming, TTFA & RTF:**
   * Uses a non-DiT dual-track architecture operating on a **12.5 Hz single-frame-rate tokenizer** (`Qwen3-TTS-Tokenizer-12Hz`), bypassing multi-step diffusion delays.
   * **TTFA:** **97 ms** (0.6B) to **~101–150 ms** (1.7B) first-packet latency; **RTF ~0.15–0.30** on consumer RTX GPUs with FlashAttention-2 / CUDA graphs ([Qwen Blog](https://qwen.ai), [faster-qwen3-tts](https://github.com/QwenLM/Qwen3-TTS)).
4. **Naturalness Evidence:**
   * Top-tier open-weight contender on **Artificial Analysis Speech Arena** and **TTS Arena V2** in 2026, achieving SOTA Word Error Rate (WER) on Seed-TTS-Eval and matching commercial APIs in blind multi-sentence conversational evaluations ([Artificial Analysis](https://artificialanalysis.ai/text-to-speech/leaderboard)).
5. **Prosody Across Sentences & Style Control:**
   * Built directly on a Qwen3 LLM backbone, it accepts **full paragraphs and multi-sentence context**, dynamically adjusting prosody, emphasis, and pacing based on semantic meaning across sentence boundaries.
   * Supports **natural-language style instructions** (e.g., *"Speak warmly with a slight sigh of relief, then shift to an upbeat tone"*).
6. **Voices & Safety/Watermarking:**
   * **`CustomVoice`:** 9 curated preset voices (including English presets *Ryan, Aiden, Vivian, Serena, Dylan, Eric*).
   * **`VoiceDesign`:** Generates brand-new voices from text descriptions.
   * **`Base`:** 3-second zero-shot voice cloning. No mandatory acoustic watermark in official Apache-2.0 weights.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch**, **vLLM**, and community **GGUF/llama.cpp** backends. On RTX 5070 (`sm_120`), either compile `flash-attn` with `TORCH_CUDA_ARCH_LIST="12.0"` or set `attn_implementation="sdpa"` in Transformers.

---

### 3. Kokoro v1.1 / v1.0 Baseline Reference (hexgrad) — *For Context*
* **Kokoro v1.0** (Jan 2025, ~21.5 months old) and **Kokoro v1.1** (Feb 2025, ~20.5 months old; adds Chinese/extra voices) remain the efficiency king (~300 MB VRAM, RTF < 0.05 on GPU, ~1,060 Elo on TTS Arena V2), but its 82M non-LLM StyleTTS2 architecture cannot match the cross-sentence semantic prosody of 0.5B–3B speech-LLMs. (See **Part C** for low-effort fixes to the current Kokoro setup.)

---

### 4. Orpheus TTS (Canopy Labs)
1. **Release & Licence:**
   * Released **March 18, 2025** (~19.5 months old; multilingual research previews in April 2025). Checkpoints: `orpheus-3b-0.1-ft`, plus smaller `1b`, `400m`, and `150m` variants.
   * **Licence:** Code is **Apache 2.0**; weights inherit the **Meta Llama 3.2 Community License** (free for personal and commercial use up to 700M monthly active users) ([canopyai/Orpheus-TTS](https://github.com/canopyai/Orpheus-TTS)).
2. **Size, VRAM & Co-residency:**
   * **3B (BF16):** ~6.5 GB weights; with vLLM KV-cache + SNAC audio decoder takes **~8.5–10.5 GB VRAM**.
   * **3B Quantised (GGUF `Q4_K_M` or `Q8_0`):** **~2.5 GB (`Q4_K_M`) to ~4.2 GB (`Q8_0`) VRAM** including SNAC decoder ([isaiahbjork/orpheus-tts-local](https://github.com/isaiahbjork/orpheus-tts-local)).
   * **Fits with Parakeet in 12 GB?** **Tight in BF16/vLLM** (risks OOM unless `gpu_memory_utilization` is capped at ~0.65), but **fits easily in GGUF `Q8_0` or `Q4_K_M`** (~5.5 GB total with Parakeet).
3. **Streaming, TTFA & RTF:**
   * Native token streaming via SNAC codec (7 tokens per frame, ~83 tokens/sec required for 1.0× real-time).
   * **TTFA:** **~150–200 ms** on consumer RTX GPUs (~100 ms with input streaming); **RTF ~0.35–0.50** (~2–3× real-time) on RTX 4090/5070 via `llama.cpp` or `vLLM` ([Canopy Labs GitHub](https://github.com/canopyai/Orpheus-TTS)).
4. **Naturalness Evidence:**
   * Widely praised in blind community evaluations and **TTS Arena V2** (~1,070–1,090 Elo range) for conversational micro-inflections and naturalistic cadence, though occasionally prone to typical autoregressive LLM repetitions/hallucinations on uncleaned text.
5. **Prosody Across Sentences & Style Control:**
   * Llama-3.2-3B backbone understands multi-sentence semantics and carries conversational tone across a paragraph (best kept under ~400–500 characters per pass to avoid SNAC token drift).
   * Native inline emotion/paralinguistic tags: `<laugh>`, `<chuckle>`, `<sigh>`, `<cough>`, `<sniffle>`, `<groan>`, `<yawn>`, `<gasp>`.
6. **Voices & Safety/Watermarking:**
   * **Preset Voices:** 8 built-in English voices (`tara`, `leah`, `jess`, `mia`, `zoe`, `dan`, `leo`, `zac`) in the `-ft` checkpoint.
   * **Zero-Shot Cloning:** Supported via the base (`orpheus-3b-0.1-pretrained`) checkpoint or few-shot audio-prompt scripts.
   * **Watermarking:** None embedded.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **vLLM**, **llama.cpp / GGUF** (LM Studio, Ollama, `llama-cpp-python`) + PyTorch/ONNX **SNAC** vocoder.
   * **Blackwell Note:** Upstream `orpheus-speech` Python package pins an older `vllm==0.7.3` wheel that lacks `sm_120` support! On RTX 5070, use **llama.cpp (CUDA 12.8 build) with GGUF weights** or a current **vLLM $\ge$ 0.8.5+** container instead of the pinned `vllm==0.7.3` wheel.

---

### 5. Sesame CSM (`csm-1b` — Sesame AI Labs)
1. **Release & Licence:**
   * Released **March 13, 2025** (~20 months old); integrated natively into Hugging Face `transformers` v4.52.1 in May 2025.
   * **Licence:** **Apache 2.0** ([SesameAILabs/csm](https://github.com/SesameAILabs/csm), [sesame/csm-1b](https://huggingface.co/sesame/csm-1b)). Commercial and personal use permitted; model card prohibits non-consensual impersonation and deceptive fraud.
2. **Size, VRAM & Co-residency:**
   * **1.55B total parameters** (1B Llama text/zeroth-codebook backbone + 100M audio depth decoder + Mimi RVQ codec).
   * Uses **~4.5–6.5 GB VRAM** in BF16 (scales up to ~8–9 GB with long multi-turn audio history in context).
   * **Fits with Parakeet in 12 GB?** **Yes** (uses ~6–8 GB combined with Parakeet INT8). Quantised INT8/INT4 (`torchao`) options reduce VRAM to ~3.5 GB.
3. **Streaming, TTFA & RTF:**
   * Official repo initially shipped batch generation only; community streaming forks (`davidbrowne17/csm-streaming`) and HF `transformers` streaming achieve **TTFA ~250–400 ms** and **RTF ~0.40–0.75** on RTX 4090/5070 ([csm-streaming GitHub](https://github.com/davidbrowne17/csm-streaming)). Note: Because the 100M depth decoder runs sequentially across 31 RVQ codebooks per 80 ms Mimi frame, `torch.compile` is mandatory to stay faster than real-time.
4. **Naturalness Evidence:**
   * In Sesame's paper and independent blind evaluations ([arXiv:2503.07550](https://arxiv.org/abs/2503.07550)), `csm-1b` achieves near-human CMOS scores when conditioned on conversational history, though isolated single-sentence zero-shot clips on TTS Arena V2 score lower than the viral closed-source "Maya/Miles" web demo (which used a larger proprietary model + fine-tuned studio dataset).
5. **Prosody Across Sentences & Style Control:**
   * **Best-in-class conversational memory design:** Accepts a list of prior `Segment(speaker, text, audio)` turns (~2-minute context window). Tone, pacing, and pitch naturally adapt to the preceding user/assistant dialogue history.
   * No explicit emotion sliders; style is steered purely by acoustic context prompts and punctuation.
6. **Voices & Safety/Watermarking:**
   * Base `csm-1b` has **no fixed preset voices**; you must supply 1–3 reference audio segments (`Segment`) as a prompt prefix (or use community fine-tunes).
   * **Watermark:** Official `SesameAILabs/csm` inference code integrates **SilentCipher** audio watermarking by default ([SesameAILabs/csm](https://github.com/SesameAILabs/csm)).
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch / HF Transformers** (`torch.compile` required for speed) and community **GGUF** ports. On RTX 5070 WSL2, requires Triton 3.2+ / PyTorch 2.7+ (`cu128`) so `torch.compile(mode="reduce-overhead")` can compile CUDA kernels for `sm_120`.

---

### 6. Kyutai TTS (Delayed Streams Modeling 1.6B & Pocket TTS 100M)
1. **Release & Licence:**
   * **Kyutai TTS 1.6B (`kyutai/tts-1.6b-en_fr`):** Released **July 3, 2025** (~16 months old).
   * **Kyutai Pocket TTS (100M, `kyutai/pocket-tts`):** Released **January 13, 2026** (~10 months old), with v4.0 micro variants (18M/7M/2M) released **October 20, 2026** (~3 weeks old).
   * **Licence:** Code is **MIT / Apache 2.0**; model weights are **CC-BY 4.0** ([kyutai-labs/delayed-streams-modeling](https://github.com/kyutai-labs/delayed-streams-modeling), [kyutai-labs/pocket-tts](https://github.com/kyutai-labs/pocket-tts)). Commercial and personal use permitted with attribution.
2. **Size, VRAM & Co-residency:**
   * **Kyutai TTS 1.6B:** **~4.5–6.0 GB VRAM** in BF16. Fits easily alongside Parakeet in 12 GB.
   * **Pocket TTS 100M:** Runs natively on **CPU (i7-14700K)** using **0 GB GPU VRAM** (~300 MB system RAM), leaving 100% of the RTX 5070 for ASR/other workloads!
3. **Streaming, TTFA & RTF:**
   * **True bi-streaming architecture:** Delayed Streams Modeling (DSM) aligns text and Mimi audio tokens on a shared 12.5 Hz frame grid so audio streams out **while input text is still arriving token-by-token from the LLM** (no need to wait for a full sentence!).
   * **Kyutai TTS 1.6B (GPU):** **TTFA ~220 ms**, **RTF ~0.20–0.30** (3–5× real-time) ([Kyutai DSM GitHub](https://github.com/kyutai-labs/delayed-streams-modeling)).
   * **Pocket TTS 100M (CPU on i7-14700K):** **TTFA ~200 ms**, **RTF ~0.16 (~6× real-time on 2 CPU cores)** ([Kyutai Pocket TTS](https://kyutai.org/next/pocket-tts)).
4. **Naturalness Evidence:**
   * Evaluated in Kyutai's DSM benchmarks ([arXiv:2509.08753](https://arxiv.org/abs/2509.08753)) and independent blind MUSHRA tests: `Pocket TTS 100M` and `Kyutai 1.6B` beat Kokoro-82M on multi-sentence flow and word error rate (WER 1.8% vs Kokoro's ~2.4%) while matching or exceeding CSM-1B naturalness.
5. **Prosody Across Sentences & Style Control:**
   * **Solves the sentence-boundary problem architecturally:** Because DSM is a continuous stream model, you can pipe the LLM's token stream directly into Kyutai TTS across an entire multi-sentence response without ever splitting sentences or resetting state.
   * Style/emotion is conditioned via voice reference audio (from the *Unmute* conversational dataset).
6. **Voices & Safety/Watermarking:**
   * Comes with dozens of CC0 preset voices from Kyutai's *Unmute Voice Donation Project* (`alba`, `marius`, `javert`, `jean`, `cosette`, etc.) and supports **zero-shot voice cloning** from 5–10s audio.
   * **Watermark:** No hidden acoustic watermark. *(Note: Initially Kyutai withheld the raw voice-embedding extractor script on 1.6B for safety, releasing pre-computed voice embeddings; Pocket TTS includes open zero-shot voice cloning).*
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * **1.6B:** PyTorch, Rust (`candle` server).
   * **Pocket TTS 100M:** Pure PyTorch CPU (no CUDA dependencies at all, immune to `sm_120` issues).

---

### 7. Dia (1.6B) & Dia2 (1B / 2B) (Nari Labs)
1. **Release & Licence:**
   * **Dia-1.6B:** Released **April 21, 2025** (~18.5 months old; updated checkpoint `Dia-1.6B-0626` in June 2025).
   * **Dia2 (`Dia2-1B`, `Dia2-2B`):** Released **November 2025** (~12 months old).
   * **Licence:** **Apache 2.0** ([nari-labs/dia](https://github.com/nari-labs/dia), [nari-labs/dia2](https://github.com/nari-labs/dia2)). Commercial and personal use allowed.
2. **Size, VRAM & Co-residency:**
   * **Dia-1.6B:** ~7.5–10.0 GB VRAM in BF16/FP16.
   * **Dia2-1B / Dia2-2B:** **~5.5 GB (1B) to ~9.5–10.0 GB (2B) VRAM** in BF16 with CUDA graphs.
   * **Fits with Parakeet in 12 GB?** **Dia2-1B fits comfortably (~7 GB total); Dia2-2B and Dia-1.6B are tight (~11–11.5 GB total)** and can OOM on long generations alongside Parakeet unless Parakeet runs on CPU or INT8.
3. **Streaming, TTFA & RTF:**
   * **Dia-1.6B:** **No streaming** (batch-only; generates 5–20s chunks at once using Descript Audio Codec, TTFA > 1.5–3.0s).
   * **Dia2 (1B/2B):** Rebuilt on Kyutai's **Mimi 12.5 Hz delayed-streams architecture**; streams audio after the first few words with **TTFA ~250–350 ms** and **RTF ~0.40–0.60** on RTX 4090/5070 with `bfloat16` + CUDA graphs ([nari-labs/dia2](https://github.com/nari-labs/dia2)).
4. **Naturalness Evidence:**
   * Dia-1.6B ranked highly on TTS Arena V2 for expressive dialogue (~1,075 Elo), praised for hyper-realistic conversational banter and non-verbals, though single-speaker assistant reading sometimes sounded overly dramatic or varied in speed unless anchored with an audio prefix.
5. **Prosody Across Sentences & Style Control:**
   * Designed specifically for multi-sentence dialogue scripts (`[S1]`, `[S2]`). Dia2 carries prosody continuously across sentences in a streaming session.
   * Supports rich non-verbal tags in Dia-1.6B: `(laughs)`, `(coughs)`, `(sighs)`, `(clears throat)`, `(gasps)`.
6. **Voices & Safety/Watermarking:**
   * **No fixed preset voice by default** (random voice unless seeded or given an audio prefix). Requires a **5–10s audio prefix + transcript** to lock in a consistent assistant voice.
   * **Watermarking:** None embedded.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch (`bfloat16` + CUDA Graphs)**. Requires PyTorch 2.7+ (`cu128`) on RTX 5070 (`sm_120`).

---

### 8. F5-TTS (SWivid)
1. **Release & Licence:**
   * Initial release **October 2024**; **F5-TTS v1 Base** released **March 12, 2025** (~20 months old).
   * **Licence:** Code is **MIT**; pretrained weights (`F5TTS_v1_Base`) are **CC-BY-NC-4.0 (Non-Commercial only)** due to Emilia dataset licensing ([SWivid/F5-TTS](https://github.com/SWivid/F5-TTS)). **Fine for private personal use**, prohibited for commercial use.
2. **Size, VRAM & Co-residency:**
   * **335.8M parameters** (~1.35 GB safetensors). Uses **~2.5–4.0 GB VRAM** in FP16 during inference (provided you pass `ref_text` explicitly so it doesn't load Whisper ASR into VRAM).
   * **Fits with Parakeet in 12 GB?** **Yes, easily** (~4–5.5 GB combined). ONNX/TensorRT quantised options available.
3. **Streaming, TTFA & RTF:**
   * Non-autoregressive Flow-Matching Diffusion Transformer (DiT) with ConvNeXt + Sway Sampling + Vocos vocoder.
   * Because DiT generates a whole chunk holistically across $N$ ODE steps (typically 16–32 NFE), "streaming" is actually **chunked batch generation**: **TTFA ~250–450 ms** (on RTX 5070/4090 with `torch.compile`), **RTF ~0.10–0.15** (~7–10× real-time) ([SWivid/F5-TTS](https://github.com/SWivid/F5-TTS)).
4. **Naturalness Evidence:**
   * Long-standing benchmark reference on **TTS Arena V2** (Elo ~1,040–1,060, roughly tied with or slightly below Kokoro-82M in blind default preference, though much stronger on zero-shot voice similarity SIM-o = 0.66) ([Seed-TTS-Eval](https://github.com/SWivid/F5-TTS)).
5. **Prosody Across Sentences & Style Control:**
   * **Limitation for your goal:** F5-TTS splits inputs $>15\text{–}30$ seconds into chunks and cross-fades them. While within-chunk prosody is very natural and mirrors the reference audio's cadence, cross-chunk tonal evolution is limited compared to LLM-based TTS models.
   * Emotion control requires swapping reference audio clips (e.g., `[Angry]`, `[Happy]` reference clips).
6. **Voices & Safety/Watermarking:**
   * Pure **zero-shot voice cloning** (requires a 5–15s reference audio file + reference transcript). No built-in preset voice table. No acoustic watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch**, **ONNX**, and **TensorRT-LLM**. Very stable on RTX 5070 under PyTorch `cu128`.

---

### 9. Fish Speech v1.5 / OpenAudio S1 & S1-mini (Fish Audio)
1. **Release & Licence:**
   * **Fish Speech v1.5:** Released December 2024 (~23 months old).
   * **OpenAudio S1 (4B) & OpenAudio S1-mini (0.5B):** Released **June 3, 2025** (~17 months old). *(Note: Only **S1-mini (0.5B)** has open weights on Hugging Face (`fishaudio/openaudio-s1-mini`); the 4B S1 model is API-only).*
   * **Licence:** Weights (`fishaudio/openaudio-s1-mini`) are **CC-BY-NC-SA-4.0 (Non-Commercial ShareAlike)** ([fishaudio/openaudio-s1-mini](https://huggingface.co/fishaudio/openaudio-s1-mini)). **Permitted for private personal use**, not commercial.
2. **Size, VRAM & Co-residency:**
   * **OpenAudio S1-mini (0.5B):** Dual-AR Transformer + DAC codec. Uses **~3.5–5.0 GB VRAM** in BF16/FP16.
   * **Fits with Parakeet in 12 GB?** **Yes, easily** (~5–6.5 GB combined).
3. **Streaming, TTFA & RTF:**
   * Supports native HTTP/WebSocket streaming via its built-in server (`tools.run_webui` / `api_server.py` with `--compile`).
   * **TTFA:** **~150–300 ms** on consumer RTX GPUs (once `torch.compile` warm-up completes); **RTF ~0.15–0.25** (~4–6× real-time) ([Fish Speech Docs](https://speech.fish.audio/)).
4. **Naturalness Evidence:**
   * Full **OpenAudio S1 (4B)** hit **#1 overall on Hugging Face TTS Arena V2** in June 2025; the open-weight **S1-mini (0.5B)** achieved a 0.8% WER on Seed-TTS-Eval and ranks in the top tier of open-weight models on TTS Arena V2 (~1,085–1,110 Elo), clearly outperforming Kokoro-82M on emotional expressiveness ([OpenAudio S1 Technical Report](https://openaudio.com)).
5. **Prosody Across Sentences & Style Control:**
   * Strong multi-sentence continuity via its Dual-AR LLM backbone ( trained with RLHF/DPO for prosody alignment).
   * **Rich inline emotion & tone markers:** Supports `(angry)`, `(sad)`, `(excited)`, `(surprised)`, `(whispering)`, `(shouting)`, `(laughing)`, `(chuckling)`, `(sighing)`, `(panting)` anywhere in the text ([Fish Speech Docs](https://speech.fish.audio/)).
6. **Voices & Safety/Watermarking:**
   * Zero-shot cloning from 10–30s reference audio (can pre-encode and save `.npy` reference tokens to act as instant "preset" voices). No mandatory audible watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch (`torch.compile`)** and **ONNX**. Requires PyTorch 2.7+ (`cu128`) on RTX 5070 (`sm_120`); first inference pass after startup takes ~30–60s to compile Triton kernels unless kernel caching is enabled.

---

### 10. Zonos v0.1 (1.6B) & ZONOS2 (8B MoE) (Zyphra)
1. **Release & Licence:**
   * **Zonos v0.1 (1.6B Transformer & Hybrid):** Released **February 12, 2025** (~21 months old).
   * **ZONOS2 (8B MoE, 900M active):** Paper/release **June 2026** (~5 months old) ([arXiv:2606.09319](https://arxiv.org/abs/2606.09319)).
   * **Licence:** **Apache 2.0** ([Zyphra/Zonos](https://github.com/Zyphra/Zonos)). Permissive personal and commercial use.
2. **Size, VRAM & Co-residency:**
   * **Zonos v0.1 (1.6B):** Uses **~5.0–6.5 GB VRAM** in BF16 (fits alongside Parakeet in 12 GB).
   * **ZONOS2 (8B total, 900M active MoE):** Requires **~16–18 GB VRAM** in BF16 for all 8B parameters (**does NOT fit in 12 GB unquantised** alongside Parakeet; requires INT4/FP8 quantisation).
3. **Streaming, TTFA & RTF:**
   * **Zonos v0.1:** Autoregressive DAC token prediction with **RTF ~0.50 (~2× real-time)** on RTX 4090/5070 and **TTFA ~250–400 ms** via community streaming wrappers ([Zyphra/Zonos](https://github.com/Zyphra/Zonos)).
   * **ZONOS2:** Uses Mini-SGLang server for low-latency streaming, but VRAM-constrained on 12 GB cards.
4. **Naturalness Evidence:**
   * Zonos v0.1 sits around **~1,000–1,030 Elo on TTS Arena V2** ([TTS Arena V2](https://huggingface.co/spaces/TTS-AGI/TTS-Arena-V2)). Listeners praise its 44.1 kHz acoustic fidelity and emotional range, but report occasional audio artifacts (clicks/hiss at chunk boundaries) and dependence on `espeak-ng` phonemization.
5. **Prosody Across Sentences & Style Control:**
   * **Explicit 8-dimensional emotion vector conditioning:** Exposes continuous sliders for *Happiness, Sadness, Disgust, Fear, Surprise, Anger, Neutral*, plus *Speaking Rate*, *Pitch Std*, and *Max Frequency (`fmax`)* ([Zyphra/Zonos](https://github.com/Zyphra/Zonos)).
   * Supports audio prefix conditioning to carry tone from the previous utterance into the next.
6. **Voices & Safety/Watermarking:**
   * Zero-shot voice cloning from 10–30s audio (speaker embeddings can be saved to disk as preset voices). No watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * **Blackwell Warning for Zonos-v0.1-Hybrid:** The Hybrid variant depends on `mamba-ssm` and `causal-conv1d`, whose prebuilt wheels frequently fail to compile or run on `sm_120`. Use the **pure Transformer variant (`Zyphra/Zonos-v0.1-transformer`)** on RTX 5070.

---

### 11. Higgs Audio v2 (3B) & v3 (4B) (Boson AI)
1. **Release & Licence:**
   * **Higgs Audio v2 (`higgs-audio-v2-generation-3B-base`):** Released **July 22, 2025** (~15.5 months old; Apache 2.0).
   * **Higgs Audio v3 TTS (`higgs-audio-v3-tts-4b`):** Released **June 2026** (~5 months old; **Boson Higgs Audio v3 Research and Non-Commercial License** — free for personal/research use, commercial requires paid license) ([boson-ai/higgs-audio](https://github.com/boson-ai/higgs-audio)).
2. **Size, VRAM & Co-residency:**
   * **v2 (3B Llama-3.2):** ~3.6B total + ~2.2B DualFFN/AudioTokenizer = **~10.5–12.5 GB VRAM** in BF16.
   * **v3 (4B Qwen3):** **~10.0–12.0 GB VRAM** in BF16; **~5.1 GB in INT8** or **~3.0 GB in INT4/GGUF**.
   * **Fits with Parakeet in 12 GB?** **Does NOT fit in BF16** alongside Parakeet (will OOM on 12 GB); **fits only if quantised to INT8/INT4 or GGUF**.
3. **Streaming, TTFA & RTF:**
   * Streams PCM audio over an OpenAI-compatible `/v1/audio/speech` endpoint via `vLLM-Omni` or `SGLang-Omni` (25 fps audio tokenizer).
   * **TTFA:** **~200–300 ms** (with vLLM/SGLang backend); **RTF ~0.35–0.60** on RTX 5070 when quantised ([vLLM Blog](https://blog.vllm.ai), [boson-ai/higgs-audio](https://github.com/boson-ai/higgs-audio)).
4. **Naturalness Evidence:**
   * Achieved a **75.7% win rate over GPT-4o-mini-tts** on Emotional Measurement in Boson's evaluations and ranks strongly in LMSYS/community comparisons for natural belt/whisper transitions and multi-speaker dialogue ([Boson AI](https://huggingface.co/bosonai)).
5. **Prosody Across Sentences & Style Control:**
   * Very strong cross-sentence prosody: the 3B/4B LLM backbone reads full paragraphs and automatically infers emotional arc from the text semantics (plus inline style/sound tags in v3).
6. **Voices & Safety/Watermarking:**
   * Supports zero-shot voice cloning (3–10s sample), multi-speaker dialogue, and automatic voice selection. No watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch**, **vLLM-Omni / SGLang-Omni**, and community **GGUF**. On a 12 GB RTX 5070, `vLLM` memory pressure is the primary bottleneck.

---

### 12. VibeVoice (1.5B, 7B & Realtime-0.5B) (Microsoft)
1. **Release & Licence:**
   * **VibeVoice-1.5B & 7B:** Released **August 25, 2025** (~14.5 months old); official repo pulled by Microsoft on September 5, 2025 over deepfake/cloning concerns (weights remain on community mirrors/forks).
   * **VibeVoice-Realtime-0.5B:** Officially released by Microsoft in **December 2025** (~11 months old) and accepted as an **ICLR 2026 Oral** ([microsoft/VibeVoice](https://github.com/microsoft/VibeVoice), [microsoft/VibeVoice-Realtime-0.5B](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B)).
   * **Licence:** **MIT License**.
2. **Size, VRAM & Co-residency:**
   * **Realtime-0.5B:** **~3.6–4.0 GB VRAM** in BF16 (fits easily alongside Parakeet in 12 GB).
   * **VibeVoice-1.5B:** **~6.0–7.5 GB VRAM** in BF16 (fits alongside Parakeet INT8).
   * **VibeVoice-7B:** ~16+ GB VRAM (does not fit in 12 GB without 4-bit quantisation).
3. **Streaming, TTFA & RTF:**
   * Uses a **Qwen2.5 LLM + Next-Token Diffusion head** at an ultra-low **7.5 Hz continuous frame rate**.
   * **VibeVoice-Realtime-0.5B:** Accepts streaming text input from an LLM and achieves **TTFA ~250–300 ms** and **RTF ~0.20–0.30** on consumer RTX GPUs ([Microsoft VibeVoice](https://github.com/microsoft/VibeVoice)).
4. **Naturalness Evidence:**
   * Strong MOS and conversational naturalness scores in ICLR 2026 benchmarks, especially on long-form turn-taking and coherent multi-sentence cadence, though `Realtime-0.5B` trades some acoustic richness for low latency.
5. **Prosody Across Sentences & Style Control:**
   * **7.5 Hz frame rate** enables massive context windows (up to 8K tokens / ~10 minutes on Realtime-0.5B, and 64K tokens / ~90 minutes on 1.5B). Carries prosody seamlessly across entire paragraphs and long responses.
6. **Voices & Safety/Watermarking:**
   * **Crucial Caveat:** In `VibeVoice-Realtime-0.5B`, Microsoft **stripped custom zero-shot voice cloning** to prevent misuse, restricting it to **preset voices only**. Furthermore, official Microsoft checkpoints prepend an **audible AI disclaimer / imperceptible watermark** unless using patched community forks ([microsoft/VibeVoice](https://github.com/microsoft/VibeVoice)).
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch / HF Transformers** (`sdpa` or `flash_attention_2`). Works well on RTX 5070 (`cu128`).

---

### 13. MegaTTS 3 (ByteDance)
1. **Release & Licence:**
   * Paper published **February 26, 2025**, code/weights released **March 2025** (~20 months old).
   * **Licence:** **Apache 2.0** ([ByteDance/MegaTTS3](https://github.com/ByteDance/MegaTTS3)).
2. **Size, VRAM & Co-residency:**
   * **~0.45B parameters** (Sparse Alignment Diffusion Transformer + WavVAE). Uses **~4.0–6.0 GB VRAM** in FP16.
   * **Fits with Parakeet in 12 GB?** **Yes** (~6–7.5 GB combined).
3. **Streaming, TTFA & RTF:**
   * Non-autoregressive latent DiT with 8-step piecewise rectified flow.
   * **No native token streaming** (chunked batch synthesis only). **RTF ~0.25–0.35**, **TTFA ~500–800 ms** per sentence/chunk ([arXiv:2502.18924](https://arxiv.org/abs/2502.18924)).
4. **Naturalness Evidence:**
   * High objective speaker similarity and intelligibility in academic benchmarks (Seed-TTS-Eval), but limited presence on Western crowdsourced TTS Arena V2.
5. **Prosody Across Sentences & Style Control:**
   * Exposes separate classifier-free guidance scales forintelligibility (`p_w`) and speaker/accent similarity (`t_w`), plus explicit phoneme duration manipulation, but lacks cross-sentence conversational LLM memory.
6. **Voices & Safety/Watermarking:**
   * **Major Caveat:** ByteDance **withheld the `WavVAE` encoder weights** for safety, meaning out-of-the-box you could only use pre-extracted `.npy` latent voices published by ByteDance (until third-party community mirrors leaked/re-implemented compatible WavVAE encoders).
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch**. Not recommended for a live streaming English voice assistant due to batch DiT design and restricted voice encoder.

---

### 14. Spark-TTS (0.5B — SparkAudio)
1. **Release & Licence:**
   * Released **March 3–4, 2025** (~20 months old). Checkpoint: `SparkAudio/Spark-TTS-0.5B`.
   * **Licence:** **Apache 2.0** ([SparkAudio/Spark-TTS](https://github.com/SparkAudio/Spark-TTS)).
2. **Size, VRAM & Co-residency:**
   * **0.5B parameters** (Qwen2.5-0.5B + single-stream `BiCodec`). Uses **~3.5–5.5 GB VRAM** in FP16.
   * **Fits with Parakeet in 12 GB?** **Yes, easily.** Also supports GGUF/llama.cpp and Triton TensorRT-LLM.
3. **Streaming, TTFA & RTF:**
   * Single-stream autoregressive token generation (50 tokens/sec).
   * In vanilla PyTorch FP16, **RTF is ~0.40–0.70** and **TTFA is ~300–500 ms**; with TensorRT-LLM / vLLM acceleration, **TTFA drops to ~180–250 ms** and **RTF to ~0.12** ([SparkAudio/Spark-TTS](https://github.com/SparkAudio/Spark-TTS)).
4. **Naturalness Evidence:**
   * Solid academic metrics (Seed-TTS-Eval), though in subjective English listening comparisons it trails Chatterbox Turbo, Orpheus, and Qwen3-TTS in conversational warmth.
5. **Prosody Across Sentences & Style Control:**
   * Uses Chain-of-Thought (CoT) attribute generation to control **gender, pitch level (very low to very high), and speaking rate (very slow to very fast)** across sentences.
6. **Voices & Safety/Watermarking:**
   * Supports both **zero-shot voice cloning** (extracting fixed-length global tokens via BiCodec) and **parametric virtual voice creation** (without reference audio). No watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch**, **vLLM**, **Triton/TensorRT-LLM**, and **GGUF**.

---

### 15. IndexTTS-2 & IndexTTS-2.5 (Bilibili IndexTeam)
1. **Release & Licence:**
   * **IndexTTS-2:** Released **September 8, 2025** (~14 months old) ([arXiv:2506.21619](https://arxiv.org/abs/2506.21619)).
   * **IndexTTS-2.5:** Released **August 10, 2026** (~3 months old) ([index-tts/index-tts](https://github.com/index-tts/index-tts)).
   * **Licence:** **Bilibili IndexTTS License** (free for personal, research, and commercial use up to 100M monthly active users; prohibits training competing general TTS models).
2. **Size, VRAM & Co-residency:**
   * **IndexTTS-2:** ~8.0–10.5 GB VRAM in FP16 (tight with Parakeet).
   * **IndexTTS-2.5 (~0.8B):** Reduced footprint to **~5.0–6.0 GB VRAM** in BF16 (**fits alongside Parakeet INT8 in 12 GB**).
3. **Streaming, TTFA & RTF:**
   * Hybrid Autoregressive GPT + Flow-Matching/Zipformer + BigVGANv2 vocoder.
   * Because of its multi-stage pipeline (GPT semantic tokens $\rightarrow$ Mel flow-matching $\rightarrow$ BigVGANv2), it is primarily a **chunked/batch dubbing engine** rather than an ultra-low-latency streaming assistant model: **RTF ~0.20–0.32** in IndexTTS-2.5 (BF16), **TTFA ~450–800 ms** ([index-tts/index-tts](https://github.com/index-tts/index-tts)).
4. **Naturalness Evidence:**
   * Widely regarded in community tests as one of the most emotionally expressive dubbing models available, outperforming F5-TTS and Fish Speech v1.5 on emotional intensity and stability.
5. **Prosody Across Sentences & Style Control:**
   * **Industry-leading emotion decoupling:** Can clone a speaker's timbre from Clip A while transferring emotion from Clip B, OR steer emotion via an **8-dimensional emotion vector** (*Happy, Angry, Sad, Fearful, Disgusted, Melancholic, Surprised, Calm*), OR use **Qwen-driven natural-language emotion text prompts**. Also supports explicit **duration/token-count control** ([IndexTTS2 Demo](https://index-tts.github.io/index-tts2.github.io/)).
6. **Voices & Safety/Watermarking:**
   * Zero-shot cloning from 3–10s sample. No mandatory watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **PyTorch (`bf16`, CUDA 12.8+ explicitly recommended by IndexTTS-2.5 docs)** — native `sm_120` support out of the box.

---

### 16. Maya1 (`maya-research/maya1` — Maya Research)
1. **Release & Licence:**
   * Released **November 2025** (~12 months old).
   * **Licence:** **Apache 2.0** ([maya-research/maya1](https://huggingface.co/maya-research/maya1)). Permissive personal and commercial use.
2. **Size, VRAM & Co-residency:**
   * **~3.3B parameters** (Llama-style transformer + 24 kHz SNAC codec).
   * **BF16:** ~7.0–8.5 GB VRAM (tight alongside Parakeet once KV-cache grows).
   * **Quantised (GGUF `Q4_K_M` / `Q8_0`):** **~2.5–4.0 GB VRAM** (**fits easily alongside Parakeet in 12 GB**).
3. **Streaming, TTFA & RTF:**
   * Streams SNAC tokens in real time (~0.98 kbps).
   * **TTFA:** **~100–200 ms** via vLLM or `llama.cpp`; **RTF ~0.30–0.45** on RTX 5070/4090 ([maya-research/maya1](https://huggingface.co/maya-research/maya1)).
4. **Naturalness Evidence:**
   * Strong community reception on Hugging Face for prompt-designed voices and inline emotional reactions, comparable to Orpheus-3B in naturalness.
5. **Prosody Across Sentences & Style Control:**
   * **Promptable voice & style design** via XML-like description tags (e.g., `<description="30-year-old British male, warm, conversational, moderate pace">`) plus **20+ inline emotion tags** (`<laugh>`, `<sigh>`, `<whisper>`, `<gasp>`, `<chuckle>`, `<excited>`, `<sad>`).
6. **Voices & Safety/Watermarking:**
   * Primarily **natural-language voice design** (keep the description string fixed for a consistent voice, or seed with an audio prompt). No watermark.
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **vLLM**, **PyTorch**, and **llama.cpp / GGUF** (recommended on 12 GB RTX 5070).

---

### 17. NeuTTS Air & NeuTTS Nano (Neuphonic)
1. **Release & Licence:**
   * **NeuTTS Air (0.75B):** Released **October 2025** (~13 months old).
   * **NeuTTS Nano (0.23B) & NeuTTS-2E:** Released **early 2026** (~8–9 months old).
   * **Licence:** **Apache 2.0** ([neuphonic/neutts-air](https://github.com/neuphonic/neutts-air), [neuphonic/neutts-air HF](https://huggingface.co/neuphonic/neutts-air)).
2. **Size, VRAM & Co-residency:**
   * **NeuTTS Air:** ~748M total parameters (Qwen2.5-0.5B backbone + 50 Hz single-codebook `NeuCodec`). Uses **~1.5–2.0 GB in FP16**, or **~500 MB–800 MB in Q4/Q8 GGUF**!
   * **Fits with Parakeet in 12 GB?** **Yes, effortlessly** (can also run purely on the i7-14700K CPU at >1× real-time, using 0 GB VRAM).
3. **Streaming, TTFA & RTF:**
   * Native streaming via `llama-cpp-python` + ONNX `NeuCodec` decoder.
   * **TTFA:** **<150 ms on GPU** (~250 ms on CPU); **RTF < 0.05 on GPU** (up to 300× real-time in Q4 GGUF on high-end RTX cards; ~2–3× real-time on CPU) ([neuphonic/neutts-air](https://github.com/neuphonic/neutts-air)).
4. **Naturalness Evidence:**
   * Clearly more conversational and context-aware than Kokoro-82M for a ~0.5B class model, though Q4 GGUF shows slight metallic codec compression compared to BF16 Chatterbox Turbo or Qwen3-TTS-1.7B.
5. **Prosody Across Sentences & Style Control:**
   * Qwen 0.5B LLM backbone carries prosody across multi-sentence passages; `NeuTTS-2E` adds explicit emotion modes (*happy, sad, angry, neutral*).
6. **Voices & Safety/Watermarking:**
   * Supports **3-second instant voice cloning** plus preset samples (`dave`, `jo`, and in 2E: `Emily`, `Paul`, `Sophie`, `Steven`).
   * **Watermark:** Embeds a **Perth perceptual watermark** by default ([neuphonic/neutts-air](https://github.com/neuphonic/neutts-air)).
7. **Runtime & Blackwell (`sm_120`) / WSL2 Notes:**
   * Runs on **llama.cpp / GGUF**, **ONNX**, and **PyTorch**. Zero Blackwell hurdles when run via CPU or CUDA 12.8 `llama.cpp`.

---

### 18. Fun-CosyVoice 3.0 (`Fun-CosyVoice3-0.5B-2512` — Alibaba FunAudioLLM) — *2026 Contender*
1. **Release & Licence:**
   * Paper published May 2025; open weights (`FunAudioLLM/Fun-CosyVoice3-0.5B-2512`) released **December 2025** (~11 months old).
   * **Licence:** **Apache 2.0** ([FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice)).
2. **Size, VRAM & Co-residency:**
   * **0.5B parameters** (Qwen2.5-0.5B + chunk-aware causal flow matching). Uses **~4.0–5.5 GB VRAM** in FP16 (**fits easily alongside Parakeet in 12 GB**).
3. **Streaming, TTFA & RTF:**
   * Supports **bi-streaming** (text-in streaming + audio-out streaming) with **TTFA ~150 ms** and **RTF ~0.15–0.25** via `vLLM` / `TensorRT-LLM` ([FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice)).
4. **Naturalness, Prosody & Voices:**
   * Top-tier CER/WER on Seed-TTS-Eval and CV3-Eval; supports natural-language instruct control (emotion, speed, whispering, laughter) and 3-second zero-shot cloning without watermarks.

---

### Summary Table: Local Models on RTX 5070 (12 GB) + Parakeet ASR

| Model (Latest Version) | Age (as of 2026-11-08) | Licence | Active VRAM | Fits w/ Parakeet? | Native Stream? | TTFA / RTF (RTX 5070 est.) | Cross-Sentence Prosody |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kokoro v1.0 / v1.1 (82M)** *(Baseline)* | ~21.5 mos | Apache 2.0 | ~0.4 GB | Yes | Chunked | ~60 ms / ~0.03 | Weak (resets per sentence) |
| **Chatterbox Turbo (350M)** | ~10.5 mos | MIT | ~3.5–4.5 GB | **Yes** | **Yes** (1-step) | **~150 ms / ~0.16** | Strong + `[laugh]`/`[sigh]` tags |
| **Qwen3-TTS (0.6B / 1.7B)** | ~9.5 mos | Apache 2.0 | 4 GB / 7.5 GB | **Yes** | **Yes** (12 Hz) | **~100 ms / ~0.20** | **Excellent** (LLM + Instruct) |
| **Kyutai TTS 1.6B / Pocket 100M** | 16m / 10m | CC-BY 4.0 | 5 GB / **0 GB (CPU)** | **Yes** | **Yes** (Bi-stream) | **~200 ms / ~0.16** | **Continuous stream (no splits)** |
| **Orpheus TTS (3B GGUF Q8)** | ~19.5 mos | Apache 2 / Llama | ~4.2 GB (Q8) | **Yes (GGUF)** | **Yes** (SNAC) | **~180 ms / ~0.40** | Strong + inline `<laugh>` tags |
| **NeuTTS Air (0.75B GGUF/FP16)** | ~13 mos | Apache 2.0 | 0.8–2.0 GB | **Yes** | **Yes** | **~150 ms / <0.05** | Good (Qwen 0.5B backbone) |
| **Fish OpenAudio S1-mini (0.5B)** | ~17 mos | CC-BY-NC-SA | ~4.5 GB | **Yes** | **Yes** | **~200 ms / ~0.20** | Strong + `(emotion)` tags |
| **Sesame CSM-1B (1.55B)** | ~20 mos | Apache 2.0 | ~5.5–7.5 GB | **Yes** | Community | ~300 ms / ~0.50 | **Excellent** (multi-turn audio ctx) |
| **VibeVoice-Realtime (0.5B)** | ~11 mos | MIT | ~3.8 GB | **Yes** | **Yes** (7.5 Hz) | ~280 ms / ~0.25 | Strong (presets only, watermark) |
| **Fun-CosyVoice 3.0 (0.5B)** | ~11 mos | Apache 2.0 | ~4.5 GB | **Yes** | **Yes** (Bi-stream) | ~150 ms / ~0.20 | Strong + Instruct mode |
| **Maya1 (3.3B GGUF Q8)** | ~12 mos | Apache 2.0 | ~4.0 GB (Q8) | **Yes (GGUF)** | **Yes** (SNAC) | ~150 ms / ~0.35 | Strong + XML voice design |
| **Dia2 (1B / 2B)** | ~12 mos | Apache 2.0 | 5.5 / 9.5 GB | **1B Yes** / 2B Tight | **Yes** (Mimi) | ~300 ms / ~0.45 | Strong dialogue continuity |
| **IndexTTS-2.5 (0.8B)** | ~3 mos | Bilibili Lic. | ~5.5 GB | **Yes** | Chunked | ~500 ms / ~0.25 | High emotion control (batch) |
| **Zonos v0.1 Transformer (1.6B)** | ~21 mos | Apache 2.0 | ~5.5 GB | **Yes** | Community | ~300 ms / ~0.50 | Emotion sliders (some artifacts) |
| **Spark-TTS (0.5B)** | ~20 mos | Apache 2.0 | ~4.5 GB | **Yes** | Yes (TRT/vLLM) | ~300 ms / ~0.45 | Pitch/speed CoT control |
| **F5-TTS v1 (335M)** | ~20 mos | CC-BY-NC 4.0 | ~3.0 GB | **Yes** | Chunked DiT | ~300 ms / ~0.12 | Within-chunk only (no LLM) |
| **Higgs Audio v2/v3 (3B/4B)** | 15.5m / 5m | Apache / NC | ~11 GB (BF16) | **Quantised only** | Yes (vLLM) | ~250 ms / ~0.45 | Strong paragraph prosody |
| **MegaTTS 3 (0.45B)** | ~20 mos | Apache 2.0 | ~4.5 GB | **Yes** | No (Batch) | ~600 ms / ~0.30 | Limited (no public WavVAE) |

---

## Part B: Hosted Options (Comparison Only)

> **Privacy Rule Reminder:** Because your privacy policy permits sending personal data only to the LLM provider (Anthropic), using any of the hosted TTS APIs below requires an **explicit privacy exception**—every sentence spoken by the assistant is transmitted in plaintext to the TTS vendor.

| Provider & Model | Price per Hour of Speech | Measured Latency (TTFA) | What the Provider Keeps or Trains On |
| :--- | :--- | :--- | :--- |
| **Google Gemini TTS / Live**<br>(`gemini-2.5-flash-preview-tts`, `gemini-2.5-flash-native-audio`) | **~$0.90–$1.08 / hr**<br>*(Billed per token at ~25 audio tokens/s = 90k tokens/hr: $0.50/1M text in + $10.00–$12.00/1M audio out)* ([Google AI Pricing](https://ai.google.dev/pricing)) | **~250–400 ms** (Live WebSocket)<br>**~450–650 ms** (Flash TTS REST) | **Paid Tier:** Google **does NOT train** on prompts or audio, but retains abuse-monitoring logs for up to **55 days** unless Enterprise Zero Data Retention (Vertex AI) is configured.<br>**Free Tier:** Google retains data and **trains models** on it ([Gemini API Terms](https://ai.google.dev/gemini-api/terms)). |
| **OpenAI TTS / Realtime**<br>(`gpt-4o-mini-tts`, `gpt-realtime` / `gpt-realtime-mini`) | **`gpt-4o-mini-tts`: ~$0.90–$1.07 / hr** *($0.60/1M text in, $12.00/1M audio out)*<br>**`gpt-realtime-mini`: ~$1.80 / hr** audio out *($20/1M)*<br>**`gpt-realtime` (full): ~$5.76 / hr** audio out *($64/1M; ~$12–$15/hr with bidirectional turn history)* ([OpenAI Pricing](https://openai.com/api/pricing/)) | **`gpt-4o-mini-tts`: ~500–650 ms**<br>**`gpt-realtime` (WebRTC / WS): ~300–500 ms** | OpenAI **does NOT train** on API inputs or outputs by default. However, standard API accounts retain inputs/outputs for **up to 30 days** for abuse monitoring unless Zero Data Retention (ZDR) is approved ([OpenAI Enterprise Privacy](https://openai.com/enterprise-privacy/)). |
| **ElevenLabs**<br>(`Flash v2.5`, `Turbo v2.5`, `Eleven v3`) | **`Flash v2.5` / `Turbo v2.5`: ~$2.40 / hr** *(~$0.04 / 1k chars at ~60k chars/hr)*<br>**`Eleven v3` / `Multilingual v2`: ~$4.80 / hr** *(~$0.08 / 1k chars)* ([ElevenLabs Pricing](https://elevenlabs.io/pricing/api)) | **`Flash v2.5` / `Turbo v2.5`: ~75–135 ms** (inference; ~180 ms w/ network)<br>**`Eleven v3`: ~280–400 ms** | **Trains by default on self-serve plans** unless you manually toggle off *"Improve the models for everyone"* in account settings. Retains synthesis history/audio on server unless you delete it or pay for an **Enterprise Zero Retention Mode (ZRM)** contract ([ElevenLabs Privacy](https://elevenlabs.io/privacy-policy)). |
| **Cartesia**<br>(`Sonic-2`, `Sonic-3` / `Sonic Turbo`) | **~$1.80–$2.90 / hr**<br>*(~45k–50k credits/hr at 1 credit/char; ~$38–$65 per 1M credits depending on Pro/Startup/Scale tier)* ([Cartesia Pricing](https://cartesia.ai/pricing)) | **~90 ms** model TTFA (**~150–190 ms** end-to-end WebSocket) ([Cartesia Sonic](https://cartesia.ai/sonic)) | Standard self-serve terms permit retaining logs and using data for service improvement; **Zero Data Retention (ZDR)** (no logging, storage, or training) is restricted to **Enterprise tier** customers ([Cartesia Trust/Security](https://cartesia.ai/security)). |
| **Hume AI**<br>(`Octave TTS`, `EVI 2 / 3`) | **~$3.00–$3.60 / hr** *(Octave TTS at ~$0.05–$0.06 / 1k chars; EVI ~$3.50/hr)*<br>**⚠️ CRITICAL STATUS: SHUTTING DOWN** | **~150–200 ms** (Octave TTS WebSocket) | **⚠️ Permanent API Shutdown in 5 Days (Nov 13, 2026):** Hume AI is permanently sunsetting its Octave TTS and EVI APIs on **2026-11-13 at 00:01 EST** to pivot to AI evaluation tooling (VoiceEQ), and will purge all stored voices and transcripts ([Hume Sunset Notice](https://voicesmiths.com)). Do not adopt. |

---

## Part C: Recommendations & Low-Effort Kokoro Improvements

### Top 3 Local Picks for This Machine (Ranked)

#### 🥇 Rank 1: Qwen3-TTS (`Qwen3-TTS-12Hz-1.7B` or `0.6B`) — *Best Overall Naturalness & Prosody*
* **Why it wins for your setup:** Released in January 2026 under **Apache 2.0**, Qwen3-TTS is built on a Qwen3 LLM backbone with a single-frame-rate **12.5 Hz tokenizer** (`Qwen3-TTS-Tokenizer-12Hz`). Unlike Kokoro's sentence-isolated encoder, Qwen3-TTS reads multi-sentence paragraphs with true semantic comprehension—shifting tone, pacing, and emphasis naturally across sentences. It achieves **~100–150 ms TTFA** and **RTF ~0.20**, fits comfortably alongside Parakeet ASR on your 12 GB RTX 5070 (~4 GB VRAM for `0.6B` or ~7.5 GB for `1.7B`), includes built-in English male/female presets (`CustomVoice`) plus 3-second voice cloning (`Base`) so you can clone Kokoro's `bm_daniel` timbre if you like that voice, and has **no watermark**.
* **Main Risk:** As a causal LLM-based speech generator, very long unchunked generations (>60–90 seconds) or unusual punctuation can occasionally trigger LLM prosodic drift or token repetition; additionally, achieving peak ~100 ms latency on Blackwell (`sm_120`) requires PyTorch 2.7+ (`cu128`) and CUDA graphs / SDPA configuration.

#### 🥈 Rank 2: Chatterbox Turbo (`ResembleAI/chatterbox-turbo`, 350M) — *Best Drop-in Expressive English TTS*
* **Why it wins for your setup:** Released in December 2025 under the **MIT license**, Chatterbox Turbo is purpose-built for English voice agents. Its 1-step distilled decoder hits **<150 ms TTFA** and **~6× real-time (RTF ~0.16)** while consuming only **~3.5–4.5 GB VRAM**—leaving 6+ GB of breathing room for Parakeet on your 12 GB RTX 5070. Blind human preference tests rank the Chatterbox family ahead of Kokoro and competitive with ElevenLabs, and it natively supports inline paralinguistic tags (`[sigh]`, `[chuckle]`, `[laugh]`, `[clear throat]`) that your LLM can emit to make the assistant sound alive.
* **Main Risk:** It embeds Resemble AI's imperceptible **PerTh watermark** by default (though removable in local MIT Python code), and because it is optimised for snappy 1–3 sentence conversational turns rather than continuous token-in bi-streaming, very long multi-paragraph explanations still need paragraph/clause chunking.

#### 🥉 Rank 3: Kyutai TTS (`Pocket TTS 100M` on CPU or `Kyutai DSM 1.6B` on GPU) — *Best Architectural Fix for Sentence-Boundary Seams*
* **Why it wins for your setup:** Kyutai's **Delayed Streams Modeling (DSM)** is one of the few architectures that supports **true bi-directional streaming**: you pipe the text token stream from Claude directly into Kyutai TTS as tokens arrive, and it emits a continuous 12.5 Hz Mimi audio stream with **~200 ms latency**—eliminating sentence-by-sentence splitting altogether. Better still, **Pocket TTS (100M, Jan 2026)** runs at **~6× real-time (RTF ~0.16) on just 2 cores of your i7-14700K CPU (0 GB GPU VRAM)**, completely eliminating any VRAM contention or Blackwell `sm_120` CUDA friction with Parakeet, while the **1.6B GPU model** (~5 GB VRAM) offers higher acoustic richness.
* **Main Risk:** While its multi-sentence continuity and rhythm are far smoother than sentence-by-sentence Kokoro, Pocket TTS's 100M capacity has less dramatic emotional range and fewer paralinguistic flourishes than Qwen3-TTS-1.7B or Chatterbox Turbo.

---

### Fastest Low-Effort Improvements to Your Current Kokoro (`sherpa-onnx`) Setup

Before replacing `sherpa-onnx` with a PyTorch/CUDA TTS service, you can make Kokoro v1.0 (`bm_daniel`) sound noticeably less flat in **under an hour of Python changes**:

1. **Synthesise Multi-Sentence Chunks (2–4 Sentences / ~350–450 Phonemes) Instead of Single Sentences:**
   * **Why:** When you feed Kokoro one sentence at a time, its duration predictor and StyleTTS2 prosody network start from a cold state and apply a terminal falling cadence at the end of every sentence. Kokoro supports up to **510 phoneme tokens (~30–40 seconds of audio)** in a single pass ([hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)).
   * **How (Zero TTFA Penalty):** Use **progressive chunk sizing**:
     * **Chunk 1:** Send the **first clause or sentence** immediately (~40–80 chars) so Time-to-First-Audio stays <100 ms.
     * **Chunks 2+:** While Chunk 1 is playing on the Mac (~2–4 seconds of audio), buffer the LLM stream into **2–3 sentence paragraphs (250–400 characters)** and pass the entire multi-sentence block to `sherpa-onnx` in a single call. Kokoro will compute cross-sentence prosody and pause transitions across the whole block.
2. **Lower `speed` from `1.2` to `1.05–1.10` and Use Punctuation Shaping:**
   * In Kokoro's StyleTTS2 duration predictor, `speed=1.2` compresses vowel and pause durations uniformly, which flattens pitch excursions and strips out natural breathing pauses. Dropping speed to `1.05–1.10` and replacing hard periods between closely linked clauses with semicolons (`;`) or em-dashes (`—`) keeps the pitch contour elevated across clauses instead of resetting to baseline.
3. **Blend `bm_daniel` with a More Expressive Voice Embedding (e.g., `bm_george`, `bm_lewis`, or `am_fenrir`):**
   * `bm_daniel` is one of the most even-keeled (and therefore flattest) style vectors in Kokoro's `voices.bin`. Because Kokoro voices are simply $510 \times 1 \times 256$ float32 style vectors indexed by token length, blending **70% `bm_daniel` + 30% `bm_lewis` (or `am_michael` / `bm_george`)** in `voices.bin` (or via `kokoro-onnx`) significantly increases pitch standard deviation while keeping Daniel's recognizable British male timbre.
4. **Switch G2P from `sherpa-onnx`'s C++ `espeak-ng` Lexicon to Native Python `misaki` (`kokoro-onnx`):**
   * `sherpa-onnx` uses a static `lexicon-us-en.txt` / `lexicon-gb-en.txt` + `espeak-ng` fallback that drops some word-level stress markers that Kokoro's native Python `misaki` G2P library preserves. Switching the Python wrapper from `sherpa-onnx` to `kokoro-onnx` (which still uses lightweight ONNX Runtime but feeds `misaki` stress-annotated phonemes) noticeably improves word emphasis.

---

### Open Questions I Couldn't Answer

1. **Exact Parakeet Model Variant & Execution Provider in Your Service:**
   * Whether your Python service runs `parakeet-tdt-0.6b-v2` (INT8 ~1.3 GB vs FP16 ~1.8 GB) or `parakeet-tdt-1.1b` (~2.5–5.5 GB), and whether `sherpa-onnx` is configured with `onnxruntime` arena shrinkage (`enable_cpu_mem_arena` / `cudnn_conv_use_max_workspace`). If `onnxruntime-gpu` pre-allocates a large BFC arena on startup, a 7–8 GB PyTorch TTS model (like Qwen3-TTS-1.7B) will need explicit `torch.cuda.set_per_process_memory_fraction()` tuning to avoid fragmentation.
2. **Exact Blackwell (`sm_120`) Measured TTFA for Every Model:**
   * Most published community and vendor benchmarks report TTFA/RTF on **RTX 4090 (`sm_89`)** or **RTX 3090 (`sm_86`)** rather than the **RTX 5070 (`sm_120`)**. Because the RTX 5070 has ~672 GB/s GDDR7 memory bandwidth (~33% less than an RTX 4090's 1,008 GB/s, though with newer Blackwell tensor cores), autoregressive token generation on 1.7B–3B models will run roughly 15–25% slower than RTX 4090 numbers, still comfortably faster than real-time (RTF < 0.35).
3. **Whether You Want to Keep a British Male Voice ("Daniel"):**
   * If keeping the exact British male persona is mandatory, models that support **3–5 second zero-shot voice cloning** (Qwen3-TTS `Base`, Chatterbox Turbo, Kyutai TTS, NeuTTS Air) can clone a clean 10-second reference WAV generated by Kokoro's `bm_daniel` (or a real British voice actor sample) directly, whereas preset-only models (`VibeVoice-Realtime-0.5B`, `Orpheus-3B-ft` out-of-the-box) default to American voices.

---
