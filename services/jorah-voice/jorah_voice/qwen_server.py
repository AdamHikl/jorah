"""Jorah's Qwen3-TTS voice, kept loaded, for live voice and Telegram replies.

Run in Qwen3-TTS's own environment: /home/jorah/apps/qwen-tts/.venv/bin/python -m jorah_voice.qwen_server
It loads the 1.7B Base model once, clones Jorah's locked voice (the l3 "warm London" design Adam picked on
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
    from qwen_tts import Qwen3TTSModel

    print("Loading Qwen3-TTS", flush=True)
    model = Qwen3TTSModel.from_pretrained(MODEL, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa")
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(VOICE / "jorah-ref.wav"), ref_text=(VOICE / "jorah-ref.txt").read_text().strip()
    )
    lock = threading.Lock()
    rate = {"value": 24000}

    def speak(text):
        text = clean_for_speech(text)
        if not text:
            return b""
        with lock:
            wavs, sr = model.generate_voice_clone(text=text, language="English", voice_clone_prompt=prompt)
        rate["value"] = sr
        samples = np.clip(np.asarray(wavs[0], dtype=np.float32), -1, 1)
        return (samples * 32767).astype(np.int16).tobytes()

    speak("Ready when you are.")  # first run is slow while kernels are picked

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            request = read_request(self.rfile)
            if request is None:
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
