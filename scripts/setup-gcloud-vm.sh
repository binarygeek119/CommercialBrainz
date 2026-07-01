#!/usr/bin/env bash
# Create a free-tier Google Cloud e2-micro VM and deploy CommercialBrainz.
#
# Always Free (subject to GCP terms):
#   - 1× e2-micro per month in us-west1, us-central1, or us-east1
#   - 30 GB standard persistent disk
#   - 1 GB/month egress from North America
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Billing enabled (free tier still requires a billing account)
#
# Usage:
#   chmod +x scripts/setup-gcloud-vm.sh
#   GCP_PROJECT_ID=my-project ./scripts/setup-gcloud-vm.sh
#
# Optional env vars:
#   GCP_PROJECT_ID    GCP project (prompted if unset)
#   GCP_ZONE          Zone, default us-central1-a (free-tier region)
#   VM_NAME           Instance name, default commercialbrainz-vm
#   REPO_URL          Git repo to clone on VM
#   REPO_BRANCH       Branch to deploy, default main
#   ADMIN_EMAIL       Seed admin on first boot (via instance metadata)
#   ADMIN_USERNAME
#   ADMIN_PASSWORD
#   ADMIN_PASSWORD
#   CREATE_STATIC_IP  Set to 1 to reserve a static external IP
#   DUCKDNS_DOMAIN    DuckDNS subdomain only (e.g. commercialbrainz → commercialbrainz.duckdns.org)
#   DUCKDNS_TOKEN     DuckDNS token from https://www.duckdns.org/
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
REGION="${ZONE%-*}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
REPO_URL="${REPO_URL:-https://github.com/binarygeek119/CommercialBrainz.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-micro}"
DISK_SIZE="${DISK_SIZE:-30GB}"
FIREWALL_TAG="${FIREWALL_TAG:-commercialbrainz-server}"
STARTUP_SCRIPT="${ROOT}/infra/gcloud/vm-startup.sh"

FREE_TIER_REGIONS=("us-west1" "us-central1" "us-east1")

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

if [[ ! -f "$STARTUP_SCRIPT" ]]; then
  echo "ERROR: Missing startup script at $STARTUP_SCRIPT"
  exit 1
fi

is_free_tier_region=false
for r in "${FREE_TIER_REGIONS[@]}"; do
  if [[ "$REGION" == "$r" ]]; then
    is_free_tier_region=true
    break
  fi
done

echo "==> CommercialBrainz free-tier VM setup"
echo "    Project:  $PROJECT_ID"
echo "    Zone:     $ZONE"
echo "    VM:       $VM_NAME"
echo "    Machine:  $MACHINE_TYPE"
echo "    Repo:     $REPO_URL ($REPO_BRANCH)"
if [[ -n "${DUCKDNS_DOMAIN:-}" ]]; then
  echo "    DuckDNS:  ${DUCKDNS_DOMAIN}.duckdns.org"
fi

if [[ "$is_free_tier_region" == false ]]; then
  echo ""
  echo "WARNING: Zone $ZONE is not in a documented Always Free region."
  echo "         Free-tier e2-micro applies to: us-west1, us-central1, us-east1"
  read -rp "Continue anyway? [y/N] " confirm
  [[ "${confirm,,}" == "y" ]] || exit 1
fi

gcloud config set project "$PROJECT_ID"

echo "==> Enabling Compute Engine API..."
gcloud services enable compute.googleapis.com

echo "==> Creating firewall rule (HTTP + API)..."
if ! gcloud compute firewall-rules describe commercialbrainz-allow-web --project="$PROJECT_ID" &>/dev/null; then
  gcloud compute firewall-rules create commercialbrainz-allow-web \
    --project="$PROJECT_ID" \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:80,tcp:8000 \
    --source-ranges=0.0.0.0/0 \
    --target-tags="$FIREWALL_TAG" \
    --description="CommercialBrainz web UI (80) and API (8000)"
else
  echo "    Firewall rule already exists."
fi

STATIC_IP_FLAG=()
if [[ "${CREATE_STATIC_IP:-0}" == "1" ]]; then
  echo "==> Reserving static external IP..."
  gcloud compute addresses describe "${VM_NAME}-ip" --region="$REGION" &>/dev/null || \
    gcloud compute addresses create "${VM_NAME}-ip" --region="$REGION"
  STATIC_IP=$(gcloud compute addresses describe "${VM_NAME}-ip" --region="$REGION" --format='value(address)')
  STATIC_IP_FLAG=(--address="$STATIC_IP")
  echo "    Static IP: $STATIC_IP"
