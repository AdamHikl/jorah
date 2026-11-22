#!/usr/bin/env bash
# Runs on the PC, as jorah, in the jorah distro. Says or switches what Jorah's Claude models bill:
#
#   brain-lane.sh status [--probe]   which lane is set; --probe also runs one test turn on main
#   brain-lane.sh api                every agent on the API key   (config/pc/api-lane.patch.json5)
#   brain-lane.sh max                main and deep on the Max login, deep unsandboxed (config/pc/max-lane.patch.json5)
#
# The Mac HUD runs it through scripts/pc/jorah-brain.sh (docs/adr/0009-hud-brain-switch.md).
# background stays on the key on both lanes: its shell needs the embedded runtime's sandbox.
# It never reads or prints the key, and never prints openclaw.json.
#
# The last line of every run is "LANE: api", "LANE: max", "LANE: mixed" or "LANE: unknown".
# Exit codes: 0 ok; 1 failed (the lines before say what to do); 2 status found a mixed or unknown
# lane; 3 refused before changing anything.
set -euo pipefail

# Overridden only by scripts/pc/tests/test_brain_lane.py.
TREE="${JORAH_TREE:-/opt/jorah}"
STATE="${JORAH_STATE:-$HOME/.openclaw-jorah}"
BACKUPS="$STATE/backups/brain-lane"
KEY_PROFILE=anthropic:jorah-store
# The agents whose own key order moves with the lane. background keeps anthropic:jorah-store.
SWITCHED_AGENTS="main deep"

oc() { openclaw --profile jorah "$@"; }
say() { printf '%s\n' "$*"; }

# A path's value as JSON, or null when it is unset or can't be read (config get prints an error
# object and exits 1 for an unset path, so only a successful answer is passed on).
config_json() {
    local out
    if out="$(oc config get "$1" --json 2>/dev/null)"; then printf '%s\n' "$out"; else echo null; fi
}

# "anthropic:jorah-store", "none" or nothing (unknown).
agent_order() {
    oc models auth order get --provider anthropic --agent "$1" 2>/dev/null \
        | sed -n 's/^Auth profile order override: \([^ ]*\).*/\1/p'
}

has_key_profile() {
    local profiles
    profiles="$(oc models auth list --provider anthropic --agent "$1" 2>/dev/null)" || return 1
    grep -q -- "- $KEY_PROFILE " <<<"$profiles"
}

