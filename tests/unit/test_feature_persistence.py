"""SQL contract tests for feature persistence without a live database."""

from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql

from feature_engineering.persistence import FeatureRepository
from feature_engineering.tables import feature_values


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
