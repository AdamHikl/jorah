#!/usr/bin/env bash
# Licence check. Python packages in pyproject.toml and uv.lock must be listed in
# config/licenses.tsv with an allowed licence (09 section 4.4, docs/adr/0001).
# It fails closed on anything it can't check, including any npm manifest.
set -euo pipefail

cd "$(dirname "$0")/.."

manifests="$(git ls-files -co --exclude-standard \
  | grep -E '(^|/)(package\.json|pnpm-lock\.yaml|package-lock\.json|pyproject\.toml|uv\.lock|requirements[^/]*\.txt)$' || true)"

if [ -z "$manifests" ]; then
  echo "no dependencies"
  exit 0
fi

# A package.json that declares no dependencies of any kind has nothing to check, such as the
# OpenClaw plugins in plugins/. One that declares any still fails closed below.
no_deps() {
  python3 - "$1" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
kinds = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies", "bundleDependencies", "bundledDependencies")
sys.exit(0 if not any(data.get(kind) for kind in kinds) else 1)
PY
}
unchecked_list() {
  printf '%s\n' "$manifests" | grep -vE '(^|/)(pyproject\.toml|uv\.lock)$' | while read -r manifest; do
    if [ "$(basename "$manifest")" = package.json ] && no_deps "$manifest"; then
      continue
    fi
    echo "$manifest"
  done
}
unchecked="$(unchecked_list || true)"
if [ -n "$unchecked" ]; then
  echo "Dependency manifests found, but no licence checker exists for them yet:" >&2
  printf '  %s\n' "$unchecked" >&2
  exit 1
fi

allowed=" MIT BSD-2-Clause BSD-3-Clause Apache-2.0 MPL-2.0 ISC CC0-1.0 0BSD Zlib "
# Accepted one by one in docs/adr/0001-voice-licences.md, not allowed in general.
allowed="$allowed LicenseRef-NVIDIA-Proprietary "
failed=0

# Names only: the first word of each pinned dependency, then every package in a lock file.
list_packages() {
  printf '%s\n' "$manifests" | while read -r manifest; do
    case "$manifest" in
      */pyproject.toml|pyproject.toml) sed -nE 's/^[[:space:]]*"([A-Za-z0-9._-]+)[[:space:]]*(==|@)[^"]*",?$/\1/p' "$manifest" ;;
      *) awk '/^\[\[package\]\]/{getline line; print line}' "$manifest" | sed -nE 's/^name = "([^"]+)"$/\1/p' ;;
    esac
  done
}
packages="$(list_packages | sort -u)"

for package in $packages; do
  [ "$package" = "jorah-voice" ] && continue
  licence="$(awk -F '\t' -v p="$package" '$1 == p { print $2 }' config/licenses.tsv)"
  if [ -z "$licence" ]; then
    echo "NOT LISTED in config/licenses.tsv: $package" >&2
    failed=1
    continue
  fi
  remaining="$licence"
  while [ -n "$remaining" ]; do
    part="${remaining%% AND *}"
    if [ "$part" = "$remaining" ]; then remaining=""; else remaining="${remaining#* AND }"; fi
    case "$allowed" in
      *" $part "*) ;;
      *) echo "NOT ALLOWED: $package is $part" >&2; failed=1 ;;
    esac
  done
done

[ "$failed" -eq 0 ] && echo "licences ok"
exit "$failed"
