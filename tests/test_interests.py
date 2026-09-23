from datetime import UTC, datetime, timedelta

import pytest

from app.interests.core import Feedback, Interest, explicit_intent, nightly
from app.interests.feedback import record_briefing_feedback


class _Result:
    def mappings(self):
        return self

    def one_or_none(self):
        return {"section": "For You", "canonical_title": "Fixture", "entities_json": "[]"}


class _Connection:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: object, parameters: object = None):
        self.calls.append((str(statement), parameters if isinstance(parameters, dict) else {}))
        return _Result()


def test_m7_stable_learning():
    now = datetime(2026, 9, 7, tzinfo=UTC)
    fs = [
        Feedback(subject="amd", action="positive", at=now - timedelta(days=i)) for i in (1, 2, 3, 4)
    ]
    assert explicit_intent("more nvidia") == ("nvidia", 1)
    assert nightly(Interest(), fs, now).adaptive == 0.25


@pytest.mark.asyncio
@pytest.mark.parametrize(("action", "expected_delta"), [("more", 0.1), ("less", -0.1)])
async def test_calibration_feedback_is_small_adaptive_signal_not_explicit_preference(
    action: str, expected_delta: float
) -> None:
    connection = _Connection()

    result = await record_briefing_feedback(
        connection,
        "briefing-1",
        "event-1",
        action,
        subject="GPU",
    )

    assert result.message == "İlgi ayarı kaydedildi."
    profile_call = next(
        params for query, params in connection.calls if "INSERT INTO interest_profile" in query
    )
    assert profile_call["delta"] == expected_delta
    assert ":delta, 0)" not in next(
        query for query, _ in connection.calls if "INSERT INTO interest_profile" in query
    )
