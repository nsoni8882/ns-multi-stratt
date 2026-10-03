import pandas as pd

from scanner.indicators import crossed_above, crossed_below, macd, rsi
from scanner.strategies.base import (HIGH, LOW, SIGNAL_WINDOW, STANDARD, Release, Signal,
                                     make_signal, thesis_negated)

HIST_WINDOW = 100  # trailing bars used to rank the histogram
HIST_QUANTILE = 0.10  # "deep" = bottom/top 10% of the trailing window
DEEP_LOOKBACK = 5  # bars before the signal bar in which the histogram was deep

# Two tiers on the BUY side. The edge falls off sharply as the level is raised -- over 165
# S&P names x 12y of daily bars the 20-bar mean return was +5.32% for a cross back above 20
# (n=86), +2.13% above 25 (n=368), +1.89% above 30 (n=1050) and -0.29% above 35 (n=2131),
# against a +1.35% buy-and-hold baseline. A cross above 20 alone fires about 7 times a year
# across the whole S&P 500, so 25 is carried as a second, standard-conviction tier; going to
# 30 would roughly triple the count for a third of the per-signal edge, so it is left out.
RSI_LOW = 20  # HIGH conviction
RSI_LOW_STANDARD = 25
RSI_HIGH = 80
# No matching second tier on the SELL side: loosening it to 75 added 504 signals whose
# short P&L was no better than the 262 at 80 (both indistinguishable from zero edge).
RSI_HIGH_STANDARD = RSI_HIGH
MIN_BARS = 150



def rule_side(hist: pd.Series, lo: pd.Series, hi: pd.Series, r: pd.Series, i: int) -> "tuple[str, str] | None":
    """Return (side, conviction) for bar i, or None. Pure function of the indicator series.

    The RSI "was beyond the level within the last 5 bars" condition is implied by
    the cross on bar i (bar i-1 was beyond the level), so only the cross is tested.
    The deeper tier is tested first, so a bar crossing from 19 to 26 is reported as HIGH.
    """
    window = slice(i - DEEP_LOOKBACK, i)
    h, h1, h2 = hist.iloc[i], hist.iloc[i - 1], hist.iloc[i - 2]

    deep_low = bool((hist.iloc[window] <= lo.iloc[window]).any())
    if deep_low and h > h1 > h2 and h <= 0:
        if crossed_above(r, i, RSI_LOW):
            return "BUY", HIGH
        if crossed_above(r, i, RSI_LOW_STANDARD):
            return "BUY", STANDARD

    deep_high = bool((hist.iloc[window] >= hi.iloc[window]).any())
    if deep_high and h < h1 < h2 and h >= 0 and crossed_below(r, i, RSI_HIGH):
        return "SELL", LOW  # see base.py: the short leg showed no measurable edge
    return None


class MacdRsiReversal:
    id = "macd-rsi-reversal"
    name = "MACD + RSI Reversal"
    description = (
        "BUY when the MACD histogram climbs back from a deep low while RSI(14) crosses back "
        "above 20 (strongest) or 25. SELL is the mirror: histogram falling from a deep high "
        "while RSI(14) crosses back below 80, and is shown as a weaker signal because the "
        "short leg of this setup did not beat holding cash over 12 years of backtesting."
    )
    min_bars = MIN_BARS
    # Newest first. See TrendPullback.history -- the top fingerprint is build-asserted.
    history = (
        Release("1.2.0", "2026-10-03",
                "A signal that fired a day or two ago is now marked 'Setup changed' when RSI has "
                "since crossed back past the level that triggered it, so a card never describes "
                "a setup that no longer holds. They are still listed, not hidden: over 12 years "
                "these did no worse than signals still intact.",
                # Fingerprint updated in place, not a new release: `params` was widened to cover the
                # indicator periods it had been missing, and no shipped signal changes.
                fingerprint="eba1a6598045"),
        Release("1.1.0", "2026-10-03",
                "Signals now carry a conviction tier. An RSI cross below 20 beat the market "
                "by 3.97% over the next 20 days against 0.78% for a cross below 25, so the "
                "deeper ones are marked stronger and listed first."),
        Release("1.0.0", "2026-10-03",
                "First version. Looks for exhaustion: a deeply negative MACD histogram in "
                "the last 5 bars plus RSI(14) turning up out of oversold territory."),
    )
    params = {
        "min_bars": MIN_BARS, "hist_window": HIST_WINDOW, "hist_quantile": HIST_QUANTILE,
        "deep_lookback": DEEP_LOOKBACK, "rsi_low": RSI_LOW, "rsi_low_standard": RSI_LOW_STANDARD,
        "rsi_high": RSI_HIGH, "rsi_high_standard": RSI_HIGH_STANDARD,
        "macd": (12, 26, 9), "rsi_length": 14,  # indicator periods decide signals too
    }
    # The same levels are used on 1d and 4H. Checked, not assumed: on 4H a cross back above
    # 20 returned +3.57% over 20 bars against a +0.77% baseline (n=23), the same shape as daily.
    chart = {"rsi_levels": [RSI_LOW, RSI_LOW_STANDARD, RSI_HIGH], "macd_deep": True, "emas": False}

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        hist = macd(df["close"])["hist"]
        lo = hist.rolling(HIST_WINDOW).quantile(HIST_QUANTILE)
        hi = hist.rolling(HIST_WINDOW).quantile(1 - HIST_QUANTILE)
        r = rsi(df["close"])
        last = len(df) - 1
        for k in range(SIGNAL_WINDOW):
            i = last - k
            hit = rule_side(hist, lo, hi, r, i)
            if hit:
                side, conviction = hit
                # The level that fired it: the deep tier for a HIGH buy, else the standard one.
                level = RSI_HIGH if side == "SELL" else (RSI_LOW if conviction == HIGH else RSI_LOW_STANDARD)
                dead = thesis_negated(r, i, last, side, level)
                return make_signal(df, i, side, {"macd_hist": hist.iloc[i], "rsi": r.iloc[i]},
                                   conviction, invalidated=dead)
        return None
