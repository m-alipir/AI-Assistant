"""Validated boundaries shared by deterministic ingestion services."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SourceKind(StrEnum):
    """Supported source families in the first ingestion milestone."""

    RSS = "rss"
    YOUTUBE = "youtube"


class SourceStream(StrEnum):
    """Editorial streams that are independent from later ranking decisions."""

    PERSONALIZED = "personalized"
    TECH = "tech"
    WORLD = "world"


class TimestampConfidence(StrEnum):
    """How the publication-time field was established."""

    SOURCE = "source"
    DISCOVERED_FALLBACK = "discovered_fallback"


class FreshnessStatus(StrEnum):
    """Result of the pre-processing freshness gate."""

    UNASSESSED = "unassessed"
    FRESH = "fresh"
    STALE = "stale"
    FUTURE_QUARANTINED = "future_quarantined"


class SourceItem(BaseModel):
    """A compact normalized feed/video item before any LLM or article extraction work."""

    source_name: str = Field(max_length=200)
    source_kind: SourceKind
    stream: SourceStream
    external_id: str | None = Field(default=None, max_length=512)
    canonical_url: str | None = Field(default=None, max_length=2_048)
    title: str = Field(min_length=1, max_length=512)
    author: str | None = Field(default=None, max_length=256)
    snippet: str | None = Field(default=None, max_length=4_000)
    source_published_at: datetime | None = None
    source_updated_at: datetime | None = None
    discovered_at: datetime
    fetched_at: datetime
    timestamp_confidence: TimestampConfidence
    freshness_status: FreshnessStatus = FreshnessStatus.UNASSESSED
    source_freshness_hours: int | None = Field(default=None, ge=1, le=720)
    content_hash: str = Field(min_length=1, max_length=128)

    @field_validator("source_published_at", "source_updated_at", "discovered_at", "fetched_at")
    @classmethod
    def normalize_to_utc(cls, value: datetime | None) -> datetime | None:
        """Normalize source dates at the model boundary and reject naïve timestamps."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timestamps must include an offset")
        return value.astimezone(UTC)

    @property
    def freshness_reference_at(self) -> datetime:
        """Use publication time when available; discovery time is an explicit fallback."""
        return self.source_published_at or self.discovered_at


class FreshnessPolicy(BaseModel):
    """Bounded lookback policy applied before any expensive processing stage."""

    news_freshness_hours: int = Field(default=48, ge=1, le=720)
    world_freshness_hours: int = Field(default=48, ge=1, le=720)
    youtube_freshness_hours: int = Field(default=72, ge=1, le=720)
    future_tolerance_hours: int = Field(default=6, ge=0, le=72)


class IngestionRun(BaseModel):
    """Observable outcome of one deterministic ingestion pass."""

    accepted: list[SourceItem] = Field(default_factory=list)
    stale: list[SourceItem] = Field(default_factory=list)
    future_quarantined: list[SourceItem] = Field(default_factory=list)
    duplicates: list[SourceItem] = Field(default_factory=list)
