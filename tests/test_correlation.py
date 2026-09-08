from datetime import UTC, datetime, timedelta

from app.correlation.core import (
    CorrelationPolicy,
    CorrelationResult,
    MemoryEvent,
    select_context,
    should_escalate,
)


def event(event_id: str, days_ago: int, importance: int = 3) -> MemoryEvent:
    return MemoryEvent(
        event_id=event_id,
        occurred_at=datetime(2026, 9, 6, tzinfo=UTC) - timedelta(days=days_ago),
        compact_summary=event_id,
        importance=importance,
        global_importance=1,
        entities=["AMD"],
        claim_ids=[f"claim-{event_id}"],
    )


def test_m4_escalates_selectively_and_sends_only_top_compact_history() -> None:
    policy = CorrelationPolicy(max_context_events=2)
    current = event("current", 0)
    relevant = event("relevant", 30)
    unrelated = event("unrelated", 31)

    assert not should_escalate(current, policy)
    assert should_escalate(current, policy, tracked_entity=True)
    assert should_escalate(current, policy, retrieval_score=0.8)
    assert [
        item.event_id for item in select_context(current, [(unrelated, 0.1), (relevant, 0.9)], 1)
    ] == ["relevant"]


def test_m4_relation_is_a_validated_inference_with_claim_evidence() -> None:
    relation = CorrelationResult.model_validate(
        {
            "relation_type": "supply_chain_update",
            "linked_event_ids": ["event-amd-tsmc"],
            "explanation": "The capacity update changes the context of the prior event.",
            "evidence_claim_ids": ["claim-amd-tsmc"],
            "confidence": 0.8,
            "status": "active",
        }
    )
    assert relation.linked_event_ids == ["event-amd-tsmc"]
