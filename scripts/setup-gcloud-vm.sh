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
#   GCP_ZONE          Zone (default: auto — tries free-tier zones until one works)
#   GCP_AUTO_ZONE     Set to 0 to disable automatic zone fallback (default: 1)
#   VM_NAME           Instance name, default commercialbrainz-vm
#   REPO_URL          Git repo to clone on VM
#   REPO_BRANCH       Branch to deploy, default main
#   ADMIN_EMAIL       Seed admin on first boot (via instance metadata)
#   ADMIN_USERNAME
#   ADMIN_PASSWORD
#   CREATE_STATIC_IP  Set to 1 to reserve a static external IP
#   DUCKDNS_DOMAIN    DuckDNS subdomain only (e.g. commercialbrainz → commercialbrainz.duckdns.org)
#   DUCKDNS_TOKEN     DuckDNS token from https://www.duckdns.org/
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# If not run from a full repo checkout, fall back to cwd or download startup script.
resolve_startup_script() {
  if [[ -n "${STARTUP_SCRIPT:-}" && -f "$STARTUP_SCRIPT" ]]; then
    echo "$STARTUP_SCRIPT"
    return
  fi

  local candidates=(
    "$ROOT/infra/gcloud/vm-startup.sh"
    "$(pwd)/infra/gcloud/vm-startup.sh"
    "$SCRIPT_DIR/../infra/gcloud/vm-startup.sh"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      echo "$(cd "$(dirname "$candidate")" && pwd)/$(basename "$candidate")"
      return
    fi
  done

  echo "==> Startup script not found locally; downloading from GitHub..." >&2
  local tmp
  tmp="$(mktemp)"
  curl -fsSL \
    "https://raw.githubusercontent.com/binarygeek119/CommercialBrainz/main/infra/gcloud/vm-startup.sh" \
    -o "$tmp"
  echo "$tmp"
}

ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
[[ -f "$ROOT/infra/gcloud/vm-startup.sh" ]] && cd "$ROOT"

PROJECT_ID="${GCP_PROJECT_ID:-}"
GCP_AUTO_ZONE="${GCP_AUTO_ZONE:-1}"
ZONE="${GCP_ZONE:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
REPO_URL="${REPO_URL:-https://github.com/binarygeek119/CommercialBrainz.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-micro}"
DISK_SIZE="${DISK_SIZE:-30GB}"
FIREWALL_TAG="${FIREWALL_TAG:-commercialbrainz-server}"
STARTUP_SCRIPT="$(resolve_startup_script)"

FREE_TIER_REGIONS=("us-west1" "us-central1" "us-east1")
# Zones to try when e2-micro capacity is exhausted (Always Free regions)
FALLBACK_ZONES=(
  us-central1-a us-central1-b us-central1-c us-central1-f
  us-east1-b us-east1-c us-east1-d
  us-west1-a us-west1-b us-west1-c
)

build_zone_list() {
  local zones=()
  local z
  if [[ -n "$ZONE" ]]; then
    zones+=("$ZONE")
  fi
  if [[ "$GCP_AUTO_ZONE" == "1" ]]; then
    for z in "${FALLBACK_ZONES[@]}"; do
      if [[ "$z" != "${ZONE:-}" ]]; then
        zones+=("$z")
      fi
    done
  elif [[ -z "$ZONE" ]]; then
    zones=("${FALLBACK_ZONES[@]}")
  fi
  printf '%s\n' "${zones[@]}"
}

zone_in_free_tier() {
  local zone="$1"
  local region="${zone%-*}"
  local r
  for r in "${FREE_TIER_REGIONS[@]}"; do
    [[ "$region" == "$r" ]] && return 0
  done
  return 1
}

create_vm_in_zone() {
  local zone="$1"
  gcloud compute instances create "$VM_NAME" \
    --zone="$zone" \
    --machine-type="$MACHINE_TYPE" \
    --boot-disk-size="$DISK_SIZE" \
    --boot-disk-type=pd-standard \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --tags="$FIREWALL_TAG" \
    "${STATIC_IP_FLAG[@]}" \
    --metadata-from-file="startup-script=$STARTUP_SCRIPT" \
    --metadata="$METADATA"
}

find_existing_vm_zone() {
  local z
  for z in $(build_zone_list); do
    if gcloud compute instances describe "$VM_NAME" --zone="$z" &>/dev/null; then
      echo "$z"
      return 0
    fi
  done
  return 1
}

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

if [[ ! -f "$STARTUP_SCRIPT" ]]; then
  echo "ERROR: Missing startup script at $STARTUP_SCRIPT"
  echo "Clone the repo or set STARTUP_SCRIPT=/path/to/vm-startup.sh"
  exit 1
fi

REGION="${ZONE%-*}"
if [[ -n "$ZONE" ]]; then
  REGION="${ZONE%-*}"
fi

echo "==> CommercialBrainz free-tier VM setup"
echo "    Project:  $PROJECT_ID"
if [[ -n "$ZONE" ]]; then
  echo "    Zone:     $ZONE (with auto-fallback: $GCP_AUTO_ZONE)"
else
  echo "    Zone:     auto (trying free-tier zones)"
fi
echo "    VM:       $VM_NAME"
echo "    Machine:  $MACHINE_TYPE"
echo "    Repo:     $REPO_URL ($REPO_BRANCH)"
echo "    Startup:  $STARTUP_SCRIPT"
if [[ -n "${DUCKDNS_DOMAIN:-}" ]]; then
  echo "    DuckDNS:  ${DUCKDNS_DOMAIN}.duckdns.org"
fi

if [[ -n "$ZONE" ]] && ! zone_in_free_tier "$ZONE"; then
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
STATIC_IP_REGION=""
if [[ "${CREATE_STATIC_IP:-0}" == "1" ]]; then
  STATIC_IP_REGION="${REGION:-us-central1}"
  echo "==> Reserving static external IP in $STATIC_IP_REGION..."
  gcloud compute addresses describe "${VM_NAME}-ip" --region="$STATIC_IP_REGION" &>/dev/null || \
    gcloud compute addresses create "${VM_NAME}-ip" --region="$STATIC_IP_REGION"
  STATIC_IP=$(gcloud compute addresses describe "${VM_NAME}-ip" --region="$STATIC_IP_REGION" --format='value(address)')
  STATIC_IP_FLAG=(--address="$STATIC_IP")
  echo "    Static IP: $STATIC_IP (region $STATIC_IP_REGION)"
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
EXISTING_ZONE=""
if EXISTING_ZONE="$(find_existing_vm_zone)"; then
  ZONE="$EXISTING_ZONE"
  REGION="${ZONE%-*}"
  echo "    VM '$VM_NAME' already exists in $ZONE. Updating metadata and restarting..."
  gcloud compute instances add-metadata "$VM_NAME" --zone="$ZONE" \
    --metadata-from-file="startup-script=$STARTUP_SCRIPT" \
    --metadata="$METADATA"
  gcloud compute instances reset "$VM_NAME" --zone="$ZONE" --quiet
else
  CREATED=false
  while IFS= read -r try_zone; do
    [[ -z "$try_zone" ]] && continue
    try_region="${try_zone%-*}"

    # Static IPs are regional — only attach when zone matches reserved region.
    if [[ "${CREATE_STATIC_IP:-0}" == "1" && -n "$STATIC_IP_REGION" && "$try_region" != "$STATIC_IP_REGION" ]]; then
      echo "    Skipping $try_zone (static IP is in $STATIC_IP_REGION)..."
      continue
    fi
    STATIC_IP_FLAG=()
    if [[ "${CREATE_STATIC_IP:-0}" == "1" && "$try_region" == "$STATIC_IP_REGION" ]]; then
      STATIC_IP_FLAG=(--address="$STATIC_IP")
    fi

    echo "    Trying zone $try_zone..."
    set +e
    CREATE_OUTPUT="$(create_vm_in_zone "$try_zone" 2>&1)"
    CREATE_STATUS=$?
    set -e

    if [[ $CREATE_STATUS -eq 0 ]]; then
      ZONE="$try_zone"
      REGION="$try_region"
      CREATED=true
      echo "    VM created in $ZONE"
      break
    fi

    if echo "$CREATE_OUTPUT" | grep -qE 'ZONE_RESOURCE_POOL_EXHAUSTED|does not have enough resources'; then
      echo "    No e2-micro capacity in $try_zone, trying next zone..."
      continue
    fi

    echo "$CREATE_OUTPUT" >&2
    exit $CREATE_STATUS
  done < <(build_zone_list)

  if [[ "$CREATED" != true ]]; then
    echo ""
    echo "ERROR: Could not create e2-micro in any free-tier zone."
    echo "       GCP is out of capacity. Try again later or pick a zone manually:"
    echo "         GCP_ZONE=us-east1-b GCP_AUTO_ZONE=0 $0"
    echo "       See: https://cloud.google.com/compute/docs/resource-error"
    exit 1
  fi
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
echo "    API docs:     http://${EXTERNAL_IP}/docs"
if [[ -n "${DUCKDNS_DOMAIN:-}" ]]; then
  echo ""
  echo "    DuckDNS:      http://${DUCKDNS_DOMAIN}.duckdns.org/"
  echo "    DuckDNS docs: http://${DUCKDNS_DOMAIN}.duckdns.org/docs"
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
