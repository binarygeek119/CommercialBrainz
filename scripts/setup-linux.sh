#!/usr/bin/env bash
# CommercialBrainz Linux setup script (Ubuntu 22.04+ / Debian)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> CommercialBrainz setup for Linux"

if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

echo "==> Installing system dependencies..."
$SUDO apt-get update
$SUDO apt-get install -y \
  python3.12 python3.12-venv python3-pip \
  postgresql postgresql-contrib libpq-dev \
  redis-server \
  curl git build-essential

if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 20 ]]; then
  echo "==> Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
  $SUDO apt-get install -y nodejs
fi

echo "==> Configuring PostgreSQL..."
$SUDO -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='commercialbrainz'" | grep -q 1 || \
  $SUDO -u postgres psql -c "CREATE USER commercialbrainz WITH PASSWORD 'commercialbrainz';"
$SUDO -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='commercialbrainz'" | grep -q 1 || \
  $SUDO -u postgres psql -c "CREATE DATABASE commercialbrainz OWNER commercialbrainz;"
$SUDO -u postgres psql -d commercialbrainz -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>/dev/null || true

echo "==> Starting Redis..."
$SUDO systemctl enable redis-server 2>/dev/null || true
$SUDO systemctl start redis-server 2>/dev/null || true

if [[ ! -f .env ]]; then
  cp .env.example .env
  SECRET=$(python3.12 -c "import secrets; print(secrets.token_urlsafe(32))")
  sed -i "s/change-me-to-a-long-random-string/$SECRET/" .env
  echo "==> Created .env with random SECRET_KEY"
fi

echo "==> Setting up Python virtual environment..."
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e "./backend[dev]"

echo "==> Running database migrations..."
cd backend
alembic upgrade head
cd "$ROOT"

echo "==> Installing frontend..."
cd frontend
npm ci
npm run build
cd "$ROOT"

if [[ "${SEED_ADMIN:-}" == "1" ]]; then
  read -rp "Admin email: " ADMIN_EMAIL
  read -rp "Admin username: " ADMIN_USERNAME
  read -rsp "Admin password: " ADMIN_PASSWORD
  echo
  source .venv/bin/activate
  cd backend
  commercialbrainz seed-admin --email "$ADMIN_EMAIL" --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  cd "$ROOT"
else
  echo "==> To seed admin: SEED_ADMIN=1 ./scripts/setup-linux.sh"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Start services:"
echo "  source .venv/bin/activate"
echo "  cd backend && uvicorn app.main:app --reload --port 8000"
echo "  cd backend && arq app.workers.settings.WorkerSettings   # separate terminal"
echo "  cd frontend && npm run dev                               # separate terminal"
echo ""
echo "Or use Docker:"
echo "  docker compose -f infra/docker-compose.yml up --build"
