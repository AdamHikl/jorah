#!/usr/bin/env bash
# One-time Mac setup for Jorah's iOS builds (issue 10). Adam runs it; no agent does.
#
#   sudo scripts/mac/setup-jorah-build.sh            # preview, then asks before changing anything
#   scripts/mac/setup-jorah-build.sh --dry-run       # preview only, no sudo needed
#
# What it sets up, only where missing:
#   1. Standard user `jorah-build` (no admin, no autologin) in `_developer`. sysadminctl asks
#      for the new user's password on the terminal; it never goes in a file or variable.
#   2. Group `jorah-handoff` with Adam (the user who ran sudo) as its only member.
#   3. /usr/local/libexec/jorah, root:wheel 0755, so jorah-build can run but not change it.
#      With --install-runner (after issue 8's `serve` is on main), also: copies
#      services/ios-runner/ into it and the wrapper scripts/mac/ios-runner-agent.sh as
#      ios-runner-agent, root-owned, no group or other write; installs the LaunchAgent
#      /Library/LaunchAgents/com.jorah.ios-runner.plist root:wheel 0644 (ADR 0002, route 2);
#      it starts at jorah-build's next login and only for that user.
#   4. /Users/Shared/jorah-handoff, owner jorah-build, group jorah-handoff, 0750, with an
#      inherited ACL so Adam can read and delete each run's folder and nobody else can look.
#   4b. /usr/local/libexec/jorah/ios-preflight, the read-only check (scripts/mac/ios-preflight.sh),
#      so jorah-build can run it too.
#   5. /Library/Application Support/Jorah and its env/ folder, root:wheel 0755, for the runner
#      allowlist (scripts/mac/install-ios-allowlist.sh) and Mizyun's env file, which Adam places.
#
# It never touches a keychain, certificate, device pairing, power or security setting.
# Those are Adam's manual steps in docs/runbooks/ios-builds.md. Rollback:
# scripts/mac/remove-jorah-build.sh.
set -euo pipefail

BUILD_USER="jorah-build"
BUILD_FULLNAME="Jorah build"
HANDOFF_GROUP="jorah-handoff"
LIBEXEC="/usr/local/libexec/jorah"
HANDOFF="/Users/Shared/jorah-handoff"
ADMIN_CONF="/Library/Application Support/Jorah"
AGENT_PLIST="/Library/LaunchAgents/com.jorah.ios-runner.plist"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
RUNNER_SRC="$REPO/services/ios-runner"
# The ACL the hand-off folder and everything created under it carries for the group.
HANDOFF_ACL="group:$HANDOFF_GROUP allow list,search,readattr,readextattr,readsecurity,read,delete,delete_child,file_inherit,directory_inherit"

DRY_RUN=0
INSTALL_RUNNER=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --install-runner) INSTALL_RUNNER=1 ;;
    -h | --help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

die() { echo "Stopped: $*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "this script is for macOS."
if [ "$(id -u)" = "0" ]; then
  ADAM="${SUDO_USER:-}"
elif [ "$DRY_RUN" = "1" ]; then
  ADAM="$(id -un)"  # A preview reads only, so it may run without sudo.
else
  die "run it with sudo, from Adam's account (or add --dry-run to preview without sudo)."
fi
[ -n "$ADAM" ] && [ "$ADAM" != "root" ] || die "run it with sudo from Adam's own account, not a root shell."
[ "$ADAM" != "$BUILD_USER" ] || die "run it from Adam's account, not $BUILD_USER."

user_exists() { dscl . -read "/Users/$1" UniqueID >/dev/null 2>&1; }
group_exists() { dscl . -read "/Groups/$1" PrimaryGroupID >/dev/null 2>&1; }
is_member() { dseditgroup -o checkmember -m "$1" "$2" >/dev/null 2>&1; }

# ---- Preview ---------------------------------------------------------------------------
plan=()
warn=()

if user_exists "$BUILD_USER"; then
  is_member "$BUILD_USER" admin && die "$BUILD_USER exists and is an admin. Remove it from admin first; this script will not continue."
  echo "ok    user $BUILD_USER exists, not an admin"
else
  plan+=("create standard user $BUILD_USER (\"$BUILD_FULLNAME\"); sysadminctl will ask you for its new password")
fi

if user_exists "$BUILD_USER" && is_member "$BUILD_USER" _developer; then
  echo "ok    $BUILD_USER is in _developer"
else
  plan+=("add $BUILD_USER to group _developer")
fi

if group_exists "$HANDOFF_GROUP"; then
  echo "ok    group $HANDOFF_GROUP exists"
else
  plan+=("create group $HANDOFF_GROUP")
fi
if group_exists "$HANDOFF_GROUP" && is_member "$ADAM" "$HANDOFF_GROUP"; then
  echo "ok    $ADAM is in $HANDOFF_GROUP"
else
  plan+=("add $ADAM to group $HANDOFF_GROUP")
fi

# A parent that Adam (or anyone but root) can write would let them swap the runner out.
for dir in /usr/local /usr/local/libexec; do
  [ -e "$dir" ] || continue
  [ "$(stat -f '%Su' "$dir")" = "root" ] || die "$dir is not owned by root ($(stat -f '%Su:%Sg %Lp' "$dir")). Fix that first."
  case "$(stat -f '%Lp' "$dir")" in *[2367]?|*?[2367]) die "$dir is group- or other-writable. Fix that first." ;; esac
