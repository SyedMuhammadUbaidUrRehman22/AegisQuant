"""Point-in-time, alignment, and missing-state tests for feature computation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from feature_engineering import FeatureObservation, compute_features


def _bars(days: int = 65) -> pd.DataFrame:
    start = datetime(2024, 1, 1, 21, tzinfo=UTC)
    rows = []
    for instrument_id, symbol, multiplier in ((1, "SPY", 1.0), (2, "QQQ", 1.5)):
        for offset in range(days):
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "canonical_symbol": symbol,
                    "bar_end_at": start + timedelta(days=offset),
                    "adjusted_close": (100.0 + offset) * multiplier,
                    "volume": 1_000_000 + offset,
                }
            )
    return pd.DataFrame(rows)


def _available(rows: tuple[object, ...], name: str) -> list[object]:
    return [row for row in rows if row.feature_name == name and row.value is not None]  # type: ignore[attr-defined]


def test_as_of_excludes_future_bars_and_future_mutation_cannot_change_history() -> None:
    bars = _bars()
    cutoff = datetime(2024, 2, 10, 21, tzinfo=UTC)
    baseline = compute_features(bars, as_of=cutoff)
    bars.loc[bars["bar_end_at"] > cutoff, "adjusted_close"] = 1_000_000.0
    mutated = compute_features(bars, as_of=cutoff)

    assert mutated == baseline
    assert all(row.feature_as_of <= row.bar_end_at <= cutoff for row in baseline)


def test_warmup_and_cross_instrument_alignment_are_explicit() -> None:
    rows = compute_features(_bars(), as_of=datetime(2024, 3, 31, tzinfo=UTC))
    simple = [
        row
        for row in rows
        if row.instrument_id == 1 and row.feature_name == "adjusted_simple_return_1d"
    ]
    correlations = _available(rows, "rolling_correlation_spy_60d")

    assert simple[0].missing_reason == "insufficient_history"
    assert simple[1].value == pytest.approx(1.0 / 100.0)
    assert len(correlations) == 10
    assert all(row.value == pytest.approx(1.0) for row in correlations)  # type: ignore[attr-defined]


def test_missing_input_is_not_filled() -> None:
    bars = _bars()
    bars.loc[(bars["instrument_id"] == 2) & (bars.index == 70), "adjusted_close"] = None
    rows = compute_features(bars, as_of=datetime(2024, 3, 31, tzinfo=UTC))

    assert any(row.instrument_id == 2 and row.missing_reason == "missing_input" for row in rows)


def test_missing_prior_price_is_not_misclassified_as_undefined() -> None:
    bars = _bars()
    missing_at = bars.loc[(bars["instrument_id"] == 1)].index[10]
    bars.loc[missing_at, "adjusted_close"] = None

    rows = compute_features(bars, as_of=datetime(2024, 3, 31, tzinfo=UTC))
    affected = [
        row
        for row in rows
        if row.instrument_id == 1
        and row.bar_end_at == bars.loc[missing_at + 1, "bar_end_at"]
        and row.feature_name in {"adjusted_simple_return_1d", "adjusted_log_return_1d"}
    ]
    rolling = [
        row
        for row in rows
        if row.instrument_id == 1
        and row.feature_name == "rolling_annualized_volatility_20d"
        and row.bar_end_at == bars.loc[missing_at + 20, "bar_end_at"]
    ]

    assert affected and all(row.missing_reason == "missing_input" for row in affected)
    assert rolling[0].missing_reason == "missing_input"


def test_naive_as_of_and_duplicate_keys_are_rejected() -> None:
    bars = _bars(2)
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_features(bars, as_of=datetime(2024, 1, 3))
    with pytest.raises(ValueError, match="duplicate"):
        compute_features(pd.concat((bars, bars.iloc[[0]])), as_of=datetime(2024, 1, 3, tzinfo=UTC))


def test_observation_contract_rejects_leakage_and_inconsistent_values() -> None:
    valid = FeatureObservation(
        instrument_id=1,
        feature_name="test",
        feature_version=1,
        definition_hash="a" * 64,
        bar_end_at=datetime(2024, 1, 2, tzinfo=UTC),
        feature_as_of=datetime(2024, 1, 2, tzinfo=UTC),
        value=1.0,
        missing_reason="available",
    )

    with pytest.raises(ValueError, match="later than"):
        replace(valid, feature_as_of=datetime(2024, 1, 3, tzinfo=UTC))
    with pytest.raises(ValueError, match="finite value"):
        replace(valid, value=None)
    with pytest.raises(ValueError, match="null value"):
        replace(valid, missing_reason="undefined")
    with pytest.raises(ValueError, match="unsupported"):
        replace(valid, value=None, missing_reason="bad")  # type: ignore[arg-type]
