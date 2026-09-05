"""Pure, vectorized price feature formulas."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def simple_return[T: (pd.Series, pd.DataFrame)](prices: T) -> T:
    """Return close-to-close arithmetic returns without filling missing values."""

    return prices.div(prices.shift(1)).sub(1.0)


def log_return[T: (pd.Series, pd.DataFrame)](prices: T) -> T:
    """Return close-to-close natural-log returns without filling missing values."""

    return cast(T, np.log(prices)).sub(cast(T, np.log(prices.shift(1))))


def rolling_annualized_volatility[T: (pd.Series, pd.DataFrame)](
    prices: T, *, window: int, annualization_factor: int = 252
) -> T:
    """Return annualized sample volatility over complete rolling log-return windows."""

    if window < 2 or annualization_factor <= 0:
        raise ValueError("window must be at least 2 and annualization_factor must be positive")
    return (
        log_return(prices)
        .rolling(window, min_periods=window)
        .std(ddof=1)
        .mul(np.sqrt(float(annualization_factor)))
    )


def momentum[T: (pd.Series, pd.DataFrame)](prices: T, *, periods: int) -> T:
    """Return point-to-point arithmetic price momentum over observed periods."""

    if periods < 1:
        raise ValueError("periods must be positive")
    return prices.div(prices.shift(periods)).sub(1.0)


def rolling_correlation[T: (pd.Series, pd.DataFrame)](left: T, right: T, *, window: int) -> T:
    """Return rolling sample correlation on aligned indices and asset columns."""

    if window < 2:
        raise ValueError("window must be at least 2")
    aligned_left, aligned_right = left.align(right, join="inner")
    result = aligned_left.rolling(window, min_periods=window).corr(aligned_right, pairwise=False)
    nonconstant = aligned_left.rolling(window, min_periods=window).var(ddof=1).gt(
        0
    ) & aligned_right.rolling(window, min_periods=window).var(ddof=1).gt(0)
    return result.where(np.isfinite(result) & nonconstant).clip(lower=-1.0, upper=1.0)
