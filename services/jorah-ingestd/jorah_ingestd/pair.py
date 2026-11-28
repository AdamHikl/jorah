"""Which Mac WAV belongs to which iPhone clip, and at what offset.

Start times narrow the candidates: the clip's creation time against the WAV's start from the
HUD's sidecar (issue #35), else its BWF time, else the copied file's modification time minus its
length. The correlation peak then decides. A clip with no WAV, no scratch audio or no trusted
peak becomes a question for Adam; nothing is guessed."""
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

from . import sync
from .probe import UNKNOWN, parse_time


def _dur(probe):
    d = (probe or {}).get("duration_s")
    return d if isinstance(d, float) else None


def _from_mtime(entry, dur):
    m = entry.get("source_mtime")
    if not isinstance(m, (int, float)) or dur is None:
        return None
    return datetime.fromtimestamp(m, timezone.utc) - timedelta(seconds=dur)


def clip_start(entry):
    probe = entry.get("probe") or {}
    for key in ("creation_time", "apple_creationdate"):
        t = parse_time(probe.get(key))
        if t:
            return t, "metadata"
    t = _from_mtime(entry, _dur(probe))
    return (t, "mtime") if t else (None, UNKNOWN)


def sidecar_for(wav_name: str, sidecars: dict):
    stem = PurePosixPath(wav_name).stem
    for name, data in sidecars.items():
        if not isinstance(data, dict):
            continue
        if data.get("audio_file") == PurePosixPath(wav_name).name:
            return data
        if PurePosixPath(name).name in (f"{stem}.json", f"{PurePosixPath(wav_name).name}.json"):
            return data
    return None


def wav_start(entry, sidecars: dict, local_tz: str):
    side = sidecar_for(entry["name"], sidecars)
    if side:
        t = parse_time(side.get("start_time"))
        if t:
            return t, "sidecar"
    tags = (entry.get("probe") or {}).get("tags") or {}
    d, t = tags.get("origination_date"), tags.get("origination_time")
    if d and t:
        when = parse_time(f"{d}T{t.replace('-', ':')}", ZoneInfo(local_tz))
        if when:
            return when, "bwf"
    t = _from_mtime(entry, _dur(entry.get("probe")))
    return (t, "mtime") if t else (None, UNKNOWN)


def _overlaps(c0, cdur, w0, wdur, skew):
    if None in (c0, w0) or cdur is None or wdur is None:
        return None
    a0, a1 = c0 - timedelta(seconds=skew), c0 + timedelta(seconds=cdur + skew)
    b0, b1 = w0, w0 + timedelta(seconds=wdur)
    return a0 < b1 and b0 < a1


def pair_take(videos, audios, sidecars, cfg, decode, path_of) -> list:
    """One result per video clip. decode(path) gives mono float audio at cfg.sync_rate, or None."""
    rate = cfg.sync_rate
    results = []
    wav_cache = {}
    starts = {a["name"]: wav_start(a, sidecars, cfg.local_tz) for a in audios}
    for v in videos:
        name = v["name"]
        res = {"clip": name, "wav": None, "status": "ask"}
        results.append(res)
        if not audios:
            res["reason"] = "no WAV in this take; copy the Mac's WAV into the same folder name"
            continue
        if not (v.get("probe") or {}).get("audio"):
            res["reason"] = "the clip has no scratch audio to sync against"
            continue
        clip_audio = decode(path_of(name))
        if clip_audio is None or len(clip_audio) < rate:
            res["reason"] = "the clip's scratch audio could not be read"
            continue
        c0, cbasis = clip_start(v)
        cdur = _dur(v.get("probe"))
        cands = [a for a in audios
                 if _overlaps(c0, cdur, starts[a["name"]][0], _dur(a.get("probe")), cfg.pair_skew_s)]
        by_time = bool(cands)
        if not cands:
            cands = list(audios)
        best = None
        for a in cands:
            an = a["name"]
            if an not in wav_cache:
                wav_cache[an] = decode(path_of(an))
            wav = wav_cache[an]
            if wav is None:
                continue
            r = sync.correlate(clip_audio, wav, rate)
            if r.get("offset_s") is not None and (best is None or r["z"] > best[1]["z"]):
                best = (a, r)
        if best is None:
            res["reason"] = "no WAV could be read"
            continue
        a, r = best
        w0, wbasis = starts[a["name"]]
        res.update({
            "wav": a["name"],
            "offset_s": round(r["offset_s"], 4),
            "ratio": r["ratio"],
            "z": r["z"],
            "time_basis": {"clip": cbasis, "wav": wbasis},
            "picked_by_time": by_time,
            "time_offset_s": round((c0 - w0).total_seconds(), 3) if c0 and w0 else UNKNOWN,
        })
        if not sync.trusted(r, cfg.sync_min_ratio, cfg.sync_min_z):
            res["reason"] = (f"low sync confidence (ratio {r['ratio']}, z {r['z']}); "
                             "check that this WAV belongs to this clip")
            continue
        d = sync.drift_ms(clip_audio, wav_cache[a["name"]], rate, r["offset_s"])
        res["drift_ms"] = d if d is not None else UNKNOWN
        if d is not None and abs(d) > cfg.drift_warn_ms:
            res["reason"] = f"the WAV drifts {d} ms against the clip over the take"
            continue
        res["status"] = "ok"
        res.pop("reason", None)
    return results
