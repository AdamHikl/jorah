#!/usr/bin/env bash
# Sets up the jorah WSL distro. Run inside it, as root. Safe to re-run.
# Windows drives and Windows programs are switched off here. It starts no Gateway.
set -euo pipefail

UV_VERSION="0.13.6"
UV_SHA256="f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645"
CLAUDE_VERSION="2.1.300"
NODE_VERSION="26.13.0"
NODE_SHA256="d28a96af6c38596f6d9d97c0ee531c13d238d757742387d1928de822d959e997"
OPENCLAW_VERSION="2026.10.9"
USER_NAME="jorah"
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
apt-get install -y -q bubblewrap ca-certificates curl libatomic1 nftables xz-utils
# Tools for Jorah's shell, and rootless Podman for OpenClaw's sandbox (OpenClaw has no bubblewrap backend).
apt-get install -y -q build-essential ripgrep jq unzip zip ffmpeg sqlite3 just htop \
  podman catatonit uidmap passt slirp4netns

# Google Chrome for the browser tool. A written exception to the 7-day rule: a browser takes security fixes
# as they ship (docs/runbooks/jorah-on-pc.md). Its package replaces this source with its own
# google-chrome.sources, signed by /usr/share/keyrings/google-chrome.gpg, and adds /etc/cron.daily/google-chrome.
if ! command -v google-chrome-stable >/dev/null; then
  install -d -m 755 /etc/apt/keyrings
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor --yes -o /etc/apt/keyrings/google-chrome.gpg
  # Google Inc. (Linux Packages Signing Authority), measured 2026-11-06.
  gpg --show-keys --with-colons /etc/apt/keyrings/google-chrome.gpg | grep -q '^fpr:::::::::EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796:' \
    || { echo "Unexpected Google signing key" >&2; exit 1; }
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list
  apt-get update -q
  apt-get install -y -q google-chrome-stable
fi

id "$USER_NAME" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$USER_NAME"
gpasswd -d "$USER_NAME" sudo >/dev/null 2>&1 || true
# Rootless Podman needs subordinate IDs. The first build named the user jorah-voice, which no longer exists.
for f in /etc/subuid /etc/subgid; do
  if ! grep -q "^$USER_NAME:" "$f"; then
    if grep -q '^jorah-voice:' "$f" && ! id jorah-voice >/dev/null 2>&1; then
      sed -i "s/^jorah-voice:/$USER_NAME:/" "$f"
    else
      echo "$USER_NAME:100000:65536" >> "$f"
    fi
  fi
done

as_user() { runuser -u "$USER_NAME" -- env HOME="$HOME_DIR" PATH="$HOME_DIR/.local/bin:/usr/local/bin:/usr/bin:/bin" "$@"; }
as_user mkdir -p "$HOME_DIR/.local/bin" "$HOME_DIR/.cache/jorah-voice" "$HOME_DIR/.claude-jorah" "$HOME_DIR/.config/jorah-voice"
chmod 700 "$HOME_DIR" "$HOME_DIR/.config/jorah-voice" "$HOME_DIR/.claude-jorah"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if ! as_user uv --version 2>/dev/null | grep -q "$UV_VERSION"; then
  curl -fsSL -o "$work/uv.tgz" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz"
  echo "$UV_SHA256  $work/uv.tgz" | sha256sum -c -
  tar -xzf "$work/uv.tgz" -C "$work" --strip-components=1
  install -o "$USER_NAME" -m 755 "$work/uv" "$HOME_DIR/.local/bin/uv"
fi

if ! as_user claude --version 2>/dev/null | grep -q "$CLAUDE_VERSION"; then
  as_user bash -c "curl -fsSL https://claude.ai/install.sh | bash -s $CLAUDE_VERSION"
fi

# Owned by root, so the agent can't change its own runtime.
if ! /opt/node/bin/node --version 2>/dev/null | grep -q "v$NODE_VERSION"; then
  curl -fsSL -o "$work/node.txz" "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.xz"
  echo "$NODE_SHA256  $work/node.txz" | sha256sum -c -
  mkdir -p /opt/node
  tar -xJf "$work/node.txz" -C /opt/node --strip-components=1
  chown -R root:root /opt/node
fi
for tool in node npm npx openclaw; do ln -sf "/opt/node/bin/$tool" "/usr/local/bin/$tool"; done
mkdir -p /opt/node/etc
printf 'min-release-age=7\nignore-scripts=true\nprefix=/opt/node\n' > /opt/node/etc/npmrc

if ! /opt/node/bin/node /opt/node/lib/node_modules/openclaw/openclaw.mjs --version 2>/dev/null | grep -q "$OPENCLAW_VERSION"; then
  (cd "$work" && npm install -g "openclaw@$OPENCLAW_VERSION" --allow-scripts=openclaw)
  # The first run finishes the package's own setup, which jorah can't do because the folder is read-only to it.
  openclaw --version
fi

token="$HOME_DIR/.config/jorah-voice/token"
if [ ! -s "$token" ]; then
  (umask 077; head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$token")
  chown "$USER_NAME": "$token"
fi

mkdir -p /opt/jorah
echo "Done. Next: restart the distro from Windows, then deploy the code. See docs/runbooks/jorah-on-pc.md."
