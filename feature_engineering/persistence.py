"""Idempotent persistence and point-in-time reads for Stage 2 features."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Engine, RowMapping, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from feature_engineering.computation import FeatureObservation
from feature_engineering.registry import FeatureRegistry
from feature_engineering.tables import feature_values


class FeatureRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def materialize(self, observations: Sequence[FeatureObservation]) -> int:
        """Upsert one deterministic value per full feature identity."""

        if not observations:
            return 0
        rows = [
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
        ]
        statement = pg_insert(feature_values).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=(
                feature_values.c.instrument_id,
                feature_values.c.feature_name,
                feature_values.c.feature_version,
                feature_values.c.definition_hash,
                feature_values.c.bar_end_at,
            ),
            set_={
                "feature_as_of": statement.excluded.feature_as_of,
                "value": statement.excluded.value,
                "missing_reason": statement.excluded.missing_reason,
                "updated_at": func.now(),
            },
        )
        with self._engine.begin() as connection:
            result = connection.execute(statement)
        return result.rowcount

    def read_as_of(
        self, as_of: datetime, *, registry: FeatureRegistry | None = None
    ) -> tuple[RowMapping, ...]:
        """Read only current registered definitions available by the requested instant."""

        if as_of.tzinfo is None:
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
