"""Pure, vectorized price feature formulas."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def simple_return(prices: pd.Series) -> pd.Series:
    """Return close-to-close arithmetic returns without filling missing values."""

    return prices.div(prices.shift(1)).sub(1.0)


def log_return(prices: pd.Series) -> pd.Series:
    """Return close-to-close natural-log returns without filling missing values."""

    return cast(pd.Series, np.log(prices.div(prices.shift(1))))


def rolling_annualized_volatility(
    prices: pd.Series, *, window: int, annualization_factor: int = 252
) -> pd.Series:
    """Return annualized sample volatility over complete rolling log-return windows."""

    if window < 2 or annualization_factor <= 0:
        raise ValueError("window must be at least 2 and annualization_factor must be positive")
    return (
        log_return(prices)
        .rolling(window, min_periods=window)
        .std(ddof=1)
        .mul(np.sqrt(float(annualization_factor)))
    )


def momentum(prices: pd.Series, *, periods: int) -> pd.Series:
    """Return point-to-point arithmetic price momentum over observed periods."""

    if periods < 1:
        raise ValueError("periods must be positive")
    return prices.div(prices.shift(periods)).sub(1.0)


def rolling_correlation(left: pd.Series, right: pd.Series, *, window: int) -> pd.Series:
    """Return rolling sample correlation on exact inner-aligned timestamps."""

    if window < 2:
        raise ValueError("window must be at least 2")
    aligned = pd.concat((left, right), axis="columns", join="inner")
    result = aligned.iloc[:, 0].rolling(window, min_periods=window).corr(aligned.iloc[:, 1])
    return result.clip(lower=-1.0, upper=1.0)
