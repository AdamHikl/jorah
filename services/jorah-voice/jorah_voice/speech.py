"""Speech models, behind plain methods so the session can be tested without them."""

import ctypes
import sys
from collections import deque
from pathlib import Path

import numpy as np

from . import models, spoken

NAMES = Path(__file__).with_name("lexicon-names.txt")


def load_cuda():
    """Load the CUDA libraries from the nvidia pip packages before sherpa-onnx needs them.

    They live in the venv rather than on the library path, so each one is opened globally,
    retrying until the ones that depend on others load too.
    """
    site = Path(sys.prefix) / "lib" / f"python{sys.version_info[0]}.{sys.version_info[1]}" / "site-packages" / "nvidia"
    pending = sorted(path for folder in ("cu13", "cudnn") for path in (site / folder / "lib").glob("lib*.so.*"))
    if not pending:
        raise RuntimeError(f"no CUDA libraries under {site}")
    while pending:
        failed = []
        for path in pending:
            try:
                ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                failed.append(path)
        if len(failed) == len(pending):
            raise RuntimeError(f"can't load {failed[0].name}")
        pending = failed


def _sherpa(provider):
    if provider == "cuda":
        load_cuda()
    import sherpa_onnx
    return sherpa_onnx
MIC_RATE = 16000
VAD_WINDOW = 512

# Kokoro v1.0 speaker numbers, to be checked by ear.
VOICES = {
    "adam": 11, "eric": 13, "liam": 15, "michael": 16, "onyx": 17,
    "daniel": 24, "fable": 25, "george": 26, "lewis": 27,
}


def _vad_config(sherpa_onnx, root, silence, speech):
    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(root / "silero_vad_v5.onnx")
    config.silero_vad.threshold = 0.5
    config.silero_vad.min_silence_duration = silence
    config.silero_vad.min_speech_duration = speech
    config.silero_vad.max_speech_duration = 30
    config.silero_vad.window_size = VAD_WINDOW
    config.sample_rate = MIC_RATE
    return config


