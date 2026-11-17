#!/usr/bin/env bash
# Restarts the live Gateway to free the MCP stdio servers that claude-cli heartbeats leave behind.
# OpenClaw 2026.10.9 bug: each isolated heartbeat of main and deep leaves its agentmemory shim and the
# shim's anchor running (about 146 MB a pair, two pairs an hour). Neither mcp.sessionIdleTtlMs nor
# `mcp reload` retires them; a Gateway stop does. Runbook: docs/runbooks/jorah-on-pc.md, "Memory leak
# and voice warm-up, 2026-11-17". Adam chose a restart every 6 hours on 2026-11-17.
#
# Run by jorah-gateway-recycle.timer as root. It never restarts while Jorah is busy: an agent turn or
# cron run in flight (the Gateway's own status, shutdownBudget.activeWork) or a voice call (an open
# WebSocket on the voice port). An unreadable status counts as busy. It checks every 10 minutes for up
# to an hour, then skips this window. OpenClaw also drains on a requested restart and resumes
# interrupted turns, so this is the second line of care, not the only one.
#
#   (no option)  Check, restart when idle, wait until the Gateway is ready again, report.
#   --dry-run    Check once and say what it would do. Restarts nothing.
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-run}"
case "$MODE" in run|--dry-run) ;; *) sed -n 2,15p "$0"; exit 2 ;; esac

UNIT=openclaw-gateway.service
VOICE_PORT=43210
TRIES="${JORAH_RECYCLE_TRIES:-7}"
WAIT="${JORAH_RECYCLE_WAIT:-600}"
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)

leftovers() {
  echo "$(pgrep -fc service-child-group-anchor || true) MCP child groups, $(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo) MB available"
}

# Prints why Jorah is busy and returns 0, or returns 1 when idle.
busy() {
  local work
  work=$(cd /tmp && "${OC[@]}" status --json 2>/dev/null | /usr/bin/python3 -I -c '
import json, sys
try:
    work = json.load(sys.stdin)["shutdownBudget"]["activeWork"]
    busy = " ".join(f"{k}={v}" for k, v in work.items() if v)
    print(busy or "idle")
except Exception:
    print("unknown")
')
  # Anything but a clear "idle" (unreadable status, an error, nothing at all) counts as busy.
  if [ "$work" != idle ]; then echo "Gateway work: ${work:-no answer}"; return 0; fi
  if ss -Htn state established "( sport = :$VOICE_PORT )" 2>/dev/null | grep -q .; then
    echo "a voice call is open"; return 0
  fi
  return 1
}

ready() {
  local port i
  port=$(cd /tmp && "${OC[@]}" config get gateway.port 2>/dev/null | tail -1)
  [[ "$port" =~ ^[0-9]+$ ]] || port=43181
  for i in $(seq 1 60); do
    if curl -fsS -m 3 "http://127.0.0.1:$port/readyz" 2>/dev/null | grep -q '"ready":true'; then
      echo "ready after $((i * 5)) s"; return 0
    fi
    sleep 5
  done
  return 1
}

echo "before: $(leftovers)"
for try in $(seq 1 "$TRIES"); do
  if why=$(busy); then
    echo "try $try of $TRIES: busy ($why)"
    if [ "$MODE" = --dry-run ]; then echo "would wait $WAIT s and check again"; exit 0; fi
    [ "$try" -lt "$TRIES" ] && sleep "$WAIT"
    continue
  fi
  if [ "$MODE" = --dry-run ]; then echo "idle: would restart $UNIT"; exit 0; fi
  echo "try $try: idle, restarting $UNIT"
  systemctl restart "$UNIT" || { echo "restart failed"; exit 1; }
  if ! ready; then echo "Gateway not ready 5 minutes after the restart"; exit 1; fi
  sleep 30
  echo "after: $(leftovers)"
  exit 0
done
echo "busy for the whole window: skipped, next window in 6 hours"
exit 0
