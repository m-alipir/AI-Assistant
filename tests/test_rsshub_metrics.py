from datetime import UTC, datetime, timedelta

import pytest

from app.collectors.rss import RssCollector
from app.config.sources import RssSourceConfig, SourceCatalog
from app.ingestion.schemas import SourceStream
from app.pilot.rsshub import (
    PilotRouteObservation,
    RssHubPilotJob,
    summarize_observations,
    summarize_routes,
)


class FeedFetcher:
    def __init__(self, payloads: dict[str, bytes | Exception]) -> None:
        self._payloads = payloads

    async def fetch(self, url: str) -> bytes:
        result = self._payloads[url]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.asyncio
async def test_pilot_records_route_aggregates_without_item_content() -> None:
    now = datetime(2026, 9, 10, 8, tzinfo=UTC)
    catalog = SourceCatalog(
        rss=[
            RssSourceConfig(
                name=f"Route {number}",
                url=f"http://rsshub:1200/route/{number}",
                stream=SourceStream.TECH,
                source_tier="community_discovery",
                enabled=True,
            )
            for number in range(15)
        ]
    )
    fresh = (now - timedelta(hours=1)).isoformat()
    payload = (
        "<rss><channel><item><title>Fresh</title><link>https://example.test/fresh</link>"
        f"<pubDate>{fresh}</pubDate></item></channel></rss>"
    ).encode()
    fetcher = FeedFetcher(
        {
            **{f"http://rsshub:1200/route/{number}": payload for number in range(14)},
            "http://rsshub:1200/route/14": RuntimeError("unavailable"),
        }
    )
    written: list[object] = []
    job = RssHubPilotJob(
        catalog,
        RssCollector(fetcher),  # type: ignore[arg-type]
        lambda observations: _append_observations(written, observations),
        clock=lambda: now,
    )

    observations = await job.run()

    assert len(observations) == 15
    assert sum(item.available for item in observations) == 14
    assert sum(item.retained_items for item in observations) == 1
    assert observations[-1].error_category == "RuntimeError"
    assert written == observations
    summary = summarize_observations(observations)
    assert summary["availability"] == pytest.approx(14 / 15, abs=0.0001)
    assert summary["duplicate_rate"] == pytest.approx(13 / 14, abs=0.0001)
    assert summary["retained_items"] == 1
    assert "Fresh" not in str(observations)


def test_route_summary_keeps_stream_tier_and_aggregate_metrics_separate() -> None:
    observed_at = datetime(2026, 9, 10, 8, tzinfo=UTC)
    observations = [
        PilotRouteObservation("A", "tech", "major_publication", observed_at, True, 50, 4, 3, 1, 3),
        PilotRouteObservation("A", "tech", "major_publication", observed_at, False, 200),
        PilotRouteObservation("B", "world", "wire_service", observed_at, True, 100, 2, 2, 0, 2),
    ]

    routes = summarize_routes(observations)

    assert routes == [
        {
            "source_name": "A",
            "stream": "tech",
            "source_tier": "major_publication",
            "observations": 2,
            "routes": 2,
            "availability": 0.5,
            "latency_ms_average": 50.0,
            "fresh_items": 3,
            "duplicate_rate": 0.25,
            "retained_items": 3,
            "maintenance_error_rate": 0.5,
        },
        {
            "source_name": "B",
            "stream": "world",
            "source_tier": "wire_service",
            "observations": 1,
            "routes": 1,
            "availability": 1.0,
            "latency_ms_average": 100.0,
            "fresh_items": 2,
            "duplicate_rate": 0.0,
            "retained_items": 2,
            "maintenance_error_rate": 0.0,
        },
    ]


async def _append_observations(written: list[object], observations: object) -> None:
    written.extend(observations)  # type: ignore[arg-type]
