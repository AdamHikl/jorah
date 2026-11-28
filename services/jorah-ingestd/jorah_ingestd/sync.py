"""Lines up the Mac's WAV with an iPhone clip's scratch audio.

Both are decoded to mono at a low rate (4 kHz by default) and cross-correlated with PHAT weighting
(GCC-PHAT), which keeps the peak sharp when the two mics sound different. The approach follows
bbc/audio-offset-finder (Apache-2.0); the code is our own.

offset_s is where the clip's first sample sits in the WAV: positive when the WAV started first.
A result is trusted only when the peak stands well above everything else (ratio and z); otherwise
the take asks Adam."""
import subprocess

try:
    import numpy as np
except ImportError:  # the Mac's python3 may lack it; the PC has Ubuntu's python3-numpy
    np = None

GUARD_S = 0.05   # peaks closer than this to the best one are the same peak (echo, smear)
BAND_HZ = (80.0, 0.45)  # low cut in Hz; high cut as a fraction of the sample rate


def decode_mono(ffmpeg: str, path, rate: int, timeout: int = 900):
    """The first audio stream as float32 mono at `rate`, or None when there is none."""
    cmd = [ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-vn",
           "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"]
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0 or not p.stdout:
        return None
    return np.frombuffer(p.stdout, dtype="<f4").astype(np.float64)


def correlate(clip, wav, rate: int, lag_min_s=None, lag_max_s=None) -> dict:
    """GCC-PHAT of clip against wav. Returns offset_s, ratio (the peak over the next-best peak
    outside GUARD_S) and z (the peak in standard deviations above the mean)."""
    clip = np.asarray(clip, dtype=np.float64)
    wav = np.asarray(wav, dtype=np.float64)
    nx, ny = len(clip), len(wav)
    if nx < rate or ny < rate:
        return {"offset_s": None, "ratio": 0.0, "z": 0.0, "reason": "under 1 s of audio"}
    clip = clip - clip.mean()
    wav = wav - wav.mean()
    n = 1 << int(np.ceil(np.log2(nx + ny - 1)))
    X = np.fft.rfft(clip, n)
    Y = np.fft.rfft(wav, n)
    R = np.conj(X) * Y
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    R[(freqs < BAND_HZ[0]) | (freqs > BAND_HZ[1] * rate)] = 0
    R /= np.abs(R) + 1e-12
    c = np.fft.irfft(R, n)
    del X, Y, R
    # c[L] = sum clip[i] * wav[i + L]. Lags run from -(nx - 1) to ny - 1.
    cc = np.abs(np.concatenate([c[n - nx + 1:], c[:ny]]))
    lags = np.arange(-(nx - 1), ny)
    lo = -(nx - 1) if lag_min_s is None else max(-(nx - 1), int(round(lag_min_s * rate)))
    hi = ny - 1 if lag_max_s is None else min(ny - 1, int(round(lag_max_s * rate)))
    if lo > hi:
        return {"offset_s": None, "ratio": 0.0, "z": 0.0, "reason": "the time window misses the WAV"}
    sel = slice(lo + nx - 1, hi + nx)
    cc, lags = cc[sel], lags[sel]
    k = int(np.argmax(cc))
    peak = float(cc[k])
    guard = int(GUARD_S * rate)
    rest = np.concatenate([cc[:max(0, k - guard)], cc[k + guard + 1:]])
    second = float(rest.max()) if rest.size else 0.0
    std = float(cc.std())
    return {
        "offset_s": float(lags[k]) / rate,
        "ratio": round(peak / second, 3) if second > 0 else float("inf"),
        "z": round((peak - float(cc.mean())) / std, 2) if std > 0 else 0.0,
    }


def trusted(result: dict, min_ratio: float, min_z: float) -> bool:
    return (result.get("offset_s") is not None and result["ratio"] >= min_ratio
            and result["z"] >= min_z)


def drift_ms(clip, wav, rate: int, offset_s: float, window_s: float = 10.0):
    """How far the end of the clip has slid against the WAV compared with its start, in ms. None
    when the clip is too short to tell (under 3 windows) or a window doesn't correlate. Short
    windows keep the peak sharp: inside a window the drift itself smears it."""
    w = int(window_s * rate)
    if len(clip) < 3 * w:
        return None
    found = []
    for start in (0, len(clip) - w):
        seg = clip[start:start + w]
        expect = offset_s + start / rate
        a = max(0, int((expect - 0.5) * rate))
        b = min(len(wav), int((expect + 0.5) * rate) + w)
        if b - a < w:
            return None
        r = correlate(seg, wav[a:b], rate, 0.0, (b - a - w) / rate)
        if not trusted(r, 1.5, 8.0):
            return None
        found.append(a / rate + r["offset_s"] - start / rate)
    return round((found[1] - found[0]) * 1000.0, 2)
