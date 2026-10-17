import numpy as np
import pandas as pd

from research import trend_etf as te


def test_the_rule_acts_on_yesterdays_close_not_todays():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    close = pd.Series(np.r_[np.linspace(100, 150, 250), np.full(150, 75.0)], index=idx)
    r = te.trend_returns(close)
    drop = close.index[250]  # the crash bar: yesterday's close was still above its average
    assert r[drop] < -0.4  # the rule is still long on the day the drop lands
    assert r.dropna().index[0] == idx[200]  # nothing is traded before the SMA exists


def test_alpha_beta_recovers_a_known_relationship():
    rng = np.random.default_rng(1)
    b = pd.Series(rng.normal(0, 0.01, 3000), index=pd.date_range("2010-01-01", periods=3000, freq="B"))
    s = 0.5 * b + 0.0004
    a, beta, t = te.alpha_beta(s, b)
    assert abs(beta - 0.5) < 1e-6 and abs(a - 0.0004) < 1e-6
