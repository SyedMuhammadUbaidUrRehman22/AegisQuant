"""Exchange-session semantics for canonical daily bars."""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd


@lru_cache(maxsize=8)
def _calendar(code: str) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(code)


class SessionCalendar:
    """Small, deterministic facade around exchange-calendars."""

    def __init__(self, code: str) -> None:
        self.code = code
        self._calendar = _calendar(code)

    def is_session(self, session_date: date) -> bool:
        """Return whether a local calendar date is a valid exchange session."""

        return bool(self._calendar.is_session(pd.Timestamp(session_date)))

    def bounds(self, session_date: date) -> tuple[datetime, datetime]:
        """Return the session open and close as UTC-aware datetimes."""

        label = pd.Timestamp(session_date)
        session_open = self._calendar.session_open(label).to_pydatetime()
        session_close = self._calendar.session_close(label).to_pydatetime()
        return session_open.astimezone(UTC), session_close.astimezone(UTC)

    def expected_completed_sessions(
        self,
        start_date: date,
        end_date: date,
        *,
        as_of: datetime,
        valid_from: date | None = None,
        valid_to: date | None = None,
    ) -> tuple[date, ...]:
        """Return valid, completed sessions in an end-exclusive requested range."""

        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        effective_start = max(filter(None, (start_date, valid_from)))
        inclusive_end = end_date.fromordinal(end_date.toordinal() - 1)
        if valid_to is not None:
            inclusive_end = min(inclusive_end, valid_to)
        if inclusive_end < effective_start:
            return ()
        sessions = self._calendar.sessions_in_range(
            pd.Timestamp(effective_start), pd.Timestamp(inclusive_end)
        )
        completed: list[date] = []
        for session in sessions:
            session_date = session.date()
            _, session_close = self.bounds(session_date)
            if session_close <= as_of.astimezone(UTC):
                completed.append(session_date)
        return tuple(completed)
