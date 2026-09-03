"""PostgreSQL persistence boundary for Stage 1 market data."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import Engine, RowMapping, func, insert, or_, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from data_pipeline.ingestion.errors import DatabaseIntegrityError
from data_pipeline.schema import (
    CONTRACT_VERSION,
    CanonicalBar,
    CorporateAction,
    Instrument,
    InstrumentSeed,
    PersistenceResult,
    QualityReport,
    RunStatus,
    SnapshotReference,
)
from data_pipeline.schema.tables import (
    corporate_actions,
    ingestion_runs,
    instrument_source_symbols,
    instruments,
    ohlcv_bars,
)

BAR_VALUE_COLUMNS = (
    "bar_end_at",
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
    "source_name",
    "contract_version",
    "quality_flags",
)
ACTION_VALUE_COLUMNS = ("action_value", "currency", "source_name", "active")


class MarketDataRepository:
    """Own transactional writes and read models for canonical market data."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def seed_instruments(self, seeds: Sequence[InstrumentSeed]) -> tuple[Instrument, ...]:
        """Idempotently seed approved reference metadata and provider mappings."""

        with self._engine.begin() as connection:
            for seed in seeds:
                instrument_statement = pg_insert(instruments).values(
                    canonical_symbol=seed.canonical_symbol,
                    name=seed.name,
                    asset_class=seed.asset_class.value,
                    venue_mic=seed.venue_mic,
                    currency=seed.currency,
                    timezone=seed.timezone,
                    calendar_code=seed.calendar_code,
                    valid_from=seed.valid_from,
                    valid_to=seed.valid_to,
                    active=seed.active,
                )
                upsert_statement = instrument_statement.on_conflict_do_update(
                    constraint="uq_instruments_canonical_symbol_venue_mic",
                    set_={
                        "name": instrument_statement.excluded.name,
                        "asset_class": instrument_statement.excluded.asset_class,
                        "currency": instrument_statement.excluded.currency,
                        "timezone": instrument_statement.excluded.timezone,
                        "calendar_code": instrument_statement.excluded.calendar_code,
                        "valid_from": instrument_statement.excluded.valid_from,
                        "valid_to": instrument_statement.excluded.valid_to,
                        "active": instrument_statement.excluded.active,
                        "updated_at": func.now(),
                    },
                    where=or_(
                        instruments.c.name.is_distinct_from(instrument_statement.excluded.name),
                        instruments.c.asset_class.is_distinct_from(
                            instrument_statement.excluded.asset_class
                        ),
                        instruments.c.currency.is_distinct_from(
                            instrument_statement.excluded.currency
                        ),
                        instruments.c.timezone.is_distinct_from(
                            instrument_statement.excluded.timezone
                        ),
                        instruments.c.calendar_code.is_distinct_from(
                            instrument_statement.excluded.calendar_code
                        ),
                        instruments.c.valid_from.is_distinct_from(
                            instrument_statement.excluded.valid_from
                        ),
                        instruments.c.valid_to.is_distinct_from(
                            instrument_statement.excluded.valid_to
                        ),
                        instruments.c.active.is_distinct_from(instrument_statement.excluded.active),
                    ),
                ).returning(instruments.c.instrument_id)
                instrument_id = connection.execute(upsert_statement).scalar_one_or_none()
                if instrument_id is None:
                    instrument_id = connection.scalar(
                        select(instruments.c.instrument_id).where(
                            instruments.c.canonical_symbol == seed.canonical_symbol,
                            instruments.c.venue_mic == seed.venue_mic,
                        )
                    )
                if instrument_id is None:
                    raise RuntimeError("Instrument upsert did not resolve an identity")
                source_statement = pg_insert(instrument_source_symbols).values(
                    instrument_id=instrument_id,
                    source_name=seed.source_name,
                    source_symbol=seed.source_symbol,
                )
                connection.execute(
                    source_statement.on_conflict_do_update(
                        constraint="uq_instrument_source_symbols_instrument_id_source_name",
                        set_={"source_symbol": source_statement.excluded.source_symbol},
                        where=instrument_source_symbols.c.source_symbol.is_distinct_from(
                            source_statement.excluded.source_symbol
                        ),
                    )
                )
        return tuple(self.get_instrument(seed.canonical_symbol) for seed in seeds)

    def get_instrument(self, canonical_symbol: str) -> Instrument:
        """Resolve one active canonical instrument and its source mapping."""

        statement = (
            select(
                instruments.c.instrument_id,
                instruments.c.canonical_symbol,
                instruments.c.name,
                instruments.c.asset_class,
                instruments.c.venue_mic,
                instruments.c.currency,
                instruments.c.timezone,
                instruments.c.calendar_code,
                instruments.c.valid_from,
                instruments.c.valid_to,
                instruments.c.active,
                instrument_source_symbols.c.source_name,
                instrument_source_symbols.c.source_symbol,
            )
            .join(
                instrument_source_symbols,
                instrument_source_symbols.c.instrument_id == instruments.c.instrument_id,
            )
            .where(
                instruments.c.canonical_symbol == canonical_symbol,
                instruments.c.active.is_(True),
            )
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one()
        return Instrument.model_validate(dict(row))

    def abandon_stale_runs(self, *, older_than_seconds: int) -> int:
        """Mark interrupted running audit records as abandoned."""

        threshold = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        with self._engine.begin() as connection:
            result = connection.execute(
                update(ingestion_runs)
                .where(
                    ingestion_runs.c.status == RunStatus.RUNNING.value,
                    ingestion_runs.c.started_at < threshold,
                )
                .values(
                    status=RunStatus.ABANDONED.value,
                    completed_at=func.now(),
                    error_type="InterruptedRun",
                    error_message="Run was still active beyond the configured stale threshold",
                    failure_phase="recovery",
                )
            )
        return result.rowcount

    def create_run(
        self,
        *,
        run_id: UUID,
        batch_id: UUID,
        instrument: Instrument,
        requested_start: date,
        requested_end: date,
        interval_code: str,
        adapter_version: str,
        provider_library_version: str,
        calendar_library_version: str,
        python_version: str,
        code_version: str,
        git_dirty: bool,
        request_parameters: dict[str, object],
    ) -> None:
        """Create a durable running audit record before provider access."""

        with self._engine.begin() as connection:
            connection.execute(
                insert(ingestion_runs).values(
                    run_id=run_id,
                    batch_id=batch_id,
                    instrument_id=instrument.instrument_id,
                    source_name=instrument.source_name,
                    source_symbol=instrument.source_symbol,
                    interval_code=interval_code,
                    requested_start=requested_start,
                    requested_end=requested_end,
                    status=RunStatus.RUNNING.value,
                    started_at=datetime.now(UTC),
                    adapter_version=adapter_version,
                    provider_library_version=provider_library_version,
                    calendar_library_version=calendar_library_version,
                    contract_version=CONTRACT_VERSION,
                    python_version=python_version,
                    code_version=code_version,
                    git_dirty=git_dirty,
                    request_parameters=request_parameters,
                )
            )

    def mark_failed(
        self,
        run_id: UUID,
        *,
        error_type: str,
        error_message: str,
        failure_phase: str,
        rows_received: int = 0,
        rows_accepted: int = 0,
        snapshot: SnapshotReference | None = None,
        normalized_sha256: str | None = None,
        report: QualityReport | None = None,
    ) -> None:
        """Durably close a failed run after its work transaction rolls back."""

        values: dict[str, object] = {
            "status": RunStatus.FAILED.value,
            "completed_at": datetime.now(UTC),
            "error_type": error_type[:128],
            "error_message": error_message[:4000],
            "failure_phase": failure_phase[:32],
            "rows_received": rows_received,
            "rows_accepted": rows_accepted,
            "normalized_sha256": normalized_sha256,
            "warning_count": 0 if report is None else report.warning_count,
            "critical_count": 0 if report is None else report.critical_count,
        }
        if snapshot is not None:
            values.update(
                snapshot_path=snapshot.relative_path,
                snapshot_sha256=snapshot.sha256,
            )
        with self._engine.begin() as connection:
            connection.execute(
                update(ingestion_runs).where(ingestion_runs.c.run_id == run_id).values(**values)
            )

    def persist_success(
        self,
        *,
        run_id: UUID,
        instrument: Instrument,
        bars: Sequence[CanonicalBar],
        actions: Sequence[CorporateAction],
        rows_received: int,
        snapshot: SnapshotReference,
        normalized_sha256: str,
        report: QualityReport,
    ) -> PersistenceResult:
        """Atomically persist canonical values and close the audit record."""

        try:
            with self._engine.begin() as connection:
                lock_key = f"ohlcv:{instrument.instrument_id}:1d"
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
                    {"lock_key": lock_key},
                )
                inserted, updated, unchanged = self._persist_bars(connection, run_id, bars)
                actions_inserted, actions_updated, actions_unchanged = self._persist_actions(
                    connection,
                    run_id,
                    instrument,
                    actions,
                    requested_start=report.requested_start,
                    requested_end=report.requested_end,
                )
                actual_dates = [bar.session_date for bar in bars]
                connection.execute(
                    update(ingestion_runs)
                    .where(ingestion_runs.c.run_id == run_id)
                    .values(
                        status=RunStatus.SUCCEEDED.value,
                        completed_at=func.now(),
                        actual_start=min(actual_dates) if actual_dates else None,
                        actual_end=max(actual_dates) if actual_dates else None,
                        rows_received=rows_received,
                        rows_accepted=len(bars),
                        rows_inserted=inserted,
                        rows_updated=updated,
                        rows_unchanged=unchanged,
                        warning_count=report.warning_count + updated + actions_updated,
                        critical_count=report.critical_count,
                        snapshot_path=snapshot.relative_path,
                        snapshot_sha256=snapshot.sha256,
                        normalized_sha256=normalized_sha256,
                    )
                )
        except IntegrityError as error:
            raise DatabaseIntegrityError(str(error.orig)) from error
        return PersistenceResult(
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            actions_inserted=actions_inserted,
            actions_updated=actions_updated,
            actions_unchanged=actions_unchanged,
        )

    @staticmethod
    def _persist_bars(
        connection: object, run_id: UUID, bars: Sequence[CanonicalBar]
    ) -> tuple[int, int, int]:
        from sqlalchemy.engine import Connection

        if not isinstance(connection, Connection):
            raise TypeError("connection must be a SQLAlchemy Connection")
        if not bars:
            return 0, 0, 0
        keys = [(bar.instrument_id, bar.interval_code.value, bar.bar_start_at) for bar in bars]
        existing_rows = connection.execute(
            select(ohlcv_bars).where(
                tuple_(
                    ohlcv_bars.c.instrument_id,
                    ohlcv_bars.c.interval_code,
                    ohlcv_bars.c.bar_start_at,
                ).in_(keys)
            )
        ).mappings()
        existing = {
            (row["instrument_id"], row["interval_code"], row["bar_start_at"]): row
            for row in existing_rows
        }
        new_values: list[dict[str, object]] = []
        changed: list[tuple[CanonicalBar, RowMapping]] = []
        unchanged = 0
        for bar in bars:
            values = _bar_values(bar, run_id)
            key = (bar.instrument_id, bar.interval_code.value, bar.bar_start_at)
            current = existing.get(key)
            if current is None:
                new_values.append(values)
            elif _matches(current, values, BAR_VALUE_COLUMNS):
                unchanged += 1
            else:
                changed.append((bar, current))
        if new_values:
            connection.execute(insert(ohlcv_bars), new_values)
        for bar, _ in changed:
            values = _bar_values(bar, run_id)
            values["quality_flags"] = sorted(set(bar.quality_flags).union({"source_correction"}))
            connection.execute(
                update(ohlcv_bars)
                .where(
                    ohlcv_bars.c.instrument_id == bar.instrument_id,
                    ohlcv_bars.c.interval_code == bar.interval_code.value,
                    ohlcv_bars.c.bar_start_at == bar.bar_start_at,
                )
                .values(**values, updated_at=func.now())
            )
        return len(new_values), len(changed), unchanged

    @staticmethod
    def _persist_actions(
        connection: object,
        run_id: UUID,
        instrument: Instrument,
        actions: Sequence[CorporateAction],
        *,
        requested_start: date,
        requested_end: date,
    ) -> tuple[int, int, int]:
        from sqlalchemy.engine import Connection

        if not isinstance(connection, Connection):
            raise TypeError("connection must be a SQLAlchemy Connection")
        keys = [
            (action.instrument_id, action.effective_date, action.action_type.value)
            for action in actions
        ]
        existing_rows = connection.execute(
            select(corporate_actions).where(
                corporate_actions.c.instrument_id == instrument.instrument_id,
                corporate_actions.c.source_name == instrument.source_name,
                corporate_actions.c.effective_date >= requested_start,
                corporate_actions.c.effective_date < requested_end,
            )
        ).mappings()
        existing = {
            (row["instrument_id"], row["effective_date"], row["action_type"]): row
            for row in existing_rows
        }
        new_values: list[dict[str, object]] = []
        changed: list[CorporateAction] = []
        removed: list[RowMapping] = []
        unchanged = 0
        for action in actions:
            values = _action_values(action, run_id)
            key = (action.instrument_id, action.effective_date, action.action_type.value)
            current = existing.get(key)
            if current is None:
                new_values.append(values)
            elif _matches(current, values, ACTION_VALUE_COLUMNS):
                unchanged += 1
            else:
                changed.append(action)
        incoming_keys = set(keys)
        for key, current in existing.items():
            if key not in incoming_keys and current["active"]:
                removed.append(current)
        if new_values:
            connection.execute(insert(corporate_actions), new_values)
        for action in changed:
            connection.execute(
                update(corporate_actions)
                .where(
                    corporate_actions.c.instrument_id == action.instrument_id,
                    corporate_actions.c.effective_date == action.effective_date,
                    corporate_actions.c.action_type == action.action_type.value,
                )
                .values(**_action_values(action, run_id), updated_at=func.now())
            )
        for current in removed:
            connection.execute(
                update(corporate_actions)
                .where(
                    corporate_actions.c.instrument_id == current["instrument_id"],
                    corporate_actions.c.effective_date == current["effective_date"],
                    corporate_actions.c.action_type == current["action_type"],
                )
                .values(active=False, ingestion_run_id=run_id, updated_at=func.now())
            )
        return len(new_values), len(changed) + len(removed), unchanged

    def latest_session(self, instrument_id: int, interval_code: str = "1d") -> date | None:
        """Return the latest persisted session for incremental range calculation."""

        with self._engine.connect() as connection:
            value = connection.execute(
                select(func.max(ohlcv_bars.c.session_date)).where(
                    ohlcv_bars.c.instrument_id == instrument_id,
                    ohlcv_bars.c.interval_code == interval_code,
                )
            ).scalar_one()
        return cast(date | None, value)

    def bars_for_symbol(
        self, canonical_symbol: str, start_date: date, end_date: date
    ) -> tuple[RowMapping, ...]:
        """Retrieve canonical bars in chronological order for inspection."""

        statement = (
            select(ohlcv_bars)
            .join(instruments, instruments.c.instrument_id == ohlcv_bars.c.instrument_id)
            .where(
                instruments.c.canonical_symbol == canonical_symbol,
                ohlcv_bars.c.session_date >= start_date,
                ohlcv_bars.c.session_date < end_date,
            )
            .order_by(ohlcv_bars.c.bar_start_at)
        )
        with self._engine.connect() as connection:
            return tuple(connection.execute(statement).mappings())

    def integrity_summary(self) -> dict[str, int]:
        """Return Stage 1 row counts and duplicate-key diagnostics."""

        duplicate_query = text(
            "SELECT count(*) FROM ("
            "SELECT instrument_id, interval_code, bar_start_at "
            "FROM ohlcv_bars GROUP BY instrument_id, interval_code, bar_start_at "
            "HAVING count(*) > 1) duplicate_keys"
        )
        with self._engine.connect() as connection:
            return {
                "instruments": connection.scalar(select(func.count()).select_from(instruments))
                or 0,
                "source_symbols": connection.scalar(
                    select(func.count()).select_from(instrument_source_symbols)
                )
                or 0,
                "bars": connection.scalar(select(func.count()).select_from(ohlcv_bars)) or 0,
                "corporate_actions": connection.scalar(
                    select(func.count()).select_from(corporate_actions)
                )
                or 0,
                "ingestion_runs": connection.scalar(
                    select(func.count()).select_from(ingestion_runs)
                )
                or 0,
                "duplicate_bar_keys": connection.scalar(duplicate_query) or 0,
            }


