"""What is in incoming/, and when a take has stopped growing.

Each top-level folder is one take. Loose files at the top level form one take together. Nothing
is followed through a symlink, and Mac and Windows litter (AppleDouble `._` files, Thumbs.db,
`:Zone.Identifier` streams) is set aside, not hashed."""
import hashlib
import os
import re
import stat
import time
from dataclasses import dataclass, replace
from pathlib import Path

VIDEO_EXT = {".mov", ".mp4", ".m4v"}
AUDIO_EXT = {".wav", ".bwf", ".m4a", ".aif", ".aiff", ".flac"}
JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".localized"}
JUNK_DIRS = {".spotlight-v100", ".trashes", ".fseventsd", ".temporaryitems",
             "system volume information", "$recycle.bin"}
LOOSE = "loose"


@dataclass(frozen=True)
class Entry:
    rel: str          # path inside the take, with "/" separators
    size: int
    mtime_ns: int
    kind: str         # video, audio, sidecar, other, junk, symlink, special


def is_junk(name: str) -> bool:
    n = name.lower()
    return n in JUNK_NAMES or n.startswith("._") or ":zone.identifier" in n


def kind_of(name: str) -> str:
    if is_junk(name):
        return "junk"
    ext = os.path.splitext(name)[1].lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext == ".json":
        return "sidecar"
    return "other"


def _entry(path: Path, rel: str, in_junk_dir: bool) -> Entry:
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        kind = "symlink"
    elif not stat.S_ISREG(st.st_mode):
        kind = "special"
    elif in_junk_dir:
        kind = "junk"
    else:
        kind = kind_of(path.name)
    return Entry(rel, st.st_size, st.st_mtime_ns, kind)


def walk(folder: Path) -> list:
    """Every file under a take folder, never following a link."""
    out = []
    for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
        base = Path(dirpath)
        rel_dir = base.relative_to(folder).as_posix()
        in_junk = any(part.lower() in JUNK_DIRS for part in Path(rel_dir).parts)
        # A symlinked folder shows up in dirnames; os.walk doesn't enter it, so record it here.
        for d in dirnames:
            if os.path.islink(base / d):
                rel = d if rel_dir == "." else f"{rel_dir}/{d}"
                out.append(_entry(base / d, rel, in_junk))
        for f in filenames:
            rel = f if rel_dir == "." else f"{rel_dir}/{f}"
            out.append(_entry(base / f, rel, in_junk))
    return sorted(out, key=lambda e: e.rel)


def groups(incoming: Path) -> dict:
    """{key: (source_path_or_None, [Entry])}. A folder's key is "dir:<name>"; loose files share
    the key "loose"."""
    result = {}
    loose = []
    try:
        names = sorted(os.listdir(incoming))
    except FileNotFoundError:
        return result
    for name in names:
        path = incoming / name
        if os.path.isdir(path) and not os.path.islink(path):
            entries = walk(path)
            if name.lower() in JUNK_DIRS:  # a card's .Trashes or .Spotlight-V100 copied over
                entries = [replace(e, kind="junk") if e.kind not in ("symlink", "special") else e
                           for e in entries]
            result[f"dir:{name}"] = (path, entries)
        else:
            loose.append(_entry(path, name, False))
    if loose:
        result[LOOSE] = (None, loose)
    return result


def signature(entries) -> str:
    h = hashlib.sha256()
    for e in entries:
        h.update(f"{e.rel}\0{e.size}\0{e.mtime_ns}\n".encode())
    return h.hexdigest()


def has_content(entries) -> bool:
    return any(e.kind in ("video", "audio", "sidecar", "other") for e in entries)


class Settler:
    """Says which groups have not changed for settle_s seconds. A group that was handled with
    a given signature isn't offered again until it changes."""

    def __init__(self, settle_s: float, clock=time.monotonic, handled=None):
        self.settle_s = settle_s
        self.clock = clock
        self.seen = {}
        self.handled = dict(handled or {})

    def update(self, found: dict) -> list:
        now = self.clock()
        ready = []
        for key, (_, entries) in found.items():
            sig = signature(entries)
            last = self.seen.get(key)
            if last is None or last[0] != sig:
                self.seen[key] = (sig, now)
                continue
            if self.handled.get(key) == sig:
                continue
            if now - last[1] >= self.settle_s and has_content(entries):
                ready.append(key)
        for key in list(self.seen):
            if key not in found:
                del self.seen[key]
                self.handled.pop(key, None)
        return ready

    def mark_handled(self, key: str, entries) -> None:
        self.handled[key] = signature(entries)


def take_id(key: str, now_utc) -> str:
    if key == LOOSE:
        return "loose-" + now_utc.strftime("%Y%m%d-%H%M%S")
    name = key.split(":", 1)[1]
    s = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-._")[:60].strip("-._")
    return s or "take"
