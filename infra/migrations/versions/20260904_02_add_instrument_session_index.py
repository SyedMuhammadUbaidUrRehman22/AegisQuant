"""Add the Stage 1 instrument/session range-query index.

Revision ID: 20260904_02
Revises: 20260903_01
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260904_02"
down_revision: str | Sequence[str] | None = "20260903_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support canonical per-instrument session-date range retrieval."""

    op.create_index(
        "ix_ohlcv_bars_instrument_session_date",
        "ohlcv_bars",
        ["instrument_id", "session_date"],
    )


def downgrade() -> None:
    """Remove the Stage 1 instrument/session range-query index."""

    op.drop_index("ix_ohlcv_bars_instrument_session_date", table_name="ohlcv_bars")
