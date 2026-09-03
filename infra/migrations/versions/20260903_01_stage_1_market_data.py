"""Create the Stage 1 canonical market-data schema.

Revision ID: 20260903_01
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Stage 1 relational metadata, audit tables, and OHLCV hypertable."""

    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "instruments",
        sa.Column("instrument_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("canonical_symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("asset_class", sa.String(length=16), nullable=False),
        sa.Column("venue_mic", sa.String(length=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("calendar_code", sa.String(length=16), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("asset_class = 'etf'", name="ck_instruments_asset_class_supported"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_instruments_currency_format"),
        sa.CheckConstraint(
            "venue_mic ~ '^[A-Z0-9]{4}$'",
            name="ck_instruments_venue_mic_format",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_instruments_validity",
        ),
        sa.PrimaryKeyConstraint("instrument_id", name="pk_instruments"),
        sa.UniqueConstraint(
            "canonical_symbol",
            "venue_mic",
            name="uq_instruments_canonical_symbol_venue_mic",
        ),
    )

    op.create_table(
        "instrument_source_symbols",
        sa.Column("instrument_source_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.String(length=32), nullable=False),
        sa.Column("source_symbol", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.instrument_id"],
            name="fk_instrument_source_symbols_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("instrument_source_id", name="pk_instrument_source_symbols"),
        sa.UniqueConstraint(
            "source_name",
            "source_symbol",
            name="uq_instrument_source_symbols_source_name_source_symbol",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "source_name",
            name="uq_instrument_source_symbols_instrument_id_source_name",
        ),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.String(length=32), nullable=False),
        sa.Column("source_symbol", sa.String(length=64), nullable=False),
        sa.Column("interval_code", sa.String(length=8), nullable=False),
        sa.Column("requested_start", sa.Date(), nullable=False),
        sa.Column("requested_end", sa.Date(), nullable=False),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_received", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_accepted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_unchanged", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("warning_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("critical_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("snapshot_path", sa.Text(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=True),
        sa.Column("normalized_sha256", sa.String(length=64), nullable=True),
        sa.Column("adapter_version", sa.String(length=32), nullable=False),
        sa.Column("provider_library_version", sa.String(length=32), nullable=False),
        sa.Column("calendar_library_version", sa.String(length=32), nullable=False),
        sa.Column("contract_version", sa.SmallInteger(), nullable=False),
        sa.Column("python_version", sa.String(length=32), nullable=False),
        sa.Column("git_commit", sa.String(length=40), nullable=False),
        sa.Column("git_dirty", sa.Boolean(), nullable=False),
        sa.Column("request_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("failure_phase", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "rows_received >= 0 AND rows_accepted >= 0 AND rows_inserted >= 0 "
            "AND rows_updated >= 0 AND rows_unchanged >= 0 "
            "AND warning_count >= 0 AND critical_count >= 0",
            name="ck_ingestion_runs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "interval_code = '1d'",
            name="ck_ingestion_runs_interval_supported",
        ),
        sa.CheckConstraint(
            "requested_end > requested_start",
            name="ck_ingestion_runs_requested_range",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'abandoned')",
            name="ck_ingestion_runs_status_supported",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.instrument_id"],
            name="fk_ingestion_runs_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_ingestion_runs"),
    )
    op.create_index("ix_ingestion_runs_batch_id", "ingestion_runs", ["batch_id"])
    op.create_index(
        "ix_ingestion_runs_instrument_started",
        "ingestion_runs",
        ["instrument_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "ohlcv_bars",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("interval_code", sa.String(length=8), nullable=False),
        sa.Column("bar_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bar_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("high", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("low", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("close", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.String(length=32), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.SmallInteger(), nullable=False),
        sa.Column(
            "quality_flags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "adjusted_close > 0",
            name="ck_ohlcv_bars_adjusted_close_positive",
        ),
        sa.CheckConstraint(
            "high >= open AND high >= close",
            name="ck_ohlcv_bars_high_bounds",
        ),
        sa.CheckConstraint("high >= low", name="ck_ohlcv_bars_high_gte_low"),
        sa.CheckConstraint(
            "interval_code = '1d'",
            name="ck_ohlcv_bars_interval_supported",
        ),
        sa.CheckConstraint(
            "low <= open AND low <= close",
            name="ck_ohlcv_bars_low_bounds",
        ),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_ohlcv_bars_prices_positive",
        ),
        sa.CheckConstraint("bar_end_at > bar_start_at", name="ck_ohlcv_bars_time_order"),
        sa.CheckConstraint("volume >= 0", name="ck_ohlcv_bars_volume_nonnegative"),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_ohlcv_bars_ingestion_run_id_ingestion_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.instrument_id"],
            name="fk_ohlcv_bars_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "instrument_id",
            "interval_code",
            "bar_start_at",
            name="pk_ohlcv_bars",
        ),
    )
    op.execute(
        "SELECT create_hypertable("
        "'ohlcv_bars', 'bar_start_at', "
        "chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_ohlcv_bars_interval_time_instrument",
        "ohlcv_bars",
        ["interval_code", "bar_start_at", "instrument_id"],
    )

    op.create_table(
        "corporate_actions",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("action_type", sa.String(length=24), nullable=False),
        sa.Column("action_value", sa.Numeric(precision=30, scale=10), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("source_name", sa.String(length=32), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(action_type = 'stock_split' AND currency IS NULL) OR "
            "(action_type <> 'stock_split' AND currency IS NOT NULL)",
            name="ck_corporate_actions_action_currency",
        ),
        sa.CheckConstraint(
            "action_type IN ('dividend', 'stock_split', 'capital_gain')",
            name="ck_corporate_actions_action_type_supported",
        ),
        sa.CheckConstraint(
            "action_value > 0",
            name="ck_corporate_actions_action_value_positive",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_corporate_actions_ingestion_run_id_ingestion_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.instrument_id"],
            name="fk_corporate_actions_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "instrument_id",
            "effective_date",
            "action_type",
            name="pk_corporate_actions",
        ),
    )
    op.create_index(
        "ix_corporate_actions_instrument_date",
        "corporate_actions",
        ["instrument_id", sa.text("effective_date DESC")],
    )


def downgrade() -> None:
    """Remove only Stage 1 objects; preserve the shared TimescaleDB extension."""

    op.drop_index("ix_corporate_actions_instrument_date", table_name="corporate_actions")
    op.drop_table("corporate_actions")
    op.drop_index("ix_ohlcv_bars_interval_time_instrument", table_name="ohlcv_bars")
    op.drop_table("ohlcv_bars")
    op.drop_index("ix_ingestion_runs_instrument_started", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_batch_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("instrument_source_symbols")
    op.drop_table("instruments")
