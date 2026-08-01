"""Community voting on possible hash-duplicate videos."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional, require_submitter
from app.database import get_db
from app.models import DuplicateIssue, DuplicateVoteChoice, User
from app.schemas import (
    DuplicateIssuePublic,
    DuplicateIssueVoteCreate,
    PaginatedResponse,
)
from app.services.duplicate_issues import (
    cast_duplicate_vote,
    clear_duplicate_vote,
    get_open_duplicate_issue,
    list_open_duplicate_issues,
)

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.get("", response_model=PaginatedResponse)
async def list_duplicates(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    items, total = await list_open_duplicate_issues(
        db,
        offset=offset,
        limit=limit,
        viewer_id=viewer.id if viewer else None,
    )
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{issue_id}", response_model=DuplicateIssuePublic)
async def get_duplicate(
    issue_id: UUID,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    payload = await get_open_duplicate_issue(
        db, issue_id, viewer_id=viewer.id if viewer else None
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Duplicate issue not found")
    return DuplicateIssuePublic(**payload)


@router.post("/{issue_id}/vote", response_model=DuplicateIssuePublic)
async def vote_on_duplicate(
    issue_id: UUID,
    body: DuplicateIssueVoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    issue = await db.get(DuplicateIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Duplicate issue not found")
    try:
        choice = DuplicateVoteChoice(body.choice)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "choice must be add_as_sub_link, remove_from_database, or make_master_link"
            ),
        ) from exc
    try:
        await cast_duplicate_vote(
            db, issue, user.id, choice, body.subject_video_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    payload = await get_open_duplicate_issue(db, issue_id, viewer_id=user.id)
    if not payload:
        raise HTTPException(status_code=404, detail="Duplicate issue not found")
    return DuplicateIssuePublic(**payload)


@router.delete("/{issue_id}/vote", response_model=DuplicateIssuePublic)
async def clear_vote_on_duplicate(
    issue_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    issue = await db.get(DuplicateIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Duplicate issue not found")
    try:
        await clear_duplicate_vote(db, issue, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    from app.services.duplicate_issues import issue_to_public

    await db.refresh(issue)
    payload = await issue_to_public(db, issue, viewer_id=user.id)
    return DuplicateIssuePublic(**payload)
