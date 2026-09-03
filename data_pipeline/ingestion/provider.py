"""Historical provider contracts and the Stage 1 Yahoo Finance adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from importlib.metadata import version
from typing import Any, Protocol, cast

import pandas as pd
import yfinance as yf

from data_pipeline.ingestion.errors import NonRetryableProviderError, RetryableProviderError
from data_pipeline.schema import IngestionRequest, Instrument, SourceBatch

YAHOO_ADAPTER_VERSION = "1"
YAHOO_COLUMNS = (
    "timestamp",
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
    "Volume",
    "Dividends",
    "Stock Splits",
    "Capital Gains",
)


class HistoricalProvider(Protocol):
    """Boundary implemented by historical market-data sources."""

    adapter_version: str
    library_version: str

    def fetch(self, instrument: Instrument, request: IngestionRequest) -> SourceBatch:
        """Fetch one end-exclusive range without applying canonical transformations."""


def _stringify(value: object) -> str | None:
    """Convert one provider cell to a stable loss-minimizing string."""

    if bool(pd.isna(cast(Any, value))):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def _looks_retryable(error: BaseException) -> bool:
    """Recognize yfinance transport/rate-limit failures without broad retries."""

    name = type(error).__name__.lower()
    message = str(error).lower()
    transient_terms = (
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "rate limit",
        "too many requests",
        "429",
        "502",
        "503",
        "504",
    )
    return "ratelimit" in name or any(term in message for term in transient_terms)


class YahooFinanceProvider:
    """Explicitly configured single-symbol daily-history adapter."""

    adapter_version = YAHOO_ADAPTER_VERSION
    library_version = version("yfinance")

    def __init__(self, *, timeout_seconds: int) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch(self, instrument: Instrument, request: IngestionRequest) -> SourceBatch:
        """Fetch raw daily OHLCV and corporate-action columns from Yahoo Finance."""

        parameters: dict[str, object] = {
            "start": request.start_date.isoformat(),
            "end": request.end_date.isoformat(),
            "interval": request.interval_code.value,
            "auto_adjust": False,
            "back_adjust": False,
            "actions": True,
            "repair": False,
            "keepna": True,
            "prepost": False,
            "rounding": False,
            "timeout": self._timeout_seconds,
            "raise_errors": True,
        }
        try:
            frame = yf.Ticker(instrument.source_symbol).history(**parameters)
        except Exception as error:
            if _looks_retryable(error):
                raise RetryableProviderError(str(error)) from error
            raise NonRetryableProviderError(str(error)) from error

        if isinstance(frame.columns, pd.MultiIndex):
            raise NonRetryableProviderError(
                "Unexpected multi-level columns from single-symbol request"
            )

        materialized = frame.copy()
        materialized.index.name = "timestamp"
        materialized = materialized.reset_index()
        for column in YAHOO_COLUMNS:
            if column not in materialized.columns:
                materialized[column] = None
        materialized = materialized.loc[:, list(YAHOO_COLUMNS)]

        rows = tuple(
            {column: _stringify(row[column]) for column in YAHOO_COLUMNS}
            for _, row in materialized.iterrows()
        )
        metadata: Mapping[str, str] = {
            "adapter_version": self.adapter_version,
            "provider_library": "yfinance",
            "provider_library_version": self.library_version,
            "request_parameters": ",".join(
                f"{key}={parameters[key]}" for key in sorted(parameters)
            ),
        }
        return SourceBatch(
            source_name=instrument.source_name,
            source_symbol=instrument.source_symbol,
            interval_code=request.interval_code,
            requested_start=request.start_date,
            requested_end=request.end_date,
            fetched_at=datetime.now(UTC),
            columns=YAHOO_COLUMNS,
            rows=rows,
            metadata=dict(metadata),
        )
