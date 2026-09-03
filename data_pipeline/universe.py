"""Approved Stage 1 instrument universe."""

from __future__ import annotations

from data_pipeline.schema import AssetClass, InstrumentSeed

SOURCE_NAME = "yahoo_finance"
TIMEZONE = "America/New_York"
CALENDAR = "XNYS"
CURRENCY = "USD"


def _etf(symbol: str, name: str, venue_mic: str) -> InstrumentSeed:
    return InstrumentSeed(
        canonical_symbol=symbol,
        name=name,
        asset_class=AssetClass.ETF,
        venue_mic=venue_mic,
        currency=CURRENCY,
        timezone=TIMEZONE,
        calendar_code=CALENDAR,
        source_name=SOURCE_NAME,
        source_symbol=symbol,
    )


STAGE_1_UNIVERSE: tuple[InstrumentSeed, ...] = (
    _etf("SPY", "SPDR S&P 500 ETF Trust", "ARCX"),
    _etf("QQQ", "Invesco QQQ Trust", "XNAS"),
    _etf("IWM", "iShares Russell 2000 ETF", "ARCX"),
    _etf("DIA", "SPDR Dow Jones Industrial Average ETF Trust", "ARCX"),
    _etf("EFA", "iShares MSCI EAFE ETF", "ARCX"),
    _etf("EEM", "iShares MSCI Emerging Markets ETF", "ARCX"),
    _etf("VNQ", "Vanguard Real Estate ETF", "ARCX"),
    _etf("TLT", "iShares 20+ Year Treasury Bond ETF", "XNAS"),
    _etf("IEF", "iShares 7-10 Year Treasury Bond ETF", "XNAS"),
    _etf("SHY", "iShares 1-3 Year Treasury Bond ETF", "XNAS"),
    _etf("LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "XNAS"),
    _etf("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "ARCX"),
    _etf("GLD", "SPDR Gold Shares", "ARCX"),
    _etf("SLV", "iShares Silver Trust", "ARCX"),
    _etf("USO", "United States Oil Fund", "ARCX"),
    _etf("XLE", "Energy Select Sector SPDR Fund", "ARCX"),
    _etf("XLF", "Financial Select Sector SPDR Fund", "ARCX"),
    _etf("XLK", "Technology Select Sector SPDR Fund", "ARCX"),
    _etf("XLP", "Consumer Staples Select Sector SPDR Fund", "ARCX"),
    _etf("XLU", "Utilities Select Sector SPDR Fund", "ARCX"),
)

PILOT_SYMBOLS: tuple[str, ...] = ("SPY", "QQQ", "IWM", "TLT", "GLD")


def universe_by_symbol() -> dict[str, InstrumentSeed]:
    """Return approved reference metadata keyed by canonical symbol."""

    return {instrument.canonical_symbol: instrument for instrument in STAGE_1_UNIVERSE}
