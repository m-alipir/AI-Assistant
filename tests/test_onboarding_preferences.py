import pytest
from pydantic import ValidationError

from app.config.onboarding import GmailPollingPreference


def test_gmail_polling_interval_defaults_to_one_hour_and_has_finite_bounds() -> None:
    assert GmailPollingPreference().interval_minutes == 60
    assert GmailPollingPreference(interval_minutes=15).interval_minutes == 15
    assert GmailPollingPreference(interval_minutes=1440).interval_minutes == 1440
    with pytest.raises(ValidationError):
        GmailPollingPreference(interval_minutes=14)
    with pytest.raises(ValidationError):
        GmailPollingPreference(interval_minutes=1441)
