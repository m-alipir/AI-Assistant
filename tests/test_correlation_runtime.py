from datetime import UTC, datetime

import pytest

from app.correlation.core import CorrelationResult, MemoryEvent
from app.correlation.runtime import CorrelationRuntime


def _event(event_id: str, importance: int = 8, claim_id: str | None = None) -> MemoryEvent:
    return MemoryEvent(
        event_id=event_id,
        occurred_at=datetime(2026, 9, 10, tzinfo=UTC),
        compact_summary=f"{event_id} compact summary",
        importance=importance,
        global_importance=0,
        entities=["NVIDIA"],
        claim_ids=[claim_id or f"claim-{event_id}"],
    )


@pytest.mark.asyncio
async def test_runtime_uses_only_top_five_and_rejects_unknown_evidence() -> None:
    seen: dict[str, object] = {}

    async def reasoner(
        version: str, payload: str, result_type: type[CorrelationResult]
    ) -> CorrelationResult:
        seen["payload"] = payload
        return result_type(
            relation_type="update",
            linked_event_ids=["old-0"],
            explanation="grounded update",
            evidence_claim_ids=["claim-current", "claim-old-0"],
            confidence=0.8,
        )

    current = _event("current", claim_id="claim-current")
    candidates = [
        (_event(f"old-{index}", claim_id=f"claim-old-{index}"), 1 - index / 20)
        for index in range(7)
    ]
    result = await CorrelationRuntime().correlate(current, candidates, reasoner)
    assert result is not None
    assert "old-5" not in str(seen["payload"])
    assert "old-6" not in str(seen["payload"])


@pytest.mark.asyncio
async def test_runtime_skips_low_signal_and_invalid_model_links() -> None:
    calls = 0

    async def reasoner(
        version: str, payload: str, result_type: type[CorrelationResult]
    ) -> CorrelationResult:
        nonlocal calls
        calls += 1
        return result_type(
            relation_type="update",
            linked_event_ids=["not-retrieved"],
            explanation="invalid",
            evidence_claim_ids=["claim-current"],
            confidence=0.8,
        )

    current = _event("current", importance=1, claim_id="claim-current")
    candidate = _event("old", importance=1)
    assert await CorrelationRuntime().correlate(current, [(candidate, 0.1)], reasoner) is None
    assert calls == 0
    assert (
        await CorrelationRuntime().correlate(_event("high"), [(candidate, 0.8)], reasoner) is None
    )
    assert calls == 1
