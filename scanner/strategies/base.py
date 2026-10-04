"""Shared types for strategies.

A strategy receives a DataFrame of *closed* bars with a UTC DatetimeIndex (bar open)
and columns open, high, low, close, volume, close_time (UTC timestamp of bar close).
"""
import hashlib
import json
import math
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
# none, in both 2015-20 and 2021-26 and on both timeframes. Re-measured against a per-ticker
# baseline on a non-overlapping sample, the Trend Pullback short came out reliably wrong
# (-2.08%, t=-8.14) and the Reversal short worth nothing (+0.05%, t=+0.09), so both legs are
# now off by default (`enable_short=False`) and nothing short is published. LOW survives as
# the tier for whatever earns it next; it is not currently used by a shipped signal.
#
# Re-measured for Trend Pullback with a per-ticker baseline and a non-overlapping sample
# (research/FINDINGS.md): its BUY leg is +0.11% alpha at t=+0.74 -- indistinguishable from
# holding the same name -- and its SELL leg is -2.08% at t=-8.14. The depth-of-cross pattern
# in the table above does NOT generalise from Reversal to Trend Pullback; inside an intact
# uptrend a deep RSI dip is the trend breaking, and grading on it only works because of 2020.
HIGH, STANDARD, LOW = "high", "standard", "low"
CONVICTION_RANK = {HIGH: 0, STANDARD: 1, LOW: 2}  # sort key: strongest signals listed first


def thesis_negated(r: pd.Series, i: int, last: int, side: str, level: float) -> bool:
    """Has the RSI cross that fired this signal been undone on a later bar?

    Both strategies trigger on RSI crossing a level, so both die the same way: a BUY that
    crossed up through 40 is dead once RSI closes back at or under 40, and a SELL that was
    rejected at 60 is dead once RSI closes back at or above it.

    This only matters for a signal still listed from an earlier bar. SIGNAL_WINDOW keeps a
    signal on the site for three bars so a reader who checks every other day still sees it,
    but without this the site goes on presenting a setup whose premise has already failed --
    CCL fired a SELL on 2026-09-30 with RSI at 56.9, and two bars later RSI was 63.6, higher
    than the 61.6 it had crossed down from, while the site still listed it as live.

    Measured before being wired up, and the result argued against hiding these: over 12y, a
    stale BUY whose premise had died returned +1.93% from the current bar against +1.52% for
    one still intact (n=2,717 vs 9,316), because RSI falling back under 40 means price dipped
    further and you are buying lower. So they are flagged, not dropped -- the problem is that
    the site described a setup that no longer holds, not that the signal was unprofitable.

    This changes no backtested number: the measurement harness enters at the signal bar,
    where no later bar exists yet.
    """
    after = r.iloc[i + 1 : last + 1]
    if after.empty:
        return False
    return bool((after >= level).any()) if side == "SELL" else bool((after <= level).any())


@dataclass(frozen=True)
class Release:
    """One entry in a strategy's visible change history.

    `summary` is one or two lines at the altitude a reader of the site cares about -- what
    changed about the signals, not which function moved. `fingerprint` is the
    `rules_version()` of the params this release shipped with, and only the newest entry
    needs it: a test asserts it still matches, so changing a threshold without adding a
    release entry fails the build. That is the whole point -- the history cannot drift out
    of date, because the thing that would make it stale is what breaks the test.
    """

    version: str  # "1.2.0"
    date: str  # ISO date, YYYY-MM-DD
    summary: str
    fingerprint: str = ""

    def as_dict(self) -> dict:
        return {"version": self.version, "date": self.date, "summary": self.summary}


def current_version(history: "tuple[Release, ...]") -> str:
    """The version a strategy is running now. History is declared newest-first, like a
    CHANGELOG, so new entries are added at the top and this never needs updating."""
    return history[0].version if history else "0.0.0"


def rules_version(params: dict) -> str:
    """Short stable fingerprint of the parameters that decide whether a signal fires.

    Recorded against every stored signal and published in strategies.json. Without it the
    history silently mixes rule generations: a row from before a threshold moved looks
    identical to one from after, so questions like "did the conviction tiers hold up live?"
    cannot be answered across a change. Deliberately a hash of the declared `params` rather
    than of the module source, so editing a comment or a docstring does not invalidate
    history -- only a change that can alter a signal does.
    """
    blob = json.dumps(params, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


@dataclass(frozen=True)
class Signal:
    side: str  # "BUY" or "SELL"
    bars_ago: int
    bar_time: pd.Timestamp  # open time of the signal bar
    fired_at: pd.Timestamp  # close time of the signal bar
    entry_price: float  # close of the signal bar
    details: dict = field(default_factory=dict)
    conviction: str = STANDARD  # HIGH, STANDARD or LOW
    invalidated: bool = False  # fired earlier in the window, premise undone since


class Strategy(Protocol):
    id: str
    name: str
    description: str
    min_bars: int
    chart: dict  # how the site draws this strategy's chart: rsi_levels, macd_deep, emas
    params: dict  # the thresholds that decide a signal, fingerprinted by rules_version()
    history: "tuple[Release, ...]"  # newest first; shown in the site's history overlay

    def evaluate(self, df: pd.DataFrame) -> "Signal | None": ...


def make_signal(df: pd.DataFrame, i: int, side: str, details: dict, conviction: str = STANDARD,
                invalidated: bool = False) -> Signal:
    return Signal(
        side=side,
        bars_ago=len(df) - 1 - i,
        bar_time=df.index[i],
        fired_at=df["close_time"].iloc[i],
        entry_price=float(df["close"].iloc[i]),
        # Non-finite values are dropped rather than published: NaN is valid in Python's JSON
        # output and not in the browser's parser, so one unmeasurable detail would break the
        # whole file. Every consumer of `details` already reads it as optional.
        details={k: round(float(v), 4) for k, v in details.items()
                 if v is not None and math.isfinite(float(v))},
        conviction=conviction,
        invalidated=invalidated,
    )
