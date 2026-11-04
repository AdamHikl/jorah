#!/usr/bin/env bash
# Sets up the jorah-voice WSL distro. Run inside it, as root. Safe to re-run.
# Windows drives and Windows programs are switched off here, so nothing in the distro can reach them.
set -euo pipefail

UV_VERSION="0.13.6"
UV_SHA256="f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645"
CLAUDE_VERSION="2.1.300"
USER_NAME="jorah-voice"
HOME_DIR="/home/$USER_NAME"

[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }

cat > /etc/wsl.conf <<CONF
[boot]
systemd=true
[automount]
enabled=false
mountFsTab=false
[interop]
enabled=false
appendWindowsPath=false
[user]
default=$USER_NAME
CONF

apt-get update -q
apt-get install -y -q ca-certificates curl

id "$USER_NAME" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$USER_NAME"
gpasswd -d "$USER_NAME" sudo >/dev/null 2>&1 || true

as_user() { runuser -u "$USER_NAME" -- env HOME="$HOME_DIR" PATH="$HOME_DIR/.local/bin:/usr/bin:/bin" "$@"; }
as_user mkdir -p "$HOME_DIR/.local/bin" "$HOME_DIR/.cache/jorah-voice" "$HOME_DIR/.claude-jorah" "$HOME_DIR/.config/jorah-voice"
chmod 700 "$HOME_DIR" "$HOME_DIR/.config/jorah-voice" "$HOME_DIR/.claude-jorah"

if ! as_user uv --version 2>/dev/null | grep -q "$UV_VERSION"; then
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  curl -fsSL -o "$work/uv.tgz" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz"
  echo "$UV_SHA256  $work/uv.tgz" | sha256sum -c -
  tar -xzf "$work/uv.tgz" -C "$work" --strip-components=1
  install -o "$USER_NAME" -m 755 "$work/uv" "$HOME_DIR/.local/bin/uv"
fi

if ! as_user claude --version 2>/dev/null | grep -q "$CLAUDE_VERSION"; then
  as_user bash -c "curl -fsSL https://claude.ai/install.sh | bash -s $CLAUDE_VERSION"
fi

token="$HOME_DIR/.config/jorah-voice/token"
if [ ! -s "$token" ]; then
  (umask 077; head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$token")
  chown "$USER_NAME": "$token"
fi

mkdir -p /opt/jorah-voice
echo "Done. Next: restart the distro from Windows, then deploy the code. See docs/runbooks/voice-on-pc.md."
