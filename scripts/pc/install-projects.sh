#!/usr/bin/env bash
# Installs Jorah's project runner on live Jorah (docs/plan/11-project-mode.md, sections 4 and 12).
# Run as root, in a Terminal attached to no agent, after /opt/jorah holds the reviewed commit and
# scripts/pc/setup-project-permissions.sh has run as jorah:
#   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-projects.sh --dry-run
#
#   (no option)  Checks the parts, makes the runner's folders, writes runner.json (the GitHub App's
#                id, read from the jorah-github plugin's config, and the owner), writes an empty
#                registry if there is none (Jorah adds projects himself with project_start, plan
#                section 5.1; projects.example.json is only an example), installs the three
#                units, enables the path unit, and enables the timer. The timer is a schedule, so
#                this needs Adam's yes. Nothing runs until Adam asks for a run.
#   --dry-run    Checks everything and prints what it would do. Writes nothing.
#   --undo       Stops and disables the units and removes them from /etc/systemd/system. Keeps
#                the registry, runner.json, run records, the work folders and the line.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 3; }
MODE="${1:-install}"
case "$MODE" in install|--dry-run|--undo) ;; *) sed -n 2,17p "$0"; exit 2 ;; esac

SRC=/opt/jorah
UNITS=(jorah-projects.service jorah-projects.timer jorah-projects.path)
JH=/home/jorah
CLAUDE=/opt/jorah-tools/claude-code/2.1.300/claude
REGISTRY="$JH/.config/jorah-projects/projects.json"
RUNNER_JSON="$JH/.config/jorah-projects/runner.json"
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
DRY=0; [ "$MODE" = --dry-run ] && DRY=1
say() { echo "$*"; }
do_() { if [ "$DRY" = 1 ]; then echo "would: $*"; else "$@"; fi; }

if [ "$MODE" = --undo ]; then
  for u in jorah-projects.timer jorah-projects.path jorah-projects.service; do
    systemctl disable --now "$u" 2>/dev/null || true
    rm -f "/etc/systemd/system/$u"
  done
  systemctl daemon-reload
  say "Removed the runner's units. Kept: $REGISTRY, $RUNNER_JSON, $JH/.jorah-projects and the work folders."
  exit 0
fi

fail=0
need() { if ! "$@" >/dev/null 2>&1; then echo "MISSING: $*"; fail=1; fi; }

# 1. The reviewed code, root-owned.
for f in services/jorah-projects/bin/jorah-projects services/jorah-projects/brief.md services/jorah-projects/gitleaks.toml \
         services/jorah-projects/jorah_projects/runner.py plugins/jorah-github/bin/jorah-github-sync.mjs \
         packages/contracts/project/backlog.schema.json packages/contracts/project/questions.schema.json \
         packages/contracts/project/adam-tasks.schema.json packages/contracts/project/project-config.schema.json \
         "${UNITS[@]/#/deploy/}"; do
  if [ ! -f "$SRC/$f" ]; then echo "MISSING: $SRC/$f (copy the reviewed commit to $SRC first)"; fail=1
  elif [ "$(stat -c %U "$SRC/$f")" != root ]; then echo "NOT ROOT-OWNED: $SRC/$f"; fail=1; fi
done

# 2. What a run needs.
need test -x "$CLAUDE"
need test -x /usr/local/bin/node
need test -x /usr/bin/git
need test -x /usr/local/bin/gitleaks
need runuser -u jorah -- /usr/bin/python3 -I -c 'import yaml, zoneinfo; zoneinfo.ZoneInfo("Europe/Bratislava")'
need command -v bwrap
need command -v socat
need test -f "$JH/.claude-jorah/project-settings.json"
need test -f "$JH/.claude-jorah/project-settings-web.json"
need test -f "$JH/.claude-jorah/project-settings-setup.json"
need test -f "$JH/.claude-jorah/project-settings-setup-web.json"
need test -f "$JH/.config/jorah-github/app.pem"
need test -d "$JH/.jorah-guard"
if [ "$fail" = 1 ]; then
  echo "Stopped: fix the lines above first. (PyYAML: apt install python3-yaml. Settings: setup-project-permissions.sh as jorah.)"
  exit 1
