#!/usr/bin/env bash
# Recover from Caddy 502 / partial stack after deploy on the VM.
# Run on the VM (or via gcloud compute ssh ... --command="sudo bash -s" < scripts/fix-gcloud-vm.sh)
#
# From your laptop:
#   gcloud compute ssh commercialbrainz-vm --zone=us-central1-b \
#     --command='sudo bash /opt/commercialbrainz/scripts/fix-gcloud-vm.sh'
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/commercialbrainz}"
cd "$APP_DIR"

if [[ "$(id -u)" -eq 0 ]]; then
  COMPOSE="docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml"
else
  COMPOSE="sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml"
fi

# Sync first, then re-exec so the remainder of this run uses the new script
# inode (bash keeps reading the old file after `git reset` replaces it).
if [[ "${CB_REPO_SYNCED:-}" != "1" ]]; then
  echo "==> Sync to origin/main (discard local tracked changes; keep .env)"
  if [[ "$(id -u)" -eq 0 ]]; then
    git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
    git fetch origin main
    git reset --hard origin/main
    git clean -fd -e .env -e infra/caddy/Caddyfile.runtime
    git rev-parse --short HEAD
  else
    sudo git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
    sudo git fetch origin main
    sudo git reset --hard origin/main
    sudo git clean -fd -e .env -e infra/caddy/Caddyfile.runtime
    sudo git rev-parse --short HEAD
  fi
  export CB_REPO_SYNCED=1
  echo "==> Re-executing deploy script from synced tree"
  if [[ "$(id -u)" -eq 0 ]]; then
    exec env CB_REPO_SYNCED=1 IMAGE_TAG="${IMAGE_TAG:-}" bash "$APP_DIR/scripts/fix-gcloud-vm.sh"
  else
    exec sudo --preserve-env=IMAGE_TAG,CB_REPO_SYNCED \
      env CB_REPO_SYNCED=1 IMAGE_TAG="${IMAGE_TAG:-}" \
      bash "$APP_DIR/scripts/fix-gcloud-vm.sh"
  fi
fi

echo "==> Full stack status"
$COMPOSE ps -a

echo ""
echo "==> Regenerate Caddyfile"
DOMAIN="$(grep '^DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)"
ACME_EMAIL="$(grep '^ACME_EMAIL=' .env 2>/dev/null | cut -d= -f2- || true)"
bash infra/gcloud/generate-caddyfile.sh infra/caddy/Caddyfile.runtime "${DOMAIN}" "${ACME_EMAIL}"

echo ""
# Prefer images prebuilt+pushed by GitHub Actions (GHCR). Fall back to on-VM
# build only if pull fails (e.g. first boot before packages exist / private).
# IMAGE_TAG from the caller wins; otherwise .env / latest.
_DEPLOY_IMAGE_TAG="${IMAGE_TAG:-}"
if [[ -f .env ]]; then
  _env_val() { grep -E "^${1}=" .env 2>/dev/null | head -1 | cut -d= -f2- || true; }
  : "${GHCR_TOKEN:=$(_env_val GHCR_TOKEN)}"
  : "${GHCR_USER:=$(_env_val GHCR_USER)}"
  : "${_DEPLOY_IMAGE_TAG:=$(_env_val IMAGE_TAG)}"
fi
export IMAGE_TAG="${_DEPLOY_IMAGE_TAG:-latest}"
echo "==> App images IMAGE_TAG=${IMAGE_TAG}"

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "==> docker login ghcr.io"
  # Root and non-root compose paths both need credentials in the docker config
  # used by the daemon client (`sudo docker` when not root).
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "${GHCR_TOKEN}" | docker login ghcr.io \
      -u "${GHCR_USER:-binarygeek119}" --password-stdin
  else
    echo "${GHCR_TOKEN}" | sudo docker login ghcr.io \
      -u "${GHCR_USER:-binarygeek119}" --password-stdin
  fi
fi

