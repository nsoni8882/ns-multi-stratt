"""Opening-range breakout, long only. Enter on the first close above the opening range's high.

`min_rvol` is the "stocks in play" filter: the opening range's volume against its own average
over the previous `rvol_days` days. 0 turns it off.
"""
import pandas as pd

DEFAULTS = {"range_bars": 3, "last_entry_bar": 30, "min_rvol": 0.0, "rvol_days": 14}
BOUNDS = {"range_bars": (1, 12), "last_entry_bar": (4, 70), "min_rvol": (0.0, 10.0),
          "rvol_days": (3, 60)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    n = int(p["range_bars"])
    in_range = df["bar"] < n
    high = df["high"].where(in_range).groupby(df["day"]).transform("max")
    cond = (df["bar"] >= n) & (df["bar"] <= p["last_entry_bar"]) & (df["close"] > high)
    if p["min_rvol"] > 0:
        or_vol = df["volume"].where(in_range).groupby(df["day"]).sum()
        prior = or_vol.shift(1).rolling(int(p["rvol_days"]), min_periods=1).mean()
        rvol = pd.Series((or_vol / prior).reindex(df["day"]).to_numpy(), index=df.index)
        cond &= rvol >= p["min_rvol"]
    return cond & (cond.groupby(df["day"]).cumsum() == 1)
