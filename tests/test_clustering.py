from datetime import UTC, datetime, timedelta

from app.knowledge.clustering import ClusterCandidate, find_cluster


def test_multi_source_coverage_clusters_only_when_title_entity_and_time_align() -> None:
    now = datetime(2026, 9, 10, 9, tzinfo=UTC)
    candidate = ClusterCandidate(
        event_id="tsmc-capacity",
        title="TSMC expands advanced packaging capacity for AMD",
        occurred_at=now - timedelta(hours=4),
        entities=["TSMC", "AMD"],
        claims=["TSMC will add advanced packaging capacity for AMD products."],
    )

    match = find_cluster(
        title="AMD and TSMC expand advanced packaging capacity",
        occurred_at=now,
        entities=["AMD", "TSMC"],
        claims=["AMD confirmed additional advanced packaging capacity from TSMC."],
        candidates=[candidate],
    )

    assert match is not None
    assert match.event_id == "tsmc-capacity"


def test_similar_company_news_without_a_matching_event_stays_separate() -> None:
    now = datetime(2026, 9, 10, 9, tzinfo=UTC)
    candidate = ClusterCandidate(
        event_id="amd-packaging",
        title="AMD expands advanced packaging capacity",
        occurred_at=now,
        entities=["AMD"],
        claims=["AMD added packaging capacity for a new processor line."],
    )

    assert (
        find_cluster(
            title="AMD launches a new mobile processor family",
            occurred_at=now + timedelta(hours=2),
            entities=["AMD"],
            claims=["The new processor family targets thin laptops."],
            candidates=[candidate],
        )
        is None
    )
