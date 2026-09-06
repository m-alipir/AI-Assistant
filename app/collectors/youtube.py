"""YouTube channel discovery and caption-only transcript support."""

import asyncio
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

import feedparser

from app.collectors.rss import FeedFetcher
from app.config.sources import YouTubeSourceConfig
from app.ingestion.schemas import SourceItem, SourceKind, TimestampConfidence
from app.normalize.source_items import content_fingerprint, normalize_url, parse_source_datetime
from app.providers.contracts import ProviderError


class YouTubeDiscovery:
    """Discover recent public channel uploads through YouTube's Atom channel feed."""

    def __init__(self, fetcher: FeedFetcher) -> None:
        self._fetcher = fetcher

    async def collect(
        self,
        source: YouTubeSourceConfig,
        fetched_at: datetime | None = None,
    ) -> list[SourceItem]:
        """Collect video metadata without downloading video or audio."""
        now = (fetched_at or datetime.now(UTC)).astimezone(UTC)
        payload = await self._fetcher.fetch(source.feed_url)
        parsed = feedparser.parse(payload)
        entries: list[Mapping[str, Any]] = list(parsed.entries)
        if parsed.bozo and not entries:
            raise ProviderError("YouTube channel feed could not be parsed")
        return [self._normalize_entry(entry, source, now) for entry in entries]

    @staticmethod
    def _normalize_entry(
        entry: Mapping[str, Any],
        source: YouTubeSourceConfig,
        fetched_at: datetime,
    ) -> SourceItem:
        title = str(entry.get("title") or "Untitled video").strip()
        snippet = str(entry.get("summary") or "").strip() or None
        published_at = parse_source_datetime(
            entry.get("published_parsed") or entry.get("published")
        )
        updated_at = parse_source_datetime(entry["updated"] if "updated" in entry else None)
        video_url = normalize_url(str(entry.get("link") or ""))
        return SourceItem(
            source_name=source.name,
            source_kind=SourceKind.YOUTUBE,
            stream=source.stream,
            external_id=_video_id(entry, video_url),
            canonical_url=video_url,
            title=title,
            author=str(entry.get("author") or "").strip() or None,
            snippet=snippet,
            source_published_at=published_at,
            source_updated_at=updated_at,
            discovered_at=fetched_at,
            fetched_at=fetched_at,
            timestamp_confidence=(
                TimestampConfidence.SOURCE
                if published_at
                else TimestampConfidence.DISCOVERED_FALLBACK
            ),
            source_freshness_hours=source.freshness_hours,
            content_hash=content_fingerprint(title, snippet),
        )


@dataclass(frozen=True)
class SubtitleTrack:
    """One downloaded caption track, never media/audio."""

    language: str
    is_automatic: bool
    vtt: str


@dataclass(frozen=True)
class TranscriptSegment:
    """A caption cue with original timing preserved in seconds."""

    start_seconds: float
    end_seconds: float
    text: str


class SubtitleFetcher(Protocol):
    """Download subtitle files only, with video/audio downloads disabled."""

    async def fetch_subtitles(self, video_url: str) -> list[SubtitleTrack]:
        """Return available manually authored and automatic VTT caption tracks."""


