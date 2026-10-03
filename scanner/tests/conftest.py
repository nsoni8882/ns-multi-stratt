import pandas as pd


def make_df(closes, start="2024-01-01"):
    """Closed-bar DataFrame in the shape strategies expect (daily-style bars)."""
    idx = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": 1000,
            "close_time": idx + pd.Timedelta(hours=20),
        },
        index=idx,
    )
