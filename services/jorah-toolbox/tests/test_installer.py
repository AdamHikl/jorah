"""The toolbox installer, with a stand-in network: approvals in, tools and results out.

Nothing here needs the network, root or unsquashfs (the AppImage step's unsquashfs is a stand-in
that checks its arguments).
"""

import copy
import getpass
import hashlib
import io
import json
import os
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from jorah_toolbox import fetch, install, unpack  # noqa: E402

REPO = HERE.parents[2]
EXAMPLES = REPO / "packages/contracts/toolbox/examples/good"
TODAY = date(2026, 11, 17)
GH_URL = "https://github.com/astral-sh/uv/releases/download/0.9.18/uv-x86_64-unknown-linux-gnu.tar.gz"
API_URL = "https://api.github.com/repos/astral-sh/uv/releases/tags/0.9.18"


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class Net:
    """URL -> bytes. Records what was asked."""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.asked = []

    def __call__(self, request, timeout):
        url = request.full_url
        self.asked.append(url)
        if url not in self.pages:
            raise OSError(f"no such page {url}")
        return Response(self.pages[url], url)


def tar_bytes(files, links=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, (data, mode) in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            tar.addfile(info, io.BytesIO(data))
        for name, target in links:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return buf.getvalue()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fake_appimage(with_squashfs=True):
    """A minimal ELF64 header whose section headers end at 128, then squashfs magic."""
    head = bytearray(64)
    head[:4] = b"\x7fELF"
    head[4], head[5] = 2, 1
    struct.pack_into("<Q", head, 0x28, 64)       # e_shoff
    struct.pack_into("<HH", head, 0x3A, 64, 1)   # e_shentsize, e_shnum -> ends at 128
    body = bytes(head) + b"\0" * 64 + (b"hsqs" if with_squashfs else b"nope") + b"\0" * 60
    return body


class World(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jorah-toolbox-test-"))
        self.opt = self.tmp / "opt"
        self.var = self.tmp / "var"
        for p in (self.opt, self.var / "approved", self.var / "results"):
            p.mkdir(parents=True)
        self.settings = install.Settings(opt=self.opt, var=self.var, state_root=str(self.tmp / "state"), approver=None,
                                         min_free_bytes=0, today=lambda: TODAY)
        self.tc = install._load_contract(self.settings.contract)
        self.tar = tar_bytes({"uv-x86_64/uv": (b"#!/bin/sh\necho uv 0.9.18 \"$@\" \"$UV_CACHE_DIR\"\n", 0o755),
                              "uv-x86_64/uvx": (b"#!/bin/sh\necho uvx\n", 0o4755)})
        self.m = json.loads((EXAMPLES / "uv.json").read_text())
        self.m["sha256"] = sha(self.tar)
        self.net = Net({GH_URL: self.tar, API_URL: self.release("2025-12-16T10:00:00Z", self.m["sha256"])})
        self.unsquash = []

    def tearDown(self):
        subprocess.run(["chmod", "-R", "u+w", str(self.tmp)], check=False)
        subprocess.run(["rm", "-rf", str(self.tmp)], check=False)

    def release(self, published, digest, **extra):
        asset = {"name": "uv-x86_64-unknown-linux-gnu.tar.gz"}
        if digest:
            asset["digest"] = f"sha256:{digest}"
        return json.dumps({"published_at": published, "assets": [asset], "draft": False, "prerelease": False, **extra}).encode()

    def approve(self, m=None, *, action="install", name=None):
        m = m or self.m
        pid = self.tc.proposal_id(m) if action == "install" else f"rm-{name}-1"
        body = {"v": 1, "id": pid, "action": action, "at": "2026-11-17T10:00:00+01:00"}
        body.update({"manifest": m} if action == "install" else {"name": name})
        (self.var / "approved" / f"{pid}.json").write_text(json.dumps(body))
        return pid

    def fake_run(self, argv, **kw):
        self.unsquash.append(argv)
        dest = Path(argv[argv.index("-d") + 1])
        dest.mkdir()
        (dest / "AppRun").write_text("#!/bin/sh\necho orca\n")
        os.chmod(dest / "AppRun", 0o755)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def installer(self):
        return install.Installer(self.settings, open_url=self.net, run=self.fake_run, log=lambda text: None)

    def only_result(self):
        results = list((self.var / "results").glob("*.json"))
        self.assertEqual(len(results), 1)
        return json.loads(results[0].read_text())


class Archives(World):
    def test_a_github_tarball_installs_with_wrappers_registry_and_result(self):
        self.m["env"] = {"UV_CACHE_DIR": "${STATE}/cache"}
        pid = self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertEqual(result["checks"]["sha256"], "matches")
        self.assertEqual(result["checks"]["githubDigest"], "matches")
        self.assertEqual(result["checks"]["published"], "2025-12-16")
        self.assertEqual(self.only_result()["id"], pid)
        self.assertEqual(list((self.var / "approved").iterdir()), [], "the approval is used up")
        tool = self.opt / "tools/uv/0.9.18"
        self.assertTrue((tool / "uv").is_file())
        self.assertFalse((tool / "uvx").stat().st_mode & stat.S_ISUID, "setuid is cleared")
        registry = json.loads((self.opt / "installed.json").read_text())
        self.assertEqual(registry["tools"]["uv"]["commands"], ["uv", "uvx"])
        self.assertEqual(registry["tools"]["uv"]["releasedBy"], "GitHub's API")
        out = subprocess.run([str(self.opt / "bin/uv"), "--version"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip(), f"uv 0.9.18 --version {self.tmp}/state/uv/cache")
        self.assertTrue((self.tmp / "state/uv").is_dir(), "the wrapper makes the tool's state folder")
        self.assertEqual(list((self.opt / ".staging").iterdir()), [])
        self.assertEqual(list((self.var / "downloads").glob("*.part")), [])

    def test_a_wrong_hash_installs_nothing(self):
        self.m["sha256"] = "a" * 64
        self.net.pages[API_URL] = self.release("2025-12-16T10:00:00Z", None)
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "failed")
        self.assertIn("SHA-256", result["error"])
        self.assertFalse((self.opt / "tools/uv").exists())
        self.assertFalse((self.opt / "installed.json").exists())
        self.assertEqual(list((self.var / "downloads").glob("*.part")), [])

    def test_githubs_date_wins_over_the_request(self):
        self.net.pages[API_URL] = self.release("2026-11-14T10:00:00Z", self.m["sha256"])
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "failed")
        self.assertIn("published 2026-11-14, less than 7 days ago", result["error"])
        self.assertNotIn(GH_URL, self.net.asked, "nothing is downloaded")

    def test_githubs_digest_must_match(self):
        self.net.pages[API_URL] = self.release("2025-12-16T10:00:00Z", "b" * 64)
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("GitHub holds a different SHA-256", result["error"])

    def test_a_prerelease_is_refused(self):
        self.net.pages[API_URL] = self.release("2025-12-16T10:00:00Z", None, prerelease=True)
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("pre-release", result["error"])

    def test_another_host_keeps_the_requests_date(self):
        url = "https://downloads.example.org/uv-0.9.18.tar.gz"
        self.m["url"] = url
        self.net.pages[url] = self.tar
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertTrue(result["checks"]["publishedBy"].startswith("the request"))
        self.assertEqual(self.net.asked, [url])

    def test_a_download_bigger_than_requested_stops(self):
        big = tar_bytes({"uv-x86_64/uv": (os.urandom(12 * 1048576), 0o755)})
        self.m.update(sha256=sha(big), download_mb=1)
        self.net.pages[GH_URL] = big
        self.net.pages[API_URL] = self.release("2025-12-16T10:00:00Z", None)
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("bigger than", result["error"])

    def test_an_archive_that_climbs_out_is_refused(self):
        evil = tar_bytes({"uv-x86_64/../../evil": (b"x", 0o644), "uv-x86_64/uv": (b"x", 0o755)})
        self.m["sha256"] = sha(evil)
        self.net.pages[GH_URL] = evil
        self.net.pages[API_URL] = self.release("2025-12-16T10:00:00Z", None)
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "failed")
        self.assertFalse((self.tmp / "evil").exists())

    def test_a_link_out_of_the_tool_is_refused(self):
        evil = tar_bytes({"uv-x86_64/uvx": (b"x", 0o755)}, links=[("uv-x86_64/uv", "/etc/passwd")])
        self.m["sha256"] = sha(evil)
        self.net.pages[GH_URL] = evil
        self.net.pages[API_URL] = self.release("2025-12-16T10:00:00Z", None)
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "failed")

    def test_a_command_missing_from_the_archive_is_refused(self):
        self.m["commands"] = {"uv": "uv", "uvw": "bin/uvw"}
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("command uvw", result["error"])
        self.assertFalse((self.opt / "bin/uv").exists())
        self.assertIn("executables in it: uv, uvx", result["error"], "what's there, so the request can be fixed")

    def test_a_wrong_strip_names_the_paths_that_are_there(self):
        self.m["strip"] = 0
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("command uv: uv isn't a file inside the tool (strip 0); executables in it: uv-x86_64/uv, uv-x86_64/uvx",
                      result["error"])

    def test_another_host_without_sizes_is_measured_at_install(self):
        url = "https://downloads.example.org/uv-0.9.18.tar.gz"
        self.m["url"] = url
        del self.m["download_mb"], self.m["installed_mb"]
        self.net.pages[url] = self.tar
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertEqual(result["checks"]["downloadBytes"], len(self.tar))
        self.assertEqual(result["checks"]["installedLimitMb"], 64, "the floor, for a tiny gzip tarball")

    def test_without_a_stated_size_the_disk_must_hold_the_capped_download(self):
        url = "https://downloads.example.org/uv-0.9.18.tar.gz"
        self.m["url"] = url
        del self.m["download_mb"], self.m["installed_mb"]
        self.net.pages[url] = self.tar
        self.settings.min_free_bytes = 1 << 62
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("not enough free disk for a download of up to 1024 MB", result["error"])
        self.assertEqual(self.net.asked, [], "the disk is checked before anything is fetched")

    def test_a_command_another_tool_has_is_refused(self):
        (self.opt / "installed.json").write_text(json.dumps({"v": 1, "tools": {"astral": {"commands": ["uvx"], "version": "1"}}}))
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("command uvx is already astral's", result["error"])

    def test_a_new_version_replaces_the_old_one(self):
        self.approve()
        self.installer().run_queue()
        newer = tar_bytes({"uv-x86_64/uv": (b"#!/bin/sh\necho new\n", 0o755)})
        m = copy.deepcopy(self.m)
        url = GH_URL.replace("0.9.18", "0.9.19")
        m.update(version="0.9.19", url=url, sha256=sha(newer), commands={"uv": "uv"}, smoke_expect="new",
                 release_page=self.m["release_page"].replace("0.9.18", "0.9.19"))
        self.net.pages[url] = newer
        self.net.pages[API_URL.replace("0.9.18", "0.9.19")] = self.release("2026-01-10T10:00:00Z", None)
        self.approve(m)
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertEqual(sorted(p.name for p in (self.opt / "tools/uv").iterdir()), ["0.9.19"])
        self.assertFalse((self.opt / "bin/uvx").exists(), "a command the new version dropped goes")
        self.assertEqual(subprocess.run([str(self.opt / "bin/uv")], capture_output=True, text=True).stdout.strip(), "new")

    def test_the_same_version_twice_is_a_no_op(self):
        self.approve()
        self.installer().run_queue()
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["checks"]["already"])

    def test_the_same_version_with_a_fixed_manifest_is_installed_again(self):
        self.approve()
        self.installer().run_queue()
        fixed = copy.deepcopy(self.m)
        fixed["purpose"] = fixed["purpose"] + " Its command fixed after a failed smoke test."
        pid = self.approve(fixed)
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertNotIn("already", result["checks"])
        registry = json.loads((self.opt / "installed.json").read_text())
        self.assertEqual(registry["tools"]["uv"]["id"], pid)
        self.assertEqual(sorted(p.name for p in (self.opt / "tools/uv").iterdir()), ["0.9.18"])

    def test_a_zip_unpacks_and_its_links_are_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            info = zipfile.ZipInfo("tool/run")
            info.external_attr = (stat.S_IFREG | 0o755) << 16
            z.writestr(info, "#!/bin/sh\necho zip\n")
        data = buf.getvalue()
        url = "https://downloads.example.org/t.zip"
        self.m.update(url=url, sha256=sha(data), format="zip", strip=1, commands={"zt": "run"}, smoke=["zt"])
        self.m.pop("smoke_expect")
        self.net.pages[url] = data
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertEqual(subprocess.run([str(self.opt / "bin/zt")], capture_output=True, text=True).stdout.strip(), "zip")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            info = zipfile.ZipInfo("tool/link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "/etc/passwd")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.zip"
            path.write_bytes(buf.getvalue())
            with self.assertRaises(unpack.UnpackError):
                unpack.unpack_zip(path, Path(tmp) / "out")

    def test_a_single_file_tool(self):
        data = b"#!/bin/sh\necho one\n"
        url = "https://downloads.example.org/one"
        self.m.update(url=url, sha256=sha(data), format="file", strip=0, commands={"one": "one"}, smoke=["one"])
        self.m.pop("smoke_expect")
        self.net.pages[url] = data
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        self.assertEqual(subprocess.run([str(self.opt / "bin/one")], capture_output=True, text=True).stdout.strip(), "one")


class AppImages(World):
    def setUp(self):
        super().setUp()
        self.m = json.loads((EXAMPLES / "orca-slicer.json").read_text())
        self.data = fake_appimage()
        self.m["sha256"] = sha(self.data)
        self.net.pages[self.m["url"]] = self.data
        self.net.pages["https://api.github.com/repos/SoftFever/OrcaSlicer/releases/tags/v2.3.1"] = json.dumps(
            {"published_at": "2026-09-01T00:00:00Z", "assets": [{"name": self.m["url"].rsplit("/", 1)[1]}]}).encode()

    def test_an_appimage_is_unpacked_with_unsquashfs_at_its_offset_never_run(self):
        self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "installed", result["error"])
        [argv] = self.unsquash
        self.assertEqual(argv[0], "/usr/bin/unsquashfs")
        self.assertEqual(argv[argv.index("-o") + 1], "128")
        self.assertEqual(subprocess.run([str(self.opt / "bin/orca-slicer")], capture_output=True, text=True).stdout.strip(), "orca")

    def test_an_appimage_without_squashfs_is_refused(self):
        self.data = fake_appimage(with_squashfs=False)
        self.m["sha256"] = sha(self.data)
        self.net.pages[self.m["url"]] = self.data
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("no squashfs", result["error"])
        self.assertEqual(self.unsquash, [])


