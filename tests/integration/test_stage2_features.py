"""Canonical Stage 1 to persisted Stage 2 feature integration tests."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from data_pipeline.schema.tables import ingestion_runs, instruments, ohlcv_bars
from feature_engineering.persistence import FeatureRepository
from feature_engineering.registry import DEFAULT_FEATURES, FeatureRegistry
from feature_engineering.service import materialize_features, validate_features
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


@pytest.mark.database
def test_historical_replay_survives_future_canonical_mutations(clean_engine: Engine) -> None:
    end = _seed_bars(clean_engine, days=70)
    cutoff = end - timedelta(days=7)
    first = materialize_features(clean_engine, as_of=cutoff)
    before = FeatureRepository(clean_engine).read_as_of(cutoff)
    with clean_engine.begin() as connection:
        connection.execute(
            update(ohlcv_bars).where(ohlcv_bars.c.bar_end_at > cutoff).values(adjusted_close=999)
        )
    materialize_features(clean_engine, as_of=end)
    assert materialize_features(clean_engine, as_of=cutoff) == first
    assert FeatureRepository(clean_engine).read_as_of(cutoff) == before
    assert validate_features(clean_engine, as_of=cutoff).passed


@pytest.mark.database
def test_correction_updates_only_changed_values_and_preserves_created_at(
    clean_engine: Engine,
) -> None:
    cutoff = _seed_bars(clean_engine)
    first = materialize_features(clean_engine, as_of=cutoff)
    repository = FeatureRepository(clean_engine)
    sentinel = datetime(2000, 1, 1, tzinfo=UTC)
    with clean_engine.begin() as connection:
        connection.execute(update(feature_values).values(updated_at=sentinel))
    before = repository.read_as_of(cutoff)
    assert repository.materialize(first, batch_size=17) == 0
    assert repository.read_as_of(cutoff) == before
    with clean_engine.begin() as connection:
        connection.execute(
            update(ohlcv_bars)
            .where(ohlcv_bars.c.instrument_id == 2, ohlcv_bars.c.bar_end_at == cutoff)
            .values(adjusted_close=400)
        )
    assert not validate_features(clean_engine, as_of=cutoff).passed
    materialize_features(clean_engine, as_of=cutoff)
    after = repository.read_as_of(cutoff)
    changed = 0
    for old, new in zip(before, after, strict=True):
        assert old["created_at"] == new["created_at"]
        if old["value"] != new["value"]:
            changed += 1
            assert new["updated_at"] > sentinel
        else:
            assert old["updated_at"] == new["updated_at"]
    assert changed == 5
    assert validate_features(clean_engine, as_of=cutoff).passed


@pytest.mark.database
def test_failed_later_batch_rolls_back_earlier_batch(clean_engine: Engine) -> None:
    cutoff = _seed_bars(clean_engine)
    first = materialize_features(clean_engine, as_of=cutoff)
    valid = next(row for row in first if row.value is not None)
    repository = FeatureRepository(clean_engine)
    before = repository.read_as_of(cutoff)
    with pytest.raises(IntegrityError):
        repository.materialize(
            (replace(valid, value=0.125), replace(valid, instrument_id=999_999)), batch_size=1
        )
    assert repository.read_as_of(cutoff) == before


@pytest.mark.database
def test_definition_versions_coexist_and_reads_filter_full_identity(clean_engine: Engine) -> None:
    cutoff = _seed_bars(clean_engine)
    materialize_features(clean_engine, as_of=cutoff)
    repository = FeatureRepository(clean_engine)
    original = repository.read_as_of(cutoff)
    revised = FeatureRegistry(
        tuple(
            replace(definition, version=definition.version + 1) for definition in DEFAULT_FEATURES
        )
    )
    materialize_features(clean_engine, as_of=cutoff, registry=revised)
    assert repository.read_as_of(cutoff) == original
    assert len(repository.read_as_of(cutoff, registry=revised)) == len(original)
    with clean_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(feature_values)) == 2 * len(
            original
        )


@pytest.mark.database
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_database_rejects_nonfinite_values_even_when_bypassing_python(
    clean_engine: Engine, value: float
) -> None:
    cutoff = _seed_bars(clean_engine)
    materialize_features(clean_engine, as_of=cutoff)
    with pytest.raises(IntegrityError), clean_engine.begin() as connection:
        connection.execute(
            update(feature_values)
            .where(feature_values.c.missing_reason == "available")
            .values(value=value)
        )