class Ears:
    """Finds where speech starts and ends in the incoming 16 kHz, 16-bit mono audio.

    One detector runs for each pause length in `pauses`, all fed the same windows, so each counts
    quiet exactly as a single fixed-pause detector would. The shortest closes segments early, so
    they can be transcribed while the session waits; the longer ones only report that their pause
    has passed. A detector with no hold time resets the quiet as soon as voice comes back, which
    stops a turn ending in the moment he starts talking again.

    Each segment comes with the quiet before it, when that quiet is short enough to be a pause
    inside a turn. Segments joined without it lose words at the join, or come back in the wrong
    language.
    """

    def __init__(self, root=models.ROOT, pauses=(0.6,)):
        sherpa_onnx = _sherpa("cpu")
        self._pauses = sorted(set(pauses))
        self._vads = [
            sherpa_onnx.VoiceActivityDetector(_vad_config(sherpa_onnx, root, pause, 0.25), buffer_size_in_seconds=60)
            for pause in self._pauses
        ]
        # Both times are shorter than one window: voice counts from the second voiced window.
        self._voice = sherpa_onnx.VadModel.create(_vad_config(sherpa_onnx, root, 0.01, 0.01))
        # Silero v5 reads each window together with the end of the one before it.
        self._context = np.zeros(self._voice.window_size() - VAD_WINDOW, dtype=np.float32)
        self._found = []
        self._quiet = 0.0
        self._pending = np.zeros(0, dtype=np.float32)
        self._max_gap = int((self._pauses[-1] + 0.5) * MIC_RATE)
        # Recent windows, enough for the longest segment and the gap before it.
        self._recent = deque(maxlen=(30 * MIC_RATE + self._max_gap) // VAD_WINDOW + 2)
        self._fed = 0
        self._last_end = None

    def accept(self, pcm):
        incoming = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        self._pending = np.concatenate((self._pending, incoming))
        while len(self._pending) >= VAD_WINDOW:
            window = self._pending[:VAD_WINDOW]
            self._pending = self._pending[VAD_WINDOW:]
            for vad in self._vads:
                vad.accept_waveform(window)
            self._recent.append((self._fed, window))
            self._fed += VAD_WINDOW
            if self._voice.is_speech(np.concatenate((self._context, window))):
                self._quiet = 0.0
            if len(self._context):
                self._context = window[-len(self._context):]
            self._collect()

    def _collect(self):
        first = self._vads[0]
        if not first.empty():
            self._quiet = self._pauses[0]
        while not first.empty():
            segment = np.array(first.front.samples, dtype=np.float32)
            start = first.front.start
            first.pop()
            self._found.append(np.concatenate((self._gap(start), segment)))
            self._last_end = start + len(segment)
        for pause, vad in zip(self._pauses[1:], self._vads[1:]):
            if not vad.empty():
                self._quiet = max(self._quiet, pause)
                while not vad.empty():
                    vad.pop()

    def _gap(self, start):
        """The audio between the last segment and this one, if it was a short pause."""
        if self._last_end is None or not 0 < start - self._last_end <= self._max_gap:
            return np.zeros(0, dtype=np.float32)
        pieces = [w for at, w in self._recent if at + VAD_WINDOW > self._last_end and at < start]
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        first_at = next(at for at, _ in self._recent if at + VAD_WINDOW > self._last_end)
        joined = np.concatenate(pieces)
        return joined[self._last_end - first_at : start - first_at]

    def speech_now(self):
        return self._vads[0].is_speech_detected()

    def quiet_seconds(self):
        """The longest of `pauses` that has passed since he last spoke, or 0."""
        return self._quiet

    def segments(self):
        found, self._found = self._found, []
        return found


class Listener:
    def __init__(self, root=models.ROOT, provider="cpu", threads=4):
        sherpa_onnx = _sherpa(provider)
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

    def transcribe(self, *pieces):
        """Transcribe one or more stretches of 16 kHz audio as one utterance."""
        stream = self._recognizer.create_stream()
        stream.accept_waveform(MIC_RATE, np.concatenate(pieces) if len(pieces) > 1 else pieces[0])
        self._recognizer.decode_stream(stream)
        return stream.result.text.strip()


class Speaker:
    def __init__(self, root=models.ROOT, provider="cuda", threads=4, voice=models.DEFAULT_VOICE, speed=models.DEFAULT_SPEED):
        sherpa_onnx = _sherpa(provider)
        folder = root / models.TTS_DIR
        lists = [folder / "lexicon-us-en.txt", NAMES]
        lists.append(spoken.write_inflections(lists[0], folder / "lexicon-inflections.txt"))
        kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=str(folder / "model.onnx"),
            voices=str(folder / "voices.bin"),
            tokens=str(folder / "tokens.txt"),
            lexicon=",".join(str(path) for path in lists),
            data_dir=str(folder / "espeak-ng-data"),
        )
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(kokoro=kokoro, provider=provider, num_threads=threads),
            max_num_sentences=1,
        )
        self._tts = sherpa_onnx.OfflineTts(config)
        self._known = spoken.load_words(*lists)
        self._voice = VOICES[voice]
        self._speed = speed

    @property
    def sample_rate(self):
        return self._tts.sample_rate

    def synthesize(self, text):
        """Return 16-bit mono audio bytes for one sentence."""
        audio = self._tts.generate(spoken.rewrite(text, self._known), sid=self._voice, speed=self._speed)
        samples = np.clip(np.asarray(audio.samples, dtype=np.float32), -1, 1)
        return (samples * 32767).astype(np.int16).tobytes()


def warm_up(listener, speaker, rounds=3):
    """Run each model a few times so the first real turn isn't the slow one."""
    quiet = np.zeros(MIC_RATE, dtype=np.float32)
    for _ in range(rounds):
        listener.transcribe(quiet)
        speaker.synthesize("Ready when you are.")
