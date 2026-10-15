import pandas as pd
import pytest

from lab import backtest
from lab.spec import Risk, Spec
from lab.tests.conftest import make_days, random_walk, sessions

RISK = Risk(stop_pct=0.01, target_pct=0.02, max_hold_bars=20)


def frame(opens, highs, lows, closes):
    base = make_days(["2024-03-04"], n=len(opens))
    base["open"], base["high"], base["low"], base["close"] = opens, highs, lows, closes
    return sessions(base)


def sig_at(df, i):
    s = pd.Series(False, index=df.index)
    s.iloc[i] = True
    return s


def test_entry_is_the_next_bars_open_not_the_signal_bars_close():
    df = frame([100, 101, 101, 101], [100, 101, 101, 101], [100, 101, 101, 101], [100, 100.5, 101, 101])
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.entry_px == 101 and t.exit_reason == "session"


def test_target_fills_at_the_target_price():
    df = frame([100, 100, 100, 100], [100, 100, 102.5, 100], [100, 100, 100, 100], [100] * 4)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.exit_reason == "target" and t.exit_px == pytest.approx(102.0)


def test_stop_wins_when_one_bar_touches_both():
    df = frame([100, 100, 100, 100], [100, 100, 103, 100], [100, 100, 98, 100], [100] * 4)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.exit_reason == "stop"


def test_a_gap_through_the_stop_fills_at_the_open_not_the_stop():
    df = frame([100, 100, 95, 95], [100, 100, 95, 95], [100, 100, 95, 95], [100, 100, 95, 95])
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.exit_px == 95 and t.exit_reason == "stop"


def test_max_hold_closes_the_trade():
    short = Risk(stop_pct=0.05, target_pct=0.2, max_hold_bars=2)
    df = frame([100] * 6, [100] * 6, [100] * 6, [100] * 6)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), short, "mega", "X")
    assert t.exit_reason == "time" and t.bars_held == 2


def test_a_signal_on_the_last_bar_of_the_day_does_not_trade():
    df = frame([100] * 4, [100] * 4, [100] * 4, [100] * 4)
    assert backtest.simulate_symbol(df, sig_at(df, 3), RISK, "mega", "X") == []


def test_no_overlapping_positions_in_one_symbol():
    df = frame([100] * 8, [100] * 8, [100] * 8, [100] * 8)
    sig = pd.Series(True, index=df.index)
    trades = backtest.simulate_symbol(df, sig, RISK, "mega", "X")
    assert len(trades) >= 1
    assert all(a.exit_time <= b.entry_time for a, b in zip(trades, trades[1:]))


def test_costs_are_charged():
    df = frame([100] * 4, [100] * 4, [100] * 4, [100] * 4)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "large", "X")
    assert t.gross == 0 and t.net < 0


def spec(**risk):
    return Spec.from_dict({"name": "t", "family": "gap_fade", "timeframe": "5Min",
                           "params": {"gap_pct": 0.002, "entry_bar": 1},
                           "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30, **risk},
                           "hypothesis": "gap downs mean-revert intraday"})


def test_run_respects_the_concurrency_cap():
    frames = {f"S{i}": sessions(random_walk(seed=i)) for i in range(6)}
    tiers = {k: "large" for k in frames}
    res = backtest.run(spec(max_concurrent=1), frames, tiers)
    ordered = sorted(res.trades, key=lambda t: t.entry_time)
    assert ordered
    for a, b in zip(ordered, ordered[1:]):
        assert b.entry_time >= a.exit_time
    assert len(backtest.run(spec(max_concurrent=5), frames, tiers).trades) >= len(res.trades)


def test_universe_membership_filters_by_year():
    frames = {"A": sessions(random_walk())}
    open_all = backtest.run(spec(), frames, {"A": "large"})
    none = backtest.run(spec(), frames, {"A": "large"}, allowed={"A": {1999}})
    assert open_all.trades and not none.trades


def test_before_and_after_partition_the_trades():
    frames = {"A": sessions(random_walk())}
    res = backtest.run(spec(), frames, {"A": "large"})
    cut = res.trades[len(res.trades) // 2].entry_time
    assert len(res.before(cut).trades) + len(res.after(cut).trades) == len(res.trades)


def test_empty_result_does_not_divide_by_zero():
    res = backtest.run(spec(), {"A": sessions(make_days(["2024-03-04"]))}, {"A": "large"})
    assert res.trades == [] and res.daily_mean().empty and res.equity_curve().empty
