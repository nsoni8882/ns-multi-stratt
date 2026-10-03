"""Shared types for strategies.

A strategy receives a DataFrame of *closed* bars with a UTC DatetimeIndex (bar open)
and columns open, high, low, close, volume, close_time (UTC timestamp of bar close).
"""
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

SIGNAL_WINDOW = 3  # a signal stays listed for bars_ago 0, 1, 2


@dataclass(frozen=True)
class Signal:
    side: str  # "BUY" or "SELL"
    bars_ago: int
    bar_time: pd.Timestamp  # open time of the signal bar
    fired_at: pd.Timestamp  # close time of the signal bar
    entry_price: float  # close of the signal bar
    details: dict = field(default_factory=dict)


class Strategy(Protocol):
    id: str
    name: str
    description: str
    min_bars: int
    chart: dict  # how the site draws this strategy's chart: rsi_levels, macd_deep, emas

    def evaluate(self, df: pd.DataFrame) -> "Signal | None": ...


def make_signal(df: pd.DataFrame, i: int, side: str, details: dict) -> Signal:
    return Signal(
        side=side,
        bars_ago=len(df) - 1 - i,
        bar_time=df.index[i],
        fired_at=df["close_time"].iloc[i],
        entry_price=float(df["close"].iloc[i]),
        details={k: round(float(v), 4) for k, v in details.items()},
    )
