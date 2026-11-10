#!/usr/bin/env bash
# Installs the firewall that follows WSL's per-boot port range. Adam runs it as root, in a
# Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-firewall-ports.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
before="$(nft list chain inet jorah_out output 2>/dev/null | grep 'oifname "loopback0" counter' | grep -oE 'packets [0-9]+' || true)"
cp /opt/jorah/deploy/jorah-firewall.nft /etc/nftables.conf
cp /opt/jorah/deploy/jorah-firewall-ports.service /etc/systemd/system/
chmod 644 /etc/systemd/system/jorah-firewall-ports.service
systemctl daemon-reload
nft -f /etc/nftables.conf
systemctl enable --now jorah-firewall-ports.service
systemctl restart jorah-firewall-ports.service
echo "  live range: $(cat /proc/sys/net/ipv4/ip_local_port_range | tr '\t' '-')"
echo "  firewall set: $(nft list set inet jorah_out ephemeral | grep -oE 'elements = \{[^}]*\}')"
echo "  loopback rejects before reload: ${before:-unknown} (the counter restarts at 0 now)"
systemctl is-enabled jorah-firewall-ports.service
