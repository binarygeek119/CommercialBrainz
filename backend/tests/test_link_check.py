"""Unit tests for YouTube dead-link classification."""

from app.models import VideoLinkCheckStatus
from app.services.link_check import classify_ytdlp_failure, classify_ytdlp_info


def test_classify_private():
    status, _ = classify_ytdlp_failure(
        "ERROR: Private video. Sign in if you've been granted access"
    )
    assert status == VideoLinkCheckStatus.PRIVATE


def test_classify_age_restricted():
    status, _ = classify_ytdlp_failure("Sign in to confirm your age")
    assert status == VideoLinkCheckStatus.AGE_RESTRICTED


def test_classify_unavailable():
    status, _ = classify_ytdlp_failure("ERROR: Video unavailable. This video has been removed")
    assert status == VideoLinkCheckStatus.UNAVAILABLE


def test_classify_timeout_as_error():
    status, _ = classify_ytdlp_failure("ERROR: Timed out while downloading")
    assert status == VideoLinkCheckStatus.ERROR


def test_classify_info_public():
    status, detail = classify_ytdlp_info({"id": "abc12345678", "availability": "public"})
    assert status == VideoLinkCheckStatus.OK
    assert detail is None


def test_classify_info_private():
    status, detail = classify_ytdlp_info({"id": "abc12345678", "availability": "private"})
    assert status == VideoLinkCheckStatus.PRIVATE
    assert detail is not None


def test_classify_info_age():
    status, _ = classify_ytdlp_info(
        {"id": "abc12345678", "availability": "needs_auth_age_restricted"}
    )
    assert status == VideoLinkCheckStatus.AGE_RESTRICTED
