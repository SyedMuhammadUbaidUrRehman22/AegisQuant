"""Stage 2 orchestration without computation or SQL business logic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Engine

from feature_engineering.access import CanonicalFeatureInput
from feature_engineering.computation import FeatureObservation, compute_features
from feature_engineering.persistence import FeatureRepository
from feature_engineering.registry import FeatureRegistry


def materialize_features(
    engine: Engine, *, as_of: datetime, registry: FeatureRegistry | None = None
) -> tuple[FeatureObservation, ...]:
    selected_registry = registry or FeatureRegistry()
    bars = CanonicalFeatureInput(engine).bars_as_of(as_of)
    observations = compute_features(bars, as_of=as_of, registry=selected_registry)
    FeatureRepository(engine).materialize(observations)
    return observations
