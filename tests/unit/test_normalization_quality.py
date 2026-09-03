"""Unit and regression tests for canonical normalization and quality policy."""

from datetime import UTC, date, datetime
from decimal import Decimal

from data_pipeline.ingestion.calendars import SessionCalendar
from data_pipeline.ingestion.normalization import normalize_source_batch
from data_pipeline.quality_checks import validate_batch
from data_pipeline.schema import QualitySeverity
from tests.factories import instrument, source_batch, source_row


def _validate(rows: tuple[dict[str, str | None], ...]) -> object:
    calendar = SessionCalendar("XNYS")
    normalized = normalize_source_batch(source_batch(rows), instrument(), calendar)
    return validate_batch(
        normalized,
        instrument(),
        calendar,
        requested_start=date(2024, 1, 2),
        requested_end=date(2024, 1, 5),
        as_of=datetime(2024, 1, 6, tzinfo=UTC),
        price_jump_fraction=0.25,
        repeated_ohlc_sessions=3,
        volume_spike_multiple=20,
        volume_window_sessions=60,
    )


def test_normalizes_timezone_prices_volume_and_corporate_action() -> None:
    row = source_row(date(2024, 1, 2), open_price="100.123456789", dividend="0.50")
    batch = source_batch((row,), end=date(2024, 1, 3))
    calendar = SessionCalendar("XNYS")

    normalized = normalize_source_batch(batch, instrument(), calendar)

    assert normalized.bars[0].open == Decimal("100.12345679")
    assert normalized.bars[0].bar_start_at == datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    assert normalized.bars[0].bar_end_at == datetime(2024, 1, 2, 21, 0, tzinfo=UTC)
    assert normalized.corporate_actions[0].action_value == Decimal("0.5000000000")
    assert {issue.code for issue in normalized.issues} == {"precision_rounded"}


def test_identical_provider_duplicates_collapse_with_warning() -> None:
    rows = tuple(source_row(day) for day in (date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)))
    duplicated = (rows[0], rows[0], rows[1], rows[2])

    validated = _validate(duplicated)

    assert len(validated.bars) == 3  # type: ignore[attr-defined]
    assert "identical_duplicate" in {  # type: ignore[attr-defined]
        issue.code
        for issue in validated.report.issues  # type: ignore[attr-defined]
    }


def test_conflicting_duplicates_and_gaps_are_critical() -> None:
    first = source_row(date(2024, 1, 2))
    conflict = source_row(date(2024, 1, 2), close="100")

    validated = _validate((first, conflict, source_row(date(2024, 1, 4))))
    critical_codes = {
        issue.code
        for issue in validated.report.issues  # type: ignore[attr-defined]
        if issue.severity is QualitySeverity.CRITICAL
    }

    assert "conflicting_duplicate" in critical_codes
    assert "unexpected_session_gap" in critical_codes


def test_extreme_price_is_warning_and_not_discarded() -> None:
    rows = (
        source_row(date(2024, 1, 2)),
        source_row(date(2024, 1, 3), open_price="199", high="205", low="198", close="200"),
        source_row(date(2024, 1, 4), open_price="201", high="203", low="200", close="202"),
    )

    validated = _validate(rows)

    assert len(validated.bars) == 3  # type: ignore[attr-defined]
    assert "unusual_price_movement" in {  # type: ignore[attr-defined]
        issue.code
        for issue in validated.report.issues  # type: ignore[attr-defined]
    }


def test_invalid_ohlc_and_noninteger_volume_are_critical() -> None:
    rows = (
        source_row(date(2024, 1, 2), high="98"),
        source_row(date(2024, 1, 3), volume="1.5"),
        source_row(date(2024, 1, 4)),
    )

    validated = _validate(rows)

    assert validated.report.critical_count >= 2  # type: ignore[attr-defined]


def test_missing_required_column_is_critical() -> None:
    row = source_row(date(2024, 1, 2))
    row.pop("Adj Close")
    batch = source_batch((row,), end=date(2024, 1, 3))

    normalized = normalize_source_batch(batch, instrument(), SessionCalendar("XNYS"))

    assert normalized.bars == ()
    assert normalized.issues[0].code == "missing_columns"


def test_null_nan_and_infinite_values_do_not_reach_canonical_bars() -> None:
    rows = (
        source_row(date(2024, 1, 2), open_price="NaN"),
        source_row(date(2024, 1, 3), close="Infinity"),
        source_row(date(2024, 1, 4), volume=""),
    )

    normalized = normalize_source_batch(source_batch(rows), instrument(), SessionCalendar("XNYS"))

    assert normalized.bars == ()
    assert (
        len([issue for issue in normalized.issues if issue.severity is QualitySeverity.CRITICAL])
        == 3
    )
