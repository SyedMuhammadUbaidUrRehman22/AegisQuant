"""Deterministic feature computation over canonical Stage 1 bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

import numpy as np
import pandas as pd

from feature_engineering.features import (
    log_return,
    momentum,
    realized_volatility,
    rolling_correlation,
    simple_return,
)
from feature_engineering.registry import FeatureRegistry

MissingReason = Literal["available", "insufficient_history", "missing_input", "undefined"]


@dataclass(frozen=True, slots=True)
class FeatureObservation:
    instrument_id: int
    feature_name: str
    feature_version: int
    definition_hash: str
    bar_end_at: datetime
    feature_as_of: datetime
    value: float | None
    missing_reason: MissingReason


REQUIRED_COLUMNS = {"instrument_id", "canonical_symbol", "bar_end_at", "adjusted_close", "volume"}


def _validate_bars(bars: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(bars.columns)
    if missing:
        raise ValueError(f"canonical bars missing columns: {sorted(missing)}")
    frame = bars.copy()
    frame["bar_end_at"] = pd.to_datetime(frame["bar_end_at"], utc=True)
    if frame.duplicated(["instrument_id", "bar_end_at"]).any():
        raise ValueError("canonical bars contain duplicate instrument timestamps")
    frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    invalid_price = frame["adjusted_close"].notna() & (
        ~np.isfinite(frame["adjusted_close"]) | (frame["adjusted_close"] <= 0)
    )
    invalid_volume = frame["volume"].notna() & (
        ~np.isfinite(frame["volume"]) | (frame["volume"] < 0)
    )
    if invalid_price.any() or invalid_volume.any():
        raise ValueError("canonical prices must be positive finite values and volume nonnegative")
    return frame.sort_values(["instrument_id", "bar_end_at"], kind="stable").reset_index(drop=True)


def compute_features(
    bars: pd.DataFrame, *, as_of: datetime, registry: FeatureRegistry | None = None
) -> tuple[FeatureObservation, ...]:
    """Compute registered features using only completed bars available by ``as_of``."""

    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    cutoff = cutoff.tz_convert("UTC")
    frame = _validate_bars(bars)
    frame = frame.loc[frame["bar_end_at"] <= cutoff].copy()
    definitions = (registry or FeatureRegistry()).all()
    if frame.empty:
        return ()

    computed: dict[tuple[int, str], pd.Series] = {}
    for instrument_id, group in frame.groupby("instrument_id", sort=True):
        typed_instrument_id = int(cast(int, instrument_id))
        prices = group.set_index("bar_end_at")["adjusted_close"].astype("float64")
        for definition in definitions:
            if definition.kind == "simple_return":
                values = simple_return(prices)
            elif definition.kind == "log_return":
                values = log_return(prices)
            elif definition.kind == "realized_volatility":
                values = realized_volatility(
                    prices,
                    window=definition.lookback_observations,
                    annualization_factor=definition.annualization_factor or 252,
                )
            elif definition.kind == "momentum":
                values = momentum(prices, periods=definition.lookback_observations)
            else:
                continue
            computed[(typed_instrument_id, definition.name)] = values

    symbol_ids = frame.groupby("canonical_symbol", sort=False)["instrument_id"].unique()
    for definition in definitions:
        if definition.kind != "rolling_correlation":
            continue
        benchmark_ids = symbol_ids.get(definition.benchmark_symbol or "", np.array([]))
        if len(benchmark_ids) != 1:
            raise ValueError(
                f"benchmark {definition.benchmark_symbol} must resolve to one instrument"
            )
        benchmark = computed[(int(benchmark_ids[0]), "adjusted_simple_return_1d")]
        for instrument_id in sorted(frame["instrument_id"].unique()):
            own = computed[(int(instrument_id), "adjusted_simple_return_1d")]
            computed[(int(instrument_id), definition.name)] = rolling_correlation(
                own, benchmark, window=definition.lookback_observations
            ).reindex(own.index)

    observations: list[FeatureObservation] = []
    for definition in definitions:
        for instrument_id in sorted(frame["instrument_id"].unique()):
            group = frame.loc[frame["instrument_id"] == instrument_id]
            values = computed[(int(instrument_id), definition.name)]
            input_missing = (
                group.set_index("bar_end_at")[list(definition.input_fields)].isna().any(axis=1)
            )
            for position, timestamp in enumerate(values.index):
                raw = values.loc[timestamp]
                if pd.notna(raw) and np.isfinite(float(raw)):
                    value, reason = float(raw), "available"
                elif bool(input_missing.loc[timestamp]):
                    value, reason = None, "missing_input"
                elif position + 1 < definition.minimum_observations:
                    value, reason = None, "insufficient_history"
                else:
                    value, reason = None, "undefined"
                instant = timestamp.to_pydatetime()
                observations.append(
                    FeatureObservation(
                        instrument_id=int(instrument_id),
                        feature_name=definition.name,
                        feature_version=definition.version,
                        definition_hash=definition.definition_hash,
                        bar_end_at=instant,
                        feature_as_of=instant,
                        value=value,
                        missing_reason=cast(MissingReason, reason),
                    )
                )
    return tuple(observations)
