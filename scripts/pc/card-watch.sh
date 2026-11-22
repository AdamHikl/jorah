#!/usr/bin/env bash
# Read-only: watch the live Gateway's pending plugin approval cards for a while and print, for each
# new card, the routing facts OpenClaw recorded (where the turn came from, who asked, the reviewers).
# It never answers a card. Titles are clipped; no other card text is printed.
# From the Mac (seconds to watch, default 180):
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     "wsl -d jorah -u jorah -- bash -s 180" < scripts/pc/card-watch.sh
set -euo pipefail
[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }
SECONDS_TO_WATCH=${1:-180}
END=$(( $(date +%s) + SECONDS_TO_WATCH ))
SEEN=$(mktemp)
trap 'rm -f "$SEEN"' EXIT
echo "watching cards for ${SECONDS_TO_WATCH}s"
while [ "$(date +%s)" -lt "$END" ]; do
  /usr/local/bin/openclaw --profile jorah gateway call plugin.approval.list --json 2>/dev/null \
    | SEEN="$SEEN" node -e '
const fs = require("fs");
const seen = new Set(fs.readFileSync(process.env.SEEN, "utf8").split("\n").filter(Boolean));
let rows = [];
try { rows = JSON.parse(fs.readFileSync(0, "utf8")); } catch { process.exit(0); }
for (const row of Array.isArray(rows) ? rows : []) {
  if (!row?.id || seen.has(row.id)) continue;
  fs.appendFileSync(process.env.SEEN, row.id + "\n");
  const r = row.request ?? {};
  const has = (v) => (v === undefined || v === null || v === "" ? "-" : "set");
  const facts = {
    at: new Date(row.createdAtMs).toISOString().slice(11, 19),
    id: String(row.id).slice(0, 12),
    title: String(r.title ?? "").slice(0, 50),
    sessionKey: r.sessionKey, agentId: r.agentId,
    turnSourceChannel: r.turnSourceChannel ?? "-", turnSourceTo: has(r.turnSourceTo),
    turnSourceAccountId: has(r.turnSourceAccountId),
    reviewerDevices: Array.isArray(r.approvalReviewerDeviceIds) ? r.approvalReviewerDeviceIds.length : "-",
    requestKeys: Object.keys(r).sort().join(","),
    rowKeys: Object.keys(row).sort().join(","),
  };
  console.log(JSON.stringify(facts));
}'
  sleep 1
done
echo "done"
