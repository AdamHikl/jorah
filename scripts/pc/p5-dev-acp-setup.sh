#!/usr/bin/env bash
# P5.4, jorah-dev only: Claude Code jobs (ACP through acpx) for the scratch profile, with their own
# config dir ~/.claude-jorah-dev, so they never share the live ~/.claude-jorah sessions or login.
# 1. ~/.claude-jorah-dev/settings.json from the live one, with ~/work swapped for ~/scratch-dev/work
#    (same sandbox: no network but the registries, home unreadable except the work folder).
# 2. A copy of the live acpx npm project under ~/scratch-dev/p5/extensions/acpx-project (loaded by path).
# The sign-in is Adam's (docs/evidence/p5/2026-11-13-p5.4-jorah-dev-github-memory-faults.md).
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
DEV=/home/jorah/.claude-jorah-dev
mkdir -p "$DEV" /home/jorah/scratch-dev/work /home/jorah/scratch-dev/p5/extensions
chmod 700 "$DEV"
python3 - "$DEV/settings.json" <<'P'
import json, sys
live = json.load(open("/home/jorah/.claude-jorah/settings.json"))
text = json.dumps(live).replace("/home/jorah/work", "/home/jorah/scratch-dev/work")
dev = json.loads(text)
dev["sandbox"]["filesystem"]["allowRead"] = [p for p in dev["sandbox"]["filesystem"]["allowRead"] if "mirrors" not in p]
deny = dev["permissions"]["deny"]
# The swap above also turned the live ~/workspace into ~/scratch-dev/workspace; keep the live one denied too.
fs = dev["sandbox"]["filesystem"]
if "/home/jorah/workspace" not in fs["denyWrite"]:
    fs["denyWrite"].append("/home/jorah/workspace")
for rule in ["Read(//home/jorah/workspace/**)", "Edit(//home/jorah/workspace/**)", "Read(//home/jorah/work/**)", "Edit(//home/jorah/work/**)"]:
    if rule not in deny:
        deny.append(rule)
for p in ["/home/jorah/.claude-jorah-dev", "/home/jorah/.openclaw-jorah-dev", "/home/jorah/.jorah-guard-dev",
          "/home/jorah/.jorah-guard", "/home/jorah/scratch-dev/p5", "/home/jorah/scratch-dev/am-home",
          "/home/jorah/scratch-dev/workspace", "/home/jorah/.agentmemory"]:
    rule = f"Read(/{p}/**)"
    if rule not in deny:
        deny.append(rule)
with open(sys.argv[1], "w") as f:
    json.dump(dev, f, indent=2)
P
chmod 600 "$DEV/settings.json"
# acpx with its dependencies: the live npm project, copied whole (about 770 MB).
SRC=$(find /home/jorah/.openclaw-jorah/npm/projects -maxdepth 1 -type d -name 'openclaw-acpx-*' | head -1)
[ -n "$SRC" ] || { echo "live acpx project not found"; exit 1; }
rm -rf /home/jorah/scratch-dev/p5/extensions/acpx /home/jorah/scratch-dev/p5/extensions/acpx-project
cp -a "$SRC" /home/jorah/scratch-dev/p5/extensions/acpx-project
echo "dev Claude Code settings: $DEV/settings.json; acpx project copied from $(basename "$SRC")."
if env CLAUDE_CONFIG_DIR="$DEV" /opt/jorah-tools/claude-code/2.1.300/claude auth status 2>/dev/null | grep -q '"loggedIn": *true'; then
  echo "signed in: yes"
else
  echo "signed in: no (Adam's step)"
fi
