"""ffprobe reports. A field ffprobe doesn't give, or gives as nonsense, is "unknown", never 0."""
import json
import re
import subprocess
from datetime import datetime, timezone

UNKNOWN = "unknown"
# Location tags (com.apple.quicktime.location.ISO6709 and the like) never enter a report.
_PRIVATE_TAG = re.compile(r"location|gps|iso6709", re.I)


def run_ffprobe(ffprobe: str, path, timeout: int = 120):
    """(data, error). ffprobe reads the file only; it gets no network and no stdin."""
    cmd = [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
           "--", str(path)]
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"ffprobe failed: {type(e).__name__}"
    if p.returncode != 0:
        return None, "ffprobe: " + (p.stderr.decode(errors="replace").strip()[-300:] or f"exit {p.returncode}")
    try:
        return json.loads(p.stdout), None
    except ValueError:
        return None, "ffprobe printed something that isn't JSON"


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return UNKNOWN
    return f if f == f and f > 0 else UNKNOWN


def _int(v):
    n = _num(v)
    return int(n) if n != UNKNOWN else UNKNOWN


def _rate(v):
    """"30000/1001" -> 29.97. "0/0" is unknown."""
    if not isinstance(v, str) or "/" not in v:
        return _num(v)
    a, _, b = v.partition("/")
    try:
        a, b = float(a), float(b)
    except ValueError:
        return UNKNOWN
    return round(a / b, 3) if a > 0 and b > 0 else UNKNOWN


def _str(v):
    return v if isinstance(v, str) and v and v != "unknown" else UNKNOWN


def _bit_depth(stream):
    n = _int(stream.get("bits_per_raw_sample"))
    if n != UNKNOWN:
        return n
    m = re.search(r"p(\d{2})(le|be)$", stream.get("pix_fmt") or "")
    if m:
        return int(m.group(1))
    return 8 if (stream.get("pix_fmt") or "").startswith(("yuv420p", "yuvj420p", "nv12")) else UNKNOWN


def _tags(*dicts):
    out = {}
    for d in dicts:
        for k, v in (d or {}).items():
            if isinstance(k, str) and not _PRIVATE_TAG.search(k) and isinstance(v, str) and len(v) < 200:
                out[k] = v
    return out


def _rotation(stream):
    for sd in stream.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                return int(float(sd["rotation"]))
            except (TypeError, ValueError):
                return UNKNOWN
    r = (stream.get("tags") or {}).get("rotate")
    return int(r) if r and r.lstrip("-").isdigit() else 0


def summarize(data: dict) -> dict:
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    tags = _tags(fmt.get("tags"), *(s.get("tags") for s in streams))
    report = {
        "container": _str(fmt.get("format_name")),
        "duration_s": _num(fmt.get("duration")),
        "bit_rate": _int(fmt.get("bit_rate")),
        "creation_time": _str(tags.get("creation_time")),
        "apple_creationdate": _str(tags.get("com.apple.quicktime.creationdate")),
        "video": None,
        "audio": [],
        "tags": tags,
    }
    if video:
        report["video"] = {
            "codec": _str(video.get("codec_name")),
            "profile": _str(video.get("profile")),
            "width": _int(video.get("width")),
            "height": _int(video.get("height")),
            "fps": _rate(video.get("avg_frame_rate")) if _rate(video.get("avg_frame_rate")) != UNKNOWN
                   else _rate(video.get("r_frame_rate")),
            "pix_fmt": _str(video.get("pix_fmt")),
            "bit_depth": _bit_depth(video),
            "color_primaries": _str(video.get("color_primaries")),
            "color_transfer": _str(video.get("color_transfer")),
            "color_space": _str(video.get("color_space")),
            "color_range": _str(video.get("color_range")),
            "rotation": _rotation(video),
        }
        if report["duration_s"] == UNKNOWN:
            report["duration_s"] = _num(video.get("duration"))
    for s in audio:
        report["audio"].append({
            "codec": _str(s.get("codec_name")),
            "sample_rate": _int(s.get("sample_rate")),
            "channels": _int(s.get("channels")),
            "duration_s": _num(s.get("duration")),
        })
    if report["duration_s"] == UNKNOWN and audio:
        report["duration_s"] = _num(audio[0].get("duration"))
    return report


def classify_color(report: dict, default: str) -> dict:
    """{"value", "basis"}. basis is "tag" (a tag names Apple Log), "metadata" (the color fields
    say Rec.709, HLG or PQ) or "assumed" (Adam's stated default, because nothing says)."""
    text = " ".join(f"{k} {v}" for k, v in report.get("tags", {}).items()).lower()
    if re.search(r"apple[ _-]?log", text):
        return {"value": "apple_log", "basis": "tag"}
    v = report.get("video") or {}
    trc, prim = v.get("color_transfer"), v.get("color_primaries")
    if trc == "arib-std-b67":
        return {"value": "hlg", "basis": "metadata"}
    if trc == "smpte2084":
        return {"value": "pq", "basis": "metadata"}
    if trc == "bt709" and prim in ("bt709", UNKNOWN):
        return {"value": "rec709", "basis": "metadata"}
    return {"value": default, "basis": "assumed"}


def parse_time(value, local_tz=None):
    """An aware UTC datetime from an ISO 8601 string, or None. A string with no zone is read in
    local_tz when one is given, otherwise refused."""
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        if local_tz is None:
            return None
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)
