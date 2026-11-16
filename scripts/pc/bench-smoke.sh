#!/usr/bin/env bash
# Smoke test for Jorah's robotics bench (docs/runbooks/robotics-bench.md). Run as jorah, after
# scripts/pc/install-robotics-bench.sh. Offline. Four parts, each must exit 0:
#   colcon  colcon build of a tiny rclcpp package (smoke/colcon_ws)
#   gz      60 simulated seconds of a differential-drive robot in headless Gazebo Harmonic
#           (gz sim -s, 60000 steps of 1 ms, smoke/gz/diff_drive.sdf)
#   pio     PlatformIO build for an ESP32 board (smoke/pio, env esp32dev)
#   cad     STEP export from build123d (smoke/cad_box.py)
# Besides pass or fail it prints what spikes S3 and S4 need (docs/plan/11-project-mode.md section 14):
# whether the ROS middleware and gz-transport start where it runs, /dev/shm, /dev/dri, and memory
# during the simulation. Those are information and never fail the test.
#
# Two ways to run it (the runbook has the exact commands):
#   direct:            bash /opt/jorah/scripts/pc/bench-smoke.sh
#                      Re-runs itself in its own network namespace (unshare -rn, loopback only), so
#                      it is offline even though jorah normally has the internet.
#   in the sandbox:    bash /opt/jorah/scripts/pc/bench-smoke.sh --via-claude
#                      Starts Claude Code headless the way the project runner does (env.sh sourced
#                      outside with PATH=/usr/bin:/bin, HOME reset, the project-run settings, Opus 5.5
#                      at high effort) and has it run this script with its Bash tool, inside its
#                      sandbox, which makes it offline. Uses a little of the Max plan. Spike S3.
# Either way it checks it can't reach the PlatformIO registry, ROS or GitHub, and fails if it can
# (--allow-network skips that check, for diagnosis only).
#
#   --part NAME      run only that part (repeatable): colcon, gz, pio, cad
#   --no-netns       don't make a network namespace (it must already be offline)
#   --allow-network  don't fail when the internet is reachable
#   --via-claude     run it through Claude Code's sandbox (above); --part passes through
#   --settings FILE  with --via-claude: the settings file (default ~/.claude-jorah/project-settings.json)
# Writes only under ~/sandbox/bench-smoke/<time>/ and ~/sandbox/.cache/jorah-bench/.
set -euo pipefail

PARTS=()
NETNS=1
ALLOW_NET=0
VIA_CLAUDE=0
SETTINGS_FILE=/home/jorah/.claude-jorah/project-settings.json
ARGS=("$@")
while [ $# -gt 0 ]; do
  case "$1" in
    --part) [ $# -ge 2 ] || { echo "--part needs a name"; exit 2; }
            case "$2" in colcon|gz|pio|cad) PARTS+=("$2") ;; *) echo "Unknown part: $2"; exit 2 ;; esac
            shift ;;
    --no-netns) NETNS=0 ;;
    --allow-network) ALLOW_NET=1 ;;
    --via-claude) VIA_CLAUDE=1 ;;
    --settings) [ $# -ge 2 ] || { echo "--settings needs a file"; exit 2; }; SETTINGS_FILE="$2"; shift ;;
    -h|--help) awk 'NR > 1 && /^#/ {print; next} NR > 1 {exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)"; exit 2 ;;
  esac
  shift
done
[ "${#PARTS[@]}" -gt 0 ] || PARTS=(colcon gz pio cad)

BENCH="${JORAH_BENCH:-/opt/jorah-bench}"
CLAUDE_BIN=/opt/jorah-tools/claude-code/2.1.300/claude