# Prints one line per setting and the lane on the last line. Reads config only.
read_lane() {
    DEFAULTS="$(config_json agents.defaults.models)" \
    DEEP="$(config_json agents.entries.deep.models)" \
    DEEP_SANDBOX="$(config_json agents.entries.deep.sandbox.mode)" \
    ORDER="$(config_json auth.order)" \
    MAIN_ORDER="$(agent_order main)" \
    DEEP_ORDER="$(agent_order deep)" \
    BACKGROUND_ORDER="$(agent_order background)" \
    KEY_PROFILE="$KEY_PROFILE" \
    python3 -I -c '
import json, os

def load(name):
    try:
        return json.loads(os.environ.get(name, ""))
    except ValueError:
        return None

key = os.environ["KEY_PROFILE"]
runtime_lane = {"openclaw": "api", "claude-cli": "max"}
lanes = []

defaults = load("DEFAULTS")
if isinstance(defaults, dict):
    runtimes = [((v or {}).get("agentRuntime") or {}).get("id")
                for k, v in defaults.items() if k.startswith("anthropic/")]
    on_key = runtimes.count("openclaw")
    on_max = runtimes.count("claude-cli")
    other = len(runtimes) - on_key - on_max
    text = f"Claude models for main, heartbeats and Dreaming: {on_key} on the API key, {on_max} on the Max login"
    print(text + (f", {other} other" if other else ""))
    if not runtimes:
        lanes.append("unknown")
    elif on_key == len(runtimes):
        lanes.append("api")
    elif on_max == len(runtimes):
        lanes.append("max")
    else:
        lanes.append("mixed")
else:
    print("Claude models for main: unknown (config not readable)")
    lanes.append("unknown")

deep = load("DEEP")
runtime = None
if isinstance(deep, dict):
    runtime = ((deep.get("anthropic/claude-opus-5-5") or {}).get("agentRuntime") or {}).get("id")
lane = runtime_lane.get(runtime, "unknown" if runtime is None else "mixed")
print("deep (Opus): " + {"api": "API key", "max": "Max login"}.get(lane, f"unknown ({runtime})"))
lanes.append(lane)

# On Max deep runs outside its sandbox (claude-cli cannot honour it); on the API lane it is sandboxed.
# An unset mode reads as null, which is the default sandbox.
sandbox = os.environ.get("DEEP_SANDBOX", "").strip()
if sandbox == "null":
    print("deep sandbox: on (default)")
    lanes.append("api")
elif sandbox == "\"off\"":
    print("deep sandbox: off (Max lane, tools limited to its allow list)")
    lanes.append("max")
else:
    print(f"deep sandbox: unknown ({sandbox[:30] or 'unreadable'})")
    lanes.append("unknown")

order = load("ORDER")
default_order = order.get("anthropic") if isinstance(order, dict) else None
if default_order == [key]:
    lanes.append("api")
elif default_order == []:
    lanes.append("max")
else:
    lanes.append("unknown" if default_order is None else "mixed")
print("Default key order: " + ("unknown" if default_order is None else (", ".join(default_order) or "none")))

for agent in ("MAIN", "DEEP"):
    value = os.environ.get(agent + "_ORDER", "")
    shown = value or "unknown"
    print(f"{agent.lower()} key order: {shown}")
    lanes.append({key: "api", "none": "max"}.get(value, "mixed" if value else "unknown"))

background = os.environ.get("BACKGROUND_ORDER", "") or "unknown"
print("background: " + ("API key, on both lanes" if background == key else "key order " + background))

if "unknown" in lanes:
    result = "unknown"
elif all(x == "api" for x in lanes):
    result = "api"
elif all(x == "max" for x in lanes):
    result = "max"
else:
    result = "mixed"
print(f"LANE: {result}")
'
}

gateway_line() {
    say "Gateway: $(systemctl is-active openclaw-gateway.service 2>/dev/null || true)"
}

# One test turn on main in a throwaway session, deleted and forgotten afterwards.
probe() {
    local key out rc=0
    key="lane-probe-$(date +%s)"
    say "Test turn on main (session $key). It uses a little credit or quota."
    out="$(oc agent --agent main --session-key "$key" --timeout 180 --json \
        -m 'Route probe. Reply with exactly: PROBE-OK' 2>&1)" || rc=$?
    OUT="$out" RC="$rc" python3 -I -c '
import json, os, re
raw = os.environ["OUT"]
data = {}
try:
    data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
except ValueError:
    pass
result = data.get("result") or {}
meta = result.get("meta") or {}
agent = meta.get("agentMeta") or {}
runner = (meta.get("executionTrace") or {}).get("runner")
credential = (agent.get("credentialSource") or {}).get("kind")
reply = " ".join(str(p.get("text", "")) for p in result.get("payloads") or [])
if not reply:
    reply = str(((meta.get("error") or {}).get("message")) or ((data.get("error") or {}).get("message")) or "")
reply = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "<redacted>", reply)[:200]
ok = data.get("status") == "ok" and "PROBE-OK" in reply
model = agent.get("model") or "?"
print("  reply: " + (reply or "(none)"))
shown_runner = runner or "?"
shown_credential = credential or "native login or none"
print(f"  runner: {shown_runner}, credential: {shown_credential}, model: {model}")
if not ok:
    lane = "failed"
elif runner == "cli":
    lane = "max"
elif runner == "embedded" and credential == "profile":
    lane = "api"
else:
    lane = "unknown"
print(f"PROBE: {lane}")
'
    oc sessions delete "agent:main:$key" --yes >/dev/null 2>&1 || say "  (could not delete the test session agent:main:$key)"
    oc memory forget --agent main --session "agent:main:$key" >/dev/null 2>&1 || true
    return "$rc"
}

status() {
    local lane
    gateway_line
    if [ "${1:-}" = "--probe" ]; then probe || true; fi
    lane="$(read_lane)"
    say "$lane"
    case "$(printf '%s\n' "$lane" | tail -n 1)" in
        "LANE: api" | "LANE: max") return 0 ;;
        *) return 2 ;;
    esac
}

