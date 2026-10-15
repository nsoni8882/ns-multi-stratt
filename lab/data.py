"""Intraday bars: fetch, cache, session-annotate. Output frames follow the repo convention:
UTC index = bar open, a `close_time` column, and only closed bars. `day` (ET date) and `bar`
(0-based index within the session) are added for the families."""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from lab import config

ET = "America/New_York"
OHLCV = ["open", "high", "low", "close", "volume"]
BAR_MINUTES = {"5Min": 5, "15Min": 15}
CACHE = Path(__file__).parent / ".cache"
OPEN_MIN, CLOSE_MIN = 9 * 60 + 30, 16 * 60


def to_frame(raw: "list[dict]") -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], tz="UTC"))
    df = pd.DataFrame(raw)
    out = pd.DataFrame({"open": df["o"], "high": df["h"], "low": df["l"], "close": df["c"],
                        "volume": df["v"]}).astype(float)
    out.index = pd.DatetimeIndex(pd.to_datetime(df["t"], utc=True))
    return out[~out.index.duplicated()].sort_index()


def regular_session(df: pd.DataFrame) -> pd.DataFrame:
    et = df.index.tz_convert(ET)
    minutes = et.hour * 60 + et.minute
    return df[(minutes >= OPEN_MIN) & (minutes < CLOSE_MIN)]


def with_session(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    out = df.copy()
    out["close_time"] = out.index + pd.Timedelta(minutes=BAR_MINUTES[timeframe])
    out["day"] = out.index.tz_convert(ET).date
    out["bar"] = out.groupby("day").cumcount()
    return out


def to_15min(df5: pd.DataFrame) -> pd.DataFrame:
    """Three 5-minute bars make one 15-minute bar. A bucket missing any (a halt) is dropped,
    never filled, so a partial bar is never presented as closed."""
    et = df5[OHLCV].tz_convert(ET)
    grouped = et.resample("15min")
    agg = grouped.agg({"open": "first", "high": "max", "low": "min", "close": "last",
                       "volume": "sum"})
    return agg[grouped["close"].count() == 3].tz_convert("UTC")


def closed_only(df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    return df[df["close_time"] <= now]


def dev_cutoff(frames: "dict[str, pd.DataFrame]") -> pd.Timestamp:
    """Where development data ends. Everything after it is the sealed holdout, which only
    lab/gate.py may read."""
    latest = max(f.index.max() for f in frames.values())
    return latest - pd.DateOffset(months=config.HOLDOUT_MONTHS)


def _fetch_5min(client, symbol: str, start: datetime, end: datetime, cache_dir: Path) -> pd.DataFrame:
    path = cache_dir / f"{symbol}_5Min.pkl"
    have = pd.read_pickle(path) if path.exists() else to_frame([])
    if len(have):
        start = max(start, have.index.max().to_pydatetime())
    fresh = regular_session(to_frame(client.bars(symbol, "5Min", start, end)))
    df = pd.concat([have, fresh]) if len(have) else fresh
    df = df[~df.index.duplicated(keep="last")].sort_index()
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


def get(client, symbol: str, timeframe: str, start: datetime, end: datetime | None = None,
        cache_dir: Path = CACHE) -> pd.DataFrame:
    end = end or datetime.now(timezone.utc)
    df5 = _fetch_5min(client, symbol, start, end, cache_dir)
    base = df5 if timeframe == "5Min" else to_15min(df5)
    framed = with_session(base, timeframe)
    return closed_only(framed, pd.Timestamp(datetime.now(timezone.utc)))