class Approvals(World):
    def test_an_approval_whose_id_doesnt_match_is_refused(self):
        pid = self.approve()
        body = json.loads((self.var / "approved" / f"{pid}.json").read_text())
        body["manifest"]["purpose"] = "Something else entirely, not what Adam saw on the card."
        (self.var / "approved" / f"{pid}.json").write_text(json.dumps(body))
        [result] = self.installer().run_queue()
        self.assertIn("doesn't match", result["error"])
        self.assertEqual(self.net.asked, [])

    def test_the_contract_is_checked_again_with_todays_date(self):
        self.m["released"] = "2026-11-16"
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn("less than 7 days ago", result["error"])

    def test_approvals_must_belong_to_jorah(self):
        self.settings.approver = "somebody-else"
        self.approve()
        [result] = self.installer().run_queue()
        self.assertIn(f"belongs to {getpass.getuser()}", result["error"])

    def test_a_link_in_the_queue_is_refused(self):
        target = self.tmp / "elsewhere.json"
        target.write_text("{}")
        (self.var / "approved" / "tb-link.json").symlink_to(target)
        self.assertEqual(self.installer().run_queue(), [])
        self.assertEqual(list((self.var / "approved").iterdir()), [])
        self.assertTrue(target.exists(), "the link's target is left alone")


