#!/usr/bin/env bash
# Create (or reset) the public CommercialBrainz GCE VM for Cloudflare.
#
# This is separate from the testing VM (commercialbrainz-vm / DuckDNS).
#
#   testing branch    → commercialbrainz-vm   → https://commercialbrainz.duckdns.org/
#   cloudflare branch → commercialbrainz-public  → https://commercialbrainz.org/
#
# Note: GCP Always Free includes only ONE e2-micro. A second VM is billed
# (still cheap on e2-micro). Prefer CREATE_STATIC_IP=1 so Cloudflare A records
# do not break when the ephemeral IP changes.
#
# Prerequisites: gcloud authenticated; billing enabled on the public project.
# Prefer GCP project commercialbrainz-public (see scripts/setup-public-gcp-project.sh).
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz-public \
#   ADMIN_EMAIL=you@example.com \
#   ADMIN_USERNAME=admin \
#   ADMIN_PASSWORD='…' \
#   ACME_EMAIL=you@example.com \
#     ./scripts/setup-cloudflare-vm.sh
#
# Then point Cloudflare DNS at the printed IP and run setup-cloudflare-domain.sh
# (see docs/cloudflare-domain.md).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

export VM_NAME="${VM_NAME:-commercialbrainz-public}"
export REPO_BRANCH="${REPO_BRANCH:-cloudflare}"
export CREATE_STATIC_IP="${CREATE_STATIC_IP:-1}"
export MACHINE_TYPE="${MACHINE_TYPE:-e2-micro}"
export DISK_SIZE="${DISK_SIZE:-40GB}"

# Public VM must not take DuckDNS credentials (testing VM owns DuckDNS).
unset DUCKDNS_DOMAIN DUCKDNS_TOKEN 2>/dev/null || true

echo "==> Public Cloudflare VM"
echo "    VM_NAME=${VM_NAME}"
echo "    REPO_BRANCH=${REPO_BRANCH}"
echo "    CREATE_STATIC_IP=${CREATE_STATIC_IP}"
echo "    (DuckDNS left unset — use commercialbrainz-vm for testing)"
echo ""

exec bash "$SCRIPT_DIR/setup-gcloud-vm.sh"
