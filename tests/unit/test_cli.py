"""Focused command-line parsing and range-resolution tests."""

import argparse
from datetime import date
from unittest.mock import MagicMock

import pytest

from data_pipeline.cli import _parser, _resolve_start_date, _selected_symbols
from data_pipeline.ingestion.repository import MarketDataRepository
from data_pipeline.universe import PILOT_SYMBOLS, STAGE_1_UNIVERSE


def test_ingest_selection_modes_and_dates() -> None:
    parser = _parser()
    pilot = parser.parse_args(["ingest", "--pilot", "--start", "2024-01-02", "--end", "2024-02-01"])
    full = parser.parse_args(["ingest", "--full"])
    subset = parser.parse_args(["ingest", "--symbols", "spy", "QQQ"])

    assert _selected_symbols(pilot) == PILOT_SYMBOLS
    assert _selected_symbols(full) == tuple(seed.canonical_symbol for seed in STAGE_1_UNIVERSE)
    assert _selected_symbols(subset) == ("SPY", "QQQ")
    assert (pilot.start, pilot.end) == (date(2024, 1, 2), date(2024, 2, 1))


@pytest.mark.parametrize(
    "arguments",
    [
        ["ingest", "--pilot", "--start", "2024/01/02"],
        ["ingest"],
        ["ingest", "--pilot", "--full"],
    ],
)
def test_invalid_ingest_input_is_rejected(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(arguments)


def test_unknown_symbol_is_rejected() -> None:
    arguments = argparse.Namespace(pilot=False, full=False, symbols=["SPY", "BAD"])
    with pytest.raises(ValueError, match="outside the approved"):
        _selected_symbols(arguments)


def test_incremental_range_replays_latest_session() -> None:
    repository = MagicMock(spec=MarketDataRepository)
    repository.latest_session.return_value = date(2024, 1, 10)

    assert _resolve_start_date(
        repository,
        1,
        configured_start=date(2000, 1, 1),
        requested_start=date(2024, 1, 1),
        incremental=True,
    ) == date(2024, 1, 10)
    repository.latest_session.assert_called_once_with(1)


def test_historical_range_does_not_query_latest_session() -> None:
    repository = MagicMock(spec=MarketDataRepository)
    assert _resolve_start_date(
        repository,
        1,
        configured_start=date(2000, 1, 1),
        requested_start=None,
        incremental=False,
    ) == date(2000, 1, 1)
    repository.latest_session.assert_not_called()
