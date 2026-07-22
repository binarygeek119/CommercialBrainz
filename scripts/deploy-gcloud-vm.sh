#!/usr/bin/env bash
# Deploy prebuilt images to the CommercialBrainz GCE VM.
# CI builds/pushes api+web to GHCR; this script syncs compose/scripts on the
# VM and pulls those images (no on-VM docker build in the common path).
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#   IMAGE_TAG=<git-sha> GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#
# GitHub Actions (.github/workflows/deploy.yml) calls this after CI on main.
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

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

echo "==> Deploying to $VM_NAME ($ZONE) IMAGE_TAG=${IMAGE_TAG}..."

# Quote IMAGE_TAG safely for the remote shell.
REMOTE_TAG=$(printf '%q' "$IMAGE_TAG")

gcloud compute ssh "$VM_NAME" \
  --zone="$ZONE" \
  --quiet \
  --ssh-flag="-o StrictHostKeyChecking=accept-new" \
  --ssh-flag="-o LogLevel=ERROR" \
  --command="
  set -euo pipefail
  cd /opt/commercialbrainz
  export IMAGE_TAG=${REMOTE_TAG}
  sudo --preserve-env=IMAGE_TAG bash scripts/fix-gcloud-vm.sh
"

echo ""
echo "==> Done. Run ./scripts/diagnose-gcloud-vm.sh to verify."