echo "==> Pull prebuilt images from GHCR"
# Prefer explicit docker pull so failures are obvious (compose may mask them).
API_IMAGE="ghcr.io/binarygeek119/commercialbrainz-api:${IMAGE_TAG}"
WEB_IMAGE="ghcr.io/binarygeek119/commercialbrainz-web:${IMAGE_TAG}"
if [[ "$(id -u)" -eq 0 ]]; then DOCKER=docker; else DOCKER="sudo docker"; fi
if $DOCKER pull "$API_IMAGE" && $DOCKER pull "$WEB_IMAGE"; then
  echo "==> Starting stack from pulled images (no on-VM build)"
  $COMPOSE up -d postgres redis
  $COMPOSE up -d --pull missing --force-recreate --no-build api worker web
else
  echo "WARN: GHCR pull failed — falling back to on-VM compose build"
  $COMPOSE build api worker web
  $COMPOSE up -d postgres redis
  $COMPOSE up -d --force-recreate api worker web
fi

echo ""
echo "==> Waiting for API (migrations + uvicorn)..."
for i in $(seq 1 36); do
  if $COMPOSE exec -T api \
    python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; then
    echo "API healthy"
    break
  fi
  if [[ $i -eq 36 ]]; then
    echo "ERROR: API did not become healthy — check migrations:"
    $COMPOSE logs api --tail=60
    exit 1
  fi
  sleep 10
done

echo ""
echo "==> Recreate Caddy (refresh Docker DNS to api/web)"
$COMPOSE up -d --force-recreate --no-deps caddy
sleep 5

echo ""
echo "==> Container ages (web/caddy should match api after deploy)"
$COMPOSE ps -a --format 'table {{.Name}}\t{{.Status}}\t{{.RunningFor}}' api worker web caddy 2>/dev/null || $COMPOSE ps api worker web caddy

echo ""
echo "==> Test login endpoint (expect 401 for bad password, not 503)"
curl -s -o /tmp/cb-login-test.json -w "HTTP %{http_code}\n" \
  -X POST http://127.0.0.1/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"__login_probe__","password":"wrong"}' || true
cat /tmp/cb-login-test.json 2>/dev/null || true

echo ""
echo "==> Verify database"
HEALTH="$(curl -sf http://127.0.0.1/health || true)"
echo "$HEALTH"
echo "$HEALTH" | grep -q '"database":"ok"' && echo "OK: database connected" || {
  echo "FAIL: database not connected — fixing .env and retrying migrations"
  grep -q '^DATABASE_URL=' .env && sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://commercialbrainz:commercialbrainz@postgres:5432/commercialbrainz|' .env \
    || echo 'DATABASE_URL=postgresql+asyncpg://commercialbrainz:commercialbrainz@postgres:5432/commercialbrainz' >> .env
  grep -q '^DATABASE_URL_SYNC=' .env && sed -i 's|^DATABASE_URL_SYNC=.*|DATABASE_URL_SYNC=postgresql://commercialbrainz:commercialbrainz@postgres:5432/commercialbrainz|' .env \
    || echo 'DATABASE_URL_SYNC=postgresql://commercialbrainz:commercialbrainz@postgres:5432/commercialbrainz' >> .env
  grep -q '^REDIS_URL=' .env && sed -i 's|^REDIS_URL=.*|REDIS_URL=redis://redis:6379/0|' .env \
    || echo 'REDIS_URL=redis://redis:6379/0' >> .env
  $COMPOSE up -d --force-recreate api worker
  sleep 15
  curl -sf http://127.0.0.1/health || true
  $COMPOSE logs api --tail=40
}

echo ""
echo "==> Verify"
$COMPOSE ps
echo ""
curl -sf http://127.0.0.1/health && echo "OK: /health via Caddy" || {
  echo "FAIL: /health via Caddy"
  $COMPOSE logs caddy --tail=30
  exit 1
}
curl -sf -o /dev/null http://127.0.0.1/ && echo "OK: / web UI via Caddy" || {
  echo "WARN: / web UI failed (check web container)"
  $COMPOSE logs web --tail=20
}

echo ""
echo "==> Done"