def _bar_values(bar: CanonicalBar, run_id: UUID) -> dict[str, object]:
    return {
        "instrument_id": bar.instrument_id,
        "interval_code": bar.interval_code.value,
        "bar_start_at": bar.bar_start_at,
        "bar_end_at": bar.bar_end_at,
        "session_date": bar.session_date,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "adjusted_close": bar.adjusted_close,
        "volume": bar.volume,
        "source_name": bar.source_name,
        "ingestion_run_id": run_id,
        "contract_version": bar.contract_version,
        "quality_flags": list(bar.quality_flags),
    }


def _action_values(action: CorporateAction, run_id: UUID) -> dict[str, object]:
    return {
        "instrument_id": action.instrument_id,
        "effective_date": action.effective_date,
        "action_type": action.action_type.value,
        "action_value": action.action_value,
        "currency": action.currency,
        "source_name": action.source_name,
        "active": action.active,
        "ingestion_run_id": run_id,
    }


def _matches(current: RowMapping, proposed: dict[str, object], columns: Iterable[str]) -> bool:
    for column in columns:
        current_value = current[column]
        proposed_value = proposed[column]
        if isinstance(current_value, list) and isinstance(proposed_value, list):
            current_flags = set(current_value)
            proposed_flags = set(proposed_value)
            if column == "quality_flags":
                current_flags.discard("source_correction")
                proposed_flags.discard("source_correction")
            if current_flags != proposed_flags:
                return False
        elif isinstance(current_value, Decimal) and isinstance(proposed_value, Decimal):
            if current_value != proposed_value:
                return False
        elif current_value != proposed_value:
            return False
    return True
