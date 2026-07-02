#!/bin/sh
set -eu

cd /app/backend

echo "==> CommercialBrainz API entrypoint"
echo "    DATABASE_URL host: $(python -c "import os; u=os.environ.get('DATABASE_URL',''); print(u.split('@')[-1].split('/')[0] if '@' in u else 'unset')")"

python <<'PY'
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("ERROR: DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)


async def wait_for_db() -> None:
    for attempt in range(30):
        try:
            engine = create_async_engine(url)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            print("Database connection OK")
            return
        except Exception as exc:
            print(f"Waiting for database ({attempt + 1}/30): {exc}", flush=True)
            await asyncio.sleep(2)
    print("ERROR: Database did not become ready in time", file=sys.stderr)
    sys.exit(1)


asyncio.run(wait_for_db())
PY

echo "==> Running migrations"
alembic upgrade head

python <<'PY'
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = os.environ["DATABASE_URL"]


async def verify_schema() -> None:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1 FROM users LIMIT 1"))
        result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        version = result.scalar_one_or_none()
        print(f"Alembic version: {version}")
    await engine.dispose()


try:
    asyncio.run(verify_schema())
except Exception as exc:
    print(f"ERROR: Database schema check failed: {exc}", file=sys.stderr)
    sys.exit(1)
PY

echo "==> Starting application (${1:-api})"
if [ "${1:-api}" = "worker" ]; then
  exec arq app.workers.settings.WorkerSettings
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