class YtDlpSubtitleFetcher:
    """yt-dlp wrapper that downloads selected VTT captions but never media or audio."""

    def __init__(
        self,
        preferred_languages: tuple[str, ...] = ("en", "en-US", "tr", "tr-TR"),
        timeout_seconds: float = 20.0,
        retries: int = 1,
        max_subtitle_bytes: int = 2_000_000,
    ) -> None:
        self._preferred_languages = preferred_languages
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._max_subtitle_bytes = max_subtitle_bytes

    async def fetch_subtitles(self, video_url: str) -> list[SubtitleTrack]:
        """Run blocking yt-dlp work off the event loop and enforce a total timeout."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_subtitles_sync, video_url),
                timeout=self._timeout_seconds + 5,
            )
        except TimeoutError as error:
            raise ProviderError("subtitle retrieval exceeded its configured timeout") from error

    def _fetch_subtitles_sync(self, video_url: str) -> list[SubtitleTrack]:
        """Use yt-dlp's library API in a temporary directory to retain captions only."""
        import yt_dlp

        with tempfile.TemporaryDirectory(prefix="personal-intelligence-subs-") as directory:
            output_template = str(Path(directory) / "%(id)s.%(ext)s")
            options = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": list(self._preferred_languages),
                "subtitlesformat": "vtt/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": self._timeout_seconds,
                "retries": self._retries,
                "fragment_retries": self._retries,
                "outtmpl": output_template,
            }
            try:
                with yt_dlp.YoutubeDL(options) as downloader:
                    info: Mapping[str, Any] = downloader.extract_info(video_url, download=True)
            except Exception as error:  # yt-dlp has a broad exception hierarchy
                raise ProviderError("yt-dlp subtitle retrieval failed") from error
            return _requested_subtitle_tracks(info, Path(directory), self._max_subtitle_bytes)


def select_preferred_track(tracks: list[SubtitleTrack]) -> SubtitleTrack | None:
    """Prefer a human-authored caption track; use automatic captions only as a fallback."""
    return next((track for track in tracks if not track.is_automatic), None) or next(
        (track for track in tracks if track.is_automatic), None
    )


def parse_webvtt(vtt: str) -> list[TranscriptSegment]:
    """Parse standard WebVTT cues while keeping their source timings intact."""
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\r?\n\s*\r?\n", vtt.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE"):
            continue
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        try:
            start_raw, end_raw = lines[timing_index].split("-->", maxsplit=1)
            start_seconds = _timestamp_seconds(start_raw.strip())
            end_seconds = _timestamp_seconds(end_raw.strip().split(maxsplit=1)[0])
        except (ValueError, IndexError):
            continue
        text = re.sub(r"<[^>]+>", "", " ".join(lines[timing_index + 1 :])).strip()
        if text:
            segments.append(TranscriptSegment(start_seconds, end_seconds, text))
    return segments


def _video_id(entry: Mapping[str, Any], video_url: str | None) -> str | None:
    value = entry.get("yt_videoid") or entry.get("videoid") or entry.get("id")
    if value:
        candidate = str(value).strip()
        if candidate.startswith("yt:video:"):
            return candidate.removeprefix("yt:video:")
        return candidate
    if video_url:
        return parse_qs(urlsplit(video_url).query).get("v", [None])[0]
    return None


def _timestamp_seconds(value: str) -> float:
    """Convert ``HH:MM:SS.mmm`` or ``MM:SS.mmm`` VTT timestamps to seconds."""
    fields = value.replace(",", ".").split(":")
    if len(fields) == 2:
        minutes, seconds = fields
        return int(minutes) * 60 + float(seconds)
    if len(fields) == 3:
        hours, minutes, seconds = fields
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError("invalid VTT timestamp")


def _requested_subtitle_tracks(
    info: Mapping[str, Any],
    directory: Path,
    max_subtitle_bytes: int,
) -> list[SubtitleTrack]:
    """Read only yt-dlp-created VTT subtitle files from the private temporary directory."""
    requested = info.get("requested_subtitles") or {}
    manual_languages = set((info.get("subtitles") or {}).keys())
    safe_directory = directory.resolve()
    tracks: list[SubtitleTrack] = []
    for language, metadata in requested.items():
        if not isinstance(metadata, Mapping):
            continue
        filename = metadata.get("filepath") or metadata.get("_filename")
        path = Path(str(filename)) if filename else None
        if (
            path is None
            or not path.is_relative_to(safe_directory)
            or not path.is_file()
            or path.suffix.lower() != ".vtt"
        ):
            continue
        if path.stat().st_size > max_subtitle_bytes:
            raise ProviderError("subtitle exceeds configured size limit")
        tracks.append(
            SubtitleTrack(
                language=str(language),
                is_automatic=str(language) not in manual_languages,
                vtt=path.read_text(encoding="utf-8"),
            )
        )
    return tracks
