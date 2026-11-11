#!/usr/bin/env bash
# Clear /jorah-freeze. Adam runs it at a terminal; Jorah has no way to. From the Mac:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     "wsl -d jorah -u jorah -- bash -s" < scripts/pc/guard-unfreeze.sh
# Pass a state folder to clear another profile's guard (jorah-dev uses ~/.jorah-guard-dev).
set -euo pipefail
DIR=${1:-/home/jorah/.jorah-guard}
F="$DIR/FROZEN"
if [ ! -e "$F" ]; then echo "Not frozen ($DIR)."; exit 0; fi
echo "Was: $(head -c 200 "$F")"
rm -f "$F"
echo "Unfrozen. The guard reads the flag on every call, so no restart is needed."
