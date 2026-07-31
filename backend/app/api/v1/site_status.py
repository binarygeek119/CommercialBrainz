"""Public site status for maintenance gate and SPA banners."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import SiteStatusPublic
from app.services.maintenance import build_site_status

router = APIRouter(tags=["site-status"])


@router.get("/site-status", response_model=SiteStatusPublic)
async def site_status(db: AsyncSession = Depends(get_db)):
    """Public maintenance + announcement snapshot (no auth)."""
    payload = await build_site_status(db)
    await db.commit()
    return SiteStatusPublic(**payload)
