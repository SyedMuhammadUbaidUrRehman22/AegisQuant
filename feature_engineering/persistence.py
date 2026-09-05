"""Idempotent persistence and point-in-time reads for Stage 2 features."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Engine, RowMapping, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from feature_engineering.computation import FeatureObservation
from feature_engineering.registry import FeatureRegistry
from feature_engineering.tables import feature_values

DEFAULT_WRITE_BATCH_SIZE = 1_000
MAX_WRITE_BATCH_SIZE = 8_000  # Eight bound fields per row; stay below 65,535 PostgreSQL parameters.


def _batches[T](values: Sequence[T], size: int) -> tuple[Sequence[T], ...]:
    if size < 1:
        raise ValueError("batch size must be positive")
    return tuple(values[offset : offset + size] for offset in range(0, len(values), size))


class FeatureRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def materialize(
        self,
        observations: Sequence[FeatureObservation],
        *,
        batch_size: int = DEFAULT_WRITE_BATCH_SIZE,
    ) -> int:
        """Upsert one deterministic value per full feature identity."""

        if batch_size < 1 or batch_size > MAX_WRITE_BATCH_SIZE:
            raise ValueError(f"batch size must be positive and at most {MAX_WRITE_BATCH_SIZE}")
        if not observations:
            return 0
        identities = [
            (
                row.instrument_id,
                row.feature_name,
                row.feature_version,
                row.definition_hash,
                row.bar_end_at,
            )
            for row in observations
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate feature identities in one materialization")
        rows = tuple(
            {
                "instrument_id": row.instrument_id,
                "feature_name": row.feature_name,
                "feature_version": row.feature_version,
                "definition_hash": row.definition_hash,
                "bar_end_at": row.bar_end_at,
                "feature_as_of": row.feature_as_of,
                "value": row.value,
                "missing_reason": row.missing_reason,
            }
            for row in observations
        )
        affected = 0
        with self._engine.begin() as connection:
            for batch in _batches(rows, batch_size):
                insert_statement = pg_insert(feature_values).values(batch)
                statement = insert_statement.on_conflict_do_update(
                    index_elements=(
                        feature_values.c.instrument_id,
                        feature_values.c.feature_name,
                        feature_values.c.feature_version,
                        feature_values.c.definition_hash,
                        feature_values.c.bar_end_at,
                    ),
                    set_={
                        "feature_as_of": insert_statement.excluded.feature_as_of,
                        "value": insert_statement.excluded.value,
                        "missing_reason": insert_statement.excluded.missing_reason,
                        "updated_at": func.now(),
                    },
                    where=or_(
                        feature_values.c.feature_as_of.is_distinct_from(
                            insert_statement.excluded.feature_as_of
                        ),
                        feature_values.c.value.is_distinct_from(insert_statement.excluded.value),
                        feature_values.c.missing_reason.is_distinct_from(
                            insert_statement.excluded.missing_reason
                        ),
                    ),
                )
                # Psycopg may expose ``rowcount == -1`` for this statement shape. RETURNING is
                # authoritative and also distinguishes no-op conflicts filtered by the WHERE.
                result = connection.execute(statement.returning(feature_values.c.instrument_id))
                affected += len(result.all())
        return affected

    def read_as_of(
        self, as_of: datetime, *, registry: FeatureRegistry | None = None
    ) -> tuple[RowMapping, ...]:
        """Read only current registered definitions available by the requested instant."""

        if as_of != as_of or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        definitions = (registry or FeatureRegistry()).all()
        identities = [(item.name, item.version, item.definition_hash) for item in definitions]
        if not identities:
            return ()
        statement = (
            select(feature_values)
            .where(
                feature_values.c.bar_end_at <= as_of,
                feature_values.c.feature_as_of <= as_of,
                feature_values.c.feature_as_of <= feature_values.c.bar_end_at,
            )
            .order_by(
                feature_values.c.instrument_id,
                feature_values.c.bar_end_at,
                feature_values.c.feature_name,
            )
        )
        # Explicit disjunction avoids returning obsolete feature versions or hashes.
        statement = statement.where(
            or_(
                *(
                    tuple_(
                        feature_values.c.feature_name,
                        feature_values.c.feature_version,
                        feature_values.c.definition_hash,
                    )
                    == identity
                    for identity in identities
                )
            )
        )
        with self._engine.connect() as connection:
            return tuple(connection.execute(statement).mappings())
