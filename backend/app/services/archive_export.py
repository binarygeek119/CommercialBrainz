"""Build a full dataset bundle for Internet Archive export."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    Advertiser,
    AdvertiserStatus,
    Commercial,
    Video,
    VideoVisibility,
)
from app.services.advertiser_metadata import advertiser_public_dict
from app.services.fingerprint_queries import format_phash_hex
from app.services.logo_storage import resolve_logo_path
from app.services.thumbnail_storage import is_hosted_thumbnail, resolve_media_path
from app.utils import youtube_thumbnail_url, youtube_watch_url

logger = logging.getLogger(__name__)
settings = get_settings()


def _site_url(path: str) -> str:
    base = settings.app_public_url.rstrip("/")
    return f"{base}{path}"


def _media_relative(url: str | None, marker: str) -> str | None:
    if not url or marker not in url:
        return None
    idx = url.find(marker)
    return unquote(url[idx + len(marker) :].lstrip("/"))


def _thumbnail_relative(url: str | None) -> str | None:
    return _media_relative(url, "/api/v1/media/thumbnails/")


def _logo_relative(url: str | None) -> str | None:
    return _media_relative(url, "/api/v1/media/logos/")


async def _download_url(
    client: httpx.AsyncClient,
    url: str,
     dest: Path) -> bool:
    try:
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return True
    except Exception as exc:
        logger.warning("Failed to download %s: %s", url, exc)
        return False


async def build_archive_export_bundle(
    output_root: Path | None = None) -> tuple[Path, dict]:
    """Assemble metadata JSON and image files for Archive.org upload."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    bundle_dir = (output_root or Path(settings.archive_export_dir)
                  ) / f"commercialbrainz-{stamp}"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    images_dir = bundle_dir / "images"
    thumbs_dir = images_dir / "thumbnails"
    logos_dir = images_dir / "logos"
    thumbs_dir.mkdir(parents=True)
    logos_dir.mkdir(parents=True)

    from app.database import async_session_factory

    stats = {
        "video_count": 0,
        "brand_count": 0,
        "thumbnail_files": 0,
        "logo_files": 0,
        "youtube_thumbnails_fetched": 0,
    }

    async with async_session_factory() as db:
        brand_rows = await _load_brands(db)
        video_rows = await _load_videos(db)

    stats["brand_count"] = len(brand_rows)
    stats["video_count"] = len(video_rows)

    async with httpx.AsyncClient() as client:
        for brand in brand_rows:
            for logo in brand["logos"]:
                rel = _logo_relative(logo.get("image_url"))
                if not rel:
                    continue
                src = resolve_logo_path(rel)
                if not src:
                    continue
                ext = src.suffix.lower() or ".png"
                dest = logos_dir / f"{logo['id']}{ext}"
                shutil.copy2(src, dest)
                logo["image_file"] = f"images/logos/{dest.name}"
                stats["logo_files"] += 1

            main_logo_id = brand.get("main_logo_id")
            if main_logo_id:
                for logo in brand["logos"]:
                    if logo["id"] == str(main_logo_id):
                        brand["main_logo_file"] = logo.get("image_file")
                        break

        for video in video_rows:
            rel = _thumbnail_relative(video.get("thumbnail_url"))
            dest: Path | None = None
            if rel:
                src = resolve_media_path(rel)
                if src:
                    ext = src.suffix.lower() or ".jpg"
                    dest = thumbs_dir / f"{video['sbid']}{ext}"
                    shutil.copy2(src, dest)
                    video["thumbnail_file"] = f"images/thumbnails/{dest.name}"
                    stats["thumbnail_files"] += 1
            elif video.get("youtube_id"):
                dest = thumbs_dir / f"{video['youtube_id']}.jpg"
                ok = await _download_url(
                    client,
                    youtube_thumbnail_url(video["youtube_id"]),
                    dest,
                )
                if ok:
                    video["thumbnail_file"] = f"images/thumbnails/{dest.name}"
                    video["thumbnail_source"] = "youtube"
                    stats["youtube_thumbnails_fetched"] += 1

    dataset = {
    "generated_at": datetime.now(UTC).isoformat(),
    "license": "CC0-1.0",
    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
    "project": settings.app_name,
    "site_url": settings.app_public_url.rstrip("/"),
    "api_base": settings.api_public_url.rstrip("/"),
    "description": (
        "CommercialBrainz open commercial video database export with metadata, "
        "brand records, site links, and thumbnail/logo images." ),
        "brands": brand_rows,
        "videos": video_rows,
        "stats": stats,
         }

    dataset_path = bundle_dir / "dataset.json"
    dataset_path.write_text(
    json.dumps(
        dataset,
        indent=2,
        default=str),
         encoding="utf-8")

    readme = bundle_dir / "README.txt"
    readme.write_text(
        "\n".join(
            [
                f"{settings.app_name} dataset export",
                f"Generated: {dataset['generated_at']}",
                "",
                f"License: {dataset['license']} ({dataset['license_url']})",
                "",
                f"Videos: {stats['video_count']}",
                f"Brands: {stats['brand_count']}",
                (
                    "Thumbnail images: "
                    f"{stats['thumbnail_files'] + stats['youtube_thumbnails_fetched']}"
                ),
                f"Logo images: {stats['logo_files']}",
                "",
                "See dataset.json for full metadata and site links.",
                f"Website: {dataset['site_url']}",
            ]
        ),
        encoding="utf-8",
    )

    return bundle_dir, stats


