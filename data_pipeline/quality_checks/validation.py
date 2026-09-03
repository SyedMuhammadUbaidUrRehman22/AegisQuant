"""Deterministic Stage 1 canonical OHLCV quality rules."""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime
from decimal import Decimal
from statistics import median

from data_pipeline.ingestion.calendars import SessionCalendar
from data_pipeline.schema import (
    CanonicalBar,
    Instrument,
    NormalizationResult,
    QualityIssue,
    QualityReport,
    QualitySeverity,
    ValidatedBatch,
)


def _issue(
    code: str,
    severity: QualitySeverity,
    message: str,
    bar: CanonicalBar | None = None,
) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=severity,
        message=message,
        session_date=None if bar is None else bar.session_date,
    )


def validate_batch(
    normalized: NormalizationResult,
    instrument: Instrument,
    calendar: SessionCalendar,
    *,
    requested_start: object,
    requested_end: object,
    as_of: datetime,
    price_jump_fraction: float,
    repeated_ohlc_sessions: int,
    volume_spike_multiple: float,
    volume_window_sessions: int,
) -> ValidatedBatch:
    """Apply release-blocking invariants and non-destructive anomaly warnings."""

    from datetime import date

    if not isinstance(requested_start, date) or not isinstance(requested_end, date):
        raise TypeError("requested dates must be date instances")

    issues = list(normalized.issues)
    expected = calendar.expected_completed_sessions(
        requested_start,
        requested_end,
        as_of=as_of,
        valid_from=instrument.valid_from,
        valid_to=instrument.valid_to,
    )
    expected_set = set(expected)
    observed_counts = Counter(bar.session_date for bar in normalized.bars)
    for session, count in sorted(observed_counts.items()):
        if count > 1:
            issues.append(
                QualityIssue(
                    code="canonical_duplicate",
                    severity=QualitySeverity.CRITICAL,
                    message=f"Canonical session occurs {count} times",
                    session_date=session,
                )
            )
    observed_set = set(observed_counts)
    for missing in sorted(expected_set - observed_set):
        issues.append(
            QualityIssue(
                code="unexpected_session_gap",
                severity=QualitySeverity.CRITICAL,
                message="Completed exchange session has no provider observation",
                session_date=missing,
            )
        )
    for unexpected in sorted(observed_set - expected_set):
        issues.append(
            QualityIssue(
                code="unexpected_session",
                severity=QualitySeverity.CRITICAL,
                message="Observation is outside the requested completed-session set",
                session_date=unexpected,
            )
        )

    recent_volumes: deque[int] = deque(maxlen=volume_window_sessions)
    repeated_count = 0
    previous_bar: CanonicalBar | None = None
    enriched_bars: list[CanonicalBar] = []
    for bar in normalized.bars:
        bar_issues: list[QualityIssue] = []
        if any(price <= 0 for price in (bar.open, bar.high, bar.low, bar.close)):
            bar_issues.append(
                _issue(
                    "nonpositive_price", QualitySeverity.CRITICAL, "OHLC price is not positive", bar
                )
            )
        if bar.adjusted_close <= 0:
            bar_issues.append(
                _issue(
                    "nonpositive_adjusted_close",
                    QualitySeverity.CRITICAL,
                    "Adjusted close is not positive",
                    bar,
                )
            )
        if bar.high < max(bar.open, bar.low, bar.close):
            bar_issues.append(
                _issue(
                    "high_inconsistent", QualitySeverity.CRITICAL, "High is below OHLC bounds", bar
                )
            )
        if bar.low > min(bar.open, bar.high, bar.close):
            bar_issues.append(
                _issue(
                    "low_inconsistent", QualitySeverity.CRITICAL, "Low is above OHLC bounds", bar
                )
            )
        if bar.volume < 0:
            bar_issues.append(
                _issue("negative_volume", QualitySeverity.CRITICAL, "Volume is negative", bar)
            )
        elif bar.volume == 0:
            bar_issues.append(
                _issue(
                    "zero_volume", QualitySeverity.WARNING, "Completed-session volume is zero", bar
                )
            )

        if previous_bar is not None:
            movement = abs(bar.close / previous_bar.close - Decimal(1))
            if movement > Decimal(str(price_jump_fraction)):
                bar_issues.append(
                    _issue(
                        "unusual_price_movement",
                        QualitySeverity.WARNING,
                        f"Close-to-close absolute return is {movement}",
                        bar,
                    )
                )
            if (bar.open, bar.high, bar.low, bar.close) == (
                previous_bar.open,
                previous_bar.high,
                previous_bar.low,
                previous_bar.close,
            ):
                repeated_count += 1
            else:
                repeated_count = 1
            if repeated_count >= repeated_ohlc_sessions:
                bar_issues.append(
                    _issue(
                        "repeated_ohlc",
                        QualitySeverity.WARNING,
                        f"OHLC repeated for {repeated_count} consecutive sessions",
                        bar,
                    )
                )
        else:
            repeated_count = 1

        nonzero_history = [value for value in recent_volumes if value > 0]
        if len(nonzero_history) >= 5:
            rolling_median = median(nonzero_history)
            if rolling_median > 0 and bar.volume > rolling_median * volume_spike_multiple:
                bar_issues.append(
                    _issue(
                        "unusual_volume",
                        QualitySeverity.WARNING,
                        f"Volume exceeds {volume_spike_multiple}x trailing median",
                        bar,
                    )
                )
        recent_volumes.append(bar.volume)
        issues.extend(bar_issues)
        flags = tuple(sorted(set(bar.quality_flags).union(issue.code for issue in bar_issues)))
        enriched_bars.append(bar.model_copy(update={"quality_flags": flags}))
        previous_bar = bar

    for action in normalized.corporate_actions:
        issues.append(
            QualityIssue(
                code="corporate_action",
                severity=QualitySeverity.WARNING,
                message=f"Observed {action.action_type.value} value {action.action_value}",
                session_date=action.effective_date,
            )
        )

    report = QualityReport(
        canonical_symbol=instrument.canonical_symbol,
        requested_start=requested_start,
        requested_end=requested_end,
        expected_sessions=len(expected),
        observed_sessions=len(observed_set),
        issues=tuple(
            sorted(
                issues,
                key=lambda item: (
                    item.session_date is None,
                    item.session_date,
                    item.severity.value,
                    item.code,
                    item.message,
                ),
            )
        ),
    )
    return ValidatedBatch(
        bars=tuple(enriched_bars),
        corporate_actions=normalized.corporate_actions,
        report=report,
    )
