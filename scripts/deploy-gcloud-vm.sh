#!/usr/bin/env bash
# Deploy prebuilt images to the CommercialBrainz GCE VM.
# CI builds/pushes api+web to GHCR; this script syncs compose/scripts on the
# VM and pulls those images (no on-VM docker build in the common path).
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz APP_BRANCH=google ./scripts/deploy-gcloud-vm.sh
#   IMAGE_TAG=<git-sha> APP_BRANCH=cloudflare GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#
# Branches: google (testing), cloudflare (public). See docs/branches.md
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
APP_BRANCH="${APP_BRANCH:-google}"

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

echo "==> Deploying to $VM_NAME ($ZONE) APP_BRANCH=${APP_BRANCH} IMAGE_TAG=${IMAGE_TAG}..."

REMOTE_TAG=$(printf '%q' "$IMAGE_TAG")
REMOTE_BRANCH=$(printf '%q' "$APP_BRANCH")

gcloud compute ssh "$VM_NAME" \
  --zone="$ZONE" \
  --quiet \
  --ssh-flag="-o StrictHostKeyChecking=accept-new" \
  --ssh-flag="-o LogLevel=ERROR" \
  --command="
  set -euo pipefail
  cd /opt/commercialbrainz
  export IMAGE_TAG=${REMOTE_TAG}
  export APP_BRANCH=${REMOTE_BRANCH}
  sudo --preserve-env=IMAGE_TAG,APP_BRANCH bash scripts/fix-gcloud-vm.sh
"

echo ""
echo "==> Done. Run ./scripts/diagnose-gcloud-vm.sh to verify."
