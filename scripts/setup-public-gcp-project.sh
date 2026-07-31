#!/usr/bin/env bash
# Create a dedicated GCP project for the public site (commercialbrainz.org).
#
# Default project id: commercialbrainz-public
# Creates: APIs, github-deploy SA, Workload Identity Federation for GitHub Actions,
# firewall rules, optional static IP + VM (commercialbrainz-public).
#
# Prerequisites (laptop):
#   gcloud auth login
#   gcloud auth application-default login   # optional
#   Billing account you can link (script prompts if BILLING_ACCOUNT unset)
#
# Usage:
#   ./scripts/setup-public-gcp-project.sh
#   BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX CREATE_VM=1 ./scripts/setup-public-gcp-project.sh
#
# After this finishes, set GitHub repo variables (printed at the end), then:
#   Actions → Setup GCE VM → cloudflare   # if CREATE_VM=0
#   Actions → Deploy → cloudflare
#
# See docs/public-gcp-project.md
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROJECT_ID="${GCP_PROJECT_ID:-commercialbrainz-public}"
PROJECT_NAME="${GCP_PROJECT_NAME:-CommercialBrainz Public}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-${REGION}-a}"
GITHUB_ORG="${GITHUB_ORG:-binarygeek119}"
GITHUB_REPO="${GITHUB_REPO:-CommercialBrainz}"
SA_NAME="${SA_NAME:-github-deploy}"
WIF_POOL="${WIF_POOL:-github-actions}"
WIF_PROVIDER="${WIF_PROVIDER:-github}"
CREATE_VM="${CREATE_VM:-0}"
VM_NAME="${VM_NAME:-commercialbrainz-public}"
FIREWALL_HTTP="${FIREWALL_HTTP:-allow-http-https}"
FIREWALL_SSH="${FIREWALL_SSH:-allow-ssh}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' is required. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
  }
}

need_cmd gcloud

echo "==> Public GCP project setup"
echo "    PROJECT_ID=${PROJECT_ID}"
echo "    REGION=${REGION}  ZONE=${ZONE}"
echo "    GitHub=${GITHUB_ORG}/${GITHUB_REPO}"
echo "    CREATE_VM=${CREATE_VM}"
echo ""

# --- Project -----------------------------------------------------------------
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> Project ${PROJECT_ID} already exists"
else
  echo "==> Creating project ${PROJECT_ID}..."
  CREATE_ARGS=(projects create "$PROJECT_ID" --name="$PROJECT_NAME")
  if [[ -n "${GCP_ORGANIZATION_ID:-}" ]]; then
    CREATE_ARGS+=(--organization="$GCP_ORGANIZATION_ID")
  elif [[ -n "${GCP_FOLDER_ID:-}" ]]; then
    CREATE_ARGS+=(--folder="$GCP_FOLDER_ID")
  fi
  gcloud "${CREATE_ARGS[@]}"
fi

gcloud config set project "$PROJECT_ID" >/dev/null

# --- Billing -----------------------------------------------------------------
BILLING_ENABLED="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || echo false)"
if [[ "$BILLING_ENABLED" != "True" && "$BILLING_ENABLED" != "true" ]]; then
  if [[ -z "${BILLING_ACCOUNT:-}" ]]; then
    echo ""
    echo "Billing is not linked. List accounts:"
    gcloud billing accounts list
    echo ""
    read -rp "Billing account ID (XXXXXX-XXXXXX-XXXXXX): " BILLING_ACCOUNT
  fi
  if [[ -z "${BILLING_ACCOUNT:-}" ]]; then
    echo "ERROR: BILLING_ACCOUNT is required to enable Compute Engine."
    exit 1
  fi
  echo "==> Linking billing account ${BILLING_ACCOUNT}..."
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
else
  echo "==> Billing already enabled"
fi

# --- APIs --------------------------------------------------------------------
echo "==> Enabling APIs..."
gcloud services enable \
  compute.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="$PROJECT_ID"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"

echo "    projectNumber=${PROJECT_NUMBER}"

# --- Service account ---------------------------------------------------------
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> Service account ${SA_EMAIL} already exists"
else
  echo "==> Creating service account ${SA_NAME}..."
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions Deploy" \
    --project="$PROJECT_ID"
fi

echo "==> Granting project roles to ${SA_EMAIL}..."
for role in \
  roles/compute.instanceAdmin.v1 \
  roles/compute.networkAdmin \
  roles/compute.securityAdmin \
  roles/iam.serviceAccountUser \
  roles/compute.viewer
do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" \
    --quiet >/dev/null
done

