"""A real build-sim of the fixture app through the HTTP front end on loopback.

Makes a temp allowlist and key, starts `jorah-ios-runner serve` on a free
loopback port, sends signed requests the way the plugin will, waits for the
run, prints the final reply and stops the server. Mac only, needs Xcode, and
the fixture folder must have no uncommitted changes. Writes nothing outside a
new temp folder.
"""

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


def main():
    tmp = Path(tempfile.mkdtemp(prefix="jorah-ios-runner-"))
    key = secrets.token_bytes(32)
    key_file = tmp / "runner.key"
    key_file.write_bytes(key)
    key_file.chmod(0o600)
    config = {
        "contract": "jorah-ios/1", "installAllowed": False,
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
        return 0 if reply["ok"] and reply["run"]["tier"] == "build" else 1
    finally:
        server.terminate()
        server.wait(timeout=20)


if __name__ == "__main__":
    sys.exit(main())
