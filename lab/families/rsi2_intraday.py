"""The daily RSI(2) reversion idea on intraday bars: oversold while still above a trend average."""
import pandas as pd

from scanner.indicators import rsi

DEFAULTS = {"rsi_len": 2, "buy_below": 10.0, "trend_len": 78, "last_entry_bar": 70}
BOUNDS = {"rsi_len": (2, 14), "buy_below": (1.0, 40.0), "trend_len": (10, 400),
          "last_entry_bar": (5, 77)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    r = rsi(df["close"], int(p["rsi_len"]))
    trend = df["close"].rolling(int(p["trend_len"])).mean()
    return (r < p["buy_below"]) & (df["close"] > trend) & (df["bar"] <= p["last_entry_bar"])
