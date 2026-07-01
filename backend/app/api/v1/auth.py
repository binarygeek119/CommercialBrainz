from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import authenticate_user, create_access_token, get_user_by_email, get_user_by_username, hash_password, user_can_submit
from app.auth.serializers import user_to_public
from app.database import get_db
from app.models import User, UserAccess, UserRole
from app.schemas import QuizAnswerSubmit, QuizGradeResult, SubmissionTermsPublic, Token, UserCreate, UserLogin, UserPublic
from app.submission_quiz import grade_quiz, quiz_for_client
from app.submission_terms import SUBMISSION_TERMS

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return user_to_public(user)


@router.get("/submission-terms", response_model=SubmissionTermsPublic)
async def submission_terms():
    return SubmissionTermsPublic(**SUBMISSION_TERMS)


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

    user.access_level = UserAccess.SUBMIT_AND_VOTE
    await db.commit()
    await db.refresh(user)
    return QuizGradeResult(
        passed=True,
        score=score,
        total=total,
        access_level=user.access_level.value,
        can_submit=True,
    )
