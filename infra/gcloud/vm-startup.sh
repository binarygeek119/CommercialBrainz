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
REPO_URL="${REPO_URL:-https://github.com/binarygeek119/spotbrainz.git}"
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
if [[ ! -f .env ]]; then
  cp .env.example .env
  SECRET=$(openssl rand -base64 32)
  sed -i "s/change-me-to-a-long-random-string/$SECRET/" .env
fi

echo "==> Building and starting containers (this may take 10–20 min on e2-micro)..."
docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml build
docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml up -d

echo "==> Waiting for API health..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "API is healthy."
    break
  fi
  sleep 5
done

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

EXTERNAL_IP=$(curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)

# --- DuckDNS (optional) ---
DUCKDNS_DOMAIN="$(get_meta duckdns-domain)"
DUCKDNS_TOKEN="$(get_meta duckdns-token)"

setup_duckdns() {
  if [[ -z "$DUCKDNS_DOMAIN" || -z "$DUCKDNS_TOKEN" ]]; then
    return 0
  fi

  echo "==> Configuring DuckDNS (${DUCKDNS_DOMAIN}.duckdns.org)..."
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

  DUCKDNS_URL="http://${DUCKDNS_DOMAIN}.duckdns.org"
  if [[ -f "$APP_DIR/.env" ]]; then
    if grep -q '^CORS_ORIGINS=' "$APP_DIR/.env"; then
      sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${DUCKDNS_URL},http://${EXTERNAL_IP},http://localhost:5173|" "$APP_DIR/.env"
    else
      echo "CORS_ORIGINS=${DUCKDNS_URL},http://${EXTERNAL_IP},http://localhost:5173" >> "$APP_DIR/.env"
    fi
    docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml up -d api web 2>/dev/null || true
  fi
}

setup_duckdns

echo ""
echo "==> CommercialBrainz VM setup complete!"
echo "    Web UI:  http://${EXTERNAL_IP}:${WEB_PORT}"
echo "    API:     http://${EXTERNAL_IP}:8000"
echo "    Docs:    http://${EXTERNAL_IP}:8000/docs"
if [[ -n "$DUCKDNS_DOMAIN" ]]; then
  echo "    DuckDNS: http://${DUCKDNS_DOMAIN}.duckdns.org/"
  echo "    DuckDNS: http://${DUCKDNS_DOMAIN}.duckdns.org:8000/docs"
fi
echo "    Log:     $LOG"
