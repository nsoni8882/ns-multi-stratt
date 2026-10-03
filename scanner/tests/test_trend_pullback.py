import numpy as np
import pandas as pd
import pytest

from scanner.strategies.base import HIGH, LOW, STANDARD
from scanner.strategies.trend_pullback import (RSI_BUY_LEVEL, TrendPullback, TrendPullbackConfig, VARIANTS,
                                               dip_depth, rule_side)
from scanner.tests.conftest import make_df


def series(values):
    return pd.Series(values, dtype=float)


def test_rule_buy_in_uptrend_when_rsi_crosses_40():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([38, 41]), 1) == ("BUY", STANDARD)


def test_rule_buy_blocked_without_uptrend():
    ema50, ema200 = series([105, 105]), series([100, 100])
    assert rule_side(series([90, 90]), ema50, ema200, series([38, 41]), 1) is None  # close below 200 EMA
    assert rule_side(series([110, 110]), series([95, 95]), ema200, series([38, 41]), 1) is None  # 50 below 200


def test_rule_sell_in_downtrend_when_rsi_crosses_below_60():
    close, ema50, ema200 = series([90, 90]), series([95, 95]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([62, 59]), 1) == ("SELL", LOW)


def test_rule_no_signal_without_cross():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([45, 46]), 1) is None


def _uptrend_with_dip():
    up = 100 * np.cumprod(1 + 0.002 + 0.003 * np.sin(np.arange(420) / 3))
    dip = up[-1] * np.cumprod(np.full(3, 1 - 0.015))
    return list(np.concatenate([up, dip, [dip[-1] * 1.01]]))


def test_evaluate_buy_on_pullback_in_uptrend():
    sig = TrendPullback().evaluate(make_df(_uptrend_with_dip()))
    assert sig is not None and sig.side == "BUY" and sig.bars_ago == 0
    assert sig.details["ema50"] > sig.details["ema200"]
    # The level that fired it travels with the signal, so the site can say why without
    # restating a threshold of its own.
    assert sig.details["rsi_level"] == RSI_BUY_LEVEL
    assert sig.conviction == STANDARD


def test_evaluate_sell_on_rally_in_downtrend():
    dn = 100 * np.cumprod(1 - 0.002 - 0.003 * np.sin(np.arange(420) / 3))
    rally = dn[-1] * np.cumprod(np.full(3, 1 + 0.015))
    closes = list(np.concatenate([dn, rally, [rally[-1] * 0.99]]))
    sig = TrendPullback().evaluate(make_df(closes))
    assert sig is not None and sig.side == "SELL" and sig.bars_ago == 0
    assert sig.conviction == LOW  # the short leg showed no measurable edge in backtesting


def test_needs_400_bars():
    """EMA200 is still seed-biased before ~400 bars, so short histories are skipped."""
    assert TrendPullback().evaluate(make_df(_uptrend_with_dip()[-399:])) is None
    assert TrendPullback().evaluate(make_df(_uptrend_with_dip())) is not None


def test_flat_prices_give_no_signal():
    assert TrendPullback().evaluate(make_df([100.0] * 500)) is None


# --- configurable gates (research/measure.py is the only non-default caller) ---


def test_default_config_is_the_shipped_rule():
    cfg = TrendPullbackConfig()
    assert cfg.adx_min is None and cfg.depth_tiers == () and cfg.require_ema50_above_ema200
    assert cfg.rsi_buy_level == 40 and not cfg.require_rising_ema200


def test_adx_gate_blocks_a_signal_in_chop():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    r = series([38, 41])
    cfg = TrendPullbackConfig(adx_min=20)
    assert rule_side(close, ema50, ema200, r, 1, series([30, 30]), cfg=cfg) == ("BUY", STANDARD)
    assert rule_side(close, ema50, ema200, r, 1, series([30, 12]), cfg=cfg) is None
    assert rule_side(close, ema50, ema200, r, 1, series([30, np.nan]), cfg=cfg) is None


