#!/usr/bin/env bash
# Create CommercialBrainz issue labels (run as a repo admin).
#
# Usage:
#   ./scripts/setup-github-labels.sh
#   gh auth login   # if needed
#
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-binarygeek119/CommercialBrainz}"

create_or_update() {
  local name="$1" color="$2" description="$3"
  if gh label list --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$name"; then
    gh label edit "$name" --repo "$REPO" --color "$color" --description "$description"
  else
    gh label create "$name" --repo "$REPO" --color "$color" --description "$description"
  fi
  echo "OK  $name"
}

create_or_update "needs-triage" "ededed" "Needs initial triage"
create_or_update "area/api" "1d76db" "Backend / API"
create_or_update "area/frontend" "5319e7" "Web UI"
create_or_update "area/auth" "b60205" "Login, accounts, tokens"
create_or_update "area/deploy" "0e8a16" "VM, Docker, CI/CD"
create_or_update "area/data" "fbca04" "Metadata, dumps, fingerprints"
create_or_update "priority/high" "d93f0b" "Blocks users or production"
create_or_update "priority/low" "c2e0c6" "Nice to have"

echo ""
echo "Labels ready on $REPO"
echo "Open an issue: https://github.com/${REPO}/issues/new/choose"
