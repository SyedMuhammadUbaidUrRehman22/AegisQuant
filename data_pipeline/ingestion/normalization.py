"""Pure normalization from Yahoo-shaped rows to the canonical contract."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from data_pipeline.ingestion.calendars import SessionCalendar
from data_pipeline.schema import (
    CanonicalBar,
    CorporateAction,
    CorporateActionType,
    Instrument,
    NormalizationResult,
    QualityIssue,
    QualitySeverity,
    SourceBatch,
)

REQUIRED_COLUMNS = frozenset({"timestamp", "Open", "High", "Low", "Close", "Adj Close", "Volume"})
PRICE_QUANTUM = Decimal("0.00000001")
ACTION_QUANTUM = Decimal("0.0000000001")


def _parse_decimal(value: str | None, *, field: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field} is null")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} is not numeric") from error
    if not parsed.is_finite():
        raise ValueError(f"{field} is not finite")
    return parsed


def _parse_volume(value: str | None) -> int:
    parsed = _parse_decimal(value, field="Volume")
    if parsed != parsed.to_integral_value():
        raise ValueError("Volume is not an integer")
    return int(parsed)


def _session_date(raw: str | None, timezone: str) -> date:
    if raw is None:
        raise ValueError("timestamp is null")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.date()
    return parsed.astimezone(ZoneInfo(timezone)).date()


def _critical(code: str, message: str, session: date | None = None) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=QualitySeverity.CRITICAL,
        message=message,
        session_date=session,
    )


def _warning(code: str, message: str, session: date | None = None) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=QualitySeverity.WARNING,
        message=message,
        session_date=session,
    )


def normalize_source_batch(
    batch: SourceBatch,
    instrument: Instrument,
    calendar: SessionCalendar,
) -> NormalizationResult:
    """Normalize source rows without silently dropping malformed observations."""

    issues: list[QualityIssue] = []
    missing = sorted(REQUIRED_COLUMNS.difference(batch.columns))
    if missing:
        issues.append(_critical("missing_columns", f"Missing required columns: {missing}"))
        return NormalizationResult(bars=(), corporate_actions=(), issues=tuple(issues))

    grouped: dict[date, list[tuple[int, dict[str, str | None]]]] = defaultdict(list)
    for row_number, row in enumerate(batch.rows, start=1):
        try:
            session = _session_date(row.get("timestamp"), instrument.timezone)
        except (ValueError, TypeError, OverflowError) as error:
            issues.append(_critical("timestamp_parse", f"Row {row_number}: {error}"))
            continue
        grouped[session].append((row_number, row))

    bars: list[CanonicalBar] = []
    actions: list[CorporateAction] = []
    for session in sorted(grouped):
        candidates = grouped[session]
        representations = {
            tuple(candidate.get(column) for column in batch.columns) for _, candidate in candidates
        }
        if len(representations) > 1:
            issues.append(
                _critical(
                    "conflicting_duplicate",
                    f"Conflicting source observations for {session.isoformat()}",
                    session,
                )
            )
            continue
        if len(candidates) > 1:
            issues.append(
                _warning(
                    "identical_duplicate",
                    f"Collapsed {len(candidates)} identical source rows",
                    session,
                )
            )
        row_number, row = candidates[0]
        try:
            if not calendar.is_session(session):
                raise ValueError("timestamp is not an expected exchange session")
            bar_start, bar_end = calendar.bounds(session)
            raw_prices = {
                field: _parse_decimal(row.get(source), field=source)
                for field, source in (
                    ("open", "Open"),
                    ("high", "High"),
                    ("low", "Low"),
                    ("close", "Close"),
                    ("adjusted_close", "Adj Close"),
                )
            }
            rounded_prices = {
                field: value.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)
                for field, value in raw_prices.items()
            }
            quality_flags: list[str] = []
            if raw_prices != rounded_prices:
                quality_flags.append("precision_rounded")
                issues.append(
                    _warning("precision_rounded", "Price precision rounded to 8 decimals", session)
                )
            bars.append(
                CanonicalBar(
                    instrument_id=instrument.instrument_id,
                    interval_code=batch.interval_code,
                    session_date=session,
                    bar_start_at=bar_start,
                    bar_end_at=bar_end,
                    volume=_parse_volume(row.get("Volume")),
                    source_name=batch.source_name,
                    quality_flags=tuple(quality_flags),
                    open=rounded_prices["open"],
                    high=rounded_prices["high"],
                    low=rounded_prices["low"],
                    close=rounded_prices["close"],
                    adjusted_close=rounded_prices["adjusted_close"],
                )
            )
            for source_column, action_type in (
                ("Dividends", CorporateActionType.DIVIDEND),
                ("Stock Splits", CorporateActionType.STOCK_SPLIT),
                ("Capital Gains", CorporateActionType.CAPITAL_GAIN),
            ):
                value = row.get(source_column)
                if value is None or value == "":
                    continue
                parsed_action = _parse_decimal(value, field=source_column)
                if math.isclose(float(parsed_action), 0.0, abs_tol=0.0):
                    continue
                if parsed_action < 0:
                    raise ValueError(f"{source_column} is negative")
                actions.append(
                    CorporateAction(
                        instrument_id=instrument.instrument_id,
                        effective_date=session,
                        action_type=action_type,
                        action_value=parsed_action.quantize(
                            ACTION_QUANTUM, rounding=ROUND_HALF_EVEN
                        ),
                        currency=None
                        if action_type is CorporateActionType.STOCK_SPLIT
                        else instrument.currency,
                        source_name=batch.source_name,
                    )
                )
        except (ValueError, InvalidOperation) as error:
            issues.append(_critical("row_parse", f"Row {row_number}: {error}", session))

    return NormalizationResult(
        bars=tuple(sorted(bars, key=lambda bar: bar.bar_start_at)),
        corporate_actions=tuple(
            sorted(actions, key=lambda action: (action.effective_date, action.action_type.value))
        ),
        issues=tuple(issues),
    )
