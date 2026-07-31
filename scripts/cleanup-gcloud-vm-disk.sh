#!/usr/bin/env bash
# Free disk on a CommercialBrainz GCE VM (Docker layer / build cache).
# Does NOT prune named volumes (Postgres data stays).
#
# Usage:
#   # Testing VM
#   GCP_PROJECT_ID=commercialbrainz VM_NAME=commercialbrainz-vm \
#     ./scripts/cleanup-gcloud-vm-disk.sh
#
#   # Public VM
#   GCP_PROJECT_ID=commercialbrainz-public VM_NAME=commercialbrainz-public \
#     ./scripts/cleanup-gcloud-vm-disk.sh
#
# Optional: GROW_DISK_GB=40 to resize the boot disk if still tight after prune.
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
GROW_DISK_GB="${GROW_DISK_GB:-}"

if [[ -z "$PROJECT_ID" ]]; then
  if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "ERROR: GCP_PROJECT_ID must be set"
    exit 1
  fi
  read -rp "GCP Project ID: " PROJECT_ID
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS="${CLOUDSDK_CORE_DISABLE_PROMPTS:-1}"
gcloud config set project "$PROJECT_ID" >/dev/null

ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found in project $PROJECT_ID"
  exit 1
fi

echo "==> Cleaning Docker on ${VM_NAME} (${ZONE}, project=${PROJECT_ID})"
gcloud compute ssh "$VM_NAME" \
  --zone="$ZONE" \
  --quiet \
  --ssh-flag="-o StrictHostKeyChecking=accept-new" \
  --command='
set -euo pipefail
echo "Before:"
df -h /
sudo docker system df 2>/dev/null || true
echo ""
echo "Pruning unused images, containers, build cache (keeping volumes)..."
sudo docker builder prune -af || true
sudo docker image prune -af || true
sudo docker container prune -f || true
sudo docker system prune -af || true
echo ""
echo "After:"
df -h /
sudo docker system df 2>/dev/null || true
'

if [[ -n "$GROW_DISK_GB" ]]; then
  DISK="$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
    --format='get(disks[0].source.basename())')"
  echo "==> Resizing boot disk ${DISK} to ${GROW_DISK_GB}GB..."
  gcloud compute disks resize "$DISK" \
    --zone="$ZONE" \
    --size="${GROW_DISK_GB}GB" \
    --quiet
  echo "==> Growing filesystem on VM..."
  gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --quiet \
    --ssh-flag="-o StrictHostKeyChecking=accept-new" \
    --command='
set -euo pipefail
# Debian/Ubuntu: grow partition then filesystem
sudo growpart /dev/sda 1 2>/dev/null || sudo growpart /dev/nvme0n1 1 2>/dev/null || true
sudo resize2fs /dev/sda1 2>/dev/null || sudo resize2fs /dev/nvme0n1p1 2>/dev/null || \
  sudo xfs_growfs / 2>/dev/null || true
df -h /
'
fi

echo ""
echo "==> Done. Re-run Deploy for this environment."
