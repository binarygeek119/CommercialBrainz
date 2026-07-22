import logging

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.database import async_session_factory
from app.services.hash_queue import enqueue_hash_job, hash_media, process_pending_queue

logger = logging.getLogger(__name__)
settings = get_settings()


async def expire_edits(ctx):
    from app.services import EditService

    async with async_session_factory() as db:
        count, pending_jobs = await EditService.expire_open_edits(db)
        await db.commit()
    for job_id in pending_jobs:
        await enqueue_hash_job(job_id)
    logger.info("Expired %d edits", count)
    return count


async def generate_dump(ctx):
    from app.api.v1.dumps import generate_dump

    path = await generate_dump()
    logger.info("Generated dump at %s", path)
    return str(path)


async def export_to_archive_org(ctx, actor_id: str | None = None):
    from uuid import UUID

    from app.services.archive_export_queue import run_archive_export

    triggered_by = UUID(actor_id) if actor_id else None
    result = await run_archive_export(triggered_by=triggered_by)
    logger.info("Archive.org export finished: %s", result.get("item_url"))
    return result


async def check_public_youtube_links(ctx, limit: int | None = None):
    """Monthly (or on-demand) scan of public YouTube links for dead/private videos."""
    from app.services.link_check import check_public_youtube_links as run_check

    async with async_session_factory() as db:
        counts = await run_check(db, limit=limit)
    logger.info("YouTube link check counts: %s", counts)
    return counts


async def startup(ctx):
    logger.info("CommercialBrainz worker started")


async def shutdown(ctx):
    logger.info("CommercialBrainz worker stopped")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        expire_edits,
        generate_dump,
        export_to_archive_org,
        hash_media,
        process_pending_queue,
        check_public_youtube_links,
    ]
    cron_jobs = [
        cron(expire_edits, hour={0, 6, 12, 18}, minute=0),
        cron(generate_dump, hour=2, minute=0),
        cron(process_pending_queue, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        # First day of each month at 04:00 UTC.
        cron(check_public_youtube_links, day=1, hour=4, minute=0),
    ]
    max_jobs = 1
    on_startup = startup
    on_shutdown = shutdown
