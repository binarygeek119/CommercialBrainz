#!/usr/bin/env bash
# Ensure the active gcloud identity can SSH to a CommercialBrainz GCE VM.
#
# GitHub Actions uses metadata SSH keys as user "runner". That path breaks when:
#   - enable-oslogin=TRUE without osAdminLogin for github-deploy, or
#   - block-project-ssh-keys=TRUE
#
# This script prefers metadata SSH for CI (disables OS Login on the instance),
# clears block-project-ssh-keys, opens tcp:22, and probes SSH with retries.
#
# Usage:
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
echo "    Active account: $(gcloud config get-value account 2>/dev/null || echo unknown)"

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

# Confirm the instance has the firewall tag (setup-gcloud-vm uses commercialbrainz-server).
TAGS="$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --format='value(tags.items)' 2>/dev/null || true)"
if [[ ",${TAGS}," != *",commercialbrainz-server,"* ]]; then
  echo "    Adding network tag commercialbrainz-server..."
  gcloud compute instances add-tags "$VM_NAME" \
    --zone="$ZONE" \
    --tags=commercialbrainz-server \
    --quiet || echo "    WARN: could not add tag"
fi

echo "    Clearing block-project-ssh-keys..."
gcloud compute instances remove-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --keys=block-project-ssh-keys \
  --quiet 2>/dev/null || true

# Metadata SSH (gcloud → user "runner" on GHA) does not work with OS Login enabled.
# Prefer metadata SSH for Actions; owners can still use OS Login from a laptop later.
echo "    Disabling OS Login on the instance (use metadata SSH for CI)..."
gcloud compute instances add-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --metadata=enable-oslogin=FALSE \
  --quiet || echo "    WARN: could not set enable-oslogin=FALSE"

# Also clear project-level OS Login if set (instance FALSE should win, but be explicit).
# Do not change project metadata aggressively — instance-level FALSE is enough.

# Pre-create the key gcloud compute ssh will use, and publish it on the instance
# so we do not wait only on project-metadata propagation.
SSH_DIR="${HOME}/.ssh"
mkdir -p "$SSH_DIR"
KEY_PATH="${SSH_DIR}/google_compute_engine"
if [[ ! -f "${KEY_PATH}" ]]; then
  echo "    Generating ${KEY_PATH}..."
  ssh-keygen -t rsa -b 3072 -f "$KEY_PATH" -N "" -C "github-actions-deploy" >/dev/null
fi
PUB="$(cat "${KEY_PATH}.pub")"
# Format: username:key — GHA runners connect as "runner"
INSTANCE_ENTRY="runner:${PUB}"
echo "    Writing instance ssh-keys metadata for user runner..."
# Merge with existing ssh-keys if any (keep other users).
EXISTING="$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
  --format='value(metadata.items.filter("key:ssh-keys").value)' 2>/dev/null || true)"
MERGED="${INSTANCE_ENTRY}"
if [[ -n "$EXISTING" ]]; then
  # Drop old runner: lines, keep others.
  OTHER="$(printf '%s\n' "$EXISTING" | grep -v '^runner:' || true)"
  if [[ -n "$OTHER" ]]; then
    MERGED="$(printf '%s\n%s\n' "$OTHER" "$INSTANCE_ENTRY")"
  fi
fi
# gcloud metadata values with newlines need a file.
TMP_KEYS="$(mktemp)"
printf '%s\n' "$MERGED" >"$TMP_KEYS"
gcloud compute instances add-metadata "$VM_NAME" \
  --zone="$ZONE" \
  --metadata-from-file=ssh-keys="$TMP_KEYS" \
  --quiet || echo "    WARN: could not set instance ssh-keys"
rm -f "$TMP_KEYS"

DEPLOY_SA="github-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
MEMBER="serviceAccount:${DEPLOY_SA}"
# Optional OS Login grants for laptop use — do not enable OS Login here.
echo "    (Optional) ensuring ${DEPLOY_SA} has osAdminLogin for future OS Login use..."
gcloud compute instances add-iam-policy-binding "$VM_NAME" \
  --zone="$ZONE" \
  --member="$MEMBER" \
  --role="roles/compute.osAdminLogin" \
  --quiet >/dev/null 2>&1 \
  && echo "      + roles/compute.osAdminLogin" \
  || echo "      (skipped — run scripts/fix-deploy-ssh-from-laptop.sh as project owner if needed)"

echo "    Waiting for guest agent to pick up SSH keys..."
sleep 10

echo "==> SSH probe (with retries)..."
ATTEMPTS="${SSH_PROBE_ATTEMPTS:-12}"
LAST_ERR=""
for i in $(seq 1 "$ATTEMPTS"); do
  if ERR="$(gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --quiet \
    --ssh-key-file="$KEY_PATH" \
    --ssh-flag="-o StrictHostKeyChecking=accept-new" \
    --ssh-flag="-o IdentitiesOnly=yes" \
    --ssh-flag="-o LogLevel=ERROR" \
    --ssh-flag="-o ConnectTimeout=15" \
    --command="echo ok" 2>&1)"; then
    echo "    SSH ok on attempt ${i}"
    exit 0
  fi
  LAST_ERR="$ERR"
  echo "    attempt ${i}/${ATTEMPTS} failed; sleeping..."
  sleep 5
done

echo "ERROR: still cannot SSH to ${VM_NAME} as $(gcloud config get-value account 2>/dev/null || echo unknown)"
echo "Last error:"
echo "$LAST_ERR"
echo ""
echo "Run this ONCE from your laptop (owner Google account):"
echo "  ./scripts/fix-deploy-ssh-from-laptop.sh"
echo "Or manually:"
echo "  gcloud auth login && gcloud config set project ${PROJECT_ID}"
echo "  gcloud compute instances add-metadata ${VM_NAME} --zone=${ZONE} --metadata=enable-oslogin=FALSE"
echo "  gcloud compute instances remove-metadata ${VM_NAME} --zone=${ZONE} --keys=block-project-ssh-keys"
exit 1
