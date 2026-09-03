"""Deterministic Stage 1 test-data factories."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from data_pipeline.schema import AssetClass, Instrument, SourceBatch


def instrument(*, instrument_id: int = 1, symbol: str = "SPY") -> Instrument:
    return Instrument(
        instrument_id=instrument_id,
        canonical_symbol=symbol,
        name=f"{symbol} test instrument",
        asset_class=AssetClass.ETF,
        venue_mic="ARCX",
        currency="USD",
        timezone="America/New_York",
        calendar_code="XNYS",
        source_name="yahoo_finance",
        source_symbol=symbol,
        valid_from=None,
        valid_to=None,
        active=True,
    )


def source_row(
    session: date,
    *,
    open_price: str = "100",
    high: str = "102",
    low: str = "99",
    close: str = "101",
    adjusted_close: str = "100.5",
    volume: str = "1000000",
    dividend: str = "0",
    split: str = "0",
) -> dict[str, str | None]:
    timestamp = datetime.combine(session, time.min, tzinfo=ZoneInfo("America/New_York"))
    return {
        "timestamp": timestamp.isoformat(),
        "Open": open_price,
        "High": high,
        "Low": low,
        "Close": close,
        "Adj Close": adjusted_close,
        "Volume": volume,
        "Dividends": dividend,
        "Stock Splits": split,
        "Capital Gains": "0",
    }


def source_batch(
    rows: tuple[dict[str, str | None], ...],
    *,
    symbol: str = "SPY",
    start: date = date(2024, 1, 2),
    end: date = date(2024, 1, 5),
) -> SourceBatch:
    columns = (
        tuple(rows[0])
        if rows
        else (
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
    )
    return SourceBatch(
        source_name="yahoo_finance",
        source_symbol=symbol,
        interval_code="1d",
        requested_start=start,
        requested_end=end,
        fetched_at=datetime(2024, 1, 6, tzinfo=UTC),
        columns=columns,
        rows=rows,
        metadata={"fixture": "true"},
    )
