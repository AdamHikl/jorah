#!/usr/bin/env bash
# Proves gitleaks with this repo's config catches each token shape Jorah uses.
# Tokens are generated here at run time into a temp repo, so nothing token-shaped
# is ever committed. A clean file must pass, or the test proves nothing.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q

alnum() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
hex() { LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c "$1"; }
digits() { LC_ALL=C tr -dc '0-9' </dev/urandom | head -c "$1"; }

# Exit code of scanning one staged file holding $1.
scan() {
  local code=0
  printf '%s\n' "$1" >"$TMP/f.txt"
  git -C "$TMP" add f.txt
  gitleaks git --staged --config "$REPO/.gitleaks.toml" --redact --no-banner \
    --log-level error "$TMP" >/dev/null 2>&1 || code=$?
  git -C "$TMP" rm -q --cached f.txt
  return "$code"
}

failed=0
expect_caught() {
  local code=0
  scan "$2" || code=$?
  if [ "$code" -eq 1 ]; then
    echo "caught: $1"
  else
    echo "MISSED: $1 (exit $code)"
    failed=1
  fi
}

expect_caught anthropic "key = sk-ant-api03-$(alnum 93)AA"
expect_caught openai "key = sk-proj-$(alnum 58)T3BlbkFJ$(alnum 58)"
expect_caught gcp "key = AIza$(alnum 35)"
expect_caught telegram "telegram_bot_token = 1$(digits 9):AA$(alnum 33)"
expect_caught elevenlabs "key = sk_$(hex 48)"
expect_caught tailscale "key = tskey-auth-$(alnum 30)"

code=0
scan "hello world" || code=$?
if [ "$code" -eq 0 ]; then
  echo "clean file passes"
else
  echo "FALSE ALARM: clean file (exit $code)"
  failed=1
fi

exit "$failed"
