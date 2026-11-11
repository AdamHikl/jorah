#!/usr/bin/env bash
# Start, stop or check the jorah-dev scratch Gateway on 127.0.0.1:43186 for P5's tests.
# Never touches the live profile. Channels and cron stay off, so it can't answer or poll any chat.
# From the Mac:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     "wsl -d jorah -u jorah -- bash -s -- start" < scripts/pc/dev-gateway.sh
set -euo pipefail

PORT=43186
LOG=/home/jorah/.openclaw-jorah-dev/logs/dev-gateway.out
OC=(/usr/local/bin/openclaw --profile jorah-dev)

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }

pid() { ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2; }

ready() {
  local h
  for _ in $(seq 1 40); do
    h=$("${OC[@]}" health 2>&1 || true)
    if ! grep -q "still starting" <<<"$h" && grep -q "event loop" <<<"$h"; then return 0; fi
    sleep 5
  done
  return 1
}

case "${1:-status}" in
  start)
    if [ -n "$(pid)" ]; then echo "jorah-dev already running (pid $(pid))."; exit 0; fi
    mkdir -p "$(dirname "$LOG")"
    OPENCLAW_SKIP_CHANNELS=1 OPENCLAW_SKIP_CRON=1 setsid "${OC[@]}" gateway run --port "$PORT" --bind loopback \
      >"$LOG" 2>&1 </dev/null &
    if ready; then echo "jorah-dev up on 127.0.0.1:$PORT (pid $(pid))."; else echo "jorah-dev didn't become ready; see $LOG"; exit 1; fi
    ;;
  stop)
    p=$(pid)
    if [ -z "$p" ]; then echo "jorah-dev not running."; exit 0; fi
    kill "$p"
    for _ in $(seq 1 20); do [ -z "$(pid)" ] && break; sleep 1; done
    if [ -z "$(pid)" ]; then echo "jorah-dev stopped."; else echo "jorah-dev still on $PORT"; exit 1; fi
    ;;
  status)
    if [ -n "$(pid)" ]; then echo "jorah-dev running (pid $(pid))."; else echo "jorah-dev not running."; fi
    ;;
  *) echo "usage: dev-gateway.sh start|stop|status"; exit 2 ;;
esac
