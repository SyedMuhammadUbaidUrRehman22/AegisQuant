"""Golden-value and numerical edge tests for Stage 2 formulas."""

import math

import numpy as np
import pandas as pd
import pytest

from feature_engineering.features import (
    log_return,
    momentum,
    rolling_annualized_volatility,
    rolling_correlation,
    simple_return,
)


def test_returns_and_momentum_match_hand_calculation() -> None:
    prices = pd.Series([100.0, 110.0, 99.0])

    assert simple_return(prices).iloc[1:].tolist() == pytest.approx([0.1, -0.1])
    assert log_return(prices).iloc[1:].tolist() == pytest.approx([math.log(1.1), math.log(0.9)])
    assert momentum(prices, periods=2).iloc[2] == pytest.approx(-0.01)


def test_rolling_volatility_uses_complete_log_return_window_and_sample_std() -> None:
    prices = pd.Series([100.0, 110.0, 99.0])
    expected = np.std([math.log(1.1), math.log(0.9)], ddof=1) * math.sqrt(252)

    actual = rolling_annualized_volatility(prices, window=2)

    assert actual.iloc[:2].isna().all()
    assert actual.iloc[2] == pytest.approx(expected)


def test_constant_windows_have_zero_volatility_and_undefined_correlation() -> None:
    prices = pd.Series([100.0, 100.0, 100.0])

    assert rolling_annualized_volatility(prices, window=2).iloc[2] == 0.0
    assert math.isnan(rolling_correlation(prices, prices, window=2).iloc[2])


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (lambda: momentum(pd.Series([1.0]), periods=0), "periods"),
        (lambda: rolling_annualized_volatility(pd.Series([1.0]), window=1), "window"),
        (lambda: rolling_correlation(pd.Series([1.0]), pd.Series([1.0]), window=1), "window"),
    ],
)
def test_invalid_parameters_fail(operation: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        operation()  # type: ignore[operator]
