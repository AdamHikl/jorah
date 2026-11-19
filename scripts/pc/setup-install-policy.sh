#!/usr/bin/env bash
# Turns on OpenClaw's security.installPolicy for live Jorah, blocking every skill or plugin install
# not on /etc/jorah/install-allowlist.json (empty today). See scripts/pc/install-policy.py and
# config/pc/install-policy.patch.json5. Run as root after /opt/jorah holds the reviewed commit:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/setup-install-policy.sh --dry-run"
#
#   --files         Installs only the policy command (/usr/local/lib/jorah/install-policy, root 755)
#                   and, if absent, the empty allowlist (/etc/jorah/install-allowlist.json, root 644).
#                   An existing allowlist is never overwritten. Touches no OpenClaw config.
#   --scratch-test  Needs --files first. A throwaway profile, policy-scratch, gets the same policy;
#                   then a linked plugin install and a local skill install must both be blocked, and
#                   `doctor --deep` runs its synthetic check. The profile is deleted afterwards.
#   --dry-run       Checks the files and validates the patch against the live config. Writes nothing.
#   (no option)     --files, then applies the patch to the live profile (hot reload, no restart).
#                   Backup: openclaw.json.pre-install-policy.
#   --undo          Sets security.installPolicy.enabled to false on the live profile. Keeps the files.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-apply}"
case "$MODE" in apply|--files|--scratch-test|--dry-run|--undo) ;; *) sed -n 2,18p "$0"; exit 2 ;; esac
SRC=/opt/jorah
LIB=/usr/local/lib/jorah
POLICY=$LIB/install-policy
ALLOW=/etc/jorah/install-allowlist.json
PATCH=$SRC/config/pc/install-policy.patch.json5
CFG=/home/jorah/.openclaw-jorah/openclaw.json
oc() { (cd / && runuser -u jorah -- /usr/local/bin/openclaw --profile "$1" "${@:2}"); }

if [ "$MODE" = --undo ]; then
  oc jorah config set security.installPolicy.enabled false
  oc jorah config get security.installPolicy.enabled
  sync
  echo "Install policy off on the live profile. $POLICY and $ALLOW stay."
  exit 0
fi

fail=0
for f in scripts/pc/install-policy.py config/pc/install-policy.patch.json5 config/security/install-allowlist.json; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done
[ "$fail" = 0 ] || exit 1

# What the policy says to a linked plugin install, run as jorah the way the Gateway runs it.
probe() {
  printf '%s' '{"protocolVersion":1,"targetType":"plugin","targetName":"jorah-probe","sourcePath":"/opt/jorah/plugins/x","source":{"kind":"local-path"},"request":{"kind":"plugin-install","mode":"install"}}' \
    | (cd / && runuser -u jorah -- "$1")
  echo
}

install_files() {
  install -d -m 755 -o root -g root "$LIB" /etc/jorah
  install -m 755 -o root -g root "$SRC/scripts/pc/install-policy.py" "$POLICY.new"
  mv "$POLICY.new" "$POLICY"
  if [ -e "$ALLOW" ]; then echo "kept the existing $ALLOW"
  else install -m 644 -o root -g root "$SRC/config/security/install-allowlist.json" "$ALLOW"; echo "wrote $ALLOW (empty)"; fi
  sync
  echo "policy says: $(probe "$POLICY")"
}

if [ "$MODE" = --dry-run ]; then
  [ -e "$POLICY" ] && echo "$POLICY exists ($(sha256sum "$POLICY" | cut -c1-12), source $(sha256sum "$SRC/scripts/pc/install-policy.py" | cut -c1-12))" \
    || echo "would: install $POLICY (root 755)"
  [ -e "$ALLOW" ] && echo "$ALLOW exists, kept" || echo "would: write $ALLOW (empty allow list, root 644)"
  echo "live security.installPolicy now: $(oc jorah config get security.installPolicy.enabled 2>&1 | tail -1)"
  oc jorah config patch --file "$PATCH" --dry-run
  echo "would: back up openclaw.json to openclaw.json.pre-install-policy and apply the patch (hot reload)"
  exit 0
fi

if [ "$MODE" = --files ]; then install_files; exit 0; fi

if [ "$MODE" = --scratch-test ]; then
  [ -x "$POLICY" ] || { echo "Run --files first."; exit 1; }
  SCRATCH=/home/jorah/.openclaw-policy-scratch
  [ -e "$SCRATCH" ] && { echo "$SCRATCH exists from an earlier run: remove it first."; exit 1; }
  SKILL=$(runuser -u jorah -- mktemp -d /home/jorah/policy-skill.XXXXXX)
  trap 'rm -rf "$SCRATCH" "$SKILL"' EXIT
  printf -- '---\nname: policy-probe\ndescription: A probe that the install policy must block.\n---\nNothing.\n' \
    | runuser -u jorah -- tee "$SKILL/SKILL.md" >/dev/null
  oc policy-scratch config patch --file "$PATCH" >/dev/null
  echo "scratch policy enabled: $(oc policy-scratch config get security.installPolicy.enabled 2>&1 | tail -1)"
  ok=1
  echo "--- linked plugin install (must be blocked)"
  if out=$(oc policy-scratch plugins install --link "$SRC/plugins/jorah-errands" --force --accept-capabilities 2>&1); then
    echo "NOT BLOCKED"; ok=0; fi
  echo "$out" | tail -4
  echo "--- local skill install (must be blocked)"
  if out=$(oc policy-scratch skills install "$SKILL" 2>&1); then echo "NOT BLOCKED"; ok=0; fi
  echo "$out" | tail -4
  echo "--- doctor --deep, install policy lines"
  oc policy-scratch doctor --deep --non-interactive 2>&1 | grep -i -A2 "install.polic" | head -12 || true
  if [ "$ok" = 1 ]; then echo "scratch test: both installs blocked"; exit 0; fi
  echo "scratch test FAILED"; exit 1
fi

install_files
case "$(probe "$POLICY")" in *'"decision": "block"'*) ;; *) echo "The policy didn't block the probe: stopping."; exit 1 ;; esac
[ -f "$CFG.pre-install-policy" ] || cp -p "$CFG" "$CFG.pre-install-policy"
oc jorah config patch --file "$PATCH"
sync
echo "live security.installPolicy.enabled: $(oc jorah config get security.installPolicy.enabled 2>&1 | tail -1)"
