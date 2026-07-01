#!/usr/bin/env bash
# SpotBrainz Google Cloud bootstrap script
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
SQL_INSTANCE="${SQL_INSTANCE:-spotbrainz-db}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-spotbrainz-runner}"

if [[ -z "$PROJECT_ID" ]]; then
  read -rp "GCP Project ID: " PROJECT_ID
fi

echo "==> SpotBrainz GCloud setup"
echo "    Project: $PROJECT_ID"
echo "    Region:  $REGION"

gcloud config set project "$PROJECT_ID"

echo "==> Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com

echo "==> Creating Artifact Registry..."
gcloud artifacts repositories describe spotbrainz --location="$REGION" 2>/dev/null || \
  gcloud artifacts repositories create spotbrainz \
    --repository-format=docker \
    --location="$REGION" \
    --description="SpotBrainz container images"

echo "==> Creating Cloud SQL instance (this may take several minutes)..."
gcloud sql instances describe "$SQL_INSTANCE" 2>/dev/null || \
  gcloud sql instances create "$SQL_INSTANCE" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region="$REGION" \
    --storage-auto-increase

gcloud sql databases describe spotbrainz --instance="$SQL_INSTANCE" 2>/dev/null || \
  gcloud sql databases create spotbrainz --instance="$SQL_INSTANCE"

DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 24)}"
gcloud sql users create spotbrainz --instance="$SQL_INSTANCE" --password="$DB_PASSWORD" 2>/dev/null || \
  gcloud sql users set-password spotbrainz --instance="$SQL_INSTANCE" --password="$DB_PASSWORD"

echo "==> Creating secrets..."
create_secret() {
  local name=$1 value=$2
  if gcloud secrets describe "$name" 2>/dev/null; then
    echo -n "$value" | gcloud secrets versions add "$name" --data-file=-
  else
    echo -n "$value" | gcloud secrets create "$name" --data-file=-
  fi
}

SECRET_KEY="${SECRET_KEY:-$(openssl rand -base64 32)}"
CONNECTION_NAME="$PROJECT_ID:$REGION:$SQL_INSTANCE"
DATABASE_URL="postgresql+asyncpg://spotbrainz:${DB_PASSWORD}@/spotbrainz?host=/cloudsql/${CONNECTION_NAME}"
DATABASE_URL_SYNC="postgresql://spotbrainz:${DB_PASSWORD}@/spotbrainz?host=/cloudsql/${CONNECTION_NAME}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

create_secret spotbrainz-secret-key "$SECRET_KEY"
create_secret spotbrainz-database-url "$DATABASE_URL"
create_secret spotbrainz-redis-url "$REDIS_URL"

echo "==> Creating GCS dump bucket..."
BUCKET="${GCS_DUMP_BUCKET:-${PROJECT_ID}-spotbrainz-dumps}"
gsutil ls -b "gs://${BUCKET}" 2>/dev/null || gsutil mb -l "$REGION" "gs://${BUCKET}"

echo "==> Building and pushing Docker images..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/spotbrainz/api:latest"
WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/spotbrainz/web:latest"

docker build -f infra/Dockerfile.api -t "$API_IMAGE" .
docker build -f infra/Dockerfile.web -t "$WEB_IMAGE" .
docker push "$API_IMAGE"
docker push "$WEB_IMAGE"

echo "==> Deploying Cloud Run API..."
gcloud run deploy spotbrainz-api \
  --image="$API_IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --add-cloudsql-instances="$CONNECTION_NAME" \
  --set-secrets="SECRET_KEY=spotbrainz-secret-key:latest,DATABASE_URL=spotbrainz-database-url:latest,REDIS_URL=spotbrainz-redis-url:latest" \
  --set-env-vars="APP_ENV=production,GCS_DUMP_BUCKET=${BUCKET}" \
  --memory=512Mi \
  --port=8000

echo "==> Deploying Cloud Run Web..."
gcloud run deploy spotbrainz-web \
  --image="$WEB_IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=256Mi \
  --port=80

API_URL=$(gcloud run services describe spotbrainz-api --region="$REGION" --format='value(status.url)')
WEB_URL=$(gcloud run services describe spotbrainz-web --region="$REGION" --format='value(status.url)')

echo ""
echo "==> Deployment complete!"
echo "    API:  $API_URL"
echo "    Web:  $WEB_URL"
echo ""
echo "Post-deploy checklist:"
echo "  1. Run migrations: gcloud run jobs create spotbrainz-migrate --image=$API_IMAGE ..."
echo "     Or exec: alembic upgrade head against Cloud SQL"
echo "  2. Seed admin: spotbrainz seed-admin --email admin@example.com --username admin"
echo "  3. Configure Redis (Memorystore or Upstash) and update spotbrainz-redis-url secret"
echo "  4. Set up Cloud Scheduler for dump export and edit expiry worker"
echo "  5. Save DB password securely: $DB_PASSWORD"
