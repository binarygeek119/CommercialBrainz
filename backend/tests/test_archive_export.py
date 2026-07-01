"""Tests for archive export helpers."""

from pathlib import Path

from app.services.archive_export import collect_bundle_files


def test_collect_bundle_files(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "images" / "thumbnails").mkdir(parents=True)
    (bundle / "dataset.json").write_text("{}", encoding="utf-8")
    (bundle / "images" / "thumbnails" / "abc.jpg").write_bytes(b"jpg")

    files = collect_bundle_files(bundle)
    remote_names = {remote for _, remote in files}

    assert "dataset.json" in remote_names
    assert "images/thumbnails/abc.jpg" in remote_names
