#!/usr/bin/env bash
# Installs Jorah's media intake, jorah-ingestd (issue #25, ADR 0013; docs/runbooks/video-intake.md).
# Run as root, in a Terminal attached to no agent, after /opt/jorah holds the reviewed commit. The
# ssh line into the PC is in docs/runbooks/jorah-on-pc.md; from there:
#   wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-ingestd.sh --dry-run
#
# What it does:
#   1. user jorah-media (uid 1104): no login, no home, no sudo. Its unit has no network at all, so
#      the firewall doesn't change.
#   2. /srv/jorah-media (root, 755) with
#        incoming/  jorah, 755, plus an ACL giving jorah-media rwx, also as the default for new
#                   folders. Explorer writes here as jorah; the service moves the takes out.
#        spool/ proxies/ state/  jorah-media, 755: readable by jorah and the HUD, written only by
#                   the service.
#        luts/      root, 755. A LUT goes in only through --pin-lut.
#   3. /etc/jorah-media/ingest.json (root, 644) from services/jorah-ingestd/ingest.example.json,
#      unless it exists.
#   4. `jorah-ingestd check` as jorah-media. A failed check stops here, before the service.
#   5. jorah-ingestd.service: installed, verified, enabled and started.
#
#   --dry-run          checks the files, the tools and the uid, verifies the unit and tries one NVENC
#                      encode as jorah. Writes nothing.
#   --pin-lut [FILE]   copies FILE (an Apple Log to Rec.709 .cube) to the config's lut_path,
#                      root-owned, writes its SHA-256 into ingest.json and restarts the service.
#                      Without FILE it pins the LUT already at lut_path. With --dry-run, shows that.
#                      A hash that differs from the one in config/video/tools.lock stops it.
#   --undo             stops and removes the unit. /srv/jorah-media (the spool holds Adam's
#                      footage), /etc/jorah-media and the user stay; the runbook says how to remove
#                      them.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
cd /   # runuser below: a process started in /root can't read its own working folder

SRC=/opt/jorah
SVC=$SRC/services/jorah-ingestd
BIN=$SVC/bin/jorah-ingestd
ROOT=/srv/jorah-media
CONF=/etc/jorah-media/ingest.json
LOCK=$SRC/config/video/tools.lock
UNIT=jorah-ingestd.service
UIDN=1104
DRY=0; UNDO=0; PIN=0; LUT_SRC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --undo) UNDO=1 ;;
    --pin-lut)
      PIN=1
      if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then LUT_SRC=$2; shift; fi ;;
    *) echo "Unknown option: $1"; awk 'NR > 1 && /^set -euo/ { exit } NR > 1' "$0"; exit 2 ;;
  esac
  shift
done
say() { echo "$*"; }
do_() { if [ "$DRY" = 1 ]; then echo "would: $*"; else "$@"; fi; }
as_media() { runuser -u jorah-media -- /usr/bin/python3 -I "$BIN" --config "$CONF" "$@"; }

if [ "$UNDO" = 1 ]; then
  systemctl disable --now "$UNIT" 2>/dev/null || true
  rm -f "/etc/systemd/system/$UNIT"
  systemctl daemon-reload
  say "Intake off: $UNIT removed. Kept: $ROOT (the spool holds the footage), $CONF and user jorah-media."
  exit 0
fi