if [ "$VIA_CLAUDE" = 1 ]; then
  [ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
  for f in "$BENCH/env.sh" "$SETTINGS_FILE" "$CLAUDE_BIN"; do
    [ -e "$f" ] || { echo "Missing $f (bench installed? setup-project-permissions.sh run?)"; exit 4; }
  done
  self="$(readlink -f "$0")"
  part_args=""
  for p in "${PARTS[@]}"; do part_args+=" --part $p"; done
  prompt="Run this one command with the Bash tool and a timeout of 600000 ms: bash $self$part_args
Then show the last 30 lines of its output exactly as printed, and nothing else. Don't change or retry anything."
  mkdir -p "$HOME/work/bench-check"
  cd "$HOME/work/bench-check"
  echo "Starting Claude Code in $PWD with $SETTINGS_FILE (a few turns of the Max plan)..."
  # shellcheck disable=SC2016 # expanded by the inner bash
  exec env -i HOME="$HOME" USER=jorah LOGNAME=jorah LANG=C.UTF-8 PATH=/usr/bin:/bin \
    bash --noprofile --norc -c '
      set -e
      . "$1/env.sh" >/dev/null
      export HOME="$2" CLAUDE_CONFIG_DIR="$2/.claude-jorah" CLAUDE_CODE_TMPDIR="$2/sandbox/.tmp"
      export DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
      mkdir -p "$CLAUDE_CODE_TMPDIR"
      exec "$3" -p --model claude-opus-5-5 --effort high --max-turns 6 --setting-sources "" \
        --settings "$4" --strict-mcp-config --disallowedTools WebFetch WebSearch <<< "$5"' \
    bench-via-claude "$BENCH" "$HOME" "$CLAUDE_BIN" "$SETTINGS_FILE" "$prompt"
fi

# Re-run inside a private network namespace. -r maps jorah to root *inside the namespace only*,
# which is what lets it bring loopback up; files it writes stay jorah's, and everything root-owned
# outside (/opt/jorah-bench, /opt/ros) stays read-only to it, exactly as for jorah.
if [ -z "${JORAH_BENCH_SMOKE_NS:-}" ]; then
  [ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
  if [ "$NETNS" = 1 ]; then
    if unshare -rn true 2>/dev/null; then
      exec unshare -rn env JORAH_BENCH_SMOKE_NS=own bash "$0" "${ARGS[@]}"
    fi
    echo "Note: can't create a network namespace here (expected inside Claude Code's sandbox)."
  fi
  export JORAH_BENCH_SMOKE_NS=inherited
fi
if [ "$JORAH_BENCH_SMOKE_NS" = own ]; then
  ip link set lo up 2>/dev/null || python3 - <<'EOF' || true
import fcntl, socket, struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ifr = struct.pack("16sH", b"lo", 0)
flags = struct.unpack("16sH", fcntl.ioctl(s, 0x8913, ifr))[1]  # SIOCGIFFLAGS
fcntl.ioctl(s, 0x8914, struct.pack("16sH", b"lo", flags | 1))  # SIOCSIFFLAGS, IFF_UP
EOF
fi

[ -f "$BENCH/env.sh" ] || { echo "No $BENCH/env.sh: install the bench first (install-robotics-bench.sh)."; exit 4; }

# BASH_ENV may already have sourced env.sh and moved HOME before this line; judge the real one.
REAL_HOME="${JORAH_BENCH_REAL_HOME:-$HOME}"
WORK="$REAL_HOME/sandbox/bench-smoke/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$WORK"
SUMMARY="$WORK/summary.txt"
: > "$SUMMARY"
# Facts gathered before env.sh, so they describe the place this runs, not the bench's fixes.
if [ -w "$REAL_HOME" ]; then HOME_W=yes; else HOME_W=no; fi
# shellcheck source=/dev/null
. "$BENCH/env.sh"

note() { printf '%s\n' "$*" | tee -a "$SUMMARY"; }
FAILED=0
result() { # part status seconds detail
  note "$(printf '%-7s %-4s %4ss  %s' "$1" "$2" "$3" "$4")"
  [ "$2" = PASS ] || FAILED=1
}
tail_log() { echo "    last lines of $1:"; tail -n 15 "$1" | sed 's/^/    | /'; }

note "Robotics bench smoke test, $(date -u +%Y-%m-%dT%H:%M:%SZ), work folder $WORK"
note "network namespace: $JORAH_BENCH_SMOKE_NS"

# ---- Offline check: direct connections to where toolchains come from must fail.
reachable="$(python3 - <<'EOF'
import socket
open_hosts = []
for host in ("api.registry.platformio.org", "packages.ros.org", "github.com"):
    try:
        socket.create_connection((host, 443), timeout=5).close()
        open_hosts.append(host)
    except OSError:
        pass
print(" ".join(open_hosts))
EOF
)"
if [ -z "$reachable" ]; then
  note "offline: yes (PlatformIO registry, packages.ros.org and github.com unreachable)"
else
  note "offline: NO, reachable: $reachable"
  if [ "$ALLOW_NET" = 0 ]; then FAILED=1; note "  This run can't prove the bench works offline (--allow-network to go on anyway)."; fi
fi

# ---- colcon
if [[ " ${PARTS[*]} " == *" colcon "* ]]; then
  start=$SECONDS
  cp -r "$BENCH/smoke/colcon_ws" "$WORK/colcon_ws"
  log="$WORK/colcon.log"
  if (cd "$WORK/colcon_ws" && timeout 900 colcon build --event-handlers console_direct+) > "$log" 2>&1 \
     && [ -x "$WORK/colcon_ws/install/bench_hello/lib/bench_hello/bench_hello" ]; then
    result colcon PASS $((SECONDS - start)) "bench_hello built"
  else
    result colcon FAIL $((SECONDS - start)) "see $log"; tail_log "$log"
  fi
  if [ -x "$WORK/colcon_ws/install/bench_hello/lib/bench_hello/bench_hello" ]; then
    if timeout 30 "$WORK/colcon_ws/install/bench_hello/lib/bench_hello/bench_hello" > "$WORK/ros-node.log" 2>&1 \
       && grep -q 'node started' "$WORK/ros-node.log"; then
      note "  info: a ROS 2 node (rclcpp, default middleware) starts and stops here: yes"
    else
      note "  info: a ROS 2 node starts here: NO (see $WORK/ros-node.log)"
    fi
  fi
fi

# ---- gz
if [[ " ${PARTS[*]} " == *" gz "* ]]; then
  start=$SECONDS
  log="$WORK/gz.log"
  export GZ_PARTITION="bench-smoke-$$"
  mem_avail() { awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo; }
  avail_before="$(mem_avail)"
  # Best effort: read the robot's pose over gz-transport while it drives.
  timeout 1200 gz topic -e -t /model/bench_bot/odometry > "$WORK/odom.txt" 2> "$WORK/odom.err" &
  echo_pid=$!
  sleep 2
  timeout 900 gz sim -s -r --iterations 60000 -v 2 "$BENCH/smoke/gz/diff_drive.sdf" > "$log" 2>&1 &
  sim_pid=$!
  min_avail="$avail_before"; peak_kb=0
  while kill -0 "$sim_pid" 2>/dev/null; do
    a="$(mem_avail)"; [ "$a" -lt "$min_avail" ] && min_avail="$a"
    for p in $(pgrep -P "$sim_pid" 2>/dev/null) "$sim_pid"; do
      hwm="$(awk '/^VmHWM:/ {print $2}' "/proc/$p/status" 2>/dev/null || true)"
      [ -n "$hwm" ] && [ "$hwm" -gt "$peak_kb" ] && peak_kb="$hwm"
    done
    sleep 1
  done
  rc=0; wait "$sim_pid" || rc=$?
  sleep 1
  kill "$echo_pid" 2>/dev/null || true
  wait "$echo_pid" 2>/dev/null || true
  wall=$((SECONDS - start - 2))
  if [ "$rc" = 0 ]; then
    result gz PASS $((SECONDS - start)) "60000 steps of 1 ms = 60 simulated s, exit 0, ${wall}s wall"
  else
    result gz FAIL $((SECONDS - start)) "gz sim exit $rc (124 = timed out), see $log"; tail_log "$log"
  fi
  odom="$(python3 - "$WORK/odom.txt" <<'EOF'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
msgs = [m for m in re.split(r"\n(?=header \{)", text) if "pose" in m]
if not msgs:
    print("unknown (no odometry message received over gz-transport)")
    sys.exit()
last = msgs[-1]
def num(pattern):
    m = re.search(pattern, last, re.S)
    return float(m.group(1)) if m else 0.0  # protobuf text omits zero fields
sec = num(r"stamp \{\s*sec: (\d+)")
x = num(r"position \{[^}]*?x: ([-0-9.e]+)")
y = num(r"position \{[^}]*?y: ([-0-9.e]+)")
print(f"{len(msgs)} messages; last at {sec:.0f} simulated s, robot at x={x:.2f} m y={y:.2f} m"
      + ("" if abs(x) > 1.0 else " (did NOT drive: check the world file)"))
EOF
)"
  note "  info: gz-transport between processes here: $odom"
  note "  info: memory available before the sim ${avail_before} MB, lowest during it ${min_avail} MB; gz peak RSS $((peak_kb / 1024)) MB"
