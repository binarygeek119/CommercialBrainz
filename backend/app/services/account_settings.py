"""Account settings: password, email, and deletion requests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import (
    get_user_by_email,
    get_user_by_username,
    hash_password,
    user_is_mod,
    verify_password,
)
from app.models import (
    AccountDeletionRequest,
    AccountDeletionStatus,
    Edit,
    EditStatus,
    User,
)
from app.services import EditService
from app.services.api_tokens import revoke_all_api_tokens
from app.services.email_verification import send_verification_email_for_user


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")
    user.hashed_password = hash_password(new_password)
    await db.flush()


async def change_email(db: AsyncSession, user: User, password: str, new_email: str) -> None:
    if not verify_password(password, user.hashed_password):
        raise ValueError("Password is incorrect")

    normalized = new_email.strip().lower()
    if normalized == user.email.lower():
        raise ValueError("That is already your email address")

    existing = await get_user_by_email(db, normalized)
    if existing and existing.id != user.id:
        raise ValueError("Email address is already in use")

    user.email = normalized
    user.email_verified = False
    user.email_verified_at = None
    await db.flush()
    await send_verification_email_for_user(db, user)


async def get_user_deletion_request(
    db: AsyncSession, user_id: UUID
) -> AccountDeletionRequest | None:
    result = await db.execute(
        select(AccountDeletionRequest)
        .options(
            selectinload(AccountDeletionRequest.recipient),
            selectinload(AccountDeletionRequest.user),
        )
        .where(
            AccountDeletionRequest.user_id == user_id,
            AccountDeletionRequest.status == AccountDeletionStatus.PENDING,
        )
        .order_by(AccountDeletionRequest.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _count_open_edits(db: AsyncSession, user_id: UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Edit)
        .where(Edit.editor_id == user_id, Edit.status == EditStatus.OPEN)
    )
    return count or 0


async def request_account_deletion(
    db: AsyncSession,
    user: User,
    password: str,
    recipient_username: str | None = None,
) -> AccountDeletionRequest:
    if not verify_password(password, user.hashed_password):
        raise ValueError("Password is incorrect")

    if user_is_mod(user):
        raise ValueError("Moderator and admin accounts cannot be deleted through self-service")

    existing = await get_user_deletion_request(db, user.id)
    if existing:
        raise ValueError("You already have a pending account deletion request")

    open_edits = await _count_open_edits(db, user.id)
    if open_edits > 0:
        raise ValueError(
            f"You have {open_edits} open edit(s). Wait for them to close or cancel them before deleting your account."
        )

    recipient: User | None = None
    if recipient_username and recipient_username.strip():
        recipient = await get_user_by_username(db, recipient_username.strip())
        if not recipient:
            raise ValueError("Recipient username not found")
        if recipient.id == user.id:
            raise ValueError("You cannot transfer points to yourself")
        if not recipient.is_active:
            raise ValueError("Recipient account is not active")

    points = float(user.reputation_points or 0)
    if recipient is None and points > 0:
        raise ValueError(
            "Specify a recipient username to transfer your reputation points, or wait until your balance is zero"
        )

    record = AccountDeletionRequest(
        user_id=user.id,
        recipient_id=recipient.id if recipient else None,
        points_to_transfer=points if recipient else 0,
        status=AccountDeletionStatus.PENDING,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record, attribute_names=["recipient", "user"])
    return record


async def cancel_deletion_request(db: AsyncSession, user: User) -> AccountDeletionRequest:
    record = await get_user_deletion_request(db, user.id)
    if not record:
        raise ValueError("No pending account deletion request")

    record.status = AccountDeletionStatus.CANCELLED
    record.reviewed_at = datetime.now(UTC)
    await db.flush()
    return record


async def list_pending_deletion_requests(db: AsyncSession) -> list[AccountDeletionRequest]:
    result = await db.execute(
        select(AccountDeletionRequest)
        .options(
            selectinload(AccountDeletionRequest.user),
            selectinload(AccountDeletionRequest.recipient),
        )
        .where(AccountDeletionRequest.status == AccountDeletionStatus.PENDING)
        .order_by(AccountDeletionRequest.created_at.asc())
    )
    return list(result.scalars().all())


async def approve_deletion_request(
    db: AsyncSession,
    request_id: UUID,
    reviewer: User,
    review_notes: str | None = None,
) -> AccountDeletionRequest:
    result = await db.execute(
        select(AccountDeletionRequest)
        .options(
            selectinload(AccountDeletionRequest.user),
            selectinload(AccountDeletionRequest.recipient),
        )
        .where(AccountDeletionRequest.id == request_id)
    )
    record = result.scalar_one_or_none()
    if not record or record.status != AccountDeletionStatus.PENDING:
        raise ValueError("Pending deletion request not found")

    user = record.user
    if not user or not user.is_active:
        raise ValueError("User account is already inactive")

    open_edits_result = await db.execute(
        select(Edit).where(Edit.editor_id == user.id, Edit.status == EditStatus.OPEN)
    )
    for edit in open_edits_result.scalars():
        await EditService.reject_edit(db, edit)

    points = float(user.reputation_points or 0)
    transfer = min(points, float(record.points_to_transfer or 0))
    if record.recipient_id and transfer > 0:
        recipient = record.recipient or await db.get(User, record.recipient_id)
        if recipient and recipient.is_active:
            recipient.reputation_points = float(recipient.reputation_points or 0) + transfer

    user.reputation_points = 0
    await revoke_all_api_tokens(db, user.id)

    user.is_active = False
    record.status = AccountDeletionStatus.APPROVED
    record.reviewed_by_id = reviewer.id
    record.review_notes = review_notes.strip() if review_notes and review_notes.strip() else None
    record.reviewed_at = datetime.now(UTC)
    await db.flush()
    return record


async def reject_deletion_request(
    db: AsyncSession,
    request_id: UUID,
    reviewer: User,
    review_notes: str | None = None,
) -> AccountDeletionRequest:
    result = await db.execute(
        select(AccountDeletionRequest)
        .options(
            selectinload(AccountDeletionRequest.user),
            selectinload(AccountDeletionRequest.recipient),
        )
        .where(AccountDeletionRequest.id == request_id)
    )
    record = result.scalar_one_or_none()
    if not record or record.status != AccountDeletionStatus.PENDING:
        raise ValueError("Pending deletion request not found")

    record.status = AccountDeletionStatus.REJECTED
    record.reviewed_by_id = reviewer.id
    record.review_notes = review_notes.strip() if review_notes and review_notes.strip() else None
    record.reviewed_at = datetime.now(UTC)
    await db.flush()
    return record
