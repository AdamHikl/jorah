#!/bin/bash
# Issue 12's Mac-side session tests (docs/runbooks/ios-test-pass.md, part B). Run in jorah-build's
# Terminal after docs/runbooks/ios-builds.md sections 1 to 5 are done:
#   bash ~/ios-test-pass.sh            (copy it there first; it changes nothing)
# Reads no key and prints no secret. It sends one unsigned request to the runner and runs the
# runner's own `call` verb with arguments that must be refused, so nothing is built or installed.
# Each line is PASS, FAIL or SKIP with the reason. Exit 0 only if nothing failed.
set -uo pipefail

RUNNER="${RUNNER:-/usr/local/libexec/jorah/ios-runner/bin/jorah-ios-runner}"
export JORAH_IOS_RUNNER_CONFIG="${JORAH_IOS_RUNNER_CONFIG:-/Library/Application Support/Jorah/ios-projects.json}"
URL="http://127.0.0.1:47820"
fails=0

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
skip() { echo "SKIP $1"; }

# The error code of a runner reply on stdin, or "none".
code_of() {
  /usr/bin/python3 -I -c 'import json, sys
try:
    r = json.load(sys.stdin)
except Exception:
    print("unreadable"); sys.exit()
print((r.get("error") or {}).get("code") or ("ok" if r.get("ok") else "none"))'
}

expect_code() { # name, wanted code, verb, json
  local got
  got="$(/usr/bin/python3 -I "$RUNNER" call "$3" "$4" 2>/dev/null | code_of)"
  if [ "$got" = "$2" ]; then pass "$1 ($got)"; else fail "$1 (wanted $2, got $got)"; fi
}

echo "jorah iOS test pass, Mac side, $(/bin/date -u +%Y-%m-%dT%H:%M:%SZ), user $(/usr/bin/id -un)"
[ "$(/usr/bin/id -un)" = "jorah-build" ] || fail "run as jorah-build (this is $(/usr/bin/id -un))"
[ -x "$RUNNER" ] || [ -f "$RUNNER" ] || fail "runner not found at $RUNNER"
[ -r "$JORAH_IOS_RUNNER_CONFIG" ] || fail "allowlist not readable at $JORAH_IOS_RUNNER_CONFIG"
if [ -w "$JORAH_IOS_RUNNER_CONFIG" ]; then fail "the allowlist is writable by jorah-build (contract 6)"; else pass "allowlist not writable by jorah-build"; fi

# 1. The service answers health, and only on loopback.
health="$(/usr/bin/curl -s -m 5 "$URL/v1/health" || true)"
case "$health" in
  *'"jorah-ios/1"'*) pass "runner health on 127.0.0.1:47820 speaks jorah-ios/1" ;;
  *) fail "runner health on 127.0.0.1:47820 (got: ${health:-no answer})" ;;
esac
listeners="$(/usr/sbin/lsof -nP -iTCP:47820 -sTCP:LISTEN 2>/dev/null | /usr/bin/awk 'NR>1 {print $9}' | /usr/bin/sort -u | /usr/bin/tr '\n' ' ')"
case "$listeners" in
  "127.0.0.1:47820 ") pass "runner listens on 127.0.0.1 only" ;;
  "") skip "listener not visible to lsof as this user (Serve's forward may be the only one shown to admins)" ;;
  *) fail "runner listens on: $listeners (wanted 127.0.0.1:47820 only)" ;;
esac

# 2. An unsigned request is refused with 401 and no detail.
status="$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' -m 5 -X POST -H 'Content-Type: application/json' -d '{}' "$URL/v1/devices" || true)"
if [ "$status" = "401" ]; then pass "unsigned request refused (401)"; else fail "unsigned request (wanted 401, got ${status:-no answer})"; fi

# 3. Off-allowlist project refused by the runner itself (the plugin refuses first; this is the second layer).
expect_code "off-allowlist project refused" PROJECT_NOT_ALLOWED build-sim '{"project":"not-on-the-list","commit":"0000000000000000000000000000000000000000","configuration":"Debug"}'

# 4. Injected arguments refused: a shell string in a ref, an extra flag field, a branch where a commit goes,
#    a path in a screenshot request, an unknown verb.
expect_code "shell string in ref refused" BAD_ARGUMENT sync '{"project":"threadfolio","ref":"main; touch /tmp/jorah-pwned"}'
expect_code "option-looking ref refused" BAD_ARGUMENT sync '{"project":"threadfolio","ref":"--upload-pack=touch"}'
expect_code "extra field refused" BAD_ARGUMENT build-sim '{"project":"threadfolio","commit":"0000000000000000000000000000000000000000","configuration":"Debug","flags":["-allowProvisioningUpdates"]}'
expect_code "branch name where a commit goes refused" BAD_ARGUMENT build-device '{"project":"threadfolio","commit":"main","configuration":"Debug"}'
expect_code "path in a screenshot request refused" BAD_ARGUMENT sim-screenshot '{"project":"threadfolio","simulator":{"name":"iPhone 17","os":"27.0"},"path":"/etc/passwd"}'
expect_code "unknown verb refused" BAD_ARGUMENT exec '{"cmd":"id"}'
if [ -e /tmp/jorah-pwned ]; then fail "/tmp/jorah-pwned exists: something ran the injected string"; else pass "no injected command ran"; fi

# 5. Signing: Development only, no distribution certificate in this keychain (waiver condition 3).
idents="$(/usr/bin/security find-identity -v -p codesigning 2>/dev/null || true)"
dev="$(printf '%s\n' "$idents" | /usr/bin/grep -c '"Apple Development' || true)"
dist="$(printf '%s\n' "$idents" | /usr/bin/grep -Eic 'Distribution|Developer ID' || true)"
if [ "$dist" = "0" ]; then pass "no distribution or Developer ID identity in jorah-build's keychain"; else fail "$dist distribution or Developer ID identities in jorah-build's keychain"; fi
if [ "$dev" -ge 1 ]; then pass "$dev Apple Development identity found"; else fail "no Apple Development identity (ios-builds.md 3.2)"; fi

# 6. TOPO-S6: the three tools run as jorah-build. Results by evidence tier: this proves they start.
if v="$(/usr/bin/xcodebuild -version 2>/dev/null | /usr/bin/head -1)"; [ -n "$v" ]; then pass "TOPO-S6 xcodebuild: $v"; else fail "TOPO-S6 xcodebuild did not run"; fi
if n="$(/usr/bin/xcrun simctl list devices available 2>/dev/null | /usr/bin/grep -c '(' )"; [ "$n" -gt 0 ]; then pass "TOPO-S6 simctl: $n available simulators"; else fail "TOPO-S6 simctl listed nothing"; fi
if out="$(/usr/bin/xcrun devicectl list devices 2>&1)"; then
  pass "TOPO-S6 devicectl runs ($(printf '%s\n' "$out" | /usr/bin/grep -ci 'available' || true) available devices)"
else
  fail "TOPO-S6 devicectl failed: $(printf '%s\n' "$out" | /usr/bin/tail -1)"
fi

# 7. SEC-T15, Mac side under route 2: no OpenClaw node runs as jorah-build.
if /usr/bin/pgrep -u "$(/usr/bin/id -u)" -f 'openclaw.*node' >/dev/null 2>&1; then fail "an OpenClaw node process runs as jorah-build"; else pass "no OpenClaw node process as jorah-build"; fi
if [ -e "$HOME/.openclaw" ]; then fail "$HOME/.openclaw exists: something set up OpenClaw for jorah-build"; else pass "no ~/.openclaw for jorah-build"; fi

echo "Result: $fails failed."
[ "$fails" = 0 ]
