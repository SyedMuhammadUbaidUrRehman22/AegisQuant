"""Adversarial cutoff, missing-data, benchmark, and registry tests."""

from dataclasses import replace
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

from data_pipeline.ingestion.calendars import SessionCalendar
from feature_engineering import FeatureRegistry, compute_features
from feature_engineering.registry import DEFAULT_FEATURES
from tests.factories import feature_bars


def _registry(window: int = 3) -> FeatureRegistry:
    return FeatureRegistry(
        (
            DEFAULT_FEATURES[0],
            replace(
                DEFAULT_FEATURES[4], lookback_observations=window, minimum_observations=window + 1
            ),
        )
    )


@pytest.mark.parametrize("future_price", [-1.0, float("inf"), float("nan")])
def test_invalid_future_values_do_not_affect_past_features(future_price: float) -> None:
    bars = feature_bars(70)
    cutoff = bars.iloc[63].bar_end_at
    expected = compute_features(bars, as_of=cutoff)
    full = compute_features(bars, as_of=bars.bar_end_at.max())
    assert tuple(row for row in full if row.bar_end_at <= cutoff) == expected
    bars.loc[bars.bar_end_at > cutoff, "adjusted_close"] = future_price
    assert compute_features(bars, as_of=cutoff) == expected
    assert compute_features(bars.sample(frac=1, random_state=7), as_of=cutoff) == expected
    assert compute_features(bars, as_of=cutoff.tz_convert("Asia/Karachi")) == expected


@pytest.mark.parametrize("timestamp", [None, pd.NaT, "2024-01-02T21:00:00"])
def test_canonical_timestamps_must_be_aware_and_nonnull(timestamp: object) -> None:
    bars = feature_bars(2)
    cutoff = bars.bar_end_at.max()
    bars["bar_end_at"] = bars.bar_end_at.astype("object")
    bars.loc[0, "bar_end_at"] = timestamp
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_features(bars, as_of=cutoff)


@pytest.mark.parametrize("instrument_id", [1, 2])
def test_correlation_retains_null_price_provenance_and_recovers(instrument_id: int) -> None:
    bars = feature_bars(10)
    bars.loc[
        (bars.instrument_id == instrument_id) & (bars.bar_end_at == bars.iloc[4].bar_end_at),
        "adjusted_close",
    ] = np.nan
    rows = compute_features(bars, as_of=bars.bar_end_at.max(), registry=_registry())
    correlations = [
        row for row in rows if row.instrument_id == 2 and "correlation" in row.feature_name
    ]
    assert correlations[3].missing_reason == "available"
    assert all(row.missing_reason == "missing_input" for row in correlations[4:8])
    assert correlations[8].missing_reason == "available"


def test_correlation_does_not_pair_returns_with_different_start_times() -> None:
    bars = feature_bars(10)
    bars = bars.drop(index=14)  # QQQ missing a session; its next return spans two sessions.
    rows = compute_features(bars, as_of=bars.bar_end_at.max(), registry=_registry())
    affected = [
        row
        for row in rows
        if row.instrument_id == 2
        and "correlation" in row.feature_name
        and row.bar_end_at == bars.loc[15, "bar_end_at"]
    ]
    assert affected[0].missing_reason == "missing_input"
    assert affected[0].value is None
    assert not any(
        row.instrument_id == 2 and row.bar_end_at == bars.loc[4, "bar_end_at"] for row in rows
    )


def test_absent_benchmark_is_missing_and_late_benchmark_has_own_warmup() -> None:
    bars = feature_bars(10)
    own_only = bars.loc[bars.instrument_id == 2]
    rows = compute_features(own_only, as_of=bars.bar_end_at.max(), registry=_registry())
    assert all(
        row.missing_reason == "missing_input" for row in rows if "correlation" in row.feature_name
    )
    late = bars.drop(index=range(7))
    rows = compute_features(late, as_of=bars.bar_end_at.max(), registry=_registry())
    assert all(
        row.missing_reason == "insufficient_history"
        for row in rows
        if "correlation" in row.feature_name and row.bar_end_at >= bars.iloc[7].bar_end_at
    )


def test_momentum_only_requires_endpoint_prices() -> None:
    bars = feature_bars(25)
    bars.loc[10, "adjusted_close"] = np.nan
    rows = compute_features(bars, as_of=bars.bar_end_at.max())
    endpoint = next(
        row
        for row in rows
        if row.instrument_id == 1
        and row.feature_name == "momentum_20d"
        and row.bar_end_at == bars.loc[20, "bar_end_at"]
    )
    assert endpoint.value == pytest.approx(0.2)


def test_renamed_dependency_and_reordered_registry_compute_same_values() -> None:
    bars = feature_bars(10)
    simple, correlation = _registry().all()
    renamed = replace(simple, name="daily_return")
    registry = FeatureRegistry((replace(correlation, dependencies=("daily_return",)), renamed))
    rows = compute_features(bars, as_of=bars.bar_end_at.max(), registry=registry)
    assert all(
        row.value == pytest.approx(1)
        for row in rows
        if "correlation" in row.feature_name and row.value is not None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"lookback_observations": 2, "minimum_observations": 3},
        {"minimum_observations": 1},
        {"current_bar_included": False},
        {"target_period_included": True},
        {"annualization_factor": 0},
        {"input_fields": ("volume",)},
        {"kind": "unknown"},
    ],
)
def test_registry_rejects_unimplemented_semantics(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT_FEATURES[0], **changes)


def test_registry_rejects_missing_dependency() -> None:
    with pytest.raises(ValueError, match="dependency"):
        FeatureRegistry((DEFAULT_FEATURES[4],))


def test_exchange_closure_and_early_close_keep_canonical_timestamps() -> None:
    calendar = SessionCalendar("XNYS")
    sessions = calendar.expected_completed_sessions(
        date(2024, 7, 1), date(2024, 7, 6), as_of=datetime(2024, 7, 7, tzinfo=UTC)
    )
    bars = feature_bars(len(sessions))
    timestamps = [calendar.bounds(session)[1] for session in sessions]
    bars["bar_end_at"] = timestamps * 2
    rows = compute_features(bars, as_of=max(timestamps))
    assert len(rows) == len(sessions) * 2 * 5
    assert {row.bar_end_at for row in rows} == set(timestamps)
    assert date(2024, 7, 4) not in {row.bar_end_at.date() for row in rows}
    assert calendar.bounds(date(2024, 7, 3))[1].hour == 17


def test_sparse_panel_windows_count_each_assets_observed_rows() -> None:
    bars = feature_bars(25).drop(index=[28, 30, 31])
    registry = FeatureRegistry(
        (DEFAULT_FEATURES[0], DEFAULT_FEATURES[2], DEFAULT_FEATURES[1], DEFAULT_FEATURES[3])
    )
    rows = compute_features(bars, as_of=bars.bar_end_at.max(), registry=registry)
    own = bars.loc[bars.instrument_id == 2]
    simple = [
        row
        for row in rows
        if row.instrument_id == 2 and row.feature_name == "adjusted_simple_return_1d"
    ]
    assert len(simple) == len(own)
    expected = own.adjusted_close.div(own.adjusted_close.shift()).sub(1).iloc[1:]
    assert [row.value for row in simple[1:]] == pytest.approx(expected.tolist())
    momentum = [
        row for row in rows if row.instrument_id == 2 and row.feature_name == "momentum_20d"
    ]
    assert all(row.missing_reason == "insufficient_history" for row in momentum[:20])
    assert momentum[20].value == pytest.approx(
        own.adjusted_close.iloc[20] / own.adjusted_close.iloc[0] - 1
    )
