"""Bounded runtime bridge from retrieved memories to evidence-bound correlations."""

import hashlib
import json
from collections.abc import Awaitable, Callable

from app.correlation.core import (
    CorrelationPolicy,
    CorrelationResult,
    MemoryEvent,
    select_context,
    should_escalate,
)

Reasoner = Callable[[str, str, type[CorrelationResult]], Awaitable[CorrelationResult]]


class CorrelationRuntime:
    """Escalate only a bounded, scored historical slice and reject ungrounded output."""

    def __init__(self, policy: CorrelationPolicy | None = None) -> None:
        self._policy = policy or CorrelationPolicy()

    async def correlate(
        self,
        current: MemoryEvent,
        candidates: list[tuple[MemoryEvent, float]],
        reasoner: Reasoner,
        *,
        tracked_entity: bool = False,
        contradiction_candidate: bool = False,
    ) -> CorrelationResult | None:
        context = select_context(current, candidates, self._policy.max_context_events)
        if not context:
            return None
        best_score = max(
            score for candidate, score in candidates if candidate.event_id != current.event_id
        )
        if not should_escalate(
            current,
            self._policy,
            tracked_entity=tracked_entity,
            retrieval_score=best_score,
            contradiction_candidate=contradiction_candidate,
        ):
            return None
        payload = {
            "current": _compact(current),
            "candidates": [_compact(candidate) for candidate in context],
        }
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        result = await reasoner(
            "correlation-runtime-v1",
            serialized,
            CorrelationResult,
        )
        allowed_events = {candidate.event_id for candidate in context}
        allowed_claims = set(current.claim_ids)
        allowed_claims.update(claim_id for candidate in context for claim_id in candidate.claim_ids)
        if not set(result.linked_event_ids).issubset(allowed_events) or not set(
            result.evidence_claim_ids
        ).issubset(allowed_claims):
            return None
        return result


def correlation_content_hash(current: MemoryEvent, candidates: list[MemoryEvent]) -> str:
    """Produce a deterministic cache key without including raw source content."""
    value = "|".join([current.event_id, *(candidate.event_id for candidate in candidates)])
    return hashlib.sha256(value.encode()).hexdigest()


def _compact(event: MemoryEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "occurred_at": event.occurred_at.isoformat(),
        "summary": event.compact_summary[:1200],
        "entities": event.entities[:12],
        "claim_ids": event.claim_ids[:12],
    }
