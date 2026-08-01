"""Unit tests for duplicate-issue helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import DuplicateVoteChoice, VideoVisibility
from app.services.duplicate_issues import (
    apply_duplicate_resolution,
    canonical_pair,
    evaluate_duplicate_votes,
)


def test_canonical_pair_orders_ids():
    a = uuid4()
    b = uuid4()
    left, right = canonical_pair(a, b)
    assert left.int < right.int
    assert {left, right} == {a, b}


@pytest.mark.asyncio
async def test_evaluate_duplicate_votes_resolves_at_threshold(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DUPLICATE_VOTE_THRESHOLD", "2")
    get_settings.cache_clear()

    from app.config import get_settings as gs
    from app.services import duplicate_issues as di

    di.settings = gs()

    issue_id = uuid4()
    video_a = uuid4()
    video_b = uuid4()
    issue = SimpleNamespace(
        id=issue_id,
        status=di.DuplicateIssueStatus.OPEN,
        video_a_id=video_a,
        video_b_id=video_b,
        resolved_choice=None,
        resolved_subject_video_id=None,
        resolved_at=None,
        updated_at=None,
    )
    votes = [
        SimpleNamespace(
            choice=DuplicateVoteChoice.REMOVE_FROM_DATABASE,
            subject_video_id=video_a,
        ),
        SimpleNamespace(
            choice=DuplicateVoteChoice.REMOVE_FROM_DATABASE,
            subject_video_id=video_a,
        ),
    ]
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=votes))))
    )

    with patch.object(di, "apply_duplicate_resolution", new=AsyncMock()) as apply:
        resolved = await evaluate_duplicate_votes(db, issue)

    assert resolved is True
    assert issue.status == di.DuplicateIssueStatus.RESOLVED
    assert issue.resolved_choice == DuplicateVoteChoice.REMOVE_FROM_DATABASE
    assert issue.resolved_subject_video_id == video_a
    apply.assert_awaited_once()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_apply_remove_sets_visibility():
    subject_id = uuid4()
    other_id = uuid4()
    commercial_id = uuid4()
    subject = SimpleNamespace(
        sbid=subject_id,
        commercial_id=commercial_id,
        visibility=VideoVisibility.PUBLIC,
    )
    other = SimpleNamespace(sbid=other_id, commercial_id=uuid4())
    issue = SimpleNamespace(video_a_id=subject_id, video_b_id=other_id)

    db = MagicMock()
    db.get = AsyncMock(side_effect=[subject, other])
    db.flush = AsyncMock()

    with patch(
        "app.services.video_popularity.recompute_main_video", new=AsyncMock()
    ) as recompute:
        await apply_duplicate_resolution(
            db,
            issue,
            DuplicateVoteChoice.REMOVE_FROM_DATABASE,
            subject_id,
        )

    assert subject.visibility == VideoVisibility.REMOVED
    recompute.assert_awaited()


@pytest.mark.asyncio
async def test_apply_make_master_forces_main_video():
    subject_id = uuid4()
    other_id = uuid4()
    subject_commercial = uuid4()
    other_commercial = uuid4()
    subject = SimpleNamespace(
        sbid=subject_id,
        commercial_id=subject_commercial,
        visibility=VideoVisibility.PUBLIC,
    )
    other = SimpleNamespace(
        sbid=other_id,
        commercial_id=other_commercial,
        visibility=VideoVisibility.PUBLIC,
    )
    subject_commercial_row = SimpleNamespace(
        sbid=subject_commercial, main_video_id=None
    )
    issue = SimpleNamespace(video_a_id=subject_id, video_b_id=other_id)

    db = MagicMock()
    db.get = AsyncMock(side_effect=[subject, other, subject_commercial_row])

    async def _fake_move(_db, video, target_commercial_id):
        video.commercial_id = target_commercial_id

    with patch(
        "app.services.duplicate_issues._move_video_to_commercial",
        new=AsyncMock(side_effect=_fake_move),
    ):
        await apply_duplicate_resolution(
            db,
            issue,
            DuplicateVoteChoice.MAKE_MASTER_LINK,
            subject_id,
        )

    assert other.commercial_id == subject_commercial
    assert subject_commercial_row.main_video_id == subject_id


@pytest.mark.asyncio
async def test_register_duplicates_restarts_when_new_partner_appears():
    from app.models import DuplicateIssueStatus, VideoVisibility
    from app.services import duplicate_issues as di

    video_id = uuid4()
    partner_a = uuid4()
    partner_b = uuid4()
    a, b = canonical_pair(video_id, partner_a)
    video = SimpleNamespace(
        sbid=video_id,
        visibility=VideoVisibility.PUBLIC,
        file_sha256="abc",
        audio_fingerprint=None,
        phash=None,
    )
    open_issue = SimpleNamespace(
        status=DuplicateIssueStatus.OPEN,
        video_a_id=a,
        video_b_id=b,
        votes=[],
        updated_at=None,
    )
    matches = [
        {
            "video_sbid": str(partner_a),
            "match_type": "file_sha256",
            "hamming_distance": None,
            "youtube_id": "a",
        },
        {
            "video_sbid": str(partner_b),
            "match_type": "file_sha256",
            "hamming_distance": None,
            "youtube_id": "b",
        },
    ]

    db = MagicMock()
    db.get = AsyncMock(return_value=video)
    db.flush = AsyncMock()
    db.add = MagicMock()

    open_result = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[open_issue])))
    )
    supersede_result = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[open_issue])))
    )
    db.execute = AsyncMock(side_effect=[open_result, supersede_result])
    db.scalar = AsyncMock(return_value=0)

    with patch.object(di, "find_hash_matches_for_video", new=AsyncMock(return_value=matches)):
        created = await di.register_duplicates_for_video(db, video_id)

    assert created == 2
    assert open_issue.status == DuplicateIssueStatus.SUPERSEDED
    assert db.add.call_count == 2
