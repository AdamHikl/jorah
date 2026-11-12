"""Tests for scripts/mac/ios_preflight.py and the allowlist template. No Mac, Xcode or network
needed: the machine is a fake, so they run anywhere `just unit` runs."""

import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location("ios_preflight", HERE.parent / "ios_preflight.py")
pf = importlib.util.module_from_spec(spec)
sys.modules["ios_preflight"] = pf
spec.loader.exec_module(pf)

BUILD_UID, ADAM_UID = 502, 501


def st(uid=0, gid=0, mode=0o755, size=0, kind=stat.S_IFDIR):
    return SimpleNamespace(st_uid=uid, st_gid=gid, st_mode=kind | mode, st_size=size)


class Fake(pf.System):
    """A Mac in a chosen state. Commands answer from a table keyed by argv prefix."""

    def __init__(self, me="adam", user_exists=True):
        self.me = me
        self.users = {"adam": (ADAM_UID, "/Users/adam")}
        if user_exists:
            self.users[pf.BUILD_USER] = (BUILD_UID, "/Users/jorah-build")
        self.stats = {}
        self.files = {}
        self.dirs = {}
        self.cmds = []  # (prefix tuple, (code, out))
        self.http = (None, "")
        self.ran = []

    def user(self):
        return self.me

    def home_of(self, name):
        return self.users.get(name, (None, None))[1]

    def uid_of(self, name):
        return self.users.get(name, (None, None))[0]

    def group_members(self, group):
        return self.groups.get(group) if hasattr(self, "groups") else None

    def is_member(self, user, group):
        return self.membership.get((user, group), False) if hasattr(self, "membership") else False

    def stat(self, path):
        return self.stats.get(path)

    def listdir(self, path):
        return self.dirs.get(path)

    def read_bytes(self, path):
        return self.files.get(path)

    def run(self, argv, timeout=30):
        self.ran.append(argv)
        for prefix, answer in self.cmds:
            if tuple(argv[:len(prefix)]) == prefix:
                return answer
        return None, ""

    def http_get(self, url):
        assert url.startswith("http://127.0.0.1:")
        return self.http


def statuses(results):
    return {r.what: r.status for r in results}


class AsAdam(unittest.TestCase):
    def test_nothing_set_up(self):
        f = Fake(user_exists=False)
        r = statuses(pf.check_user(f))
        self.assertEqual(r["user jorah-build exists"], pf.MISSING)
        self.assertEqual(pf.check_health(f).status, pf.MISSING)

    def test_build_user_only_checks_are_unknown_never_done(self):
        f = Fake(me="adam")
        f.stats["/Users/jorah-build/" + pf.KEY_REL] = "denied"
        for r in pf.check_signing(f, "adam", "/Users/jorah-build"):
            self.assertEqual(r.status, pf.UNKNOWN, r.what)
        self.assertEqual(pf.check_key(f, "adam", "/Users/jorah-build").status, pf.UNKNOWN)
        self.assertEqual(pf.check_agent_loaded(f, "adam").status, pf.UNKNOWN)
        # And nothing ran that would need jorah-build's keychain.
        self.assertFalse(any("security" in " ".join(a) for a in f.ran))

    def test_admin_build_user_is_missing(self):
        f = Fake()
        f.membership = {(pf.BUILD_USER, "admin"): True, (pf.BUILD_USER, "_developer"): True}
        f.cmds = [(("/usr/bin/defaults",), (1, ""))]
        r = statuses(pf.check_user(f))
        self.assertEqual(r["jorah-build is not an admin"], pf.MISSING)
        self.assertEqual(r["jorah-build is in _developer"], pf.DONE)

    def test_autologin_to_build_user_is_missing(self):
        f = Fake()
        f.membership = {}
        f.cmds = [(("/usr/bin/defaults",), (0, "jorah-build\n"))]
        self.assertEqual(statuses(pf.check_user(f))["automatic login is not jorah-build"], pf.MISSING)


