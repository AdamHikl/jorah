#!/usr/bin/env python3
"""Checks that every PlatformIO platform and package the bench install fetched is old enough.

Usage: pio-age-check.py <core-dir> [min-days]

Reads each installed package's .piopm record under <core-dir>/platforms and <core-dir>/packages,
asks the PlatformIO registry when that exact version was released, and prints one line per package.
Exit 0 when all are at least min-days old (default 7, Adam's rule); 1 when any is newer or its date
can't be found (unknown is a failure, never a pass); 2 on bad arguments.
Run by scripts/pc/install-robotics-bench.sh as root during install, the only time it has network.
"""
import datetime
import json
import pathlib
import sys
import urllib.parse
import urllib.request

REGISTRY = "https://api.registry.platformio.org/v3/packages"


def installed(core):
    for sub in ("platforms", "packages"):
        base = core / sub
        if not base.is_dir():
            continue
        for meta in sorted(base.glob("*/.piopm")):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                yield {"dir": meta.parent.name, "error": f"unreadable .piopm: {exc}"}
                continue
            spec = data.get("spec") or {}
            yield {
                "dir": meta.parent.name,
                "type": data.get("type", ""),
                "owner": spec.get("owner") or "",
                "name": data.get("name") or spec.get("name") or "",
                "version": data.get("version", ""),
            }


def released_at(pkg, cache):
    key = (pkg["owner"], pkg["type"], pkg["name"])
    if key not in cache:
        url = "/".join([REGISTRY] + [urllib.parse.quote(part, safe="") for part in key])
        req = urllib.request.Request(url, headers={"User-Agent": "jorah-bench-install"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            cache[key] = json.load(resp)
    for version in cache[key].get("versions", []):
        if version.get("name") == pkg["version"]:
            return datetime.datetime.fromisoformat(version["released_at"].replace("Z", "+00:00"))
    return None


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    core = pathlib.Path(argv[1])
    min_days = int(argv[2]) if len(argv) == 3 else 7
    now = datetime.datetime.now(datetime.timezone.utc)
    cache = {}
    bad = 0
    count = 0
    for pkg in installed(core):
        count += 1
        if "error" in pkg:
            print(f"  UNKNOWN  {pkg['dir']}: {pkg['error']}")
            bad += 1
            continue
        label = f"{pkg['owner']}/{pkg['name']}@{pkg['version']}"
        if not (pkg["owner"] and pkg["type"] and pkg["name"] and pkg["version"]):
            print(f"  UNKNOWN  {pkg['dir']}: incomplete .piopm ({label})")
            bad += 1
            continue
        try:
            when = released_at(pkg, cache)
        except Exception as exc:  # network or registry error: unknown, never a pass
            print(f"  UNKNOWN  {label}: registry lookup failed ({exc.__class__.__name__})")
            bad += 1
            continue
        if when is None:
            print(f"  UNKNOWN  {label}: version not listed in the registry")
            bad += 1
            continue
        age = (now - when).days
        verdict = "ok      " if age >= min_days else "TOO NEW "
        if age < min_days:
            bad += 1
        print(f"  {verdict} {label}  released {when.date()}  ({age} days)")
    if count == 0:
        print("  UNKNOWN  no installed PlatformIO packages found")
        return 1
    print(f"  {count} packages, {bad} failing the {min_days}-day rule or unknown")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
