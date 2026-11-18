#!/usr/bin/env bash
# Installs KiCad 10 for Jorah's project runs (docs/runbooks/toolbox.md, "KiCad"): kicad-cli for
# ERC, DRC, Gerbers and drill files, BOMs, netlists, PDF and SVG plots and the board as STEP, with
# KiCad's symbol and footprint libraries (not the 3D models, several GB). From KiCad's official PPA,
# a new apt source with its own signing key, so it's a build-session install on Adam's yes, never a
# toolbox card. Run as root, in a Terminal attached to no agent, after /opt/jorah holds the reviewed
# commit:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-kicad.sh --dry-run
#
# Pins in deploy/kicad/versions.env: the PPA's key fingerprint (checked before anything is trusted)
# and the exact version. /etc/apt/preferences.d/jorah-kicad holds kicad at that version and keeps
# the PPA from supplying anything else.
#
#   --dry-run          checks the key and simulates the install with throwaway apt lists in a
#                      temporary folder: the real package count and sizes. Writes nothing.
#   --undo             purges what this install newly installed (recorded in
#                      /var/lib/jorah-kicad/apt-added.txt), removes the source, key and pin. Asks
#                      for "yes" first. --undo --dry-run shows what would go.
set -euo pipefail

MODE=install
DRY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --undo) MODE=undo ;;
    -h|--help) awk 'NR > 1 && /^#/ {print; next} NR > 1 {exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 2 ;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO/deploy/kicad"
APT_SOURCE=/etc/apt/sources.list.d/jorah-kicad.sources
KEYRING=/usr/share/keyrings/jorah-kicad-ppa.gpg
PIN=/etc/apt/preferences.d/jorah-kicad
STATE=/var/lib/jorah-kicad
APT_ADDED="$STATE/apt-added.txt"
PACKAGES=(kicad kicad-symbols kicad-footprints)
export DEBIAN_FRONTEND=noninteractive LC_ALL=C

[ -f "$SRC/versions.env" ] || { echo "Missing $SRC/versions.env: is $REPO the reviewed checkout?"; exit 4; }
# shellcheck source=/dev/null
. "$SRC/versions.env"

