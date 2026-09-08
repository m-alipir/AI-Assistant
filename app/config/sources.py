"""Validated, non-secret source configuration and seed-file loading."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, model_validator

from app.ingestion.schemas import FreshnessPolicy, SourceStream


class SourceDefaults(BaseModel):
    """Global freshness values loaded from the source seed file."""

    timezone: str = "Europe/Istanbul"
    news_freshness_hours: int = Field(default=48, ge=1, le=720)
    world_freshness_hours: int = Field(default=48, ge=1, le=720)
    youtube_freshness_hours: int = Field(default=72, ge=1, le=720)
    future_tolerance_hours: int = Field(default=6, ge=0, le=72)

    def to_freshness_policy(self) -> FreshnessPolicy:
        """Convert YAML defaults into the policy consumed by the ingestion pipeline."""
        return FreshnessPolicy(
            news_freshness_hours=self.news_freshness_hours,
            world_freshness_hours=self.world_freshness_hours,
            youtube_freshness_hours=self.youtube_freshness_hours,
            future_tolerance_hours=self.future_tolerance_hours,
        )


class RssSourceConfig(BaseModel):
    """One RSS or Atom source configured for collection."""

    name: str = Field(min_length=1)
    url: str
    stream: SourceStream
    enabled: bool = False
    source_tier: str = "unknown"
    freshness_hours: int | None = Field(default=None, ge=1, le=720)

    @model_validator(mode="after")
    def enabled_source_requires_http_url(self) -> "RssSourceConfig":
        """Permit disabled placeholders while preventing an enabled malformed endpoint."""
        parsed = urlparse(self.url)
        if self.enabled and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
            raise ValueError("enabled RSS sources require an absolute HTTP(S) URL")
        return self


class YouTubeSourceConfig(BaseModel):
    """One public YouTube channel discovered through its Atom feed."""

    name: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    stream: SourceStream = SourceStream.PERSONALIZED
    enabled: bool = False
    freshness_hours: int | None = Field(default=None, ge=1, le=720)
    language: Literal["tr", "en"] | None = None

    @model_validator(mode="after")
    def enabled_source_requires_real_channel_id(self) -> "YouTubeSourceConfig":
        """Reject example placeholders only when the source is switched on."""
        if self.enabled and self.channel_id.upper().startswith("REPLACE"):
            raise ValueError("enabled YouTube sources require a channel ID")
        return self

    @property
    def feed_url(self) -> str:
        """Return YouTube's public channel-feed endpoint without any API credential."""
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"


class SourceCatalog(BaseModel):
    """The complete seedable RSS and YouTube source catalog."""

    defaults: SourceDefaults = Field(default_factory=SourceDefaults)
    rss: list[RssSourceConfig] = Field(default_factory=list)
    youtube: list[YouTubeSourceConfig] = Field(default_factory=list)

    @property
    def freshness_policy(self) -> FreshnessPolicy:
        """Expose configured defaults directly to the freshness-first pipeline."""
        return self.defaults.to_freshness_policy()


def load_source_catalog(path: Path) -> SourceCatalog:
    """Load a YAML source catalog without accepting executable YAML constructs."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("source configuration root must be a mapping")
    return SourceCatalog.model_validate(data)
