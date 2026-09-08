from datetime import UTC, datetime, timedelta

from app.interests.core import Feedback, Interest, explicit_intent, nightly


def test_m7_stable_learning():
    now = datetime(2026, 9, 7, tzinfo=UTC)
    fs = [
        Feedback(subject="amd", action="positive", at=now - timedelta(days=i)) for i in (1, 2, 3, 4)
    ]
    assert explicit_intent("more nvidia") == ("nvidia", 1)
    assert nightly(Interest(), fs, now).adaptive == 0.25