class Apt(World):
    def setUp(self):
        super().setUp()
        self.m = json.loads((EXAMPLES / "java.json").read_text())

    def test_ubuntu_packages_wait_for_adams_root_command_then_get_recorded(self):
        pid = self.approve()
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "needs-root")
        self.assertEqual(result["rootCommand"], f"bash /opt/jorah/scripts/pc/toolbox-apt.sh {pid}")
        self.assertEqual(self.net.asked, [], "the installer fetches nothing for apt")
        inst = self.installer()
        with self.assertRaises(install.Refused):
            inst.record_apt(pid, {})
        done = inst.record_apt(pid, {"openjdk-21-jre-headless": "21.0.9+10-1~24.04"})
        self.assertEqual(done["status"], "installed")
        tool = json.loads((self.opt / "installed.json").read_text())["tools"]["java"]
        self.assertEqual(tool["kind"], "apt")
        self.assertEqual(tool["packageVersions"], {"openjdk-21-jre-headless": "21.0.9+10-1~24.04"})
        with self.assertRaises(install.Refused):
            inst.record_apt(pid, {"openjdk-21-jre-headless": "x"})  # no longer waiting
        self.approve(action="remove", name="java")
        [removal] = self.installer().run_queue()
        self.assertEqual(removal["status"], "needs-root")
        self.assertEqual(removal["rootCommand"], "bash /opt/jorah/scripts/pc/toolbox-apt.sh --remove java")
        self.installer().forget_apt("java")
        self.assertEqual(json.loads((self.opt / "installed.json").read_text())["tools"], {})


