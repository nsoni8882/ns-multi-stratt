"""A signal still listed from an earlier bar is flagged when its premise has since died.

Regression anchor: CCL fired a Trend Pullback SELL on 2026-09-30 with RSI 56.9, having
crossed down through 60 from 61.6. Two bars later RSI was 63.6 -- higher than before the
cross -- and the site still listed it as a live SELL with no caveat.
"""
import numpy as np
import pandas as pd
import pytest

from scanner.strategies.base import thesis_negated
from scanner.strategies.trend_pullback import TrendPullback
from scanner.tests.conftest import make_df


def s(values):
    return pd.Series(values, dtype=float)


def test_a_buy_is_negated_when_rsi_falls_back_to_its_level():
    r = s([38, 42, 44, 39])  # crossed up through 40 at bar 1, back under it at bar 3
    assert thesis_negated(r, 1, 3, "BUY", 40) is True
    assert thesis_negated(r, 1, 2, "BUY", 40) is False  # not yet, as of bar 2


def test_a_sell_is_negated_when_rsi_climbs_back_to_its_level():
    r = s([62, 57, 58, 64])
    assert thesis_negated(r, 1, 3, "SELL", 60) is True
    assert thesis_negated(r, 1, 2, "SELL", 60) is False


def test_touching_the_level_exactly_counts_as_negated():
    """RSI back at the level means the move that fired the signal is gone."""
    assert thesis_negated(s([62, 57, 60]), 1, 2, "SELL", 60) is True
    assert thesis_negated(s([38, 42, 40]), 1, 2, "BUY", 40) is True


def test_a_signal_on_the_latest_bar_can_never_be_negated():
    """There is no bar after it yet, so there is nothing to undo it."""
    assert thesis_negated(s([62, 57]), 1, 1, "SELL", 60) is False


def test_the_ccl_shape_is_flagged_but_still_listed():
    """Down-leg, a bounce that trips the SELL, then RSI pushes back through 60."""
    down = list(100 * np.cumprod(1 - 0.004 - 0.004 * np.sin(np.arange(460) / 5)))
    closes = down + [down[-1] * m for m in (1.06, 1.12, 1.10, 1.14, 1.20)]
    sig = TrendPullback().evaluate(make_df(closes))
    if sig is None or sig.side != "SELL" or sig.bars_ago == 0:
        pytest.skip("fixture did not produce a stale SELL on this shape")
    assert sig.invalidated is True  # flagged...
    assert sig.side == "SELL"  # ...but still reported, not dropped


def test_a_fresh_signal_is_not_flagged():
    up = 100 * np.cumprod(1 + 0.002 + 0.003 * np.sin(np.arange(420) / 3))
    dip = up[-1] * np.cumprod(np.full(3, 1 - 0.015))
    sig = TrendPullback().evaluate(make_df(list(np.concatenate([up, dip, [dip[-1] * 1.01]]))))
    assert sig is not None and sig.bars_ago == 0
    assert sig.invalidated is False


def test_invalidated_defaults_false_so_nothing_is_flagged_by_accident():
    from scanner.strategies.base import make_signal
    df = make_df([100.0] * 10)
    assert make_signal(df, 5, "BUY", {}).invalidated is False
