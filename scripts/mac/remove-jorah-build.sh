#!/usr/bin/env bash
# Rollback for scripts/mac/setup-jorah-build.sh (issue 10). Adam runs it; no agent does.
#
#   sudo scripts/mac/remove-jorah-build.sh                  # preview, then asks
#   scripts/mac/remove-jorah-build.sh --dry-run             # preview only, no sudo needed
#   sudo scripts/mac/remove-jorah-build.sh --keep-handoff   # keep built .ipa files
#
# Removes, where present: the runner LaunchAgent com.jorah.ios-runner (ADR 0002, route 2),
# the user jorah-build with its home (its keychain, clones and device trust go with it),
# /usr/local/libexec/jorah, /Library/Application Support/Jorah (the runner allowlist),
# /Users/Shared/jorah-handoff (unless --keep-handoff) and the group jorah-handoff. The Tailscale
# Serve forward and the key copy on the PC are manual (runbook, "Rollback"). It does not revoke the certificate, delete profiles in the developer portal,
# remove a GitHub deploy key or unpair the phone: those are manual, see
# docs/runbooks/ios-builds.md, "Rollback".
set -euo pipefail

BUILD_USER="jorah-build"
HANDOFF_GROUP="jorah-handoff"
LIBEXEC="/usr/local/libexec/jorah"
HANDOFF="/Users/Shared/jorah-handoff"
ADMIN_CONF="/Library/Application Support/Jorah"
LAUNCHD_LABEL="com.jorah.ios-runner"
AGENT_PLIST="/Library/LaunchAgents/$LAUNCHD_LABEL.plist"

DRY_RUN=0
KEEP_HANDOFF=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --keep-handoff) KEEP_HANDOFF=1 ;;
    -h | --help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

die() { echo "Stopped: $*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "this script is for macOS."
if [ "$(id -u)" != "0" ] && [ "$DRY_RUN" != "1" ]; then
  die "run it with sudo, from Adam's account (or add --dry-run to preview without sudo)."
fi
[ "${SUDO_USER:-$(id -un)}" != "$BUILD_USER" ] || die "run it from Adam's account, not $BUILD_USER."

user_exists() { dscl . -read "/Users/$1" UniqueID >/dev/null 2>&1; }
group_exists() { dscl . -read "/Groups/$1" PrimaryGroupID >/dev/null 2>&1; }

plan=()
build_home=""
if user_exists "$BUILD_USER"; then
  build_home="$(dscl . -read "/Users/$BUILD_USER" NFSHomeDirectory | awk '{print $2}')"
fi

[ -e "$AGENT_PLIST" ] && plan+=("stop the runner agent and delete $AGENT_PLIST")
if [ -n "$build_home" ]; then
  plan+=("stop processes of $BUILD_USER")
  plan+=("delete user $BUILD_USER and its home $build_home (signing keychain, profiles, clones); cannot be undone")
fi
[ -e "$LIBEXEC" ] && plan+=("delete $LIBEXEC")
[ -e "$ADMIN_CONF" ] && plan+=("delete $ADMIN_CONF (runner allowlist)")
if [ -e "$HANDOFF" ]; then
  if [ "$KEEP_HANDOFF" = "1" ]; then
    echo "keep  $HANDOFF (--keep-handoff); its owner becomes a bare UID once the user is gone"
  else
    runs="$(find "$HANDOFF" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l | tr -d ' ')"
    plan+=("delete $HANDOFF and the $runs run folder(s) in it; cannot be undone")
  fi
fi
group_exists "$HANDOFF_GROUP" && plan+=("delete group $HANDOFF_GROUP")

echo
if [ "${#plan[@]}" -eq 0 ]; then
  echo "Nothing to remove."
  exit 0
fi
echo "This will:"
for item in "${plan[@]}"; do echo "  - $item"; done
echo
echo "Manual afterwards: revoke the jorah-build Development certificate, delete its profiles"
echo "if unused, remove any deploy keys, and check the phone (runbook, Rollback)."
echo

if [ "$DRY_RUN" = "1" ]; then
  echo "Dry run: nothing changed."
  exit 0
fi

read -r -p "Type yes to remove exactly this: " answer
[ "$answer" = "yes" ] || die "nothing removed."

if [ -e "$AGENT_PLIST" ]; then
  if [ -n "$build_home" ]; then
    launchctl bootout "gui/$(id -u "$BUILD_USER")/$LAUNCHD_LABEL" 2>/dev/null || true
  fi
  rm -f "$AGENT_PLIST"
fi

if [ -n "$build_home" ]; then
  pkill -u "$BUILD_USER" 2>/dev/null || true
  sleep 2
  pkill -9 -u "$BUILD_USER" 2>/dev/null || true
  # Interactive: sysadminctl asks for an admin's authentication if it needs it.
  sysadminctl -deleteUser "$BUILD_USER"
  user_exists "$BUILD_USER" && die "$BUILD_USER still exists."
  [ -e "$build_home" ] && echo "note  $build_home still exists; check it, then delete it by hand"
fi

rm -rf "$LIBEXEC" "$ADMIN_CONF"
rmdir /usr/local/libexec 2>/dev/null || true

if [ "$KEEP_HANDOFF" != "1" ]; then
  rm -rf "$HANDOFF"
fi

group_exists "$HANDOFF_GROUP" && dseditgroup -o delete "$HANDOFF_GROUP"

echo
echo "Result:"
user_exists "$BUILD_USER" && echo "FAIL  user $BUILD_USER exists" || echo "ok    user $BUILD_USER is gone"
[ -e "$LIBEXEC" ] && echo "FAIL  $LIBEXEC exists" || echo "ok    $LIBEXEC is gone"
[ -e "$AGENT_PLIST" ] && echo "FAIL  $AGENT_PLIST exists" || echo "ok    $AGENT_PLIST is gone"
group_exists "$HANDOFF_GROUP" && echo "FAIL  group $HANDOFF_GROUP exists" || echo "ok    group $HANDOFF_GROUP is gone"
if [ "$KEEP_HANDOFF" = "1" ]; then echo "kept  $HANDOFF"; else
  [ -e "$HANDOFF" ] && echo "FAIL  $HANDOFF exists" || echo "ok    $HANDOFF is gone"
fi
