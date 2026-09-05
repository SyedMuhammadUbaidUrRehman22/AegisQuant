"""Immutable, versioned definitions for the Stage 2 feature contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from types import MappingProxyType
from typing import Literal

FeatureKind = Literal[
    "simple_return",
    "log_return",
    "rolling_annualized_volatility",
    "momentum",
    "rolling_correlation",
]


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    """Complete, hashable semantics for one versioned feature."""

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
    dependency_hashes: tuple[str, ...] = ()
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
        if self.kind not in {
            "simple_return",
            "log_return",
            "momentum",
            "rolling_annualized_volatility",
            "rolling_correlation",
        }:
            raise ValueError("unsupported feature kind")
        if self.minimum_observations != self.lookback_observations + 1:
            raise ValueError("minimum observations must equal lookback plus one")
        if self.kind in {"simple_return", "log_return"} and self.lookback_observations != 1:
            raise ValueError("daily returns require lookback 1")
        if self.kind in {"rolling_correlation", "rolling_annualized_volatility"}:
            if self.lookback_observations < 2:
                raise ValueError("sample statistics require lookback at least 2")
        if self.kind == "rolling_annualized_volatility":
            if self.annualization_factor is None or self.annualization_factor <= 0:
                raise ValueError("volatility requires a positive annualization factor")
        elif self.annualization_factor is not None:
            raise ValueError("annualization factor only applies to volatility")
        if self.kind != "rolling_correlation" and self.benchmark_symbol is not None:
            raise ValueError("benchmark only applies to correlation")
        if self.input_fields != ("adjusted_close",) or self.frequency != "1d":
            raise ValueError("Stage 2 supports daily adjusted-close inputs only")
        if (
            not self.current_bar_included
            or self.target_period_included
            or not self.point_in_time_safe
        ):
            raise ValueError("Stage 2 requires current completed bars and excludes future targets")
        if self.output_type != "float64" or len(self.name) > 96:
            raise ValueError("unsupported output type or feature name length")

    @property
    def definition_hash(self) -> str:
        """Return a stable digest over every definition and parameter field."""

        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DEFAULT_FEATURES: tuple[FeatureDefinition, ...] = (
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
        name="rolling_annualized_volatility_20d",
        version=1,
        kind="rolling_annualized_volatility",
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


# Version 2 corrects missing-input provenance and return-interval alignment.
# Retain version 1 rows in storage; active reads select the revised identities.
DEFAULT_FEATURES = tuple(
    replace(
        definition,
        version=2,
        missing_value_policy=(
            "no filling; required null inputs precede warmup; momentum uses endpoints; "
            "correlation requires equal return start/end timestamps; constant windows undefined"
        ),
    )
    for definition in DEFAULT_FEATURES
)


class FeatureRegistry:
    """Read-only name-to-definition registry with duplicate protection."""

    def __init__(self, definitions: tuple[FeatureDefinition, ...] = DEFAULT_FEATURES) -> None:
        by_name = {definition.name: definition for definition in definitions}
        if len(by_name) != len(definitions):
            raise ValueError("feature names must be unique")
        for definition in definitions:
            expected_kind = {
                "rolling_correlation": "simple_return",
                "rolling_annualized_volatility": "log_return",
            }.get(definition.kind)
            if expected_kind is None:
                if definition.dependencies:
                    raise ValueError("price-only features cannot declare dependencies")
            elif len(definition.dependencies) != 1 or (
                definition.dependencies[0] not in by_name
                or by_name[definition.dependencies[0]].kind != expected_kind
            ):
                raise ValueError(
                    f"{definition.name} requires one registered {expected_kind} dependency"
                )

        resolved: dict[str, FeatureDefinition] = {}

        def resolve(name: str, visiting: frozenset[str] = frozenset()) -> FeatureDefinition:
            if name in resolved:
                return resolved[name]
            if name in visiting:
                raise ValueError("feature dependency cycle detected")
            definition = by_name[name]
            dependency_hashes = tuple(
                resolve(dependency, visiting | {name}).definition_hash
                for dependency in definition.dependencies
            )
            resolved[name] = replace(definition, dependency_hashes=dependency_hashes)
            return resolved[name]

        self._definitions: Mapping[str, FeatureDefinition] = MappingProxyType(
            {name: resolve(name) for name in by_name}
        )

    def get(self, name: str) -> FeatureDefinition:
        """Resolve one definition by its stable feature name."""

        try:
            return self._definitions[name]
        except KeyError:
            raise KeyError(f"unknown feature: {name}") from None

    def all(self) -> tuple[FeatureDefinition, ...]:
        """Return definitions in deterministic registration order."""

        return tuple(self._definitions.values())