installed_packages() { dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' | awk '$1 ~ /^ii/ {print $2}' | sort -u; }
say() { printf '== %s\n' "$*"; }

write_source() {
  cat > "$1" <<SRC
# KiCad 10 from KiCad's official PPA (scripts/pc/install-kicad.sh). Key $KICAD_PPA_KEY_FPR.
Types: deb
URIs: $KICAD_PPA_URL
Suites: noble
Components: main
Architectures: amd64
Signed-By: $2
SRC
}

write_pin() {
  cat > "$1" <<PIN
# KiCad stays at the version scripts/pc/install-kicad.sh pinned (Adam's 7-day rule), and the PPA
# supplies nothing else.
Package: *
Pin: origin ppa.launchpadcontent.net
Pin-Priority: 100

Package: kicad kicad-symbols kicad-footprints kicad-templates kicad-packages3d kicad-libraries kicad-demos kicad-doc-en
Pin: version $KICAD_VERSION
Pin-Priority: 1001
PIN
}

check_key() {
  local home fpr
  home="$(mktemp -d)"
  fpr="$(gpg --homedir "$home" --batch --with-colons --show-keys "$SRC/kicad-ppa.asc" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
  rm -rf "$home"
  [ "$fpr" = "$KICAD_PPA_KEY_FPR" ] || { echo "  Key fingerprint mismatch: file has '${fpr:-none}', pinned $KICAD_PPA_KEY_FPR. Stopping."; exit 5; }
  echo "  PPA key: $fpr (matches the pin)"
}

if [ "$MODE" = undo ]; then
  [ -f "$APT_SOURCE" ] || [ -f "$APT_ADDED" ] || { echo "Nothing to undo."; exit 0; }
  mapfile -t remove < <({ [ -f "$APT_ADDED" ] && cat "$APT_ADDED"; true; } | sort -u | comm -12 - <(installed_packages))
  say "Undo: what goes"
  echo "  $APT_SOURCE, $KEYRING, $PIN"
  echo "  apt packages this install added and still installed: ${#remove[@]}"
  extra=()
  if [ "${#remove[@]}" -gt 0 ]; then
    mapfile -t extra < <(apt-get -s purge "${remove[@]}" | awk '$1 == "Purg" {print $2}' | sort -u | comm -23 - <(printf '%s\n' "${remove[@]}" | sort -u))
    [ "${#extra[@]}" -gt 0 ] && { echo "  These weren't added by it but depend on it and would go too:"; printf '    %s\n' "${extra[@]}"; }
  fi
  if [ "$DRY" = 1 ]; then echo "Dry run: nothing removed."; exit 0; fi
  [ "${#extra[@]}" -eq 0 ] || { echo "Stopping: other packages depend on KiCad."; exit 6; }
  read -r -p "Type yes to remove all of the above: " answer
  [ "$answer" = yes ] || { echo "Nothing removed."; exit 0; }
  [ "${#remove[@]}" -gt 0 ] && apt-get purge -y "${remove[@]}"
  rm -f "$APT_SOURCE" "$KEYRING" "$PIN" "$APT_ADDED"
  apt-get -qq update || true
  sync
  echo "Undo done. Check: command -v kicad-cli finds nothing."
  exit 0
fi

say "1. Checks"
# shellcheck disable=SC1091
. /etc/os-release
[ "${VERSION_CODENAME:-}" = noble ] || { echo "  This is ${PRETTY_NAME:-unknown}; this needs Ubuntu 24.04 (noble)."; exit 4; }
[ "$(dpkg --print-architecture)" = amd64 ] || [ "${JORAH_KICAD_ANY_ARCH:-}" = 1 ] || { echo "  Needs amd64."; exit 4; }
check_key
echo "  KiCad $KICAD_VERSION: ${PACKAGES[*]} (no 3D models)"
echo "  free on /: $(df -BG --output=avail / | tail -1 | tr -d ' ')"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/parts" "$TMP/prefs" "$TMP/lists/partial" "$TMP/cache/archives/partial" "$TMP/gnupg"
chmod 700 "$TMP/gnupg"
cp /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list "$TMP/parts/" 2>/dev/null || true
if [ -f /etc/apt/sources.list ]; then cp /etc/apt/sources.list "$TMP/sources.list"; else : > "$TMP/sources.list"; fi
cp /etc/apt/preferences.d/* "$TMP/prefs/" 2>/dev/null || true
gpg --homedir "$TMP/gnupg" --batch --dearmor < "$SRC/kicad-ppa.asc" > "$TMP/kicad.gpg"
write_source "$TMP/parts/jorah-kicad.sources" "$TMP/kicad.gpg"
write_pin "$TMP/prefs/jorah-kicad"
APT_TMP=(-o "Dir::Etc::SourceList=$TMP/sources.list" -o "Dir::Etc::SourceParts=$TMP/parts" -o "Dir::Etc::PreferencesParts=$TMP/prefs"
  -o "Dir::State::Lists=$TMP/lists" -o "Dir::Cache=$TMP/cache" -o "APT::Sandbox::User=root")
say "2. apt simulation (throwaway lists)"
apt-get "${APT_TMP[@]}" -qq --error-on=any update || { echo "  apt couldn't read every source (the PPA answers 503 at times): try again in a few minutes."; exit 8; }
candidate="$(apt-cache "${APT_TMP[@]}" policy kicad | awk '/Candidate:/ {print $2}')"
echo "  kicad candidate: $candidate"
[ "$candidate" = "$KICAD_VERSION" ] || { echo "  The PPA doesn't offer kicad $KICAD_VERSION (it keeps only its latest upload). Update versions.env after checking the new release's age."; exit 7; }
sim="$(apt-get "${APT_TMP[@]}" -s install --no-install-recommends "${PACKAGES[@]}")"
mapfile -t new < <(printf '%s\n' "$sim" | awk '$1 == "Inst" {print $2}')
echo "  packages apt would newly install: ${#new[@]}"
if [ "${#new[@]}" -gt 0 ]; then
  echo "  download: about $(apt-get "${APT_TMP[@]}" -qq --print-uris install --no-install-recommends "${PACKAGES[@]}" | awk '{s += $3} END {printf "%.0f", s / 1048576}') MB;" \
       "installed size: about $(apt-cache "${APT_TMP[@]}" show --no-all-versions "${new[@]}" 2>/dev/null | awk '/^Installed-Size:/ {s += $2} END {printf "%.0f", s / 1024}') MB"
  printf '%s\n' "$sim" | awk '$1 == "Inst" && $2 ~ /^kicad/ {print "    " $2 " " $3 " " $4}' | tr -d '(['
  printf '%s\n' "$sim" | awk '$1 == "Inst" && $0 ~ /LP-PPA/ && $2 !~ /^kicad/ {print "    UNEXPECTED from the PPA: " $2}'
fi
if [ "$DRY" = 1 ]; then echo "Dry run: nothing written outside a temporary folder, which is removed."; exit 0; fi

say "3. Source, key and pin"
install -d -m 755 "$STATE"
[ -f "$STATE/.apt-before.txt" ] || installed_packages > "$STATE/.apt-before.txt"
gpg_home="$(mktemp -d)"
gpg --homedir "$gpg_home" --batch --dearmor < "$SRC/kicad-ppa.asc" > "$KEYRING.new"
rm -rf "$gpg_home"
chmod 644 "$KEYRING.new" && mv "$KEYRING.new" "$KEYRING"
write_source "$APT_SOURCE" "$KEYRING"
write_pin "$PIN"
chmod 644 "$APT_SOURCE" "$PIN"
apt-get -qq --error-on=any update || { echo "  apt couldn't read every source; nothing installed yet. Rerun in a few minutes (or --undo)."; exit 8; }

say "4. apt install"
apt-get install -y --no-install-recommends "${PACKAGES[@]}"
{ [ -f "$APT_ADDED" ] && cat "$APT_ADDED"; comm -13 "$STATE/.apt-before.txt" <(installed_packages); } | sort -u > "$APT_ADDED.new"
mv "$APT_ADDED.new" "$APT_ADDED"
echo "  newly installed by this script (kept for --undo): $(wc -l < "$APT_ADDED") packages"

say "5. Record"
{
  echo "Installed $(date -u +%Y-%m-%dT%H:%M:%SZ) by scripts/pc/install-kicad.sh from $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 'the reviewed copy')"
  for p in "${PACKAGES[@]}"; do echo "  $p $(dpkg-query -W -f='${Version}' "$p" 2>/dev/null || echo unknown)"; done
  # shellcheck disable=SC2016 # dpkg-query's own ${...} format
  echo "apt packages added: $(wc -l < "$APT_ADDED"), installed size $(xargs dpkg-query -W -f='${Installed-Size}\n' < "$APT_ADDED" | awk '{s += $1} END {printf "%.0f MB", s / 1024}')"
  echo "free on / afterwards: $(df -BG --output=avail / | tail -1 | tr -d ' ')"
} > "$STATE/INSTALLED.txt"
chmod 644 "$STATE/INSTALLED.txt"
sed 's/^/  /' "$STATE/INSTALLED.txt"
sync

say "6. As jorah: kicad-cli answers"
runuser -u jorah -- env HOME=/home/jorah kicad-cli version
echo "Done. Next: bench-smoke.sh --part kicad as jorah, then --via-claude (docs/runbooks/toolbox.md). Undo: --undo."
