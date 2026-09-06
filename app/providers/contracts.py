"""Narrow, testable contracts for network-backed providers."""

from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel, Field


class ProviderError(RuntimeError):
    """A recoverable provider failure with no sensitive payload attached."""


class ExternalItem(BaseModel):
    """Minimal normalized item shape returned by a collector provider."""

    external_id: str | None = None
    canonical_url: str | None = None
    title: str
    snippet: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class CollectorProvider(Protocol):
    """A provider that streams compact items without prescribing a source type."""

    def collect(self) -> AsyncIterator[ExternalItem]:
        """Yield normalized external items."""


class LlmRequest(BaseModel):
    """Role-routed future LLM request boundary with no fixed model slug."""

    role: str
    content: str


class LlmResponse(BaseModel):
    """Validated provider response metadata for future role routing."""

    content: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0


class LlmProvider(Protocol):
    """Future OpenRouter-compatible client interface."""

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Produce one response for a role-routed request."""