class AsBuildUser(unittest.TestCase):
    def signing(self, valid, all_):
        f = Fake(me=pf.BUILD_USER)
        f.cmds = [
            (("/usr/bin/security", "find-identity", "-v"), (0, valid)),
            (("/usr/bin/security", "find-identity", "-p"), (0, all_)),
            (("/usr/bin/security", "show-keychain-info"), (0, "Keychain ... no-timeout\n")),
        ]
        f.dirs["/Users/jorah-build/" + pf.PROFILES_REL] = ["a.mobileprovision"] * 4
        return statuses(pf.check_signing(f, pf.BUILD_USER, "/Users/jorah-build"))

    def test_one_development_identity_is_done(self):
        line = '  1) ABC "Apple Development: Adam (XYZ)"\n     1 valid identities found\n'
        r = self.signing(line, line)
        self.assertEqual(r["one Apple Development identity in jorah-build's keychain"], pf.DONE)
        self.assertEqual(r["no distribution identity in jorah-build's keychain"], pf.DONE)
        self.assertEqual(r["login keychain does not auto-lock"], pf.DONE)
        self.assertEqual(r["provisioning profiles installed"], pf.DONE)

    def test_distribution_identity_is_missing_even_if_expired(self):
        valid = '  1) ABC "Apple Development: Adam (XYZ)"\n'
        r = self.signing(valid, valid + '  2) DEF "Apple Distribution: Company (T)" (CSSMERR_TP_CERT_EXPIRED)\n')
        self.assertEqual(r["no distribution identity in jorah-build's keychain"], pf.MISSING)

    def test_two_development_identities_is_missing(self):
        two = '  1) A "Apple Development: x"\n  2) B "Apple Development: y"\n'
        self.assertEqual(self.signing(two, two)["one Apple Development identity in jorah-build's keychain"], pf.MISSING)

    def test_key_file_mode_and_size_never_content(self):
        f = Fake(me=pf.BUILD_USER)
        path = "/Users/jorah-build/" + pf.KEY_REL
        f.stats[path] = st(uid=BUILD_UID, mode=0o600, size=32, kind=stat.S_IFREG)
        self.assertEqual(pf.check_key(f, pf.BUILD_USER, "/Users/jorah-build").status, pf.DONE)
        f.stats[path] = st(uid=BUILD_UID, mode=0o644, size=32, kind=stat.S_IFREG)
        self.assertEqual(pf.check_key(f, pf.BUILD_USER, "/Users/jorah-build").status, pf.MISSING)
        self.assertNotIn(path, f.files)  # the check has no way to read it

    def test_agent_running(self):
        f = Fake(me=pf.BUILD_USER)
        f.cmds = [(("/bin/launchctl",), (0, "state = running\n"))]
        self.assertEqual(pf.check_agent_loaded(f, pf.BUILD_USER).status, pf.DONE)
        f.cmds = [(("/bin/launchctl",), (113, ""))]
        self.assertEqual(pf.check_agent_loaded(f, pf.BUILD_USER).status, pf.MISSING)


