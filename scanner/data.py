"""Fetch Yahoo bars and shape them into closed-bar DataFrames.

Output frame: UTC DatetimeIndex (bar open; midnight UTC of the trading date for daily bars),
columns open, high, low, close, volume, close_time (UTC). Only closed bars are returned.
"""
import logging
import time

import pandas as pd
import yfinance as yf

ET = "America/New_York"
OHLCV = ["open", "high", "low", "close", "volume"]
BATCH_SIZE = 50
HOURLY_LOOKBACK_DAYS = 729  # Yahoo rejects requests reaching back 730 days
MIDDAY = pd.Timedelta(hours=13, minutes=30)  # end of the first 4H bar (ET)
CLOSE = pd.Timedelta(hours=16)  # end of the second 4H bar / daily bar (ET)

log = logging.getLogger(__name__)


def _clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=str.lower)[OHLCV]
    return df.dropna(subset=["close"])


def _et_timestamp(day, offset: pd.Timedelta) -> pd.Timestamp:
    return pd.Timestamp(f"{day} 00:00").tz_localize(ET) + offset


def to_daily(raw: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Daily bars with a US-market 16:00 ET close time; drops bars not yet closed."""
    df = _clean(raw)
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    days = idx.normalize()
    close_time = [_et_timestamp(d.date(), CLOSE).tz_convert("UTC") for d in days]
    out = df.set_axis(days.tz_localize("UTC"))
    out["close_time"] = pd.DatetimeIndex(close_time)
    return out[out["close_time"] <= now]


def to_four_hour(raw: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Resample 1H regular-session bars into 4H bars: 09:30-13:30 and 13:30-16:00 ET.

    A group is dropped if its boundary is still in the future, or if its final hourly bar
    is missing (so a partially delivered bar is never treated as closed).
    """
    df = _clean(raw)
    et = df.index.tz_convert(ET)
    minutes = et.hour * 60 + et.minute
    grouped = df.assign(ts=et, half=(minutes >= 13 * 60 + 30).astype(int), day=et.date).groupby(["day", "half"])
    out = grouped.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), start=("ts", "min"), last=("ts", "max"),
    )
    boundary = [
        _et_timestamp(day, MIDDAY if half == 0 else CLOSE)
        for day, half in out.index
    ]
    out["close_time"] = pd.DatetimeIndex(boundary).tz_convert("UTC")
    complete = pd.Series([last >= b - pd.Timedelta(hours=1) for last, b in zip(out["last"], boundary)], index=out.index)
    out = out[complete & (out["close_time"] <= now)]
    out = out.set_axis(pd.DatetimeIndex(out["start"]).tz_convert("UTC"))
    return out[OHLCV + ["close_time"]]


def _download(tickers: "list[str]", timeframe: str, now: pd.Timestamp, attempts: int = 3) -> pd.DataFrame:
    if timeframe == "1d":
        kwargs = {"period": "2y", "interval": "1d"}
    else:
        start = (now - pd.Timedelta(days=HOURLY_LOOKBACK_DAYS)).date()
        kwargs = {"start": start, "interval": "1h"}
    for attempt in range(1, attempts + 1):
        try:
            return yf.download(tickers, group_by="ticker", auto_adjust=True, threads=True, progress=False, **kwargs)
        except Exception as exc:  # network / rate limit
            log.warning("download attempt %d/%d failed: %s", attempt, attempts, exc)
            time.sleep(5 * attempt)
    return pd.DataFrame()


def fetch_bars(tickers: "list[str]", timeframe: str, now: pd.Timestamp) -> "tuple[dict[str, pd.DataFrame], list[str]]":
    """Return ({ticker: closed-bar frame}, [tickers that returned no usable data])."""
    shape = to_daily if timeframe == "1d" else to_four_hour
    bars, failed = {}, []
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i : i + BATCH_SIZE]
        raw = _download(chunk, timeframe, now)
        for ticker in chunk:
            try:
                sub = raw[ticker].dropna(how="all") if ticker in raw.columns.get_level_values(0) else None
                frame = shape(sub, now) if sub is not None and not sub.empty else None
            except Exception as exc:
                log.warning("%s %s: %s", ticker, timeframe, exc)
                frame = None
            if frame is None or frame.empty:
                failed.append(ticker)
            else:
                bars[ticker] = frame
    return bars, failed
