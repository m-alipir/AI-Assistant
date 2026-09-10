"""Credential-free RSSHub pilot collection and aggregate-only measurement."""

import argparse
import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collectors.rss import HttpFeedFetcher, RssCollector
from app.config.settings import get_settings
from app.config.sources import SourceCatalog, load_source_catalog
from app.dedup.cache import InMemoryDedupCache
from app.ingestion.pipeline import DeterministicIngestionPipeline


@dataclass(frozen=True)
class PilotRouteObservation:
    """One safe, route-level observation; no feed body or item text is retained."""

    source_name: str
    stream: str
    source_tier: str
    observed_at: datetime
    available: bool
    latency_ms: int | None
    fetched_items: int = 0
    fresh_items: int = 0
    duplicate_items: int = 0
    retained_items: int = 0
    error_category: str | None = None


PersistObservations = Callable[[Sequence[PilotRouteObservation]], Awaitable[None]]


class RssHubPilotJob:
    """Measure approved RSSHub routes without invoking the knowledge-processing runtime."""

    def __init__(
        self,
        catalog: SourceCatalog,
        collector: RssCollector,
        persist_observations: PersistObservations,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        _validate_pilot_catalog(catalog)
        self._catalog = catalog
        self._collector = collector
        self._persist_observations = persist_observations
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(self) -> list[PilotRouteObservation]:
        """Collect each route once and save only aggregate operational measurements."""
        observations: list[PilotRouteObservation] = []
        pipeline = DeterministicIngestionPipeline(
            self._catalog.freshness_policy, InMemoryDedupCache()
        )
        for source in self._catalog.rss:
            if not source.enabled:
                continue
            started = time.perf_counter()
            observed_at = self._clock().astimezone(UTC)
            try:
                items = await self._collector.collect(source, fetched_at=observed_at)
                deterministic = await pipeline.process(items)
                observations.append(
                    PilotRouteObservation(
                        source_name=source.name,
                        stream=source.stream.value,
                        source_tier=source.source_tier,
                        observed_at=observed_at,
                        available=True,
                        latency_ms=_elapsed_ms(started),
                        fetched_items=len(items),
                        fresh_items=len(deterministic.accepted),
                        duplicate_items=len(deterministic.duplicates),
                        retained_items=len(deterministic.accepted),
                    )
                )
            except Exception as error:  # A failed route must not stop the remaining pilot routes.
                observations.append(
                    PilotRouteObservation(
                        source_name=source.name,
                        stream=source.stream.value,
                        source_tier=source.source_tier,
                        observed_at=observed_at,
                        available=False,
                        latency_ms=_elapsed_ms(started),
                        error_category=type(error).__name__,
                    )
                )
        await self._persist_observations(observations)
        return observations


def database_observation_writer(
    sessions: async_sessionmaker[AsyncSession],
) -> PersistObservations:
    """Persist route aggregates only, never source entry text or URLs."""

    async def persist(observations: Sequence[PilotRouteObservation]) -> None:
        if not observations:
            return
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO rsshub_pilot_route_observations "
                    "(id, source_name, stream, source_tier, observed_at, available, latency_ms, "
                    "fetched_items, fresh_items, duplicate_items, retained_items, error_category) "
                    "VALUES (:id, :source_name, :stream, :source_tier, :observed_at, :available, "
                    ":latency_ms, :fetched_items, :fresh_items, :duplicate_items, :retained_items, "
                    ":error_category)"
                ),
                [
                    {
                        "id": str(uuid.uuid4()),
                        "source_name": observation.source_name,
                        "stream": observation.stream,
                        "source_tier": observation.source_tier,
                        "observed_at": observation.observed_at,
                        "available": observation.available,
                        "latency_ms": observation.latency_ms,
                        "fetched_items": observation.fetched_items,
                        "fresh_items": observation.fresh_items,
                        "duplicate_items": observation.duplicate_items,
                        "retained_items": observation.retained_items,
                        "error_category": observation.error_category,
                    }
                    for observation in observations
                ],
            )

    return persist


