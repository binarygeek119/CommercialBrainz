#!/usr/bin/env bash
# One-time fix: restore GitHub Actions SSH to the testing / public VMs.
# Run on your laptop as a GCP project owner (not inside GitHub Actions).
#
# Usage:
#   ./scripts/fix-deploy-ssh-from-laptop.sh
#   VM_NAME=commercialbrainz-public ZONE=us-central1-a ./scripts/fix-deploy-ssh-from-laptop.sh
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-commercialbrainz}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
ZONE="${ZONE:-}"

echo "==> Fix deploy SSH for ${VM_NAME}"
echo "    Project: ${PROJECT_ID}"

if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | grep -q .; then
  echo "No active gcloud account. Opening login..."
  gcloud auth login
fi

gcloud config set project "$PROJECT_ID"

if [[ -z "$ZONE" ]]; then
  ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
fi
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM ${VM_NAME} not found in project ${PROJECT_ID}"
  echo "Available instances:"
  gcloud compute instances list
  exit 1
fi
echo "    Zone: ${ZONE}"
echo "    Account: $(gcloud config get-value account)"

SA="github-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Firewall tcp:22 for tag commercialbrainz-server"
if ! gcloud compute firewall-rules describe commercialbrainz-allow-ssh --project="$PROJECT_ID" &>/dev/null; then
  gcloud compute firewall-rules create commercialbrainz-allow-ssh \
    --project="$PROJECT_ID" \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=commercialbrainz-server \
    --description="CommercialBrainz SSH for gcloud deploy"
fi

echo "==> Network tag"
gcloud compute instances add-tags "$VM_NAME" \
  --zone="$ZONE" \
  --tags=commercialbrainz-server \
  --quiet || true

echo "==> Disable OS Login + unblock project SSH keys (Actions uses metadata keys as user runner)"
gcloud compute instances add-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --metadata=enable-oslogin=FALSE
gcloud compute instances remove-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --keys=block-project-ssh-keys 2>/dev/null || true

echo "==> Grant github-deploy OS Login roles (optional, for later)"
gcloud compute instances add-iam-policy-binding "$VM_NAME" \
  --zone="$ZONE" \
  --member="serviceAccount:${SA}" \
  --role="roles/compute.osAdminLogin" \
  --quiet || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/compute.osAdminLogin" \
  --quiet || true

gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="serviceAccount:${SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet || true

echo "==> Probe SSH as your user (sanity check)"
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="echo laptop-ssh-ok && hostname" \
  --ssh-flag="-o StrictHostKeyChecking=accept-new"

cat <<EOF

==> Done for ${VM_NAME}

Re-run GitHub Actions → Deploy → testing (or cloudflare).

If Actions still fails, the VM guest agent may need a minute after metadata
changes — wait ~2 minutes and redeploy.

Public VM (if needed):
  VM_NAME=commercialbrainz-public ZONE=<zone> ./scripts/fix-deploy-ssh-from-laptop.sh
EOF
