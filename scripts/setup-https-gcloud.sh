#!/usr/bin/env bash
# Enable free HTTPS (Let's Encrypt) on an existing CommercialBrainz GCE VM via Caddy.
#
# Prerequisites:
#   - DuckDNS pointing at the VM
#   - GCP firewall allows tcp:443
#
# Usage:
#   ACME_EMAIL=you@example.com DUCKDNS_DOMAIN=commercialbrainz \
#     GCP_PROJECT_ID=commercialbrainz ./scripts/setup-https-gcloud.sh
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
DUCKDNS_DOMAIN="${DUCKDNS_DOMAIN:-commercialbrainz}"
ACME_EMAIL="${ACME_EMAIL:-}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

if [[ -z "$ACME_EMAIL" ]]; then
  read -rp "Email for Let's Encrypt expiry notices: " ACME_EMAIL
fi

FQDN="${DUCKDNS_DOMAIN}.duckdns.org"

gcloud config set project "$PROJECT_ID"

echo "==> Locating VM..."
ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  exit 1
fi
echo "    Zone: $ZONE"

echo "==> Ensuring firewall allows HTTPS (tcp:443)..."
if gcloud compute firewall-rules describe commercialbrainz-allow-https --project="$PROJECT_ID" &>/dev/null; then
  echo "    Rule already exists."
else
  gcloud compute firewall-rules create commercialbrainz-allow-https \
    --project="$PROJECT_ID" \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:443 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=commercialbrainz-server \
    --description="CommercialBrainz HTTPS (Let's Encrypt via Caddy)"
fi

echo "==> Updating instance metadata..."
gcloud compute instances add-metadata "$VM_NAME" --zone="$ZONE" \
  --metadata="acme-email=${ACME_EMAIL},duckdns-domain=${DUCKDNS_DOMAIN}"

echo "==> Configuring HTTPS on VM..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  set -e
  cd /opt/commercialbrainz
  sudo git pull origin main

  set_env() {
    local key=\$1 value=\$2
    if grep -q \"^\${key}=\" .env; then
      sudo sed -i \"s|^\${key}=.*|\${key}=\${value}|\" .env
    else
      echo \"\${key}=\${value}\" | sudo tee -a .env >/dev/null
    fi
  }

  sudo bash infra/gcloud/generate-caddyfile.sh infra/caddy/Caddyfile.runtime '${FQDN}' '${ACME_EMAIL}'
  set_env DOMAIN '${FQDN}'
  set_env ACME_EMAIL '${ACME_EMAIL}'
  set_env CORS_ORIGINS 'https://${FQDN},http://${FQDN}'

  sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml up -d --build caddy api web
  echo 'Waiting for certificate...'
  for i in \$(seq 1 30); do
    if curl -sfk https://${FQDN}/health >/dev/null 2>&1 || curl -sf https://${FQDN}/health >/dev/null 2>&1; then
      echo 'HTTPS is up!'
      exit 0
    fi
    sleep 10
  done
  echo 'HTTPS not ready yet — check: sudo docker compose logs caddy --tail=50'
"

echo ""
echo "==> Done!"
echo "    https://${FQDN}/"
echo "    https://${FQDN}/docs"
