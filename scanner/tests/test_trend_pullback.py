import numpy as np
import pandas as pd

from scanner.strategies.trend_pullback import TrendPullback, rule_side
from scanner.tests.conftest import make_df


def series(values):
    return pd.Series(values, dtype=float)


def test_rule_buy_in_uptrend_when_rsi_crosses_40():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([38, 41]), 1) == "BUY"


def test_rule_buy_blocked_without_uptrend():
    ema50, ema200 = series([105, 105]), series([100, 100])
    assert rule_side(series([90, 90]), ema50, ema200, series([38, 41]), 1) is None  # close below 200 EMA
    assert rule_side(series([110, 110]), series([95, 95]), ema200, series([38, 41]), 1) is None  # 50 below 200


def test_rule_sell_in_downtrend_when_rsi_crosses_below_60():
    close, ema50, ema200 = series([90, 90]), series([95, 95]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([62, 59]), 1) == "SELL"


def test_rule_no_signal_without_cross():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([45, 46]), 1) is None


def _uptrend_with_dip():
    up = 100 * np.cumprod(1 + 0.002 + 0.003 * np.sin(np.arange(260) / 3))
    dip = up[-1] * np.cumprod(np.full(3, 1 - 0.015))
    return list(np.concatenate([up, dip, [dip[-1] * 1.01]]))


def test_evaluate_buy_on_pullback_in_uptrend():
    sig = TrendPullback().evaluate(make_df(_uptrend_with_dip()))
    assert sig is not None and sig.side == "BUY" and sig.bars_ago == 0
    assert sig.details["ema50"] > sig.details["ema200"]


def test_evaluate_sell_on_rally_in_downtrend():
    dn = 100 * np.cumprod(1 - 0.002 - 0.003 * np.sin(np.arange(260) / 3))
    rally = dn[-1] * np.cumprod(np.full(3, 1 + 0.015))
    closes = list(np.concatenate([dn, rally, [rally[-1] * 0.99]]))
    sig = TrendPullback().evaluate(make_df(closes))
    assert sig is not None and sig.side == "SELL" and sig.bars_ago == 0


def test_needs_250_bars():
    assert TrendPullback().evaluate(make_df(_uptrend_with_dip()[-200:])) is None


def test_flat_prices_give_no_signal():
    assert TrendPullback().evaluate(make_df([100.0] * 300)) is None
