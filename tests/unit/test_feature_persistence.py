"""SQL contract tests for feature persistence without a live database."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from feature_engineering import compute_features
from feature_engineering.persistence import FeatureRepository, _batches
from feature_engineering.tables import feature_values
from tests.factories import feature_bars


def test_feature_table_identity_and_point_in_time_constraint() -> None:
    assert [column.name for column in feature_values.primary_key.columns] == [
        "instrument_id",
        "feature_name",
        "feature_version",
        "definition_hash",
        "bar_end_at",
    ]
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in feature_values.constraints
        if constraint.name and hasattr(constraint, "sqltext")
    }
    assert "feature_as_of <= bar_end_at" in constraints["ck_feature_values_point_in_time"]


def test_write_batches_are_bounded_and_validate_size() -> None:
    assert _batches(tuple(range(5)), 2) == ((0, 1), (2, 3), (4,))
    with pytest.raises(ValueError, match="positive"):
        _batches((1,), 0)


def test_duplicate_identities_fail_before_writing_even_across_batches() -> None:
    bars = feature_bars(2)
    observation = compute_features(bars, as_of=bars.bar_end_at.max())[0]
    engine = Mock()
    with pytest.raises(ValueError, match="duplicate"):
        FeatureRepository(engine).materialize((observation, observation), batch_size=1)
    engine.begin.assert_not_called()


def test_oversized_batch_cannot_exceed_postgresql_parameter_limit() -> None:
    with pytest.raises(ValueError, match="at most"):
        FeatureRepository(Mock()).materialize((), batch_size=8001)


def test_materialization_uses_one_transaction_for_bounded_statements() -> None:
    bars = feature_bars(2)
    observations = compute_features(bars, as_of=bars.bar_end_at.max())
    from unittest.mock import MagicMock

    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 1
    FeatureRepository(engine).materialize(observations, batch_size=3)
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 7
    for call in connection.execute.call_args_list:
        compiled = call.args[0].compile(dialect=postgresql.dialect())
        assert len(compiled.params) <= 3 * 8
        assert "IS DISTINCT FROM" in str(compiled)


def test_read_as_of_query_contains_both_temporal_guards() -> None:
    class CapturingConnection:
        statement = None

        def __enter__(self) -> "CapturingConnection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, statement: object) -> object:
            self.statement = statement

            class Empty:
                def mappings(self) -> tuple[object, ...]:
                    return ()

            return Empty()

    connection = CapturingConnection()

    class EngineStub:
        def connect(self) -> CapturingConnection:
            return connection

    repository = FeatureRepository(EngineStub())  # type: ignore[arg-type]
    repository.read_as_of(datetime(2024, 1, 2, tzinfo=UTC))
    sql = str(connection.statement.compile(dialect=postgresql.dialect()))  # type: ignore[union-attr]

    assert "feature_values.bar_end_at <=" in sql
    assert "feature_values.feature_as_of <=" in sql
