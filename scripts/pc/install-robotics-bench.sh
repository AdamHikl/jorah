#!/usr/bin/env bash
# Installs Jorah's robotics bench on the jorah distro (docs/plan/11-project-mode.md section 7,
# docs/runbooks/robotics-bench.md). Adam runs it as root, in a Terminal attached to no agent, after
# /opt/jorah holds the reviewed commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-robotics-bench.sh --dry-run
#
# What it installs (pins in deploy/jorah-bench/versions.env):
#   1. ROS 2 Jazzy from the ROS *snapshot* repository of 2026-10-05 (a frozen, signed copy of
#      packages.ros.org; key 4B63CF8F...F125EA checked against the pinned fingerprint): ros-base,
#      Nav2 (navigation2's packages without its RViz plugin), robot_localization, ros_gz (sim,
#      bridge, interfaces), Gazebo Harmonic through ROS's own gz_*_vendor packages (run server-only),
#      colcon and rosdep. No RViz, no GUI tools. apt brings Ubuntu's own dependencies as they are.
#   2. PlatformIO Core in /opt/jorah-bench/pio (venv from requirements-pio.txt, hashes required),
#      then the Espressif 32 and Raspberry Pi RP2040 platforms and their toolchains: fetched now, by
#      building deploy/jorah-bench/smoke/pio for every board in it, then checked for age (7 days).
#   3. build123d in /opt/jorah-bench/py (venv from requirements-cad.txt, hashes required).
#   4. rosdep's database, at the rosdistro tag matching the snapshot, in /opt/jorah-bench/ros-home.
#   5. /opt/jorah-bench/env.sh, bin/ (pio, platformio, cad-python), the smoke assets, and a record
#      of what was installed (INSTALLED.txt). All root-owned and read-only to jorah.
# KiCad CLI is not installed (no CLI-only package on noble; see the runbook).
#
#   --dry-run          checks the sources, the key and the pins, and simulates the apt install with
#                      throwaway apt lists in a temporary folder (removed again), so it prints the
#                      real package count and sizes. Writes nothing to the system.
#   --undo             removes what this install added: the apt packages it newly installed (recorded
#                      in /opt/jorah-bench/apt-added.txt), the snapshot apt source and key, and
#                      /opt/jorah-bench. Asks for "yes" first. Packages that were there before stay.
#   --undo --dry-run   shows what --undo would remove (apt simulation), removes nothing.
# Rerunning the install is safe: apt is a no-op, the venvs are rebuilt, PlatformIO keeps its packages.
set -euo pipefail

MODE=install
DRY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --undo) MODE=undo ;;
    -h|--help) awk 'NR > 1 && /^#/ {print; next} NR > 1 {exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 2 ;;
  esac
done