fi
say "Parts present: Claude Code $("$CLAUDE" --version 2>/dev/null | head -1), node $(/usr/local/bin/node --version), $(/usr/local/bin/gitleaks version 2>/dev/null | head -1 | sed 's/^/gitleaks /')."

# 3. The App id from the plugin's config (not a secret), and the owner.
APP_ID="$("${OC[@]}" config get plugins.entries.jorah-github.config.appId 2>/dev/null | tr -d '"[:space:]' || true)"
OWNER="$("${OC[@]}" config get plugins.entries.jorah-github.config.owner 2>/dev/null | tr -d '"[:space:]' || true)"
[[ "$APP_ID" =~ ^[0-9]+$ ]] || { echo "Couldn't read jorah-github's appId from the config."; exit 1; }
[[ "$OWNER" =~ ^[A-Za-z0-9-]+$ ]] || { echo "Couldn't read jorah-github's owner from the config."; exit 1; }
say "GitHub: App $APP_ID, owner $OWNER."

# 4. Folders and files, as jorah, private.
for d in "$JH/.jorah-projects" "$JH/.config/jorah-projects" "$JH/work" "$JH/sandbox" "$JH/.jorah-github"; do
  if [ ! -d "$d" ]; then do_ install -d -o jorah -g jorah -m 700 "$d"; fi
done
RUNNER_TEXT="{\"githubAppId\": \"$APP_ID\", \"githubOwner\": \"$OWNER\", \"timezone\": \"Europe/Bratislava\"}"
if [ "$DRY" = 1 ]; then
  say "would write $RUNNER_JSON (mode 600): $RUNNER_TEXT"
else
  # shellcheck disable=SC2016 # $1 expands in the inner shell, on purpose
  runuser -u jorah -- /bin/sh -c 'umask 077; cat > "$1"' sh "$RUNNER_JSON" <<<"$RUNNER_TEXT"
fi
if [ -f "$REGISTRY" ]; then
  say "Registry kept as it is: $REGISTRY"
elif [ "$DRY" = 1 ]; then
  say "would write an empty registry $REGISTRY (mode 600): Jorah adds projects with project_start"
else
  # shellcheck disable=SC2016 # $1 expands in the inner shell, on purpose
  runuser -u jorah -- /bin/sh -c 'umask 077; printf "{}\n" > "$1"' sh "$REGISTRY"
  say "Registry written, empty: Jorah adds projects with project_start (plan 11, section 5.1)."
fi

# 5. The runner's own check of the registry and schemas, read only.
if [ "$DRY" = 0 ] || [ -f "$REGISTRY" ]; then
  runuser -u jorah -- /usr/bin/python3 -I "$SRC/services/jorah-projects/bin/jorah-projects" status || { echo "The runner's status check failed."; exit 1; }
fi

# 6. Units.
for u in "${UNITS[@]}"; do
  if [ "$DRY" = 1 ]; then
    say "would install /etc/systemd/system/$u"
    cmp -s "$SRC/deploy/$u" "/etc/systemd/system/$u" 2>/dev/null && say "  (unchanged)" || true
  else
    install -o root -g root -m 644 "$SRC/deploy/$u" "/etc/systemd/system/$u"
  fi
done
if [ "$DRY" = 1 ]; then
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  cp "${UNITS[@]/#/$SRC/deploy/}" "$tmp/"
  systemd-analyze verify "$tmp"/jorah-projects.* && say "systemd-analyze verify: ok"
  say "would: systemctl daemon-reload; systemctl enable --now jorah-projects.path jorah-projects.timer"
  say "Dry run: nothing written."
  exit 0
fi
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/jorah-projects.service /etc/systemd/system/jorah-projects.timer /etc/systemd/system/jorah-projects.path
systemctl enable --now jorah-projects.path jorah-projects.timer
systemctl --no-pager list-timers jorah-projects.timer | head -3
say "Installed. No project yet: Adam starts one in chat, and level 0 runs only on a run-now request."
say "Undo: bash $SRC/scripts/pc/install-projects.sh --undo"
