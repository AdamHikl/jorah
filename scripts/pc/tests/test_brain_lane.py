"""scripts/pc/brain-lane.sh against a fake `openclaw`: how it reads the lane, and both switches.

The fake answers the few commands the script runs, with the output shapes OpenClaw 2026.10.9 gave
on the PC on 2026-11-21, and applies the lane patches by their file name. It proves the script's
own logic, not OpenClaw's commands: the live run on the PC does that (docs/adr/0009).
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/pc/brain-lane.sh"
KEY = "anthropic:jorah-store"
MODELS = ["haiku-5-5", "opus-5-5", "opus-5", "sonnet-5-5", "sonnet-5", "fable-5-1", "fable-5",
          "opus-4-7", "sonnet-4-6", "opus-4-6", "*"]

FAKE_OPENCLAW = r'''#!/usr/bin/env python3
import json, os, sys
state_path = os.environ["FAKE_STATE"]
state = json.load(open(state_path))
args = sys.argv[3:]  # after --profile jorah
with open(os.environ["FAKE_CALLS"], "a") as calls:
    calls.write(" ".join(args) + "\n")
def save():
    json.dump(state, open(state_path, "w"))
def flag(name):
    return args[args.index(name) + 1]
cmd = " ".join(args[:2])
if state.get("fail") == cmd + (" dry" if "--dry-run" in args else ""):
    print("fake failure"); sys.exit(1)
if cmd == "config get":
    path = args[2]
    if state.get("unreadable"):
        print('{"ok": false}'); sys.exit(1)
    if path == "agents.defaults.models":
        runtimes = state["defaults"]
        print(json.dumps({f"anthropic/claude-{m}" if m != "*" else "anthropic/*": {"agentRuntime": {"id": r}}
                          for m, r in zip(state["models"], runtimes)}))
    elif path == "agents.entries.deep.models":
        print(json.dumps({"anthropic/claude-opus-5-5": {"agentRuntime": {"id": state["deep"]}}}))
    elif path == "auth.order":
        print(json.dumps({"anthropic": state["order"]}))
    elif path in ("agents.entries.deep.sandbox.mode", "agents.entries.deep.sandbox", "agents.entries.deep.tools.allow"):
        value = {"agents.entries.deep.sandbox.mode": state.get("deep_sandbox"),
                 "agents.entries.deep.sandbox": {"mode": state["deep_sandbox"]} if state.get("deep_sandbox") else None,
                 "agents.entries.deep.tools.allow": state.get("deep_allow")}[path]
        if value is None:
            print(json.dumps({"ok": False, "error": {"type": "cli_error", "message": f"Config path is valid but unset: {path}."}}))
            sys.exit(1)
        print(json.dumps(value))
    else:
        sys.exit(1)
elif cmd == "config unset":
    path = args[2]
    if path == "agents.entries.deep.sandbox":
        state["deep_sandbox"] = None
    elif path == "agents.entries.deep.tools.allow":
        state["deep_allow"] = None
    save()
    print(f"Removed {path}. Change will apply without restarting the gateway.")
elif cmd == "config patch":
    if "--dry-run" in args:
        print("Dry run successful: 13 update(s) validated against ~/.openclaw-jorah/openclaw.json.")
    else:
        lane = "openclaw" if "api-lane" in flag("--file") else "claude-cli"
        state["defaults"] = [lane] * len(state["models"])
        state["deep"] = lane
        state["order"] = [os.environ["FAKE_KEY"]] if lane == "openclaw" else []
        if lane == "claude-cli":
            state["deep_sandbox"] = "off"
            state["deep_allow"] = ["web_search", "x_search", "web_fetch", "browser", "price_compare", "tool_search", "tool_describe"]
        save()
        print("Applied 13 config update(s). Change will apply without restarting the gateway.")
elif cmd == "models auth":
    sub = " ".join(args[2:4])
    agent = flag("--agent")
    if sub == "order get":
        value = state["agents"][agent]
        shown = value if value != "none" else "none (config selects no profiles)"
        print(f"Agent: {agent}\nProvider: anthropic\nAuth profile order override: {shown}")
    elif sub == "order set":
        if state.get("fail") == "order set":
            sys.exit(1)
        state["agents"][agent] = args[-1]; save()
    elif sub == "order clear":
        state["agents"][agent] = "none"; save()
    elif args[2] == "list":
        print(f"Agent: {agent}\nProvider: anthropic\nProfiles:")
        if state["profiles"].get(agent):
            print(f"- {os.environ['FAKE_KEY']} [anthropic/api_key]")
elif cmd == "config validate":
    print("Config valid: ~/.openclaw-jorah/openclaw.json")
elif cmd == "secrets audit":
    print("Secrets audit: clean. plaintext=0, unresolved=0, shadowed=0, storeResidue=0, legacy=0.")
else:
    sys.exit(2)
'''


def lane_state(lane):
    runtime = {"api": "openclaw", "max": "claude-cli"}[lane]
    order = "none" if lane == "max" else KEY
    return {
        "models": MODELS,
        "defaults": [runtime] * len(MODELS),
        "deep": runtime,
        "order": [KEY] if lane == "api" else [],
        "agents": {"main": order, "deep": order, "background": KEY},
        "deep_sandbox": "off" if lane == "max" else None,
        "deep_allow": ["web_search", "x_search", "web_fetch", "browser", "price_compare", "tool_search", "tool_describe"] if lane == "max" else None,
        "profiles": {"main": True, "deep": True, "background": True},
    }


class BrainLane(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        self.write_tool(bin_dir / "openclaw", FAKE_OPENCLAW)
        self.write_tool(bin_dir / "id", '#!/bin/sh\necho jorah\n')
        self.write_tool(bin_dir / "systemctl", '#!/bin/sh\necho active\n')
        self.write_tool(bin_dir / "flock", '#!/bin/sh\nexit 0\n')
        home = self.tmp / "home"
        (home / ".claude-jorah").mkdir(parents=True)
        state_dir = self.tmp / "state"
        state_dir.mkdir()
        (state_dir / "openclaw.json").write_text("{}")
        tree = self.tmp / "tree/config/pc"
        tree.mkdir(parents=True)
        for name in ("api-lane.patch.json5", "max-lane.patch.json5"):
            shutil.copy(ROOT / "config/pc" / name, tree / name)
        self.state = self.tmp / "fake-state.json"
        self.calls = self.tmp / "calls"
        self.calls.write_text("")
        self.env = {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "HOME": str(home),
            "JORAH_TREE": str(self.tmp / "tree"),
            "JORAH_STATE": str(state_dir),
            "FAKE_STATE": str(self.state),
            "FAKE_CALLS": str(self.calls),
            "FAKE_KEY": KEY,
        }
        self.backups = state_dir / "backups/brain-lane"

    @staticmethod
    def write_tool(path, text):
        path.write_text(text)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def set_state(self, state):
        self.state.write_text(json.dumps(state))

    def run_script(self, *args):
        done = subprocess.run(["bash", str(SCRIPT), *args], env=self.env, capture_output=True, text=True,
                              timeout=60)
        lines = done.stdout.strip().splitlines()
        return done.returncode, lines, done.stderr

    def assert_lane(self, lines, lane):
        self.assertEqual(lines[-1], f"LANE: {lane}", "\n".join(lines))

    def test_status_reads_api(self):
        self.set_state(lane_state("api"))
        code, lines, _ = self.run_script("status")
        self.assertEqual(code, 0)
        self.assert_lane(lines, "api")
        self.assertIn("Claude models for main, heartbeats and Dreaming: 11 on the API key, 0 on the Max login", lines)

    def test_status_reads_max(self):
        self.set_state(lane_state("max"))
        code, lines, _ = self.run_script("status")
        self.assertEqual(code, 0)
        self.assert_lane(lines, "max")
        self.assertIn("main key order: none", lines)

    def test_one_setting_off_is_mixed(self):
        for change in ("defaults", "deep", "order", "main"):
            state = lane_state("api")
            if change == "defaults":
                state["defaults"][3] = "claude-cli"
            elif change == "deep":
                state["deep"] = "claude-cli"
            elif change == "order":
                state["order"] = []
            else:
                state["agents"]["main"] = "none"
            self.set_state(state)
            with self.subTest(change=change):
                code, lines, _ = self.run_script("status")
                self.assertEqual(code, 2)
                self.assert_lane(lines, "mixed")

    def test_unreadable_config_is_unknown_not_a_lane(self):
        state = lane_state("max")
        state["unreadable"] = True
        self.set_state(state)
        code, lines, _ = self.run_script("status")
        self.assertEqual(code, 2)
        self.assert_lane(lines, "unknown")

    def test_switch_to_api_and_back(self):
        self.set_state(lane_state("max"))
        code, lines, err = self.run_script("api")
        self.assertEqual(code, 0, "\n".join(lines) + err)
        self.assert_lane(lines[:-1], "api")
        self.assertEqual(lines[-1], "SWITCHED to api. Existing chats carry over.")
        calls = self.calls.read_text()
        self.assertIn("api-lane.patch.json5 --dry-run", calls)
        self.assertIn(f"models auth order set --provider anthropic --agent main {KEY}", calls)
        self.assertIn(f"models auth order set --provider anthropic --agent deep {KEY}", calls)
        self.assertNotIn("--agent background", calls.replace("order get --provider anthropic --agent background", ""))
        self.assertEqual(len(list(self.backups.glob("openclaw.json.*.pre-api"))), 1)

        state = json.loads(self.state.read_text())
        # On the API lane deep is sandboxed again: the script removed the Max lane's two settings.
        self.assertIsNone(state["deep_sandbox"])
        self.assertIsNone(state["deep_allow"])
        self.assertIn("config unset agents.entries.deep.sandbox", calls)
        self.assertIn("config unset agents.entries.deep.tools.allow", calls)

        code, lines, err = self.run_script("max")
        self.assertEqual(code, 0, "\n".join(lines) + err)
        self.assert_lane(lines[:-1], "max")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["agents"], {"main": "none", "deep": "none", "background": KEY})
        self.assertEqual(state["deep_sandbox"], "off")
        self.assertIn("deep sandbox: off (Max lane, tools limited to its allow list)", lines)

    def test_max_with_deep_still_sandboxed_is_mixed(self):
        state = lane_state("max")
        state["deep_sandbox"] = None
        self.set_state(state)
        code, lines, _ = self.run_script("status")
        self.assert_lane(lines, "mixed")
        self.assertIn("deep sandbox: on (default)", lines)

    def test_api_switch_with_deep_already_sandboxed_unsets_nothing(self):
        state = lane_state("api")
        self.set_state(state)
        code, lines, err = self.run_script("api")
        self.assertEqual(code, 0, "\n".join(lines) + err)
        self.assertNotIn("config unset", self.calls.read_text())

    def test_api_refused_without_a_key_profile_changes_nothing(self):
        state = lane_state("max")
        state["profiles"]["deep"] = False
        self.set_state(state)
        code, lines, _ = self.run_script("api")
        self.assertEqual(code, 3)
        self.assertTrue(any(line.startswith("REFUSED: deep has no") for line in lines), lines)
        self.assert_lane(lines, "max")
        self.assertNotIn("config patch", self.calls.read_text())
        self.assertFalse(self.backups.exists() and any(self.backups.glob("openclaw.json.*")))

    def test_failed_dry_run_changes_nothing(self):
        state = lane_state("max")
        state["fail"] = "config patch dry"
        self.set_state(state)
        code, lines, _ = self.run_script("api")
        self.assertEqual(code, 3)
        self.assertIn("REFUSED: the dry run failed", lines)
        self.assertNotIn("api-lane.patch.json5\n", self.calls.read_text())
        self.assert_lane(lines, "max")

    def test_a_failure_after_the_patch_says_mixed(self):
        state = lane_state("max")
        state["fail"] = "order set"
        self.set_state(state)
        code, lines, _ = self.run_script("api")
        self.assertEqual(code, 1)
        self.assertIn("FAILED: could not set main's key order", lines)
        self.assert_lane(lines, "mixed")

    def test_keeps_the_newest_twenty_backups(self):
        self.backups.mkdir(parents=True)
        for i in range(25):
            old = self.backups / f"openclaw.json.20261101-0000{i:02d}.pre-api"
            old.write_text("{}")
            os.utime(old, (1_700_000_000 + i, 1_700_000_000 + i))
        self.set_state(lane_state("max"))
        code, _, _ = self.run_script("api")
        self.assertEqual(code, 0)
        left = sorted(p.name for p in self.backups.glob("openclaw.json.*"))
        self.assertEqual(len(left), 20)
        self.assertNotIn("openclaw.json.20261101-000000.pre-api", left)

    def test_refuses_other_words(self):
        self.set_state(lane_state("api"))
        code, lines, _ = self.run_script("status; rm -rf /")
        self.assertEqual(code, 3)
        self.assertEqual(lines, ["usage: brain-lane.sh status [--probe] | api | max"])


if __name__ == "__main__":
    unittest.main()
