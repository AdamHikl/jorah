"""The installer: approved requests in, tools in /opt/jorah-toolbox out (docs/runbooks/toolbox.md).

Runs as the system user jorah-toolbox, started by jorah-toolbox.path when the jorah-projects plugin
puts an approval in /var/lib/jorah-toolbox/approved/ (only after Adam's card). It never runs
anything it downloaded, never has root, and can't read Jorah's home or secrets.

For each approval, oldest first:
1. The file must be a plain file owned by jorah, under 64 KB. The manifest is checked again against
   jorah-tool-v1 with today's date, and must hash to the approval's id.
2. archive: download over https; for a GitHub release asset, GitHub's API must say the release is
   at least 7 days old, not a draft or pre-release, and hold the same SHA-256 when it holds one;
   the file must match the manifest's SHA-256 and sizes; unpack (unpack.py) into a staging folder;
   every command must resolve to a file inside the tool; then the tool moves into
   tools/<name>/<version>, wrappers go into bin/, and installed.json is rewritten.
   apt: nothing is installed here. The result says `needs-root` with the one command Adam runs as
   root (scripts/pc/toolbox-apt.sh), which installs only from Ubuntu's own archive and then calls
   `record-apt` to add the tool here.
3. A result goes to results/<id>.json, and the approval is removed.
"""

import fcntl
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import fetch, unpack

REPO_ROOT = Path(__file__).resolve().parents[3]
MAX_APPROVAL = 64 * 1024
APT_SCRIPT = "/opt/jorah/scripts/pc/toolbox-apt.sh"


def _load_contract(folder):
    import importlib.util

    path = Path(folder) / "toolcheck.py"
    spec = importlib.util.spec_from_file_location("jorah_toolcheck", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class Settings:
    opt: Path = Path("/opt/jorah-toolbox")
    var: Path = Path("/var/lib/jorah-toolbox")
    contract: Path = REPO_ROOT / "packages/contracts/toolbox"
    # Where each tool's wrapper sends its writes: ~/sandbox is the one place outside a project
    # that the project sandbox may write.
    state_root: str = "/home/jorah/sandbox/.cache/jorah-toolbox"
    unsquashfs: str = "/usr/bin/unsquashfs"
    approver: str | None = "jorah"  # approvals must be owned by this user; None in tests
    min_free_bytes: int = 20 * 1024**3
    github_api: str = "https://api.github.com"
    today: object = field(default=None)  # a callable returning a date; None: the real date

    def day(self):
        return self.today() if self.today else date.today()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path, data, mode=0o644):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_json(path, default=None, limit=4 << 20):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return default
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError(f"{Path(path).name} isn't a plain file under {limit // 1024} KB")
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Refused(RuntimeError):
    """The approval or the download fails a rule; the result says which."""


