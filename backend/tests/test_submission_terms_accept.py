"""Terms of Submission acceptance is persisted on the user row."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import submission_terms as terms_service


@pytest.mark.asyncio
async def test_record_terms_acceptance_sets_version_and_timestamp(monkeypatch):
    user = SimpleNamespace(submission_terms_version=None, submission_terms_accepted_at=None)
    doc = SimpleNamespace(version=7)

    monkeypatch.setattr(
        terms_service,
        "get_active_submission_terms",
        AsyncMock(return_value=doc),
    )

    before = datetime.now(UTC)
    accepted = await terms_service.record_terms_acceptance(AsyncMock(), user)

    assert accepted.version == 7
    assert user.submission_terms_version == 7
    assert user.submission_terms_accepted_at is not None
    assert user.submission_terms_accepted_at >= before


@pytest.mark.asyncio
async def test_validate_and_record_requires_agreement(monkeypatch):
    with pytest.raises(ValueError, match="must agree"):
        await terms_service.validate_and_record_terms_acceptance(
            AsyncMock(), SimpleNamespace(), terms_agreed=False
        )

    user = SimpleNamespace(submission_terms_version=None, submission_terms_accepted_at=None)
    doc = SimpleNamespace(version=2)
    monkeypatch.setattr(
        terms_service,
        "get_active_submission_terms",
        AsyncMock(return_value=doc),
    )
    accepted = await terms_service.validate_and_record_terms_acceptance(
        AsyncMock(), user, terms_agreed=True
    )
    assert accepted.version == 2
    assert user.submission_terms_version == 2
    assert user.submission_terms_accepted_at is not None