done

if [ -d "$LIBEXEC" ] && [ "$(stat -f '%Su:%Sg %Lp' "$LIBEXEC")" = "root:wheel 755" ]; then
  echo "ok    $LIBEXEC is root:wheel 0755"
else
  plan+=("create $LIBEXEC as root:wheel 0755 (parents too)")
fi
# The read-only preflight, root-owned where jorah-build can run it (it cannot read Adam's home).
if cmp -s "$REPO/scripts/mac/ios_preflight.py" "$LIBEXEC/ios_preflight.py" 2>/dev/null && [ -x "$LIBEXEC/ios-preflight" ]; then
  echo "ok    $LIBEXEC/ios-preflight is current"
else
  plan+=("install the read-only preflight as $LIBEXEC/ios-preflight, root:wheel 0755")
fi

if [ "$INSTALL_RUNNER" = "1" ]; then
  [ -x "$RUNNER_SRC/bin/jorah-ios-runner" ] || die "--install-runner given, but $RUNNER_SRC/bin/jorah-ios-runner is not on this checkout (issue 8 not merged?)."
  grep -rqs '"serve"' "$RUNNER_SRC/ios_runner" || die "--install-runner given, but this runner has no 'serve' verb yet (issue 8's HTTP front end). Not installing a LaunchAgent that would fail."
  plan+=("copy $RUNNER_SRC to $LIBEXEC/ios-runner, replacing any older copy, root:wheel, no group or other write")
  plan+=("install scripts/mac/ios-runner-agent.sh as $LIBEXEC/ios-runner-agent, root:wheel 0755")
  plan+=("install $AGENT_PLIST, root:wheel 0644; it starts at $BUILD_USER's next login")
fi

if [ -d "$ADMIN_CONF/env" ]; then
  echo "ok    $ADMIN_CONF and its env folder exist ($(stat -f '%Su:%Sg %Lp' "$ADMIN_CONF"))"
else
  plan+=("create $ADMIN_CONF and $ADMIN_CONF/env as root:wheel 0755 (allowlist and Mizyun's env file, which you place)")
fi

if [ -d "$HANDOFF" ]; then
  echo "info  $HANDOFF exists ($(stat -f '%Su:%Sg %Lp' "$HANDOFF")); owner, mode and ACL will be set again"
fi
plan+=("make $HANDOFF owned by $BUILD_USER:$HANDOFF_GROUP, mode 0750, with ACL: $HANDOFF_ACL")

autologin="$(defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null || true)"
if [ "$autologin" = "$BUILD_USER" ]; then
  plan+=("turn automatic login off (it is set to $BUILD_USER)")
else
  echo "ok    automatic login is not $BUILD_USER"
fi

[ "$INSTALL_RUNNER" = "1" ] || warn+=("runner and LaunchAgent not installed: add --install-runner once issue 8's 'serve' is on main.")
if [ "$(DevToolsSecurity -status 2>/dev/null | grep -c enabled || true)" = "0" ]; then
  warn+=("DevToolsSecurity is disabled. Builds and installs do not need it [inference]; this script leaves it alone.")
fi

echo
if [ "${#plan[@]}" -eq 0 ]; then
  echo "Nothing to change."
else
  echo "This will:"
  for item in "${plan[@]}"; do echo "  - $item"; done
