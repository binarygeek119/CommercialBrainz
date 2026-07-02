"""Normalize submission genre/classification metadata."""

from __future__ import annotations

from app.schemas import SubmissionGenres

GENRE_BOOL_FIELDS = (
    "banned",
    "adult_rated",
    "late_night",
    "spoof",
    "fake",
    "real",
    "ai_enhanced",
)
GENRE_TEXT_FIELDS = ("age_range", "target_channel", "holiday", "event", "store", "service")


def compact_submission_genres(genres: SubmissionGenres | dict | None) -> dict | None:
    if genres is None:
        return None
    raw = genres.model_dump() if isinstance(genres, SubmissionGenres) else dict(genres)
    compact: dict = {}
    for key in GENRE_TEXT_FIELDS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            compact[key] = value.strip()
    for key in GENRE_BOOL_FIELDS:
        if raw.get(key):
            compact[key] = True
    return compact or None


def merge_genres_into_metadata(metadata: dict | None, genres: SubmissionGenres | dict | None) -> dict:
    merged = dict(metadata or {})
    compact = compact_submission_genres(genres)
    if compact:
        merged["genres"] = compact
    return merged
