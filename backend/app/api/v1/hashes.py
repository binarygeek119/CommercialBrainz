"""Public hash grab and lookup APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import (
    DuplicateMatchPublic,
    HashLookupRequest,
    HashTypesPublic,
    PaginatedResponse,
    VideoHashesPublic,
)
from app.services.fingerprint_queries import (
    HASH_TYPES,
    get_video_hashes_by_sbid,
    get_video_hashes_by_youtube_id,
    list_video_hashes,
    lookup_videos_by_hash,
    video_hashes_dict,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/hashes", tags=["hashes"])
settings = get_settings()


@router.get("/types", response_model=HashTypesPublic)
async def list_hash_types(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
):
    """List media hash types available for grab and lookup."""
    await check_rate_limit(request, user is not None)
    return HashTypesPublic(
        hash_types=list(HASH_TYPES),
        phash_duplicate_threshold=settings.phash_duplicate_threshold,
        notes={
            "phash": "64-bit perceptual hash (hex). Lookup uses Hamming distance ≤ threshold.",
            "file_sha256": "SHA-256 hex digest of the downloaded media file (exact match).",
            "audio_fingerprint": "Chromaprint string from fpcalc (exact match; prefer POST).",
        },
    )


@router.get("", response_model=PaginatedResponse)
async def list_hashes(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    hashed_only: bool = Query(
        default=False,
        description="If true, only include videos that have at least one hash stored",
    ),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Grab a paginated catalog of media hashes for public videos."""
    await check_rate_limit(request, user is not None)
    videos, total = await list_video_hashes(
        db,
        offset=offset,
        limit=limit,
        hashed_only=hashed_only,
        public_only=True,
    )
    items = [VideoHashesPublic(**video_hashes_dict(v)).model_dump(mode="json") for v in videos]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/videos/{sbid}", response_model=VideoHashesPublic)
async def get_hashes_by_video(
    sbid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Grab all stored hashes for a public video by CommercialBrainz ID."""
    await check_rate_limit(request, user is not None)
    video = await get_video_hashes_by_sbid(db, sbid, public_only=True)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoHashesPublic(**video_hashes_dict(video))


@router.get("/youtube/{youtube_id}", response_model=VideoHashesPublic)
async def get_hashes_by_youtube_id(
    youtube_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Grab all stored hashes for a public video by YouTube ID."""
    await check_rate_limit(request, user is not None)
    try:
        video = await get_video_hashes_by_youtube_id(db, youtube_id, public_only=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoHashesPublic(**video_hashes_dict(video))


async def _run_lookup(
    db: AsyncSession,
    *,
    phash: str | None,
    file_sha256: str | None,
    audio_fingerprint: str | None,
    threshold: int | None,
) -> list[DuplicateMatchPublic]:
    try:
        matches = await lookup_videos_by_hash(
            db,
            phash=phash,
            file_sha256=file_sha256,
            audio_fingerprint=audio_fingerprint,
            threshold=threshold,
            public_only=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [DuplicateMatchPublic(**match) for match in matches]


@router.get("/lookup", response_model=list[DuplicateMatchPublic])
async def lookup_by_hash_get(
    request: Request,
    phash: str | None = Query(default=None, max_length=32),
    file_sha256: str | None = Query(default=None, max_length=128),
    audio_fingerprint: str | None = Query(default=None, max_length=8000),
    threshold: int | None = Query(default=None, ge=0, le=64),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Look up public videos by exactly one hash query parameter."""
    await check_rate_limit(request, user is not None)
    return await _run_lookup(
        db,
        phash=phash,
        file_sha256=file_sha256,
        audio_fingerprint=audio_fingerprint,
        threshold=threshold,
    )


@router.post("/lookup", response_model=list[DuplicateMatchPublic])
async def lookup_by_hash_post(
    body: HashLookupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Look up public videos by hash (supports long Chromaprint values)."""
    await check_rate_limit(request, user is not None)
    return await _run_lookup(
        db,
        phash=body.phash,
        file_sha256=body.file_sha256,
        audio_fingerprint=body.audio_fingerprint,
        threshold=body.threshold,
    )
