#!/usr/bin/env bash
# Add or update DuckDNS on an existing CommercialBrainz GCE VM.
#
# Usage:
#   DUCKDNS_DOMAIN=commercialbrainz DUCKDNS_TOKEN=your-token \
#     GCP_PROJECT_ID=my-project ./scripts/setup-duckdns-gcloud.sh
#
# Optional:
#   VM_NAME       default commercialbrainz-vm
#   GCP_ZONE      zone (auto-detected across project if omitted)
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"

FALLBACK_ZONES=(
  us-central1-a us-central1-b us-central1-c us-central1-f
  us-east1-b us-east1-c us-east1-d
  us-west1-a us-west1-b us-west1-c
)

find_vm_zone() {
  local vm_name="$1"
  local z found

  # Fast path: gcloud list across entire project
  found="$(gcloud compute instances list \
    --filter="name=${vm_name}" \
    --format='value(zone.basename())' \
    --limit=1 2>/dev/null || true)"
  if [[ -n "$found" ]]; then
    echo "$found"
    return 0
  fi

  # Fallback: probe known free-tier zones
  if [[ -n "${ZONE:-}" ]]; then
    if gcloud compute instances describe "$vm_name" --zone="$ZONE" &>/dev/null; then
      echo "$ZONE"
      return 0
    fi
  fi

  for z in "${FALLBACK_ZONES[@]}"; do
    [[ "$z" == "${ZONE:-}" ]] && continue
    if gcloud compute instances describe "$vm_name" --zone="$z" &>/dev/null; then
      echo "$z"
      return 0
    fi
  done

  return 1
}

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

if [[ -z "${DUCKDNS_DOMAIN:-}" ]]; then
  read -rp "DuckDNS subdomain (e.g. commercialbrainz): " DUCKDNS_DOMAIN
fi

if [[ -z "${DUCKDNS_TOKEN:-}" ]]; then
  read -rsp "DuckDNS token: " DUCKDNS_TOKEN
  echo
fi

gcloud config set project "$PROJECT_ID"

echo "==> Locating VM '$VM_NAME'..."
if ! ZONE="$(find_vm_zone "$VM_NAME")"; then
  echo "ERROR: VM '$VM_NAME' not found in project $PROJECT_ID"
  echo "       List instances: gcloud compute instances list --project=$PROJECT_ID"
  exit 1
fi
echo "    Found in zone: $ZONE"

echo "==> Adding DuckDNS metadata to $VM_NAME..."
gcloud compute instances add-metadata "$VM_NAME" --zone="$ZONE" \
  --metadata="duckdns-domain=$DUCKDNS_DOMAIN,duckdns-token=$DUCKDNS_TOKEN"

EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "==> Updating DuckDNS (${DUCKDNS_DOMAIN}.duckdns.org → ${EXTERNAL_IP})..."
RESPONSE=$(curl -sf \
  "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${EXTERNAL_IP}" \
  || echo "KO")

if [[ "$RESPONSE" == "OK" ]]; then
  echo "    DuckDNS updated."
else
  echo "    WARNING: DuckDNS returned: $RESPONSE"
fi

echo "==> Installing DuckDNS cron on VM..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  sudo mkdir -p /etc/commercialbrainz
  echo 'DUCKDNS_DOMAIN=$DUCKDNS_DOMAIN' | sudo tee /etc/commercialbrainz/duckdns.env >/dev/null
  echo 'DUCKDNS_TOKEN=$DUCKDNS_TOKEN' | sudo tee -a /etc/commercialbrainz/duckdns.env >/dev/null
  sudo chmod 600 /etc/commercialbrainz/duckdns.env
  if [[ -f /opt/commercialbrainz/infra/gcloud/duckdns-update.sh ]]; then
    sudo install -m 0755 /opt/commercialbrainz/infra/gcloud/duckdns-update.sh /usr/local/bin/duckdns-update
  else
    sudo curl -fsSL -o /usr/local/bin/duckdns-update \
      https://raw.githubusercontent.com/binarygeek119/CommercialBrainz/main/infra/gcloud/duckdns-update.sh
    sudo chmod 755 /usr/local/bin/duckdns-update
  fi
  echo '*/5 * * * * root /usr/local/bin/duckdns-update' | sudo tee /etc/cron.d/commercialbrainz-duckdns >/dev/null
  sudo /usr/local/bin/duckdns-update || true
"

echo ""
echo "==> Done!"
echo "    Zone:   $ZONE"
echo "    IP:     $EXTERNAL_IP"
echo "    http://${DUCKDNS_DOMAIN}.duckdns.org/"
echo "    http://${DUCKDNS_DOMAIN}.duckdns.org/docs"
