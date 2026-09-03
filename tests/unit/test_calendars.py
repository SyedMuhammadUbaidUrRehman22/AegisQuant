"""Unit tests for exchange-session handling."""

from datetime import UTC, date, datetime

from data_pipeline.ingestion.calendars import SessionCalendar


def test_expected_sessions_distinguish_holiday_and_early_close() -> None:
    calendar = SessionCalendar("XNYS")

    sessions = calendar.expected_completed_sessions(
        date(2024, 7, 1), date(2024, 7, 6), as_of=datetime(2024, 7, 7, tzinfo=UTC)
    )
    _, july_third_close = calendar.bounds(date(2024, 7, 3))

    assert sessions == (date(2024, 7, 1), date(2024, 7, 2), date(2024, 7, 3), date(2024, 7, 5))
    assert july_third_close == datetime(2024, 7, 3, 17, 0, tzinfo=UTC)


def test_incomplete_session_is_not_expected() -> None:
    calendar = SessionCalendar("XNYS")

    sessions = calendar.expected_completed_sessions(
        date(2024, 1, 2),
        date(2024, 1, 3),
        as_of=datetime(2024, 1, 2, 17, 0, tzinfo=UTC),
    )

    assert sessions == ()
