"""Unpacking a downloaded tool without running anything from it.

- tar: Python's own tarfile with the "data" filter (no absolute paths, nothing outside the folder,
  no links that leave it, no devices, no setuid), after dropping `strip` leading folders.
- zip: by hand, the same rules; zip symlinks are refused.
- AppImage (type 2): the squashfs image after the ELF runtime is unpacked with `unsquashfs -o`.
  The AppImage itself is never started, so no code from the download runs at install.
- file: a single binary, copied and made executable.

Afterwards `harden` walks the tree: devices, fifos and sockets are refused, setuid, setgid and
write bits for others are cleared, and the size is counted.
"""

import os
import re
import shutil
import stat
import struct
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


class UnpackError(RuntimeError):
    pass


RELPART = re.compile(r"^[A-Za-z0-9_+@-][A-Za-z0-9._+@-]{0,99}$")  # jorah-tool-v1's path parts


def _stripped(name, strip):
    parts = [p for p in PurePosixPath(name).parts if p not in ("", ".")]
    if parts and parts[0] == "/":
        parts = parts[1:]
    if any(p == ".." for p in parts):
        raise UnpackError(f"{name[:80]} climbs out of the archive")
    parts = parts[strip:]
    return "/".join(parts) if parts else None


def unpack_tar(src, dest, strip=0):
    dest = Path(dest)
    dest.mkdir(parents=True)
    try:
        with tarfile.open(src, "r:*") as tar:
            members = []
            for member in tar.getmembers():
                name = _stripped(member.name, strip)
                if name is None:
                    continue
                changes = {"name": name}
                if member.islnk():
                    target = _stripped(member.linkname, strip)
                    if target is None:
                        raise UnpackError(f"hard link {member.name[:80]} points at a stripped folder")
                    changes["linkname"] = target
                members.append(member.replace(**changes, deep=False))
            if not members:
                raise UnpackError("the archive is empty after stripping")
            tar.extractall(dest, members=members, filter="data")
    except (tarfile.TarError, OSError) as error:
        raise UnpackError(f"tar: {type(error).__name__}: {str(error)[:160]}") from None


def unpack_zip(src, dest, strip=0):
    dest = Path(dest)
    dest.mkdir(parents=True)
    try:
        with zipfile.ZipFile(src) as archive:
            for info in archive.infolist():
                kind = (info.external_attr >> 16) & 0o170000
                if kind == stat.S_IFLNK:
                    raise UnpackError(f"{info.filename[:80]} is a symlink; zip links aren't unpacked")
                name = _stripped(info.filename, strip)
                if name is None:
                    continue
                target = dest / name
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, "xb") as out:
                    shutil.copyfileobj(source, out, 1 << 20)
                mode = (info.external_attr >> 16) & 0o777
                os.chmod(target, 0o755 if mode & 0o111 else 0o644)
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        raise UnpackError(f"zip: {type(error).__name__}: {str(error)[:160]}") from None


def appimage_offset(path):
    """Where a type 2 AppImage's squashfs starts: just after the ELF runtime's section headers."""
    with open(path, "rb") as handle:
        head = handle.read(64)
        if len(head) < 64 or head[:4] != b"\x7fELF":
            raise UnpackError("not an AppImage: no ELF header")
        if head[4] != 2 or head[5] != 1:
            raise UnpackError("not a 64-bit little-endian AppImage")
        shoff = struct.unpack_from("<Q", head, 0x28)[0]
        shentsize, shnum = struct.unpack_from("<HH", head, 0x3A)
        offset = shoff + shentsize * shnum
        size = os.fstat(handle.fileno()).st_size
        if not 64 <= offset < size - 4:
            raise UnpackError("the AppImage's ELF header points outside the file")
        handle.seek(offset)
        if handle.read(4) != b"hsqs":
            raise UnpackError("no squashfs after the AppImage runtime (only type 2 squashfs AppImages are supported)")
    return offset


def unpack_appimage(src, dest, unsquashfs="/usr/bin/unsquashfs", run=subprocess.run):
    offset = appimage_offset(src)
    dest = Path(dest)
    if os.path.lexists(dest):
        raise UnpackError(f"{dest} exists")
    done = run([unsquashfs, "-no-progress", "-no-xattrs", "-o", str(offset), "-d", str(dest), str(src)],
               capture_output=True, timeout=1800, check=False, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    if done.returncode != 0:
        tail = (done.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or ["no message"]
        raise UnpackError(f"unsquashfs failed: {tail[0][:200]}")
    if not dest.is_dir():
        raise UnpackError("unsquashfs made no folder")


def place_file(src, dest, name):
    dest = Path(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(src, dest / name)
    os.chmod(dest / name, 0o755)


def harden(root):
    """Refuse special files, clear setuid/setgid/sticky and others' write bits. Returns total bytes."""
    total = 0
    root = Path(root)
    for here, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(here, name)
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                continue
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise UnpackError(f"{os.path.relpath(path, root)[:80]} is a device, fifo or socket")
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
                os.chmod(path, 0o755 if info.st_mode & 0o111 else 0o644)
            else:
                os.chmod(path, 0o755)
    os.chmod(root, 0o755)
    return total


def executables(root, limit=8):
    """Up to `limit` executable files under `root`, as plain relative paths (names that couldn't go in
    a request's commands are left out), shallowest first: what a refusal names so the request can
    be fixed without guessing the archive's layout."""
    root = Path(root)
    found = []
    for here, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(here, name)
            info = os.lstat(path)
            rel = os.path.relpath(path, root)
            if stat.S_ISREG(info.st_mode) and info.st_mode & 0o111 and len(rel) <= 120 and \
                    all(RELPART.match(p) and p not in (".", "..") for p in rel.split(os.sep)):
                found.append(rel)
    found.sort(key=lambda r: (r.count(os.sep), r))
    return found[:limit]


def inside(root, rel):
    """The real path of `rel` under `root` if it resolves inside `root` to a regular file, else None."""
    root = os.path.realpath(root)
    path = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        return None
    return path
