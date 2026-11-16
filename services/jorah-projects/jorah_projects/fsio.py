"""File and YAML access inside a work repo that a sandboxed run wrote, so it's untrusted.

- Every path is checked component by component: no symlinks, nothing outside the repo. A run could
  commit `project/field-data -> /home/jorah/.ssh`, and the runner must never read a secret into a
  commit or write through a link.
- YAML is read with PyYAML's safe loader, with timestamps left as text, so a date stays the string
  the schema checks (`2026-11-16`), and written back block style.
"""

import json
import os
import stat
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError as error:  # pragma: no cover - the install checks it
    raise SystemExit("jorah-projects needs PyYAML (Ubuntu: apt install python3-yaml)") from error

MAX_STATE_BYTES = 2 << 20  # a state file over 2 MB is refused, not parsed


class Unsafe(ValueError):
    """A path leaves the repo or passes through a link."""


class Loader(yaml.SafeLoader):
    pass


class Dumper(yaml.SafeDumper):
    pass


def _without_timestamps(cls):
    cls.yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
        for first, resolvers in cls.yaml_implicit_resolvers.items()
    }


_without_timestamps(Loader)
_without_timestamps(Dumper)


def _str(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _str)
Dumper.ignore_aliases = lambda self, data: True  # the contract's loader refuses anchors and aliases


def safe_path(root, rel, *, must_exist=False):
    """The absolute path of `rel` under `root`, refusing links, `..` and absolute parts."""
    root = Path(root)
    parts = Path(rel).parts
    if not parts or Path(rel).is_absolute() or any(p in ("..", "") for p in parts):
        raise Unsafe(f"{rel}: not a plain path inside the repo")
    current = root
    for i, part in enumerate(parts):
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if must_exist:
                raise
            # Nothing further exists, so nothing further can be a link.
            return root.joinpath(*parts)
        if stat.S_ISLNK(info.st_mode):
            raise Unsafe(f"{'/'.join(parts[:i + 1])} is a link")
        if i < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise Unsafe(f"{'/'.join(parts[:i + 1])} isn't a folder")
    return current


def read_bytes(root, rel):
    """Bytes of a regular file, or None if it doesn't exist. Refuses links and big files."""
    path = safe_path(root, rel)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise Unsafe(f"{rel} isn't a regular file")
        if info.st_size > MAX_STATE_BYTES:
            raise Unsafe(f"{rel} is over {MAX_STATE_BYTES} bytes")
        return handle.read()


def write_bytes(root, rel, data, mode=0o644):
    """Write a file atomically inside the repo, making folders as needed, never through a link."""
    path = safe_path(root, rel)
    parent = path.parent
    rel_parent = os.path.relpath(parent, root)
    if rel_parent != ".":
        safe_path(root, rel_parent)
        parent.mkdir(parents=True, exist_ok=True)
        safe_path(root, rel_parent, must_exist=True)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".jorah-runner-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, mode)
        safe_path(root, rel)  # still not a link right before the swap
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def remove(root, rel):
    path = safe_path(root, rel)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def parse_yaml(data):
    """Parsed YAML, or raises ValueError (never returns half a document)."""
    if data is None:
        return None
    try:
        return yaml.load(data.decode("utf-8"), Loader=Loader)  # noqa: S506 - SafeLoader subclass
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ValueError(f"not valid YAML: {str(error).splitlines()[0]}") from None


def dump_yaml(value):
    return yaml.dump(value, Dumper=Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100).encode("utf-8")


def json_safe(value):
    """True if the parsed YAML holds only JSON types (the schemas speak JSON)."""
    try:
        json.dumps(value, allow_nan=False)
        return True
    except (TypeError, ValueError):
        return False


# ---- private runner files (outside the repo, trusted) -------------------------------------------

def write_private_json(path, value):
    """Atomic write, mode 600, folder 700."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def read_private_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