def test_adx_gate_requires_an_adx_series():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    with pytest.raises(ValueError, match="no ADX series"):
        rule_side(close, ema50, ema200, series([38, 41]), 1, None, cfg=TrendPullbackConfig(adx_min=20))


def test_rsi_level_is_configurable():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    cfg = TrendPullbackConfig(rsi_buy_level=35)
    assert rule_side(close, ema50, ema200, series([38, 41]), 1, None, cfg=cfg) is None  # never reached 35
    assert rule_side(close, ema50, ema200, series([33, 36]), 1, None, cfg=cfg) == ("BUY", STANDARD)


def test_dropping_the_ema50_condition_admits_a_signal_it_blocked():
    close, ema200, r = series([110, 110]), series([100, 100]), series([38, 41])
    ema50 = series([95, 95])  # 50 still below 200
    assert rule_side(close, ema50, ema200, r, 1) is None
    cfg = TrendPullbackConfig(require_ema50_above_ema200=False)
    assert rule_side(close, ema50, ema200, r, 1, None, cfg=cfg) == ("BUY", STANDARD)


def test_rising_ema200_gate_blocks_a_falling_trend_line():
    close, ema50, r = series([110] * 4), series([105] * 4), series([0, 0, 38, 41])
    cfg = TrendPullbackConfig(require_rising_ema200=True, rising_lookback=2)
    assert rule_side(close, ema50, series([100, 100, 101, 102]), r, 3, None, cfg=cfg) == ("BUY", STANDARD)
    assert rule_side(close, ema50, series([100, 100, 99, 98]), r, 3, None, cfg=cfg) is None


def test_dip_depth_traces_the_unbroken_sub_level_run():
    r = series([50, 45, 38, 31, 36, 42])
    assert dip_depth(r, 5, 40) == 31  # bars 2-4 are the dip
    assert dip_depth(r, 5, 40, max_lookback=1) == 36  # only bar 4 is in view


def test_dip_depth_stops_at_the_level_not_at_an_earlier_dip():
    r = series([25, 50, 38, 42])
    assert dip_depth(r, 3, 40) == 38  # the 25 is on the far side of a >=40 bar


def test_depth_tiers_grade_conviction_by_how_deep_the_pullback_went():
    close, ema50, ema200 = series([110] * 5), series([105] * 5), series([100] * 5)
    cfg = VARIANTS["tiered-deep-is-strong"]
    deep = series([50, 45, 38, 28, 41])
    shallow = series([50, 45, 39, 38, 41])
    mid = series([50, 45, 38, 33, 41])
    assert rule_side(close, ema50, ema200, deep, 4, None, cfg=cfg) == ("BUY", HIGH)
    assert rule_side(close, ema50, ema200, mid, 4, None, cfg=cfg) == ("BUY", STANDARD)
    assert rule_side(close, ema50, ema200, shallow, 4, None, cfg=cfg) == ("BUY", LOW)


def test_evaluate_with_adx_gate_reports_adx_in_details():
    sig = TrendPullback(TrendPullbackConfig(adx_min=5)).evaluate(make_df(_uptrend_with_dip()))
    assert sig is not None and sig.side == "BUY" and "adx" in sig.details


def test_evaluate_with_impossible_adx_gate_finds_nothing():
    assert TrendPullback(TrendPullbackConfig(adx_min=99)).evaluate(make_df(_uptrend_with_dip())) is None


def test_every_variant_evaluates_without_error():
    df = make_df(_uptrend_with_dip())
    for label, cfg in VARIANTS.items():
        TrendPullback(cfg).evaluate(df)  # must not raise


# --- structural pullback: did price actually come back to a mean? ---

def test_near_ema50_gate_rejects_an_extended_name():
    """Same RSI dip, two very different setups: one sitting on the EMA50, one 25% above it."""
    ema50, ema200, r = series([105, 105]), series([100, 100]), series([38, 41])
    cfg = TrendPullbackConfig(max_ema50_distance=0.02)
    assert rule_side(series([106, 106]), ema50, ema200, r, 1, None, None, cfg=cfg) == ("BUY", STANDARD)
    assert rule_side(series([131, 131]), ema50, ema200, r, 1, None, None, cfg=cfg) is None
    # unchanged without the gate
    assert rule_side(series([131, 131]), ema50, ema200, r, 1) == ("BUY", STANDARD)


