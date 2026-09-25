import pytest

from app.interests.feedback import record_briefing_feedback
from app.main import select_telegram_calibration_candidates


def _candidate_row(
    event_id: str,
    *,
    entities: str = "[]",
    topics: str = "[]",
    section: str = "For You",
    source_urls: list[str] | None = None,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "section": section,
        "entities_json": entities,
        "topics_json": topics,
        "source_urls": source_urls or [],
    }


def test_calibration_candidates_keep_concrete_subjects_and_skip_publishers_events_and_variants():
    rows = [
        _candidate_row(
            "event-techcrunch",
            entities='["TechCrunch Disrupt"]',
            topics='["TechCrunch Disrupt 2026"]',
            source_urls=["https://techcrunch.com/2026/09/24/story"],
        ),
        _candidate_row(
            "event-nyt-publisher",
            entities='["The New York Times"]',
            source_urls=["https://www.nytimes.com/2026/09/24/story"],
        ),
        _candidate_row(
            "event-google-io",
            entities='["Google I/O"]',
            topics='["Google I/O announcements"]',
            source_urls=["https://techcrunch.com/2026/09/24/google"],
        ),
        _candidate_row(
            "event-google-photos",
            entities='["Google Photos"]',
            topics='["Google Photos feature updates"]',
            source_urls=[
                "https://techcrunch.com/2026/09/24/photos",
                "https://google.com/photos/updates",
            ],
        ),
        _candidate_row(
            "event-google-photos-variant",
            entities='["Google Photos updates"]',
            source_urls=["https://example.com/photos"],
        ),
        _candidate_row(
            "event-publisher-only",
            entities='["TechCrunch"]',
            source_urls=["https://techcrunch.com/2026/09/24/another-story"],
        ),
        _candidate_row(
            "event-waymo",
            entities='["Waymo"]',
            topics='["robotaxi fleet expansion"]',
            source_urls=["https://waymo.com/news"],
        ),
        _candidate_row(
            "event-world",
            entities='["Climate policy"]',
            section="World in Brief",
        ),
        _candidate_row("event-generic", topics='["technology", "news"]'),
    ]

    assert select_telegram_calibration_candidates(rows) == [
        {"event_id": "event-google-photos", "subject": "Google Photos"},
        {"event_id": "event-waymo", "subject": "Waymo"},
    ]


def test_calibration_candidate_list_is_capped_at_three():
    rows = [
        _candidate_row(f"event-{subject.casefold()}", entities=f'["{subject}"]')
        for subject in ("Google Photos", "Waymo", "Android", "NVIDIA")
    ]

    assert [candidate["subject"] for candidate in select_telegram_calibration_candidates(rows)] == [
        "Google Photos",
        "Waymo",
        "Android",
    ]


class _Result:
    def mappings(self):
        return self

    def one_or_none(self):
        return {"section": "For You", "canonical_title": "Fixture", "entities_json": "[]"}


class _FeedbackConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: object, parameters: object = None):
        self.calls.append((str(statement), parameters if isinstance(parameters, dict) else {}))
        return _Result()


@pytest.mark.asyncio
async def test_selected_subject_is_the_exact_adaptive_feedback_identity():
    selected = select_telegram_calibration_candidates(
        [_candidate_row("event-photos", entities='["Google Photos"]')]
    )[0]
    connection = _FeedbackConnection()

    await record_briefing_feedback(
        connection,
        "briefing-1",
        selected["event_id"],
        "more",
        subject=selected["subject"],
    )

    feedback = next(
        params for query, params in connection.calls if "INSERT INTO feedback_events" in query
    )
    profile = next(
        params for query, params in connection.calls if "INSERT INTO interest_profile" in query
    )
    assert feedback["subject"] == profile["subject"] == selected["subject"] == "Google Photos"
    assert profile["delta"] == 0.1
