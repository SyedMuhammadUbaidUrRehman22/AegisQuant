"""Create the versioned Stage 2 feature table.

Revision ID: 20260904_03
Revises: 20260904_02
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_03"
down_revision: str | Sequence[str] | None = "20260904_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_values",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_name", sa.String(length=96), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("definition_hash", sa.String(length=64), nullable=False),
        sa.Column("bar_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(precision=53), nullable=True),
        sa.Column("missing_reason", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("definition_hash ~ '^[0-9a-f]{64}$'", name="definition_hash_format"),
        sa.CheckConstraint("feature_as_of <= bar_end_at", name="point_in_time"),
        sa.CheckConstraint("feature_version > 0", name="version_positive"),
        sa.CheckConstraint(
            "missing_reason IN ('available', 'insufficient_history', 'missing_input', 'undefined')",
            name="missing_reason_supported",
        ),
        sa.CheckConstraint(
            "(missing_reason = 'available' AND value IS NOT NULL) OR "
            "(missing_reason <> 'available' AND value IS NULL)",
            name="value_matches_missing_reason",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.instrument_id"],
            name="fk_feature_values_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "instrument_id",
            "feature_name",
            "feature_version",
            "definition_hash",
            "bar_end_at",
            name="pk_feature_values",
        ),
    )
    op.create_index(
        "ix_feature_values_name_time_instrument",
        "feature_values",
        ["feature_name", "bar_end_at", "instrument_id"],
    )
    op.create_index(
        "ix_feature_values_instrument_time", "feature_values", ["instrument_id", "bar_end_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_feature_values_instrument_time", table_name="feature_values")
    op.drop_index("ix_feature_values_name_time_instrument", table_name="feature_values")
    op.drop_table("feature_values")
