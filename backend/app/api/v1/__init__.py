from fastapi import APIRouter

from app.api.v1 import admin, auth, dmca, dumps, edits, public

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(public.router)
api_router.include_router(edits.router)
api_router.include_router(dmca.router)
api_router.include_router(admin.router)
api_router.include_router(dumps.router)
