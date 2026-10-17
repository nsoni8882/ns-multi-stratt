"""The trade loop must match rsi2_edge_backtest.backtest on entries and exits, or the universe
result is about a different rule."""
import numpy as np
import pandas as pd

from research import rsi2_universe as ru


def frame(close):
    idx = pd.date_range("2015-01-01", periods=len(close), freq="B", tz="UTC")
    c = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c})


def test_trade_loop_matches_the_reference_backtest_trade_for_trade():
    """Both must be the live rule: one position at a time, a trade closed on a bar cannot re-enter
    on it. (The reference used to, which double-counted the rebound bar as a phantom one-bar
    trade and inflated every headline number; see FINDINGS.md.)"""
    rng = np.random.default_rng(3)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.02, 1500))
    df = frame(close)
    mine = ru.trades("X", df, "rsi2")
    ref, _, _ = ru._edge.backtest(df["close"], cost_bps=5.5)
    ref = ref[ref["exit"] < df.index[-1]]
    nxt = {d: df.index[i + 1] for i, d in enumerate(df.index[:-1])}
    assert len(mine) == len(ref) > 10
    for m, r in zip(mine.itertuples(), ref.itertuples()):
        assert nxt[m.signal] == r.entry and m.bars == r.bars and np.isclose(m.net, r.ret)


def test_a_trade_open_at_the_end_of_data_is_not_scored():
    close = [100.0] * 250 + [101.0, 99.0, 90.0, 80.0]
    assert ru.trades("X", frame(close), "rsi2").empty
