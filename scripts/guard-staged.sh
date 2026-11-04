#!/usr/bin/env bash
# Pre-commit guard: refuses private files even after `git add -f`, and scripts that
# print openclaw.json (docs/plan/09-engineering-and-ops.md 4.1). Paths are read from
# stdin when given, for the test, otherwise from the staged list.
set -euo pipefail

if [ -t 0 ] || [ "${1:-}" != "--stdin" ]; then
  paths="$(git diff --cached --name-only --diff-filter=ACMR)"
else
  paths="$(cat)"
fi

failed=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    workspace/USER.md | workspace/MEMORY.md | workspace/DREAMS.md | workspace/memory/* | \
      workspace-voice/USER.md | workspace-voice/memory/* | *.sqlite | *.sqlite-*)
      echo "REFUSED, private: $path" >&2
      failed=1
      ;;
    docs/evidence/*/answers.md | docs/evidence/*/mango-*.md)
      echo "REFUSED, private answers belong in ~/.jorah-private: $path" >&2
      failed=1
      ;;
    fixtures/synthetic/*) ;;
    *.wav | *.m4a)
      echo "REFUSED, audio outside fixtures/synthetic: $path" >&2
      failed=1
      ;;
  esac
done <<<"$paths"

# Only for real staged scripts: a script must not print values from the config file.
if [ "${1:-}" != "--stdin" ]; then
  while IFS= read -r path; do
    case "$path" in
      *.sh)
        if git show ":$path" | grep -qE '\b(cat|less|more|head|tail|bat)\b[^|;&]*openclaw\.json'; then
          echo "REFUSED, prints openclaw.json: $path" >&2
          failed=1
        fi
        ;;
    esac
  done <<<"$paths"
fi

exit "$failed"
