"""jorah-ingestd: watches /srv/jorah-media/incoming and turns each copied take into a spool entry
with hashes, a probe report, a sound pairing and 1080p proxies (ADR 0013, issue #25).

  run              the service loop (systemd runs this)
  once             one pass by hand: scan, wait settle_s, ingest what held still, make proxies
  status           the takes and what each one is waiting on
  check            config, folders, tools, NVENC, LUT, free space
  probe FILE       the probe report and color class of one file
  sync CLIP WAV    the offset, confidence and drift between a clip and a WAV
"""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

from . import config as config_mod
from . import probe, proxy, scan, spool, sync

STOP = False
SYSTEM_CONFIG = "/etc/jorah-media/ingest.json"


def log(msg):
    print(msg, flush=True)


def _on_term(signum, frame):
    global STOP
    STOP = True


def take_lock(cfg):
    cfg.state.mkdir(parents=True, exist_ok=True)
    fd = os.open(cfg.state / "run.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def load_handled(cfg):
    try:
        data = json.loads((cfg.state / "handled.json").read_text())
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (FileNotFoundError, ValueError):
        return {}


class Runner:
    def __init__(self, cfg, clock=time.monotonic, decode=None):
        self.cfg = cfg
        self.settler = scan.Settler(cfg.settle_s, clock, load_handled(cfg))
        self.waiting = {}   # group key -> message (refused, settling or error)
        self.errored = set()  # handled for now, but retried after a restart
        self.decode = decode

    def ingest(self, found=None):
        found = scan.groups(self.cfg.incoming) if found is None else found
        for key in self.settler.update(found):
            if STOP:
                break
            folder, entries = found[key]
            try:
                res = spool.ingest_group(self.cfg, key, folder, entries, log=log, decode=self.decode)
            except Exception as e:  # one bad take must not stop the others
                res = {"status": "error", "message": f"{type(e).__name__}: {e}"}
            if res["status"] in ("refused", "settling"):
                if self.waiting.get(key) != res["message"]:
                    log(f"{key}: {res['message']}")
                self.waiting[key] = res["message"]
                continue
            self.settler.mark_handled(key, entries)
            self.waiting.pop(key, None)
            if res["status"] == "error":
                log(f"{key}: ingest failed: {res['message']}")
                self.waiting[key] = f"ingest failed: {res['message']}"
                self.errored.add(key)
            else:
                self.errored.discard(key)
        for key in list(self.waiting):
            if key not in found:
                self.waiting.pop(key)
                self.errored.discard(key)
        spool.write_json(self.cfg.state / "handled.json",
                         {k: v for k, v in self.settler.handled.items() if k not in self.errored})
        return found

    def one_proxy(self):
        job = spool.next_proxy_job(self.cfg)
        if job:
            spool.run_proxy(self.cfg, *job, log=log)
        return job is not None

    def write_status(self, found):
        pending = {k: "settling" for k, (_, e) in found.items()
                   if scan.has_content(e) and self.settler.handled.get(k) != scan.signature(e)}
        pending.update(self.waiting)
        spool.write_json(self.cfg.state / "status.json", spool.status_summary(self.cfg, pending))


def cmd_run(cfg, args):
    fd = take_lock(cfg)
    if fd is None:
        log("another jorah-ingestd holds the lock; stopping")
        return 1
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    r = Runner(cfg)
    log(f"jorah-ingestd watching {cfg.incoming} (settle {cfg.settle_s}s, poll {cfg.poll_s}s)")
    while not STOP:
        try:
            found = r.ingest()
            r.write_status(found)
            if not STOP and r.one_proxy():
                continue  # more may be queued; scan again without sleeping
        except OSError as e:  # a missing folder or a full disk: say so, keep going
            log(f"loop: {type(e).__name__}: {e}")
        for _ in range(int(cfg.poll_s * 10)):
            if STOP:
                break
            time.sleep(0.1)
    log("jorah-ingestd stopped")
    return 0


def cmd_once(cfg, args):
    fd = take_lock(cfg)
    if fd is None:
        log("the service is running and holds the lock; it will ingest on its own")
        return 1
    r = Runner(cfg)
    r.ingest()
    log(f"waiting {cfg.settle_s}s to see that the files hold still")
    time.sleep(cfg.settle_s)
    found = r.ingest()
    while r.one_proxy():
        pass
    r.write_status(found)
    return cmd_status(cfg, args)


def cmd_status(cfg, args):
    try:
        data = json.loads((cfg.state / "status.json").read_text())
    except (FileNotFoundError, ValueError):
        data = spool.status_summary(cfg)
        data["note"] = "no status.json yet; this was read from the spool now"
    if args.json:
        print(json.dumps(data, indent=1))
        return 0
    free = data.get("free_bytes")
    print(f"updated {data.get('updated_at')}, free {spool.gb(free) if isinstance(free, int) else free}")
    for key, msg in (data.get("incoming") or {}).items():
        print(f"  incoming {key}: {msg}")
    for t in data.get("takes", []):
        print(f"  {t['take']}: {t['status']}, {t['clips']} clip(s)")
        for q in t["questions"]:
            print(f"    ? {q}")
        for n in t["notes"]:
            print(f"    - {n}")
    return 0


def _ok(label, good, detail="", warn=False):
    mark = "ok  " if good else ("WARN" if warn else "FAIL")
    print(f"{mark} {label}{': ' + detail if detail else ''}")
    return good or warn


def cmd_check(cfg, args):
    good = True
    for name in ("root_path", "incoming", "spool", "proxies", "state"):
        p = getattr(cfg, name)
        need = os.W_OK | os.R_OK | os.X_OK
        good &= _ok(f"folder {p}", p.is_dir() and os.access(p, need),
                    "" if p.is_dir() else "missing", warn=name == "root_path")
    for tool in ("ffmpeg", "ffprobe"):
        path = getattr(cfg, tool)
        good &= _ok(tool, os.access(path, os.X_OK), path)
    good &= _ok("numpy (sound sync)", sync.np is not None,
                getattr(sync.np, "__version__", "missing: install python3-numpy"))
    if cfg.proxy_encoder == "h264_nvenc" and os.access(cfg.ffmpeg, os.X_OK):
        cmd = [cfg.ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
               "color=c=black:s=320x240:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"]
        try:
            p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
            nv, why = p.returncode == 0, p.stderr.decode(errors="replace").strip()[-200:]
        except (OSError, subprocess.TimeoutExpired) as e:
            nv, why = False, type(e).__name__
        _ok("NVENC test encode", nv, why or "h264_nvenc works", warn=True)
    state, msg = proxy.lut_state(cfg)
    _ok(f"Apple Log LUT ({state})", state == "ok", msg, warn=True)
    try:
        free = spool.free_bytes(cfg.root_path)
        _ok("free space", free > 50e9, spool.gb(free), warn=True)
    except OSError as e:
        good &= _ok("free space", False, type(e).__name__)
    return 0 if good else 1


def cmd_probe(cfg, args):
    data, err = probe.run_ffprobe(cfg.ffprobe, args.file)
    if not data:
        print(err, file=sys.stderr)
        return 1
    rep = probe.summarize(data)
    rep["color"] = probe.classify_color(rep, cfg.default_color)
    print(json.dumps(rep, indent=1))
    return 0


def cmd_sync(cfg, args):
    if sync.np is None:
        print("numpy is missing", file=sys.stderr)
        return 1
    clip = sync.decode_mono(cfg.ffmpeg, args.clip, cfg.sync_rate)
    wav = sync.decode_mono(cfg.ffmpeg, args.wav, cfg.sync_rate)
    if clip is None or wav is None:
        print("could not decode the audio of " + ("the clip" if clip is None else "the WAV"),
              file=sys.stderr)
        return 1
    r = sync.correlate(clip, wav, cfg.sync_rate)
    r["trusted"] = sync.trusted(r, cfg.sync_min_ratio, cfg.sync_min_z)
    if r["trusted"]:
        d = sync.drift_ms(clip, wav, cfg.sync_rate, r["offset_s"])
        r["drift_ms"] = d if d is not None else probe.UNKNOWN
    print(json.dumps(r, indent=1))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jorah-ingestd", description=__doc__.split("\n")[0])
    ap.add_argument("--config", help=f"JSON config (default {SYSTEM_CONFIG} when it exists)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("once")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    sub.add_parser("check")
    pr = sub.add_parser("probe")
    pr.add_argument("file")
    sy = sub.add_parser("sync")
    sy.add_argument("clip")
    sy.add_argument("wav")
    args = ap.parse_args(argv)
    path = args.config or (SYSTEM_CONFIG if os.path.exists(SYSTEM_CONFIG) else None)
    try:
        cfg = config_mod.load(path)
    except (OSError, ValueError) as e:
        print(f"config: {e}", file=sys.stderr)
        return 2
    if args.cmd in ("once", "status"):
        args.json = getattr(args, "json", False)
    return {"run": cmd_run, "once": cmd_once, "status": cmd_status, "check": cmd_check,
            "probe": cmd_probe, "sync": cmd_sync}[args.cmd](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
