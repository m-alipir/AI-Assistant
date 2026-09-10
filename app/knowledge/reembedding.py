"""Explicit, bounded re-embedding orchestration; never runs automatically at startup."""

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.llm.core import EmbeddingResult


@dataclass(frozen=True)
class ReembeddingRecord:
    record_id: str
    text: str
    model_id: str | None
    dimensions: int | None


FetchRecords = Callable[[int], Awaitable[list[ReembeddingRecord]]]
PersistVectors = Callable[[list[tuple[str, EmbeddingResult, int]]], Awaitable[None]]
Embed = Callable[[list[str], str], Awaitable[EmbeddingResult]]


class ReembeddingService:
    """Re-embed only missing or incompatible compact retained records in small batches."""

    def __init__(self, fetch: FetchRecords, persist: PersistVectors, embed: Embed) -> None:
        self._fetch, self._persist, self._embed = fetch, persist, embed

    async def run(self, *, limit: int = 50, batch_size: int = 20) -> int:
        if not 1 <= limit <= 200 or not 1 <= batch_size <= 50:
            raise ValueError("re-embedding limits are out of range")
        records = await self._fetch(limit)
        written = 0
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            texts = [record.text[:2400] for record in batch if record.text]
            usable = [record for record in batch if record.text]
            if not usable:
                continue
            digest = hashlib.sha256(
                "|".join(record.record_id for record in usable).encode()
            ).hexdigest()
            result = await self._embed(texts, digest)
            if len(result.vectors) != len(usable):
                raise ValueError("embedding result count does not match requested records")
            await self._persist(
                [(record.record_id, result, index) for index, record in enumerate(usable)]
            )
            written += len(usable)
        return written
