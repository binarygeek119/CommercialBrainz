"""Tests for YouTube URL / playlist ID helpers and playlist expand wiring."""

from unittest.mock import patch

import pytest

from app.services.youtube_metadata import _run_ytdlp_playlist_flat
from app.utils import (
    extract_youtube_id,
    extract_youtube_playlist_id,
    youtube_playlist_url,
)

PLAYLIST_ID = "PLNpVzr42JvwfUQtqwiHgQXHTEXkLfjFKU"
PLAYLIST_URL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"


def test_extract_youtube_playlist_id_from_playlist_url():
    assert extract_youtube_playlist_id(PLAYLIST_URL) == PLAYLIST_ID


def test_extract_youtube_playlist_id_from_watch_with_list():
    url = f"https://www.youtube.com/watch?v=dQw4w9WgXcQ&list={PLAYLIST_ID}&index=2"
    assert extract_youtube_playlist_id(url) == PLAYLIST_ID


def test_extract_youtube_playlist_id_raw():
    assert extract_youtube_playlist_id(PLAYLIST_ID) == PLAYLIST_ID


def test_extract_youtube_playlist_id_rejects_video_only():
    with pytest.raises(ValueError, match="playlist"):
        extract_youtube_playlist_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_extract_youtube_id_still_rejects_playlist_url():
    with pytest.raises(ValueError, match="Invalid YouTube URL or ID"):
        extract_youtube_id(PLAYLIST_URL)


def test_run_ytdlp_playlist_flat_uses_playlist_url():
    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)

        class Result:
            returncode = 0
            stdout = f'{{"id":"{PLAYLIST_ID}","title":"Demo","entries":[]}}'
            stderr = ""

        return Result()

    with (
        patch("app.services.youtube_metadata.ytdlp_common_args", return_value=[]),
        patch("app.services.youtube_metadata.subprocess.run", side_effect=fake_run),
    ):
        info = _run_ytdlp_playlist_flat(PLAYLIST_URL)

    assert info["id"] == PLAYLIST_ID
    assert captured
    assert captured[0][-1] == youtube_playlist_url(PLAYLIST_ID)
    assert "--flat-playlist" in captured[0]
