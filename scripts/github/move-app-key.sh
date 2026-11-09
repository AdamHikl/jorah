#!/usr/bin/env bash
# Moves the jorah-bot GitHub App's private key from the Mac to the PC, then deletes it here.
# Adam runs it in a Terminal attached to no agent, with the key's path, or with none to look in
# Downloads and the repo's docs folder:
#   ~/Documents/jorah/scripts/github/move-app-key.sh [path/to/jorah-bot....private-key.pem]
# The key goes over SSH on stdin, straight into a mode-600 file only Jorah's Gateway user can read.
set -euo pipefail
shopt -s nullglob
if [ -n "${1:-}" ]; then
  keys=( "$1" )
else
  keys=( "$HOME"/Downloads/jorah-bot*.private-key.pem "$HOME"/Documents/jorah/docs/jorah-bot*.private-key.pem )
fi
if [ "${#keys[@]}" -ne 1 ] || [ ! -f "${keys[0]}" ]; then
  echo "Expected exactly one jorah-bot*.private-key.pem, found ${#keys[@]}. Pass its path."; exit 2
fi
key="${keys[0]}"
echo "Moving $(basename "$key") to the PC..."
ssh -i "$HOME/.ssh/jorah-pc-setup" -o IdentitiesOnly=yes adamh@100.115.240.14 \
  wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/store-app-key.sh < "$key"
rm -f "$key"
echo "Deleted the Mac copy. If it's in the Bin, empty it."
echo "Compare: the fingerprint above should match the one on the App's page under Private keys."