class Strays(World):
    def test_anything_that_isnt_an_approval_is_moved_aside(self):
        (self.var / "approved" / ".tb-x.json.123.tmp").write_text("{")
        (self.var / "approved" / "notes.txt").write_text("hi")
        self.assertEqual(self.installer().run_queue(), [])
        self.assertEqual(list((self.var / "approved").iterdir()), [])
        self.assertEqual(len(list((self.var / "downloads" / "stray").iterdir())), 2)


class Removal(World):
    def test_remove_takes_the_tool_and_its_wrappers(self):
        self.approve()
        self.installer().run_queue()
        self.approve(action="remove", name="uv")
        [result] = self.installer().run_queue()
        self.assertEqual(result["status"], "removed")
        self.assertFalse((self.opt / "tools/uv").exists())
        self.assertFalse((self.opt / "bin/uv").exists())
        self.assertEqual(json.loads((self.opt / "installed.json").read_text())["tools"], {})

    def test_removing_what_isnt_there_fails(self):
        self.approve(action="remove", name="nothing")
        [result] = self.installer().run_queue()
        self.assertIn("isn't in the toolbox", result["error"])


class Fetch(unittest.TestCase):
    def test_only_https(self):
        with self.assertRaises(fetch.FetchError):
            fetch.download("http://example.com/x", "/nonexistent", 10, Net())

    def test_non_release_urls_have_no_github_check(self):
        self.assertIsNone(fetch.github_release("https://github.com/o/r/archive/refs/tags/v1.tar.gz", Net()))

    def test_a_redirect_off_https_is_refused(self):
        handler = fetch._HttpsOnly()
        with self.assertRaises(fetch.FetchError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://evil.example/x")


if __name__ == "__main__":
    unittest.main()
