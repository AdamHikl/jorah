#!/usr/bin/env bash
# Sets the firewall's "ephemeral" port set to the range WSL chose this boot
# (net.ipv4.ip_local_port_range), so jorah's own random local ports work and no other loopback
# port opens. Run as root by jorah-firewall-ports.service after every nftables load.
set -euo pipefail
read -r low high < /proc/sys/net/ipv4/ip_local_port_range
[[ "$low" =~ ^[0-9]+$ && "$high" =~ ^[0-9]+$ && "$low" -ge 1024 && "$low" -lt "$high" ]] \
  || { echo "unexpected ip_local_port_range: $low $high"; exit 1; }
nft flush set inet jorah_out ephemeral
nft add element inet jorah_out ephemeral "{ $low-$high }"
echo "jorah firewall: own ephemeral ports $low-$high"
