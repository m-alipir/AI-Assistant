"""Freshness-first deterministic ingestion orchestration with no LLM dependency."""

from collections.abc import Awaitable, Callable, Iterable

from app.dedup.cache import InMemoryDedupCache
from app.freshness.gate import assess_freshness
from app.ingestion.schemas import FreshnessPolicy, FreshnessStatus, IngestionRun, SourceItem

CandidateProcessor = Callable[[SourceItem], Awaitable[None]]


class DeterministicIngestionPipeline:
    """Apply freshness and identity checks before allowing any downstream processing."""

    def __init__(self, freshness_policy: FreshnessPolicy, dedup_cache: InMemoryDedupCache) -> None:
        self._freshness_policy = freshness_policy
        self._dedup_cache = dedup_cache

    async def process(
        self,
        items: Iterable[SourceItem],
        process_candidate: CandidateProcessor | None = None,
    ) -> IngestionRun:
        """Return fresh unique candidates without processing stale or quarantined items."""
        run = IngestionRun()
        for item in items:
            status = assess_freshness(item, self._freshness_policy)
            assessed = item.model_copy(update={"freshness_status": status})
            if status is FreshnessStatus.STALE:
                run.stale.append(assessed)
                continue
            if status is FreshnessStatus.FUTURE_QUARANTINED:
                run.future_quarantined.append(assessed)
                continue
            if not self._dedup_cache.reserve(assessed):
                run.duplicates.append(assessed)
                continue
            run.accepted.append(assessed)
            if process_candidate is not None:
                await process_candidate(assessed)
        return run
