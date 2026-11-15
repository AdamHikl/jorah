#!/usr/bin/env bash
# Adds, signs in, checks and removes Adam's signed-in sites (docs/runbooks/site-readers.md). Run as
# root in a Terminal attached to no agent, after install-site-readers.sh, from the Mac:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/site.sh status
#
#   site.sh status                    every site: file ok, address set, browser running, signed in?
#   site.sh set-host <name> <host>    put a private address (a school's) in /etc/jorah/sites.private.json
#   site.sh add <name> [--dry-run]    the site's browser profile in OpenClaw and its browser service
#   site.sh signin <name>             a visible window on the PC's screen; sign in, then close it
#   site.sh remove <name> [--wipe]    stop it and drop the profile; --wipe also deletes its sign-in
# The site file itself (config/sites/<name>.json) comes with a reviewed commit, like any code.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
SRC=/opt/jorah
PRIV=/etc/jorah/sites.private.json
CMD="${1:-status}"
NAME="${2:-}"

need_name() {
  [[ "$NAME" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || { echo "Give a site name: lower-case letters, digits and dashes."; exit 2; }
  [ -f "$SRC/config/sites/$NAME.json" ] || { echo "No $SRC/config/sites/$NAME.json: the site file comes with a reviewed commit."; exit 1; }
}

# The site as the guard sees it, from the same code (plugins/jorah-guard/lib/sites.js).
site_json() {
  node --input-type=module -e '
    const { loadSites, profileOf } = await import(process.argv[1]);
    const { sites, errors } = loadSites({ dir: process.argv[2], privateFile: process.argv[3] });
    const s = sites.get(process.argv[4]);
    const out = s ? { name: s.name, title: s.title, enabled: s.enabled, why: s.disabledReason, port: s.cdpPort, profile: profileOf(s.name) } : null;
    console.log(JSON.stringify({ site: out, errors }));
  ' "$SRC/plugins/jorah-guard/lib/sites.js" "$SRC/config/sites" "$PRIV" "$1"
}
field() {
  python3 -I -c '
import json, sys
v = json.loads(sys.argv[1])
for k in sys.argv[2:]:
    v = v.get(k) if isinstance(v, dict) else None
print("" if v is None else json.dumps(v) if isinstance(v, (list, dict)) else v)' "$@"
}

case "$CMD" in
  status)
    for f in "$SRC"/config/sites/*.json; do
      n=$(basename "$f" .json); [[ "$n" == _* ]] && continue
      j=$(site_json "$n")
      unit="jorah-site-browser@$n"
      printf '%-12s %-9s %-9s %s\n' "$n" \
        "$( [ "$(field "$j" site enabled)" = True ] && echo address || echo no-addr)" \
        "$(systemctl is-active "$unit" 2>/dev/null || true)" \
        "$(field "$j" site why)"
    done
    j=$(site_json _none_); errs=$(field "$j" errors)
    [ "$errs" = "[]" ] || echo "Site file problems: $errs"
    systemctl is-active jorah-site-proxy >/dev/null && echo "proxy: running" || echo "proxy: NOT running"
    ;;

  set-host)
    need_name
    HOST="${3:-}"
    [[ "$HOST" =~ ^[a-z0-9.-]{3,253}$ ]] || { echo "usage: site.sh set-host <name> <host>"; exit 2; }
    cp -p "$PRIV" "$PRIV.bak"
    python3 -I - "$PRIV" "$NAME" "$HOST" <<'P'
import json, sys
path, name, host = sys.argv[1:]
data = json.load(open(path))
data.setdefault("sites", {}).setdefault(name, {})["host"] = host
open(path, "w").write(json.dumps(data, indent=2) + "\n")
P
    j=$(site_json "$NAME")
    if [ "$(field "$j" site enabled)" != True ]; then
      cp -p "$PRIV.bak" "$PRIV"
      echo "Refused: $(field "$j" site why). Nothing changed."; exit 1
    fi
    echo "$NAME's address is set (private file only). Next: site.sh add $NAME"
    ;;

  add)
    need_name
    j=$(site_json "$NAME")
    [ "$(field "$j" site enabled)" = True ] || { echo "Not ready: $(field "$j" site why)"; exit 1; }
    PORT=$(field "$j" site port); PROFILE=$(field "$j" site profile)
    TMP=$(mktemp /tmp/site-profile.XXXXXX.json5); trap 'rm -f "$TMP"' EXIT
    printf '{ browser: { profiles: { "%s": { cdpUrl: "http://127.0.0.1:%s", attachOnly: true } } } }\n' "$PROFILE" "$PORT" > "$TMP"
    chmod 644 "$TMP"
    "${OC[@]}" config patch --file "$TMP" --dry-run
    [ "${3:-}" = --dry-run ] && { echo "Dry run only: would add $PROFILE and start jorah-site-browser@$NAME."; exit 0; }
    "${OC[@]}" config patch --file "$TMP"
    systemctl enable --now "jorah-site-browser@$NAME"
    sleep 2
    systemctl is-active "jorah-site-browser@$NAME"
    curl -s --max-time 3 "http://127.0.0.1:$PORT/json/version" | python3 -I -c 'import json,sys; print("DevTools answers:", json.load(sys.stdin).get("Browser","?"))' \
      || echo "DevTools didn't answer on $PORT yet; check: journalctl -u jorah-site-browser@$NAME"
    echo "Added. If it isn't signed in yet: site.sh signin $NAME"
    ;;

  signin)
    need_name
    j=$(site_json "$NAME")
    [ "$(field "$j" site enabled)" = True ] || { echo "Not ready: $(field "$j" site why)"; exit 1; }
    echo "Opening $NAME on the PC's screen. Sign in there yourself, don't let Chrome save the password, then close the window."
    systemctl stop "jorah-site-browser@$NAME" 2>/dev/null || true
    runuser -u jorah-sites -- env DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir \
      bash "$SRC/scripts/pc/site-browser.sh" "$NAME" --signin || true
    systemctl start "jorah-site-browser@$NAME"
    echo "Back to the headless browser. Check it from Telegram: \"what's on my $NAME today?\""
    ;;

  remove)
    need_name
    j=$(site_json "$NAME"); PROFILE=$(field "$j" site profile)
    systemctl disable --now "jorah-site-browser@$NAME" 2>/dev/null || true
    TMP=$(mktemp /tmp/site-profile.XXXXXX.json5); trap 'rm -f "$TMP"' EXIT
    printf '{ browser: { profiles: { "%s": null } } }\n' "${PROFILE:-site-$NAME}" > "$TMP"; chmod 644 "$TMP"
    "${OC[@]}" config patch --file "$TMP" || true
    if [ "${3:-}" = --wipe ]; then rm -rf "/var/lib/jorah-sites/$NAME"; echo "Sign-in deleted."; fi
    echo "Removed $NAME's browser and profile. Its site file and private entry stay until you remove them."
    ;;

  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
