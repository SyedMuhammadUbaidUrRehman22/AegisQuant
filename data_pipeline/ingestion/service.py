"""Application service orchestrating auditable Stage 1 ingestion runs."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

from data_pipeline.ingestion.calendars import SessionCalendar
from data_pipeline.ingestion.errors import DataQualityError, classify_error
from data_pipeline.ingestion.normalization import normalize_source_batch
from data_pipeline.ingestion.provider import HistoricalProvider
from data_pipeline.ingestion.repository import MarketDataRepository
from data_pipeline.ingestion.retry import retry_call
from data_pipeline.ingestion.snapshots import SnapshotStore
from data_pipeline.quality_checks import validate_batch
from data_pipeline.schema import (
    BatchIngestionResult,
    IngestionRequest,
    IngestionResult,
    QualityReport,
    RunStatus,
    SnapshotReference,
)

_SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|token|secret|api[_-]?key)(\s*[=:]\s*)([^\s,;&]+)"
)


def _safe_error_message(error: BaseException) -> str:
    """Bound error messages and redact common credential-shaped values."""

    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", str(error))[:4000]


def _source_digest(root: Path | None = None) -> str:
    """Hash ingestion runtime sources when repository metadata is unavailable."""

    resolved_root = root or Path(__file__).resolve().parents[2]
    candidates = [resolved_root / "pyproject.toml", resolved_root / "constraints.lock"]
    for directory in ("config", "data_pipeline"):
        candidates.extend((resolved_root / directory).rglob("*.py"))
        candidates.extend((resolved_root / directory).rglob("*.yaml"))
    digest = hashlib.sha256()
    for path in sorted({item for item in candidates if item.is_file()}):
        digest.update(path.relative_to(resolved_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _code_state() -> tuple[str, bool]:
    """Return a Git revision or deterministic runtime-source digest and dirty state."""

    try:
        revision = subprocess.run(
            ["git", "-c", "safe.directory=*", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-c", "safe.directory=*", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError):
        return f"source-sha256:{_source_digest()}", True
    if dirty:
        return f"source-sha256:{_source_digest()}", True
    return f"git:{revision[:40]}", False


class IngestionService:
    """Coordinate provider, snapshot, quality, and transaction boundaries."""

    def __init__(
        self,
        *,
        repository: MarketDataRepository,
        provider: HistoricalProvider,
        snapshots: SnapshotStore,
        max_attempts: int,
        backoff_base_seconds: float,
        backoff_cap_seconds: float,
        price_jump_fraction: float,
        repeated_ohlc_sessions: int,
        volume_spike_multiple: float,
        volume_window_sessions: int,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._snapshots = snapshots
        self._max_attempts = max_attempts
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_cap_seconds = backoff_cap_seconds
        self._price_jump_fraction = price_jump_fraction
        self._repeated_ohlc_sessions = repeated_ohlc_sessions
        self._volume_spike_multiple = volume_spike_multiple
        self._volume_window_sessions = volume_window_sessions

    def ingest_batch(
        self,
        requests: Sequence[IngestionRequest],
        *,
        batch_id: UUID | None = None,
        as_of: datetime | None = None,
    ) -> BatchIngestionResult:
        """Run instruments independently so one failure cannot corrupt peers."""

        resolved_batch_id = batch_id or uuid4()
        results = tuple(
            self.ingest_one(request, batch_id=resolved_batch_id, as_of=as_of)
            for request in requests
        )
        return BatchIngestionResult(batch_id=resolved_batch_id, results=results)

    def ingest_one(
        self,
        request: IngestionRequest,
        *,
        batch_id: UUID | None = None,
        as_of: datetime | None = None,
    ) -> IngestionResult:
        """Execute one fully audited ingestion attempt."""

        resolved_batch_id = batch_id or uuid4()
        run_id = uuid4()
        now = (as_of or datetime.now(UTC)).astimezone(UTC)
        instrument = self._repository.get_instrument(request.canonical_symbol)
        calendar = SessionCalendar(instrument.calendar_code)
        code_version, git_dirty = _code_state()
        request_parameters: dict[str, object] = {
            "canonical_symbol": request.canonical_symbol,
            "source_symbol": instrument.source_symbol,
            "start": request.start_date.isoformat(),
            "end": request.end_date.isoformat(),
            "end_exclusive": True,
            "interval": request.interval_code.value,
            "auto_adjust": False,
            "back_adjust": False,
            "actions": True,
            "repair": False,
            "keepna": True,
            "prepost": False,
            "rounding": False,
        }
        self._repository.create_run(
            run_id=run_id,
            batch_id=resolved_batch_id,
            instrument=instrument,
            requested_start=request.start_date,
            requested_end=request.end_date,
            interval_code=request.interval_code.value,
            adapter_version=self._provider.adapter_version,
            provider_library_version=self._provider.library_version,
            calendar_library_version=version("exchange-calendars"),
            python_version=sys.version.split()[0],
            code_version=code_version,
            git_dirty=git_dirty,
            request_parameters=request_parameters,
        )

        phase = "provider_fetch"
        snapshot: SnapshotReference | None = None
        report: QualityReport | None = None
        normalized_hash: str | None = None
        rows_received = 0
        rows_accepted = 0
        try:
            source_batch = retry_call(
                lambda: self._provider.fetch(instrument, request),
                max_attempts=self._max_attempts,
                base_seconds=self._backoff_base_seconds,
                cap_seconds=self._backoff_cap_seconds,
            )
            rows_received = len(source_batch.rows)
            if (
                source_batch.source_name != instrument.source_name
                or source_batch.source_symbol != instrument.source_symbol
                or source_batch.requested_start != request.start_date
                or source_batch.requested_end != request.end_date
                or source_batch.interval_code != request.interval_code
            ):
                raise DataQualityError("Provider response identity does not match the request")

            phase = "snapshot"
            snapshot = self._snapshots.write(source_batch)
            phase = "normalization"
            normalized = normalize_source_batch(source_batch, instrument, calendar)
            phase = "quality_validation"
            validated = validate_batch(
                normalized,
                instrument,
                calendar,
                requested_start=request.start_date,
                requested_end=request.end_date,
                as_of=now,
                price_jump_fraction=self._price_jump_fraction,
                repeated_ohlc_sessions=self._repeated_ohlc_sessions,
                volume_spike_multiple=self._volume_spike_multiple,
                volume_window_sessions=self._volume_window_sessions,
            )
            rows_accepted = len(validated.bars)
            report = validated.report
            from data_pipeline.schema.hashing import normalized_batch_sha256

            normalized_hash = normalized_batch_sha256(validated.bars, validated.corporate_actions)
            if report.critical_count:
                raise DataQualityError(
                    f"Batch has {report.critical_count} critical data-quality finding(s)"
                )
            phase = "persistence"
            persistence = self._repository.persist_success(
                run_id=run_id,
                instrument=instrument,
                bars=validated.bars,
                actions=validated.corporate_actions,
                rows_received=rows_received,
                snapshot=snapshot,
                normalized_sha256=normalized_hash,
                report=report,
            )
            return IngestionResult(
                run_id=run_id,
                batch_id=resolved_batch_id,
                canonical_symbol=request.canonical_symbol,
                status=RunStatus.SUCCEEDED,
                snapshot=snapshot,
                normalized_sha256=normalized_hash,
                persistence=persistence,
                quality_report=report,
            )
        except Exception as error:
            safe_message = _safe_error_message(error)
            self._repository.mark_failed(
                run_id,
                error_type=classify_error(error).value,
                error_message=safe_message,
                failure_phase=phase,
                rows_received=rows_received,
                rows_accepted=rows_accepted,
                snapshot=snapshot,
                normalized_sha256=normalized_hash,
                report=report,
            )
            return IngestionResult(
                run_id=run_id,
                batch_id=resolved_batch_id,
                canonical_symbol=request.canonical_symbol,
                status=RunStatus.FAILED,
                snapshot=snapshot,
                normalized_sha256=normalized_hash,
                persistence=None,
                quality_report=report,
                error_type=classify_error(error).value,
                error_message=safe_message,
            )
