"""Jorah's Qwen3-TTS voice, kept loaded, for live voice and Telegram replies.

Run in the faster-qwen3-tts environment: /home/jorah/apps/fast-qwen/.venv/bin/python -m jorah_voice.qwen_server
(falls back to upstream qwen-tts if that's what's installed). faster-qwen3-tts adds a static cache and CUDA graphs:
measured on 2026-11-08 at 0.35 s of compute per second of speech, first audio 0.29 s, 5.1 GB. It loads the 1.7B Base model once, clones Jorah's locked voice (the l3 "warm London" design Adam picked on
2026-11-08, kept as ~/.config/jorah-voice/voice/jorah-ref.wav and .txt), and answers on a Unix socket only
jorah can open, so nothing listens on a network port. Protocol in qwen_protocol.py.
"""

import os
import socketserver
import sys
import threading

from .core import clean_for_speech
from .qwen_protocol import SOCKET, VOICE, read_request, write_reply

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def main():
    import numpy as np
    import torch

    ref_audio = str(VOICE / "jorah-ref.wav")
    ref_text = (VOICE / "jorah-ref.txt").read_text().strip()
    try:
        from faster_qwen3_tts import FasterQwen3TTS

        print("Loading Qwen3-TTS (faster-qwen3-tts)", flush=True)
        fast = FasterQwen3TTS.from_pretrained(MODEL)

        def generate(text):
            return fast.generate_voice_clone(text=text, language="English", ref_audio=ref_audio, ref_text=ref_text)

        def generate_pieces(text):
            # Measured 2026-11-08 (tools/fast_qwen_bench.py): first audio 0.29 s with chunk_size 8.
            for chunk, sr, _timing in fast.generate_voice_clone_streaming(
                    text=text, language="English", ref_audio=ref_audio, ref_text=ref_text, chunk_size=8):
                yield chunk, sr
    except ImportError:
        from qwen_tts import Qwen3TTSModel

        print("Loading Qwen3-TTS (upstream, slower than real time)", flush=True)
        model = Qwen3TTSModel.from_pretrained(MODEL, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa")
        prompt = model.create_voice_clone_prompt(ref_audio=ref_audio, ref_text=ref_text)

        def generate(text):
            return model.generate_voice_clone(text=text, language="English", voice_clone_prompt=prompt)

        def generate_pieces(text):
            wavs, sr = generate(text)
            yield wavs[0], sr

    lock = threading.Lock()
    rate = {"value": 24000}

    def to_pcm(samples):
        samples = np.clip(np.asarray(samples, dtype=np.float32).reshape(-1), -1, 1)
        return (samples * 32767).astype(np.int16).tobytes()

    def speak(text):
        text = clean_for_speech(text)
        if not text:
            return b""
        with lock:
            wavs, sr = generate(text)
        rate["value"] = sr
        return to_pcm(wavs[0])

    def speak_pieces(text):
        """Yield the audio as it's made. The GPU does one sentence at a time, so this holds the lock
        until the sentence is done or the caller hangs up."""
        text = clean_for_speech(text)
        if not text:
            return
        with lock:
            for samples, sr in generate_pieces(text):
                rate["value"] = sr
                pcm = to_pcm(samples)
                if pcm:
                    yield pcm

    speak("Ready when you are.")  # first run is slow while kernels are picked
    for _ in speak_pieces("Ready when you are."):  # and the streaming path's
        pass

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            request = read_request(self.rfile)
            if request is None:
                return
            if request.get("stream"):
                pieces = speak_pieces(str(request.get("text", ""))[:2000])
                try:
                    for pcm in pieces:
                        write_reply(self.wfile, rate["value"], pcm)
                    write_reply(self.wfile, rate["value"], b"")
                except (BrokenPipeError, ConnectionResetError):
                    pass  # jorah-voice stopped listening, such as Adam talking over him
                except Exception as error:  # report, end the stream, keep serving
                    print(f"speak failed: {error}", flush=True)
                    try:
                        write_reply(self.wfile, rate["value"], b"")
                    except OSError:
                        pass
                finally:
                    pieces.close()  # frees the GPU for the next sentence
                return
            try:
                pcm = b"" if request.get("ping") else speak(str(request.get("text", ""))[:2000])
            except Exception as error:  # report, keep serving
                print(f"speak failed: {error}", flush=True)
                pcm = b""
            write_reply(self.wfile, rate["value"], pcm)

    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    if SOCKET.exists():
        SOCKET.unlink()
    old = os.umask(0o077)
    server = socketserver.ThreadingUnixStreamServer(str(SOCKET), Handler)
    os.umask(old)
    print(f"Qwen3-TTS ready on {SOCKET}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
