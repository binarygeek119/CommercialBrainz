from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import authenticate_user, create_access_token, get_user_by_email, get_user_by_username, hash_password, user_can_submit
from app.auth.serializers import user_to_public
from app.database import get_db
from app.models import User, UserAccess, UserRole
from app.schemas import (
    ForgotPasswordRequest,
    MessageResponse,
    QuizAnswerSubmit,
    QuizGradeResult,
    ResetPasswordRequest,
    SubmissionTermsPublic,
    Token,
    UserCreate,
    UserLogin,
    UserPublic,
)
from app.services.password_reset import request_password_reset, reset_password_with_token
from app.services.submission_terms import (
    ensure_submission_terms_seeded,
    fallback_terms_dict,
    get_active_submission_terms,
    terms_document_to_dict,
)
from app.submission_quiz import grade_quiz, quiz_for_client

router = APIRouter(prefix="/auth", tags=["auth"])


async def _load_terms(db: AsyncSession) -> dict:
    doc = await get_active_submission_terms(db)
    if doc:
        return terms_document_to_dict(doc)
    return fallback_terms_dict()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
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
    return user_to_public(user)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_access_token(user.id))


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


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return user_to_public(user)


@router.get("/submission-terms", response_model=SubmissionTermsPublic)
async def submission_terms(db: AsyncSession = Depends(get_db)):
    return SubmissionTermsPublic(**await _load_terms(db))


@router.post("/submission-terms/accept", response_model=UserPublic)
async def accept_submission_terms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user_can_submit(user):
        raise HTTPException(status_code=403, detail="Submission access required")

    doc = await get_active_submission_terms(db)
    if not doc:
        doc = await ensure_submission_terms_seeded(db)

    user.submission_terms_version = doc.version
    await db.commit()
    await db.refresh(user)
    return user_to_public(user)


@router.get("/submission-quiz")
async def submission_quiz(user: User = Depends(get_current_user)):
    if user_can_submit(user):
        raise HTTPException(status_code=400, detail="You already have submission access")
    return {"questions": quiz_for_client(), "pass_score": len(quiz_for_client())}


@router.post("/submission-upgrade", response_model=QuizGradeResult)
async def submission_upgrade(
    data: QuizAnswerSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user_can_submit(user):
        raise HTTPException(status_code=400, detail="You already have submission access")

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
