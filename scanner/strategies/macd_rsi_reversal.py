import pandas as pd

from scanner.indicators import crossed_above, crossed_below, macd, rsi
from scanner.strategies.base import SIGNAL_WINDOW, Signal, make_signal

HIST_WINDOW = 100  # trailing bars used to rank the histogram
HIST_QUANTILE = 0.10  # "deep" = bottom/top 10% of the trailing window
DEEP_LOOKBACK = 5  # bars before the signal bar in which the histogram was deep
RSI_LOW = 20
RSI_HIGH = 80


def rule_side(hist: pd.Series, lo: pd.Series, hi: pd.Series, r: pd.Series, i: int) -> "str | None":
    """Return "BUY", "SELL" or None for bar i. Pure function of the indicator series.

    The RSI "was beyond the level within the last 5 bars" condition is implied by
    the cross on bar i (bar i-1 was beyond the level), so only the cross is tested.
    """
    window = slice(i - DEEP_LOOKBACK, i)
    h, h1, h2 = hist.iloc[i], hist.iloc[i - 1], hist.iloc[i - 2]

    deep_low = bool((hist.iloc[window] <= lo.iloc[window]).any())
    if deep_low and h > h1 > h2 and h <= 0 and crossed_above(r, i, RSI_LOW):
        return "BUY"

    deep_high = bool((hist.iloc[window] >= hi.iloc[window]).any())
    if deep_high and h < h1 < h2 and h >= 0 and crossed_below(r, i, RSI_HIGH):
        return "SELL"
    return None


class MacdRsiReversal:
    id = "macd-rsi-reversal"
    name = "MACD + RSI Reversal"
    description = (
        "BUY when the MACD histogram climbs back from a deep low while RSI(14) crosses "
        "back above 20. SELL is the mirror: histogram falling from a deep high while "
        "RSI(14) crosses back below 80."
    )
    min_bars = 150
    chart = {"rsi_levels": [RSI_LOW, RSI_HIGH], "macd_deep": True, "emas": False}

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        hist = macd(df["close"])["hist"]
        lo = hist.rolling(HIST_WINDOW).quantile(HIST_QUANTILE)
        hi = hist.rolling(HIST_WINDOW).quantile(1 - HIST_QUANTILE)
        r = rsi(df["close"])
        for k in range(SIGNAL_WINDOW):
            i = len(df) - 1 - k
            side = rule_side(hist, lo, hi, r, i)
            if side:
                return make_signal(df, i, side, {"macd_hist": hist.iloc[i], "rsi": r.iloc[i]})
        return None
