"""Upload dataset bundles to Internet Archive."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def archive_org_configured() -> bool:
    return bool(settings.ia_access_key and settings.ia_secret_key)


def upload_bundle_to_archive_org(
    bundle_dir: Path,
    *,
    identifier: str,
    files: list[tuple[Path, str]],
    stats: dict,
) -> str:
    """Upload all bundle files to a single Archive.org item. Returns item URL."""
    if settings.ia_skip_upload:
        logger.info("IA_SKIP_UPLOAD set — bundle kept at %s", bundle_dir)
        return f"file://{bundle_dir.resolve()}"

    if not archive_org_configured():
        raise RuntimeError(
            "Internet Archive credentials not configured (IA_ACCESS_KEY, IA_SECRET_KEY)"
        )

    import internetarchive as ia

    os.environ.setdefault("IA_ACCESS_KEY", settings.ia_access_key)
    os.environ.setdefault("IA_SECRET_KEY", settings.ia_secret_key)

    metadata = {
        "title": f"{settings.app_name} dataset {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "description": (
            f"Open dataset export from {settings.app_name}: "
            f"{stats.get('video_count', 0)} public videos, "
            f"{stats.get('brand_count', 0)} brands, thumbnails and logo images, "
            "with JSON metadata and links to videos and brands on the live site."
        ),
        "mediatype": "data",
        "collection": settings.ia_collection,
        "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
        "subject": ["television commercials", "advertising", "open data"],
        "creator": settings.app_name,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
    }

    file_map = {remote: str(local) for local, remote in files}
    logger.info("Uploading %d files to archive.org/%s", len(file_map), identifier)

    item = ia.get_item(identifier)
    response = item.upload(
        files=file_map,
        metadata=metadata,
        verbose=True,
        retries=5,
        queue_derive=False,
    )

    errors = [result for result in response if result.status_code >= 400]
    if errors:
        detail = "; ".join(f"{r.filename}: {r.status_code}" for r in errors[:5])
        raise RuntimeError(f"Archive.org upload failed: {detail}")

    return f"https://archive.org/details/{identifier}"
