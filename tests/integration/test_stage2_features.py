"""Canonical Stage 1 to persisted Stage 2 feature integration tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, insert, select

from data_pipeline.schema.tables import ingestion_runs, instruments, ohlcv_bars
from feature_engineering.persistence import FeatureRepository
from feature_engineering.service import materialize_features
from feature_engineering.tables import feature_values


def _seed_bars(engine: Engine, days: int = 65) -> datetime:
    start = datetime(2024, 1, 1, 14, 30, tzinfo=UTC)
    with engine.begin() as connection:
        ids: dict[str, int] = {}
        for symbol in ("SPY", "QQQ"):
            ids[symbol] = int(
                connection.scalar(
                    insert(instruments)
                    .values(
                        canonical_symbol=symbol,
                        name=symbol,
                        asset_class="etf",
                        venue_mic="ARCX",
                        currency="USD",
                        timezone="America/New_York",
                        calendar_code="XNYS",
                    )
                    .returning(instruments.c.instrument_id)
                )
            )
            run_id = uuid4()
            connection.execute(
                insert(ingestion_runs).values(
                    run_id=run_id,
                    batch_id=uuid4(),
                    instrument_id=ids[symbol],
                    source_name="fixture",
                    source_symbol=symbol,
                    interval_code="1d",
                    requested_start=date(2024, 1, 1),
                    requested_end=date(2024, 4, 1),
                    status="succeeded",
                    started_at=start,
                    completed_at=start,
                    adapter_version="test",
                    provider_library_version="test",
                    calendar_library_version="test",
                    contract_version=1,
                    python_version="3.12",
                    code_version="test",
                    git_dirty=False,
                    request_parameters={},
                )
            )
            connection.execute(
                insert(ohlcv_bars),
                [
                    {
                        "instrument_id": ids[symbol],
                        "interval_code": "1d",
                        "bar_start_at": start + timedelta(days=offset),
                        "bar_end_at": start + timedelta(days=offset, hours=6, minutes=30),
                        "session_date": (start + timedelta(days=offset)).date(),
                        "open": Decimal("100"),
                        "high": Decimal("200"),
                        "low": Decimal("90"),
                        "close": Decimal(str(100 + offset)),
                        "adjusted_close": Decimal(
                            str((100 + offset) * (1 if symbol == "SPY" else 2))
                        ),
                        "volume": 1_000_000 + offset,
                        "source_name": "fixture",
                        "ingestion_run_id": run_id,
                        "contract_version": 1,
                    }
                    for offset in range(days)
                ],
            )
    return start + timedelta(days=days - 1, hours=6, minutes=30)


@pytest.mark.database
def test_canonical_to_materialized_features_is_idempotent_and_point_in_time_correct(
    clean_engine: Engine,
) -> None:
    cutoff = _seed_bars(clean_engine)
    first = materialize_features(clean_engine, as_of=cutoff)
    stored = FeatureRepository(clean_engine).read_as_of(cutoff)
    second = materialize_features(clean_engine, as_of=cutoff)

    assert len(first) == len(second) == len(stored) == 65 * 2 * 5
    assert first == second
    assert all(row["feature_as_of"] <= row["bar_end_at"] <= cutoff for row in stored)
    expected = {
        (row.instrument_id, row.feature_name, row.definition_hash, row.bar_end_at): (
            row.value,
            row.missing_reason,
        )
        for row in first
    }
    actual = {
        (row["instrument_id"], row["feature_name"], row["definition_hash"], row["bar_end_at"]): (
            row["value"],
            row["missing_reason"],
        )
        for row in stored
    }
    assert actual == expected
    with clean_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(feature_values)) == len(first)
