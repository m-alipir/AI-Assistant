from pathlib import Path

import pytest

from app.config.runtime_sources import SourceControlError, add_source, disable_source, list_sources


def test_runtime_source_management_persists_enabled_rss_and_youtube(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("defaults: {}\nrss: []\nyoutube: []\n", encoding="utf-8")

    rss = add_source(path, "rss", "https://example.test/feed.xml", "Example feed")
    youtube = add_source(
        path,
        "youtube",
        "https://youtube.com/channel/UCabcdefghij_1234567890",
        "Example channel",
    )
    rows = list_sources(path)

    assert [row["id"] for row in rows] == [rss["id"], youtube["id"]]
    assert all(row["enabled"] for row in rows)
    assert disable_source(path, rss["id"]) == "Example feed"
    assert list_sources(path)[0]["enabled"] is False


def test_runtime_source_management_detects_explicit_youtube_channel_url(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("rss: []\nyoutube: []\n", encoding="utf-8")

    source = add_source(
        path,
        "auto",
        "https://www.youtube.com/channel/UCabcdefghij_1234567890",
    )

    assert source["id"].startswith("youtube-")


def test_runtime_source_management_rejects_invalid_or_duplicate_inputs(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("rss: []\nyoutube: []\n", encoding="utf-8")

    with pytest.raises(SourceControlError):
        add_source(path, "rss", "file:///etc/passwd")
    with pytest.raises(SourceControlError):
        add_source(path, "rss", "https://operator:secret@example.test/feed.xml")
    with pytest.raises(SourceControlError):
        add_source(path, "youtube", "https://youtube.com/@unresolvable")

    add_source(path, "rss", "https://example.test/feed.xml")
    with pytest.raises(SourceControlError, match="zaten"):
        add_source(path, "rss", "https://example.test/feed.xml")
