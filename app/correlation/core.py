"""M4 deterministic escalation and compact, evidence-bound correlation records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    occurred_at: datetime
    compact_summary: str
    importance: int = Field(ge=0, le=10)
    global_importance: int = Field(ge=0, le=10)
    entities: list[str]
    claim_ids: list[str]


class CorrelationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    importance_threshold: int = Field(default=7, ge=0, le=10)
    retrieval_threshold: float = Field(default=0.7, ge=0, le=1)
    max_context_events: int = Field(default=5, ge=1, le=10)


class CorrelationResult(BaseModel):
    """Model boundary: relation remains an inference with explicit event/claim evidence."""

    model_config = ConfigDict(extra="forbid")
    relation_type: str
    linked_event_ids: list[str] = Field(min_length=1)
    explanation: str
    evidence_claim_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    status: str = "active"


def should_escalate(
    event: MemoryEvent,
    policy: CorrelationPolicy,
    *,
    tracked_entity: bool = False,
    retrieval_score: float = 0,
    contradiction_candidate: bool = False,
) -> bool:
    """Use a strong reasoner only for meaningful, already-narrowed candidates."""
    return (
        event.importance >= policy.importance_threshold
        or event.global_importance >= policy.importance_threshold
        or tracked_entity
        or retrieval_score >= policy.retrieval_threshold
        or contradiction_candidate
    )


def select_context(
    current: MemoryEvent, candidates: list[tuple[MemoryEvent, float]], limit: int
) -> list[MemoryEvent]:
    """Keep only top relevant historical memories; never send the whole event store."""
    eligible = [candidate for candidate in candidates if candidate[0].event_id != current.event_id]
    return [event for event, _ in sorted(eligible, key=lambda item: item[1], reverse=True)[:limit]]
