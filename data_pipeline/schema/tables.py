"""SQLAlchemy Core metadata for the Stage 1 TimescaleDB schema."""

from __future__ import annotations

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

instruments = Table(
    "instruments",
    metadata,
    Column("instrument_id", BigInteger, primary_key=True, autoincrement=True),
    Column("canonical_symbol", String(32), nullable=False),
    Column("name", Text, nullable=False),
    Column("asset_class", String(16), nullable=False),
    Column("venue_mic", String(4), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("timezone", Text, nullable=False),
    Column("calendar_code", String(16), nullable=False),
    Column("valid_from", Date, nullable=True),
    Column("valid_to", Date, nullable=True),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("canonical_symbol", "venue_mic"),
    CheckConstraint("asset_class = 'etf'", name="asset_class_supported"),
    CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
    CheckConstraint("venue_mic ~ '^[A-Z0-9]{4}$'", name="venue_mic_format"),
    CheckConstraint(
        "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="validity"
    ),
)

instrument_source_symbols = Table(
    "instrument_source_symbols",
    metadata,
    Column("instrument_source_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "instrument_id",
        BigInteger,
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("source_name", String(32), nullable=False),
    Column("source_symbol", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("source_name", "source_symbol"),
    UniqueConstraint("instrument_id", "source_name"),
)

ingestion_runs = Table(
    "ingestion_runs",
    metadata,
    Column("run_id", Uuid(as_uuid=True), primary_key=True),
    Column("batch_id", Uuid(as_uuid=True), nullable=False),
    Column(
        "instrument_id",
        BigInteger,
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("source_name", String(32), nullable=False),
    Column("source_symbol", String(64), nullable=False),
    Column("interval_code", String(8), nullable=False),
    Column("requested_start", Date, nullable=False),
    Column("requested_end", Date, nullable=False),
    Column("actual_start", Date, nullable=True),
    Column("actual_end", Date, nullable=True),
    Column("status", String(16), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("rows_received", Integer, nullable=False, server_default=text("0")),
    Column("rows_accepted", Integer, nullable=False, server_default=text("0")),
    Column("rows_inserted", Integer, nullable=False, server_default=text("0")),
    Column("rows_updated", Integer, nullable=False, server_default=text("0")),
    Column("rows_unchanged", Integer, nullable=False, server_default=text("0")),
    Column("warning_count", Integer, nullable=False, server_default=text("0")),
    Column("critical_count", Integer, nullable=False, server_default=text("0")),
    Column("snapshot_path", Text, nullable=True),
    Column("snapshot_sha256", String(64), nullable=True),
    Column("normalized_sha256", String(64), nullable=True),
    Column("adapter_version", String(32), nullable=False),
    Column("provider_library_version", String(32), nullable=False),
    Column("calendar_library_version", String(32), nullable=False),
    Column("contract_version", SmallInteger, nullable=False),
    Column("python_version", String(32), nullable=False),
    Column("git_commit", String(40), nullable=False),
    Column("git_dirty", Boolean, nullable=False),
    Column("request_parameters", JSONB, nullable=False),
    Column("error_type", String(128), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("failure_phase", String(32), nullable=True),
    CheckConstraint("requested_end > requested_start", name="requested_range"),
    CheckConstraint("interval_code = '1d'", name="interval_supported"),
    CheckConstraint(
        "status IN ('running', 'succeeded', 'failed', 'abandoned')",
        name="status_supported",
    ),
    CheckConstraint(
        "rows_received >= 0 AND rows_accepted >= 0 AND rows_inserted >= 0 "
        "AND rows_updated >= 0 AND rows_unchanged >= 0 "
        "AND warning_count >= 0 AND critical_count >= 0",
        name="counts_nonnegative",
    ),
)

ohlcv_bars = Table(
    "ohlcv_bars",
    metadata,
    Column(
        "instrument_id",
        BigInteger,
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("interval_code", String(8), primary_key=True),
    Column("bar_start_at", DateTime(timezone=True), primary_key=True),
    Column("bar_end_at", DateTime(timezone=True), nullable=False),
    Column("session_date", Date, nullable=False),
    Column("open", Numeric(20, 8), nullable=False),
    Column("high", Numeric(20, 8), nullable=False),
    Column("low", Numeric(20, 8), nullable=False),
    Column("close", Numeric(20, 8), nullable=False),
    Column("adjusted_close", Numeric(20, 8), nullable=False),
    Column("volume", BigInteger, nullable=False),
    Column("source_name", String(32), nullable=False),
    Column(
        "ingestion_run_id",
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("contract_version", SmallInteger, nullable=False),
    Column("quality_flags", ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("interval_code = '1d'", name="interval_supported"),
    CheckConstraint("bar_end_at > bar_start_at", name="time_order"),
    CheckConstraint("open > 0 AND high > 0 AND low > 0 AND close > 0", name="prices_positive"),
    CheckConstraint("adjusted_close > 0", name="adjusted_close_positive"),
    CheckConstraint("high >= low", name="high_gte_low"),
    CheckConstraint("high >= open AND high >= close", name="high_bounds"),
    CheckConstraint("low <= open AND low <= close", name="low_bounds"),
    CheckConstraint("volume >= 0", name="volume_nonnegative"),
)

corporate_actions = Table(
    "corporate_actions",
    metadata,
    Column(
        "instrument_id",
        BigInteger,
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("effective_date", Date, primary_key=True),
    Column("action_type", String(24), primary_key=True),
    Column("action_value", Numeric(30, 10), nullable=False),
    Column("currency", String(3), nullable=True),
    Column("source_name", String(32), nullable=False),
    Column(
        "ingestion_run_id",
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "action_type IN ('dividend', 'stock_split', 'capital_gain')",
        name="action_type_supported",
    ),
    CheckConstraint("action_value > 0", name="action_value_positive"),
    CheckConstraint(
        "(action_type = 'stock_split' AND currency IS NULL) OR "
        "(action_type <> 'stock_split' AND currency IS NOT NULL)",
        name="action_currency",
    ),
)

Index(
    "ix_ohlcv_bars_interval_time_instrument",
    ohlcv_bars.c.interval_code,
    ohlcv_bars.c.bar_start_at,
    ohlcv_bars.c.instrument_id,
)
Index("ix_ingestion_runs_batch_id", ingestion_runs.c.batch_id)
Index(
    "ix_ingestion_runs_instrument_started",
    ingestion_runs.c.instrument_id,
    ingestion_runs.c.started_at.desc(),
)
Index(
    "ix_corporate_actions_instrument_date",
    corporate_actions.c.instrument_id,
    corporate_actions.c.effective_date.desc(),
)
