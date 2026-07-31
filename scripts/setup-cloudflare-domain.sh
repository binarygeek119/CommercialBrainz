#!/usr/bin/env bash
# Point CommercialBrainz at commercialbrainz.org via Cloudflare Free.
# Cloudflare terminates visitor SSL; Caddy uses a free Cloudflare Origin CA cert.
#
# Prerequisites:
#   - Domain on Cloudflare Free; nameservers active
#   - A @ and www → VM IP, Proxied (orange), SSL mode Full (strict)
#   - Origin CA cert + key downloaded from Cloudflare
#   - gcloud authenticated; VM already running CommercialBrainz
#
# Usage:
#   GCP_PROJECT_ID=your-project \
#   DOMAIN=commercialbrainz.org \
#   ACME_EMAIL=you@example.com \
#   ORIGIN_CERT=$HOME/cb-origin.crt \
#   ORIGIN_KEY=$HOME/cb-origin.key \
#     ./scripts/setup-cloudflare-domain.sh
#
# Optional:
#   VM_NAME=commercialbrainz-public   # public VM (default)
#   DOMAIN_ALIASES=www.commercialbrainz.org
#   KEEP_DUCKDNS=0                 # default 0 on public VM
#   CADDY_TLS_MODE=origin          # default; use "auto" only for grey-cloud Let's Encrypt
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-public}"
DOMAIN="${DOMAIN:-commercialbrainz.org}"
ACME_EMAIL="${ACME_EMAIL:-}"
DOMAIN_ALIASES="${DOMAIN_ALIASES:-www.${DOMAIN}}"
KEEP_DUCKDNS="${KEEP_DUCKDNS:-0}"
DUCKDNS_FQDN="${DUCKDNS_FQDN:-commercialbrainz.duckdns.org}"
CADDY_TLS_MODE="${CADDY_TLS_MODE:-origin}"
ORIGIN_CERT="${ORIGIN_CERT:-}"
ORIGIN_KEY="${ORIGIN_KEY:-}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi
if [[ -z "$ACME_EMAIL" ]]; then
  read -rp "Admin / ACME email: " ACME_EMAIL
fi

if [[ "$CADDY_TLS_MODE" == "origin" ]]; then
  if [[ -z "$ORIGIN_CERT" || -z "$ORIGIN_KEY" ]]; then
    echo "ORIGIN_CERT and ORIGIN_KEY are required for CADDY_TLS_MODE=origin"
    echo "Create them in Cloudflare → SSL/TLS → Origin Server → Create Certificate"
    read -rp "Path to Origin Certificate (.crt/.pem): " ORIGIN_CERT
    read -rp "Path to Private Key (.key): " ORIGIN_KEY
  fi
  if [[ ! -f "$ORIGIN_CERT" || ! -f "$ORIGIN_KEY" ]]; then
    echo "ERROR: cert or key file not found"
    exit 1
  fi
fi

if [[ "$KEEP_DUCKDNS" == "1" ]]; then
  if [[ ",${DOMAIN_ALIASES}," != *",${DUCKDNS_FQDN},"* ]]; then
    DOMAIN_ALIASES="${DOMAIN_ALIASES},${DUCKDNS_FQDN}"
  fi
fi
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

if [[ "$CADDY_TLS_MODE" == "origin" ]]; then
  cat <<EOF

═══════════════════════════════════════════════════════════════════
  Cloudflare Free — edge SSL (\$0/mo). Confirm before continuing:
═══════════════════════════════════════════════════════════════════

1. Site ${DOMAIN} on https://dash.cloudflare.com (Free).
2. Registrar nameservers → Cloudflare NS.
3. DNS A @ and www → ${EXTERNAL_IP}  (Proxied / orange cloud).
4. SSL/TLS → Full (strict).
5. Origin Server certificate created for ${DOMAIN} + *.${DOMAIN}
   (files: ${ORIGIN_CERT} , ${ORIGIN_KEY}).

EOF
else
  cat <<EOF

═══════════════════════════════════════════════════════════════════
  Let's Encrypt mode (grey cloud until certs work)
═══════════════════════════════════════════════════════════════════

