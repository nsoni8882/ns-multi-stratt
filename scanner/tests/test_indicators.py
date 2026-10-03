import numpy as np
import pandas as pd
import pytest

from scanner.indicators import adx, crossed_above, crossed_below, ema, macd, rising, rsi

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


def _hlc(closes, width=0.005):
    c = pd.Series(closes, dtype=float)
    return c * (1 + width), c * (1 - width), c


def test_adx_is_nan_until_two_lengths_of_bars():
    out = adx(*_hlc(np.arange(100.0, 160.0)), 14)
    assert out.iloc[:28].isna().all()
    assert out.iloc[28:].notna().all()


def test_adx_short_series_is_all_nan():
    assert adx(*_hlc(np.arange(100.0, 110.0)), 14).isna().all()


def test_adx_of_monotone_trend_converges_to_100():
    """A series that only ever rises has no -DM, so -DI is 0, DX is 100 and ADX follows."""
    up = adx(*_hlc(np.arange(100.0, 200.0)), 14)
    down = adx(*_hlc(np.arange(200.0, 100.0, -1.0)), 14)
    assert up.iloc[-1] == pytest.approx(100.0, abs=0.5)
    assert down.iloc[-1] == pytest.approx(100.0, abs=0.5)  # direction-blind


def test_adx_of_flat_series_is_zero_not_nan():
    out = adx(*_hlc([50.0] * 60, width=0.0), 14)
    assert out.iloc[-1] == 0.0


def test_adx_of_chop_is_low_and_of_trend_is_high():
    chop = 100 + 2 * np.sin(np.arange(200) / 1.5)
    trend = 100 * np.cumprod(1 + np.full(200, 0.004))
    assert adx(*_hlc(chop), 14).iloc[-1] < 20
    assert adx(*_hlc(trend), 14).iloc[-1] > 40


def test_rising_compares_against_the_lookback_bar():
    s = pd.Series([1.0, 2.0, 3.0, 2.5])
    assert rising(s, 3, 1) is False  # 2.5 < 3.0 one bar back
    assert rising(s, 3, 3) is True  # 2.5 > 1.0 three bars back
    assert rising(s, 1, 5) is False  # not enough history
    assert rising(pd.Series([np.nan, 2.0]), 1, 1) is False
