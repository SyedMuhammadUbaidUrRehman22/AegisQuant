"""Stage 2 orchestration without computation or SQL business logic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Engine

from feature_engineering.access import CanonicalFeatureInput
from feature_engineering.computation import FeatureObservation, compute_features
from feature_engineering.persistence import FeatureRepository
from feature_engineering.registry import FeatureRegistry
from feature_engineering.validation import FeatureValidation, validate_materialization


def materialize_features(
    engine: Engine, *, as_of: datetime, registry: FeatureRegistry | None = None
) -> tuple[FeatureObservation, ...]:
    """Read canonical bars, compute registered features, and persist them atomically."""

    selected_registry = registry or FeatureRegistry()
    bars = CanonicalFeatureInput(engine).bars_as_of(as_of)
    observations = compute_features(bars, as_of=as_of, registry=selected_registry)
    FeatureRepository(engine).materialize(observations)
    return observations


def validate_features(
    engine: Engine, *, as_of: datetime, registry: FeatureRegistry | None = None
) -> FeatureValidation:
    """Audit stored coverage and replay without modifying canonical or feature data."""

    selected_registry = registry or FeatureRegistry()
    bars = CanonicalFeatureInput(engine).bars_as_of(as_of)
    expected = compute_features(bars, as_of=as_of, registry=selected_registry)
    stored = FeatureRepository(engine).read_as_of(as_of, registry=selected_registry)
    return validate_materialization(
        expected, [{str(key): value for key, value in row.items()} for row in stored]
    )
