#!/usr/bin/env bash
# Install and start Jorah's Qwen3-TTS voice service, then restart jorah-voice so it uses it.
# Run as root, from a Terminal attached to no agent (no inner quotes, which Windows' shell breaks):
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-qwen-voice.sh
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
SOCK=/home/jorah/.cache/jorah-voice/qwen.sock

cp /opt/jorah/deploy/jorah-voice-qwen.service /etc/systemd/system/
chmod 644 /etc/systemd/system/jorah-voice-qwen.service
systemctl daemon-reload
systemctl enable --now jorah-voice-qwen
echo "Waiting for the voice model to load (up to 3 minutes)..."
for _ in $(seq 1 60); do
  [ -S "$SOCK" ] && journalctl -u jorah-voice-qwen --since -5min --no-pager | grep -q "ready on" && break
  sleep 3
done
journalctl -u jorah-voice-qwen --since -5min --no-pager | grep -E "ready on|rror" | tail -2
systemctl restart jorah-voice
sleep 20
journalctl -u jorah-voice --since -1min --no-pager | grep -E "Speaking with|unavailable" | tail -1