A @ and www → ${EXTERNAL_IP} as DNS only (grey), then run this script.
After HTTPS works you may switch to Proxied + Full strict (prefer Origin CA).

EOF
fi

read -rp "Cloudflare ready? [Enter] " _

REMOTE_CERT_DIR="/opt/commercialbrainz/data/caddy/certs"
if [[ "$CADDY_TLS_MODE" == "origin" ]]; then
  echo "==> Uploading Origin CA cert to VM..."
  gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="sudo mkdir -p ${REMOTE_CERT_DIR} && sudo chmod 755 /opt/commercialbrainz/data /opt/commercialbrainz/data/caddy ${REMOTE_CERT_DIR}"
  gcloud compute scp "$ORIGIN_CERT" "${VM_NAME}:/tmp/cb-origin.crt" --zone="$ZONE"
  gcloud compute scp "$ORIGIN_KEY" "${VM_NAME}:/tmp/cb-origin.key" --zone="$ZONE"
  gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
    sudo mv /tmp/cb-origin.crt ${REMOTE_CERT_DIR}/origin.crt
    sudo mv /tmp/cb-origin.key ${REMOTE_CERT_DIR}/origin.key
    sudo chmod 644 ${REMOTE_CERT_DIR}/origin.crt
    sudo chmod 600 ${REMOTE_CERT_DIR}/origin.key
  "
fi

echo "==> Configuring VM for ${DOMAIN} (tls=${CADDY_TLS_MODE})..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  set -e
  cd /opt/commercialbrainz
  sudo git fetch origin cloudflare testing
  # Prefer cloudflare for public domain setup; fall back to testing.
  if sudo git rev-parse --verify origin/cloudflare >/dev/null 2>&1; then
    sudo git checkout -B cloudflare origin/cloudflare
    sudo git reset --hard origin/cloudflare
  elif sudo git rev-parse --verify origin/testing >/dev/null 2>&1; then
    sudo git checkout -B testing origin/testing
    sudo git reset --hard origin/testing
  else
    sudo git checkout -B testing origin/google
    sudo git reset --hard origin/google
  fi

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
  set_env CADDY_TLS_MODE '${CADDY_TLS_MODE}'
  set_env APP_PUBLIC_URL 'https://${DOMAIN}'
  set_env API_PUBLIC_URL 'https://${DOMAIN}'
  set_env CORS_ORIGINS '${CORS_ORIGINS}'
  set_env PUBLIC_SITE 'true'
  set_env APP_ENV 'production'

  sudo bash infra/gcloud/write-compose-env.sh /opt/commercialbrainz
  sudo bash infra/gcloud/generate-caddyfile.sh \
    infra/caddy/Caddyfile.runtime \
    '${DOMAIN}' \
    '${ACME_EMAIL}' \
    '${DOMAIN_ALIASES}' \
    '${CADDY_TLS_MODE}'

  COMPOSE='docker compose --project-directory infra --env-file infra/compose.env -f infra/docker-compose.yml -f infra/docker-compose.vm.yml'
  sudo \$COMPOSE up -d --force-recreate --no-deps caddy api web
  echo 'Waiting for https://${DOMAIN}/health ...'
  for i in \$(seq 1 36); do
    if curl -sf 'https://${DOMAIN}/health' >/dev/null 2>&1; then
      echo 'HTTPS is up for ${DOMAIN}'
      exit 0
    fi
    sleep 10
  done
  echo 'Not ready yet — check Caddy logs and Cloudflare SSL mode / Origin cert.'
  sudo \$COMPOSE logs caddy --tail=40 || true
  exit 1
"

cat <<EOF

==> Done (if HTTPS probe succeeded)

  Site:  https://${DOMAIN}/
  WWW:   https://www.${DOMAIN}/  (redirects to apex)
  Docs:  https://${DOMAIN}/docs
  Old:   https://${DUCKDNS_FQDN}/  (LE alias if kept)

Cloudflare should stay Proxied + Full (strict).
Cost: Free plan + your domain + public VM (second e2-micro is billed; see docs/cloudflare-domain.md).
EOF
