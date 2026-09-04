"""Immutable, versioned definitions for the Stage 2 feature contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Literal

FeatureKind = Literal[
    "simple_return", "log_return", "realized_volatility", "momentum", "rolling_correlation"
]


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    version: int
    kind: FeatureKind
    input_fields: tuple[str, ...]
    lookback_observations: int
    minimum_observations: int
    frequency: str
    dependencies: tuple[str, ...]
    as_of_semantics: str
    current_bar_included: bool
    target_period_included: bool
    missing_value_policy: str
    output_type: str
    output_domain: str
    description: str
    point_in_time_safe: bool
    benchmark_symbol: str | None = None
    annualization_factor: int | None = None
    observation_timestamp: str = "canonical bar_end_at"
    market_closure_policy: str = "no synthetic row; windows count observed sessions"
    newly_listed_policy: str = "null with insufficient_history until minimum observations"
    unexpected_gap_policy: str = "never fill; preserve the gap and reduce aligned history"

    def __post_init__(self) -> None:
        if not self.name or self.version < 1:
            raise ValueError("feature name must be nonempty and version must be positive")
        if self.lookback_observations < 1 or self.minimum_observations < 1:
            raise ValueError("lookback and minimum observations must be positive")
        if self.minimum_observations > self.lookback_observations + 1:
            raise ValueError("minimum observations exceed available price observations")
        if self.kind == "rolling_correlation" and not self.benchmark_symbol:
            raise ValueError("rolling correlation requires a benchmark symbol")

    @property
    def definition_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DEFAULT_FEATURES = (
    FeatureDefinition(
        name="adjusted_simple_return_1d",
        version=1,
        kind="simple_return",
        input_fields=("adjusted_close",),
        lookback_observations=1,
        minimum_observations=2,
        dependencies=(),
        output_domain="(-1, +inf)",
        description="Adjusted close-to-close simple return: P[t] / P[t-1] - 1.",
        frequency="1d",
        as_of_semantics="available at bar_end_at after the bar closes",
        current_bar_included=True,
        target_period_included=False,
        missing_value_policy="no filling; emit null with an explicit missing reason",
        output_type="float64",
        point_in_time_safe=True,
    ),
    FeatureDefinition(
        name="adjusted_log_return_1d",
        version=1,
        kind="log_return",
        input_fields=("adjusted_close",),
        lookback_observations=1,
        minimum_observations=2,
        dependencies=(),
        output_domain="finite real numbers",
        description="Natural log adjusted return: ln(P[t] / P[t-1]).",
        frequency="1d",
        as_of_semantics="available at bar_end_at after the bar closes",
        current_bar_included=True,
        target_period_included=False,
        missing_value_policy="no filling; emit null with an explicit missing reason",
        output_type="float64",
        point_in_time_safe=True,
    ),
    FeatureDefinition(
        name="realized_volatility_20d",
        version=1,
        kind="realized_volatility",
        input_fields=("adjusted_close",),
        lookback_observations=20,
        minimum_observations=21,
        dependencies=("adjusted_log_return_1d",),
        annualization_factor=252,
        output_domain="[0, +inf)",
        description="Sample standard deviation of 20 log returns, annualized by sqrt(252).",
        frequency="1d",
        as_of_semantics="available at bar_end_at after the bar closes",
        current_bar_included=True,
        target_period_included=False,
        missing_value_policy="no filling; emit null with an explicit missing reason",
        output_type="float64",
        point_in_time_safe=True,
    ),
    FeatureDefinition(
        name="momentum_20d",
        version=1,
        kind="momentum",
        input_fields=("adjusted_close",),
        lookback_observations=20,
        minimum_observations=21,
        dependencies=(),
        output_domain="(-1, +inf)",
        description="Adjusted price momentum: P[t] / P[t-20] - 1.",
        frequency="1d",
        as_of_semantics="available at bar_end_at after the bar closes",
        current_bar_included=True,
        target_period_included=False,
        missing_value_policy="no filling; emit null with an explicit missing reason",
        output_type="float64",
        point_in_time_safe=True,
    ),
    FeatureDefinition(
        name="rolling_correlation_spy_60d",
        version=1,
        kind="rolling_correlation",
        input_fields=("adjusted_close",),
        lookback_observations=60,
        minimum_observations=61,
        dependencies=("adjusted_simple_return_1d",),
        benchmark_symbol="SPY",
        output_domain="[-1, 1] or null for a constant window",
        description=(
            "Sample correlation of instrument and SPY simple returns over 60 aligned sessions."
        ),
        frequency="1d",
        as_of_semantics="available at bar_end_at after the bar closes",
        current_bar_included=True,
        target_period_included=False,
        missing_value_policy="no filling; emit null with an explicit missing reason",
        output_type="float64",
        point_in_time_safe=True,
    ),
)


class FeatureRegistry:
    def __init__(self, definitions: tuple[FeatureDefinition, ...] = DEFAULT_FEATURES) -> None:
        by_name = {definition.name: definition for definition in definitions}
        if len(by_name) != len(definitions):
            raise ValueError("feature names must be unique")
        self._definitions: Mapping[str, FeatureDefinition] = MappingProxyType(by_name)

    def get(self, name: str) -> FeatureDefinition:
        try:
            return self._definitions[name]
        except KeyError:
            raise KeyError(f"unknown feature: {name}") from None

    def all(self) -> tuple[FeatureDefinition, ...]:
        return tuple(self._definitions.values())