class Shared(unittest.TestCase):
    def test_health(self):
        f = Fake()
        f.http = (200, json.dumps({"contract": "jorah-ios/1", "runner_version": "1", "busy": False}))
        self.assertEqual(pf.check_health(f).status, pf.DONE)
        f.http = (200, json.dumps({"contract": "other"}))
        self.assertEqual(pf.check_health(f).status, pf.MISSING)

    def test_root_dirs(self):
        f = Fake()
        f.stats[pf.LIBEXEC] = st()
        self.assertEqual(pf._root_dir(f, pf.LIBEXEC, "x", "A2").status, pf.DONE)
        f.stats[pf.LIBEXEC] = st(uid=ADAM_UID)
        self.assertEqual(pf._root_dir(f, pf.LIBEXEC, "x", "A2").status, pf.MISSING)
        f.stats[pf.LIBEXEC] = "denied"
        self.assertEqual(pf._root_dir(f, pf.LIBEXEC, "x", "A2").status, pf.UNKNOWN)

    def test_runner_files_must_not_be_writable_by_others(self):
        f = Fake()
        f.stats[pf.RUNNER_BIN] = st(mode=0o775, kind=stat.S_IFREG)
        self.assertEqual(pf._root_file(f, pf.RUNNER_BIN, "x", "A9", True).status, pf.MISSING)

    def test_allowlist_with_placeholders_is_missing(self):
        f = Fake()
        f.stats[pf.ALLOWLIST] = st(mode=0o644, kind=stat.S_IFREG)
        f.files[pf.ALLOWLIST] = (REPO / "scripts/mac/ios-projects.template.json").read_bytes()
        self.assertEqual(statuses(pf.check_allowlist(f))["allowlist filled in"], pf.MISSING)

    def test_tailscale_serve(self):
        f = Fake()
        f.stats["/usr/local/bin/tailscale"] = st(kind=stat.S_IFREG)
        f.cmds = [(("/usr/local/bin/tailscale", "serve"), (0, json.dumps({"TCP": {"47820": {"TCPForward": "127.0.0.1:47820"}}})))]
        self.assertEqual(pf.check_tailscale(f).status, pf.DONE)
        f.cmds = [(("/usr/local/bin/tailscale", "serve"), (0, "{}"))]
        self.assertEqual(pf.check_tailscale(f).status, pf.MISSING)
        f.cmds = []
        self.assertEqual(pf.check_tailscale(f).status, pf.UNKNOWN)

    def test_iphone(self):
        f = Fake()
        devices = {"result": {"devices": [{
            "hardwareProperties": {"reality": "physical", "deviceType": "iPhone"},
            "connectionProperties": {"pairingState": "paired", "transportType": "wired"},
            "deviceProperties": {"name": "phone", "developerModeStatus": "enabled"}}]}}

        def run(argv, timeout=30):
            path = argv[argv.index("--json-output") + 1]
            f.files[path] = json.dumps(devices).encode()
            return 0, ""
        f.run = run
        r = statuses(pf.check_iphone(f, "adam", "/tmp"))
        self.assertEqual(r["iPhone paired for adam"], pf.DONE)
        self.assertEqual(r["iPhone paired for jorah-build"], pf.UNKNOWN)

    def test_exit_codes(self):
        out = []
        self.assertEqual(pf.render([("s", [pf.Result(pf.DONE, "a")])], "adam", out.append), 0)
        self.assertEqual(pf.render([("s", [pf.Result(pf.UNKNOWN, "a")])], "adam", out.append), 3)
        self.assertEqual(pf.render([("s", [pf.Result(pf.MISSING, "a"), pf.Result(pf.UNKNOWN, "b")])], "adam", out.append), 1)


class Template(unittest.TestCase):
    """The allowlist template must load in the runner's own checker once placeholders are filled."""

    def test_filled_template_loads_in_runner(self):
        sys.path.insert(0, str(REPO / "services/ios-runner"))
        try:
            from ios_runner.config import load_config
        finally:
            sys.path.pop(0)
        text = (REPO / "scripts/mac/ios-projects.template.json").read_text()
        counter = iter(range(1, 100))
        text = re.sub(r'"<EXPO_PUBLIC_[^"]*>"', lambda m: '"EXPO_PUBLIC_X%d"' % next(counter), text)
        text = text.replace('"<iPhone UDID: xcrun devicectl list devices>"', '"00008140-0000000000000000"')
        text = re.sub(r'"<[^"]*>"', '"filled"', text)
        self.assertNotIn("<", text)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ios-projects.json"
            p.write_text(text)
            os.chmod(p, 0o600)
            config = load_config(p)
        self.assertEqual(sorted(config.projects), ["mizyun", "threadfolio"])
        self.assertEqual(config.port, pf.PORT)
        self.assertEqual(set(config.projects["mizyun"].signing.profiles),
                         {"MizyunDev", "ExpoWidgetsTarget", "MizyunWorkoutWatchDev"})

    def test_launch_agent_plist_points_at_wrapper(self):
        import plistlib
        plist = plistlib.loads((REPO / "scripts/mac/com.jorah.ios-runner.plist").read_bytes())
        self.assertEqual(plist["Label"], pf.AGENT_LABEL)
        self.assertEqual(plist["ProgramArguments"], [pf.AGENT_WRAPPER])
        wrapper = (REPO / "scripts/mac/ios-runner-agent.sh").read_text()
        self.assertIn(pf.RUNNER_BIN + " serve", wrapper)
        self.assertIn(pf.ALLOWLIST, wrapper)


if __name__ == "__main__":
    unittest.main()