class Installer:
    def __init__(self, settings=None, *, open_url=fetch.urlopen, run=subprocess.run, log=None):
        self.s = settings or Settings()
        self.tc = _load_contract(self.s.contract)
        self.open_url = open_url
        self.run = run
        self.log = log or (lambda text: print(text, flush=True))

    # ---- paths -----------------------------------------------------------------------------------

    @property
    def approved(self):
        return Path(self.s.var) / "approved"

    @property
    def results(self):
        return Path(self.s.var) / "results"

    @property
    def registry(self):
        return Path(self.s.opt) / "installed.json"

    def installed(self):
        data = read_json(self.registry, {"v": 1, "tools": {}})
        if not isinstance(data, dict) or not isinstance(data.get("tools"), dict):
            raise ValueError("installed.json is damaged")
        return data

    # ---- the queue -------------------------------------------------------------------------------

    def run_queue(self):
        """Process every approval, oldest first. Returns the results."""
        for sub in ("results", "downloads"):
            (Path(self.s.var) / sub).mkdir(exist_ok=True)
        for sub in ("tools", "bin", ".staging"):
            (Path(self.s.opt) / sub).mkdir(exist_ok=True)
        lock = open(Path(self.s.var) / "downloads" / "installer.lock", "a+")  # noqa: SIM115 - held for the queue
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.log("another installer is running; this one stops")
            lock.close()
            return []
        out = []
        try:
            # Only whole approvals arrive here (the plugin writes elsewhere and renames them in), so
            # anything that isn't one is moved aside: jorah-toolbox.path starts this service while
            # the folder isn't empty, and a stray file must not keep starting it.
            stray = Path(self.s.var) / "downloads" / "stray"
            for path in self.approved.iterdir():
                if path.suffix != ".json" or not stat.S_ISREG(os.lstat(path).st_mode):
                    stray.mkdir(exist_ok=True)
                    os.replace(path, stray / f"{path.name[:60]}.{os.getpid()}")
                    self.log(f"moved aside {path.name[:60]}: not an approval")
            entries = sorted((p for p in self.approved.glob("*.json")), key=lambda p: (os.lstat(p).st_mtime, p.name))
            for path in entries:
                result = self.process(path)
                write_json(self.results / f"{result['id']}.json", result)
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                self.log(f"{result['id']}: {result['status']}{': ' + result['error'] if result.get('error') else ''}")
                out.append(result)
        finally:
            lock.close()
        return out

    def _read_approval(self, path):
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):
            raise Refused("the approval isn't a plain file")
        if info.st_size > MAX_APPROVAL:
            raise Refused("the approval is over 64 KB")
        if self.s.approver is not None:
            try:
                owner = pwd.getpwuid(info.st_uid).pw_name
            except KeyError:
                owner = str(info.st_uid)
            if owner != self.s.approver:
                raise Refused(f"the approval belongs to {owner}, not {self.s.approver}")
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise Refused("the approval isn't JSON") from None
        if not isinstance(data, dict) or data.get("v") != 1 or data.get("action") not in ("install", "remove"):
            raise Refused("the approval isn't a v1 install or remove")
        return data

    def process(self, path):
        stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(path).stem)[:40] or "unnamed"
        result = {"v": 1, "id": stem, "action": None, "name": None, "version": None, "status": "failed", "at": _now(),
                  "checks": {}, "error": None, "rootCommand": None, "manifest": None}
        try:
            approval = self._read_approval(path)
            result["action"] = approval["action"]
            if approval["action"] == "remove":
                name = approval.get("name")
                if not isinstance(name, str) or not self.tc.NAME.match(name):
                    raise Refused("the removal names no tool")
                result.update(id=stem, name=name)
                return self.remove(name, result)
            manifest = approval.get("manifest")
            problems = self.tc.check(manifest, self.s.day())
            if problems:
                raise Refused(f"the request breaks jorah-tool-v1: {problems[0]}")
            pid = self.tc.proposal_id(manifest)
            if approval.get("id") != pid or stem != pid:
                raise Refused("the approval's id doesn't match its request")
            result.update(id=pid, name=manifest["name"], version=manifest["version"], manifest=manifest)
            if manifest["kind"] == "apt":
                return self.needs_root(manifest, pid, result)
            return self.install_archive(manifest, pid, result)
        except (Refused, fetch.FetchError, unpack.UnpackError, ValueError, OSError, subprocess.SubprocessError) as error:
            result["status"] = "failed"
            result["error"] = str(error).splitlines()[0][:300] if str(error) else type(error).__name__
            return result

    # ---- archives --------------------------------------------------------------------------------

    def install_archive(self, m, pid, result):
        checks = result["checks"]
        registry = self.installed()
        current = registry["tools"].get(m["name"])
        if current and current.get("version") == m["version"] and current.get("sha256") == m["sha256"]:
            result["status"] = "installed"
            checks["already"] = True
            return result
        taken = {cmd: name for name, tool in registry["tools"].items() if name != m["name"] for cmd in tool.get("commands") or []}
        clash = sorted(set(m["commands"]) & set(taken))
        if clash:
            raise Refused(f"command {clash[0]} is already {taken[clash[0]]}'s")
        # Both sizes are limits (jorah-tool-v1 "Sizes"). Without a download size (a non-GitHub host
        # that states none), the download is capped at UNSTATED_DOWNLOAD_MB and the unpacked limit is
        # set from the bytes that came.
        download_mb = m.get("download_mb") or self.tc.UNSTATED_DOWNLOAD_MB
        installed_mb = m.get("installed_mb")
        self._room(installed_mb * 1.25 if installed_mb else download_mb * 1.1 + 5, installed_mb or f"a download of up to {download_mb}")

        # The source's own record, where the installer can read one.
        release = fetch.github_release(m["url"], self.open_url, self.s.github_api)
        if release is not None:
            age = self.s.day() - release["published"]
            checks["published"] = release["published"].isoformat()
            checks["publishedBy"] = "GitHub's API"
            if release["draft"] or release["prerelease"]:
                raise Refused("GitHub marks the release a draft or pre-release")
            if age < timedelta(days=self.tc.MIN_AGE_DAYS):
                raise Refused(f"GitHub says the release was published {release['published']}, less than "
                              f"{self.tc.MIN_AGE_DAYS} days ago")
            if release["digest"] is not None and release["digest"] != m["sha256"]:
                raise Refused("GitHub holds a different SHA-256 for this asset than the request")
            checks["githubDigest"] = "matches" if release["digest"] else "GitHub holds none for this asset"
        else:
            checks["published"] = m["released"]
            checks["publishedBy"] = "the request (this host has no release record the installer reads)"

        downloads = Path(self.s.var) / "downloads"
        part = downloads / f"{pid}.part"
        if part.exists():
            part.unlink()
        staging = Path(tempfile.mkdtemp(prefix=f"{pid}-", dir=Path(self.s.opt) / ".staging"))
        try:
            max_bytes = self.tc.download_cap(download_mb)
            sha, size = fetch.download(m["url"], part, max_bytes, self.open_url)
            checks["downloadBytes"] = size
            if installed_mb is None:
                installed_mb = self.tc.installed_ceiling(m["format"], m["url"], max(1, -(-size // 1048576)))
                checks["installedLimitMb"] = installed_mb
                self._room(installed_mb * 1.25, installed_mb)
            if sha != m["sha256"]:
                raise Refused(f"the download's SHA-256 is {sha[:16]}…, not the request's {m['sha256'][:16]}…")
            checks["sha256"] = "matches"
            tool = staging / "tool"
            fmt = m["format"]
            if fmt == "tar":
                unpack.unpack_tar(part, tool, m.get("strip", 0))
            elif fmt == "zip":
                unpack.unpack_zip(part, tool, m.get("strip", 0))
            elif fmt == "appimage":
                unpack.unpack_appimage(part, tool, self.s.unsquashfs, self.run)
            else:
                unpack.place_file(part, tool, next(iter(m["commands"].values())))
            total = unpack.harden(tool)
            checks["installedBytes"] = total
            if total > installed_mb * 1.25 * 1048576 + 50 * 1048576:
                raise Refused(f"unpacked it is {total // 1048576} MB, well over the {installed_mb} MB limit")
            for cmd, rel in m["commands"].items():
                real = unpack.inside(tool, rel)
                if real is None:
                    found = unpack.executables(tool)
                    raise Refused(f"command {cmd}: {rel} isn't a file inside the tool"
                                  + (f" (strip {m.get('strip', 0)}); executables in it: {', '.join(found)}" if found else ""))
                if not os.stat(real).st_mode & 0o111:
                    os.chmod(real, 0o755)
            self._place(m, pid, tool, registry, checks)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if part.exists():
                part.unlink()
        result["status"] = "installed"
        return result

    def _room(self, mb, what):
        """Refuse unless `mb` megabytes fit on /opt beside the reserve."""
        if shutil.disk_usage(self.s.opt).free < int(mb * 1048576) + self.s.min_free_bytes:
            raise Refused(f"not enough free disk for {what} MB plus the 20 GB reserve")

    def _place(self, m, pid, tool, registry, checks):
        tools = Path(self.s.opt) / "tools" / m["name"]
        tools.mkdir(exist_ok=True)
        os.chmod(tools, 0o755)
        target = tools / m["version"]
        old = [p for p in tools.iterdir() if p.name != m["version"]]
        if os.path.lexists(target):
            shutil.rmtree(target)
        os.rename(tool, target)
        previous = registry["tools"].get(m["name"]) or {}
        for cmd in previous.get("commands") or []:
            wrapper = Path(self.s.opt) / "bin" / cmd
            if wrapper.exists() and cmd not in m["commands"]:
                wrapper.unlink()
        for cmd, rel in m["commands"].items():
            self._wrapper(m, cmd, target, rel)
        registry["tools"][m["name"]] = self._entry(m, pid, checks)
        write_json(self.registry, registry)
        for path in old:
            shutil.rmtree(path, ignore_errors=True)

    def _wrapper(self, m, cmd, target, rel):
        state = f"{self.s.state_root}/{m['name']}"
        lines = ["#!/bin/sh",
                 f"# {m['name']} {m['version']} from Jorah's toolbox (jorah-toolbox, {date.today().isoformat()}). Written by the installer; don't edit.",
                 f"TOOL='{target}'",
                 f"STATE='{state}'",
                 'mkdir -p "$STATE" 2>/dev/null || true']
        for key, value in sorted((m.get("env") or {}).items()):
            text = value.replace("${TOOL}", "$TOOL").replace("${STATE}", "$STATE")
            lines.append(f'export {key}="{text}"')
        lines.append(f'exec "$TOOL/{rel}" "$@"')
        path = Path(self.s.opt) / "bin" / cmd
        tmp = path.with_name(f".{cmd}.new")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o755)
        os.replace(tmp, path)

    def _entry(self, m, pid, checks):
        return {"id": pid, "name": m["name"], "title": m["title"], "version": m["version"], "kind": m["kind"],
                "purpose": m["purpose"], "forProject": m.get("for_project"), "homepage": m["homepage"],
                "commands": sorted(m["commands"]) if m["kind"] == "archive" else [],
                "packages": m.get("packages") if m["kind"] == "apt" else None,
                "licence": m["licence"], "licenceSource": m["licence_source"],
                "source": self.tc.source_text(m), "sha256": m.get("sha256"),
                "released": checks.get("published") or m["released"], "releasedBy": checks.get("publishedBy") or "the request",
                "smoke": m["smoke"], "smokeExpect": m.get("smoke_expect"),
                "installedAt": _now(), "installedBytes": checks.get("installedBytes"),
                "path": str(Path(self.s.opt) / "tools" / m["name"] / m["version"]) if m["kind"] == "archive" else None}

    # ---- Ubuntu packages: root is Adam's ---------------------------------------------------------

    def needs_root(self, m, pid, result):
        result["status"] = "needs-root"
        result["rootCommand"] = f"bash {APT_SCRIPT} {pid}"
        result["checks"]["root"] = "Ubuntu packages need root, which the installer never has: Adam runs the command"
        return result

    def record_apt(self, pid, installed_versions):
        """After toolbox-apt.sh installed a needs-root request (as root), add it to installed.json.
        `installed_versions`: {package: version} that dpkg reports. Returns the result."""
        path = self.results / f"{pid}.json"
        result = read_json(path)
        if not isinstance(result, dict) or result.get("status") != "needs-root" or not isinstance(result.get("manifest"), dict):
            raise Refused(f"{pid} isn't waiting for a root install")
        m = result["manifest"]
        if self.tc.check(m, self.s.day()) or self.tc.proposal_id(m) != pid or m["kind"] != "apt":
            raise Refused(f"{pid}'s request no longer passes the contract")
        missing = [p for p in m["packages"] if not installed_versions.get(p)]
        if missing:
            raise Refused(f"not installed: {', '.join(missing)}")
        registry = self.installed()
        result["checks"]["packages"] = {p: installed_versions[p] for p in m["packages"]}
        registry["tools"][m["name"]] = self._entry(m, pid, {"published": None})
        registry["tools"][m["name"]]["packageVersions"] = result["checks"]["packages"]
        write_json(self.registry, registry)
        result.update(status="installed", at=_now(), rootCommand=None, error=None)
        write_json(path, result)
        return result

    # ---- removal ---------------------------------------------------------------------------------

    def remove(self, name, result):
        registry = self.installed()
        tool = registry["tools"].get(name)
        if tool is None:
            raise Refused(f"{name} isn't in the toolbox")
        result["version"] = tool.get("version")
        if tool.get("kind") == "apt":
            result["status"] = "needs-root"
            result["rootCommand"] = f"bash {APT_SCRIPT} --remove {name}"
            return result
        for cmd in tool.get("commands") or []:
            wrapper = Path(self.s.opt) / "bin" / cmd
            if wrapper.exists():
                wrapper.unlink()
        shutil.rmtree(Path(self.s.opt) / "tools" / name, ignore_errors=True)
        del registry["tools"][name]
        write_json(self.registry, registry)
        result["status"] = "removed"
        return result

    def forget_apt(self, name):
        """After toolbox-apt.sh --remove purged a tool's packages (as root)."""
        registry = self.installed()
        tool = registry["tools"].get(name)
        if tool is None or tool.get("kind") != "apt":
            raise Refused(f"{name} isn't an apt tool in the toolbox")
        del registry["tools"][name]
        write_json(self.registry, registry)
        return {"name": name, "status": "removed"}


def main_status(settings):
    inst = Installer(settings)
    data = inst.installed()
    out = {"tools": {n: {"version": t.get("version"), "kind": t.get("kind"), "commands": t.get("commands")} for n, t in data["tools"].items()},
           "waiting": sorted(p.name for p in inst.approved.glob("*.json")) if inst.approved.is_dir() else [],
           "results": sorted(p.name for p in inst.results.glob("*.json"))[-10:] if inst.results.is_dir() else []}
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0
