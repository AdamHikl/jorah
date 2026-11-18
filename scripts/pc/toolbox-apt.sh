#!/usr/bin/env bash
# Installs the Ubuntu packages of one toolbox request Adam already approved on a card
# (docs/runbooks/toolbox.md). The installer never has root, so a request of kind apt stops at
# "needs-root", and Adam runs this, as root, in a Terminal attached to no agent:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/toolbox-apt.sh <id>
# or on the PC, in Windows Terminal:  wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/toolbox-apt.sh <id>
#
# It reads /var/lib/jorah-toolbox/results/<id>.json (status needs-root), checks the request against
# jorah-tool-v1 again, and simulates the install: every package apt would install must come from
# Ubuntu's own archive (origin Ubuntu, noble), never from the ROS snapshot, the KiCad PPA or any
# other source. It shows the list and the sizes and asks for "yes". Then it installs with
# --no-install-recommends, records what it added in /var/lib/jorah-toolbox/apt/<name>.txt, and
# has the installer record the tool (as jorah-toolbox).
#
#   <id> --dry-run     the checks and the simulation only
#   --remove <name>    purges the packages that tool's install added (asks for "yes"), then the
#                      installer forgets the tool
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
SRC=/opt/jorah
VAR=/var/lib/jorah-toolbox
CLI=(runuser -u jorah-toolbox -- /usr/bin/python3 -I "$SRC/services/jorah-toolbox/bin/jorah-toolbox")
export DEBIAN_FRONTEND=noninteractive LC_ALL=C

installed_packages() { dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' | awk '$1 ~ /^ii/ {print $2}' | sort -u; }

if [ "${1:-}" = --remove ]; then
  name="${2:-}"
  [[ "$name" =~ ^[a-z][a-z0-9-]{1,39}$ ]] || { echo "Give the tool's name."; exit 2; }
  list="$VAR/apt/$name.txt"
  [ -f "$list" ] || { echo "No record of what $name's install added ($list)."; exit 1; }
  mapfile -t remove < <(sort -u "$list" | comm -12 - <(installed_packages))
  echo "Packages $name's install added and still installed: ${#remove[@]}"
  printf '  %s\n' "${remove[@]}"
  if [ "${#remove[@]}" -gt 0 ]; then
    mapfile -t extra < <(apt-get -s purge "${remove[@]}" | awk '$1 == "Purg" {print $2}' | sort -u | comm -23 - <(printf '%s\n' "${remove[@]}" | sort -u))
    if [ "${#extra[@]}" -gt 0 ]; then
      echo "These were not added by it but depend on it and would go too; stopping:"; printf '  %s\n' "${extra[@]}"; exit 6
    fi
    read -r -p "Type yes to purge them: " answer
    [ "$answer" = yes ] || { echo "Nothing removed."; exit 0; }
    apt-get purge -y "${remove[@]}"
  fi
  "${CLI[@]}" forget-apt "$name"
  rm -f "$list"
  sync
  echo "Removed $name."
  exit 0
fi

id="${1:-}"
DRY=0
[ "${2:-}" = --dry-run ] && DRY=1
[[ "$id" =~ ^tb-[0-9a-f]{10}$ ]] || { echo "Give the request's id (tb- and 10 hex digits), as toolbox_list shows it."; exit 2; }
result="$VAR/results/$id.json"
[ -f "$result" ] && [ ! -L "$result" ] || { echo "No result $result: has Adam approved it, and has the installer run?"; exit 1; }

# The packages, from a request that still passes the contract and is waiting for root.
mapfile -t packages < <(python3 -I - "$result" "$SRC/packages/contracts/toolbox" <<'P'
import json, sys
sys.path.insert(0, sys.argv[2])
import toolcheck
r = json.load(open(sys.argv[1]))
m = r.get("manifest") or {}
if r.get("status") != "needs-root" or m.get("kind") != "apt":
    sys.exit(f"{r.get('id')} isn't an apt request waiting for root (status {r.get('status')})")
problems = toolcheck.check(m)
if problems or toolcheck.proposal_id(m) != r.get("id"):
    sys.exit("the request no longer passes jorah-tool-v1: " + (problems[0] if problems else "its id doesn't match"))
print(m["name"])
for p in m["packages"]:
    print(p)
P
)
name="${packages[0]}"; packages=("${packages[@]:1}")
echo "Request $id: tool $name, Ubuntu packages: ${packages[*]}"

apt-get -qq update
sim="$(apt-get -s install --no-install-recommends "${packages[@]}")"
# "Inst name (version Origin:Release/suite [arch])": every one must be Ubuntu's own noble archive.
foreign="$(printf '%s\n' "$sim" | awk '$1 == "Inst" && $0 !~ /\([^ ]+ Ubuntu:24\.04\/noble(-updates|-security)?[] ,]/ {print "  " $2 " " $3 " " $4}')"
if [ -n "$foreign" ]; then
  echo "These would come from somewhere other than Ubuntu's own archive; stopping:"
  printf '%s\n' "$foreign"
  exit 5
fi
mapfile -t new < <(printf '%s\n' "$sim" | awk '$1 == "Inst" {print $2}')
echo "apt would newly install ${#new[@]} packages:"
printf '%s\n' "$sim" | awk '$1 == "Inst" {print "  " $2 " " $3}' | tr -d '(' | head -60
[ "${#new[@]}" -gt 60 ] && echo "  ... and $(( ${#new[@]} - 60 )) more"
if [ "${#new[@]}" -gt 0 ]; then
  echo "installed size: about $(apt-cache show --no-all-versions "${new[@]}" 2>/dev/null | awk '/^Installed-Size:/ {s += $2} END {printf "%.0f", s / 1024}') MB"
fi
if [ "$DRY" = 1 ]; then echo "Dry run: nothing installed."; exit 0; fi
read -r -p "Type yes to install them: " answer
[ "$answer" = yes ] || { echo "Nothing installed."; exit 0; }

before="$(mktemp)"; trap 'rm -f "$before"' EXIT
installed_packages > "$before"
apt-get install -y --no-install-recommends "${packages[@]}"
install -d -o root -g root -m 755 "$VAR/apt"
{ [ -f "$VAR/apt/$name.txt" ] && cat "$VAR/apt/$name.txt"; comm -13 "$before" <(installed_packages); } | sort -u > "$VAR/apt/$name.txt.new"
mv "$VAR/apt/$name.txt.new" "$VAR/apt/$name.txt"
chmod 644 "$VAR/apt/$name.txt"
"${CLI[@]}" record-apt "$id"
sync
echo "Installed $name. The project runner smoke-tests it at its next tick (every 15 minutes); toolbox_list shows it."
