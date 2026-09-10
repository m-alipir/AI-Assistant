import pytest

from app.knowledge.reembedding import ReembeddingRecord, ReembeddingService
from app.llm.core import EmbeddingResult


@pytest.mark.asyncio
async def test_reembedding_is_explicit_bounded_and_batched() -> None:
    persisted: list[tuple[str, EmbeddingResult, int]] = []
    calls: list[list[str]] = []

    async def fetch(limit: int) -> list[ReembeddingRecord]:
        assert limit == 3
        return [
            ReembeddingRecord("one", "one", None, None),
            ReembeddingRecord("two", "two", "old", 3),
            ReembeddingRecord("empty", "", None, None),
        ]

    async def embed(values: list[str], content_hash: str) -> EmbeddingResult:
        calls.append(values)
        return EmbeddingResult(model_id="new", dimensions=2, vectors=[[0.1, 0.2] for _ in values])

    async def persist(values: list[tuple[str, EmbeddingResult, int]]) -> None:
        persisted.extend(values)

    written = await ReembeddingService(fetch, persist, embed).run(limit=3, batch_size=2)
    assert written == 2
    assert calls == [["one", "two"]]
    assert [value[0] for value in persisted] == ["one", "two"]
