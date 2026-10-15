"""Buy a stretch below the session VWAP, once per day. VWAP accumulates from the open, so
bar i only ever sees bars up to i."""
import numpy as np
import pandas as pd

DEFAULTS = {"dev_pct": 0.006, "min_bar": 6, "last_entry_bar": 60}
BOUNDS = {"dev_pct": (0.001, 0.03), "min_bar": (1, 40), "last_entry_bar": (5, 70)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = (typical * df["volume"]).groupby(df["day"]).cumsum()
    vol = df["volume"].groupby(df["day"]).cumsum().replace(0, np.nan)
    vwap = pv / vol
    cond = ((df["bar"] >= p["min_bar"]) & (df["bar"] <= p["last_entry_bar"])
            & (df["close"] < vwap * (1 - p["dev_pct"])))
    return cond & (cond.groupby(df["day"]).cumsum() == 1)
