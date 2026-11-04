"""Speech models, behind plain methods so the session can be tested without them."""

import numpy as np
import sherpa_onnx

from . import models

MIC_RATE = 16000
VAD_WINDOW = 512

# Kokoro v1.0 speaker numbers, to be checked by ear.
VOICES = {
    "adam": 11, "eric": 13, "liam": 15, "michael": 16, "onyx": 17,
    "daniel": 24, "fable": 25, "george": 26, "lewis": 27,
}


class Ears:
    """Finds where speech starts and ends in the incoming 16 kHz, 16-bit mono audio."""

    def __init__(self, root=models.ROOT, silence=0.6):
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(root / "silero_vad_v5.onnx")
        config.silero_vad.threshold = 0.5
        config.silero_vad.min_silence_duration = silence
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.max_speech_duration = 30
        config.silero_vad.window_size = VAD_WINDOW
        config.sample_rate = MIC_RATE
        self._vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)
        self._pending = np.zeros(0, dtype=np.float32)

    def accept(self, pcm):
        incoming = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        self._pending = np.concatenate((self._pending, incoming))
        while len(self._pending) >= VAD_WINDOW:
            self._vad.accept_waveform(self._pending[:VAD_WINDOW])
            self._pending = self._pending[VAD_WINDOW:]

    def speech_now(self):
        return self._vad.is_speech_detected()

    def segments(self):
        found = []
        while not self._vad.empty():
            found.append(np.array(self._vad.front.samples, dtype=np.float32))
            self._vad.pop()
        return found


class Listener:
    def __init__(self, root=models.ROOT, provider="cpu", threads=4):
        folder = root / models.STT_DIR
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(folder / "encoder.int8.onnx"),
            decoder=str(folder / "decoder.int8.onnx"),
            joiner=str(folder / "joiner.int8.onnx"),
            tokens=str(folder / "tokens.txt"),
            num_threads=threads,
            provider=provider,
            model_type="nemo_transducer",
        )

    def transcribe(self, samples):
        stream = self._recognizer.create_stream()
        stream.accept_waveform(MIC_RATE, samples)
        self._recognizer.decode_stream(stream)
        return stream.result.text.strip()


class Speaker:
    def __init__(self, root=models.ROOT, provider="cpu", threads=4, voice="michael", speed=1.0):
        folder = root / models.TTS_DIR
        kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=str(folder / "model.int8.onnx"),
            voices=str(folder / "voices.bin"),
            tokens=str(folder / "tokens.txt"),
            lexicon=str(folder / "lexicon-us-en.txt"),
            data_dir=str(folder / "espeak-ng-data"),
        )
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(kokoro=kokoro, provider=provider, num_threads=threads),
            max_num_sentences=1,
        )
        self._tts = sherpa_onnx.OfflineTts(config)
        self._voice = VOICES[voice]
        self._speed = speed

    @property
    def sample_rate(self):
        return self._tts.sample_rate

    def synthesize(self, text):
        """Return 16-bit mono audio bytes for one sentence."""
        audio = self._tts.generate(text, sid=self._voice, speed=self._speed)
        samples = np.clip(np.asarray(audio.samples, dtype=np.float32), -1, 1)
        return (samples * 32767).astype(np.int16).tobytes()
