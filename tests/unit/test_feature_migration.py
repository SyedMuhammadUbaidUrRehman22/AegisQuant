"""Render the migration chain without claiming online PostgreSQL execution."""

from io import StringIO

import pytest
from alembic import command
from alembic.config import Config


def test_offline_feature_integrity_migration_upgrade_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AEGISQUANT_DATABASE_URL", "postgresql+psycopg://offline:offline@localhost/unused"
    )
    output = StringIO()
    configuration = Config("alembic.ini", output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    ddl = output.getvalue()
    assert "CREATE TABLE feature_values" in ddl
    assert "ADD CONSTRAINT ck_feature_values_value_finite CHECK" in ddl
    assert "ADD CONSTRAINT ck_feature_values_name_nonempty CHECK" in ddl
    assert "value > '-Infinity'::float8 AND value < 'Infinity'::float8" in ddl
    output.seek(0)
    output.truncate()
    command.downgrade(configuration, "20260905_04:20260904_03", sql=True)
    assert "DROP CONSTRAINT ck_feature_values_value_finite" in output.getvalue()
    assert "DROP CONSTRAINT ck_feature_values_name_nonempty" in output.getvalue()
