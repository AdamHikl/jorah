#!/usr/bin/env bash
# Checks that Jorah can learn on the Claude CLI login. Changes nothing by default.
# Safe to re-run.
#
# Background reviews do not run on the CLI runtime, so learning comes from two places:
#   1. The rules in workspace/AGENTS.md ("Learning and Automating"), which need no setup.
#   2. An optional daily review of recent sessions, created only with --create-review-job.
#      That is a new schedule, so run it only after Adam says yes.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT="$REPO/config/learning-review.prompt.md"
JOB_NAME="Learning review"
JOB_CRON="30 8 * * *" # After Dreaming (03:00) and outside quiet hours (23:00-08:00)
JOB_MODEL="anthropic/claude-sonnet-5-5"
JOB_TOOLS="sessions_list,sessions_history,sessions_search,memory_search,memory_get,skill_workshop"

oc() { openclaw --profile jorah "$@"; }

case "${1:-}" in
  "") create_job=0 ;;
  --create-review-job) create_job=1 ;;
  *) echo "Usage: $0 [--create-review-job]" >&2; exit 2 ;;
esac

# `workshop list` reports the effective mode, including the default when it is unset.
if ! oc skills workshop list 2>/dev/null | grep -q "Mode: auto"; then
  echo "Warning: skills.workshop.autonomous.mode is off. skill_workshop still works, but unused-skill cleanup and any future background review will not run." >&2
fi

# A tools policy can hide skill_workshop. The coding profile, which is the default, allows it.
doctor_lines="$(oc doctor </dev/null 2>/dev/null | grep "skill_workshop" || true)"
if [ -n "$doctor_lines" ]; then
  echo "Warning: doctor reports a problem with skill_workshop:" >&2
  echo "$doctor_lines" >&2
fi

grep -q '^## Learning and Automating' "$REPO/workspace/AGENTS.md" \
  || { echo "workspace/AGENTS.md has no Learning and Automating section." >&2; exit 1; }

if oc cron list --all 2>/dev/null | grep -q "$JOB_NAME"; then
  echo "Review job: exists."
  exit 0
fi

if [ "$create_job" -eq 0 ]; then
  echo "Review job: not created. It needs Adam's yes, then: $0 --create-review-job"
  exit 0
fi

# Same owner the gateway already trusts. The value is telegram:<chat id>.
owner="$(oc config get commands.ownerAllowFrom --json 2>/dev/null | grep -o 'telegram:[0-9]*' | head -1 || true)"
[ -n "$owner" ] || { echo "No telegram owner in commands.ownerAllowFrom." >&2; exit 1; }

oc cron add \
  --name "$JOB_NAME" \
  --declaration-key "jorah:learning-review" \
  --description "Saves corrections Jorah missed as learned skills, and proposes repeated work" \
  --agent main \
  --cron "$JOB_CRON" \
  --session isolated \
  --model "$JOB_MODEL" \
  --tools "$JOB_TOOLS" \
  --timeout-seconds 600 \
  --announce --channel telegram --to "${owner#telegram:}" \
  --message "$(cat "$PROMPT")"

echo "Created. Run it once now with: openclaw --profile jorah cron run <id> (ids: openclaw --profile jorah cron list)"
