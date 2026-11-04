#!/usr/bin/env bash
# Licence check. While the repo has no dependencies it says so and passes.
# It fails closed once a manifest appears, so the first issue that adds a
# dependency also has to add the real check (09 section 4.4's allowlist).
set -euo pipefail

cd "$(dirname "$0")/.."

manifests="$(git ls-files -co --exclude-standard \
  | grep -E '(^|/)(package\.json|pnpm-lock\.yaml|package-lock\.json|pyproject\.toml|uv\.lock|requirements[^/]*\.txt)$' || true)"

if [ -z "$manifests" ]; then
  echo "no dependencies"
  exit 0
fi

echo "Dependency manifests found, but no licence checker exists yet:" >&2
printf '  %s\n' "$manifests" >&2
echo "Add it per docs/plan/09-engineering-and-ops.md 4.4." >&2
exit 1