# ---- --pin-lut ------------------------------------------------------------------------------------
if [ "$PIN" = 1 ]; then
  [ -f "$CONF" ] || { echo "$CONF is missing: install the intake first."; exit 1; }
  LUT=$(/usr/bin/python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["lut_path"])' "$CONF")
  case "$LUT" in
    "$ROOT"/luts/*.cube) ;;
    *) echo "lut_path in $CONF is $LUT, not a .cube file under $ROOT/luts/: stopping."; exit 1 ;;
  esac
  case "$LUT" in *[[:space:]:\'\"\\]*) echo "lut_path has a space, colon, quote or backslash, which the ffmpeg filter can't take: stopping."; exit 1 ;; esac
  CHECK=${LUT_SRC:-$LUT}
  if [ ! -f "$CHECK" ] || [ -L "$CHECK" ]; then echo "$CHECK isn't a regular file (or is a link): stopping."; exit 1; fi
  [ "$(stat -c %s "$CHECK")" -le $((64 << 20)) ] || { echo "$CHECK is over 64 MB, which no .cube LUT is: stopping."; exit 1; }
  grep -qE '^[[:space:]]*LUT_3D_SIZE[[:space:]]+[0-9]+' "$CHECK" || { echo "$CHECK has no LUT_3D_SIZE line, so it isn't a 3D .cube LUT: stopping."; exit 1; }
  SHA=$(sha256sum "$CHECK" | cut -d' ' -f1)
  say "LUT: $CHECK"
  say "SHA-256: $SHA"
  LOCKED=$(awk -F'\t' '$1 == "apple-log-lut" { print $3 }' "$LOCK" 2>/dev/null || true)
  case "$LOCKED" in
    "") echo "$LOCK has no apple-log-lut line: copy the reviewed commit to $SRC first."; exit 1 ;;
    pending) say "The lock has no LUT hash yet. Record this line in config/video/tools.lock (a build session commits it):"
             printf '  apple-log-lut\t<version from the file name>\t%s\t<where it was downloaded>\t%s\tAdam\n' "$SHA" "$(date +%F)" ;;
    "$SHA") say "matches $LOCK" ;;
    *) echo "This LUT's hash differs from the one in $LOCK ($LOCKED): stopping. A new LUT needs a reviewed lock line first."; exit 1 ;;
  esac
  [ -n "$LUT_SRC" ] && do_ install -o root -g root -m 644 "$LUT_SRC" "$LUT"
  if [ "$DRY" = 1 ]; then
    say "would: set lut_sha256 in $CONF to the hash above and restart $UNIT if it runs."
    say "Dry run: nothing written."
    exit 0
  fi
  /usr/bin/python3 -I - "$CONF" "$SHA" <<'P'
import json, os, sys
path, sha = sys.argv[1], sys.argv[2]
cfg = json.load(open(path))
cfg["lut_sha256"] = sha
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
os.chmod(tmp, 0o644)
os.replace(tmp, path)
P
  sync
  systemctl try-restart "$UNIT"
  say "Pinned. Check as jorah-media:"
  as_media check || true
  exit 0
fi

# ---- checks ---------------------------------------------------------------------------------------
fail=0
need() { if ! "$@" >/dev/null 2>&1; then echo "MISSING: $*"; fail=1; fi; }
for f in services/jorah-ingestd/bin/jorah-ingestd services/jorah-ingestd/ingest.example.json \
         services/jorah-ingestd/jorah_ingestd/{__init__,cli,config,pair,probe,proxy,scan,spool,sync}.py \
         config/video/tools.lock "deploy/$UNIT"; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f (copy the reviewed commit to $SRC first)"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done
need test -x /usr/bin/python3
need test -x /usr/bin/ffmpeg
need test -x /usr/bin/ffprobe
need /usr/bin/python3 -I -c 'import numpy, zoneinfo; zoneinfo.ZoneInfo("Europe/Bratislava")'
need command -v setfacl
need command -v systemd-analyze
if have=$(id -u jorah-media 2>/dev/null); then
  [ "$have" = "$UIDN" ] || { echo "jorah-media exists with uid $have, not $UIDN: stopping."; fail=1; }
elif getent passwd "$UIDN" >/dev/null; then
  echo "uid $UIDN is taken by $(getent passwd "$UIDN" | cut -d: -f1): stopping."; fail=1
fi
if [ "$fail" = 1 ]; then
  echo "Stopping: fix the lines above first (apt-get install acl python3-numpy ffmpeg, as Adam decides)."
  exit 1
fi
say "files, tools and uid $UIDN: ok (numpy $(/usr/bin/python3 -I -c 'import numpy; print(numpy.__version__)'), $(/usr/bin/ffmpeg -hide_banner -version | head -1 | cut -d' ' -f1-3))"

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
cp "$SRC/deploy/$UNIT" "$tmp/"
systemd-analyze verify "$tmp/$UNIT" && say "systemd-analyze verify: ok"

if [ "$DRY" = 1 ]; then
  if runuser -u jorah -- /usr/bin/ffmpeg -nostdin -hide_banner -v error -f lavfi -i color=c=black:s=320x240:d=0.2 \
       -c:v h264_nvenc -f null - >"$tmp/nvenc.log" 2>&1; then
    say "NVENC test encode as jorah (outside the unit's sandbox): works"
  else
    say "NVENC test encode as jorah failed: $(tail -c 200 "$tmp/nvenc.log"). Proxies would use libx264."
  fi
  if id jorah-media >/dev/null 2>&1; then say "would keep: user jorah-media ($UIDN)"
  else say "would: useradd --system --uid $UIDN --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin jorah-media"; fi
  say "would: make $ROOT (root 755); incoming/ (jorah 755, ACL u:jorah-media:rwx and the same default);"
  say "       spool/ proxies/ state/ (jorah-media 755); luts/ (root 755)"
  if [ -f "$CONF" ]; then say "would keep: $CONF"; else say "would: install $SVC/ingest.example.json as $CONF (root 644)"; fi
  say "would: run 'jorah-ingestd check' as jorah-media; install $UNIT, daemon-reload, verify, enable --now"
  say "Dry run: nothing written."
  exit 0
fi

# ---- 1. user --------------------------------------------------------------------------------------
id jorah-media >/dev/null 2>&1 || useradd --system --uid "$UIDN" --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin jorah-media

# ---- 2. folders -----------------------------------------------------------------------------------
install -d -o root -g root -m 755 "$ROOT" "$ROOT/luts"
install -d -o jorah -g jorah -m 755 "$ROOT/incoming"
setfacl -m u:jorah-media:rwx "$ROOT/incoming"
setfacl -d -m u:jorah-media:rwx "$ROOT/incoming"
install -d -o jorah-media -g jorah-media -m 755 "$ROOT/spool" "$ROOT/proxies" "$ROOT/state"
getfacl -p "$ROOT/incoming" 2>/dev/null | grep -E "jorah-media|mask" | sed 's/^/  incoming acl: /'

# ---- 3. config ------------------------------------------------------------------------------------
install -d -o root -g root -m 755 /etc/jorah-media
[ -f "$CONF" ] || install -o root -g root -m 644 "$SVC/ingest.example.json" "$CONF"

# ---- 4. check -------------------------------------------------------------------------------------
if ! as_media check; then
  echo "The check failed (FAIL lines above): the service is not installed. Folders, user and config stay."
  exit 1
fi

# ---- 5. unit --------------------------------------------------------------------------------------
install -o root -g root -m 644 "$SRC/deploy/$UNIT" /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify "/etc/systemd/system/$UNIT"
systemctl enable --now "$UNIT"
sleep 3
systemctl is-active "$UNIT"
journalctl -u "$UNIT" -n 5 --no-pager -o cat || true
sync
say "Done. Status as jorah:"
runuser -u jorah -- /usr/bin/python3 -I "$BIN" --config "$CONF" status || true
say "Next: --pin-lut FILE for Apple Log (docs/runbooks/video-intake.md). Undo: the same command with --undo."
