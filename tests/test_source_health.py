from datetime import UTC, datetime

import httpx

from app.ingestion.source_health import FetchFailure, classify_fetch_failure, next_retry_at


def test_source_health_classifies_rate_limit_and_bounds_backoff() -> None:
    request = httpx.Request("GET", "https://example.test/feed")
    response = httpx.Response(429, headers={"retry-after": "60"}, request=request)
    error = httpx.HTTPStatusError("limited", request=request, response=response)
    decision = classify_fetch_failure(error)
    retry_at = next_retry_at(decision, 20, datetime(2026, 9, 12, tzinfo=UTC))

    assert decision.category is FetchFailure.RATE_LIMITED
    assert retry_at == datetime(2026, 9, 12, 0, 12, tzinfo=UTC)


def test_source_health_marks_404_as_terminal() -> None:
    request = httpx.Request("GET", "https://example.test/missing")
    response = httpx.Response(404, request=request)
    error = httpx.HTTPStatusError("missing", request=request, response=response)
    decision = classify_fetch_failure(error)

    assert decision.category is FetchFailure.NOT_FOUND
    assert decision.terminal is True
    assert next_retry_at(decision, 1) is None
