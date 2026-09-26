from datetime import UTC, datetime, timedelta
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


def test_subsecond_delivery_wakeup_does_not_report_a_phantom_second() -> None:
    target = datetime(2026, 9, 25, 14, 0, tzinfo=ZoneInfo("Europe/Istanbul"))

    assert _delivery_delay_note(target, target + timedelta(milliseconds=200)) is None
    assert _delivery_delay_note(target, target + timedelta(milliseconds=999)) is None


def test_whole_second_and_large_delay_remain_visible_without_rounding_up() -> None:
    target = datetime(2026, 9, 25, 14, 0, tzinfo=ZoneInfo("Europe/Istanbul"))
    utc_target = target.astimezone(UTC)

    assert _delivery_delay_note(target, utc_target.replace(second=1)) == (
        "Hedef 14:00 idi; 1 sn gecikme."
    )
