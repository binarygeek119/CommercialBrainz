#!/usr/bin/env bash
# CommercialBrainz VM startup script (runs on first boot via GCE metadata)
# Installs Docker, clones the repo, and starts the stack on a free e2-micro.
set -euo pipefail

LOG="/var/log/commercialbrainz-startup.log"
exec > >(tee -a "$LOG") 2>&1

echo "==> CommercialBrainz VM startup $(date -Is)"

get_meta() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" 2>/dev/null || true
}

APP_DIR="${APP_DIR:-/opt/commercialbrainz}"
REPO_URL="$(get_meta repo-url)"
REPO_URL="${REPO_URL:-https://github.com/binarygeek119/CommercialBrainz.git}"
REPO_BRANCH="$(get_meta repo-branch)"
REPO_BRANCH="${REPO_BRANCH:-main}"
WEB_PORT="${WEB_PORT:-80}"

# e2-micro has 1 GB RAM — add swap so Docker builds don't OOM
if ! swapon --show | grep -q /swapfile; then
  echo "==> Creating 2G swap file..."
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Installing Docker..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME:-jammy}") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable docker
systemctl start docker

echo "==> Cloning CommercialBrainz..."
mkdir -p "$(dirname "$APP_DIR")"
if [[ -d "$APP_DIR/.git" ]]; then
  cd "$APP_DIR"
  git fetch origin
  git checkout "$REPO_BRANCH"
  git pull origin "$REPO_BRANCH"
else
  git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi

echo "==> Configuring environment..."

set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

if [[ ! -f .env ]]; then
  cp .env.example .env
  SECRET=$(openssl rand -base64 32)
  sed -i "s/change-me-to-a-long-random-string/$SECRET/" .env
fi

# Docker Compose service names — localhost in .env breaks API/worker inside containers.
set_env "DATABASE_URL" "postgresql+asyncpg://commercialbrainz:commercialbrainz@postgres:5432/commercialbrainz"
set_env "DATABASE_URL_SYNC" "postgresql://commercialbrainz:commercialbrainz@postgres:5432/commercialbrainz"
set_env "REDIS_URL" "redis://redis:6379/0"

DUCKDNS_DOMAIN="$(get_meta duckdns-domain)"
DUCKDNS_TOKEN="$(get_meta duckdns-token)"
ACME_EMAIL="$(get_meta acme-email)"

EXTERNAL_IP=$(curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)

if [[ -n "$DUCKDNS_DOMAIN" ]]; then
  FQDN="${DUCKDNS_DOMAIN}.duckdns.org"
  set_env "DOMAIN" "$FQDN"
  if [[ -n "$ACME_EMAIL" ]]; then
    set_env "ACME_EMAIL" "$ACME_EMAIL"
    set_env "CORS_ORIGINS" "https://${FQDN},http://${FQDN},http://${EXTERNAL_IP}"
    echo "==> HTTPS enabled for ${FQDN} (Let's Encrypt via Caddy)"
  else
    set_env "CORS_ORIGINS" "http://${FQDN},http://${EXTERNAL_IP}"
    echo "==> WARNING: ACME_EMAIL not set — HTTPS disabled. Set metadata acme-email and redeploy."
  fi
fi

bash "$APP_DIR/infra/gcloud/generate-caddyfile.sh" \
  "$APP_DIR/infra/caddy/Caddyfile.runtime" \
  "${DUCKDNS_DOMAIN:+$DUCKDNS_DOMAIN.duckdns.org}" \
  "${ACME_EMAIL:-}"

echo "==> Starting containers (pull prebuilt GHCR images; build only if pull fails)..."
export IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE="docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml"
if $COMPOSE pull api worker web; then
  $COMPOSE up -d --pull missing --no-build
else
  echo "WARN: GHCR pull failed — building on VM (slow on e2-micro)"
  $COMPOSE build
  $COMPOSE up -d
fi

echo "==> Waiting for services (Caddy + API)..."
for i in $(seq 1 90); do
  if curl -sf http://localhost/health >/dev/null 2>&1; then
    echo "    Stack is healthy."
    break
  fi
  sleep 5
done

echo "==> Verifying endpoints..."
curl -sf http://localhost/health >/dev/null && echo "    HTTP  /health OK" || echo "    WARNING: /health failed"
curl -sf http://localhost/docs >/dev/null && echo "    HTTP  /docs OK" || echo "    WARNING: /docs failed"
if [[ -n "${DUCKDNS_DOMAIN:-}" && -n "${ACME_EMAIL:-}" ]]; then
  for i in $(seq 1 30); do
    if curl -sf "https://${DUCKDNS_DOMAIN}.duckdns.org/health" >/dev/null 2>&1; then
      echo "    HTTPS /health OK"
      break
    fi
    echo "    Waiting for Let's Encrypt certificate (attempt $i)..."
    sleep 10
  done
fi

# Optional admin seed from instance metadata
ADMIN_EMAIL=$(curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/admin-email 2>/dev/null || true)
ADMIN_USERNAME=$(curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/admin-username 2>/dev/null || true)
ADMIN_PASSWORD=$(curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/admin-password 2>/dev/null || true)

if [[ -n "$ADMIN_EMAIL" && -n "$ADMIN_USERNAME" && -n "$ADMIN_PASSWORD" ]]; then
  echo "==> Seeding admin user..."
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml exec -T api commercialbrainz seed-admin \
    --email "$ADMIN_EMAIL" \
    --username "$ADMIN_USERNAME" \
    --password "$ADMIN_PASSWORD" || true
fi

# --- DuckDNS cron (optional) ---
if [[ -n "$DUCKDNS_DOMAIN" && -n "$DUCKDNS_TOKEN" ]]; then
  echo "==> Configuring DuckDNS cron (${DUCKDNS_DOMAIN}.duckdns.org)..."
  mkdir -p /etc/commercialbrainz
  cat > /etc/commercialbrainz/duckdns.env <<EOF
DUCKDNS_DOMAIN=$DUCKDNS_DOMAIN
DUCKDNS_TOKEN=$DUCKDNS_TOKEN
EOF
  chmod 600 /etc/commercialbrainz/duckdns.env
  install -m 0755 "$APP_DIR/infra/gcloud/duckdns-update.sh" /usr/local/bin/duckdns-update
  cat > /etc/cron.d/commercialbrainz-duckdns <<'CRON'
# Refresh DuckDNS when GCE ephemeral IP changes (every 5 minutes)
*/5 * * * * root /usr/local/bin/duckdns-update
CRON
  /usr/local/bin/duckdns-update || true
fi

echo ""
echo "==> CommercialBrainz VM setup complete!"
echo "    Web UI:  http://${EXTERNAL_IP}/"
echo "    Docs:    http://${EXTERNAL_IP}/docs"
if [[ -n "$DUCKDNS_DOMAIN" ]]; then
  echo "    DuckDNS: http://${DUCKDNS_DOMAIN}.duckdns.org/"
  echo "    Docs:    http://${DUCKDNS_DOMAIN}.duckdns.org/docs"
  if [[ -n "$ACME_EMAIL" ]]; then
    echo "    HTTPS:   https://${DUCKDNS_DOMAIN}.duckdns.org/"
    echo "    Docs:    https://${DUCKDNS_DOMAIN}.duckdns.org/docs"
  fi
fi
echo "    Log:     $LOG"
