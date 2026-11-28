"""Moves a settled take from incoming/ into the read-only spool, and keeps its manifest.

Each file is copied and hashed in one pass, so the SHA-256 is of exactly the bytes in the spool.
The spool copy belongs to the ingest user and is read-only (0444). The original is removed only
after the copy is in place and the original hasn't changed. If the ingest user can't remove it,
the take still lands and the note says to delete the original in Explorer."""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import pair, probe, proxy, scan

SCHEMA = "jorah-media/take@1"
CONTENT = ("video", "audio", "sidecar", "other")
SIDECAR_MAX = 1 << 20


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def gb(n):
    return f"{n / 1e9:.1f} GB"


def free_bytes(path) -> int:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def copy_hash(src: Path, dst: Path, chunk: int = 8 << 20) -> tuple:
    """Copies src to a new file dst (never overwriting) and returns (sha256, bytes)."""
    import hashlib
    h = hashlib.sha256()
    n = 0
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with open(src, "rb") as fin, os.fdopen(fd, "wb", closefd=False) as fout:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                h.update(b)
                fout.write(b)
                n += len(b)
            fout.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    return h.hexdigest(), n


def manifest_path(take_dir: Path) -> Path:
    return take_dir / "take.json"


def read_manifest(take_dir: Path):
    try:
        return json.loads(manifest_path(take_dir).read_text())
    except FileNotFoundError:
        return None


