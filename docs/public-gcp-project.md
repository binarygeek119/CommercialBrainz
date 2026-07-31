# Public site GCP project (`commercialbrainz-public`)

Dedicated Google Cloud **project** for https://commercialbrainz.org/ — separate from testing (`commercialbrainz` + DuckDNS).

| Env | GCP project | VM | Deploy branch |
|-----|-------------|-----|---------------|
| Testing | `commercialbrainz` | `commercialbrainz-vm` | `testing` |
| Public | **`commercialbrainz-public`** | `commercialbrainz-public` | `public` |

## One-shot setup (laptop)

```bash
gcloud auth login
gcloud auth application-default login   # optional

# List billing accounts, then link during the script (or pass BILLING_ACCOUNT=…)
gcloud billing accounts list

./scripts/setup-public-gcp-project.sh
# or create the VM in the same run:
# CREATE_VM=1 ADMIN_EMAIL=… ADMIN_USERNAME=… ADMIN_PASSWORD=… ACME_EMAIL=… \
#   ./scripts/setup-public-gcp-project.sh
```

The script:

1. Creates project **`commercialbrainz-public`** (if missing)
2. Links billing
3. Enables Compute / IAM / Resource Manager APIs
4. Creates **`github-deploy@commercialbrainz-public.iam.gserviceaccount.com`**
5. Sets up Workload Identity Federation for GitHub Actions (`binarygeek119/CommercialBrainz`)
6. Creates HTTP/HTTPS + SSH firewall rules
7. Optionally creates VM **`commercialbrainz-public`** (`CREATE_VM=1`)

## Manual gcloud (same steps)

```bash
PROJECT_ID=commercialbrainz-public
GITHUB_ORG=binarygeek119
GITHUB_REPO=CommercialBrainz

gcloud projects create "$PROJECT_ID" --name="CommercialBrainz Public"
gcloud billing projects link "$PROJECT_ID" --billing-account=XXXXXX-XXXXXX-XXXXXX
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  compute.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com

gcloud iam service-accounts create github-deploy \
  --display-name="GitHub Actions Deploy"

SA=github-deploy@${PROJECT_ID}.iam.gserviceaccount.com
for role in \
  roles/compute.instanceAdmin.v1 \
  roles/compute.networkAdmin \
  roles/compute.securityAdmin \
  roles/iam.serviceAccountUser \
  roles/compute.viewer
do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" --role="$role"
done

gcloud iam workload-identity-pools create github-actions \
  --location=global --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --location=global \
  --workload-identity-pool=github-actions \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}"

gcloud compute firewall-rules create allow-http-https \
  --allow=tcp:80,tcp:443 --direction=INGRESS --network=default
gcloud compute firewall-rules create allow-ssh \
  --allow=tcp:22 --direction=INGRESS --network=default

# VM (static IP recommended)
GCP_PROJECT_ID="$PROJECT_ID" CREATE_STATIC_IP=1 ./scripts/setup-cloudflare-vm.sh
```

WIF provider resource (for GitHub variables):

```bash
echo "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/providers/github"
```

## GitHub Actions variables

After setup, set **repository variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Public project value |
|----------|----------------------|
| `GCP_PROJECT_ID_PUBLIC` | `commercialbrainz-public` (default in workflows) |
| `GCP_WIF_PROVIDER_PUBLIC` | `projects/227542386250/.../providers/github` (default; override if project number changes) |
| `GCP_SA_EMAIL_PUBLIC` | `github-deploy@commercialbrainz-public.iam.gserviceaccount.com` (default) |
| `VM_NAME_PUBLIC` | `commercialbrainz-public` (default) |

Legacy aliases still accepted by workflows: `GCP_*_CLOUDFLARE`, `VM_NAME_CLOUDFLARE`.

Repo variables are optional when using the stock `commercialbrainz-public` project created by `setup-public-gcp-project.sh`. Set them only if you recreate the project (new project number) or rename the SA/VM.

Testing (unchanged defaults):

| Variable | Testing value |
|----------|---------------|
| `GCP_PROJECT_ID` | `commercialbrainz` |
| `GCP_WIF_PROVIDER` | existing pool in `commercialbrainz` |
| `GCP_SA_EMAIL` | `github-deploy@commercialbrainz.iam.gserviceaccount.com` |
| `VM_NAME_TESTING` | `commercialbrainz-vm` (legacy: `VM_NAME_GOOGLE`) |

**Deploy** and **Setup GCE VM** pick project / WIF / SA from the branch (`testing` vs `public`).

## Deploy / DNS

1. Create VM if needed: Actions → **Setup GCE VM** → `public`, or laptop `setup-cloudflare-vm.sh` with `GCP_PROJECT_ID=commercialbrainz-public`.
2. Point Cloudflare A `@` / `www` at the new static IP (project `commercialbrainz-public`).
3. Origin CA + [`docs/cloudflare-domain.md`](cloudflare-domain.md).
4. Actions → **Deploy** → `public`.

## Cost

A second GCP project still bills for the public e2-micro + static IP. Always Free’s one free e2-micro stays on the testing project if that VM remains the only free-tier instance in that project/region ruleset.
