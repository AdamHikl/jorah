"""A real build-sim of the fixture app through the HTTP front end on loopback.

Makes a temp allowlist and key, starts `jorah-ios-runner serve` on a free
loopback port, sends signed requests the way the plugin will, waits for the
run, prints the final reply and stops the server. Mac only, needs Xcode, and
the fixture folder must have no uncommitted changes. Writes nothing outside a
new temp folder.

With --simulator it then goes on, on a real iOS Simulator: boot, install and
launch the build, take a screenshot, read it back in pages, stop the app and
shut the simulator down. It picks a simulator that is shut down now (newest
iOS, an iPhone with a unique name), so it never takes over one in use, or
uses --simulator "NAME@OS" (also shut down now).
"""

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from ios_runner.auth import sign_headers  # noqa: E402

FIXTURE = HERE / "tests" / "fixtures" / "Sample"


def post(base, key, verb, body):
    data = json.dumps(body).encode()
    path = f"/v1/{verb}"
    req = urllib.request.Request(base + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **sign_headers(key, path, data)})
    with urllib.request.urlopen(req, timeout=150) as r:
        return json.loads(r.read())


def short(reply):
    """The fields that show what each step proved, without log tails."""
    out = {k: reply[k] for k in reply if k not in ("run", "contract", "data_base64")}
    run = reply.get("run")
    if run:
        out["run"] = {k: run.get(k) for k in ("run_id", "kind", "state", "tier", "tier_note", "simulator",
                                              "process_id", "artifact", "build_run_id")}
    return out


def pick(base, key):
    listed = post(base, key, "sim-list", {})
    if not listed["ok"]:
        raise SystemExit(json.dumps(listed))
    sims = listed["simulators"]
    args = sys.argv[sys.argv.index("--simulator") + 1:]
    if args and "@" in args[0]:
        name, os_version = args[0].rsplit("@", 1)
        chosen = [s for s in sims if s["name"] == name and s["os"] == os_version]
    else:
        counts = {}
        for s in sims:
            counts[(s["name"], s["os"])] = counts.get((s["name"], s["os"]), 0) + 1
        chosen = [s for s in sims if s["name"].startswith("iPhone") and counts[(s["name"], s["os"])] == 1]
    chosen = [s for s in chosen if s["state"] == "shutdown"]
    chosen.sort(key=lambda s: tuple(int(x) for x in s["os"].split(".")), reverse=True)
    if not chosen:
        raise SystemExit("No matching simulator that is shut down now; the sample won't take over one in use.")
    return {"name": chosen[0]["name"], "os": chosen[0]["os"]}


def simulator_steps(base, key, build_id, tmp):
    sim = pick(base, key)
    steps = []

    def step(verb, body):
        reply = post(base, key, verb, body)
        steps.append({"verb": verb, "reply": short(reply)})
        print(f"{verb}: ok={reply['ok']} {(reply.get('run') or {}).get('tier', '')}", file=sys.stderr)
        return reply

    good = True
    try:
        good &= step("sim-boot", {"simulator": sim})["ok"]
        installed = step("sim-install", {"build_run_id": build_id, "simulator": sim, "launch": True})
        good &= installed["ok"] and installed["run"]["tier"] == "launch"
        shot = step("sim-screenshot", {"project": "sample", "simulator": sim})
        good &= shot["ok"]
        if shot["ok"]:
            data, offset = b"", 0
            while True:
                page = post(base, key, "sim-screenshot-read", {"run_id": shot["run"]["run_id"], "offset": offset,
                                                               "max_bytes": 262144})
                if not page["ok"]:
                    good = False
                    steps.append({"verb": "sim-screenshot-read", "reply": short(page)})
                    break
                data += base64.b64decode(page["data_base64"])
                offset += page["bytes"]
                if page["eof"]:
                    break
            match = hashlib.sha256(data).hexdigest() == shot["run"]["artifact"]["sha256"]
            steps.append({"verb": "sim-screenshot-read", "reply": {"pages_bytes": len(data),
                                                                   "sha256_matches_artifact": match}})
            good &= match
            (tmp / "screenshot.png").write_bytes(data)
            print(f"screenshot read back to {tmp / 'screenshot.png'}", file=sys.stderr)
        good &= step("sim-terminate", {"project": "sample", "simulator": sim})["ok"]
    finally:
        good &= step("sim-shutdown", {"simulator": sim})["ok"]
    print(json.dumps({"simulator": sim, "steps": steps}, indent=2, sort_keys=True))
    return 0 if good else 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="jorah-ios-runner-"))
    key = secrets.token_bytes(32)
    key_file = tmp / "runner.key"
    key_file.write_bytes(key)
    key_file.chmod(0o600)
    config = {
        "contract": "jorah-ios/1", "installAllowed": False, "simulatorAllowed": True,
        "stateDir": str(tmp / "state"), "handoffDir": str(tmp / "handoff"), "keyFile": str(key_file),
        "listen": {"host": "127.0.0.1", "port": 0},
        "path": ["/usr/bin", "/bin", "/usr/sbin", "/sbin"],
        "projects": {"sample": {"repo": "AdamHikl/jorah", "path": str(FIXTURE), "project": "Sample.xcodeproj",
                                "scheme": "Sample", "bundleId": "dev.jorah.fixture.sample"}},
    }
    cfg = tmp / "projects.json"
    cfg.write_text(json.dumps(config))
    cfg.chmod(0o600)
    commit = subprocess.run(["git", "-C", str(FIXTURE), "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    env = {"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"], "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
           "JORAH_IOS_RUNNER_CONFIG": str(cfg)}
    server = subprocess.Popen([sys.executable, "-I", str(HERE / "bin" / "jorah-ios-runner"), "serve"], env=env,
                              stderr=subprocess.PIPE, text=True)
    try:
        line = server.stderr.readline()
        if "listening on" not in line:
            raise SystemExit(f"server did not start: {line}")
        base = "http://127.0.0.1:" + line.strip().rsplit(":", 1)[1]
        with urllib.request.urlopen(base + "/v1/health", timeout=5) as r:
            print("health:", r.read().decode(), file=sys.stderr)
        first = post(base, key, "build-sim", {"project": "sample", "commit": commit, "configuration": "Debug"})
        print(f"build-sim replied: state {first.get('run', {}).get('state')}", file=sys.stderr)
        if not first["ok"]:
            print(json.dumps(first, indent=2))
            return 1
        run_id = first["run"]["run_id"]
        while True:
            reply = post(base, key, "status", {"run_id": run_id, "wait_seconds": 120})
            if reply["run"]["state"] in ("succeeded", "failed", "cancelled", "unknown"):
                break
        reply["run"]["log"]["tail"] = reply["run"]["log"]["tail"][-300:]
        print(json.dumps(reply, indent=2, sort_keys=True))
        if not (reply["ok"] and reply["run"]["tier"] == "build"):
            return 1
        if "--simulator" in sys.argv:
            return simulator_steps(base, key, run_id, tmp)
        return 0
    finally:
        server.terminate()
        server.wait(timeout=20)


if __name__ == "__main__":
    sys.exit(main())