refuse() {
    say "REFUSED: $*"
    say "Nothing was changed."
    read_lane | tail -n 1
    exit 3
}

# A change was made, then something failed. Says so, and what to do, then the lane as it is now.
fail() {
    say "FAILED: $*"
    say "Jorah may be on a mixed route. Switch again, either way: both switches are safe to repeat."
    [ -n "${BACKUP:-}" ] && say "The config before this switch: $BACKUP"
    read_lane
    exit 1
}

switch_to() {
    local target="$1" patch agent lane
    patch="$TREE/config/pc/$target-lane.patch.json5"

    say "1/6 Checking"
    install -d -m 700 "$BACKUPS"
    exec 9>"$BACKUPS/.lock"
    flock -n 9 || refuse "another switch is running"
    [ -f "$patch" ] || refuse "$patch is missing on the PC"
    if [ "$target" = api ]; then
        for agent in $SWITCHED_AGENTS; do
            has_key_profile "$agent" || refuse "$agent has no $KEY_PROFILE key profile. Run $TREE/scripts/pc/use-api-key.sh first"
        done
    else
        [ -d "$HOME/.claude-jorah" ] || refuse "Jorah's Claude login (~/.claude-jorah) is missing"
    fi
    lane="$(read_lane | tail -n 1)"
    say "Now: ${lane#LANE: }"

    say "2/6 Backing up the config"
    BACKUP="$BACKUPS/openclaw.json.$(date +%Y%m%d-%H%M%S).pre-$target"
    if ! { cp -p "$STATE/openclaw.json" "$BACKUP" && chmod 600 "$BACKUP"; }; then
        refuse "could not back up the config"
    fi
    # Keep the newest 20. The names are this script's own, with no spaces.
    # shellcheck disable=SC2012
    ls -1t "$BACKUPS"/openclaw.json.* | tail -n +21 | while IFS= read -r old; do rm -f -- "$old"; done
    say "    $BACKUP"

    say "3/6 Dry run of $(basename "$patch")"
    oc config patch --file "$patch" --dry-run 2>&1 | tail -n 3 || refuse "the dry run failed"

    say "4/6 Applying it (hot reload, no restart)"
    oc config patch --file "$patch" 2>&1 | tail -n 3 || fail "the patch did not apply"

    say "5/6 Key order for $SWITCHED_AGENTS, and deep's sandbox"
    for agent in $SWITCHED_AGENTS; do
        if [ "$target" = api ]; then
            oc models auth order set --provider anthropic --agent "$agent" "$KEY_PROFILE" >/dev/null 2>&1 \
                || fail "could not set $agent's key order"
        else
            oc models auth order clear --provider anthropic --agent "$agent" >/dev/null 2>&1 \
                || fail "could not clear $agent's key order"
        fi
        say "    $agent: $(agent_order "$agent")"
    done

    # deep's sandbox moves with the lane: the Max patch turns it off with an allow list; here the API
    # lane removes both, so deep is sandboxed as before.
    if [ "$target" = api ]; then
        for path in agents.entries.deep.sandbox agents.entries.deep.tools.allow; do
            if [ "$(config_json "$path")" != null ]; then
                oc config unset "$path" >/dev/null 2>&1 || fail "could not remove $path"
            fi
        done
    fi
    say "    deep sandbox: $(config_json agents.entries.deep.sandbox.mode | tr -d '"' | sed 's/^null$/on (default)/')"

    say "6/6 Validating and reading it back"
    oc config validate 2>&1 | tail -n 1 || fail "the config does not validate"
    if [ "$target" = api ]; then
        oc secrets audit --check 2>&1 | tail -n 1 || say "WARNING: the secrets audit flagged something. Tell Claude, without pasting the key."
    fi
    gateway_line
    lane="$(read_lane)"
    say "$lane"
    [ "$(printf '%s\n' "$lane" | tail -n 1)" = "LANE: $target" ] || fail "the config does not read back as $target"
    say "SWITCHED to $target. Existing chats carry over."
}

[ "$(id -un)" = jorah ] || { say "Run this as jorah."; exit 3; }

case "${1:-}" in
    status) shift; status "$@" ;;
    api | max) switch_to "$1" ;;
    *) say "usage: brain-lane.sh status [--probe] | api | max"; exit 3 ;;
esac
