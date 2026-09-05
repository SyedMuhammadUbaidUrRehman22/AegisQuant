"""Deterministic feature computation over canonical Stage 1 bars."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

import numpy as np
import pandas as pd

from feature_engineering.features import (
    log_return,
    momentum,
    rolling_annualized_volatility,
    rolling_correlation,
    simple_return,
)
from feature_engineering.registry import FeatureDefinition, FeatureRegistry

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

    def __post_init__(self) -> None:
        if self.instrument_id <= 0 or not self.feature_name or self.feature_version <= 0:
            raise ValueError("feature identity fields must be nonempty and positive")
        if re.fullmatch(r"[0-9a-f]{64}", self.definition_hash) is None:
            raise ValueError("definition_hash must be a lowercase SHA-256 digest")
        if (
            pd.isna(self.bar_end_at)
            or pd.isna(self.feature_as_of)
            or self.bar_end_at.utcoffset() is None
            or self.feature_as_of.utcoffset() is None
        ):
            raise ValueError("feature timestamps must be timezone-aware")
        if self.feature_as_of > self.bar_end_at:
            raise ValueError("feature_as_of cannot be later than bar_end_at")
        if self.missing_reason not in {
            "available",
            "insufficient_history",
            "missing_input",
            "undefined",
        }:
            raise ValueError("unsupported feature missing reason")
        if self.missing_reason == "available":
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("available observations require a finite value")
        elif self.value is not None:
            raise ValueError("unavailable observations must have a null value")


REQUIRED_COLUMNS = {"instrument_id", "canonical_symbol", "bar_end_at", "adjusted_close", "volume"}


def _validate_bars(bars: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(bars.columns)
    if missing:
        raise ValueError(f"canonical bars missing columns: {sorted(missing)}")
    frame = bars.copy()
    timestamps = frame["bar_end_at"].map(pd.Timestamp)
    if any(value is pd.NaT or value.tzinfo is None for value in timestamps):
        raise ValueError("canonical timestamps must be non-null and timezone-aware")
    frame["bar_end_at"] = pd.to_datetime(frame["bar_end_at"], utc=True)
    # Validate values only inside the requested information set.
    frame = frame.loc[frame["bar_end_at"] <= cutoff].copy()
    if frame.duplicated(["instrument_id", "bar_end_at"]).any():
        raise ValueError("canonical bars contain duplicate instrument timestamps")
    frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="raise")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="raise")
    identifiers = pd.to_numeric(frame["instrument_id"], errors="raise")
    if (identifiers.isna() | (identifiers <= 0) | (identifiers % 1 != 0)).any():
        raise ValueError("instrument ids must be positive integers")
    frame["instrument_id"] = identifiers.astype("int64")
    if frame["canonical_symbol"].isna().any() or frame["canonical_symbol"].eq("").any():
        raise ValueError("canonical symbols must be nonempty")
    if (frame.groupby("instrument_id")["canonical_symbol"].nunique() != 1).any():
        raise ValueError("each instrument must have one canonical symbol")
    invalid_price = frame["adjusted_close"].notna() & (
        ~np.isfinite(frame["adjusted_close"]) | (frame["adjusted_close"] <= 0)
    )
    invalid_volume = frame["volume"].notna() & (
        ~np.isfinite(frame["volume"]) | (frame["volume"] < 0)
    )
    if invalid_price.any() or invalid_volume.any():
        raise ValueError("canonical prices must be positive finite values and volume nonnegative")
    return frame.sort_values(["instrument_id", "bar_end_at"], kind="stable").reset_index(drop=True)


def _panel(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    """Pack each instrument by observed-row ordinal; no calendar rows are created."""

    return frame.assign(position=frame.groupby("instrument_id").cumcount()).pivot(
        index="position", columns="instrument_id", values=field
    )


def _unpack(panel: pd.DataFrame, frame: pd.DataFrame) -> pd.Series:
    """Gather only original observations from a padded numerical panel."""

    positions = frame.groupby("instrument_id").cumcount().to_numpy()
    columns = panel.columns.get_indexer(pd.Index(frame["instrument_id"]))
    return pd.Series(panel.to_numpy()[positions, columns], index=frame.index)


def _input_missing_mask(prices: pd.DataFrame, definition: FeatureDefinition) -> pd.DataFrame:
    """Identify null inputs used by each formula; warmup padding is handled separately."""

    if definition.kind == "momentum":
        return prices.isna() | prices.isna().shift(
            definition.lookback_observations, fill_value=False
        )
    count = definition.lookback_observations + 1
    return prices.isna().rolling(count, min_periods=1).max().astype("bool")


def _correlation(
    frame: pd.DataFrame,
    returns: pd.Series,
    missing_returns: pd.Series,
    definition: FeatureDefinition,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute all instrument/benchmark pairs, checking both return endpoints."""

    candidates = frame.loc[frame["canonical_symbol"] == definition.benchmark_symbol]
    if candidates["instrument_id"].nunique() > 1:
        raise ValueError(f"benchmark {definition.benchmark_symbol} must resolve to one instrument")
    if candidates.empty:
        return (
            pd.Series(np.nan, index=frame.index),
            pd.Series(True, index=frame.index),
            pd.Series(False, index=frame.index),
        )
    data = frame.assign(
        own=returns,
        missing=missing_returns,
        start=frame.groupby("instrument_id")["bar_end_at"].shift(),
        row_id=frame.index,
    )
    benchmark = data.loc[candidates.index, ["bar_end_at", "own", "missing", "start"]].rename(
        columns={"own": "benchmark", "missing": "benchmark_missing", "start": "benchmark_start"}
    )
    paired = data.merge(benchmark, on="bar_end_at", how="inner", validate="many_to_one").set_index(
        "row_id"
    )
    has_prior = paired["start"].notna() & paired["benchmark_start"].notna()
    mismatch = has_prior & paired["start"].ne(paired["benchmark_start"])
    paired["missing"] = paired["missing"] | paired["benchmark_missing"] | mismatch
    paired.loc[mismatch, ["own", "benchmark"]] = np.nan
    window = definition.lookback_observations
    values = rolling_correlation(_panel(paired, "own"), _panel(paired, "benchmark"), window=window)
    missing = (
        _panel(paired, "missing").fillna(False).rolling(window, min_periods=1).max().astype("bool")
    )
    prior_counts = has_prior.astype("int64").groupby(paired["instrument_id"]).cumsum()
    return (
        _unpack(values, paired).reindex(frame.index),
        _unpack(missing, paired).reindex(frame.index, fill_value=True),
        prior_counts.lt(window).reindex(frame.index, fill_value=False),
    )


