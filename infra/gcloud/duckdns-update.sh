#!/usr/bin/env bash
# Update DuckDNS A record to this machine's public IP.
# Reads config from /etc/commercialbrainz/duckdns.env
#
# Env file format:
#   DUCKDNS_DOMAIN=myapp        # subdomain only (myapp.duckdns.org)
#   DUCKDNS_TOKEN=your-token
#
set -euo pipefail

CONFIG="${DUCKDNS_CONFIG:-/etc/commercialbrainz/duckdns.env}"
LOG="${DUCKDNS_LOG:-/var/log/duckdns-update.log}"

if [[ ! -f "$CONFIG" ]]; then
  exit 0
fi

# shellcheck source=/dev/null
source "$CONFIG"

if [[ -z "${DUCKDNS_DOMAIN:-}" || -z "${DUCKDNS_TOKEN:-}" ]]; then
  echo "$(date -Is) duckdns: missing domain or token in $CONFIG" >> "$LOG"
  exit 1
fi

PUBLIC_IP=$(curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip \
  2>/dev/null || curl -sf https://api.ipify.org || true)

if [[ -z "$PUBLIC_IP" ]]; then
  echo "$(date -Is) duckdns: could not determine public IP" >> "$LOG"
  exit 1
fi

RESPONSE=$(curl -sf "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${PUBLIC_IP}" || echo "KO")

echo "$(date -Is) duckdns: ${DUCKDNS_DOMAIN}.duckdns.org -> ${PUBLIC_IP} (${RESPONSE})" >> "$LOG"

if [[ "$RESPONSE" != "OK" ]]; then
  exit 1
fi
