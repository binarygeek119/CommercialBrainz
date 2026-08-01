"""Possible-duplicate issues: detect, vote, and resolve."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    Commercial,
    DuplicateIssue,
    DuplicateIssueStatus,
    DuplicateIssueVote,
    DuplicateVoteChoice,
    Video,
    VideoVisibility,
)
from app.services.fingerprint_queries import (
    find_audio_fingerprint_matches,
    find_file_sha256_matches,
    find_phash_duplicates,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def canonical_pair(video_a: UUID, video_b: UUID) -> tuple[UUID, UUID]:
    if video_a == video_b:
        raise ValueError("Cannot pair a video with itself")
    return (video_a, video_b) if video_a.int < video_b.int else (video_b, video_a)


async def find_hash_matches_for_video(db: AsyncSession, video: Video) -> list[dict]:
    """Match a catalog video against other public videos by stored hashes."""
    matches: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _extend(rows: list[dict]) -> None:
        for row in rows:
            key = (row["video_sbid"], row["match_type"])
            if key in seen:
                continue
            seen.add(key)
            matches.append(row)

    if video.file_sha256:
        _extend(
            await find_file_sha256_matches(
                db, video.file_sha256, exclude_video_id=video.sbid, public_only=True
            )
        )
    if video.audio_fingerprint:
        _extend(
            await find_audio_fingerprint_matches(
                db,
                video.audio_fingerprint,
                exclude_video_id=video.sbid,
                public_only=True,
            )
        )
    if video.phash is not None:
        _extend(
            await find_phash_duplicates(
                db, video.phash, exclude_video_id=video.sbid, public_only=True
            )
        )

    type_rank = {"file_sha256": 0, "audio_fingerprint": 1, "phash": 2}
    matches.sort(
        key=lambda row: (
            type_rank.get(row["match_type"], 9),
            row["hamming_distance"] if row["hamming_distance"] is not None else -1,
            row["youtube_id"],
        )
    )
    return matches


def _match_meta_for_partner(matches: list[dict], partner_id: UUID) -> dict:
    types: list[str] = []
    best_type: str | None = None
    distance: int | None = None
    partner = str(partner_id)
    for row in matches:
        if row["video_sbid"] != partner:
            continue
        mt = row["match_type"]
        if mt not in types:
            types.append(mt)
        if best_type is None:
            best_type = mt
            distance = row.get("hamming_distance")
    return {
        "match_types": types,
        "best_match_type": best_type,
        "hamming_distance": distance,
    }


async def _next_generation(db: AsyncSession, a: UUID, b: UUID) -> int:
    current = await db.scalar(
        select(func.max(DuplicateIssue.generation)).where(
            DuplicateIssue.video_a_id == a,
            DuplicateIssue.video_b_id == b,
        )
    )
    return int(current or 0) + 1


async def _supersede_open_issues(db: AsyncSession, video_ids: set[UUID]) -> list[DuplicateIssue]:
    if not video_ids:
        return []
    result = await db.execute(
        select(DuplicateIssue)
        .options(selectinload(DuplicateIssue.votes))
        .where(
            DuplicateIssue.status == DuplicateIssueStatus.OPEN,
            or_(
                DuplicateIssue.video_a_id.in_(video_ids),
                DuplicateIssue.video_b_id.in_(video_ids),
            ),
        )
    )
    issues = list(result.scalars().all())
    for issue in issues:
        issue.status = DuplicateIssueStatus.SUPERSEDED
        issue.updated_at = datetime.now(UTC)
    return issues


async def _create_open_issue(
    db: AsyncSession,
    video_id: UUID,
    partner_id: UUID,
    *,
    match_types: list[str],
    best_match_type: str | None,
    hamming_distance: int | None,
) -> DuplicateIssue:
    a, b = canonical_pair(video_id, partner_id)
    generation = await _next_generation(db, a, b)
    issue = DuplicateIssue(
        status=DuplicateIssueStatus.OPEN,
        video_a_id=a,
        video_b_id=b,
        match_types=list(match_types),
        best_match_type=best_match_type,
        hamming_distance=hamming_distance,
        generation=generation,
    )
    db.add(issue)
    return issue


async def register_duplicates_for_video(db: AsyncSession, video_id: UUID) -> int:
    """
    After fingerprinting, open/refresh duplicate issues for hash matches.

    If a new partner appears for a video that already has open issues, those
    issues are superseded and voting starts over for the fresh pairs.
    """
    video = await db.get(Video, video_id)
    if not video or video.visibility != VideoVisibility.PUBLIC:
        return 0
    if not video.file_sha256 and not video.audio_fingerprint and video.phash is None:
        return 0

    matches = await find_hash_matches_for_video(db, video)
    match_ids = {UUID(row["video_sbid"]) for row in matches}
    if not match_ids:
        return 0

    open_result = await db.execute(
        select(DuplicateIssue).where(
            DuplicateIssue.status == DuplicateIssueStatus.OPEN,
            or_(
                DuplicateIssue.video_a_id == video_id,
                DuplicateIssue.video_b_id == video_id,
            ),
        )
    )
    open_issues = list(open_result.scalars().all())
    existing_partners: set[UUID] = set()
    for issue in open_issues:
        other = issue.video_b_id if issue.video_a_id == video_id else issue.video_a_id
        existing_partners.add(other)

    new_partners = match_ids - existing_partners
    created = 0

    if new_partners or not open_issues:
        touched = {video_id} | match_ids | existing_partners
        await _supersede_open_issues(db, touched)
        await db.flush()
        for partner_id in match_ids:
            meta = _match_meta_for_partner(matches, partner_id)
            if not meta["match_types"]:
                continue
            await _create_open_issue(
                db,
                video_id,
                partner_id,
                match_types=meta["match_types"],
                best_match_type=meta["best_match_type"],
                hamming_distance=meta["hamming_distance"],
            )
            created += 1
        # Recreate superseded pairs among previous partners that still match each other
        # only via the new video's match graph — keep scope to video_id pairs for clarity.
        logger.info(
            "Opened %d duplicate issue(s) for video %s (restart=%s)",
            created,
            video_id,
            bool(new_partners and open_issues),
        )
        return created

    # Same partner set: refresh metadata on existing open issues.
    by_partner = {
        (issue.video_b_id if issue.video_a_id == video_id else issue.video_a_id): issue
        for issue in open_issues
    }
    for partner_id in match_ids:
        meta = _match_meta_for_partner(matches, partner_id)
        issue = by_partner.get(partner_id)
        if not issue:
            await _create_open_issue(
                db,
                video_id,
                partner_id,
                match_types=meta["match_types"],
                best_match_type=meta["best_match_type"],
                hamming_distance=meta["hamming_distance"],
            )
            created += 1
            continue
        issue.match_types = list(meta["match_types"])
        issue.best_match_type = meta["best_match_type"]
        issue.hamming_distance = meta["hamming_distance"]
        issue.updated_at = datetime.now(UTC)
    return created


async def _move_video_to_commercial(
    db: AsyncSession,
    video: Video,
    target_commercial_id: UUID,
) -> None:
    from app.services.video_popularity import recompute_main_video

    source_id = video.commercial_id
    if source_id == target_commercial_id:
        return
    video.commercial_id = target_commercial_id
    await db.flush()
    await recompute_main_video(db, source_id)
    await recompute_main_video(db, target_commercial_id)

    remaining = await db.scalar(
        select(func.count())
        .select_from(Video)
        .where(
            Video.commercial_id == source_id,
            Video.visibility == VideoVisibility.PUBLIC,
        )
    )
    if int(remaining or 0) == 0:
        source = await db.get(Commercial, source_id)
        if source:
            await db.delete(source)


async def apply_duplicate_resolution(
    db: AsyncSession,
    issue: DuplicateIssue,
    choice: DuplicateVoteChoice,
    subject_video_id: UUID,
) -> None:
    """Apply the winning vote action."""
    from app.services.video_popularity import recompute_main_video

    other_id = (
        issue.video_b_id if subject_video_id == issue.video_a_id else issue.video_a_id
    )
    subject = await db.get(Video, subject_video_id)
    other = await db.get(Video, other_id)
    if not subject or not other:
        raise ValueError("Duplicate issue videos missing")

    if choice == DuplicateVoteChoice.REMOVE_FROM_DATABASE:
        commercial_id = subject.commercial_id
        subject.visibility = VideoVisibility.REMOVED
        await db.flush()
        await recompute_main_video(db, commercial_id)
        return

    if choice == DuplicateVoteChoice.ADD_AS_SUB_LINK:
        # Keep `other`'s commercial; attach subject as a sub link there.
        await _move_video_to_commercial(db, subject, other.commercial_id)
        await recompute_main_video(db, other.commercial_id)
        return

    if choice == DuplicateVoteChoice.MAKE_MASTER_LINK:
        # Both on subject's commercial; subject becomes main link (force, not popularity).
        await _move_video_to_commercial(db, other, subject.commercial_id)
        commercial = await db.get(Commercial, subject.commercial_id)
        if commercial:
            commercial.main_video_id = subject.sbid
        return

    raise ValueError(f"Unknown duplicate vote choice: {choice}")


async def evaluate_duplicate_votes(db: AsyncSession, issue: DuplicateIssue) -> bool:
    """Resolve the issue when one (choice, subject) reaches the threshold."""
    if issue.status != DuplicateIssueStatus.OPEN:
        return False

    result = await db.execute(
        select(DuplicateIssueVote).where(DuplicateIssueVote.issue_id == issue.id)
    )
    votes = list(result.scalars().all())
    tallies: dict[tuple[str, UUID], int] = defaultdict(int)
    for vote in votes:
        tallies[(vote.choice.value, vote.subject_video_id)] += 1

    threshold = settings.duplicate_vote_threshold
    winner: tuple[DuplicateVoteChoice, UUID] | None = None
    for (choice_val, subject_id), count in tallies.items():
        if count >= threshold:
            winner = (DuplicateVoteChoice(choice_val), subject_id)
            break
    if not winner:
        return False

    choice, subject_id = winner
    await apply_duplicate_resolution(db, issue, choice, subject_id)
    issue.status = DuplicateIssueStatus.RESOLVED
    issue.resolved_choice = choice
    issue.resolved_subject_video_id = subject_id
    issue.resolved_at = datetime.now(UTC)
    issue.updated_at = datetime.now(UTC)
    logger.info(
        "Resolved duplicate issue %s with %s on subject %s",
        issue.id,
        choice.value,
        subject_id,
    )
    return True


async def cast_duplicate_vote(
    db: AsyncSession,
    issue: DuplicateIssue,
    voter_id: UUID,
    choice: DuplicateVoteChoice,
    subject_video_id: UUID,
) -> DuplicateIssueVote:
    if issue.status != DuplicateIssueStatus.OPEN:
        raise ValueError("This duplicate issue is no longer open for voting")
    if subject_video_id not in (issue.video_a_id, issue.video_b_id):
        raise ValueError("Subject must be one of the two videos in the issue")

    result = await db.execute(
        select(DuplicateIssueVote).where(
            DuplicateIssueVote.issue_id == issue.id,
            DuplicateIssueVote.voter_id == voter_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.choice = choice
        existing.subject_video_id = subject_video_id
        vote = existing
    else:
        vote = DuplicateIssueVote(
            issue_id=issue.id,
            voter_id=voter_id,
            choice=choice,
            subject_video_id=subject_video_id,
        )
        db.add(vote)
    await db.flush()
    await evaluate_duplicate_votes(db, issue)
    return vote


async def clear_duplicate_vote(
    db: AsyncSession, issue: DuplicateIssue, voter_id: UUID
) -> None:
    if issue.status != DuplicateIssueStatus.OPEN:
        raise ValueError("This duplicate issue is no longer open for voting")
    result = await db.execute(
        select(DuplicateIssueVote).where(
            DuplicateIssueVote.issue_id == issue.id,
            DuplicateIssueVote.voter_id == voter_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()


def _tally_votes(votes: list[DuplicateIssueVote]) -> list[dict]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for vote in votes:
        counts[(vote.choice.value, str(vote.subject_video_id))] += 1
    return [
        {
            "choice": choice,
            "subject_video_id": subject,
            "count": count,
        }
        for (choice, subject), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]


async def _video_card(db: AsyncSession, video: Video | None) -> dict | None:
    if not video:
        return None
    from app.services.video_popularity import enrich_video_public, list_commercial_video_meta
    from app.services.video_response import video_to_public_dict

    main_id, viewer_votes = await list_commercial_video_meta(db, video.commercial_id)
    return enrich_video_public(
        video_to_public_dict(video),
        main_video_id=main_id,
        viewer_votes=viewer_votes,
        video=video,
    )


async def issue_to_public(
    db: AsyncSession,
    issue: DuplicateIssue,
    *,
    viewer_id: UUID | None = None,
) -> dict:
    votes = list(issue.votes) if issue.votes is not None else []
    if not votes:
        result = await db.execute(
            select(DuplicateIssueVote).where(DuplicateIssueVote.issue_id == issue.id)
        )
        votes = list(result.scalars().all())

    video_a = issue.video_a or await db.get(Video, issue.video_a_id)
    video_b = issue.video_b or await db.get(Video, issue.video_b_id)

    my_vote = None
    if viewer_id:
        for vote in votes:
            if vote.voter_id == viewer_id:
                my_vote = {
                    "choice": vote.choice.value,
                    "subject_video_id": str(vote.subject_video_id),
                }
                break

    return {
        "id": issue.id,
        "status": issue.status.value,
        "generation": issue.generation,
        "match_types": list(issue.match_types or []),
        "best_match_type": issue.best_match_type,
        "hamming_distance": issue.hamming_distance,
        "vote_threshold": settings.duplicate_vote_threshold,
        "tallies": _tally_votes(votes),
        "my_vote": my_vote,
        "vote_count": len(votes),
        "video_a": await _video_card(db, video_a),
        "video_b": await _video_card(db, video_b),
        "resolved_choice": issue.resolved_choice.value if issue.resolved_choice else None,
        "resolved_subject_video_id": issue.resolved_subject_video_id,
        "resolved_at": issue.resolved_at,
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
    }


async def list_open_duplicate_issues(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 25,
    viewer_id: UUID | None = None,
) -> tuple[list[dict], int]:
    total = await db.scalar(
        select(func.count())
        .select_from(DuplicateIssue)
        .where(DuplicateIssue.status == DuplicateIssueStatus.OPEN)
    ) or 0
    result = await db.execute(
        select(DuplicateIssue)
        .options(
            selectinload(DuplicateIssue.votes),
            selectinload(DuplicateIssue.video_a),
            selectinload(DuplicateIssue.video_b),
        )
        .where(DuplicateIssue.status == DuplicateIssueStatus.OPEN)
        .order_by(DuplicateIssue.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    issues = list(result.scalars().all())
    items = [await issue_to_public(db, issue, viewer_id=viewer_id) for issue in issues]
    return items, int(total)


async def get_open_duplicate_issue(
    db: AsyncSession,
    issue_id: UUID,
    *,
    viewer_id: UUID | None = None,
) -> dict | None:
    result = await db.execute(
        select(DuplicateIssue)
        .options(
            selectinload(DuplicateIssue.votes),
            selectinload(DuplicateIssue.video_a),
            selectinload(DuplicateIssue.video_b),
        )
        .where(DuplicateIssue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if not issue:
        return None
    return await issue_to_public(db, issue, viewer_id=viewer_id)
