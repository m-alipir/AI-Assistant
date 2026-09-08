"""Freshness classification before article extraction or model work."""

from datetime import timedelta

from app.ingestion.schemas import (
    FreshnessPolicy,
    FreshnessStatus,
    SourceItem,
    SourceKind,
    SourceStream,
)


def assess_freshness(item: SourceItem, policy: FreshnessPolicy) -> FreshnessStatus:
    """Classify an item using published time, or discovered time only as a marked fallback."""
    reference = item.freshness_reference_at
    if reference > item.fetched_at + timedelta(hours=policy.future_tolerance_hours):
        return FreshnessStatus.FUTURE_QUARANTINED
    if item.source_freshness_hours is not None:
        max_age_hours = item.source_freshness_hours
    elif item.source_kind is SourceKind.YOUTUBE:
        max_age_hours = policy.youtube_freshness_hours
    elif item.stream is SourceStream.WORLD:
        max_age_hours = policy.world_freshness_hours
    else:
        max_age_hours = policy.news_freshness_hours
    if reference < item.fetched_at - timedelta(hours=max_age_hours):
        return FreshnessStatus.STALE
    return FreshnessStatus.FRESH