[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO/deploy/jorah-bench"
BENCH=/opt/jorah-bench
APT_SOURCE=/etc/apt/sources.list.d/jorah-bench-ros-snapshot.sources
KEYRING=/usr/share/keyrings/jorah-bench-ros-snapshots.gpg
APT_ADDED="$BENCH/apt-added.txt"
APT_BEFORE="$BENCH/.apt-before.txt"
export DEBIAN_FRONTEND=noninteractive LC_ALL=C
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PIP_NO_INPUT=1

[ -f "$SRC/versions.env" ] || { echo "Missing $SRC/versions.env: is $REPO the reviewed checkout?"; exit 4; }
# shellcheck source=/dev/null
. "$SRC/versions.env"

# Explicit package list. Nav2 is navigation2's own dependency list in the snapshot, minus
# nav2_rviz_plugins (RViz needs a display). ros_gz is ros_gz_sim, _bridge and _interfaces, minus
# ros_gz_sim_demos (which pulls RViz).
ROS_PACKAGES=(
  ros-jazzy-ros-base
  ros-jazzy-nav2-amcl ros-jazzy-nav2-behavior-tree ros-jazzy-nav2-behaviors ros-jazzy-nav2-bt-navigator
  ros-jazzy-nav2-collision-monitor ros-jazzy-nav2-constrained-smoother ros-jazzy-nav2-controller
  ros-jazzy-nav2-core ros-jazzy-nav2-costmap-2d ros-jazzy-nav2-dwb-controller
  ros-jazzy-nav2-graceful-controller ros-jazzy-nav2-lifecycle-manager ros-jazzy-nav2-map-server
  ros-jazzy-nav2-mppi-controller ros-jazzy-nav2-msgs ros-jazzy-nav2-navfn-planner ros-jazzy-nav2-planner
  ros-jazzy-nav2-regulated-pure-pursuit-controller ros-jazzy-nav2-rotation-shim-controller
  ros-jazzy-nav2-route ros-jazzy-nav2-simple-commander ros-jazzy-nav2-smac-planner ros-jazzy-nav2-smoother
  ros-jazzy-nav2-theta-star-planner ros-jazzy-nav2-util ros-jazzy-nav2-velocity-smoother
  ros-jazzy-nav2-voxel-grid ros-jazzy-nav2-waypoint-follower ros-jazzy-opennav-docking
  ros-jazzy-opennav-docking-bt ros-jazzy-opennav-docking-core
  ros-jazzy-robot-localization
  ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge ros-jazzy-ros-gz-interfaces
  ros-jazzy-gz-sim-vendor ros-jazzy-gz-tools-vendor
  python3-colcon-common-extensions python3-rosdep
)
# libgl1: OCP (build123d's OpenCascade) loads libGL.so.1. Gazebo pulls it in too; named for clarity.
UBUNTU_PACKAGES=(build-essential python3-venv libgl1)
ALL_PACKAGES=("${ROS_PACKAGES[@]}" "${UBUNTU_PACKAGES[@]}")

say() { printf '== %s\n' "$*"; }

installed_packages() { dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' | awk '$1 ~ /^ii/ {print $2}' | sort -u; }

# Throwaway apt: the system's own sources plus the snapshot, lists and cache in a temp folder.
TMP=""
cleanup() { if [ -n "$TMP" ]; then rm -rf "$TMP"; fi; }
trap cleanup EXIT
temp_apt() {
  TMP="$(mktemp -d)"
  mkdir -p "$TMP/parts" "$TMP/lists/partial" "$TMP/cache/archives/partial" "$TMP/gnupg"
  chmod 700 "$TMP/gnupg"
  cp /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list "$TMP/parts/" 2>/dev/null || true
  if [ -f /etc/apt/sources.list ]; then cp /etc/apt/sources.list "$TMP/sources.list"; else : > "$TMP/sources.list"; fi
  gpg --homedir "$TMP/gnupg" --batch --dearmor < "$SRC/keys/ros-snapshots.asc" > "$TMP/ros-snapshots.gpg"
  write_source "$TMP/parts/jorah-bench-ros-snapshot.sources" "$TMP/ros-snapshots.gpg"
  APT_TMP=(-o "Dir::Etc::SourceList=$TMP/sources.list" -o "Dir::Etc::SourceParts=$TMP/parts"
    -o "Dir::State::Lists=$TMP/lists" -o "Dir::Cache=$TMP/cache" -o "APT::Sandbox::User=root")
}

write_source() {
  cat > "$1" <<EOF
# Jorah's robotics bench: ROS 2 $ROS_DISTRO from the ROS snapshot of $ROS_SNAPSHOT (scripts/pc/install-robotics-bench.sh).
# Plain http is the snapshot server's only working scheme; apt checks the signature (key $ROS_SNAPSHOT_KEY_FPR).
Types: deb
URIs: $ROS_SNAPSHOT_URL
Suites: noble
Components: main
Architectures: amd64
Signed-By: $2
EOF
}

check_key() {
  local home fpr
  home="$(mktemp -d)"
  fpr="$(gpg --homedir "$home" --batch --with-colons --show-keys "$SRC/keys/ros-snapshots.asc" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
  rm -rf "$home"
  if [ "$fpr" != "$ROS_SNAPSHOT_KEY_FPR" ]; then
    echo "  Key fingerprint mismatch: file has '${fpr:-none}', pinned $ROS_SNAPSHOT_KEY_FPR. Stopping."
    exit 5
  fi
  echo "  snapshot key: $fpr (matches the pin)"
}

check_system() {
  # shellcheck disable=SC1091
  . /etc/os-release
  [ "${VERSION_CODENAME:-}" = noble ] || { echo "  This is ${PRETTY_NAME:-unknown}; the bench needs Ubuntu 24.04 (noble)."; exit 4; }
  [ "$(dpkg --print-architecture)" = amd64 ] || { echo "  Needs amd64."; exit 4; }
  for bin in gpg apt-get python3 runuser; do command -v "$bin" >/dev/null || { echo "  $bin is missing."; exit 4; }; done
  for f in env.sh requirements-pio.txt requirements-cad.txt pio-age-check.py keys/ros-snapshots.asc \
           rosdep/20-default.list smoke/pio/platformio.ini smoke/gz/diff_drive.sdf smoke/cad_box.py; do
    [ -f "$SRC/$f" ] || { echo "  Missing $SRC/$f"; exit 4; }
  done
  # The seed project's platform pins must be the ones in versions.env.
  if ! grep -q "platformio/espressif32@$PIO_ESPRESSIF32\$" "$SRC/smoke/pio/platformio.ini" \
    || ! grep -q "platformio/raspberrypi@$PIO_RASPBERRYPI\$" "$SRC/smoke/pio/platformio.ini"; then
    echo "  smoke/pio/platformio.ini doesn't pin espressif32@$PIO_ESPRESSIF32 and raspberrypi@$PIO_RASPBERRYPI."
    exit 4
  fi
  grep -q "^platformio==$PIO_VERSION " "$SRC/requirements-pio.txt" || { echo "  requirements-pio.txt doesn't pin platformio==$PIO_VERSION."; exit 4; }
  grep -q "^build123d==$BUILD123D_VERSION " "$SRC/requirements-cad.txt" || { echo "  requirements-cad.txt doesn't pin build123d==$BUILD123D_VERSION."; exit 4; }
  # A live ROS source next to the snapshot would let apt mix newer packages in.
  if grep -rlsE 'packages\.ros\.org|repo\.ros2\.org' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null; then
    echo "  A live ROS apt source is configured (files above). Remove it first: the bench pins the snapshot."
    exit 4
  fi
  echo "  $PRETTY_NAME, $(dpkg --print-architecture), python $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  echo "  free on /: $(df -BG --output=avail / | tail -1 | tr -d ' ') (the bench needs about 10 GB; measured at install)"
  echo "  memory: $(free -m | awk '/^Mem:/ {printf "%d MB total, %d MB available", $2, $7}')"
}

simulate_apt() {
  temp_apt
  echo "  apt update with throwaway lists (network reads only)..."
  apt-get "${APT_TMP[@]}" -qq update
  local sim new dl inst
  sim="$(apt-get "${APT_TMP[@]}" -s install --no-install-recommends "${ALL_PACKAGES[@]}")"
  mapfile -t new < <(printf '%s\n' "$sim" | awk '$1 == "Inst" {print $2}')
  echo "  packages apt would newly install: ${#new[@]}"
  if [ "${#new[@]}" -gt 0 ]; then
    dl="$(apt-get "${APT_TMP[@]}" -qq --print-uris install --no-install-recommends "${ALL_PACKAGES[@]}" \
      | awk '{s += $3} END {printf "%.0f", s / 1048576}')"
    inst="$(apt-cache "${APT_TMP[@]}" show --no-all-versions "${new[@]}" 2>/dev/null \
      | awk '/^Installed-Size:/ {s += $2} END {printf "%.0f", s / 1024}')"
    echo "  download: about ${dl} MB; installed size: about ${inst} MB"
    printf '%s\n' "$sim" | awk '$1 == "Inst" && $2 ~ /^ros-jazzy-(ros-base|navigation2|nav2-core|robot-localization|ros-gz-sim|gz-sim-vendor|gz-tools-vendor|rclcpp)$/ {print "    " $2 " " $3}' | tr -d '[]'
    printf '%s\n' "$sim" | awk '$1 == "Inst" && $2 ~ /^ros-jazzy-rviz/ {print "    UNEXPECTED: " $2}'
  fi
}

# ---------------------------------------------------------------------------------------------
if [ "$MODE" = undo ]; then
  [ -d "$BENCH" ] || [ -f "$APT_SOURCE" ] || { echo "Nothing to undo: no $BENCH and no $APT_SOURCE."; exit 0; }
  extra=()
  mapfile -t remove < <(
    if [ -f "$APT_ADDED" ]; then cat "$APT_ADDED"
    elif [ -f "$APT_BEFORE" ]; then comm -13 "$APT_BEFORE" <(installed_packages)
    fi | sort -u | comm -12 - <(installed_packages))
  say "Undo: what goes"
  echo "  $BENCH ($(du -sh "$BENCH" 2>/dev/null | cut -f1 || echo absent))"
  echo "  $APT_SOURCE and $KEYRING"
  echo "  apt packages this install added and still installed: ${#remove[@]}"
  if [ "${#remove[@]}" -gt 0 ]; then
    apt-get -s purge "${remove[@]}" | awk '$1 == "Purg" {n++} END {print "  apt simulation: " n+0 " packages purged"}'
    mapfile -t extra < <(apt-get -s purge "${remove[@]}" | awk '$1 == "Purg" {print $2}' | sort -u \
      | comm -23 - <(printf '%s\n' "${remove[@]}" | sort -u))
    if [ "${#extra[@]}" -gt 0 ]; then
      echo "  These were NOT added by this install but depend on what it added, and would go too:"
      printf '    %s\n' "${extra[@]}"
    fi
  fi
  echo "  Per-user caches stay: /home/jorah/sandbox/.cache/jorah-bench (jorah may delete it)."
  if [ "$DRY" = 1 ]; then echo "Dry run: nothing removed."; exit 0; fi
  if [ "${#extra[@]}" -gt 0 ]; then echo "Stopping: other packages depend on the bench. Remove them first or purge by hand."; exit 6; fi
  read -r -p "Type yes to remove all of the above: " answer
  [ "$answer" = yes ] || { echo "Nothing removed."; exit 0; }
  [ "${#remove[@]}" -gt 0 ] && apt-get purge -y "${remove[@]}"
  rm -f "$APT_SOURCE" "$KEYRING"
  rm -rf "$BENCH"
  apt-get -qq update || true
  echo "Undo done. Check: dpkg -l 'ros-jazzy-*' lists nothing; ls $BENCH fails."
  exit 0
fi

# ---------------------------------------------------------------------------------------------
say "1. Checks"
check_system
check_key
echo "  ROS snapshot: $ROS_SNAPSHOT_URL (rosdistro tag $ROSDISTRO_TAG)"
echo "  PlatformIO $PIO_VERSION; espressif32@$PIO_ESPRESSIF32, raspberrypi@$PIO_RASPBERRYPI; build123d $BUILD123D_VERSION"
echo "  PyPI pins: $(grep -c '^[A-Za-z0-9]' "$SRC/requirements-pio.txt") for PlatformIO, $(grep -c '^[A-Za-z0-9]' "$SRC/requirements-cad.txt") for build123d, every one with a hash"

if [ "$DRY" = 1 ]; then
  say "2. apt simulation"
  simulate_apt
  say "Would then"
  echo "  write $APT_SOURCE and $KEYRING, apt-get install --no-install-recommends (${#ALL_PACKAGES[@]} named packages)"
  echo "  build $BENCH/pio/venv and $BENCH/py/venv with pip --require-hashes --only-binary :all:"
  echo "  fetch the PlatformIO platforms and toolchains into $BENCH/pio/core by building every board in"
  echo "  smoke/pio (esp32dev, xiao_esp32s3, pico), then check each package's release date (7 days)"
  echo "  rosdep update into $BENCH/ros-home; copy env.sh, bin/, smoke/; chown root, read-only to jorah"
  echo "Dry run: nothing written outside a temporary folder, which is removed."
  exit 0
fi

mkdir -p "$BENCH"
chmod 755 "$BENCH"
[ -f "$APT_BEFORE" ] || installed_packages > "$APT_BEFORE"

say "2. ROS snapshot apt source and key"
gpg_home="$(mktemp -d)"
gpg --homedir "$gpg_home" --batch --dearmor < "$SRC/keys/ros-snapshots.asc" > "$KEYRING.new"
rm -rf "$gpg_home"
chmod 644 "$KEYRING.new" && mv "$KEYRING.new" "$KEYRING"
write_source "$APT_SOURCE" "$KEYRING"
chmod 644 "$APT_SOURCE"
apt-get -qq update

say "3. apt install (ROS 2 Jazzy, Nav2, robot_localization, ros_gz with Gazebo Harmonic, colcon, rosdep)"
apt-get install -y --no-install-recommends "${ALL_PACKAGES[@]}"
{ [ -f "$APT_ADDED" ] && cat "$APT_ADDED"; comm -13 "$APT_BEFORE" <(installed_packages); } | sort -u > "$APT_ADDED.new"
mv "$APT_ADDED.new" "$APT_ADDED"
echo "  newly installed by this script (kept for --undo): $(wc -l < "$APT_ADDED") packages"

say "4. PlatformIO Core $PIO_VERSION in $BENCH/pio"
rm -rf "$BENCH/pio/venv"
mkdir -p "$BENCH/pio/core"
python3 -m venv "$BENCH/pio/venv"
"$BENCH/pio/venv/bin/pip" install -q --require-hashes --no-deps --only-binary :all: -r "$SRC/requirements-pio.txt"
"$BENCH/pio/venv/bin/pip" check
mkdir -p "$BENCH/bin"
ln -sfn ../pio/venv/bin/pio "$BENCH/bin/pio"
ln -sfn ../pio/venv/bin/platformio "$BENCH/bin/platformio"

say "5. PlatformIO platforms and toolchains (network now, never again)"
seed="$(mktemp -d)"
cp -r "$SRC/smoke/pio/." "$seed/"
(
  export PLATFORMIO_CORE_DIR="$BENCH/pio/core" PLATFORMIO_SETTING_ENABLE_TELEMETRY=No
  "$BENCH/bin/pio" pkg install -d "$seed"
  "$BENCH/bin/pio" run -d "$seed" -e esp32dev -e xiao_esp32s3 -e pico
)
rm -rf "$seed" "$BENCH/pio/core/.cache"
# PlatformIO may pip-install helpers for a platform during a build; those bypass the hashed lock.
extra_py="$("$BENCH/pio/venv/bin/pip" freeze --all | cut -d= -f1 | tr 'A-Z_' 'a-z-' | sort -u \
  | comm -23 - <(grep -oE '^[A-Za-z0-9._-]+==' "$SRC/requirements-pio.txt" | tr -d '=' | tr 'A-Z_' 'a-z-' | sort -u) | tr '\n' ' ')"
echo "  Python packages added by PlatformIO outside the hashed lock: ${extra_py:-none}"
echo "  release dates of everything fetched:"
python3 "$SRC/pio-age-check.py" "$BENCH/pio/core" 7 || {
  echo "  Something fetched is newer than 7 days or its date is unknown. Stopping before the rest."
  echo "  Pin it in smoke/pio/platformio.ini (platform_packages) or write an exception, then rerun."
  exit 7
}

say "6. build123d $BUILD123D_VERSION in $BENCH/py"
rm -rf "$BENCH/py/venv"
mkdir -p "$BENCH/py"
python3 -m venv "$BENCH/py/venv"
"$BENCH/py/venv/bin/pip" install -q --require-hashes --no-deps --only-binary :all: -r "$SRC/requirements-cad.txt"
"$BENCH/py/venv/bin/pip" check
"$BENCH/py/venv/bin/python" -c 'import build123d; print("  build123d", build123d.__version__)'
# A wrapper, not a symlink: Python finds its venv from the path it was started by.
printf '#!/bin/sh\n# build123d Python (scripts/pc/install-robotics-bench.sh)\nexec %s "$@"\n' "$BENCH/py/venv/bin/python" > "$BENCH/bin/cad-python"
chmod 755 "$BENCH/bin/cad-python"

say "7. rosdep database at $ROSDISTRO_TAG"
mkdir -p "$BENCH/rosdep/sources.list.d" "$BENCH/ros-home"
install -m 644 "$SRC/rosdep/20-default.list" "$BENCH/rosdep/sources.list.d/20-default.list"
ROS_HOME="$BENCH/ros-home" ROSDEP_SOURCE_PATH="$BENCH/rosdep/sources.list.d" \
  ROSDISTRO_INDEX_URL="https://raw.githubusercontent.com/ros/rosdistro/$ROSDISTRO_TAG/index-v4.yaml" \
  rosdep update --rosdistro "$ROS_DISTRO"

say "8. env.sh, smoke assets, ownership"
install -m 644 "$SRC/env.sh" "$BENCH/env.sh"
install -m 644 "$SRC/versions.env" "$BENCH/versions.env"
rm -rf "$BENCH/smoke"
cp -r "$SRC/smoke" "$BENCH/smoke"
chown -R root:root "$BENCH"
chmod -R u+rwX,go+rX,go-w "$BENCH"
chmod 600 "$APT_BEFORE"

say "9. Record"
{
  echo "Installed $(date -u +%Y-%m-%dT%H:%M:%SZ) by scripts/pc/install-robotics-bench.sh from $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 'unknown commit')"
  echo "ROS snapshot: $ROS_SNAPSHOT_URL"
  for p in ros-jazzy-ros-base ros-jazzy-nav2-core ros-jazzy-robot-localization ros-jazzy-ros-gz-sim \
           ros-jazzy-gz-sim-vendor python3-colcon-core python3-rosdep; do
    echo "  $p $(dpkg-query -W -f='${Version}' "$p" 2>/dev/null || echo unknown)"
  done
  echo "PlatformIO: $("$BENCH/bin/pio" --version 2>/dev/null || echo unknown)"
  echo "build123d: $("$BENCH/bin/cad-python" -c 'import build123d; print(build123d.__version__)' 2>/dev/null || echo unknown)"
  # shellcheck disable=SC2016 # dpkg-query's own ${...} format
  echo "apt packages added: $(wc -l < "$APT_ADDED"), installed size $(xargs dpkg-query -W -f='${Installed-Size}\n' < "$APT_ADDED" | awk '{s += $1} END {printf "%.0f MB", s / 1024}')"
  echo "disk: /opt/ros/jazzy $(du -sh /opt/ros/jazzy | cut -f1), $BENCH/pio $(du -sh "$BENCH/pio" | cut -f1), $BENCH/py $(du -sh "$BENCH/py" | cut -f1)"
  echo "free on / afterwards: $(df -BG --output=avail / | tail -1 | tr -d ' ')"
} > "$BENCH/INSTALLED.txt"
chmod 644 "$BENCH/INSTALLED.txt"
sed 's/^/  /' "$BENCH/INSTALLED.txt"

say "10. As jorah: the commands resolve (no build yet; that's bench-smoke.sh)"
# shellcheck disable=SC2016 # expanded by jorah's shell
runuser -u jorah -- env HOME=/home/jorah bash -c '. /opt/jorah-bench/env.sh && for c in ros2 colcon rosdep gz pio cad-python; do printf "  %-11s %s\n" "$c" "$(command -v "$c" || echo MISSING)"; done'
echo "Done. Next: bench-smoke.sh as jorah (docs/runbooks/robotics-bench.md). Undo: --undo."
