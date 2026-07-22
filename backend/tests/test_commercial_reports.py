"""Tests for content report reason validation helpers."""

from uuid import uuid4

import pytest

from app.models import ContentReportReason
from app.services.commercial_reports import REASON_OUTCOMES


def test_report_reasons_cover_requested_categories():
    values = {r.value for r in ContentReportReason}
    assert values == {
        "banned",
        "adult_ad",
        "adult_porn",
        "hate_speech",
        "other",
    }


def test_outcome_hints():
    assert "flagged" in REASON_OUTCOMES[ContentReportReason.BANNED].lower()
    assert "flagged" in REASON_OUTCOMES[ContentReportReason.ADULT_AD].lower()
    assert "removed" in REASON_OUTCOMES[ContentReportReason.ADULT_PORN].lower()


@pytest.mark.asyncio
async def test_other_requires_details():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.services.commercial_reports import create_content_report

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    commercial = SimpleNamespace(sbid=uuid4())
    reporter = SimpleNamespace(id=uuid4())

    with pytest.raises(ValueError, match="Other"):
        await create_content_report(
            db,
            commercial=commercial,
            reporter=reporter,
            reason=ContentReportReason.OTHER,
            details="  ",
        )


@pytest.mark.asyncio
async def test_requires_exactly_one_target():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.services.commercial_reports import create_content_report

    db = AsyncMock()
    reporter = SimpleNamespace(id=uuid4())

    with pytest.raises(ValueError, match="exactly one"):
        await create_content_report(
            db,
            reporter=reporter,
            reason=ContentReportReason.BANNED,
        )