# --- Workload Identity Federation --------------------------------------------
if gcloud iam workload-identity-pools describe "$WIF_POOL" \
  --location=global --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> WIF pool ${WIF_POOL} already exists"
else
  echo "==> Creating WIF pool ${WIF_POOL}..."
  gcloud iam workload-identity-pools create "$WIF_POOL" \
    --location=global \
    --display-name="GitHub Actions" \
    --project="$PROJECT_ID"
fi

if gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
  --location=global \
  --workload-identity-pool="$WIF_POOL" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> WIF provider ${WIF_PROVIDER} already exists (updating attribute condition)..."
  gcloud iam workload-identity-pools providers update-oidc "$WIF_PROVIDER" \
    --location=global \
    --workload-identity-pool="$WIF_POOL" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
    --project="$PROJECT_ID" \
    --quiet || true
else
  echo "==> Creating OIDC provider ${WIF_PROVIDER}..."
  gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
    --location=global \
    --workload-identity-pool="$WIF_POOL" \
    --display-name="GitHub" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
    --project="$PROJECT_ID"
fi

echo "==> Allowing ${GITHUB_ORG}/${GITHUB_REPO} to impersonate ${SA_EMAIL}..."
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}" \
  --quiet >/dev/null

# --- Firewall ----------------------------------------------------------------
echo "==> Firewall rules..."
if ! gcloud compute firewall-rules describe "$FIREWALL_HTTP" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules create "$FIREWALL_HTTP" \
    --project="$PROJECT_ID" \
    --allow=tcp:80,tcp:443 \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --description="HTTP/HTTPS for CommercialBrainz public site"
else
  echo "    ${FIREWALL_HTTP} exists"
fi

if ! gcloud compute firewall-rules describe "$FIREWALL_SSH" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules create "$FIREWALL_SSH" \
    --project="$PROJECT_ID" \
    --allow=tcp:22 \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --description="SSH for deploy / admin"
else
  echo "    ${FIREWALL_SSH} exists"
fi

# --- Optional VM -------------------------------------------------------------
if [[ "$CREATE_VM" == "1" || "$CREATE_VM" == "true" ]]; then
  echo "==> Creating public VM ${VM_NAME} in ${PROJECT_ID}..."
  export GCP_PROJECT_ID="$PROJECT_ID"
  export VM_NAME
  export REPO_BRANCH="${REPO_BRANCH:-cloudflare}"
  export CREATE_STATIC_IP="${CREATE_STATIC_IP:-1}"
  export MACHINE_TYPE="${MACHINE_TYPE:-e2-micro}"
  export DISK_SIZE="${DISK_SIZE:-30GB}"
  export GCP_ZONE="${GCP_ZONE:-$ZONE}"
  unset DUCKDNS_DOMAIN DUCKDNS_TOKEN 2>/dev/null || true
  bash "$SCRIPT_DIR/setup-cloudflare-vm.sh"
else
  echo "==> Skipping VM create (set CREATE_VM=1 to create ${VM_NAME} now)"
fi

# --- Summary -----------------------------------------------------------------
cat <<EOF

========================================================================
Done. Public GCP project is ready.

GitHub → Settings → Variables → Actions — set these for the public site:

  GCP_PROJECT_ID_CLOUDFLARE     = ${PROJECT_ID}
  GCP_WIF_PROVIDER_CLOUDFLARE   = ${WIF_PROVIDER_RESOURCE}
  GCP_SA_EMAIL_CLOUDFLARE       = ${SA_EMAIL}
  VM_NAME_CLOUDFLARE            = ${VM_NAME}

Keep testing on the existing project (defaults / existing vars):

  GCP_PROJECT_ID                = commercialbrainz
  GCP_WIF_PROVIDER              = projects/820871329461/locations/global/workloadIdentityPools/github-actions/providers/github
  GCP_SA_EMAIL                  = github-deploy@commercialbrainz.iam.gserviceaccount.com
  VM_NAME_TESTING               = commercialbrainz-vm
  # (legacy alias still accepted: VM_NAME_GOOGLE)

Next:
  1. Set the *_CLOUDFLARE variables above in the repo.
  2. Create VM (if CREATE_VM=0):
       Actions → Setup GCE VM → target cloudflare
     or:
       GCP_PROJECT_ID=${PROJECT_ID} CREATE_STATIC_IP=1 ./scripts/setup-cloudflare-vm.sh
  3. Point Cloudflare A @ / www at the VM static IP.
  4. Origin CA + scripts/setup-cloudflare-domain.sh (docs/cloudflare-domain.md)
  5. Actions → Deploy → branch cloudflare

One-liner reminder (re-print WIF resource):
  echo projects/\$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}
========================================================================
EOF