async def _load_brands(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Advertiser)
        .options(selectinload(Advertiser.logos))
        .where(Advertiser.status == AdvertiserStatus.APPROVED)
        .order_by(Advertiser.name)
    )
    brands: list[dict] = []
    for advertiser in result.scalars().all():
        public = advertiser_public_dict(advertiser)
        logos = []
        for logo in sorted(
            advertiser.logos,
            key=lambda row: (-row.popularity_score, row.created_at),
        ):
            logos.append(
                {
                    "id": str(logo.id),
                    "label": logo.label,
                    "year": logo.year,
                    "month": logo.month,
                    "event": logo.event,
                    "notes": logo.notes,
                    "popularity_score": logo.popularity_score,
                    "image_url": logo.image_url,
                    "is_main": logo.id == advertiser.main_logo_id,
                    "created_at": logo.created_at.isoformat(),
                }
            )
        brands.append(
            {
                **public,
                "sbid": str(public["sbid"]),
                "main_logo_id": str(advertiser.main_logo_id) if advertiser.main_logo_id else None,
                "site_url": _site_url(f"/advertiser/{advertiser.sbid}"),
                "api_url": (
                    f"{settings.api_public_url.rstrip('/')}"
                    f"/api/v1/advertisers/{advertiser.sbid}"
                ),
                "logos": logos,
            }
        )
    return brands


async def _load_videos(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Video)
        .options(
            selectinload(Video.commercial).selectinload(Commercial.advertiser),
            selectinload(Video.commercial).selectinload(Commercial.agency),
            selectinload(Video.commercial).selectinload(Commercial.products),
            selectinload(Video.credits),
            selectinload(Video.tags),
        )
        .where(Video.visibility == VideoVisibility.PUBLIC)
        .order_by(Video.created_at)
    )
    videos: list[dict] = []
    for video in result.scalars().all():
        commercial = video.commercial
        advertiser = commercial.advertiser if commercial else None
        agency = commercial.agency if commercial else None
        thumb = video.thumbnail_url
        if not thumb and video.youtube_id:
            thumb = youtube_thumbnail_url(video.youtube_id)

        row = {
            "sbid": str(video.sbid),
            "site_url": _site_url(f"/video/{video.sbid}"),
            "api_url": f"{settings.api_public_url.rstrip('/')}/api/v1/videos/{video.sbid}",
            "commercial_sbid": str(commercial.sbid) if commercial else None,
            "commercial_title": commercial.title if commercial else None,
            "commercial_url": _site_url(f"/commercial/{commercial.sbid}") if commercial else None,
            "commercial_api_url": (
                f"{settings.api_public_url.rstrip('/')}/api/v1/commercials/{commercial.sbid}"
                if commercial
                else None
            ),
            "brand_sbid": str(advertiser.sbid) if advertiser else None,
            "brand_name": advertiser.name if advertiser else None,
            "brand_url": _site_url(f"/advertiser/{advertiser.sbid}") if advertiser else None,
            "brand_api_url": (
                f"{settings.api_public_url.rstrip('/')}/api/v1/advertisers/{advertiser.sbid}"
                if advertiser
                else None
            ),
            "agency_name": agency.name if agency else None,
            "youtube_id": video.youtube_id,
            "youtube_url": video.youtube_url or (
                youtube_watch_url(video.youtube_id) if video.youtube_id else None
            ),
            "thumbnail_url": thumb,
            "thumbnail_hosted": is_hosted_thumbnail(video.thumbnail_url),
            "channel_name": video.channel_name,
            "upload_date": video.upload_date.isoformat() if video.upload_date else None,
            "duration_ms": video.duration_ms,
            "aspect_ratio": video.aspect_ratio,
            "resolution": video.resolution,
            "language": video.language,
            "region": video.region,
            "sub_region": video.sub_region,
            "market": video.market,
            "first_aired_date": (
                video.first_aired_date.isoformat() if video.first_aired_date else None
            ),
            "last_aired_date": video.last_aired_date.isoformat() if video.last_aired_date else None,
            "network": video.network,
            "transcript": video.transcript,
            "slogan": video.slogan,
            "cta_text": video.cta_text,
            "year": commercial.year if commercial else None,
            "decade": commercial.decade if commercial else None,
            "commercial_type": (
                commercial.commercial_type.value
                if commercial and commercial.commercial_type is not None
                else None
            ),
            "bumper_channel": commercial.bumper_channel if commercial else None,
            "campaign_name": commercial.campaign_name if commercial else None,
            "commercial_description": commercial.description if commercial else None,
            "products": [p.product for p in commercial.products] if commercial else [],
            "credits": [{"role": c.role, "name": c.name} for c in video.credits],
            "tags": [t.tag for t in video.tags],
            "metadata": video.extra_data or {},
            "phash": format_phash_hex(video.phash),
            "file_sha256": video.file_sha256,
            "audio_fingerprint": video.audio_fingerprint,
            "created_at": video.created_at.isoformat(),
            "updated_at": video.updated_at.isoformat(),
        }
        videos.append(row)
    return videos


def collect_bundle_files(bundle_dir: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in sorted(bundle_dir.rglob("*")):
        if path.is_file():
            files.append(
    (path, str(
        path.relative_to(bundle_dir)).replace(
            "\\", "/")))
    return files
