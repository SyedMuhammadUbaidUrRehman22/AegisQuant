"""Network-free tests for the Yahoo Finance source adapter."""

from datetime import date
from typing import Any

import pandas as pd

from data_pipeline.ingestion.calendars import SessionCalendar
from data_pipeline.ingestion.normalization import normalize_source_batch
from data_pipeline.ingestion.provider import YahooFinanceProvider
from data_pipeline.schema import IngestionRequest
from tests.factories import instrument


def test_yahoo_adapter_sets_every_semantic_parameter(monkeypatch: Any) -> None:
    observed: dict[str, object] = {}
    index = pd.DatetimeIndex(["2024-01-02"], tz="America/New_York", name="Date")
    frame = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Adj Close": [100.5],
            "Volume": [1_000_000],
            "Dividends": [0.0],
            "Stock Splits": [0.0],
        },
        index=index,
    )

    class FakeTicker:
        def history(self, **parameters: object) -> pd.DataFrame:
            observed.update(parameters)
            return frame

    monkeypatch.setattr("data_pipeline.ingestion.provider.yf.Ticker", lambda _: FakeTicker())
    provider = YahooFinanceProvider(timeout_seconds=17)

    batch = provider.fetch(
        instrument(),
        IngestionRequest(
            canonical_symbol="SPY", start_date=date(2024, 1, 2), end_date=date(2024, 1, 3)
        ),
    )

    assert observed == {
        "start": "2024-01-02",
        "end": "2024-01-03",
        "interval": "1d",
        "auto_adjust": False,
        "back_adjust": False,
        "actions": True,
        "repair": False,
        "keepna": True,
        "prepost": False,
        "rounding": False,
        "timeout": 17,
        "raise_errors": True,
    }
    assert batch.rows[0]["timestamp"] == "2024-01-02T00:00:00-05:00"
    assert "Capital Gains" not in batch.rows[0]
    normalized = normalize_source_batch(batch, instrument(), SessionCalendar("XNYS"))
    assert "precision_rounded" not in {issue.code for issue in normalized.issues}