def compute_features(
    bars: pd.DataFrame, *, as_of: datetime, registry: FeatureRegistry | None = None
) -> tuple[FeatureObservation, ...]:
    """Compute the registered set with vectorized observed-session panels."""

    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    frame = _validate_bars(bars, cutoff.tz_convert("UTC"))
    definitions = (registry or FeatureRegistry()).all()
    if frame.empty:
        return ()
    prices = _panel(frame, "adjusted_close").astype("float64")
    positions = frame.groupby("instrument_id").cumcount()
    computed: dict[str, pd.Series] = {}
    missing_masks: dict[str, pd.Series] = {}
    warmup_masks: dict[str, pd.Series] = {}
    for definition in definitions:
        if definition.kind == "simple_return":
            values = simple_return(prices)
        elif definition.kind == "log_return":
            values = log_return(prices)
        elif definition.kind == "rolling_annualized_volatility":
            values = rolling_annualized_volatility(
                prices,
                window=definition.lookback_observations,
                annualization_factor=cast(int, definition.annualization_factor),
            )
        elif definition.kind == "momentum":
            values = momentum(prices, periods=definition.lookback_observations)
        else:
            continue
        computed[definition.name] = _unpack(values, frame)
        missing_masks[definition.name] = _unpack(_input_missing_mask(prices, definition), frame)
        warmup_masks[definition.name] = positions.add(1).lt(definition.minimum_observations)
    for definition in definitions:
        if definition.kind == "rolling_correlation":
            dependency = definition.dependencies[0]
            (
                computed[definition.name],
                missing_masks[definition.name],
                warmup_masks[definition.name],
            ) = _correlation(frame, computed[dependency], missing_masks[dependency], definition)

    observations: list[FeatureObservation] = []
    for definition in definitions:
        definition_hash = definition.definition_hash
        values_array = computed[definition.name].to_numpy()
        available = np.isfinite(values_array)
        reasons = np.where(
            available,
            "available",
            np.where(
                missing_masks[definition.name],
                "missing_input",
                np.where(warmup_masks[definition.name], "insufficient_history", "undefined"),
            ),
        )
        # Only serialization loops over output rows; numerical calculations above are batched.
        for instrument_id, timestamp, raw, reason in zip(
            frame["instrument_id"], frame["bar_end_at"], values_array, reasons, strict=True
        ):
            instant = timestamp.to_pydatetime()
            observations.append(
                FeatureObservation(
                    instrument_id=int(instrument_id),
                    feature_name=definition.name,
                    feature_version=definition.version,
                    definition_hash=definition_hash,
                    bar_end_at=instant,
                    feature_as_of=instant,
                    value=float(raw) if reason == "available" else None,
                    missing_reason=cast(MissingReason, reason),
                )
            )
    return tuple(observations)
