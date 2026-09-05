"""Reject nonfinite feature values and empty names.

Revision ID: 20260905_04
Revises: 20260904_03
"""

from alembic import op

revision = "20260905_04"
down_revision = "20260904_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("name_nonempty", "feature_values", "length(feature_name) > 0")
    op.create_check_constraint(
        "value_finite",
        "feature_values",
        "value IS NULL OR (value > '-Infinity'::float8 AND value < 'Infinity'::float8)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_feature_values_value_finite"), "feature_values", type_="check")
    op.drop_constraint(op.f("ck_feature_values_name_nonempty"), "feature_values", type_="check")
