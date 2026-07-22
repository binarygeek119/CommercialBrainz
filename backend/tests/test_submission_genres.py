"""Tests for submission genre metadata."""

from app.schemas import SubmissionGenres
from app.services.submission_genres import compact_submission_genres, merge_genres_into_metadata


def test_compact_submission_genres_omits_empty():
    assert compact_submission_genres(SubmissionGenres(adult_rated=True, holiday="Christmas")) == {
        "adult_rated": True,
        "holiday": "Christmas",
    }


def test_compact_submission_genres_ignores_legacy_spoof_flag():
    # Spoof is a commercial type now; leftover genre flags must not be stored.
    compact = compact_submission_genres({"spoof": True, "real": True})
    assert compact == {"real": True}


def test_merge_genres_into_metadata():
    merged = merge_genres_into_metadata(
        {"source": "youtube"},
        SubmissionGenres(target_channel="ESPN", real=True),
    )
    assert merged["source"] == "youtube"
    assert merged["genres"] == {"target_channel": "ESPN", "real": True}
