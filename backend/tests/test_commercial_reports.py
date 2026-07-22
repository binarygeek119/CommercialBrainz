"""Tests for commercial report reason validation helpers."""

from uuid import uuid4

import pytest

from app.models import CommercialReportReason
from app.services.commercial_reports import REASON_OUTCOMES


def test_report_reasons_cover_requested_categories():
    values = {r.value for r in CommercialReportReason}
    assert values == {
        "banned",
        "adult_ad",
        "adult_porn",
        "hate_speech",
        "other",
    }


def test_outcome_hints():
    assert "flagged" in REASON_OUTCOMES[CommercialReportReason.BANNED].lower()
    assert "flagged" in REASON_OUTCOMES[CommercialReportReason.ADULT_AD].lower()
    assert "removed" in REASON_OUTCOMES[CommercialReportReason.ADULT_PORN].lower()


@pytest.mark.asyncio
async def test_other_requires_details(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.services.commercial_reports import create_commercial_report

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    commercial = SimpleNamespace(sbid=uuid4())
    reporter = SimpleNamespace(id=uuid4())

    with pytest.raises(ValueError, match="Other"):
        await create_commercial_report(
            db,
            commercial=commercial,
            reporter=reporter,
            reason=CommercialReportReason.OTHER,
            details="  ",
        )
