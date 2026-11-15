#!/usr/bin/env bash
# Starts one site's signed-in Chrome (docs/runbooks/site-readers.md). Run as jorah-sites by
# jorah-site-browser@<name>.service, or by site.sh signin. Its profile lives in
# /var/lib/jorah-sites/<name> (mode 700, jorah-sites only), so no Jorah process can read its cookies.
# Every request goes through the site proxy; the firewall lets jorah-sites reach nothing else.
#   site-browser.sh <name>           headless, DevTools on 127.0.0.1:<cdpPort> for the Gateway
#   site-browser.sh <name> --signin  a visible window on the PC's screen (WSLg), for Adam to sign in
set -euo pipefail
NAME="${1:-}"
MODE="${2:-}"
[[ "$NAME" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || { echo "usage: site-browser.sh <name> [--signin]"; exit 2; }
[ "$(id -un)" = jorah-sites ] || { echo "Run this as jorah-sites."; exit 3; }
# jorah-dev's tests point a test site's browser at the test proxy (43218) and its own site folder.
SITES_DIR="${JORAH_SITES_DIR:-/opt/jorah/config/sites}"
PROXY_PORT="${JORAH_SITE_PROXY:-43219}"
[[ "$PROXY_PORT" =~ ^4321[89]$ ]] || { echo "The site proxy is on 43219 (43218 for jorah-dev's tests)."; exit 2; }
SITE=$SITES_DIR/$NAME.json
[ -f "$SITE" ] || { echo "No site file $SITE."; exit 1; }
PORT=$(python3 -I -c 'import json,sys; p=json.load(open(sys.argv[1]))["cdpPort"]; assert isinstance(p,int) and 43220<=p<=43229; print(p)' "$SITE")
DATA=/var/lib/jorah-sites/$NAME
mkdir -p "$DATA"
chmod 700 "$DATA"

ARGS=(
  --user-data-dir="$DATA"
  --proxy-server="http://127.0.0.1:$PROXY_PORT"
  --proxy-bypass-list="<-loopback>"
  --no-first-run --no-default-browser-check --disable-default-apps --disable-extensions
  --disable-background-networking --disable-component-update --disable-sync --no-pings
  "--disable-features=Translate,OptimizationHints,MediaRouter,AutofillServerCommunication,PasswordManagerOnboarding"
  --password-store=basic --metrics-recording-only
)

if [ "$MODE" = --signin ]; then
  # Adam signs in by hand, then closes the window. Don't let Chrome save the password.
  START=$(python3 -I - "$SITE" /etc/jorah/sites.private.json <<'P'
import json, sys, urllib.parse
site = json.load(open(sys.argv[1]))
host = site["host"]
if isinstance(host, dict):
    try:
        host = json.load(open(sys.argv[2]))["sites"][site["name"]]["host"]
    except (OSError, KeyError, ValueError):
        sys.exit("The site's address isn't in /etc/jorah/sites.private.json yet.")
page = site["pages"][0]
query = urllib.parse.urlencode(page.get("query", {}))
print(f"https://{host}{page['path']}" + (f"?{query}" if query else ""))
P
)
  exec /usr/bin/google-chrome-stable "${ARGS[@]}" "$START"
fi

exec /usr/bin/google-chrome-stable --headless=new \
  --remote-debugging-address=127.0.0.1 --remote-debugging-port="$PORT" \
  "${ARGS[@]}" about:blank
