"""TimescaleDB integration fixtures; skipped unless a test URL is explicit."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.environ.get("AEGISQUANT_TEST_DATABASE_URL") or os.environ.get(
        "AEGISQUANT_DATABASE_URL"
    )
    if value is None:
        pytest.skip("AEGISQUANT_TEST_DATABASE_URL is not configured")
    return value


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    configuration = Config("alembic.ini")
    configuration.set_main_option("sqlalchemy.url", database_url)
    previous = os.environ.get("AEGISQUANT_DATABASE_URL")
    os.environ["AEGISQUANT_DATABASE_URL"] = database_url
    try:
        command.downgrade(configuration, "base")
        command.upgrade(configuration, "head")
        engine = create_engine(database_url, pool_pre_ping=True)
        yield engine
        engine.dispose()
    finally:
        if previous is None:
            os.environ.pop("AEGISQUANT_DATABASE_URL", None)
        else:
            os.environ["AEGISQUANT_DATABASE_URL"] = previous


@pytest.fixture()
def clean_engine(migrated_engine: Engine) -> Iterator[Engine]:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE ohlcv_bars, corporate_actions, ingestion_runs, "
                "instrument_source_symbols, instruments RESTART IDENTITY CASCADE"
            )
        )
    yield migrated_engine
