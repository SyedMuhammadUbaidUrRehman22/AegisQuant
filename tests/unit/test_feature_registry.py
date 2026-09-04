"""Feature registry contract and versioning tests."""

from dataclasses import replace

import pytest

from feature_engineering.registry import DEFAULT_FEATURES, FeatureRegistry


def test_default_registry_is_complete_and_point_in_time_safe() -> None:
    registry = FeatureRegistry()

    assert {item.name for item in registry.all()} == {
        "adjusted_simple_return_1d",
        "adjusted_log_return_1d",
        "rolling_annualized_volatility_20d",
        "momentum_20d",
        "rolling_correlation_spy_60d",
    }
    assert all(item.point_in_time_safe for item in registry.all())
    assert all(
        item.current_bar_included and not item.target_period_included for item in registry.all()
    )


def test_definition_hash_is_deterministic_and_tracks_semantics() -> None:
    definition = DEFAULT_FEATURES[0]

    assert definition.definition_hash == definition.definition_hash
    assert replace(definition, version=2).definition_hash != definition.definition_hash
    assert replace(definition, description="changed").definition_hash != definition.definition_hash


def test_registry_rejects_duplicate_names_and_unknown_lookup() -> None:
    with pytest.raises(ValueError, match="unique"):
        FeatureRegistry((DEFAULT_FEATURES[0], DEFAULT_FEATURES[0]))
    with pytest.raises(KeyError, match="unknown feature"):
        FeatureRegistry().get("absent")
