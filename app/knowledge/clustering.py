"""Conservative deterministic clustering for distinct sources covering one public event."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "announces",
    "announced",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class ClusterCandidate:
    event_id: str
    title: str
    occurred_at: datetime
    entities: list[str]
    claims: list[str]


@dataclass(frozen=True)
class ClusterMatch:
    event_id: str
    score: float


def find_cluster(
    *,
    title: str,
    occurred_at: datetime,
    entities: list[str],
    claims: list[str],
    candidates: list[ClusterCandidate],
    max_age: timedelta = timedelta(hours=72),
) -> ClusterMatch | None:
    """Return only high-confidence corroboration; uncertain coverage remains a separate event."""
    if occurred_at.tzinfo is None:
        raise ValueError("event timestamp must be timezone-aware")
    title_terms = _terms(title)
    entity_terms = {_normal(entity) for entity in entities if _normal(entity)}
    claim_terms = _terms(" ".join(claims))
    matches: list[ClusterMatch] = []
    for candidate in candidates:
        if candidate.occurred_at.tzinfo is None:
            continue
        if abs(occurred_at.astimezone(UTC) - candidate.occurred_at.astimezone(UTC)) > max_age:
            continue
        title_overlap = _overlap(title_terms, _terms(candidate.title))
        entity_overlap = _overlap(
            entity_terms, {_normal(entity) for entity in candidate.entities if _normal(entity)}
        )
        claim_overlap = _overlap(claim_terms, _terms(" ".join(candidate.claims)))
        # A shared entity alone is never enough. Require a near-identical title, or strong title
        # and independently overlapping source-backed claims.
        if not (
            (entity_overlap > 0 and title_overlap >= 0.72)
            or (entity_overlap > 0 and title_overlap >= 0.55 and claim_overlap >= 0.35)
        ):
            continue
        score = 0.55 * title_overlap + 0.3 * entity_overlap + 0.15 * claim_overlap
        matches.append(ClusterMatch(candidate.event_id, score))
    return max(matches, key=lambda match: match.score) if matches else None


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[\w-]+", value.casefold()) if term not in _STOP_WORDS}


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0
