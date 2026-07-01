# CommercialBrainz

**CommercialBrainz** is an open commercial video database modeled after [MusicBrainz](https://musicbrainz.org). Each entry represents one YouTube video of a single commercial, with rich metadata, community edits, voting, and a scrape-friendly public API.

## Features

- **Rich data model** — Advertisers, agencies, commercials, videos, credits, tags, airings
- **One entry = one video** — Each record links a commercial to a specific YouTube upload
- **MusicBrainz-style edits** — Community submissions with 7-day voting periods
- **Roles** — Users, mods (auto-editors), and admins
- **DMCA takedown system** — Link suppression with audit trail and mod review queue
- **Scrape-friendly API** — Versioned JSON, ETags, rate limits, nightly dumps (CC0)

## Quick start (Docker)

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

- Web UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Seed an admin user:

```bash
docker compose -f infra/docker-compose.yml exec api \
  commercialbrainz seed-admin --email admin@example.com --username admin --password yourpassword
```

## Linux setup

For bare-metal install on Ubuntu 22.04+ / Debian:

```bash
chmod +x scripts/setup-linux.sh
SEED_ADMIN=1 ./scripts/setup-linux.sh
```

Then start services:

```bash
source .venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && arq app.workers.settings.WorkerSettings   # worker
cd frontend && npm run dev                               # frontend
```

## Google Cloud — free VM (e2-micro)

The cheapest way to run CommercialBrainz on GCP uses the **Always Free** e2-micro instance (1 vCPU, 1 GB RAM) in `us-west1`, `us-central1`, or `us-east1`. Everything runs on one VM via Docker Compose.

Prerequisites: `gcloud` CLI, billing account (free tier still requires one).

```bash
chmod +x scripts/setup-gcloud-vm.sh
GCP_PROJECT_ID=your-project ./scripts/setup-gcloud-vm.sh
```

Optional admin seed on first boot:

```bash
GCP_PROJECT_ID=your-project \
ADMIN_EMAIL=admin@example.com \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD=yourpassword \
./scripts/setup-gcloud-vm.sh
```

After 10–20 minutes (Docker build on e2-micro is slow):

- Web UI: `http://EXTERNAL_IP/`
- API docs: `http://EXTERNAL_IP:8000/docs`

Monitor startup:

```bash
gcloud compute ssh commercialbrainz-vm --zone=us-central1-a \
  --command='sudo tail -f /var/log/commercialbrainz-startup.log'
```

See [scripts/setup-gcloud-vm.sh](scripts/setup-gcloud-vm.sh) and [infra/gcloud/vm-startup.sh](infra/gcloud/vm-startup.sh).

### DuckDNS (free hostname for your VM)

1. Create a subdomain at [duckdns.org](https://www.duckdns.org/) and copy your token.
2. Deploy the VM with DuckDNS (updates DNS immediately + every 5 min on the VM):

```bash
GCP_PROJECT_ID=your-project \
DUCKDNS_DOMAIN=commercialbrainz \
DUCKDNS_TOKEN=your-duckdns-token \
./scripts/setup-gcloud-vm.sh
```

3. After startup: `http://commercialbrainz.duckdns.org/` (web) and `:8000/docs` (API).

Add DuckDNS to an **existing** VM:

```bash
DUCKDNS_DOMAIN=commercialbrainz DUCKDNS_TOKEN=your-token \
GCP_PROJECT_ID=your-project ./scripts/setup-duckdns-gcloud.sh
```

DuckDNS is ideal with ephemeral GCE IPs (no static IP cost). For HTTPS, add a reverse proxy (e.g. Caddy + Let's Encrypt) in front of port 80.

## Google Cloud — production (Cloud Run)

Prerequisites: `gcloud` CLI, billing enabled, Docker.

```bash
chmod +x scripts/setup-gcloud.sh
GCP_PROJECT_ID=your-project ./scripts/setup-gcloud.sh
```

This provisions Cloud SQL, Secret Manager, Artifact Registry, Cloud Run (API + web), and a GCS dump bucket. See [scripts/setup-gcloud.sh](scripts/setup-gcloud.sh) for the post-deploy checklist.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  React Web  │────▶│  FastAPI     │────▶│ PostgreSQL │
│  (Vite)     │     │  /api/v1     │     │            │
└─────────────┘     └──────┬───────┘     └────────────┘
                           │
                    ┌──────▼───────┐     ┌────────────┐
                    │ ARQ Worker   │────▶│ Redis      │
                    │ edits/dumps  │     │            │
                    └──────────────┘     └────────────┘
```

## API usage (scrapers)

Base URL: `/api/v1`

| Endpoint | Description |
|----------|-------------|
| `GET /videos/{sbid}` | Video with nested commercial/advertiser |
| `GET /commercials/{sbid}` | Commercial with linked videos |
| `GET /advertisers/{sbid}` | Advertiser with commercials |
| `GET /search?query=&type=video` | Full-text search |
| `GET /browse/videos?advertiser=&tag=` | Filtered browse |
| `GET /edits/{id}` | Public edit history |
| `GET /dumps/latest` | Latest data dump info |

### Scraper etiquette

1. **User-Agent required**: `YourApp/1.0 (contact@example.com)`
2. **Rate limits**: 1 req/s anonymous, 5 req/s authenticated
3. **Use ETags**: Send `If-None-Match` with cached ETag for 304 responses
4. **Bulk data**: Download nightly dumps from `/api/v1/dumps/latest`

OpenAPI spec: `/docs` or `/openapi.json`

## Edit & voting guide

1. Register and log in
2. Submit a commercial video via the web UI or `POST /api/v1/edits/submit-video`
3. Edits stay open for **7 days** unless resolved early
4. **3 unanimous Yes** → applied; **3 unanimous No** → rejected
5. After 7 days: more Yes than No → applied; otherwise rejected
6. Voting requires account age ≥ 14 days and ≥ 10 accepted edits
7. Mods and admins can auto-apply edits instantly

## DMCA policy

Copyright holders may submit takedown notices via `/dmca` or `POST /api/v1/dmca`. Valid claims hide the YouTube link from public API responses while preserving archival metadata. Contact: dmca@commercialbrainz.org

## Data license

CommercialBrainz data is released under **[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)** (public domain dedication).

## Development

```bash
# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
pytest
ruff check app tests

# Frontend
cd frontend
npm ci
npm run dev
npm run build

# Worker
cd backend
arq app.workers.settings.WorkerSettings

# CLI
commercialbrainz seed-admin --email admin@example.com --username admin
commercialbrainz expire-edits
commercialbrainz generate-dump
```

## Project structure

```
├── backend/           FastAPI + SQLAlchemy + Alembic
├── frontend/          React + Vite + TypeScript
├── infra/             Docker, nginx, GCloud configs
├── scripts/           setup-linux.sh, setup-gcloud.sh
└── .github/workflows/ CI pipeline
```

## Identifiers (CBID)

Every entity has a **CommercialBrainz ID** (CBID) — UUID v4 used in URLs and API:

```
/commercial/550e8400-e29b-41d4-a716-446655440000
/api/v1/videos/550e8400-e29b-41d4-a716-446655440000
```
