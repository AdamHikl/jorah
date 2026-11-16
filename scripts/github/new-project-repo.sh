#!/usr/bin/env bash
# Puts a project Jorah started local-only on GitHub: a new private repo, then the rulesets that keep
# Jorah's GitHub App to jorah/** branches (protect-repo.sh). Run on the Mac, signed in to gh as Adam:
#   scripts/github/new-project-repo.sh <name> ["one-line description"] [--dry-run]
#
# Why Adam runs it: creating a repo and its rulesets needs admin rights. Giving those to Jorah's App
# would let it remove the very rules that stop it pushing to main (docs/plan/11-project-mode.md, 5.1).
# The App is installed on all of Adam's repos, so the new repo is covered once it exists.
# The repo starts with a README on main; the runner merges that into Jorah's local line once.
# Then tell Jorah: "connect <name> to GitHub". Undo: delete the repo on GitHub (Settings -> Danger zone).
set -euo pipefail

name="${1:-}"; desc=""; mode=""
shift || true
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then mode="--dry-run"; else desc="$arg"; fi
done
[[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "usage: $0 <name> [\"description\"] [--dry-run]"; exit 2; }
owner="${JORAH_GITHUB_OWNER:-AdamHikl}"
repo="$owner/$name"
here="$(cd "$(dirname "$0")" && pwd)"

login="$(gh api user --jq .login)"
[ "$login" = "$owner" ] || { echo "gh is signed in as $login, not $owner: stop"; exit 1; }
if gh repo view "$repo" >/dev/null 2>&1; then
  echo "$repo already exists. If it should be Jorah's project, protect it and tell Jorah to connect it:"
  echo "  $here/protect-repo.sh $repo"
  exit 1
fi

if [ "$mode" = "--dry-run" ]; then
  echo "Dry run: would create $repo (private, with a README${desc:+, description \"$desc\"}), then add the two jorah rulesets."
  exit 0
fi

gh repo create "$repo" --private --add-readme ${desc:+--description "$desc"}
"$here/protect-repo.sh" "$repo"
echo
echo "Done: $repo is private and protected. Tell Jorah: \"connect $name to GitHub\"."
