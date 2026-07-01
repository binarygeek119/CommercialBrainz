import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import Advertiser, Commercial, Video, VideoVisibility

router = APIRouter(prefix="/dumps", tags=["dumps"])


@router.get("/latest")
async def latest_dump_info():
    dumps_dir = Path("dumps")
    if not dumps_dir.exists():
        return {"available": False, "message": "No dumps generated yet"}
    files = sorted(dumps_dir.glob("commercialbrainz-*.json.gz"), reverse=True)
    if not files:
        return {"available": False, "message": "No dumps generated yet"}
    latest = files[0]
    return {
        "available": True,
        "filename": latest.name,
        "url": f"/api/v1/dumps/files/{latest.name}",
        "size_bytes": latest.stat().st_size,
    }


@router.get("/files/{filename}")
async def download_dump(filename: str):
    from fastapi.responses import FileResponse

    path = Path("dumps") / filename
    if not path.exists() or ".." in filename:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Dump not found")
    return FileResponse(path, media_type="application/gzip", filename=filename)


async def generate_dump(output_dir: Path | None = None) -> Path:
    output_dir = output_dir or Path("dumps")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    output_path = output_dir / f"commercialbrainz-{date_str}.json.gz"

    async with async_session_factory() as db:
        result = await db.execute(
            select(Video)
            .options(
                selectinload(Video.commercial).selectinload(Commercial.advertiser),
                selectinload(Video.commercial).selectinload(Commercial.agency),
            )
            .where(Video.visibility == VideoVisibility.PUBLIC)
        )
        videos = result.scalars().all()

        dump_data = {
            "generated_at": datetime.now(UTC).isoformat(),
            "license": "CC0-1.0",
            "videos": [],
        }
        for v in videos:
            dump_data["videos"].append(
                {
                    "sbid": str(v.sbid),
                    "youtube_id": v.youtube_id,
                    "youtube_url": v.youtube_url,
                    "commercial_title": v.commercial.title if v.commercial else None,
                    "advertiser": v.commercial.advertiser.name
                    if v.commercial and v.commercial.advertiser
                    else None,
                    "agency": v.commercial.agency.name if v.commercial and v.commercial.agency else None,
                    "duration_ms": v.duration_ms,
                    "language": v.language,
                    "region": v.region,
                    "sub_region": v.sub_region,
                    "metadata": v.extra_data,
                }
            )

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        json.dump(dump_data, f)

    return output_path
