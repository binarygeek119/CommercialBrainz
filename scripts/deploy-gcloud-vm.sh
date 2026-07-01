#!/usr/bin/env bash
# Pull latest code and rebuild API/worker on the CommercialBrainz VM.
# Use this after pushing fixes — a plain "up -d" may reuse a cached image
# without the new Alembic migrations.
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

gcloud config set project "$PROJECT_ID" >/dev/null

ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  exit 1
fi

echo "==> Deploying to $VM_NAME ($ZONE)..."

gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  set -euo pipefail
  cd /opt/commercialbrainz
  sudo bash scripts/fix-gcloud-vm.sh
"

echo ""
echo "==> Done. Run ./scripts/diagnose-gcloud-vm.sh to verify."
