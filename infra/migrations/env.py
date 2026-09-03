"""Alembic environment for the approved Stage 1 schema."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from config.settings import get_settings
from data_pipeline.schema.tables import metadata

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = metadata


def _database_url() -> str:
    """Resolve a full URL override or build one from validated environment settings."""

    explicit_url = os.environ.get("AEGISQUANT_DATABASE_URL")
    if explicit_url:
        return explicit_url
    return get_settings().database.sqlalchemy_url()


def run_migrations_offline() -> None:
    """Configure an offline migration context."""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Configure an online migration context with a short-lived connection."""

    section = alembic_config.get_section(alembic_config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
