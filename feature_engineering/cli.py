"""Command-line orchestration for deterministic Stage 2 materialization."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import create_engine

from config import load_settings
from feature_engineering.service import materialize_features


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AegisQuant Stage 2 feature materialization")
    parser.add_argument(
        "--as-of",
        required=True,
        type=_aware_datetime,
        help="inclusive point-in-time cutoff with UTC offset, for example 2026-09-04T21:00:00Z",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    settings = load_settings()
    engine = create_engine(settings.database.sqlalchemy_url(), pool_pre_ping=True)
    try:
        observations = materialize_features(engine, as_of=arguments.as_of)
    finally:
        engine.dispose()
    available = sum(row.value is not None for row in observations)
    print(
        f"materialized={len(observations)} available={available} "
        f"unavailable={len(observations) - available} as_of={arguments.as_of.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
