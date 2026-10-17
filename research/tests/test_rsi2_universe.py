"""The trade loop must match rsi2_edge_backtest.backtest on entries and exits, or the universe
result is about a different rule."""
import numpy as np
import pandas as pd

from research import rsi2_universe as ru


def frame(close):
    idx = pd.date_range("2015-01-01", periods=len(close), freq="B", tz="UTC")
    c = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c})


def test_trade_loop_matches_the_reference_backtest_until_its_re_entry_quirk():
    """The reference re-enters on the bar it exits when the prior bar also signalled, counting
    that bar's return twice and shifting every later trade; this loop does not. So the two agree
    trade for trade up to the first such case, and the prefix must be a real stretch of trades."""
    rng = np.random.default_rng(3)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.02, 1500))
    df = frame(close)
    mine = ru.trades("X", df, "rsi2")
    ref, _, _ = ru._edge.backtest(df["close"], cost_bps=5.5)
    nxt = {d: df.index[i + 1] for i, d in enumerate(df.index[:-1])}
    agree = 0
    for m, r in zip(mine.itertuples(), ref.itertuples()):
        if nxt[m.signal] != r.entry or m.bars != r.bars or not np.isclose(m.net, r.ret):
            break
        agree += 1
    assert agree >= 8


def test_a_trade_open_at_the_end_of_data_is_not_scored():
    close = [100.0] * 250 + [101.0, 99.0, 90.0, 80.0]
    assert ru.trades("X", frame(close), "rsi2").empty
