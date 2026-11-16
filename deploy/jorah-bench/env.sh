# shellcheck shell=bash
# Jorah's robotics bench environment. Installed at /opt/jorah-bench/env.sh (root-owned, read-only).
# Source it in bash, as jorah, inside or outside Claude Code's sandbox:
#   . /opt/jorah-bench/env.sh
#
# The bench in /opt/jorah-bench and /opt/ros/jazzy is read-only to jorah. Everything a tool writes
# goes under ~/sandbox/.cache/jorah-bench, the one place Claude Code's sandbox lets it write
# besides ~/work. Nothing here reaches the network: toolchains were fetched at install.
#
# Two passes. The first source does the full setup (ROS, Gazebo, PlatformIO, PATH) and exports
# JORAH_BENCH_ENV_DONE=1 and BASH_ENV pointing here. Every later bash started from that environment,
# such as each command Claude Code runs in its sandbox, sources this again through BASH_ENV and
# takes the short pass: only the per-place fixes (HOME, TMPDIR), which depend on where it runs.
# That matters because the project runner captures these variables once, outside the sandbox
# (services/jorah-projects, bench_environment) and hands them to Claude Code.
#
# PlatformIO with a read-only core [measured 2026-11-16, PlatformIO 6.2.0 on the Mac, offline]:
# pointing PLATFORMIO_CORE_DIR at a read-only folder fails (HomeDirPermissionsError: it locks and
# writes appstate.json and .cache/ there). PLATFORMIO_PLATFORMS_DIR and _PACKAGES_DIR at read-only
# folders fail too, because `pio run` takes a lock file *next to* them (platforms.lock in their
# parent). What works, with nothing written under the read-only copy: a small per-user core in the
# cache folder whose platforms/ and packages/ are symlinks to the bench's read-only copies.
#
# Safe to source any number of times. It never exits the calling shell and prints nothing.

JORAH_BENCH="${JORAH_BENCH:-/opt/jorah-bench}"
export JORAH_BENCH
# Where writes go. Fixed on the first source, so the HOME change below doesn't move it.
if [ -z "${JORAH_BENCH_STATE:-}" ]; then
  JORAH_BENCH_STATE="$HOME/sandbox/.cache/jorah-bench"
fi
export JORAH_BENCH_STATE

# ---- Every pass: fixes that depend on where this shell runs.

# Inside Claude Code's sandbox the real home is hidden and read-only, but Gazebo writes
# ~/.gz/sim/log/<time>/server_console.log on every start, with no variable to move it (gz-common's
# GZ_HOMEDIR is HOME itself on Linux). So when HOME can't be written, HOME becomes a folder in the
# cache. Where HOME is writable it stays as it is.
if [ ! -w "$HOME" ]; then
  mkdir -p "$JORAH_BENCH_STATE/home" 2>/dev/null || true
  if [ -w "$JORAH_BENCH_STATE/home" ]; then
    export JORAH_BENCH_REAL_HOME="$HOME"
    export HOME="$JORAH_BENCH_STATE/home"
  fi
fi

# Compilers and CMake write temporary files to TMPDIR (default /tmp). Claude Code's sandbox sets
# its own; if whatever is set can't be written, use the cache.
if [ ! -w "${TMPDIR:-/tmp}" ]; then
  mkdir -p "$JORAH_BENCH_STATE/tmp" 2>/dev/null || true
  export TMPDIR="$JORAH_BENCH_STATE/tmp"
fi

# ---- First pass only: the bench itself.
if [ "${JORAH_BENCH_ENV_DONE:-}" != 1 ]; then
  mkdir -p "$JORAH_BENCH_STATE/platformio" "$JORAH_BENCH_STATE/xdg-cache" "$JORAH_BENCH_STATE/ros/log" \
    "$JORAH_BENCH_STATE/gz/fuel" 2>/dev/null || true
  export XDG_CACHE_HOME="$JORAH_BENCH_STATE/xdg-cache"

  # ROS 2 Jazzy. setup.bash reads unset variables and runs commands that may return non-zero, so
  # nounset and errexit are off while it runs, then restored.
  if [ -f /opt/ros/jazzy/setup.bash ]; then
    _jb_flags=$-
    set +eu
    # shellcheck disable=SC1091
    . /opt/ros/jazzy/setup.bash
    case $_jb_flags in *e*) set -e ;; esac
    case $_jb_flags in *u*) set -u ;; esac
    unset _jb_flags
  fi
  # rosdep's database was built at install (rosdep update) and is read from here; logs go to the cache.
  export ROS_HOME="$JORAH_BENCH/ros-home"
  export ROS_LOG_DIR="$JORAH_BENCH_STATE/ros/log"
  export ROSDEP_SOURCE_PATH="$JORAH_BENCH/rosdep/sources.list.d"
  export ROSDISTRO_INDEX_URL="https://raw.githubusercontent.com/ros/rosdistro/jazzy/2026-10-05/index-v4.yaml"
  # ROS discovery stays on this machine.
  export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
  export COLCON_HOME="$JORAH_BENCH_STATE/colcon"

  # Gazebo Harmonic (ROS's gz_*_vendor packages): transport on loopback, no model downloads, and the
  # installed server.config read in place instead of copied to ~/.gz/sim/8 on first start.
  export GZ_IP=127.0.0.1
  export GZ_FUEL_CACHE_PATH="$JORAH_BENCH_STATE/gz/fuel"
  if [ -f /opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/server.config ]; then
    export GZ_SIM_SERVER_CONFIG_PATH=/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/server.config
  fi

  # PlatformIO: per-user core with symlinks to the read-only platforms and packages (see the top).
  export PLATFORMIO_CORE_DIR="$JORAH_BENCH_STATE/platformio"
  for _jb_d in platforms packages; do
    if [ ! -e "$PLATFORMIO_CORE_DIR/$_jb_d" ] && [ -d "$JORAH_BENCH/pio/core/$_jb_d" ]; then
      ln -s "$JORAH_BENCH/pio/core/$_jb_d" "$PLATFORMIO_CORE_DIR/$_jb_d" 2>/dev/null || true
    fi
  done
  unset _jb_d
  export PLATFORMIO_BUILD_CACHE_DIR="$JORAH_BENCH_STATE/platformio-build-cache"
  export PLATFORMIO_SETTING_ENABLE_TELEMETRY=No
  export PLATFORMIO_SETTING_CHECK_PLATFORMIO_INTERVAL=3650
  export PLATFORMIO_SETTING_DISABLE_UDEV_RULES_CHECK=Yes

  # Commands: pio, platformio and cad-python (build123d's Python). Not the venvs' own bin folders,
  # whose python3 would shadow the system Python that ROS needs.
  case ":$PATH:" in
    *":$JORAH_BENCH/bin:"*) ;;
    *) export PATH="$JORAH_BENCH/bin:$PATH" ;;
  esac
  # The project runner evaluates this file with PATH=/usr/bin:/bin and passes the result on as the
  # run's whole PATH, so keep /usr/local/bin, where the distro's own tools live.
  case ":$PATH:" in
    *":/usr/local/bin:"*) ;;
    *) export PATH="$PATH:/usr/local/bin" ;;
  esac

  export BASH_ENV="$JORAH_BENCH/env.sh"
  export JORAH_BENCH_ENV_DONE=1
fi
