"""Command-line entry point for Stage 1 historical ingestion operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine

from config import load_settings
from data_pipeline.ingestion.provider import YahooFinanceProvider
from data_pipeline.ingestion.repository import MarketDataRepository
from data_pipeline.ingestion.service import IngestionService
from data_pipeline.ingestion.snapshots import SnapshotStore
from data_pipeline.quality_checks import write_batch_report
from data_pipeline.schema import IngestionRequest
from data_pipeline.universe import PILOT_SYMBOLS, STAGE_1_UNIVERSE, universe_by_symbol
from data_pipeline.validation import compare_alpha_vantage


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AegisQuant Stage 1 market-data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed", help="idempotently seed the approved 20-instrument universe")

    ingest = subparsers.add_parser("ingest", help="run historical or incremental ingestion")
    selection = ingest.add_mutually_exclusive_group(required=True)
    selection.add_argument("--pilot", action="store_true", help="ingest the approved five symbols")
    selection.add_argument("--full", action="store_true", help="ingest all approved symbols")
    selection.add_argument("--symbols", nargs="+", help="ingest an approved symbol subset")
    ingest.add_argument("--start", type=_date, help="inclusive date; defaults to configured start")
    ingest.add_argument("--end", type=_date, help="exclusive date; defaults to today")
    ingest.add_argument(
        "--incremental",
        action="store_true",
        help="start at each symbol's latest stored session to detect revisions",
    )
    ingest.add_argument(
        "--report-dir",
        type=Path,
        default=Path("data/reports"),
        help="quality result output directory",
    )

    subparsers.add_parser("inspect", help="print row counts and duplicate diagnostics")
    compare = subparsers.add_parser(
        "compare-second-source", help="spot-check pilot closes against Alpha Vantage"
    )
    compare.add_argument("--output", type=Path, default=Path("data/reports/second-source.json"))
    return parser


def _build_service() -> tuple[MarketDataRepository, IngestionService]:
    settings = load_settings()
    engine = create_engine(settings.database.sqlalchemy_url(), pool_pre_ping=True)
    repository = MarketDataRepository(engine)
    pipeline = settings.data_pipeline
    service = IngestionService(
        repository=repository,
        provider=YahooFinanceProvider(timeout_seconds=pipeline.request_timeout_seconds),
        snapshots=SnapshotStore(pipeline.raw_data_dir),
        max_attempts=pipeline.max_attempts,
        backoff_base_seconds=pipeline.backoff_base_seconds,
        backoff_cap_seconds=pipeline.backoff_cap_seconds,
        price_jump_fraction=pipeline.price_jump_warning_fraction,
        repeated_ohlc_sessions=pipeline.repeated_ohlc_warning_sessions,
        volume_spike_multiple=pipeline.volume_spike_warning_multiple,
        volume_window_sessions=pipeline.volume_window_sessions,
    )
    return repository, service


def _selected_symbols(arguments: argparse.Namespace) -> tuple[str, ...]:
    if arguments.pilot:
        return PILOT_SYMBOLS
    if arguments.full:
        return tuple(seed.canonical_symbol for seed in STAGE_1_UNIVERSE)
    approved = universe_by_symbol()
    requested = tuple(symbol.upper() for symbol in arguments.symbols)
    unknown = sorted(set(requested).difference(approved))
    if unknown:
        raise ValueError(f"Symbols are outside the approved Stage 1 universe: {unknown}")
    return requested


def _resolve_start_date(
    repository: MarketDataRepository,
    instrument_id: int,
    *,
    configured_start: date,
    requested_start: date | None,
    incremental: bool,
) -> date:
    """Resolve a deterministic historical or overlap-aware incremental start."""

    start_date = requested_start or configured_start
    if incremental:
        latest = repository.latest_session(instrument_id)
        if latest is not None:
            start_date = latest
    return start_date


def main(argv: list[str] | None = None) -> int:
    """Execute one Stage 1 operational command."""

    arguments = _parser().parse_args(argv)
    repository, service = _build_service()
    if arguments.command == "seed":
        seeded = repository.seed_instruments(STAGE_1_UNIVERSE)
        print(json.dumps({"seeded": [item.canonical_symbol for item in seeded]}))
        return 0
    if arguments.command == "inspect":
        print(json.dumps(repository.integrity_summary(), indent=2, sort_keys=True))
        return 0
    if arguments.command == "compare-second-source":
        comparison_result = compare_alpha_vantage(
            repository,
            PILOT_SYMBOLS,
            api_key=os.environ.get("ALPHAVANTAGE_API_KEY", ""),
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(comparison_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(comparison_result, indent=2, sort_keys=True))
        return 0 if comparison_result["passed"] is True else 1

    repository.seed_instruments(STAGE_1_UNIVERSE)
    settings = load_settings()
    end_date = arguments.end or date.today()
    requests: list[IngestionRequest] = []
    for symbol in _selected_symbols(arguments):
        instrument = repository.get_instrument(symbol)
        start_date = _resolve_start_date(
            repository,
            instrument.instrument_id,
            configured_start=settings.data_pipeline.historical_start,
            requested_start=arguments.start,
            incremental=arguments.incremental,
        )
        requests.append(
            IngestionRequest(canonical_symbol=symbol, start_date=start_date, end_date=end_date)
        )
    result = service.ingest_batch(requests)
    report_path = write_batch_report(result, arguments.report_dir)
    print(result.model_dump_json(indent=2))
    print(f"quality_report={report_path}")
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
