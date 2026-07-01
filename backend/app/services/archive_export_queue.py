"""Archive.org export job status and enqueue."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

import redis
from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

STATUS_KEY = "archive_export:status"
LOCK_KEY = "archive_export:lock"
LOCK_TTL_SECONDS = 6 * 60 * 60


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def get_archive_export_status() -> dict:
    raw = _redis_client().get(STATUS_KEY)
    if not raw:
        return {"status": "idle"}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "idle"}


def _set_status(payload: dict) -> None:
    _redis_client().set(STATUS_KEY, json.dumps(payload, default=str))


def is_archive_export_running() -> bool:
    status = get_archive_export_status()
    return status.get("status") == "running"


async def enqueue_archive_export(actor_id: UUID | None = None) -> None:
    if is_archive_export_running():
        raise RuntimeError("An Archive.org export is already running")

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job(
            "export_to_archive_org",
            str(actor_id) if actor_id else None,
        )
    finally:
        await pool.aclose()


async def run_archive_export(triggered_by: UUID | None = None) -> dict:
    """Build dataset bundle and upload to Internet Archive."""
    client = _redis_client()
    if not client.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS):
        raise RuntimeError("Archive.org export lock already held")

    started = datetime.now(UTC).isoformat()
    export_id = uuid.uuid4()
    _set_status(
        {
            "status": "running",
            "started_at": started,
            "export_id": str(export_id),
            "triggered_by": str(triggered_by) if triggered_by else None,
            "stage": "building",
        }
    )

    bundle_dir = None
    try:
        from app.services.archive_export import build_archive_export_bundle, collect_bundle_files
        from app.services.archive_org_upload import upload_bundle_to_archive_org

        bundle_dir, stats = await build_archive_export_bundle()
        files = collect_bundle_files(bundle_dir)

        identifier = (
            f"commercialbrainz-dataset-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        )
        _set_status(
            {
                "status": "running",
                "started_at": started,
                "triggered_by": str(triggered_by) if triggered_by else None,
                "stage": "uploading",
                "bundle_path": str(bundle_dir),
                "identifier": identifier,
                **stats,
            }
        )

        item_url = upload_bundle_to_archive_org(
            bundle_dir,
            identifier=identifier,
            files=files,
            stats=stats,
        )

        finished = datetime.now(UTC).isoformat()
        result = {
            "status": "completed",
            "started_at": started,
            "finished_at": finished,
            "triggered_by": str(triggered_by) if triggered_by else None,
            "identifier": identifier,
            "item_url": item_url,
            "bundle_path": str(bundle_dir),
            **stats,
        }
        _set_status(result)

        from app.database import async_session_factory
        from app.models import AuditLog

        async with async_session_factory() as db:
            db.add(
                AuditLog(
                    action="archive_org_export",
                    entity_type="archive_export",
                    entity_id=export_id,
                    actor_id=triggered_by,
                    details=result,
                )
            )
            await db.commit()

        logger.info("Archive.org export completed: %s", item_url)
        return result
    except Exception as exc:
        logger.exception("Archive.org export failed")
        finished = datetime.now(UTC).isoformat()
        error_payload = {
            "status": "failed",
            "started_at": started,
            "finished_at": finished,
            "triggered_by": str(triggered_by) if triggered_by else None,
            "error": str(exc),
            "bundle_path": str(bundle_dir) if bundle_dir else None,
        }
        _set_status(error_payload)
        raise
    finally:
        client.delete(LOCK_KEY)
