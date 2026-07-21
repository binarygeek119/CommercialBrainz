#!/usr/bin/env bash
# Pull latest code and rebuild the stack on the CommercialBrainz VM.
# Use this after pushing fixes — a plain "up -d" may reuse a cached image
# without the new Alembic migrations.
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#
# GitHub Actions (after CI on main) calls this via .github/workflows/deploy.yml
# with secrets GCP_PROJECT_ID + GCP_SA_KEY.
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"

if [[ -z "$PROJECT_ID" ]]; then
  if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "ERROR: GCP_PROJECT_ID must be set in CI"
    exit 1
  fi
  read -rp "GCP Project ID: " PROJECT_ID
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS="${CLOUDSDK_CORE_DISABLE_PROMPTS:-1}"

gcloud config set project "$PROJECT_ID" >/dev/null

ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  exit 1
fi

echo "==> Deploying to $VM_NAME ($ZONE)..."

gcloud compute ssh "$VM_NAME" \
  --zone="$ZONE" \
  --quiet \
  --ssh-flag="-o StrictHostKeyChecking=accept-new" \
  --ssh-flag="-o LogLevel=ERROR" \
  --command="
  set -euo pipefail
  cd /opt/commercialbrainz
  sudo bash scripts/fix-gcloud-vm.sh
"

echo ""
echo "==> Done. Run ./scripts/diagnose-gcloud-vm.sh to verify."
