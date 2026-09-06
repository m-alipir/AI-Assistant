"""Small in-memory M3 repository and deterministic hybrid retrieval service."""

import math
import re
from datetime import UTC, datetime

from app.knowledge.schemas import Category, Entity, EventDraft, RetrievalQuery, RetrievedEvent


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


class InMemoryKnowledgeRepository:
    """Offline repository fake used by M3 acceptance tests before job wiring is introduced."""

    def __init__(self) -> None:
        self.categories: dict[str, Category] = {}
        self.entities: dict[str, Entity] = {}
        self.aliases: dict[str, str] = {}
        self.topics: set[str] = set()
        self.events: dict[str, EventDraft] = {}

    def add_category(self, slug: str, name: str, parent_path: str | None = None) -> Category:
        path = f"{parent_path}.{slug}" if parent_path else slug
        category = Category(slug=slug, name=name, path=path, parent_path=parent_path)
        self.categories[path] = category
        return category

    def add_entity(self, canonical_name: str, aliases: list[str] | None = None) -> Entity:
        entity = Entity(canonical_name=canonical_name, aliases=aliases or [])
        self.entities[canonical_name] = entity
        for value in [canonical_name, *entity.aliases]:
            self.aliases[_normal(value)] = canonical_name
        return entity

    def add_topic(self, topic: str) -> None:
        self.topics.add(_normal(topic))

    def add_event(self, event: EventDraft) -> EventDraft:
        if event.occurred_at.tzinfo is None:
            raise ValueError("event timestamps must be timezone-aware UTC timestamps")
        if any(
            len(event.embedding) != len(existing.embedding) for existing in self.events.values()
        ):
            raise ValueError("embedding dimensions must match configured collection metadata")
        self.events[event.event_id] = event.model_copy(
            update={"occurred_at": event.occurred_at.astimezone(UTC)}
        )
        return self.events[event.event_id]

    def resolve_entity(self, name_or_alias: str) -> str | None:
        return self.aliases.get(_normal(name_or_alias))

    def expire_raw_content(self, before: datetime) -> int:
        """Apply raw-content retention without deleting distilled event/provenance records."""
        count = 0
        for event_id, event in self.events.items():
            if event.occurred_at < before.astimezone(UTC) and event.raw_content is not None:
                self.events[event_id] = event.model_copy(update={"raw_content": None})
                count += 1
        return count


class HybridRetriever:
    """Structured filtering then deterministic lexical/vector scoring over the narrowed set."""

    def __init__(self, repository: InMemoryKnowledgeRepository) -> None:
        self._repository = repository

    @staticmethod
    def _cosine(left: list[float], right: list[float] | None) -> float:
        if right is None or len(left) != len(right):
            return 0.0
        denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
            sum(value * value for value in right)
        )
        return (
            sum(a * b for a, b in zip(left, right, strict=True)) / denominator
            if denominator
            else 0.0
        )

    @staticmethod
    def _lexical(event: EventDraft, text: str | None) -> float:
        if not text:
            return 0.0
        haystack = " ".join(
            [
                event.title,
                *event.entities,
                *event.topics,
                *(claim.statement for claim in event.claims),
            ]
        ).casefold()
        terms = set(re.findall(r"[\w-]+", text.casefold()))
        return sum(term in haystack for term in terms) / max(len(terms), 1)

    def search(self, query: RetrievalQuery) -> list[RetrievedEvent]:
        resolved_entity = self._repository.resolve_entity(query.entity) if query.entity else None
        candidates: list[RetrievedEvent] = []
        for event in self._repository.events.values():
            if query.category_path and not any(
                path == query.category_path or path.startswith(f"{query.category_path}.")
                for path in event.category_paths
            ):
                continue
            if resolved_entity and resolved_entity not in event.entities:
                continue
            if query.entity and resolved_entity is None:
                continue
            if query.topic and _normal(query.topic) not in {
                _normal(topic) for topic in event.topics
            }:
                continue
            if query.since and event.occurred_at < query.since.astimezone(UTC):
                continue
            if query.until and event.occurred_at > query.until.astimezone(UTC):
                continue
            lexical = self._lexical(event, query.text)
            semantic = self._cosine(event.embedding, query.embedding)
            candidates.append(
                RetrievedEvent(
                    event=event,
                    lexical_score=lexical,
                    semantic_score=semantic,
                    combined_score=(lexical + semantic) / 2,
                )
            )
        return sorted(candidates, key=lambda result: result.combined_score, reverse=True)[
            : query.limit
        ]
