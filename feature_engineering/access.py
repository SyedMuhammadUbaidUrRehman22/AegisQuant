"""Read-only access to the canonical Stage 1 market-data contract."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import Engine, select

from data_pipeline.schema.tables import instruments, ohlcv_bars


class CanonicalFeatureInput:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def bars_as_of(self, as_of: datetime) -> pd.DataFrame:
        """Return completed canonical daily bars only; never fetch or fill data."""

        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        statement = (
            select(
                ohlcv_bars.c.instrument_id,
                instruments.c.canonical_symbol,
                ohlcv_bars.c.bar_end_at,
                ohlcv_bars.c.adjusted_close,
                ohlcv_bars.c.volume,
            )
            .join(instruments, instruments.c.instrument_id == ohlcv_bars.c.instrument_id)
            .where(ohlcv_bars.c.interval_code == "1d", ohlcv_bars.c.bar_end_at <= as_of)
            .order_by(ohlcv_bars.c.instrument_id, ohlcv_bars.c.bar_end_at)
        )
        with self._engine.connect() as connection:
            rows = tuple(connection.execute(statement).mappings())
        return pd.DataFrame(
            rows,
            columns=("instrument_id", "canonical_symbol", "bar_end_at", "adjusted_close", "volume"),
        )
