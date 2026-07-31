#!/usr/bin/env bash
# Point CommercialBrainz at a real domain via Cloudflare Free (cheapest).
#
# You do Cloudflare DNS in the dashboard (this script cannot log into CF).
# This script updates the GCE VM: DOMAIN, aliases, CORS, APP_PUBLIC_URL, Caddy.
#
# Prerequisites:
#   - Domain registered (e.g. commercialbrainz.org) and added to Cloudflare Free
#   - gcloud CLI authenticated
#   - VM already running CommercialBrainz
#
# Usage:
#   GCP_PROJECT_ID=your-project \
#   DOMAIN=commercialbrainz.org \
#   ACME_EMAIL=you@example.com \
#     ./scripts/setup-cloudflare-domain.sh
#
# Optional:
#   DOMAIN_ALIASES=www.commercialbrainz.org,commercialbrainz.duckdns.org
#   KEEP_DUCKDNS=1   # append commercialbrainz.duckdns.org if not already in aliases
#   ENABLE_PROXY=0   # print orange-cloud tips after DNS-only LE succeeds (default tips on)
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
DOMAIN="${DOMAIN:-commercialbrainz.org}"
ACME_EMAIL="${ACME_EMAIL:-}"
DOMAIN_ALIASES="${DOMAIN_ALIASES:-www.${DOMAIN}}"
KEEP_DUCKDNS="${KEEP_DUCKDNS:-1}"
DUCKDNS_FQDN="${DUCKDNS_FQDN:-commercialbrainz.duckdns.org}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi
if [[ -z "$ACME_EMAIL" ]]; then
  read -rp "Email for Let's Encrypt notices: " ACME_EMAIL
fi

if [[ "$KEEP_DUCKDNS" == "1" ]]; then
  if [[ ",${DOMAIN_ALIASES}," != *",${DUCKDNS_FQDN},"* ]]; then
    DOMAIN_ALIASES="${DOMAIN_ALIASES},${DUCKDNS_FQDN}"
  fi
fi

# Normalize commas / spaces
DOMAIN_ALIASES="$(echo "$DOMAIN_ALIASES" | tr -s ' ' | sed 's/ //g')"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Locating VM..."
ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  exit 1
fi
EXTERNAL_IP="$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
echo "    Zone: $ZONE"
echo "    External IP: $EXTERNAL_IP"

echo "==> Ensuring firewall allows HTTP/HTTPS..."
if ! gcloud compute firewall-rules describe commercialbrainz-allow-https --project="$PROJECT_ID" &>/dev/null; then
  gcloud compute firewall-rules create commercialbrainz-allow-https \
    --project="$PROJECT_ID" \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:443 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=commercialbrainz-server \
    --description="CommercialBrainz HTTPS"
fi

CORS_ORIGINS="https://${DOMAIN},https://www.${DOMAIN}"
IFS=',' read -ra _aliases <<< "$DOMAIN_ALIASES"
for host in "${_aliases[@]}"; do
  [[ -z "$host" ]] && continue
  if [[ ",${CORS_ORIGINS}," != *",https://${host},"* ]]; then
    CORS_ORIGINS="${CORS_ORIGINS},https://${host}"
  fi
done

cat <<EOF

═══════════════════════════════════════════════════════════════════
  Cloudflare Free — do this in the dashboard (one-time, \$0/mo)
═══════════════════════════════════════════════════════════════════

1. Add site ${DOMAIN} on https://dash.cloudflare.com (Free plan).
2. At your registrar, switch nameservers to the two Cloudflare NS hosts.
3. DNS → create records (IMPORTANT: Proxy status = DNS only / grey cloud
   until Let's Encrypt succeeds — orange cloud breaks HTTP-01):

     Type  Name  Content           Proxy
     A     @     ${EXTERNAL_IP}    DNS only
     A     www   ${EXTERNAL_IP}    DNS only

4. SSL/TLS → Overview → set mode to **Full** (or Full strict after certs).
5. Wait until Cloudflare shows the zone Active, then press Enter here.

EOF

read -rp "Cloudflare DNS ready (grey cloud) and nameservers active? [Enter] " _

echo "==> Configuring VM for ${DOMAIN}..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  set -e
  cd /opt/commercialbrainz
  sudo git fetch origin main
  sudo git reset --hard origin/main

  set_env() {
    local key=\$1 value=\$2
    if grep -q \"^\${key}=\" .env; then
      sudo sed -i \"s|^\${key}=.*|\${key}=\${value}|\" .env
    else
      echo \"\${key}=\${value}\" | sudo tee -a .env >/dev/null
    fi
  }

  set_env DOMAIN '${DOMAIN}'
  set_env DOMAIN_ALIASES '${DOMAIN_ALIASES}'
  set_env ACME_EMAIL '${ACME_EMAIL}'
  set_env APP_PUBLIC_URL 'https://${DOMAIN}'
  set_env API_PUBLIC_URL 'https://${DOMAIN}'
  set_env CORS_ORIGINS '${CORS_ORIGINS}'

  sudo bash infra/gcloud/write-compose-env.sh /opt/commercialbrainz
  sudo bash infra/gcloud/generate-caddyfile.sh \
    infra/caddy/Caddyfile.runtime \
    '${DOMAIN}' \
    '${ACME_EMAIL}' \
    '${DOMAIN_ALIASES}'

  COMPOSE='docker compose --env-file infra/compose.env -f infra/docker-compose.yml -f infra/docker-compose.vm.yml'
  sudo \$COMPOSE up -d --force-recreate --no-deps caddy api web
  echo 'Waiting for HTTPS certificate (Let's Encrypt)...'
  for i in \$(seq 1 36); do
    if curl -sf 'https://${DOMAIN}/health' >/dev/null 2>&1; then
      echo 'HTTPS is up for ${DOMAIN}'
      exit 0
    fi
    sleep 10
  done
  echo 'Not ready yet — on the VM check: sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs caddy --tail=80'
  exit 1
"

cat <<EOF

==> Done (if HTTPS probe succeeded)

  Site:  https://${DOMAIN}/
  WWW:   https://www.${DOMAIN}/  (redirects to apex)
  Docs:  https://${DOMAIN}/docs
  Old:   https://${DUCKDNS_FQDN}/  (still served if kept as alias)

Optional — turn on Cloudflare proxy (orange cloud) after certs work:
  1. DNS → edit A @ and www → Proxied
  2. SSL/TLS → Full (strict)
  3. (Optional) Speed → Caching level standard; skip paid add-ons

Cost: Cloudflare Free \$0 + your domain registration + existing free-tier VM.
EOF
