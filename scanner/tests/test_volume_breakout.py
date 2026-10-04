"""The candidate third strategy. These pin the rule; whether it is worth publishing is a
question for research/measure.py and research/ACCEPTANCE.md, not for a unit test."""
import pandas as pd
import pytest

from scanner.strategies import STRATEGIES
from scanner.strategies.base import STANDARD
from scanner.strategies.volume_breakout import (VARIANTS, VolumeBreakout, VolumeBreakoutConfig,
                                                base_rvol, close_strength, is_breakout, rule_side)


def series(values):
    return pd.Series(values, dtype=float)


def inputs(rvol_last=3.0):
    close = series([100] * 49 + [110])
    high = series([101] * 49 + [111])
    low = series([99] * 49 + [104])
    rvol = series([1.0] * 49 + [rvol_last])
    return close, high, low, rvol


def test_a_loud_bar_fires_and_a_quiet_one_does_not():
    close, high, low, rvol = inputs()
    assert rule_side(close, high, low, rvol, 49) == ("BUY", STANDARD)
    assert rule_side(close, high, low, series([1.0] * 50), 49) is None


def test_an_unmeasured_bar_is_rejected_rather_than_passed():
    close, high, low, rvol = inputs()
    assert rule_side(close, high, low, series([1.0] * 49 + [float("nan")]), 49) is None


def test_breakout_gate_needs_the_highest_close_of_the_lookback():
    close, high, low, rvol = inputs()
    cfg = VolumeBreakoutConfig(require_breakout=True, breakout_lookback=50)
    assert rule_side(close, high, low, rvol, 49, cfg=cfg) is not None
    lower = series([100] * 48 + [120, 110])  # a higher close inside the window
    assert rule_side(lower, high, low, rvol, 49, cfg=cfg) is None


def test_uptrend_gate_requires_the_ema200_series():
    close, high, low, rvol = inputs()
    with pytest.raises(ValueError):
        rule_side(close, high, low, rvol, 49, cfg=VolumeBreakoutConfig(require_uptrend=True))


def test_close_strength_is_the_position_in_the_bar_range():
    assert close_strength(series([10]), series([0]), series([8]), 0) == pytest.approx(0.8)
    assert close_strength(series([5]), series([5]), series([5]), 0) == 0.5  # no range, no verdict


def test_quiet_base_excludes_the_spike_bar_itself():
    rvol = series([0.5] * 20 + [4.0])
    assert base_rvol(rvol, 20, 20) == pytest.approx(0.5)


def test_is_breakout_rejects_a_window_with_gaps():
    assert not is_breakout(series([float("nan"), 1, 2]), 2, 3)


def test_the_candidate_is_not_published_until_it_is_measured():
    """ACCEPTANCE.md: an unmeasured strategy on the site would be the only list with no
    evidence behind it. Registering it is the last step, not the first."""
    assert "volume-breakout" not in {s.id for s in STRATEGIES}


def test_every_variant_is_a_config():
    assert all(isinstance(c, VolumeBreakoutConfig) for c in VARIANTS.values())
    assert VolumeBreakout().min_bars == 400
