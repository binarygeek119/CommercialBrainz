#!/usr/bin/env bash
# Diagnose CommercialBrainz VM connectivity (DuckDNS, ports, Docker).
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz ./scripts/diagnose-gcloud-vm.sh
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
VM_NAME="${VM_NAME:-commercialbrainz-vm}"
DUCKDNS_DOMAIN="${DUCKDNS_DOMAIN:-commercialbrainz}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Finding VM..."
ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  exit 1
fi
echo "    VM:   $VM_NAME"
echo "    Zone: $ZONE"

EXTERNAL_IP="$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
echo "    GCP IP: $EXTERNAL_IP"

echo ""
echo "==> DuckDNS check..."
DUCKDNS_IP=""
if command -v dig >/dev/null 2>&1; then
  DUCKDNS_IP="$(dig +short "${DUCKDNS_DOMAIN}.duckdns.org" @8.8.8.8 2>/dev/null | tail -1 || true)"
  if [[ -z "$DUCKDNS_IP" ]]; then
    DUCKDNS_IP="$(dig +short "${DUCKDNS_DOMAIN}.duckdns.org" 2>/dev/null | tail -1 || true)"
  fi
fi
if [[ -z "$DUCKDNS_IP" ]] && command -v nslookup >/dev/null 2>&1; then
  DUCKDNS_IP="$(nslookup "${DUCKDNS_DOMAIN}.duckdns.org" 8.8.8.8 2>/dev/null | awk '/^Address: / { print $2 }' | tail -1 || true)"
fi
if [[ -n "$DUCKDNS_IP" ]]; then
  echo "    DuckDNS ${DUCKDNS_DOMAIN}.duckdns.org → $DUCKDNS_IP"
  if [[ "$DUCKDNS_IP" == "$EXTERNAL_IP" ]]; then
    echo "    OK: DuckDNS matches GCP IP"
  else
    echo "    MISMATCH: Run setup-duckdns-gcloud.sh or wait for cron (updates every 5 min)"
  fi
else
  echo "    Could not resolve ${DUCKDNS_DOMAIN}.duckdns.org"
fi

check_url() {
  local label="$1"
  local url="$2"
  printf "    %-28s " "$label"
  if curl -sf --max-time 10 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -qE '^(200|304)$'; then
    echo "OK  $url"
    return 0
  fi
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "fail")"
  echo "FAIL ($code) $url"
  return 1
}

echo ""
echo "==> HTTP checks (port 80 — preferred)..."
check_url "Web UI" "http://${EXTERNAL_IP}/" || true
check_url "API health" "http://${EXTERNAL_IP}/health" || true
check_url "API docs" "http://${EXTERNAL_IP}/docs" || true
if [[ -n "$DUCKDNS_IP" ]]; then
  check_url "HTTPS docs" "https://${DUCKDNS_DOMAIN}.duckdns.org/docs" || true
fi

echo ""
echo "==> HTTP checks (port 8000 — internal only on VM; failure here is normal)..."
check_url "Direct API" "http://${EXTERNAL_IP}:8000/health" || true
check_url "Direct docs" "http://${EXTERNAL_IP}:8000/docs" || true

echo ""
echo "==> Docker on VM..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  if [[ -d /opt/commercialbrainz ]]; then
    cd /opt/commercialbrainz
    echo '--- git rev ---'
    sudo git rev-parse --short HEAD 2>/dev/null || echo '(unknown)'
    sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml ps -a
    echo '--- api container state ---'
    sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml ps api web worker postgres caddy 2>/dev/null || true
    echo '--- stale container warning ---'
    API_AGE=\$(sudo docker inspect --format='{{.Created}}' infra-api-1 2>/dev/null || echo '')
    WEB_AGE=\$(sudo docker inspect --format='{{.Created}}' infra-web-1 2>/dev/null || echo '')
    CADDY_ID=\$(sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml ps -q caddy 2>/dev/null | head -1)
    CADDY_AGE=\$(sudo docker inspect --format='{{.Created}}' \"\$CADDY_ID\" 2>/dev/null || echo '')
    if [[ -n \"\$API_AGE\" && -n \"\$WEB_AGE\" && \"\$API_AGE\" != \"\$WEB_AGE\" ]]; then
      echo \"WARN: web container older/different than api — run: sudo bash scripts/fix-gcloud-vm.sh\"
    fi
    if [[ -n \"\$API_AGE\" && -n \"\$CADDY_AGE\" && \"\$CADDY_AGE\" != \"\$API_AGE\" ]]; then
      echo \"WARN: caddy container older/different than api — Caddy may proxy stale IPs (502). Run fix-gcloud-vm.sh\"
    fi
    echo '--- migration fix in api image? ---'
    sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml run --rm --no-deps api \
      grep -q 'videohashstatus AS ENUM' alembic/versions/004_media_fingerprints.py \
      && echo 'OK: migration 004 has enum CREATE' \
      || echo 'MISSING: rebuild api with ./scripts/deploy-gcloud-vm.sh'
    echo '--- localhost via caddy ---'
    curl -sf http://127.0.0.1/health && echo 'OK: localhost/health via caddy' \
      || echo 'FAIL: localhost/health (run: sudo bash scripts/fix-gcloud-vm.sh)'
    echo '--- caddy -> api direct ---'
    sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml exec -T caddy \
      wget -qO- http://api:8000/health 2>/dev/null && echo 'OK: caddy can reach api:8000' \
      || echo 'FAIL: caddy cannot reach api (recreate stack: scripts/fix-gcloud-vm.sh)'
    echo '--- recent caddy logs ---'
    sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs caddy --tail=10
    echo '--- recent api logs ---'
    sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs api --tail=20
  else
    echo 'Repo not at /opt/commercialbrainz — startup may still be running'
    sudo tail -20 /var/log/commercialbrainz-startup.log 2>/dev/null || true
  fi
" 2>/dev/null || echo "    (SSH failed — check gcloud auth)"

echo ""
echo "==> Recommended URLs"
echo "    Web:  https://${DUCKDNS_DOMAIN}.duckdns.org/"
echo "    Docs: https://${DUCKDNS_DOMAIN}.duckdns.org/docs"