fi

# ---- pio
if [[ " ${PARTS[*]} " == *" pio "* ]]; then
  start=$SECONDS
  cp -r "$BENCH/smoke/pio" "$WORK/pio"
  log="$WORK/pio.log"
  if timeout 900 pio run -d "$WORK/pio" -e esp32dev > "$log" 2>&1 && [ -s "$WORK/pio/.pio/build/esp32dev/firmware.bin" ]; then
    result pio PASS $((SECONDS - start)) "esp32dev firmware.bin $(stat -c %s "$WORK/pio/.pio/build/esp32dev/firmware.bin") bytes"
  else
    result pio FAIL $((SECONDS - start)) "see $log"; tail_log "$log"
  fi
fi

# ---- cad
if [[ " ${PARTS[*]} " == *" cad "* ]]; then
  start=$SECONDS
  mkdir -p "$WORK/cad"
  log="$WORK/cad.log"
  if timeout 300 cad-python "$BENCH/smoke/cad_box.py" "$WORK/cad/box.step" > "$log" 2>&1 \
     && [ "$(head -c 13 "$WORK/cad/box.step" 2>/dev/null)" = "ISO-10303-21;" ]; then
    result cad PASS $((SECONDS - start)) "box.step $(stat -c %s "$WORK/cad/box.step") bytes, $(grep -o 'volume_mm3=[0-9.]*' "$log")"
  else
    result cad FAIL $((SECONDS - start)) "see $log"; tail_log "$log"
  fi
fi

# ---- Where it ran (S3, S4)
note "Environment:"
note "  home writable before env.sh: $HOME_W (no means sandboxed; env.sh then moves HOME to the cache)"
if touch /dev/shm/.jorah-bench-$$ 2>/dev/null; then rm -f /dev/shm/.jorah-bench-$$; shm=writable; elif [ -d /dev/shm ]; then shm="present, not writable"; else shm=absent; fi
note "  /dev/shm: $shm; /dev/dri: $([ -e /dev/dri ] && echo present || echo absent)"
note "  memory: $(awk '/^MemTotal:/ {t=$2} /^MemAvailable:/ {a=$2} END {printf "%d MB total, %d MB available now", t/1024, a/1024}' /proc/meminfo)"
voice="$(systemctl is-active jorah-voice jorah-voice-qwen 2>/dev/null | tr '\n' ' ' || true)"
note "  voice services (jorah-voice, jorah-voice-qwen): ${voice:-unknown (systemctl not reachable here)}"

if [ "$FAILED" = 0 ]; then
  note "RESULT: PASS (${PARTS[*]})"
else
  note "RESULT: FAIL"
fi
echo "Summary: $SUMMARY"
exit "$FAILED"
