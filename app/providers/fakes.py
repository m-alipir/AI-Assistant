"""Deterministic provider fakes for unit tests and offline development."""

from collections.abc import AsyncIterator

from app.providers.contracts import ExternalItem, LlmRequest, LlmResponse


class FakeCollectorProvider:
    """In-memory collector fake that performs no network I/O."""

    def __init__(self, items: list[ExternalItem]) -> None:
        self._items = items

    async def collect(self) -> AsyncIterator[ExternalItem]:
        for item in self._items:
            yield item


class FakeLlmProvider:
    """In-memory LLM fake with observable requests for assertions."""

    def __init__(self, response: LlmResponse) -> None:
        self.response = response
        self.requests: list[LlmRequest] = []

    async def complete(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        return self.response
