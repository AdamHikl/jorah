#!/usr/bin/env bash
# Licence check. Python packages in pyproject.toml, uv.lock and pinned requirements*.txt files must
# be listed in config/licenses.tsv with an allowed licence (09 section 4.4, docs/adr/0001, 0003).
# It fails closed on anything it can't check, including any npm manifest and any requirements line
# other than `name==version`, `--hash=sha256:...`, comments and blanks.
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
# Names from a hash-pinned requirements file. Exits 1, naming the line, on anything else
# (ranges, -r/-e/-c includes, URLs, extras, markers), so such a file stays unchecked.
requirements_names() {
  awk '
    /^[[:space:]]*(#.*)?$/ { next }
    /^[A-Za-z0-9][A-Za-z0-9._-]*==[^[:space:]\\;@]+([[:space:]]+\\)?[[:space:]]*$/ { split($0, a, "=="); print a[1]; next }
    /^[[:space:]]+--hash=sha256:[0-9a-f]+([[:space:]]+\\)?[[:space:]]*$/ { next }
    { bad = 1; print "  can'"'"'t parse " FILENAME ":" NR > "/dev/stderr" }
    END { exit bad }' "$1"
}
unchecked_list() {
  printf '%s\n' "$manifests" | grep -vE '(^|/)(pyproject\.toml|uv\.lock)$' | while read -r manifest; do
    if [ "$(basename "$manifest")" = package.json ] && no_deps "$manifest"; then
      continue
    fi
    case "$(basename "$manifest")" in
      requirements*.txt) if requirements_names "$manifest" >/dev/null; then continue; fi ;;
    esac
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
# Accepted in docs/adr/0003-robotics-bench-licences.md, and only for packages pinned in the robotics
# bench's own lock files (tools installed on the PC, never imported by Jorah's code) that no other
# manifest uses. The same package in any other manifest must have an allowed licence.
bench_allowed=" LGPL-2.0-or-later PSF-2.0 Unlicense MIT-CMU LGPL-2.1-only WITH OCCT-exception-1.0 "
failed=0

# Names only: the first word of each pinned dependency, then every package in a lock file.
list_packages() {
  while read -r manifest; do
    case "$manifest" in
      */requirements*.txt|requirements*.txt) requirements_names "$manifest" ;;
      */pyproject.toml|pyproject.toml) sed -nE 's/^[[:space:]]*"([A-Za-z0-9._-]+)[[:space:]]*(==|@)[^"]*",?$/\1/p' "$manifest" ;;
      *) awk '/^\[\[package\]\]/{getline line; print line}' "$manifest" | sed -nE 's/^name = "([^"]+)"$/\1/p' ;;
    esac
  done
}
packages="$(printf '%s\n' "$manifests" | list_packages | sort -u)"
bench_only=" $(printf '%s\n' "$manifests" | grep -E '^deploy/jorah-bench/' | list_packages | sort -u | tr '\n' ' ') "
for other in $(printf '%s\n' "$manifests" | grep -vE '^deploy/jorah-bench/' | list_packages | sort -u); do
  bench_only="${bench_only/ $other / }"
done

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
      *" $part "*) continue ;;
    esac
    case "$bench_only" in
      *" $package "*) case "$bench_allowed" in *" $part "*) continue ;; esac ;;
    esac
    echo "NOT ALLOWED: $package is $part" >&2; failed=1
  done
done

[ "$failed" -eq 0 ] && echo "licences ok"
exit "$failed"
