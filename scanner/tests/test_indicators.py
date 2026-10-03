import numpy as np
import pandas as pd
import pytest

from scanner.indicators import crossed_above, crossed_below, ema, macd, rsi

# Classic Wilder/StockCharts RSI worked example (14-period). StockCharts rounds its
# intermediate averages, so its published values sit ~0.07 above the exact result.
WILDER_CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
]
WILDER_RSI = [70.53, 66.32, 66.55, 69.41, 66.36, 57.97]


def test_rsi_matches_wilder_reference():
    out = rsi(pd.Series(WILDER_CLOSES), 14)
    assert out.iloc[:14].isna().all()
    assert out.iloc[14:].round(2).tolist() == pytest.approx(WILDER_RSI, abs=0.1)


def test_rsi_rising_series_is_100_and_falling_is_0():
    up = pd.Series(np.arange(1.0, 40.0))
    down = pd.Series(np.arange(40.0, 1.0, -1.0))
    assert rsi(up).iloc[-1] == 100.0
    assert rsi(down).iloc[-1] == 0.0


def test_rsi_flat_series_is_50_not_nan():
    out = rsi(pd.Series([10.0] * 40))
    assert out.iloc[-1] == 50.0


def test_rsi_short_series_is_all_nan():
    assert rsi(pd.Series([1.0, 2.0, 3.0])).isna().all()


def test_ema_of_constant_is_constant():
    assert ema(pd.Series([5.0] * 30), 10).iloc[-1] == pytest.approx(5.0)


def test_macd_hist_is_line_minus_signal():
    close = pd.Series(np.linspace(100, 130, 80) + np.sin(np.arange(80)))
    m = macd(close)
    assert (m["hist"] - (m["macd"] - m["signal"])).abs().max() < 1e-12
    # Hand check of the 12/26 EMA difference on the last bar.
    expected = ema(close, 12).iloc[-1] - ema(close, 26).iloc[-1]
    assert m["macd"].iloc[-1] == pytest.approx(expected)


def test_crossed_above_and_below():
    s = pd.Series([25.0, 19.0, 21.0, 18.0])
    assert crossed_above(s, 2, 20) is True
    assert crossed_above(s, 1, 20) is False
    assert crossed_below(s, 1, 20) is True
    assert crossed_below(s, 2, 20) is False


def test_crossed_with_nan_is_false():
    s = pd.Series([np.nan, 21.0])
    assert crossed_above(s, 1, 20) is False
    assert crossed_below(s, 1, 20) is False
