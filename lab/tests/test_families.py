import pandas as pd
import pytest

from lab.families import REGISTRY, gap_fade, orb, rsi2_intraday, vwap_reversion
from lab.tests.conftest import make_days, random_walk, sessions

PERMISSIVE = {
    "orb": {"range_bars": 1, "last_entry_bar": 70},
    "vwap_reversion": {"dev_pct": 0.001, "min_bar": 1},
    "rsi2_intraday": {"buy_below": 40.0, "trend_len": 10},
    "gap_fade": {"gap_pct": 0.002, "entry_bar": 1},
    "gap_fade_idio": {"gap_pct": 0.002, "entry_bar": 1},
}


def params_for(name):
    mod = REGISTRY[name]
    return {**mod.DEFAULTS, **PERMISSIVE[name]}


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_signal_never_uses_future_bars(name):
    """The guard that makes LLM-proposed specs safe: truncating the data must not change
    any earlier decision. A family that peeks forward fails here."""
    raw = random_walk()
    full = REGISTRY[name].signal(sessions(raw), params_for(name))
    assert full.sum() > 0, "permissive params should fire at least once on the walk"
    for k in (150, 400, 901, 1500):
        cut = REGISTRY[name].signal(sessions(raw.iloc[:k]), params_for(name))
        assert (cut.to_numpy() == full.iloc[:k].to_numpy()).all(), f"{name} changed at k={k}"


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_defaults_sit_inside_bounds(name):
    mod = REGISTRY[name]
    assert set(mod.DEFAULTS) == set(mod.BOUNDS)
    for k, (lo, hi) in mod.BOUNDS.items():
        assert lo <= mod.DEFAULTS[k] <= hi, k


def test_orb_fires_once_per_day_and_only_after_the_range():
    df = sessions(random_walk())
    sig = orb.signal(df, {**orb.DEFAULTS, "range_bars": 3, "last_entry_bar": 70})
    assert (df.loc[sig, "bar"] >= 3).all()
    assert (df[sig].groupby("day").size() <= 1).all()


def test_orb_volume_filter_blocks_the_first_day():
    df = sessions(random_walk())
    sig = orb.signal(df, {**orb.DEFAULTS, "range_bars": 1, "min_rvol": 0.5})
    assert not sig[df["day"] == df["day"].iloc[0]].any()  # no prior days -> no relative volume


def test_gap_fade_only_after_a_down_gap():
    day1 = make_days(["2024-03-04"], base=100)
    up = make_days(["2024-03-05"], base=105)
    dn = make_days(["2024-03-06"], base=95)
    df = sessions(pd.concat([day1, up, dn]))
    sig = gap_fade.signal(df, {"gap_pct": 0.01, "entry_bar": 1})
    fired = set(df.loc[sig, "day"])
    assert len(fired) == 1 and next(iter(fired)).day == 6


def test_vwap_reversion_silent_when_price_sits_on_vwap():
    df = sessions(make_days(["2024-03-04", "2024-03-05"]))
    assert not vwap_reversion.signal(df, {**vwap_reversion.DEFAULTS, "dev_pct": 0.001}).any()


def test_rsi2_requires_price_above_trend():
    falling = sessions(make_days(["2024-03-04"], drift=-0.05))  # one unbroken decline
    sig = rsi2_intraday.signal(falling, {**rsi2_intraday.DEFAULTS, "trend_len": 20, "buy_below": 40.0})
    assert not sig.any()  # a steady decline never closes above its own average


def test_idiosyncratic_gap_fade_skips_days_the_market_gapped():
    from lab.families import gap_fade_idio
    day1 = make_days(["2024-03-04"], base=100)
    dn = make_days(["2024-03-05"], base=95)
    df = sessions(pd.concat([day1, dn]))
    p = {"gap_pct": 0.01, "entry_bar": 1, "market_gap_max": 0.003}
    assert gap_fade_idio.signal(df.assign(mkt_gap=0.0), p).any()
    assert not gap_fade_idio.signal(df.assign(mkt_gap=-0.05), p).any()
    assert gap_fade_idio.signal(df, p).any()  # no market column: treated as a flat market
