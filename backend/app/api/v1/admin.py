from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin
from app.auth.security import user_bulk_submit_eligible
from app.auth.serializers import user_to_public_basic
from app.database import get_db
from app.models import (
    DMCAStatus,
    DMCATakedown,
    Edit,
    EditStatus,
    FingerprintStatus,
    MediaFingerprint,
    User,
    UserAccess,
    UserRole,
    Video,
    VideoHashStatus,
)
from app.schemas import (
    AdminBulkSubmitUpdate,
    AdminFingerprintPublic,
    AdminStats,
    AdminUserActiveUpdate,
    AdminUserPublic,
    ArchiveExportStatus,
    FingerprintQueueStatus,
    PaginatedResponse,
    RegistrationInviteCreate,
    RegistrationInviteOnlyUpdate,
    RegistrationInvitePublic,
    RegistrationSettingsPublic,
    YtdlpCookiesStatus,
    YtdlpCookiesUpdate,
)
from app.services.archive_export_queue import (
    enqueue_archive_export,
    get_archive_export_status,
    is_archive_export_running,
)
from app.services.archive_org_upload import archive_org_configured
from app.services.fingerprint_queue_status import get_fingerprint_queue_status
from app.services.hash_queue import enqueue_hash_job
from app.services.registration_invites import (
    create_registration_invite,
    invite_to_public,
    is_registration_invite_only,
    list_registration_invites,
    revoke_registration_invite,
    set_registration_invite_only,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_user_public(user: User) -> AdminUserPublic:
    return AdminUserPublic(
        **user_to_public_basic(user).model_dump(),
        is_active=user.is_active,
        bulk_submit_revoked_at=user.bulk_submit_revoked_at,
        bulk_submit_revoke_reason=user.bulk_submit_revoke_reason,
    )


@router.get("/stats", response_model=AdminStats)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    users = await db.scalar(select(func.count()).select_from(User))
    videos = await db.scalar(select(func.count()).select_from(Video))
    open_edits = await db.scalar(
        select(func.count()).select_from(Edit).where(Edit.status == EditStatus.OPEN)
    )
    pending_fp = await db.scalar(
        select(func.count())
        .select_from(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.PENDING)
    )
    failed_fp = await db.scalar(
        select(func.count())
        .select_from(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.FAILED)
    )
    pending_hash = await db.scalar(
        select(func.count()).select_from(Video).where(Video.hash_status == VideoHashStatus.PENDING)
    )
    dmca_open = await db.scalar(
        select(func.count())
        .select_from(DMCATakedown)
        .where(DMCATakedown.status.in_([DMCAStatus.SUBMITTED, DMCAStatus.UNDER_REVIEW]))
    )
    return AdminStats(
        users=users or 0,
        videos=videos or 0,
        open_edits=open_edits or 0,
        pending_fingerprints=pending_fp or 0,
        failed_fingerprints=failed_fp or 0,
        pending_video_hashes=pending_hash or 0,
        open_dmca=dmca_open or 0,
    )


@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    q: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(User).order_by(User.created_at.desc())
    count_stmt = select(func.count()).select_from(User)
    if q:
        pattern = f"%{q.strip()}%"
        filt = (User.username.ilike(pattern)) | (User.email.ilike(pattern))
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    total = await db.scalar(count_stmt)
    result = await db.execute(stmt.offset(offset).limit(limit))
    users = result.scalars().all()
    items = [_admin_user_public(u).model_dump() for u in users]
    return PaginatedResponse(items=items, total=total or len(items), offset=offset, limit=limit)


@router.post("/users/{user_id}/role/{role}", response_model=AdminUserPublic)
async def set_user_role(
    user_id: UUID,
    role: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id and role != UserRole.ADMIN.value:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")

    try:
        new_role = UserRole(role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid role") from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = new_role
    user.is_auto_editor = new_role in (UserRole.MOD, UserRole.ADMIN)
    if new_role in (UserRole.MOD, UserRole.ADMIN):
        user.access_level = UserAccess.SUBMIT_AND_VOTE
    await db.flush()
    return _admin_user_public(user)


@router.post("/users/{user_id}/access/{access}", response_model=AdminUserPublic)
async def set_user_access(
    user_id: UUID,
    access: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        new_access = UserAccess(access)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid access level") from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role in (UserRole.MOD, UserRole.ADMIN):
        raise HTTPException(status_code=400, detail="Use role change for mods/admins")

    user.access_level = new_access
    await db.flush()
    return _admin_user_public(user)


@router.post("/users/{user_id}/active", response_model=AdminUserPublic)
async def set_user_active(
    user_id: UUID,
    data: AdminUserActiveUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id and not data.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = data.is_active
    await db.flush()
    return _admin_user_public(user)


@router.post("/users/{user_id}/bulk-submit", response_model=AdminUserPublic)
async def set_user_bulk_submit(
    user_id: UUID,
    data: AdminBulkSubmitUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.enabled:
        if not user_bulk_submit_eligible(user):
            raise HTTPException(
                status_code=400,
                detail=(
                    "User must have 500+ reputation points or be a mod/admin "
                    "to enable bulk submit"
                ),
            )
        user.bulk_submit_enabled = True
        user.bulk_submit_revoked_at = None
        user.bulk_submit_revoke_reason = None
    else:
        user.bulk_submit_enabled = False
        user.bulk_submit_revoked_at = datetime.now(UTC)
        user.bulk_submit_revoke_reason = (data.revoke_reason or "").strip() or None
        # Clear terms so re-grant requires fresh acceptance of current version.
        user.power_user_terms_version = None
        user.power_user_terms_accepted_at = None

    await db.flush()
    return _admin_user_public(user)


@router.get("/fingerprint-queue", response_model=FingerprintQueueStatus)
async def fingerprint_queue(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return FingerprintQueueStatus(**await get_fingerprint_queue_status(db))


@router.get("/fingerprints", response_model=PaginatedResponse)
async def list_fingerprints(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(MediaFingerprint).order_by(MediaFingerprint.created_at.desc())
    if status:
        try:
            fp_status = FingerprintStatus(status)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid status") from e
        stmt = stmt.where(MediaFingerprint.status == fp_status)
        count_stmt = select(func.count()).select_from(MediaFingerprint).where(
            MediaFingerprint.status == fp_status
        )
    else:
        count_stmt = select(func.count()).select_from(MediaFingerprint)

    total = await db.scalar(count_stmt)
    result = await db.execute(stmt.offset(offset).limit(limit))
    rows = result.scalars().all()
    items = [AdminFingerprintPublic.from_row(r).model_dump() for r in rows]
    return PaginatedResponse(items=items, total=total or len(items), offset=offset, limit=limit)


@router.post("/fingerprints/{fingerprint_id}/retry")
async def retry_fingerprint(
    fingerprint_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    fp = await db.get(MediaFingerprint, fingerprint_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Fingerprint job not found")

    fp.status = FingerprintStatus.PENDING
    fp.retry_count = 0
    fp.error_message = None
    fp.started_at = None
    fp.completed_at = None
    if fp.video_id:
        video = await db.get(Video, fp.video_id)
        if video:
            video.hash_status = VideoHashStatus.PENDING
            extra = dict(video.extra_data or {})
            if "hash_error" in extra:
                extra = dict(extra)
                extra.pop("hash_error", None)
                video.extra_data = extra
    await db.flush()
    await enqueue_hash_job(fingerprint_id)
    return {"status": "queued", "id": str(fingerprint_id)}


@router.get("/exports/archive-org/status", response_model=ArchiveExportStatus)
async def archive_export_status(_admin: User = Depends(require_admin)):
    payload = get_archive_export_status()
    payload["configured"] = archive_org_configured()
    return ArchiveExportStatus(**payload)


@router.post("/exports/archive-org/trigger")
async def trigger_archive_export(
    admin: User = Depends(require_admin),
):
    if is_archive_export_running():
        raise HTTPException(status_code=409, detail="An Archive.org export is already running")
    if not archive_org_configured():
        from app.config import get_settings

        settings = get_settings()
        if not settings.ia_skip_upload:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Configure IA_ACCESS_KEY and IA_SECRET_KEY, or set "
                    "IA_SKIP_UPLOAD=true for local bundles only"
                ),
            )
    try:
        await enqueue_archive_export(admin.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "queued"}


@router.get("/registration-settings", response_model=RegistrationSettingsPublic)
async def admin_registration_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return RegistrationSettingsPublic(invite_only=await is_registration_invite_only(db))


@router.post("/registration-settings", response_model=RegistrationSettingsPublic)
async def admin_set_registration_settings(
    data: RegistrationInviteOnlyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    enabled = await set_registration_invite_only(db, data.invite_only)
    return RegistrationSettingsPublic(invite_only=enabled)


@router.get("/invites", response_model=PaginatedResponse)
async def admin_list_invites(
    include_revoked: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    invites = await list_registration_invites(db, include_revoked=include_revoked)
    items = [RegistrationInvitePublic(**invite_to_public(inv)).model_dump() for inv in invites]
    return PaginatedResponse(items=items, total=len(items), offset=0, limit=len(items))


@router.post("/invites", response_model=RegistrationInvitePublic, status_code=201)
async def admin_create_invite(
    data: RegistrationInviteCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        invite = await create_registration_invite(
            db,
            created_by=admin,
            label=data.label,
            max_uses=data.max_uses,
            expires_in_days=data.expires_in_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RegistrationInvitePublic(**invite_to_public(invite))


@router.post("/invites/{invite_id}/revoke", response_model=RegistrationInvitePublic)
async def admin_revoke_invite(
    invite_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        invite = await revoke_registration_invite(db, invite_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RegistrationInvitePublic(**invite_to_public(invite))


@router.get("/ytdlp-cookies", response_model=YtdlpCookiesStatus)
async def admin_ytdlp_cookies_status(_admin: User = Depends(require_admin)):
    """Status of the managed YouTube cookies file (never returns cookie contents)."""
    from app.services.ytdlp_cookies import cookies_status

    return YtdlpCookiesStatus(**cookies_status())


@router.put("/ytdlp-cookies", response_model=YtdlpCookiesStatus)
async def admin_set_ytdlp_cookies(
    data: YtdlpCookiesUpdate,
    _admin: User = Depends(require_admin),
):
    """Replace the managed Netscape cookies.txt used by yt-dlp."""
    from app.services.ytdlp_cookies import save_cookies_text

    try:
        return YtdlpCookiesStatus(**save_cookies_text(data.cookies))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not write cookies file: {e}",
        ) from e


@router.delete("/ytdlp-cookies", response_model=YtdlpCookiesStatus)
async def admin_clear_ytdlp_cookies(_admin: User = Depends(require_admin)):
    """Delete the managed cookies file."""
    from app.services.ytdlp_cookies import clear_cookies

    try:
        return YtdlpCookiesStatus(**clear_cookies())
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not clear cookies file: {e}",
        ) from e
