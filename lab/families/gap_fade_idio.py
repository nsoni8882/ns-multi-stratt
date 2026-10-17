"""Fade a stock-specific gap down: `gap_fade`, but only on days the market itself did not gap.
`backtest.run` attaches `mkt_gap`, the median open-vs-prior-close gap across the universe,
which is known at bar 0 and so is causal for any `entry_bar`. A frame without it counts as a
flat market. A separate family rather than a new `gap_fade` param, so no earlier fingerprint moves."""
import pandas as pd

from lab.families import gap_fade

USES_MARKET_GAP = True
DEFAULTS = {**gap_fade.DEFAULTS, "market_gap_max": 0.003}
BOUNDS = {**gap_fade.BOUNDS, "market_gap_max": (0.0005, 0.05)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    sig = gap_fade.signal(df, p)
    if "mkt_gap" not in df:
        return sig
    return sig & (df["mkt_gap"].abs() <= p["market_gap_max"]).to_numpy()


def day_gaps(df: pd.DataFrame) -> pd.Series:
    """One symbol's gap per day: its day-open over the previous day's last close."""
    day_open = df["open"].where(df["bar"] == 0).groupby(df["day"]).max()
    return day_open / df["close"].groupby(df["day"]).last().shift(1) - 1
