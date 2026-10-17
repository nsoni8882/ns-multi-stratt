import numpy as np
import pandas as pd

from research import trend_crypto as tc


def test_a_switch_costs_once_each_way_and_nothing_trades_before_the_average_exists():
    idx = pd.date_range("2020-01-01", periods=200, freq="D")
    close = pd.Series(np.r_[np.linspace(100, 200, 100), np.linspace(200, 100, 100)], index=idx)
    r = tc.trend_returns(close, cost=0.01)
    assert r.dropna().index[0] == idx[tc.SMA]
    free = tc.trend_returns(close, cost=0.0)
    assert abs((free - r).sum() - 0.01 * 2) < 1e-9  # one entry and one exit
