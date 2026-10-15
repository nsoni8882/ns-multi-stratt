"""Fade a gap down: buy at `entry_bar` when the open is more than `gap_pct` under the prior
session's close. The prior close is the shifted last close of the *previous* day, so the
current day never contributes to its own gap."""
import pandas as pd

DEFAULTS = {"gap_pct": 0.01, "entry_bar": 1}
BOUNDS = {"gap_pct": (0.002, 0.10), "entry_bar": (0, 10)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    day_open = df["open"].where(df["bar"] == 0).groupby(df["day"]).transform("max")
    prev_close = df["close"].groupby(df["day"]).last().shift(1).reindex(df["day"]).to_numpy()
    gap = day_open.to_numpy() / prev_close - 1
    return pd.Series((df["bar"].to_numpy() == int(p["entry_bar"])) & (gap < -p["gap_pct"]),
                     index=df.index)
