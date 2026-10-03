import pandas as pd

from scanner.indicators import crossed_above, crossed_below, ema, rsi
from scanner.strategies.base import SIGNAL_WINDOW, Signal, make_signal

RSI_BUY_LEVEL = 40
RSI_SELL_LEVEL = 60


def rule_side(close: pd.Series, ema50: pd.Series, ema200: pd.Series, r: pd.Series, i: int) -> "str | None":
    """Return "BUY", "SELL" or None for bar i. The 5-bar RSI lookback in the spec is
    implied by the cross on bar i (bar i-1 was beyond the level)."""
    if close.iloc[i] > ema200.iloc[i] and ema50.iloc[i] > ema200.iloc[i] and crossed_above(r, i, RSI_BUY_LEVEL):
        return "BUY"
    if close.iloc[i] < ema200.iloc[i] and ema50.iloc[i] < ema200.iloc[i] and crossed_below(r, i, RSI_SELL_LEVEL):
        return "SELL"
    return None


class TrendPullback:
    id = "trend-pullback"
    name = "Trend Pullback"
    description = (
        "BUY when price is in an uptrend (above the 200 EMA, with the 50 EMA above it) "
        "and RSI(14) dips below 40 then crosses back above it. SELL is the mirror in a "
        "downtrend with RSI crossing back below 60."
    )
    min_bars = 250
    chart = {"rsi_levels": [RSI_BUY_LEVEL, RSI_SELL_LEVEL], "macd_deep": False, "emas": True}

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        close = df["close"]
        ema50, ema200 = ema(close, 50), ema(close, 200)
        r = rsi(close)
        for k in range(SIGNAL_WINDOW):
            i = len(df) - 1 - k
            side = rule_side(close, ema50, ema200, r, i)
            if side:
                return make_signal(df, i, side, {"rsi": r.iloc[i], "ema50": ema50.iloc[i], "ema200": ema200.iloc[i]})
        return None
