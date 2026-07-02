"""Commercial video link popularity voting and main link selection."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Commercial,
    LogoPopularityChoice,
    User,
    Video,
    VideoPopularityVote,
    VideoVisibility,
)


def video_link_label(video: Video) -> str:
    if video.version_label and video.version_label.strip():
        return video.version_label.strip()
    if video.slogan and video.slogan.strip():
        return video.slogan.strip()
    if video.youtube_id:
        return video.youtube_id
    return "Video link"


async def recompute_main_video(db: AsyncSession, commercial_id: UUID) -> None:
    commercial = await db.get(Commercial, commercial_id)
    if not commercial:
        return

    result = await db.execute(
        select(Video)
        .where(Video.commercial_id == commercial_id, Video.visibility == VideoVisibility.PUBLIC)
        .order_by(
            Video.popularity_score.desc(),
            Video.created_at.asc(),
        )
        .limit(1)
    )
    top = result.scalar_one_or_none()
    commercial.main_video_id = top.sbid if top else None


async def refresh_video_popularity(db: AsyncSession, video_id: UUID) -> int:
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (VideoPopularityVote.choice == LogoPopularityChoice.UP, 1),
                        else_=-1,
                    )
                ),
                0,
            )
        ).where(VideoPopularityVote.video_id == video_id)
    )
    score = int(result.scalar() or 0)
    video = await db.get(Video, video_id)
    if video:
        video.popularity_score = score
        await recompute_main_video(db, video.commercial_id)
    return score


async def cast_video_popularity_vote(
    db: AsyncSession,
    video: Video,
    voter: User,
    choice: LogoPopularityChoice | None,
) -> VideoPopularityVote | None:
    existing = await db.execute(
        select(VideoPopularityVote).where(
            VideoPopularityVote.video_id == video.sbid,
            VideoPopularityVote.voter_id == voter.id,
        )
    )
    vote = existing.scalar_one_or_none()

    if choice is None:
        if vote:
            await db.delete(vote)
            await db.flush()
            await refresh_video_popularity(db, video.sbid)
        return None

    if vote:
        if vote.choice == choice:
            return vote
        vote.choice = choice
    else:
        vote = VideoPopularityVote(video_id=video.sbid, voter_id=voter.id, choice=choice)
        db.add(vote)

    await db.flush()
    await refresh_video_popularity(db, video.sbid)
    return vote


async def get_video_for_commercial(
    db: AsyncSession, commercial_id: UUID, video_id: UUID
) -> Video | None:
    result = await db.execute(
        select(Video).where(
            Video.sbid == video_id,
            Video.commercial_id == commercial_id,
            Video.visibility == VideoVisibility.PUBLIC,
        )
    )
    return result.scalar_one_or_none()


async def list_commercial_video_meta(
    db: AsyncSession,
    commercial_id: UUID,
    *,
    viewer: User | None = None,
) -> tuple[UUID | None, dict[UUID, LogoPopularityChoice]]:
    commercial = await db.get(Commercial, commercial_id)
    main_id = commercial.main_video_id if commercial else None

    viewer_votes: dict[UUID, LogoPopularityChoice] = {}
    if viewer:
        result = await db.execute(
            select(VideoPopularityVote)
            .join(Video, Video.sbid == VideoPopularityVote.video_id)
            .where(
                Video.commercial_id == commercial_id,
                Video.visibility == VideoVisibility.PUBLIC,
                VideoPopularityVote.voter_id == viewer.id,
            )
        )
        viewer_votes = {v.video_id: v.choice for v in result.scalars().all()}

    return main_id, viewer_votes


def enrich_video_public(
    video_public: dict,
    *,
    main_video_id: UUID | None,
    viewer_votes: dict[UUID, LogoPopularityChoice],
    video: Video,
) -> dict:
    choice = viewer_votes.get(video.sbid)
    return {
        **video_public,
        "version_label": video.version_label,
        "popularity_score": video.popularity_score,
        "is_main": video.sbid == main_video_id,
        "viewer_vote": choice.value if choice else None,
        "link_label": video_link_label(video),
    }
