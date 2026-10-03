"""Shared types for strategies.

A strategy receives a DataFrame of *closed* bars with a UTC DatetimeIndex (bar open)
and columns open, high, low, close, volume, close_time (UTC timestamp of bar close).
"""
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

SIGNAL_WINDOW = 3  # a signal stays listed for bars_ago 0, 1, 2

# Conviction tiers, measured over 165 S&P names x 12y of daily bars (and 63 names x 2y of 4H):
#
#   leg                             n     20-bar mean   vs buy-and-hold   win %
#   Reversal BUY, RSI crossed 20    86        +5.32%          +3.97%       67.4
#   Reversal BUY, RSI crossed 25   368        +2.13%          +0.78%       61.1
#   Trend Pullback BUY           7,198        +1.14%          -0.21%       56.9
#   Trend Pullback SELL          2,879   short lost 1.39%                  43.9
#   Reversal SELL                  262   short lost 0.74%                  42.0
#
# The long legs carry an edge that grows the deeper the RSI cross is; the short legs carry
# none, in both 2015-20 and 2021-26 and on both timeframes. Shorting is kept (it is a real
# setup, and 12 years of a bull regime is a thin basis for deleting it) but tagged LOW so
# the site can rank and style it as the weaker signal rather than a peer of the long side.
#
# Re-measured for Trend Pullback with a per-ticker baseline and a non-overlapping sample
# (research/FINDINGS.md): its BUY leg is +0.11% alpha at t=+0.74 -- indistinguishable from
# holding the same name -- and its SELL leg is -2.08% at t=-8.14. The depth-of-cross pattern
# in the table above does NOT generalise from Reversal to Trend Pullback; inside an intact
# uptrend a deep RSI dip is the trend breaking, and grading on it only works because of 2020.
HIGH, STANDARD, LOW = "high", "standard", "low"
CONVICTION_RANK = {HIGH: 0, STANDARD: 1, LOW: 2}  # sort key: strongest signals listed first


@dataclass(frozen=True)
class Signal:
    side: str  # "BUY" or "SELL"
    bars_ago: int
    bar_time: pd.Timestamp  # open time of the signal bar
    fired_at: pd.Timestamp  # close time of the signal bar
    entry_price: float  # close of the signal bar
    details: dict = field(default_factory=dict)
    conviction: str = STANDARD  # HIGH, STANDARD or LOW


class Strategy(Protocol):
    id: str
    name: str
    description: str
    min_bars: int
    chart: dict  # how the site draws this strategy's chart: rsi_levels, macd_deep, emas

    def evaluate(self, df: pd.DataFrame) -> "Signal | None": ...


def make_signal(df: pd.DataFrame, i: int, side: str, details: dict, conviction: str = STANDARD) -> Signal:
    return Signal(
        side=side,
        bars_ago=len(df) - 1 - i,
        bar_time=df.index[i],
        fired_at=df["close_time"].iloc[i],
        entry_price=float(df["close"].iloc[i]),
        details={k: round(float(v), 4) for k, v in details.items()},
        conviction=conviction,
    )
