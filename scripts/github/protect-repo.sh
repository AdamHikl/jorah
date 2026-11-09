#!/usr/bin/env bash
# Gives Jorah's GitHub account push access to one repo, limited server-side to jorah/** branches.
# Adam runs it on the Mac, signed in to gh as himself (repo admin):
#   scripts/github/protect-repo.sh AdamHikl/some-repo jorah-account-name [--dry-run]
#
# 1. Ruleset "jorah: only jorah/**": every branch except jorah/** refuses creation, update,
#    deletion and force pushes. Repository admins (Adam) bypass it, so Adam's own pushes work.
# 2. Ruleset "jorah/**: no force, no delete": Jorah's branches can only move forward.
# 3. Invites the account as a collaborator with write ("push") permission.
# Rulesets on private repos need GitHub Pro (the Student Pack includes it); the API says so if not.
# Never for AdamHikl/jorah: Jorah never gets write access to its own code (Adam, 2026-11-07).
#
# Undo: delete the two rulesets in Settings -> Rules -> Rulesets, and remove the collaborator.
set -euo pipefail

repo="${1:-}"; account="${2:-}"; mode="${3:-}"
[[ "$repo" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || { echo "usage: $0 owner/repo jorah-account [--dry-run]"; exit 2; }
[[ "$account" =~ ^[A-Za-z0-9-]+$ ]] || { echo "usage: $0 owner/repo jorah-account [--dry-run]"; exit 2; }
if [ "$(printf %s "$repo" | tr '[:upper:]' '[:lower:]')" = "adamhikl/jorah" ]; then
  echo "Refused: Jorah never gets write access to AdamHikl/jorah."; exit 3
fi

only_jorah='{
  "name": "jorah: only jorah/**",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [{ "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }],
  "conditions": { "ref_name": { "include": ["~ALL"], "exclude": ["refs/heads/jorah/**"] } },
  "rules": [{ "type": "creation" }, { "type": "update" }, { "type": "deletion" }, { "type": "non_fast_forward" }]
}'
jorah_forward='{
  "name": "jorah/**: no force, no delete",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [{ "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }],
  "conditions": { "ref_name": { "include": ["refs/heads/jorah/**"], "exclude": [] } },
  "rules": [{ "type": "deletion" }, { "type": "non_fast_forward" }]
}'

echo "Repo: $repo   Account: $account"
echo "Existing rulesets:"
gh api "repos/$repo/rulesets" --jq '.[] | "  - \(.name) (\(.enforcement))"' || true
if [ "$mode" = "--dry-run" ]; then
  echo "Dry run: would add the two rulesets above (by name, skipped if present) and invite $account with push."
  exit 0
fi

have() { gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$1\") | .id" | grep -q .; }
for body in "$only_jorah" "$jorah_forward"; do
  name="$(printf %s "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"
  if have "$name"; then echo "  ruleset present: $name"; continue; fi
  printf %s "$body" | gh api -X POST "repos/$repo/rulesets" --input - --jq '"  ruleset added: \(.name) (id \(.id))"'
done
gh api -X PUT "repos/$repo/collaborators/$account" -f permission=push --jq '"  invited: \(.invitee.login // "already a collaborator")"' 2>/dev/null \
  || echo "  $account is already a collaborator, or the invite failed: check Settings -> Collaborators"
echo "Next: accept the invite as $account (github.com/$repo/invitations)."