fi

METADATA="repo-url=$REPO_URL,repo-branch=$REPO_BRANCH"
[[ -n "${ADMIN_EMAIL:-}" ]] && METADATA+=",admin-email=$ADMIN_EMAIL"
[[ -n "${ADMIN_USERNAME:-}" ]] && METADATA+=",admin-username=$ADMIN_USERNAME"
[[ -n "${ADMIN_PASSWORD:-}" ]] && METADATA+=",admin-password=$ADMIN_PASSWORD"
[[ -n "${DUCKDNS_DOMAIN:-}" ]] && METADATA+=",duckdns-domain=$DUCKDNS_DOMAIN"
[[ -n "${DUCKDNS_TOKEN:-}" ]] && METADATA+=",duckdns-token=$DUCKDNS_TOKEN"

if [[ -n "${DUCKDNS_DOMAIN:-}" && -z "${DUCKDNS_TOKEN:-}" ]] || [[ -z "${DUCKDNS_DOMAIN:-}" && -n "${DUCKDNS_TOKEN:-}" ]]; then
  echo "ERROR: Set both DUCKDNS_DOMAIN and DUCKDNS_TOKEN, or neither."
  exit 1
fi

echo "==> Creating VM (free-tier e2-micro)..."
if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" &>/dev/null; then
  echo "    VM '$VM_NAME' already exists. Updating metadata and restarting..."
  gcloud compute instances add-metadata "$VM_NAME" --zone="$ZONE" \
    --metadata-from-file="startup-script=$STARTUP_SCRIPT" \
    --metadata="$METADATA"
  gcloud compute instances reset "$VM_NAME" --zone="$ZONE" --quiet
else
  gcloud compute instances create "$VM_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --boot-disk-size="$DISK_SIZE" \
    --boot-disk-type=pd-standard \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --tags="$FIREWALL_TAG" \
    "${STATIC_IP_FLAG[@]}" \
    --metadata-from-file="startup-script=$STARTUP_SCRIPT" \
    --metadata="$METADATA"
fi

echo "==> Waiting for VM to get an external IP..."
sleep 10

EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

if [[ -n "${DUCKDNS_DOMAIN:-}" && -n "${DUCKDNS_TOKEN:-}" ]]; then
  echo "==> Updating DuckDNS (${DUCKDNS_DOMAIN}.duckdns.org → ${EXTERNAL_IP})..."
  DUCKDNS_RESPONSE=$(curl -sf \
    "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${EXTERNAL_IP}" \
    || echo "KO")
  if [[ "$DUCKDNS_RESPONSE" == "OK" ]]; then
    echo "    DuckDNS updated successfully."
  else
    echo "    WARNING: DuckDNS update returned: $DUCKDNS_RESPONSE"
    echo "    The VM startup script will retry once boot completes."
  fi
fi

echo ""
echo "==> VM created! Startup script is installing Docker and CommercialBrainz."
echo "    This takes 10–20 minutes on a free e2-micro (includes Docker image build)."
echo ""
echo "    External IP:  $EXTERNAL_IP"
echo "    Web UI:       http://${EXTERNAL_IP}/          (port 80, after startup finishes)"
echo "    API:          http://${EXTERNAL_IP}:8000/"
echo "    API docs:     http://${EXTERNAL_IP}:8000/docs"
if [[ -n "${DUCKDNS_DOMAIN:-}" ]]; then
  echo ""
  echo "    DuckDNS:      http://${DUCKDNS_DOMAIN}.duckdns.org/"
  echo "    DuckDNS API:  http://${DUCKDNS_DOMAIN}.duckdns.org:8000/docs"
fi
echo ""
echo "Monitor startup progress:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo tail -f /var/log/commercialbrainz-startup.log'"
echo ""
echo "SSH into the VM:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "Manage the stack on the VM:"
echo "  cd /opt/commercialbrainz"
echo "  sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml ps"
echo ""
echo "Stop VM (saves compute while keeping disk):"
echo "  gcloud compute instances stop $VM_NAME --zone=$ZONE"
echo ""
echo "Delete VM:"
echo "  gcloud compute instances delete $VM_NAME --zone=$ZONE"
