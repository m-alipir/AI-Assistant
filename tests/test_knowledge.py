from datetime import UTC, datetime, timedelta

from app.knowledge.repository import HybridRetriever, InMemoryKnowledgeRepository
from app.knowledge.schemas import EventDraft, Inference, RetrievalQuery, SourceBackedClaim


def amd_tsmc_event(now: datetime) -> EventDraft:
    return EventDraft(
        event_id="event-amd-tsmc",
        title="AMD expands TSMC advanced packaging capacity",
        occurred_at=now,
        category_paths=["technology.semiconductors.manufacturing"],
        entities=["AMD", "TSMC"],
        topics=["advanced packaging"],
        source_item_ids=["source-amd", "source-tsmc"],
        claims=[
            SourceBackedClaim(
                statement="AMD said TSMC will provide additional advanced packaging capacity.",
                source_item_id="source-amd",
                source_locator="announcement paragraph 2",
            )
        ],
        inferences=[
            Inference(
                statement="Supply flexibility may improve.",
                inference_type="implication",
                supporting_claim_ids=["claim-amd-tsmc"],
            )
        ],
        embedding=[0.9, 0.1, 0.0],
        raw_content="Raw public announcement retained temporarily.",
    )


def test_m3_fixture_is_discoverable_by_structured_lexical_and_semantic_paths() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    repository = InMemoryKnowledgeRepository()
    repository.add_category("technology", "Technology")
    repository.add_category("semiconductors", "Semiconductors", "technology")
    repository.add_category("manufacturing", "Manufacturing", "technology.semiconductors")
    repository.add_entity("AMD", ["Advanced Micro Devices"])
    repository.add_entity("TSMC", ["Taiwan Semiconductor"])
    repository.add_topic("advanced packaging")
    event = repository.add_event(amd_tsmc_event(now))
    retriever = HybridRetriever(repository)

    results = retriever.search(
        RetrievalQuery(
            category_path="technology.semiconductors",
            entity="Advanced Micro Devices",
            topic="advanced packaging",
            since=now - timedelta(days=1),
            until=now + timedelta(days=1),
            text="AMD TSMC packaging",
            embedding=[1.0, 0.0, 0.0],
        )
    )

    assert [result.event.event_id for result in results] == [event.event_id]
    assert results[0].lexical_score > 0
    assert results[0].semantic_score > 0.9
    assert results[0].combined_score > 0.4
    assert results[0].event.source_item_ids == ["source-amd", "source-tsmc"]
    assert results[0].event.claims[0].source_item_id == "source-amd"
    assert results[0].event.inferences[0].statement == "Supply flexibility may improve."


def test_raw_retention_removes_only_expired_public_content() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    repository = InMemoryKnowledgeRepository()
    repository.add_event(amd_tsmc_event(now - timedelta(days=31)))

    assert repository.expire_raw_content(now - timedelta(days=30)) == 1
    retained = repository.events["event-amd-tsmc"]
    assert retained.raw_content is None
    assert retained.claims[0].statement
    assert retained.source_item_ids == ["source-amd", "source-tsmc"]


def test_m3_rejects_inconsistent_embedding_dimensions() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    repository = InMemoryKnowledgeRepository()
    repository.add_event(amd_tsmc_event(now))
    wrong_dimensions = amd_tsmc_event(now).model_copy(
        update={"event_id": "event-mismatched", "embedding": [1.0, 0.0]}
    )

    try:
        repository.add_event(wrong_dimensions)
    except ValueError as error:
        assert "dimensions" in str(error)
    else:
        raise AssertionError("inconsistent vector dimensions must not enter the collection")
