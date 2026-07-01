#!/usr/bin/env bash
# Pull latest code and rebuild API/worker on the CommercialBrainz VM.
# Use this after pushing fixes — a plain "up -d" may reuse a cached image
# without the new Alembic migrations.
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

gcloud config set project "$PROJECT_ID" >/dev/null

ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  exit 1
fi

echo "==> Deploying to $VM_NAME ($ZONE)..."

gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  set -euo pipefail
  cd /opt/commercialbrainz
  echo '--- git pull ---'
  sudo git pull origin main
  echo '--- git rev ---'
  sudo git rev-parse --short HEAD
  echo '--- rebuild api + worker (no cache) ---'
  sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml build --no-cache api worker
  echo '--- restart stack ---'
  sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml up -d
  echo '--- waiting for api health ---'
  for i in \$(seq 1 30); do
    if sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml exec -T api \
      python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')\" 2>/dev/null; then
      echo 'API healthy'
      exit 0
    fi
    sleep 10
  done
  echo 'API not healthy yet — recent logs:'
  sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs api --tail=40
  exit 1
"

echo ""
echo "==> Done. Run ./scripts/diagnose-gcloud-vm.sh to verify."
