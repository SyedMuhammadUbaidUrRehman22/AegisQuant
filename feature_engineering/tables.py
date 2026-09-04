"""SQLAlchemy metadata for versioned Stage 2 materialized features."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    func,
)

from data_pipeline.schema.tables import metadata

feature_values = Table(
    "feature_values",
    metadata,
    Column(
        "instrument_id",
        BigInteger,
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("feature_name", String(96), primary_key=True),
    Column("feature_version", Integer, primary_key=True),
    Column("definition_hash", String(64), primary_key=True),
    Column("bar_end_at", DateTime(timezone=True), primary_key=True),
    Column("feature_as_of", DateTime(timezone=True), nullable=False),
    Column("value", Float(precision=53), nullable=True),
    Column("missing_reason", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
    CheckConstraint("feature_version > 0", name="version_positive"),
    CheckConstraint("definition_hash ~ '^[0-9a-f]{64}$'", name="definition_hash_format"),
    CheckConstraint("feature_as_of <= bar_end_at", name="point_in_time"),
    CheckConstraint(
        "missing_reason IN ('available', 'insufficient_history', 'missing_input', 'undefined')",
        name="missing_reason_supported",
    ),
    CheckConstraint(
        "(missing_reason = 'available' AND value IS NOT NULL) OR "
        "(missing_reason <> 'available' AND value IS NULL)",
        name="value_matches_missing_reason",
    ),
)

Index(
    "ix_feature_values_name_time_instrument",
    feature_values.c.feature_name,
    feature_values.c.bar_end_at,
    feature_values.c.instrument_id,
)
Index(
    "ix_feature_values_instrument_time",
    feature_values.c.instrument_id,
    feature_values.c.bar_end_at,
)
