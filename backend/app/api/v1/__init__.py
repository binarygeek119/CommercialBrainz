from fastapi import APIRouter

from app.api.v1 import (
    admin,
    advertiser_logos,
    auth,
    commercial_videos,
    dmca,
    dumps,
    edits,
    hashes,
    media,
    mod_panel,
    public,
    reports,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(public.router)
api_router.include_router(hashes.router)
api_router.include_router(media.router)
api_router.include_router(advertiser_logos.router)
api_router.include_router(commercial_videos.router)
api_router.include_router(edits.router)
api_router.include_router(dmca.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(mod_panel.router)
api_router.include_router(dumps.router)
