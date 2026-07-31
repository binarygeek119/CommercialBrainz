#!/usr/bin/env bash
# Ensure the active gcloud identity can SSH to a CommercialBrainz GCE VM.
#
# Common deploy failure:
#   Permission denied (publickey) as runner@IP
# Causes:
#   - instance metadata block-project-ssh-keys=TRUE (project keys ignored)
#   - OS Login required but github-deploy lacks osAdminLogin on the instance
#
# Usage (env):
#   GCP_PROJECT_ID=commercialbrainz VM_NAME=commercialbrainz-vm ZONE=us-central1-b \
#     ./scripts/ensure-gcloud-vm-ssh.sh
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-}"
ZONE="${ZONE:-}"

if [[ -z "$PROJECT_ID" || -z "$VM_NAME" ]]; then
  echo "ERROR: GCP_PROJECT_ID and VM_NAME are required"
  exit 1
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS="${CLOUDSDK_CORE_DISABLE_PROMPTS:-1}"
gcloud config set project "$PROJECT_ID" >/dev/null

if [[ -z "$ZONE" ]]; then
  ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
fi
if [[ -z "$ZONE" ]]; then
  echo "ERROR: could not resolve zone for VM ${VM_NAME}"
  exit 1
fi

echo "==> Ensuring SSH access to ${VM_NAME} (${ZONE})"

# Allow SSH from the internet (GitHub-hosted runners are not on your VPC).
if ! gcloud compute firewall-rules describe commercialbrainz-allow-ssh --project="$PROJECT_ID" &>/dev/null; then
  echo "    Creating firewall rule commercialbrainz-allow-ssh (tcp:22)..."
  gcloud compute firewall-rules create commercialbrainz-allow-ssh \
    --project="$PROJECT_ID" \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=commercialbrainz-server \
    --description="CommercialBrainz SSH for gcloud deploy" \
    --quiet || echo "    WARN: could not create SSH firewall rule (may lack permission)"
else
  echo "    Firewall commercialbrainz-allow-ssh already exists"
fi

# Project metadata SSH keys are ignored when this is TRUE.
echo "    Clearing block-project-ssh-keys (if set)..."
gcloud compute instances remove-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --keys=block-project-ssh-keys \
  --quiet 2>/dev/null || true

DEPLOY_SA="github-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
MEMBER="serviceAccount:${DEPLOY_SA}"
echo "    Granting OS Login roles to ${DEPLOY_SA} on ${VM_NAME}..."
for role in roles/compute.osAdminLogin roles/compute.osLogin; do
  gcloud compute instances add-iam-policy-binding "$VM_NAME" \
    --zone="$ZONE" \
    --member="$MEMBER" \
    --role="$role" \
    --quiet >/dev/null 2>&1 \
    && echo "      + ${role}" \
    || echo "      WARN: could not bind ${role} (may already exist or lack permission)"
done

# Project-level helps some OS Login lookups; ignore failures.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$MEMBER" \
  --role="roles/compute.osAdminLogin" \
  --condition=None \
  --quiet >/dev/null 2>&1 || true

# Enable OS Login after IAM grants so the next SSH uses the SA identity.
echo "    Enabling OS Login on the instance..."
gcloud compute instances add-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --metadata=enable-oslogin=TRUE \
  --quiet || echo "    WARN: could not set enable-oslogin"

echo "    Waiting a few seconds for metadata / IAM to settle..."
sleep 8

echo "==> SSH probe (with retries)..."
ATTEMPTS="${SSH_PROBE_ATTEMPTS:-12}"
for i in $(seq 1 "$ATTEMPTS"); do
  if gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --quiet \
    --ssh-flag="-o StrictHostKeyChecking=accept-new" \
    --ssh-flag="-o LogLevel=ERROR" \
    --ssh-flag="-o ConnectTimeout=10" \
    --command="echo ok" 2>/dev/null; then
    echo "    SSH ok on attempt ${i}"
    exit 0
  fi
  echo "    attempt ${i}/${ATTEMPTS} failed; sleeping..."
  sleep 5
done

echo "ERROR: still cannot SSH to ${VM_NAME} as $(gcloud config get-value account 2>/dev/null || echo unknown)"
echo "  From a laptop owner account, run:"
echo "    gcloud compute instances add-iam-policy-binding ${VM_NAME} --zone=${ZONE} \\"
echo "      --member='serviceAccount:${DEPLOY_SA}' --role='roles/compute.osAdminLogin'"
echo "    gcloud compute instances remove-metadata ${VM_NAME} --zone=${ZONE} --keys=block-project-ssh-keys"
exit 1
