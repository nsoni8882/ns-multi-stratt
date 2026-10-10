import pytest

from trader import params
from trader.rule import decide, sma, wilder_rsi


def rising(n, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def test_sma_needs_full_window():
    assert sma([1.0, 2.0], 3) is None
    assert sma([1.0, 2.0, 3.0], 3) == 2.0


def test_wilder_rsi_all_up_is_100():
    assert wilder_rsi(rising(50), 2) == 100.0


def test_insufficient_history_returns_no_decision():
    """Fewer than TREND_LEN closes leaves SMA(200) undefined. Skip the symbol -- an
    undefined trend gate is not an open trend gate."""
    d = decide(rising(199), held=False, bars_held=0)
    assert d.action == "skip"
    assert "history" in d.reason
    assert d.sma200 is None


def test_oversold_in_uptrend_buys():
    closes = rising(400) + [460.0, 420.0]
    d = decide(closes, held=False, bars_held=0)
    assert d.action == "buy"
    assert d.rsi2 < params.BUY_BELOW
    assert d.price > d.sma200
    assert d.trend_gap_pct > 0


def test_oversold_below_trend_is_blocked():
    """The 200-day gate is load-bearing: the same trigger below it earned more per trade
    but with a 24% drawdown and a Sharpe of 0.11. Reject, do not buy."""
    closes = rising(400, start=500.0, step=-1.0) + [95.0, 90.0]
    d = decide(closes, held=False, bars_held=0)
    assert d.action == "wait"
    assert d.reason == "trend gate blocked"
    assert d.price < d.sma200
    assert d.trend_gap_pct < 0


def test_not_oversold_waits():
    d = decide(rising(400), held=False, bars_held=0)
    assert d.action == "wait"
    assert d.reason == "not oversold"


def test_held_position_exits_on_rsi():
    # RSI(2) at 72.9 here: the plan's 470.0 tail only reached 62.8, under the threshold.
    closes = rising(400) + [460.0, 420.0, 500.0]
    d = decide(closes, held=True, bars_held=2)
    assert d.action == "sell"
    assert d.reason == "rsi"
    assert d.rsi2 > params.SELL_ABOVE


def test_held_position_exits_on_time_stop_at_exactly_max_hold():
    closes = rising(400) + [460.0, 420.0, 421.0]
    d = decide(closes, held=True, bars_held=params.MAX_HOLD)
    assert d.action == "sell"
    assert d.reason == "time_stop"


def test_held_position_holds_one_bar_short_of_the_time_stop():
    closes = rising(400) + [460.0, 420.0, 421.0]
    d = decide(closes, held=True, bars_held=params.MAX_HOLD - 1)
    assert d.action == "hold"


def test_decision_is_frozen():
    d = decide(rising(400), held=False, bars_held=0)
    with pytest.raises(Exception):
        d.action = "buy"  # type: ignore[misc]


def test_params_covers_every_threshold_that_moves_a_signal():
    p = params.params()
    for key in ("rsi_len", "buy_below", "sell_above", "trend_len", "max_hold",
                "slice_pct", "max_concurrent", "symbols"):
        assert key in p, key
