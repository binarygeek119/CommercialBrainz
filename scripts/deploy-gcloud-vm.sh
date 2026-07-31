#!/usr/bin/env bash
# Deploy prebuilt images to the matching CommercialBrainz GCE VM.
# CI builds/pushes api+web to GHCR; this script syncs compose/scripts on the
# VM and pulls those images (no on-VM docker build in the common path).
#
# Usage:
#   GCP_PROJECT_ID=commercialbrainz APP_BRANCH=testing ./scripts/deploy-gcloud-vm.sh
#   IMAGE_TAG=<git-sha> APP_BRANCH=cloudflare GCP_PROJECT_ID=commercialbrainz ./scripts/deploy-gcloud-vm.sh
#
# Branches / default VMs:
#   testing    → commercialbrainz-vm   (DuckDNS testing)
#   cloudflare → commercialbrainz-public  (public site)
# See docs/branches.md
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
APP_BRANCH="${APP_BRANCH:-testing}"
if [[ "$APP_BRANCH" == "main" || "$APP_BRANCH" == "google" ]]; then
  echo "WARN: APP_BRANCH=${APP_BRANCH} is retired; using testing"
  APP_BRANCH=testing
fi

if [[ -z "${VM_NAME:-}" ]]; then
  case "$APP_BRANCH" in
    cloudflare) VM_NAME="${VM_NAME_CLOUDFLARE:-commercialbrainz-public}" ;;
    *) VM_NAME="${VM_NAME_TESTING:-${VM_NAME_GOOGLE:-commercialbrainz-vm}}" ;;
  esac
fi

if [[ -z "$PROJECT_ID" ]]; then
  if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "ERROR: GCP_PROJECT_ID must be set in CI"
    exit 1
  fi
  read -rp "GCP Project ID: " PROJECT_ID
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS="${CLOUDSDK_CORE_DISABLE_PROMPTS:-1}"

gcloud config set project "$PROJECT_ID" >/dev/null

ZONE="$(gcloud compute instances list --filter="name=${VM_NAME}" --format='value(zone.basename())' --limit=1)"
if [[ -z "$ZONE" ]]; then
  echo "ERROR: VM '$VM_NAME' not found"
  echo "  For public site create it with: GCP_PROJECT_ID=$PROJECT_ID ./scripts/setup-cloudflare-vm.sh"
  exit 1
fi

echo "==> Deploying to $VM_NAME ($ZONE) APP_BRANCH=${APP_BRANCH} IMAGE_TAG=${IMAGE_TAG}..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
chmod +x "$SCRIPT_DIR/ensure-gcloud-vm-ssh.sh"
GCP_PROJECT_ID="$PROJECT_ID" VM_NAME="$VM_NAME" ZONE="$ZONE" \
  bash "$SCRIPT_DIR/ensure-gcloud-vm-ssh.sh"

REMOTE_TAG=$(printf '%q' "$IMAGE_TAG")
REMOTE_BRANCH=$(printf '%q' "$APP_BRANCH")

# Bootstrap git on the VM before fix-gcloud-vm.sh:
# 1) VMs may still have an old fix script that defaults to deleted `main`
# 2) sudo often drops APP_BRANCH via env_reset unless passed as `sudo env ...`
gcloud compute ssh "$VM_NAME" \
  --zone="$ZONE" \
  --quiet \
  --ssh-flag="-o StrictHostKeyChecking=accept-new" \
  --ssh-flag="-o IdentitiesOnly=yes" \
  --ssh-flag="-o LogLevel=ERROR" \
  --command="
  set -euo pipefail
  cd /opt/commercialbrainz
  IMAGE_TAG=${REMOTE_TAG}
  APP_BRANCH=${REMOTE_BRANCH}
  if [[ \"\$APP_BRANCH\" == \"main\" || \"\$APP_BRANCH\" == \"google\" ]]; then
    echo \"WARN: APP_BRANCH=\${APP_BRANCH} is retired; using testing\"
    APP_BRANCH=testing
  fi
  sudo git config --global --add safe.directory /opt/commercialbrainz 2>/dev/null || true
  # Single-branch clones (old main) may lack origin/<branch> tracking refs.
  sudo git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*' || true
  echo \"==> Bootstrap sync to origin/\${APP_BRANCH}\"
  sudo git fetch origin \"refs/heads/\${APP_BRANCH}:refs/remotes/origin/\${APP_BRANCH}\"
  if sudo git rev-parse --verify \"origin/\${APP_BRANCH}\" >/dev/null 2>&1; then
    sudo git checkout -B \"\$APP_BRANCH\" \"origin/\$APP_BRANCH\"
    sudo git reset --hard \"origin/\$APP_BRANCH\"
  else
    sudo git checkout -B \"\$APP_BRANCH\" FETCH_HEAD
    sudo git reset --hard FETCH_HEAD
  fi
  sudo git clean -fd -e .env -e infra/caddy/Caddyfile.runtime -e infra/compose.env -e data/maintenance -e data/caddy
  sudo git rev-parse --short HEAD
  # CB_REPO_SYNCED=1 skips the in-script sync (already done); sudo env keeps vars.
  sudo env IMAGE_TAG=\"\$IMAGE_TAG\" APP_BRANCH=\"\$APP_BRANCH\" CB_REPO_SYNCED=1 \
    bash scripts/fix-gcloud-vm.sh
"

echo ""
echo "==> Done. Run VM_NAME=${VM_NAME} ./scripts/diagnose-gcloud-vm.sh to verify."