fi
for item in "${warn[@]}"; do echo "note  $item"; done
echo

if [ "$DRY_RUN" = "1" ] || [ "${#plan[@]}" -eq 0 ]; then
  [ "$DRY_RUN" = "1" ] && echo "Dry run: nothing changed."
  exit 0
fi

read -r -p "Type yes to apply exactly this: " answer
[ "$answer" = "yes" ] || die "not applied."

# ---- Apply -----------------------------------------------------------------------------
if ! user_exists "$BUILD_USER"; then
  # "-password -" makes sysadminctl prompt; no -admin, so it is a standard user. It gets no
  # Secure Token, so it cannot unlock FileVault at boot, which is intended.
  sysadminctl -addUser "$BUILD_USER" -fullName "$BUILD_FULLNAME" -shell /bin/zsh -password -
  user_exists "$BUILD_USER" || die "sysadminctl did not create $BUILD_USER."
fi
is_member "$BUILD_USER" admin && die "$BUILD_USER ended up in admin. Stopping."
is_member "$BUILD_USER" _developer || dseditgroup -o edit -a "$BUILD_USER" -t user _developer

group_exists "$HANDOFF_GROUP" || dseditgroup -o create -r "Jorah iOS hand-off readers" "$HANDOFF_GROUP"
is_member "$ADAM" "$HANDOFF_GROUP" || dseditgroup -o edit -a "$ADAM" -t user "$HANDOFF_GROUP"

mkdir -p "$LIBEXEC"
chown root:wheel "$LIBEXEC"
chmod 0755 "$LIBEXEC"
install -o root -g wheel -m 0644 "$REPO/scripts/mac/ios_preflight.py" "$LIBEXEC/ios_preflight.py"
install -o root -g wheel -m 0755 "$REPO/scripts/mac/ios-preflight.sh" "$LIBEXEC/ios-preflight"

if [ "$INSTALL_RUNNER" = "1" ]; then
  staging="$(mktemp -d "$LIBEXEC/.ios-runner.XXXXXX")"
  ditto "$RUNNER_SRC" "$staging"
  find "$staging" -name '__pycache__' -type d -prune -exec rm -rf {} +
  chown -R root:wheel "$staging"
  chmod -R go-w "$staging"
  chmod 0755 "$staging"
  rm -rf "$LIBEXEC/ios-runner"
  mv "$staging" "$LIBEXEC/ios-runner"
  install -o root -g wheel -m 0755 "$REPO/scripts/mac/ios-runner-agent.sh" "$LIBEXEC/ios-runner-agent"
  plutil -lint "$REPO/scripts/mac/com.jorah.ios-runner.plist" >/dev/null
  install -o root -g wheel -m 0644 "$REPO/scripts/mac/com.jorah.ios-runner.plist" "$AGENT_PLIST"
fi

mkdir -p "$ADMIN_CONF/env"
chown root:wheel "$ADMIN_CONF" "$ADMIN_CONF/env"
chmod 0755 "$ADMIN_CONF" "$ADMIN_CONF/env"

mkdir -p "$HANDOFF"
chown "$BUILD_USER:$HANDOFF_GROUP" "$HANDOFF"
chmod 0750 "$HANDOFF"
chmod -N "$HANDOFF"
chmod +a "$HANDOFF_ACL" "$HANDOFF"

if [ "$autologin" = "$BUILD_USER" ]; then
  defaults delete /Library/Preferences/com.apple.loginwindow autoLoginUser
fi

# ---- Check -----------------------------------------------------------------------------
echo
echo "Result:"
id "$BUILD_USER"
is_member "$BUILD_USER" admin && echo "FAIL  $BUILD_USER is an admin" || echo "ok    $BUILD_USER is not an admin"
is_member "$BUILD_USER" _developer && echo "ok    $BUILD_USER is in _developer" || echo "FAIL  $BUILD_USER is not in _developer"
stat -f '%Su:%Sg %Sp %N' "$LIBEXEC" "$ADMIN_CONF"
[ -e "$AGENT_PLIST" ] && stat -f '%Su:%Sg %Sp %N' "$AGENT_PLIST" "$LIBEXEC/ios-runner-agent"
ls -led "$HANDOFF"
echo
echo "Next: docs/runbooks/ios-builds.md, the step after the one you ran. $ADAM may need to log out and in once"
echo "before the new $HANDOFF_GROUP membership applies to Finder."
