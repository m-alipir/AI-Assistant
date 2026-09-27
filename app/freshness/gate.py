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
    max_age_hours = freshness_window_hours(item, policy)
    if reference < item.fetched_at - timedelta(hours=max_age_hours):
        return FreshnessStatus.STALE
    return FreshnessStatus.FRESH


def freshness_window_hours(item: SourceItem, policy: FreshnessPolicy) -> int:
    """Resolve the positive per-source snapshot or the existing stream default."""
    if item.source_freshness_hours is not None:
        return item.source_freshness_hours
    if item.source_kind is SourceKind.YOUTUBE:
        return policy.youtube_freshness_hours
    if item.stream is SourceStream.WORLD:
        return policy.world_freshness_hours
    return policy.news_freshness_hours
