from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.main import _delivery_delay_note


def test_late_delivery_note_uses_configured_local_target_and_exact_delay() -> None:
    target = datetime(2026, 9, 25, 14, 0, tzinfo=ZoneInfo("Europe/Istanbul"))
    delivered = datetime(2026, 9, 25, 11, 8, 34, tzinfo=UTC)

    assert _delivery_delay_note(target, delivered) == (
        "Hedef 14:00 idi; 8 dk 34 sn gecikme."
    )


def test_on_time_or_early_delivery_has_no_delay_note() -> None:
    target = datetime(2026, 9, 25, 14, 0, tzinfo=ZoneInfo("Europe/Istanbul"))
    early = datetime(2026, 9, 25, 10, 59, 59, tzinfo=UTC)
    on_time = target.astimezone(UTC)

    assert _delivery_delay_note(target, early) is None
    assert _delivery_delay_note(target, on_time) is None
