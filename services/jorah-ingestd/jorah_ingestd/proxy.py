"""1080p review proxies (ADR 0013, points 2 and 3).

Apple Log clips go through Apple's LUT with ffmpeg lut3d, and only a LUT whose SHA-256 matches the
pin in the root-owned config is used. Proxies are H.264 from h264_nvenc. If NVENC fails, libx264
makes the proxy and the manifest says so; a GPU problem never hides."""
import hashlib
import os
import re
import subprocess
from pathlib import Path

SAFE_PATH = re.compile(r"^/[A-Za-z0-9/._-]+$")
MATRIX = {"bt2020nc": "bt2020", "bt2020c": "bt2020", "bt709": "bt709",
          "smpte170m": "smpte170m", "bt470bg": "bt470"}
TAGS_709 = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-color_range", "tv"]


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lut_state(cfg) -> tuple:
    """("ok", path) or (problem, message). Apple Log proxies wait on anything but ok."""
    path = cfg.lut_path
    if not SAFE_PATH.match(path):
        return "bad_path", f"the LUT path {path!r} has characters ffmpeg's filter syntax would misread"
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        return "missing", f"no LUT at {path}; download Apple's Apple Log LUT and pin it (runbook)"
    if p.stat().st_size > 64 << 20:
        return "bad_file", "the LUT file is over 64 MB, so it isn't a .cube LUT"
    if not cfg.lut_sha256:
        return "unpinned", "the LUT is there but not pinned; run install-ingestd.sh --pin-lut"
    if sha256_file(p) != cfg.lut_sha256:
        return "mismatch", "the LUT's SHA-256 doesn't match the pin; it changed since it was pinned"
    with open(p, "rb") as f:
        head = f.read(1 << 16).decode(errors="replace")
    if "LUT_3D_SIZE" not in head:
        return "bad_file", "the LUT has no LUT_3D_SIZE line, so ffmpeg can't read it as a 3D .cube"
    return "ok", path


def video_filter(color: str, video: dict, height: int, lut_path=None) -> str:
    scale = f"scale=-2:{height}:flags=lanczos"
    tail = "format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
    if color == "apple_log":
        if not lut_path:
            raise ValueError("an Apple Log proxy needs a LUT")
        # swscale assumes BT.601 unless told, so name the source matrix. Apple Log is BT.2020
        # when the file doesn't say.
        m = MATRIX.get((video or {}).get("color_space"), "bt2020")
        rng = "full" if (video or {}).get("color_range") == "pc" else "tv"
        return (f"{scale}:in_color_matrix={m}:in_range={rng},format=gbrp16le,"
                f"lut3d=file={lut_path}:interp=tetrahedral,"
                f"scale=out_color_matrix=bt709:out_range=tv,{tail}")
    return f"{scale},{tail}"


def build_cmd(ffmpeg, src, dst, color, video, height, encoder, lut_path=None) -> list:
    vf = video_filter(color, video, height, lut_path)
    if encoder == "h264_nvenc":
        venc = ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-rc", "vbr", "-cq", "23",
                "-b:v", "8M", "-maxrate", "12M", "-bufsize", "16M", "-g", "30", "-bf", "2",
                "-profile:v", "high"]
    elif encoder == "libx264":
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-g", "30",
                "-profile:v", "high"]
    else:
        raise ValueError(f"unknown encoder {encoder}")
    return ([ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y", "-i", str(src),
             "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf] + venc + TAGS_709 +
            ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-movflags", "+faststart",
             "-f", "mp4", str(dst)])


def make(cfg, src: Path, dst: Path, color: str, video: dict, duration_s) -> dict:
    """Writes dst through a temporary name. Returns the manifest's proxy record."""
    lut = None
    if color == "apple_log":
        state, msg = lut_state(cfg)
        if state != "ok":
            return {"status": "waiting", "reason": msg}
        lut = msg
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.stem}.part.mp4")
    timeout = int(120 + 4 * duration_s) if isinstance(duration_s, float) else 7200
    errors = []
    for encoder in ([cfg.proxy_encoder, "libx264"] if cfg.proxy_encoder != "libx264" else ["libx264"]):
        cmd = build_cmd(cfg.ffmpeg, src, tmp, color, video, cfg.proxy_height, encoder, lut)
        try:
            p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
            ok, err = p.returncode == 0, p.stderr.decode(errors="replace").strip()[-300:]
        except (OSError, subprocess.TimeoutExpired) as e:
            ok, err = False, type(e).__name__
        if ok and tmp.exists() and tmp.stat().st_size > 0:
            os.replace(tmp, dst)
            rec = {"status": "done", "path": str(dst), "encoder": encoder, "lut": lut,
                   "size": dst.stat().st_size}
            if errors:
                rec["fallback_because"] = errors
            if color in ("hlg", "pq"):
                rec["note"] = f"{color} source: the proxy is not tone-mapped"
            return rec
        errors.append(f"{encoder}: {err or 'no output'}")
        tmp.unlink(missing_ok=True)
    return {"status": "failed", "reason": "; ".join(errors)}
