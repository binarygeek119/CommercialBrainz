"""Public hash-type discovery and video lookup by media hash."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import DuplicateMatchPublic, HashLookupRequest, HashTypesPublic
from app.services.fingerprint_queries import HASH_TYPES, lookup_videos_by_hash
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/hashes", tags=["hashes"])
settings = get_settings()


@router.get("/types", response_model=HashTypesPublic)
async def list_hash_types(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
):
    """List media hash types that can be used with /hashes/lookup."""
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
