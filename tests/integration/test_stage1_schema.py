"""Integration checks for the fresh Stage 1 TimescaleDB migration."""

import pytest
from sqlalchemy import Engine, text


@pytest.mark.database
def test_fresh_migration_creates_hypertable_constraints_and_indexes(
    migrated_engine: Engine,
) -> None:
    with migrated_engine.connect() as connection:
        hypertable = connection.scalar(
            text(
                "SELECT count(*) FROM timescaledb_information.hypertables "
                "WHERE hypertable_name = 'ohlcv_bars'"
            )
        )
        constraints = set(
            connection.scalars(
                text(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_schema = 'public' AND table_name = 'ohlcv_bars'"
                )
            )
        )
        indexes = set(
            connection.scalars(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'ohlcv_bars'")
            )
        )
        index_definition = connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'ohlcv_bars' "
                "AND indexname = 'ix_ohlcv_bars_instrument_session_date'"
            )
        )

    assert hypertable == 1
    assert "pk_ohlcv_bars" in constraints
    assert "ck_ohlcv_bars_prices_positive" in constraints
    assert "ix_ohlcv_bars_interval_time_instrument" in indexes
    assert "ix_ohlcv_bars_instrument_session_date" in indexes
    assert index_definition is not None
    assert "(instrument_id, session_date)" in index_definition
