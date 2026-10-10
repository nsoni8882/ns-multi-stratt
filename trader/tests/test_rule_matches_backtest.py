"""The two implementations of one rule must agree, bar for bar.

`trader/rule.py` is stdlib-only because the live path takes no dependencies; `research/` and
the original backtest use pandas. That is a deliberate duplication, and this is what stops it
drifting: every entry signal over ~6,700 bars of real AMZN and AAPL history, computed both
ways, must match exactly. Offline -- the closes are cached fixtures.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trader import params
from trader.rule import sma, wilder_rsi

FIXTURES = Path(__file__).parent / "fixtures"


def pandas_rsi(close, n):
    d = close.diff()
    au = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    ad = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad.replace(0, np.nan))


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_rsi_and_sma_match_pandas_to_floating_point(symbol):
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    want_rsi = pandas_rsi(close, params.RSI_LEN)
    want_sma = close.rolling(params.TREND_LEN).mean()
    closes = [float(x) for x in close.to_numpy()]

    # Walk the series the way the live bot sees it: a growing prefix ending at each bar.
    checked = 0
    for i in range(params.TREND_LEN, len(closes), 7):  # every 7th bar keeps the test ~1s
        prefix = closes[: i + 1]
        got_r, got_s = wilder_rsi(prefix, params.RSI_LEN), sma(prefix, params.TREND_LEN)
        assert got_r == pytest.approx(float(want_rsi.iloc[i]), abs=1e-9), f"{symbol} RSI bar {i}"
        assert got_s == pytest.approx(float(want_sma.iloc[i]), rel=1e-12), f"{symbol} SMA bar {i}"
        checked += 1
    assert checked > 800, f"only checked {checked} bars"


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_entry_signals_agree_exactly(symbol):
    """The number that matters: identical entry decisions, not merely close indicators."""
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    want = ((pandas_rsi(close, params.RSI_LEN) < params.BUY_BELOW)
            & (close > close.rolling(params.TREND_LEN).mean())).fillna(False).to_numpy()
    closes = [float(x) for x in close.to_numpy()]

    disagreements = []
    for i in range(params.TREND_LEN, len(closes)):
        prefix = closes[: i + 1]
        r, s = wilder_rsi(prefix, params.RSI_LEN), sma(prefix, params.TREND_LEN)
        got = r is not None and s is not None and r < params.BUY_BELOW and prefix[-1] > s
        if got != bool(want[i]):
            disagreements.append((i, close.index[i].date(), r, s, bool(want[i]), got))
    assert disagreements == [], f"{symbol}: {len(disagreements)} disagreements, first {disagreements[:3]}"