def write_json(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def new_manifest(tid: str, now) -> dict:
    return {"schema": SCHEMA, "take": tid, "created_at": iso(now), "updated_at": iso(now),
            "sources": [], "files": {}, "ignored": [], "refused": [], "sidecars": {},
            "pairs": [], "proxies": {}, "questions": [], "notes": [], "status": "ingesting"}


def _place(tmp: Path, dst: Path) -> None:
    """Read-only, and never over an existing file."""
    os.chmod(tmp, 0o444)
    os.link(tmp, dst)
    os.unlink(tmp)


def _remove_empty_dirs(folder: Path) -> None:
    for dirpath, _, _ in sorted(os.walk(folder, followlinks=False), key=lambda t: -len(t[0])):
        try:
            os.rmdir(dirpath)
        except OSError:
            pass


def ingest_group(cfg, key, folder, entries, now=None, log=print, decode=None) -> dict:
    """Returns {"take", "status", "message"}. status "refused" and "settling" mean try again
    later; anything else means this signature has been dealt with."""
    now = now or utcnow()
    tid = scan.take_id(key, now)
    take_dir = cfg.spool / tid
    usable = [e for e in entries if e.kind in CONTENT]
    junk = [e for e in entries if e.kind == "junk"]
    bad = [e for e in entries if e.kind in ("symlink", "special")]
    total = sum(e.size for e in usable)
    free = free_bytes(cfg.root_path)
    if free < cfg.space_factor * total:
        return {"take": tid, "status": "refused",
                "message": f"free space {gb(free)} is below {cfg.space_factor:g} x the take's "
                           f"{gb(total)}; it retries once space is freed"}
    man = read_manifest(take_dir) or new_manifest(tid, now)
    base = folder if folder is not None else cfg.incoming
    source = f"incoming/{folder.name}" if folder is not None else "incoming/ (loose files)"
    if source not in man["sources"]:
        man["sources"].append(source)
    media = take_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    left, conflicts = [], []
    for e in usable:
        src, dst = base / e.rel, media / e.rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(f".part-{dst.name}")
        tmp.unlink(missing_ok=True)
        log(f"{tid}: copying {e.rel} ({gb(e.size)})")
        sha, n = copy_hash(src, tmp)
        st = os.lstat(src)
        if n != e.size or st.st_size != e.size or st.st_mtime_ns != e.mtime_ns:
            tmp.unlink()
            write_json(manifest_path(take_dir), man)
            return {"take": tid, "status": "settling",
                    "message": f"{e.rel} changed while it was copied; waiting for it to settle"}
        known = man["files"].get(e.rel)
        if known is None and dst.exists():
            # Left by a run that stopped between placing the file and writing the manifest.
            known = {"sha256": proxy.sha256_file(dst), "orphan": True}
        replaceable = known and (known.get("orphan") or known.get("probe", "") is None)
        if known and known["sha256"] != sha and not replaceable:
            tmp.unlink()
            conflicts.append(e.rel)
            continue
        if known and known["sha256"] == sha and not known.get("orphan"):
            tmp.unlink()  # the spool already holds these exact bytes
            if man["proxies"].get(e.rel, {}).get("status") == "failed":
                del man["proxies"][e.rel]  # copying a clip again retries its proxy
        else:
            if known:  # an unreadable copy, or an orphan: the new bytes replace it
                dst.unlink()
                man["proxies"].pop(e.rel, None)
            _place(tmp, dst)
            man["files"][e.rel] = {"kind": e.kind, "size": n, "sha256": sha,
                                   "source_mtime": st.st_mtime_ns / 1e9, "ingested_at": iso(now)}
        try:
            os.unlink(src)
        except OSError:
            left.append(e.rel)
    for e in junk:
        dst = take_dir / "ignored" / e.rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not dst.exists():
                os.rename(base / e.rel, dst)
                man["ignored"].append(e.rel)
        except OSError:
            left.append(e.rel)
    for e in bad:
        rec = {"name": e.rel, "kind": e.kind}
        if rec not in man["refused"]:
            man["refused"].append(rec)
    if folder is not None:
        _remove_empty_dirs(folder)
    man["notes"] = [n for n in man["notes"] if not n.startswith("originals left")]
    if left:
        man["notes"].append(f"originals left in {source}: {len(left)} file(s) could not be removed "
                            "(permission); the spool holds them, so delete them in Explorer")
    man["conflicts"] = [f"{source}/{c} has the same name as a file in this take but different "
                        "content; rename it and copy it again" for c in conflicts]
    analyze(cfg, take_dir, man, decode=decode, log=log)
    man["updated_at"] = iso(utcnow())
    write_json(manifest_path(take_dir), man)
    log(f"{tid}: {man['status']}, {len(man['files'])} file(s), {len(man['questions'])} question(s)")
    return {"take": tid, "status": man["status"], "message": "; ".join(man["questions"][:3])}


def _read_sidecar(path: Path) -> dict:
    if path.stat().st_size > SIDECAR_MAX:
        return {"error": "over 1 MB"}
    try:
        data = json.loads(path.read_text())
    except (ValueError, UnicodeDecodeError):
        return {"error": "not JSON"}
    if not isinstance(data, dict):
        return {"error": "not a JSON object"}
    out = {k: data[k] for k in ("schema", "audio_file", "start_time", "device", "sample_rate", "take")
           if isinstance(data.get(k), (str, int, float))}
    lines = data.get("lines")
    if isinstance(lines, list):
        out["lines"] = [{"line": x["line"], "t": x["t"]} for x in lines[:10000]
                        if isinstance(x, dict) and isinstance(x.get("line"), int)
                        and isinstance(x.get("t"), (int, float))]
    return out


def analyze(cfg, take_dir: Path, man: dict, decode=None, log=print) -> None:
    """Probes new clips, reads sidecars, classifies color, pairs sound, and sets the status."""
    from . import sync
    media = take_dir / "media"
    for rel, f in man["files"].items():
        if f["kind"] in ("video", "audio") and "probe" not in f:
            data, err = probe.run_ffprobe(cfg.ffprobe, media / rel)
            f["probe"] = probe.summarize(data) if data else None
            if err:
                f["probe_error"] = err
            if f["kind"] == "video" and f["probe"] and not f["probe"].get("video"):
                f["kind"] = "audio"  # a .mov with sound only
        if f["kind"] == "video":
            f["color"] = (probe.classify_color(f["probe"], cfg.default_color) if f.get("probe")
                          else {"value": cfg.default_color, "basis": "assumed"})
        if f["kind"] == "sidecar" and rel not in man["sidecars"]:
            man["sidecars"][rel] = _read_sidecar(media / rel)
    questions, notes = [], [n for n in man["notes"] if n.startswith("originals left")]
    videos = [dict(name=r, **f) for r, f in sorted(man["files"].items()) if f["kind"] == "video"]
    audios = [dict(name=r, **f) for r, f in sorted(man["files"].items())
              if f["kind"] == "audio" and f.get("probe")]
    for v in videos:
        if not v.get("probe"):
            questions.append(f"{v['name']}: unreadable ({v.get('probe_error', 'no report')}); "
                             "copy it again from the card")
            continue
        c = v["color"]
        if c["basis"] != "assumed" and c["value"] != cfg.default_color:
            questions.append(f"{v['name']}: tagged {c['value']}, but the stated format is "
                             f"{cfg.default_color}; which is it?")
        vid = v["probe"]["video"]
        if vid["codec"] not in ("hevc", probe.UNKNOWN):
            notes.append(f"{v['name']}: codec {vid['codec']}, not HEVC")
        if isinstance(vid["fps"], float) and abs(vid["fps"] - 30.0) > 0.01:
            notes.append(f"{v['name']}: {vid['fps']} fps, not 30")
    if videos and sync.np is None:
        man["pairs"] = [{"clip": v["name"], "status": "ask", "reason": "numpy is missing"} for v in videos]
    elif videos:
        dec = decode or (lambda p: sync.decode_mono(cfg.ffmpeg, p, cfg.sync_rate))
        man["pairs"] = pair.pair_take(videos, audios, man["sidecars"], cfg, dec, lambda r: media / r)
    for p in man["pairs"]:
        if p["status"] != "ok":
            questions.append(f"{p['clip']}: {p['reason']}")
    questions += man.get("conflicts", [])
    man["questions"], man["notes"] = questions, notes
    set_status(cfg, man)


def proxy_path(cfg, tid: str, rel: str) -> Path:
    stem = rel.rsplit(".", 1)[0].replace("/", "__")
    return cfg.proxies / tid / f"{stem}.proxy.mp4"


def set_status(cfg, man: dict) -> None:
    clips = [r for r, f in man["files"].items() if f["kind"] == "video" and f.get("probe")]
    states = [man["proxies"].get(r, {}).get("status") for r in clips]
    if man["questions"]:
        man["status"] = "ask"
    elif any(s == "waiting" for s in states):
        man["status"] = "waiting"
    elif any(s == "failed" for s in states):
        man["status"] = "failed"
    elif any(s is None for s in states):
        man["status"] = "working"
    else:
        man["status"] = "ready"


def next_proxy_job(cfg):
    """(take_dir, rel) of the next clip that needs a proxy, or None. A clip waiting on the LUT is
    offered again only once the LUT is in place and pinned. A failed one waits until Adam copies
    the clip again."""
    lut_ok = None
    if not cfg.spool.exists():
        return None
    for take_dir in sorted(p for p in cfg.spool.iterdir() if p.is_dir()):
        man = read_manifest(take_dir)
        if not man:
            continue
        for rel, f in sorted(man["files"].items()):
            if f["kind"] != "video" or not f.get("probe"):
                continue
            rec = man["proxies"].get(rel)
            if rec is None:
                return take_dir, rel
            if rec.get("status") == "waiting":
                if lut_ok is None:
                    lut_ok = proxy.lut_state(cfg)[0] == "ok"
                if lut_ok:
                    return take_dir, rel
    return None


def run_proxy(cfg, take_dir: Path, rel: str, log=print) -> dict:
    man = read_manifest(take_dir)
    f = man["files"][rel]
    log(f"{man['take']}: proxy for {rel}")
    try:
        rec = proxy.make(cfg, take_dir / "media" / rel, proxy_path(cfg, man["take"], rel),
                         f["color"]["value"], f["probe"]["video"], f["probe"]["duration_s"])
    except Exception as e:  # recorded, so the same job isn't offered forever
        rec = {"status": "failed", "reason": f"{type(e).__name__}: {e}"}
    man["proxies"][rel] = rec
    set_status(cfg, man)
    man["updated_at"] = iso(utcnow())
    write_json(manifest_path(take_dir), man)
    log(f"{man['take']}: proxy {rel} {rec['status']}{': ' + rec['reason'] if 'reason' in rec else ''}")
    return rec


def status_summary(cfg, incoming_status=None) -> dict:
    takes = []
    if cfg.spool.exists():
        for take_dir in sorted(p for p in cfg.spool.iterdir() if p.is_dir()):
            man = read_manifest(take_dir)
            if man:
                takes.append({"take": man["take"], "status": man["status"],
                              "clips": sum(1 for f in man["files"].values() if f["kind"] == "video"),
                              "questions": man["questions"], "notes": man["notes"],
                              "updated_at": man["updated_at"]})
    try:
        free = free_bytes(cfg.root_path)
    except OSError:
        free = probe.UNKNOWN
    return {"schema": "jorah-media/status@1", "updated_at": iso(utcnow()), "free_bytes": free,
            "incoming": incoming_status or {}, "takes": takes}


def remove_tree_owned(path: Path) -> None:
    """Only for tests and scratch roots."""
    shutil.rmtree(path, ignore_errors=True)
