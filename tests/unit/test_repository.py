"""Focused persistence comparison tests."""

from typing import cast

from sqlalchemy import RowMapping

from data_pipeline.ingestion.repository import BAR_VALUE_COLUMNS, _matches


def test_batch_relative_quality_flags_do_not_create_source_corrections() -> None:
    current: dict[str, object] = {column: f"value-{column}" for column in BAR_VALUE_COLUMNS}
    proposed: dict[str, object] = dict(current)
    current["quality_flags"] = ["repeated_ohlc"]
    proposed["quality_flags"] = []

    assert _matches(cast(RowMapping, current), proposed, BAR_VALUE_COLUMNS)
