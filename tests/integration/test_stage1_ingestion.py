"""Database-backed Stage 1 persistence, idempotency, and recovery tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from data_pipeline.ingestion.provider import HistoricalProvider
from data_pipeline.ingestion.repository import MarketDataRepository
from data_pipeline.ingestion.service import IngestionService
from data_pipeline.ingestion.snapshots import SnapshotStore
from data_pipeline.schema import IngestionRequest, Instrument, RunStatus, SourceBatch
from data_pipeline.universe import STAGE_1_UNIVERSE
from tests.factories import source_batch, source_row


class StaticProvider(HistoricalProvider):
    adapter_version = "test-1"
    library_version = "test-1"

    def __init__(self, batches: dict[str, SourceBatch]) -> None:
        self.batches = batches

    def fetch(self, instrument: Instrument, request: IngestionRequest) -> SourceBatch:
        return self.batches[instrument.canonical_symbol].model_copy(
            update={
                "requested_start": request.start_date,
                "requested_end": request.end_date,
            }
        )


def _service(engine: Engine, provider: HistoricalProvider, snapshot_root: Path) -> IngestionService:
    return IngestionService(
        repository=MarketDataRepository(engine),
        provider=provider,
        snapshots=SnapshotStore(snapshot_root),
        max_attempts=1,
        backoff_base_seconds=0.01,
        backoff_cap_seconds=0.01,
        price_jump_fraction=0.25,
        repeated_ohlc_sessions=3,
        volume_spike_multiple=20,
        volume_window_sessions=60,
    )


def _three_rows() -> tuple[dict[str, str | None], ...]:
    return tuple(source_row(day) for day in (date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)))


@pytest.mark.database
def test_same_and_overlapping_loads_are_idempotent_and_corrections_explicit(
    clean_engine: Engine, tmp_path: Path
) -> None:
    repository = MarketDataRepository(clean_engine)
    repository.seed_instruments(STAGE_1_UNIVERSE)
    initial_rows = list(_three_rows())
    initial_rows[0] = source_row(date(2024, 1, 2), dividend="0.50")
    provider = StaticProvider({"SPY": source_batch(tuple(initial_rows))})
    service = _service(clean_engine, provider, tmp_path)
    request = IngestionRequest(
        canonical_symbol="SPY", start_date=date(2024, 1, 2), end_date=date(2024, 1, 5)
    )

    first = service.ingest_one(request, as_of=datetime(2024, 1, 6, tzinfo=UTC))
    original = repository.bars_for_symbol("SPY", date(2024, 1, 2), date(2024, 1, 5))
    second = service.ingest_one(request, as_of=datetime(2024, 1, 6, tzinfo=UTC))
    replayed = repository.bars_for_symbol("SPY", date(2024, 1, 2), date(2024, 1, 5))

    overlap_rows = (
        _three_rows()[1],
        _three_rows()[2],
        source_row(date(2024, 1, 5)),
    )
    provider.batches["SPY"] = source_batch(
        overlap_rows, start=date(2024, 1, 3), end=date(2024, 1, 6)
    )
    overlap = service.ingest_one(
        IngestionRequest(
            canonical_symbol="SPY", start_date=date(2024, 1, 3), end_date=date(2024, 1, 6)
        ),
        as_of=datetime(2024, 1, 7, tzinfo=UTC),
    )

    corrected_rows = list(_three_rows())
    corrected_rows[1] = source_row(
        date(2024, 1, 3), open_price="100", high="103", low="99", close="102"
    )
    provider.batches["SPY"] = source_batch(tuple(corrected_rows))
    correction = service.ingest_one(request, as_of=datetime(2024, 1, 6, tzinfo=UTC))
    corrected = repository.bars_for_symbol("SPY", date(2024, 1, 2), date(2024, 1, 5))
    final_replay = service.ingest_one(request, as_of=datetime(2024, 1, 6, tzinfo=UTC))

    assert first.persistence is not None and first.persistence.inserted == 3
    assert second.persistence is not None and second.persistence.unchanged == 3
    assert overlap.persistence is not None
    assert (overlap.persistence.inserted, overlap.persistence.unchanged) == (1, 2)
    assert [row["updated_at"] for row in original] == [row["updated_at"] for row in replayed]
    assert correction.persistence is not None and correction.persistence.updated == 1
    assert correction.persistence.actions_updated == 1
    assert "source_correction" in corrected[1]["quality_flags"]
    assert final_replay.persistence is not None and final_replay.persistence.unchanged == 3
    assert repository.integrity_summary()["duplicate_bar_keys"] == 0
    with clean_engine.connect() as connection:
        action_active = connection.scalar(text("SELECT active FROM corporate_actions"))
    assert action_active is False


@pytest.mark.database
def test_failed_quality_transaction_can_retry_without_partial_rows(
    clean_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = MarketDataRepository(clean_engine)
    repository.seed_instruments(STAGE_1_UNIVERSE)
    provider = StaticProvider({"SPY": source_batch(_three_rows())})
    service = _service(clean_engine, provider, tmp_path)
    request = IngestionRequest(
        canonical_symbol="SPY", start_date=date(2024, 1, 2), end_date=date(2024, 1, 5)
    )

    def fail_after_bars(*args: object, **kwargs: object) -> tuple[int, int, int]:
        raise RuntimeError("injected transaction failure")

    with monkeypatch.context() as context:
        context.setattr(MarketDataRepository, "_persist_actions", staticmethod(fail_after_bars))
        failed = service.ingest_one(request, as_of=datetime(2024, 1, 6, tzinfo=UTC))
    assert failed.status is RunStatus.FAILED
    assert repository.integrity_summary()["bars"] == 0

    succeeded = service.ingest_one(request, as_of=datetime(2024, 1, 6, tzinfo=UTC))

    assert succeeded.status is RunStatus.SUCCEEDED
    assert repository.integrity_summary()["bars"] == 3
    with clean_engine.connect() as connection:
        statuses = tuple(
            connection.scalars(text("SELECT status FROM ingestion_runs ORDER BY started_at"))
        )
    assert statuses == ("failed", "succeeded")


@pytest.mark.database
def test_concurrent_same_instrument_ingestion_serializes_without_duplicates(
    clean_engine: Engine, tmp_path: Path
) -> None:
    repository = MarketDataRepository(clean_engine)
    repository.seed_instruments(STAGE_1_UNIVERSE)
    provider = StaticProvider({"SPY": source_batch(_three_rows())})
    request = IngestionRequest(
        canonical_symbol="SPY", start_date=date(2024, 1, 2), end_date=date(2024, 1, 5)
    )

    def run() -> object:
        return _service(clean_engine, provider, tmp_path).ingest_one(
            request, as_of=datetime(2024, 1, 6, tzinfo=UTC)
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: run(), range(2)))

    assert all(result.status is RunStatus.SUCCEEDED for result in results)  # type: ignore[attr-defined]
    assert sorted(result.persistence.inserted for result in results) == [0, 3]  # type: ignore[attr-defined, union-attr]
    assert repository.integrity_summary()["bars"] == 3
    assert repository.integrity_summary()["duplicate_bar_keys"] == 0
