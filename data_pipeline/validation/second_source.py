"""Read-only Alpha Vantage spot checks against persisted Yahoo closes."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import urlopen

from data_pipeline.ingestion.repository import MarketDataRepository

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def _fetch_alpha_vantage(symbol: str, api_key: str, timeout_seconds: int) -> dict[date, Decimal]:
    parameters = urlencode(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "datatype": "json",
            "apikey": api_key,
        }
    )
    with urlopen(f"{ALPHA_VANTAGE_URL}?{parameters}", timeout=timeout_seconds) as response:
        payload: object = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Alpha Vantage response must be an object")
    typed_payload = cast(dict[str, Any], payload)
    if "Error Message" in typed_payload:
        raise ValueError("Alpha Vantage rejected the symbol request")
    if "Note" in typed_payload or "Information" in typed_payload:
        raise RuntimeError("Alpha Vantage request limit or entitlement prevented validation")
    series = typed_payload.get("Time Series (Daily)")
    if not isinstance(series, dict):
        raise ValueError("Alpha Vantage daily time series is absent")
    parsed: dict[date, Decimal] = {}
    for raw_date, raw_values in series.items():
        if not isinstance(raw_date, str) or not isinstance(raw_values, dict):
            raise ValueError("Alpha Vantage daily row has an invalid shape")
        raw_close = raw_values.get("4. close")
        try:
            parsed[date.fromisoformat(raw_date)] = Decimal(str(raw_close))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("Alpha Vantage close value is invalid") from error
    return parsed


def compare_alpha_vantage(
    repository: MarketDataRepository,
    symbols: tuple[str, ...],
    *,
    api_key: str,
    as_of: date | None = None,
    timeout_seconds: int = 30,
    relative_tolerance: Decimal = Decimal("0.0001"),
) -> dict[str, object]:
    """Compare recent raw closes without writing secondary data to canonical tables."""

    if not api_key:
        raise ValueError("ALPHAVANTAGE_API_KEY is required for second-source validation")
    end_date = (as_of or date.today()) + timedelta(days=1)
    start_date = end_date - timedelta(days=180)
    results: list[dict[str, object]] = []
    total_matches = 0
    total_mismatches = 0
    for symbol in symbols:
        secondary = _fetch_alpha_vantage(symbol, api_key, timeout_seconds)
        canonical = {
            row["session_date"]: Decimal(row["close"])
            for row in repository.bars_for_symbol(symbol, start_date, end_date)
        }
        overlap = sorted(set(canonical).intersection(secondary))[-5:]
        comparisons: list[dict[str, object]] = []
        for session in overlap:
            yahoo_close = canonical[session]
            alpha_close = secondary[session]
            relative_difference = abs(yahoo_close - alpha_close) / alpha_close
            matches = relative_difference <= relative_tolerance
            total_matches += int(matches)
            total_mismatches += int(not matches)
            comparisons.append(
                {
                    "session_date": session.isoformat(),
                    "canonical_yahoo_close": str(yahoo_close),
                    "alpha_vantage_close": str(alpha_close),
                    "relative_difference": str(relative_difference),
                    "matches": matches,
                }
            )
        results.append(
            {
                "symbol": symbol,
                "overlap_count": len(overlap),
                "comparisons": comparisons,
            }
        )
    return {
        "primary_source": "yahoo_finance",
        "validation_source": "alpha_vantage",
        "persisted": False,
        "relative_tolerance": str(relative_tolerance),
        "matches": total_matches,
        "mismatches": total_mismatches,
        "symbols": results,
    }
