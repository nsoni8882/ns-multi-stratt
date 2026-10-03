import pandas as pd

from scanner.indicators import crossed_above, crossed_below, ema, rsi
from scanner.strategies.base import LOW, SIGNAL_WINDOW, STANDARD, Signal, make_signal

# Cardwell's RSI range shift: RSI oscillates 40-80 in an uptrend (40 acts as support) and
# 20-60 in a downtrend (60 acts as resistance). The classic 30/70 and 20/80 bands were built
# for range-bound markets and barely fire inside a trend -- measured over 165 S&P names x 12y
# of daily bars, 20/80 produced 11 BUY and 6 SELL signals in total, against 7,198/2,890 here.
RSI_BUY_LEVEL = 40
RSI_SELL_LEVEL = 60

# EMA200 with adjust=False still carries ~8% of its weight on the seed bar after 250 bars,
# which left a 0.67% median error against a converged EMA200 and flipped the close-vs-EMA200
# verdict on 5 of 161 names. At 400 bars the error is 0.14% and nothing flipped. Both
# timeframes already fetch more than this (daily ~500 bars, 4H ~970), so the only tickers
# this excludes are recent listings whose trend could not be classified reliably anyway.
MIN_BARS = 400


def rule_side(close: pd.Series, ema50: pd.Series, ema200: pd.Series, r: pd.Series, i: int) -> "tuple[str, str] | None":
    """Return (side, conviction) for bar i, or None. The 5-bar RSI lookback in the spec is
    implied by the cross on bar i (bar i-1 was beyond the level)."""
    if close.iloc[i] > ema200.iloc[i] and ema50.iloc[i] > ema200.iloc[i] and crossed_above(r, i, RSI_BUY_LEVEL):
        return "BUY", STANDARD
    if close.iloc[i] < ema200.iloc[i] and ema50.iloc[i] < ema200.iloc[i] and crossed_below(r, i, RSI_SELL_LEVEL):
        return "SELL", LOW  # see base.py: the short leg showed no measurable edge
    return None


class TrendPullback:
    id = "trend-pullback"
    name = "Trend Pullback"
    description = (
        "BUY when price is in an uptrend (above the 200 EMA, with the 50 EMA above it) "
        "and RSI(14) dips below 40 then crosses back above it. SELL is the mirror in a "
        "downtrend with RSI crossing back below 60, and is shown as a weaker signal: "
        "backtested over 12 years, the short leg of this setup did not beat holding cash."
    )
    min_bars = MIN_BARS
    # The same 40/60 levels are used on 1d and 4H. Checked, not assumed: on 4H the BUY leg
    # returned +0.36% over 20 bars against a +0.77% baseline (t=3.9, n=821), the same shape
    # as daily. Re-measure before changing them on one timeframe only.
    chart = {"rsi_levels": [RSI_BUY_LEVEL, RSI_SELL_LEVEL], "macd_deep": False, "emas": True}

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        close = df["close"]
        ema50, ema200 = ema(close, 50), ema(close, 200)
        r = rsi(close)
        for k in range(SIGNAL_WINDOW):
            i = len(df) - 1 - k
            hit = rule_side(close, ema50, ema200, r, i)
            if hit:
                side, conviction = hit
                return make_signal(
                    df, i, side, {"rsi": r.iloc[i], "ema50": ema50.iloc[i], "ema200": ema200.iloc[i]}, conviction
                )
        return None
