#!/usr/bin/env bash
# P5.4, jorah-dev only: a second agentmemory with its own home, data and secret, on loopback
# 43192 (REST), 43194 (viewer) and 43196 (engine), inside the firewall's 43181-43199 range.
# It never touches the live one on 47300. The engine binary is a copy of the live, pinned one.
#   ssh ... "wsl -d jorah -u jorah -- bash -s -- start|stop|status" < scripts/pc/p5-dev-agentmemory.sh
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
H=/home/jorah/scratch-dev/am-home
BIN=/home/jorah/apps/agentmemory/node_modules/.bin
run() { env -i HOME="$H" PATH="$BIN:/usr/local/bin:/usr/bin:/bin" "$BIN/agentmemory" "$@"; }
up() { ss -ltn 2>/dev/null | grep -q '127.0.0.1:43192 '; }

case "${1:-status}" in
  start)
    if up; then echo "dev agentmemory already up on 43192."; exit 0; fi
    mkdir -p "$H/.agentmemory/bin"; chmod 700 "$H" "$H/.agentmemory"
    [ -x "$H/.agentmemory/bin/iii" ] || cp -p /home/jorah/.agentmemory/bin/iii "$H/.agentmemory/bin/iii"
    cmp -s /home/jorah/.agentmemory/bin/iii "$H/.agentmemory/bin/iii" || { echo "engine binary differs from live"; exit 1; }
    [ -f "$H/.agentmemory/preferences.json" ] || cp -p /home/jorah/.agentmemory/preferences.json "$H/.agentmemory/"
    printf '%s\n' III_REST_PORT=43192 III_VIEWER_PORT=43194 III_ENGINE_PORT=43196 EMBEDDING_PROVIDER=local OTEL_ENABLED=false \
      > "$H/.agentmemory/.env"
    chmod 600 "$H/.agentmemory/.env"
    ( cd "$H" && run >"$H/start.log" 2>&1 ) || { echo "start failed; see $H/start.log"; exit 1; }
    for _ in $(seq 1 60); do up && break; sleep 5; done
    if up; then echo "dev agentmemory up on 127.0.0.1:43192."; else echo "not up; see $H/start.log"; exit 1; fi
    ;;
  stop) ( cd "$H" && run stop ) | tail -1 ;;
  status) if up; then echo "dev agentmemory up on 43192."; else echo "dev agentmemory down."; fi ;;
  *) echo "usage: start|stop|status"; exit 2 ;;
esac
