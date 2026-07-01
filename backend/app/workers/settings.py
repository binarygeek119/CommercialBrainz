import logging

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)
settings = get_settings()


async def expire_edits(ctx):
    from app.services import EditService

    async with async_session_factory() as db:
        count = await EditService.expire_open_edits(db)
        await db.commit()
        logger.info("Expired %d edits", count)
        return count


async def generate_dump(ctx):
    from app.api.v1.dumps import generate_dump

    path = await generate_dump()
    logger.info("Generated dump at %s", path)
    return str(path)


async def startup(ctx):
    logger.info("SpotBrainz worker started")


async def shutdown(ctx):
    logger.info("SpotBrainz worker stopped")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [expire_edits, generate_dump]
    cron_jobs = [
        cron(expire_edits, hour={0, 6, 12, 18}, minute=0),
        cron(generate_dump, hour=2, minute=0),
    ]
    on_startup = startup
    on_shutdown = shutdown