def test_near_ema50_gate_boundary_is_inclusive():
    ema50, ema200, r = series([100, 100]), series([90, 90]), series([38, 41])
    cfg = TrendPullbackConfig(max_ema50_distance=0.02)
    assert rule_side(series([102, 102]), ema50, ema200, r, 1, None, None, cfg=cfg) is not None
    assert rule_side(series([102.01, 102.01]), ema50, ema200, r, 1, None, None, cfg=cfg) is None


def test_at_ema50_gate_requires_price_at_or_under_the_mean():
    ema50, ema200, r = series([100, 100]), series([90, 90]), series([38, 41])
    cfg = VARIANTS["at-ema50"]
    assert rule_side(series([99, 99]), ema50, ema200, r, 1, None, None, cfg=cfg) is not None
    assert rule_side(series([101, 101]), ema50, ema200, r, 1, None, None, cfg=cfg) is None


def test_below_ema20_gate_requires_the_dip_to_reach_the_short_mean():
    ema50, ema200, r = series([105, 105]), series([100, 100]), series([38, 41])
    cfg = TrendPullbackConfig(require_below_ema20=True)
    close = series([110, 110])
    assert rule_side(close, ema50, ema200, r, 1, None, series([112, 112]), cfg=cfg) == ("BUY", STANDARD)
    assert rule_side(close, ema50, ema200, r, 1, None, series([108, 108]), cfg=cfg) is None
    assert rule_side(close, ema50, ema200, r, 1, None, series([np.nan, np.nan]), cfg=cfg) is None


def test_below_ema20_gate_requires_an_ema20_series():
    ema50, ema200, r = series([105, 105]), series([100, 100]), series([38, 41])
    with pytest.raises(ValueError, match="no EMA20 series"):
        rule_side(series([110, 110]), ema50, ema200, r, 1, None, None,
                  cfg=TrendPullbackConfig(require_below_ema20=True))


def test_structural_gates_do_not_touch_the_short_leg():
    """These conditions describe a pullback in an uptrend; the SELL leg must be unaffected."""
    close, ema50, ema200, r = series([90, 90]), series([95, 95]), series([100, 100]), series([62, 59])
    for cfg in (VARIANTS["at-ema50"], VARIANTS["below-ema20"], VARIANTS["near-ema50-2pct"]):
        assert rule_side(close, ema50, ema200, r, 1, None, series([80, 80]), cfg=cfg) == ("SELL", LOW)


def test_evaluate_supplies_ema20_when_the_gate_needs_it():
    strat = TrendPullback(TrendPullbackConfig(require_below_ema20=True))
    assert strat.indicators(make_df(_uptrend_with_dip()))["ema20"] is not None
    assert TrendPullback().indicators(make_df(_uptrend_with_dip()))["ema20"] is None


def test_params_cover_every_config_field_so_the_fingerprint_cannot_miss_one():
    """A new gate that is not in `params` would change signals without changing the
    fingerprint, which is the one thing rules_version exists to prevent."""
    from dataclasses import fields
    params = TrendPullback().params
    for f in fields(TrendPullbackConfig):
        assert f.name in params, f"{f.name} missing from TrendPullback.params"
    assert "min_bars" in params


def test_rules_version_changes_when_a_gate_changes_and_not_otherwise():
    from scanner.strategies.base import rules_version
    shipped = rules_version(TrendPullback().params)
    assert shipped == rules_version(TrendPullback(TrendPullbackConfig()).params)
    assert shipped != rules_version(TrendPullback(TrendPullbackConfig(adx_min=20)).params)
    assert shipped != rules_version(TrendPullback(TrendPullbackConfig(rsi_buy_level=35)).params)
    assert len(shipped) == 12
