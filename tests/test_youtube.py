import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.collectors.rss import FeedFetcher
from app.collectors.youtube import (
    SubtitleTrack,
    YouTubeDiscovery,
    YtDlpSubtitleFetcher,
    _subtitle_languages_for,
    parse_webvtt,
    select_preferred_track,
)
from app.config.sources import YouTubeSourceConfig
from app.ingestion.schemas import SourceKind


class FixtureFeedFetcher(FeedFetcher):
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.urls: list[str] = []

    async def fetch(self, url: str) -> bytes:
        self.urls.append(url)
        return self.payload


@pytest.mark.asyncio
async def test_youtube_discovery_uses_public_atom_metadata_without_media_download() -> None:
    payload = (Path(__file__).parent / "fixtures" / "youtube.xml").read_bytes()
    fetcher = FixtureFeedFetcher(payload)
    discovery = YouTubeDiscovery(fetcher)
    source = YouTubeSourceConfig(name="Fixture Channel", channel_id="UCfixture", enabled=True)

    items = await discovery.collect(source, fetched_at=datetime(2026, 9, 6, 12, tzinfo=UTC))

    assert fetcher.urls == ["https://www.youtube.com/feeds/videos.xml?channel_id=UCfixture"]
    assert len(items) == 1
    assert items[0].source_kind is SourceKind.YOUTUBE
    assert items[0].external_id == "abc123"
    assert items[0].canonical_url == "https://www.youtube.com/watch?v=abc123"


def test_caption_selection_prefers_human_track_and_vtt_keeps_timestamps() -> None:
    vtt = (Path(__file__).parent / "fixtures" / "sample.vtt").read_text(encoding="utf-8")
    automatic = SubtitleTrack(language="en", is_automatic=True, vtt="WEBVTT")
    human = SubtitleTrack(language="tr", is_automatic=False, vtt=vtt)

    selected = select_preferred_track([automatic, human])
    segments = parse_webvtt(selected.vtt if selected else "")

    assert selected == human
    assert [(segment.start_seconds, segment.end_seconds) for segment in segments] == [
        (1.0, 3.5),
        (60.25, 62.0),
    ]
    assert segments[0].text == "Welcome to graphics programming."


def test_caption_selection_uses_configured_language_family_before_caption_type() -> None:
    tr_automatic = SubtitleTrack(language="tr", is_automatic=True, vtt="WEBVTT")
    tr_regional_human = SubtitleTrack(language="tr-TR", is_automatic=False, vtt="WEBVTT")
    en_human = SubtitleTrack(language="en-US", is_automatic=False, vtt="WEBVTT")

    assert (
        select_preferred_track([tr_automatic, en_human, tr_regional_human], "tr")
        == tr_regional_human
    )
    assert select_preferred_track([tr_automatic, en_human], "tr") == tr_automatic
    assert select_preferred_track([tr_regional_human, en_human], "en") == en_human
    assert select_preferred_track([en_human], "tr") is None


def test_ytdlp_wrapper_requests_captions_only_without_downloading_media(monkeypatch) -> None:
    captured_options: dict[str, object] = {}

    class FakeYoutubeDl:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)

        def __enter__(self) -> "FakeYoutubeDl":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, _: str, download: bool) -> dict[str, object]:
            assert download is True
            output_template = str(captured_options["outtmpl"])
            subtitle_path = Path(output_template.replace("%(id)s.%(ext)s", "abc.en.vtt"))
            subtitle_path.write_text(
                "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nCaption",
                encoding="utf-8",
            )
            return {
                "subtitles": {"en": [{}]},
                "requested_subtitles": {"en": {"filepath": str(subtitle_path)}},
            }

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDl))
    tracks = YtDlpSubtitleFetcher()._fetch_subtitles_sync(
        "https://example.test/watch?v=abc", ("en", "en-US", "tr", "tr-TR")
    )

    assert captured_options["skip_download"] is True
    assert captured_options["writesubtitles"] is True
    assert captured_options["writeautomaticsub"] is True
    assert captured_options["subtitleslangs"] == ["en", "en-US", "tr", "tr-TR"]
    assert tracks == [
        SubtitleTrack(
            language="en",
            is_automatic=False,
            vtt="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nCaption",
        )
    ]


def test_configured_caption_language_requests_only_its_known_regional_family() -> None:
    legacy = ("en", "en-US", "tr", "tr-TR")

    assert _subtitle_languages_for(None, legacy) == legacy
    assert _subtitle_languages_for("tr", legacy) == ("tr", "tr-TR", "tr-CY")
    assert _subtitle_languages_for("en", legacy) == (
        "en",
        "en-US",
        "en-GB",
        "en-AU",
        "en-CA",
        "en-IN",
        "en-NZ",
    )
