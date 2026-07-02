from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.auth.deps import get_current_user, get_current_user_jwt, require_write_access
from app.auth.security import authenticate_user, create_access_token, get_user_by_email, get_user_by_username, hash_password, user_can_submit, user_email_verified
from app.auth.serializers import user_to_public
from app.database import get_db
from app.models import User, UserAccess, UserRole
from app.schemas import (
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenPublic,
    AccountDeletionRequestCreate,
    AccountDeletionRequestPublic,
    ChangeEmailRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MessageResponse,
    QuizAnswerSubmit,
    QuizGradeResult,
    RegistrationSettingsPublic,
    ResetPasswordRequest,
    SubmissionTermsPublic,
    Token,
    UserCreate,
    UserLogin,
    UserPublic,
    VerifyEmailRequest,
)
from app.services.registration_invites import (
    consume_invite,
    is_registration_invite_only,
    validate_invite_code,
)
from app.services.email_verification import (
    resend_verification_email,
    send_verification_email_for_user,
    verify_email_with_token,
)
from app.services.password_reset import request_password_reset, reset_password_with_token
from app.services.api_tokens import create_api_token, list_user_api_tokens, revoke_api_token
from app.services.account_settings import (
    cancel_deletion_request,
    change_email,
    change_password,
    get_user_deletion_request,
    request_account_deletion,
)
from app.services.submission_terms import (
    ensure_submission_terms_seeded,
    fallback_terms_dict,
    get_active_submission_terms,
    terms_document_to_dict,
)
from app.submission_quiz import grade_quiz, quiz_for_client

router = APIRouter(prefix="/auth", tags=["auth"])


def _deletion_request_public(record) -> AccountDeletionRequestPublic:
    return AccountDeletionRequestPublic(
        id=record.id,
        status=record.status.value,
        points_to_transfer=float(record.points_to_transfer or 0),
        username=record.user.username if getattr(record, "user", None) else None,
        recipient_username=record.recipient.username if record.recipient else None,
        review_notes=record.review_notes,
        reviewed_at=record.reviewed_at,
        created_at=record.created_at,
    )


async def _load_terms(db: AsyncSession) -> dict:
    doc = await get_active_submission_terms(db)
    if doc:
        return terms_document_to_dict(doc)
    return fallback_terms_dict()


@router.get("/registration-settings", response_model=RegistrationSettingsPublic)
async def registration_settings(db: AsyncSession = Depends(get_db)):
    return RegistrationSettingsPublic(invite_only=await is_registration_invite_only(db))


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    invite_only = await is_registration_invite_only(db)
    if invite_only:
        if not data.invite_code or not data.invite_code.strip():
            raise HTTPException(status_code=403, detail="Registration is invite-only. An invite code is required.")
        try:
            invite = await validate_invite_code(db, data.invite_code)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        invite = None

    if await get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if await get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.USER,
        access_level=UserAccess.VOTE_ONLY,
    )
    db.add(user)
    await db.flush()
    if invite is not None:
        await consume_invite(db, invite)
    await send_verification_email_for_user(db, user)
    return await user_to_public(db, user)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return Token(access_token=create_access_token(user.id, remember_me=data.remember_me))


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await request_password_reset(db, data.email)
    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        await reset_password_with_token(db, data.token, data.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message="Password updated. You can log in with your new password.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        await verify_email_with_token(db, data.token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message="Email verified. You can vote and submit edits.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    try:
        await resend_verification_email(db, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message="If your email is unverified, a new verification link has been sent.")


@router.get("/me", response_model=UserPublic)
async def me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await user_to_public(db, user)


@router.get("/submission-terms", response_model=SubmissionTermsPublic)
async def submission_terms(db: AsyncSession = Depends(get_db)):
    return SubmissionTermsPublic(**await _load_terms(db))


@router.post("/submission-terms/accept", response_model=UserPublic)
async def accept_submission_terms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    if not user_can_submit(user):
        raise HTTPException(status_code=403, detail="Submission access required")

    doc = await get_active_submission_terms(db)
    if not doc:
        doc = await ensure_submission_terms_seeded(db)

    user.submission_terms_version = doc.version
    await db.commit()
    await db.refresh(user)
    return await user_to_public(db, user)


@router.get("/submission-quiz")
async def submission_quiz(user: User = Depends(get_current_user)):
    if user_can_submit(user):
        raise HTTPException(status_code=400, detail="You already have submission access")
    return {"questions": quiz_for_client(), "pass_score": len(quiz_for_client())}


@router.post("/submission-upgrade", response_model=QuizGradeResult)
async def submission_upgrade(
    data: QuizAnswerSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    if user_can_submit(user):
        raise HTTPException(status_code=400, detail="You already have submission access")

    if not user_email_verified(user):
        raise HTTPException(status_code=403, detail="Verify your email address before upgrading.")

    score, total, passed = grade_quiz(data.answers)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail=f"Quiz not passed ({score}/{total}). Review the terms and try again.",
        )

    doc = await get_active_submission_terms(db)
    if not doc:
        doc = await ensure_submission_terms_seeded(db)

    user.access_level = UserAccess.SUBMIT_AND_VOTE
    user.submission_terms_version = doc.version
    await db.commit()
    await db.refresh(user)
    return QuizGradeResult(
        passed=True,
        score=score,
        total=total,
        access_level=user.access_level.value,
        can_submit=True,
    )


@router.get("/api-tokens", response_model=list[ApiTokenPublic])
async def list_api_tokens(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    tokens = await list_user_api_tokens(db, user.id)
    return [
        ApiTokenPublic(
            id=t.id,
            token_prefix=t.token_prefix,
            label=t.label,
            scope=t.scope,
            created_at=t.created_at,
            last_used_at=t.last_used_at,
        )
        for t in tokens
    ]


@router.post("/api-tokens", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_user_api_token(
    body: ApiTokenCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    try:
        record, raw_token = await create_api_token(db, user, body.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(record)
    return ApiTokenCreated(
        id=record.id,
        token_prefix=record.token_prefix,
        label=record.label,
        scope=record.scope,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        token=raw_token,
    )


@router.delete("/api-tokens/{token_id}", response_model=MessageResponse)
async def revoke_user_api_token(
    token_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    if not await revoke_api_token(db, user.id, token_id):
        raise HTTPException(status_code=404, detail="API token not found")
    await db.commit()
    return MessageResponse(message="API token revoked")


@router.post("/change-password", response_model=MessageResponse)
async def change_user_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    try:
        await change_password(db, user, body.current_password, body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return MessageResponse(message="Password updated.")


@router.post("/change-email", response_model=UserPublic)
async def change_user_email(
    body: ChangeEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    try:
        await change_email(db, user, body.password, body.new_email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(user)
    return await user_to_public(db, user)


@router.get("/deletion-request", response_model=AccountDeletionRequestPublic | None)
async def get_deletion_request(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    record = await get_user_deletion_request(db, user.id)
    if not record:
        return None
    return _deletion_request_public(record)


@router.post("/deletion-request", response_model=AccountDeletionRequestPublic, status_code=status.HTTP_201_CREATED)
async def create_deletion_request(
    body: AccountDeletionRequestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    try:
        record = await request_account_deletion(
            db, user, body.password, body.recipient_username
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(record, attribute_names=["recipient"])
    return _deletion_request_public(record)


@router.post("/deletion-request/cancel", response_model=MessageResponse)
async def cancel_user_deletion_request(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    try:
        await cancel_deletion_request(db, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return MessageResponse(message="Account deletion request cancelled.")
