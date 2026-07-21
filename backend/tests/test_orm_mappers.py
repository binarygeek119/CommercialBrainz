"""Ensure ORM relationships configure cleanly (login and other routes depend on this)."""

from sqlalchemy.orm import configure_mappers


def test_configure_mappers_succeeds():
    """Regression: Commercial.main_video_id + Video.commercial_id must not be ambiguous.

    When mappers fail to initialize, /auth/login wraps the failure as
    InvalidRequestError and returns 503 for every login attempt.
    """
    import app.models  # noqa: F401

    configure_mappers()
