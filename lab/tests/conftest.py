import numpy as np
import pandas as pd

from lab.data import ET, with_session


def make_days(days, n=78, base=100.0, drift=0.0, vol=1000, start_hm="09:30"):
    """5-minute regular-session bars for each ET day in `days` (list of 'YYYY-MM-DD')."""
    frames = []
    for d in days:
        open_et = pd.Timestamp(f"{d} {start_hm}", tz=ET)
        idx = pd.date_range(open_et, periods=n, freq="5min").tz_convert("UTC")
        close = base + drift * np.arange(n)
        frames.append(pd.DataFrame(
            {"open": close, "high": close * 1.001, "low": close * 0.999, "close": close,
             "volume": float(vol)}, index=idx))
    return pd.concat(frames)


def random_walk(n_days=25, seed=7):
    """Seeded multi-day 5-minute series with overnight jumps, so every family can fire."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2024-03-04", periods=n_days).strftime("%Y-%m-%d").tolist()
    price, frames = 100.0, []
    for d in days:
        price *= 1 + rng.normal(0, 0.01)
        close = price * np.cumprod(1 + rng.normal(0, 0.002, 78))
        open_ = np.concatenate([[price], close[:-1]])
        idx = pd.date_range(pd.Timestamp(f"{d} 09:30", tz=ET), periods=78, freq="5min").tz_convert("UTC")
        frames.append(pd.DataFrame(
            {"open": open_, "high": np.maximum(open_, close) * 1.0005,
             "low": np.minimum(open_, close) * 0.9995, "close": close,
             "volume": rng.integers(500, 1500, 78).astype(float)}, index=idx))
        price = close[-1]
    return pd.concat(frames)


def sessions(raw, tf="5Min"):
    return with_session(raw, tf)
