import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.config import get_settings
from app.database import async_session_factory
from app.services.rate_limit import close_redis

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    description="Open commercial video database — MusicBrainz for TV spots",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health(response: Response):
    payload: dict = {"status": "ok", "app": settings.app_name, "database": "unknown"}
    db_host = settings.database_url.split("@")[-1].split("/")[0] if "@" in settings.database_url else "unknown"
    payload["database_host"] = db_host
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            version = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        payload["database"] = "ok"
        payload["alembic_version"] = version
    except Exception as exc:
        logger.exception("Database health check failed")
        payload["status"] = "degraded"
        payload["database"] = "error"
        payload["database_error"] = str(exc.__class__.__name__)
        response.status_code = 503
    return payload
