"""Public donate endpoints, fund bars, and admin cookie-donation backlog."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional, require_admin
from app.database import get_db
from app.models import DonationFund, User
from app.schemas import (
    CookieDonationPublic,
    CookieDonationReject,
    CookieDonationSubmit,
    CookieDonationSubmitResult,
    DonateFundCostCreate,
    DonateFundsAdmin,
    DonateFundsGoalsUpdate,
    DonateFundsPublic,
    PaginatedResponse,
)
from app.services import cookie_donations as cd
from app.services import donate_funds as funds
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/donate", tags=["donate"])


@router.get("/cookie-backlog/stats")
async def cookie_backlog_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Public counts for the cookie donation backlog (no secrets)."""
    await check_rate_limit(request, user is not None)
    counts = await cd.backlog_counts(db)
    return {
        "pending": counts.get("pending", 0),
        "active": counts.get("active", 0),
        "exhausted": counts.get("exhausted", 0),
        "rejected": counts.get("rejected", 0),
    }


@router.get("/funds", response_model=DonateFundsPublic)
async def public_donate_funds(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Public Domain / Cloud VM fund balances for the donate page bars."""
    await check_rate_limit(request, user is not None)
    payload = await funds.public_funds_payload(db, maybe_sync=True)
    await db.commit()
    return DonateFundsPublic(**payload)


@router.post("/bmc-webhook")
async def buymeacoffee_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Buy Me a Coffee webhook — verify signature then sync supporters."""
    raw = await request.body()
    signature = request.headers.get("x-signature-sha256")
    if not funds.verify_bmc_webhook_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    event_type = payload.get("type") if isinstance(payload, dict) else None
    if event_type in funds.WEBHOOK_SYNC_EVENTS and funds.sync_configured():
        try:
            await funds.sync_supporters(db, force=True)
            await db.commit()
        except ValueError:
            # Token missing — acknowledge webhook anyway.
            pass
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            raise HTTPException(status_code=502, detail=f"Sync failed: {exc}") from exc
    return {"ok": True}


@router.post(
    "/cookies",
    response_model=CookieDonationSubmitResult,
    status_code=status.HTTP_201_CREATED,
)
async def submit_donated_cookies(
    data: CookieDonationSubmit,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Queue a Netscape cookies.txt donation for YouTube metadata/hash scraping."""
    await check_rate_limit(request, user is not None)
    try:
        row = await cd.submit_cookie_donation(
            db,
            cookies=data.cookies,
            agreement_accepted=data.agreement_accepted,
            donor_note=data.donor_note,
            donor=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not store cookies: {exc}") from exc
    await db.commit()
    return CookieDonationSubmitResult(
        id=row.id,
        status=row.status.value,
        message=(
            "Thanks — your cookies are now active for YouTube scraping."
            if row.status.value == "active"
            else "Thanks — your cookies were added to the backlog and will be used when needed."
        ),
    )


@router.get("/admin/funds", response_model=DonateFundsAdmin)
async def admin_donate_funds(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    payload = await funds.admin_funds_payload(db)
    return DonateFundsAdmin(**payload)


@router.put("/admin/funds/goals", response_model=DonateFundsAdmin)
async def admin_set_fund_goals(
    body: DonateFundsGoalsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        payload = await funds.set_goals(
            db,
            domain_goal=body.domain_goal,
            cloud_vm_goal=body.cloud_vm_goal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return DonateFundsAdmin(**payload)


@router.post(
    "/admin/funds/costs",
    response_model=DonateFundsAdmin,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_fund_cost(
    body: DonateFundCostCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        await funds.add_cost(
            db,
            fund=DonationFund(body.fund),
            amount=body.amount,
            note=body.note,
            paid_at=body.paid_at,
            created_by=admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    payload = await funds.admin_funds_payload(db)
    return DonateFundsAdmin(**payload)


@router.delete("/admin/funds/costs/{cost_id}", response_model=DonateFundsAdmin)
async def admin_delete_fund_cost(
    cost_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ok = await funds.delete_cost(db, cost_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Cost not found")
    await db.commit()
    payload = await funds.admin_funds_payload(db)
    return DonateFundsAdmin(**payload)


@router.post("/admin/funds/sync", response_model=DonateFundsAdmin)
async def admin_sync_fund_donations(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        payload = await funds.sync_supporters(db, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await db.commit()  # persist last_sync_error
        raise HTTPException(status_code=502, detail=f"Sync failed: {exc}") from exc
    await db.commit()
    return DonateFundsAdmin(**payload)


@router.get("/admin/cookies", response_model=PaginatedResponse)
async def admin_list_cookie_donations(
    status_filter: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    rows = await cd.list_cookie_donations(
        db, status=status_filter, offset=offset, limit=limit
    )
    counts = await cd.backlog_counts(db)
    total = sum(counts.values())
    if status_filter:
        total = counts.get(status_filter, 0)
    return PaginatedResponse(
        items=[CookieDonationPublic(**cd.donation_public_dict(r)) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/admin/cookies/activate-next", response_model=CookieDonationPublic)
async def admin_activate_next_cookie(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = await cd.activate_next_pending(db)
    if not row:
        raise HTTPException(status_code=404, detail="No pending cookie donations")
    await db.commit()
    return CookieDonationPublic(**cd.donation_public_dict(row))


@router.post("/admin/cookies/rotate", response_model=CookieDonationPublic)
async def admin_rotate_cookie_donation(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Exhaust the active donation and promote the next pending one."""
    row = await cd.rotate_exhausted_to_next(db)
    if not row:
        raise HTTPException(status_code=404, detail="No pending cookie donations to rotate to")
    await db.commit()
    return CookieDonationPublic(**cd.donation_public_dict(row))


@router.post("/admin/cookies/{donation_id}/reject", response_model=CookieDonationPublic)
async def admin_reject_cookie_donation(
    donation_id: UUID,
    body: CookieDonationReject,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = await cd.get_cookie_donation(db, donation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        row = await cd.reject_donation(db, row, reviewer=admin, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return CookieDonationPublic(**cd.donation_public_dict(row))
