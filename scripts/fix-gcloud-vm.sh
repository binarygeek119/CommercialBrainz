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

echo "==> git pull"
if [[ "$(id -u)" -eq 0 ]]; then
  git pull origin main || true
else
  sudo git pull origin main || true
fi
git rev-parse --short HEAD

echo "==> Full stack status"
$COMPOSE ps -a

echo ""
echo "==> Regenerate Caddyfile"
DOMAIN="$(grep '^DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)"
ACME_EMAIL="$(grep '^ACME_EMAIL=' .env 2>/dev/null | cut -d= -f2- || true)"
bash infra/gcloud/generate-caddyfile.sh infra/caddy/Caddyfile.runtime "${DOMAIN}" "${ACME_EMAIL}"

echo ""
echo "==> Rebuild and start full stack"
$COMPOSE build api worker web
$COMPOSE up -d postgres redis
$COMPOSE up -d --force-recreate api worker web

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
