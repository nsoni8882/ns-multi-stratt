import numpy as np
import pandas as pd
import pytest

from scanner.strategies.base import HIGH, LOW, STANDARD
from scanner.strategies.macd_rsi_reversal import (RSI_LOW, RSI_LOW_STANDARD, VARIANTS,
                                                  MacdRsiReversal, off_high, recovery_bars,
                                                  rule_side)
from scanner.tests.conftest import make_df


def series(values):
    return pd.Series(values, dtype=float)


def buy_inputs():
    # Bar index 9 is the signal bar. Histogram was deep (<= lo) at bar 5, then rose 3 bars, still <= 0.
    hist = series([0, 0, 0, 0, -5, -6, -5, -4, -3, -2])
    lo = series([-5.5] * 10)
    hi = series([5.5] * 10)
    rsi = series([50, 50, 50, 50, 30, 25, 22, 21, 19, 21])
    return hist, lo, hi, rsi


def test_rule_buy_below_20_is_high_conviction():
    hist, lo, hi, rsi = buy_inputs()
    assert rule_side(hist, lo, hi, rsi, 9) == ("BUY", HIGH)


def test_rule_buy_between_20_and_25_is_standard_conviction():
    hist, lo, hi, rsi = buy_inputs()
    rsi.iloc[8], rsi.iloc[9] = 23, 26  # crosses 25 but was never below 20
    assert rule_side(hist, lo, hi, rsi, 9) == ("BUY", STANDARD)


def test_rule_buy_crossing_both_tiers_takes_the_deeper_one():
    hist, lo, hi, rsi = buy_inputs()
    rsi.iloc[8], rsi.iloc[9] = 19, 26
    assert rule_side(hist, lo, hi, rsi, 9) == ("BUY", HIGH)


def test_rule_buy_above_25_gives_nothing():
    hist, lo, hi, rsi = buy_inputs()
    rsi.iloc[8], rsi.iloc[9] = 28, 31  # a 30 cross is not a tier: the edge is gone by then
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_buy_needs_deep_histogram():
    hist, lo, hi, rsi = buy_inputs()
    assert rule_side(hist, series([-10.0] * 10), hi, rsi, 9) is None


def test_rule_buy_needs_two_rising_bars():
    hist, lo, hi, rsi = buy_inputs()
    hist.iloc[8] = -1  # bar 8 above bar 9 -> not rising into the signal bar
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_buy_needs_histogram_not_above_zero():
    hist, lo, hi, rsi = buy_inputs()
    hist = hist + 4  # signal bar histogram is now > 0
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_buy_needs_rsi_cross_on_signal_bar():
    hist, lo, hi, rsi = buy_inputs()
    rsi.iloc[8], rsi.iloc[9] = 26, 27  # above both tiers on the prior bar: no cross
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_sell_is_the_mirror_and_low_conviction():
    hist, lo, hi, rsi = buy_inputs()
    # Published again, but pinned to LOW: the leg measured +0.05% (t +0.09), which is
    # nothing, and `long-only` is the variant that reproduces that measurement.
    assert rule_side(-hist, -hi, -lo, 100 - rsi, 9) == ("SELL", LOW)
    assert rule_side(-hist, -hi, -lo, 100 - rsi, 9, cfg=VARIANTS["long-only"]) is None


def test_sell_has_no_standard_tier():
    """A 75 cross is deliberately not a signal: it added volume with no measurable edge."""
    hist, lo, hi, rsi = buy_inputs()
    r = 100 - rsi
    r.iloc[8], r.iloc[9] = 77, 74
    assert rule_side(-hist, -hi, -lo, r, 9) is None


def test_evaluate_buy_on_crash_then_bounce():
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    closes = list(np.concatenate([up, down, [down[-1] * 1.06]]))
    sig = MacdRsiReversal().evaluate(make_df(closes))
    assert sig is not None
    assert sig.side == "BUY" and sig.bars_ago == 0
    assert sig.entry_price == closes[-1]
    assert sig.fired_at == make_df(closes)["close_time"].iloc[-1]
    assert sig.details["rsi"] > 20 and sig.details["macd_hist"] <= 0
    # The level that fired it travels with the signal, so the site can say why without
    # restating a threshold of its own.
    assert sig.details["rsi_level"] in (RSI_LOW, RSI_LOW_STANDARD)
    assert sig.conviction in (HIGH, STANDARD)


def test_signal_window_is_three_bars():
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    closes = list(np.concatenate([up, down, [down[-1] * 1.06]]))
    strat = MacdRsiReversal()
    assert strat.evaluate(make_df(closes + [closes[-1]] * 2)).bars_ago == 2
    assert strat.evaluate(make_df(closes + [closes[-1]] * 3)) is None


def test_too_few_bars_returns_none():
    assert MacdRsiReversal().evaluate(make_df([100.0] * 50)) is None


def test_flat_prices_give_no_signal():
    assert MacdRsiReversal().evaluate(make_df([100.0] * 300)) is None


def test_nan_prices_do_not_crash_or_signal():
    closes = [100.0] * 300
    closes[-5] = float("nan")
    assert MacdRsiReversal().evaluate(make_df(closes)) is None


def test_signal_details_describe_this_name_not_the_rule():
    """The card's explanation is per stock, so the numbers behind it travel on the signal.

    Each of these is descriptive: the rule reads none of them, which is why they are absent
    from `params` and cannot change which bars fire.
    """
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    closes = list(np.concatenate([up, down, [down[-1] * 1.06]]))
    sig = MacdRsiReversal().evaluate(make_df(closes))
    assert sig is not None and sig.side == "BUY"
    d = sig.details
    # The rule needs two consecutive up-moves in the histogram; this records how many there
    # actually were, which is 2 at the minimum and more on a name that has been turning longer.
    assert d["recovery_bars"] >= 2
    assert d["hist_trough"] <= d["macd_hist"]  # the low it is climbing out of
    assert d["rsi_trough"] <= d["rsi"]
    assert d["off_high"] < 0  # it is below its recent high, by construction of this fixture
    params = MacdRsiReversal().params
    assert not {"recovery_bars", "hist_trough", "rsi_trough", "off_high"} & set(params)


def test_recovery_bars_counts_only_the_unbroken_run():
    hist = pd.Series([0.0, -1.0, -0.8, -0.9, -0.5, -0.2])
    assert recovery_bars(hist, 5) == 2  # -0.9 -> -0.5 -> -0.2; the -0.8 -> -0.9 dip stops it
    assert recovery_bars(hist, 1) == 0


def test_off_high_is_the_decline_from_the_window_peak():
    close = pd.Series([100.0] * 10 + [50.0])
    assert off_high(close, 10) == pytest.approx(-0.5)
