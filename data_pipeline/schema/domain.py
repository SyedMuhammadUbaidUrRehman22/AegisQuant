"""Canonical Stage 1 market-data contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = 1


class AssetClass(StrEnum):
    """Asset classes supported by the Stage 1 universe."""

    ETF = "etf"


class IntervalCode(StrEnum):
    """Canonical bar intervals supported in Stage 1."""

    DAILY = "1d"


class RunStatus(StrEnum):
    """Lifecycle states for one instrument ingestion attempt."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class QualitySeverity(StrEnum):
    """Severity levels used by deterministic data-quality rules."""

    WARNING = "warning"
    CRITICAL = "critical"


class CorporateActionType(StrEnum):
    """Corporate-action types exposed by the initial provider."""

    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    CAPITAL_GAIN = "capital_gain"


class InstrumentSeed(BaseModel):
    """Version-controlled reference metadata for one approved instrument."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9.-]+$")
    name: str = Field(min_length=1)
    asset_class: AssetClass = AssetClass.ETF
    venue_mic: str = Field(min_length=4, max_length=4, pattern=r"^[A-Z0-9]{4}$")
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    timezone: str = Field(min_length=1)
    calendar_code: str = Field(min_length=1, max_length=16)
    source_name: str = Field(min_length=1, max_length=32)
    source_symbol: str = Field(min_length=1, max_length=64)
    valid_from: date | None = None
    valid_to: date | None = None
    active: bool = True

    @model_validator(mode="after")
    def validate_validity_window(self) -> InstrumentSeed:
        """Reject inverted instrument validity windows."""

        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to cannot be earlier than valid_from")
        return self


class Instrument(BaseModel):
    """Resolved database identity plus provider mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument_id: int = Field(gt=0)
    canonical_symbol: str
    name: str
    asset_class: AssetClass
    venue_mic: str
    currency: str
    timezone: str
    calendar_code: str
    source_name: str
    source_symbol: str
    valid_from: date | None
    valid_to: date | None
    active: bool


class IngestionRequest(BaseModel):
    """One historical request for one canonical instrument."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_symbol: str = Field(min_length=1, max_length=32)
    start_date: date
    end_date: date
    interval_code: IntervalCode = IntervalCode.DAILY

    @model_validator(mode="after")
    def validate_range(self) -> IngestionRequest:
        """Require a non-empty, end-exclusive date range."""

        if self.end_date <= self.start_date:
            raise ValueError("end_date must be later than start_date")
        return self


class SourceBatch(BaseModel):
    """Provider-shaped rows retained before canonical normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: str
    source_symbol: str
    interval_code: IntervalCode
    requested_start: date
    requested_end: date
    fetched_at: datetime
    columns: tuple[str, ...]
    rows: tuple[dict[str, str | None], ...]
    metadata: dict[str, str]

    @field_validator("fetched_at")
    @classmethod
    def require_aware_fetched_at(cls, value: datetime) -> datetime:
        """Normalize the source acquisition time to UTC."""

        if value.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        return value.astimezone(UTC)


class CanonicalBar(BaseModel):
    """One normalized, completed OHLCV observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument_id: int = Field(gt=0)
    interval_code: IntervalCode
    session_date: date
    bar_start_at: datetime
    bar_end_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int
    source_name: str
    contract_version: int = CONTRACT_VERSION
    quality_flags: tuple[str, ...] = ()

    @field_validator("bar_start_at", "bar_end_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        """Require aware timestamps and canonicalize them to UTC."""

        if value.tzinfo is None:
            raise ValueError("bar timestamps must be timezone-aware")
        return value.astimezone(UTC)


class CorporateAction(BaseModel):
    """One normalized cash distribution or split event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument_id: int = Field(gt=0)
    effective_date: date
    action_type: CorporateActionType
    action_value: Decimal
    currency: str | None
    source_name: str


class QualityIssue(BaseModel):
    """One machine-readable quality finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: QualitySeverity
    message: str
    session_date: date | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class QualityReport(BaseModel):
    """Deterministic quality result for one requested range."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_symbol: str
    requested_start: date
    requested_end: date
    expected_sessions: int
    observed_sessions: int
    issues: tuple[QualityIssue, ...] = ()

    @property
    def critical_count(self) -> int:
        """Return the number of release-blocking findings."""

        return sum(issue.severity is QualitySeverity.CRITICAL for issue in self.issues)

    @property
    def warning_count(self) -> int:
        """Return the number of non-destructive anomaly findings."""

        return sum(issue.severity is QualitySeverity.WARNING for issue in self.issues)


class NormalizationResult(BaseModel):
    """Canonical observations plus normalization findings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bars: tuple[CanonicalBar, ...]
    corporate_actions: tuple[CorporateAction, ...]
    issues: tuple[QualityIssue, ...] = ()


class ValidatedBatch(BaseModel):
    """Deduplicated canonical data safe to offer to persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bars: tuple[CanonicalBar, ...]
    corporate_actions: tuple[CorporateAction, ...]
    report: QualityReport


class SnapshotReference(BaseModel):
    """Portable reference to one immutable provider-response snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str
    sha256: str = Field(min_length=64, max_length=64)


class PersistenceResult(BaseModel):
    """Counts produced by one atomic canonical persistence transaction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inserted: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    actions_inserted: int = Field(ge=0)
    actions_updated: int = Field(ge=0)
    actions_unchanged: int = Field(ge=0)


class IngestionResult(BaseModel):
    """Public result for one completed ingestion attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    batch_id: UUID
    canonical_symbol: str
    status: RunStatus
    snapshot: SnapshotReference | None
    normalized_sha256: str | None
    persistence: PersistenceResult | None
    quality_report: QualityReport | None
    error_type: str | None = None
    error_message: str | None = None


class BatchIngestionResult(BaseModel):
    """Aggregate result for an unattended multi-instrument command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_id: UUID
    results: tuple[IngestionResult, ...]

    @property
    def succeeded(self) -> bool:
        """Return true only when every instrument succeeded."""

        return all(result.status is RunStatus.SUCCEEDED for result in self.results)