def summarize_observations(
    observations: Sequence[PilotRouteObservation],
) -> dict[str, object]:
    """Render a compact, no-content report for the seven-day keep/disable decision."""
    total = len(observations)
    available = [item for item in observations if item.available]
    latency_values = [item.latency_ms for item in available if item.latency_ms is not None]
    fetched = sum(item.fetched_items for item in observations)
    duplicates = sum(item.duplicate_items for item in observations)
    return {
        "routes": total,
        "availability": round(len(available) / total, 4) if total else 0.0,
        "latency_ms_average": round(sum(latency_values) / len(latency_values), 1)
        if latency_values
        else None,
        "fresh_items": sum(item.fresh_items for item in observations),
        "duplicate_rate": round(duplicates / fetched, 4) if fetched else 0.0,
        "retained_items": sum(item.retained_items for item in observations),
        "maintenance_error_rate": round((total - len(available)) / total, 4) if total else 0.0,
    }


def summarize_routes(
    observations: Sequence[PilotRouteObservation],
) -> list[dict[str, object]]:
    """Group safe aggregates per configured route for the human pilot decision."""
    by_route: dict[str, list[PilotRouteObservation]] = {}
    for observation in observations:
        by_route.setdefault(observation.source_name, []).append(observation)
    return [
        {
            "source_name": source_name,
            "stream": grouped[0].stream,
            "source_tier": grouped[0].source_tier,
            "observations": len(grouped),
            **summarize_observations(grouped),
        }
        for source_name, grouped in sorted(by_route.items())
    ]


async def load_observations(
    sessions: async_sessionmaker[AsyncSession], days: int
) -> list[PilotRouteObservation]:
    """Load a bounded measurement window without reading any source content."""
    if not 1 <= days <= 31:
        raise ValueError("report days must be between 1 and 31")
    async with sessions() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT source_name, stream, source_tier, observed_at, available, latency_ms, "
                    "fetched_items, fresh_items, duplicate_items, retained_items, error_category "
                    "FROM rsshub_pilot_route_observations "
                    "WHERE observed_at >= now() - (:days * INTERVAL '1 day') "
                    "ORDER BY source_name, observed_at"
                ),
                {"days": days},
            )
        ).mappings()
    return [
        PilotRouteObservation(
            source_name=str(row["source_name"]),
            stream=str(row["stream"]),
            source_tier=str(row["source_tier"]),
            observed_at=row["observed_at"],
            available=bool(row["available"]),
            latency_ms=int(row["latency_ms"]) if row["latency_ms"] is not None else None,
            fetched_items=int(row["fetched_items"]),
            fresh_items=int(row["fresh_items"]),
            duplicate_items=int(row["duplicate_items"]),
            retained_items=int(row["retained_items"]),
            error_category=str(row["error_category"]) if row["error_category"] else None,
        )
        for row in rows
    ]


async def _run_cli(report_days: int | None) -> None:
    from app.db.session import create_engine, create_session_factory

    settings = get_settings()
    engine = create_engine(settings)
    try:
        sessions = create_session_factory(engine)
        if report_days is not None:
            observations = await load_observations(sessions, report_days)
            print(
                json.dumps(
                    {
                        "days": report_days,
                        "overall": summarize_observations(observations),
                        "routes": summarize_routes(observations),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        catalog = load_source_catalog(settings.admin_sources_path)
        job = RssHubPilotJob(
            catalog,
            RssCollector(
                HttpFeedFetcher(
                    allow_private_hosts=settings.allow_private_source_urls,
                    allow_insecure_http=settings.allow_insecure_source_urls,
                ),
                max_items=settings.rss_max_items_per_feed,
            ),
            database_observation_writer(sessions),
        )
        observations = await job.run()
        print(json.dumps(summarize_observations(observations), ensure_ascii=False, sort_keys=True))
    finally:
        await engine.dispose()


def _validate_pilot_catalog(catalog: SourceCatalog) -> None:
    enabled = [source for source in catalog.rss if source.enabled]
    approved_urls = all(source.url.startswith("http://rsshub:1200/") for source in enabled)
    if len(enabled) != 15 or not approved_urls:
        raise ValueError("RSSHub pilot requires exactly the approved internal RSSHub route catalog")


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def main() -> None:
    """Run one explicit pilot collection; the normal application never invokes this command."""
    parser = argparse.ArgumentParser(description="Run one RSSHub pilot measurement")
    parser.add_argument("--report-days", type=int, metavar="DAYS")
    arguments = parser.parse_args()
    asyncio.run(_run_cli(arguments.report_days))


if __name__ == "__main__":
    main()
