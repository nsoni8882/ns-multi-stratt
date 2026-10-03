"""Write the JSON files the website reads."""
import json
import math
from pathlib import Path

import pandas as pd

from scanner.indicators import ema, macd, rsi

CHART_BARS = 250


def unix(ts: pd.Timestamp) -> int:
    return int(ts.timestamp())


def _num(value) -> "float | None":
    return None if value is None or pd.isna(value) or math.isinf(value) else round(float(value), 4)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, allow_nan=False, separators=(",", ":")))


SPARK_BARS = 30


def signal_row(ticker: str, name: str, sector: str, sig, closes: pd.Series) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "price": round(sig.entry_price, 4),
        "side": sig.side,
        "conviction": sig.conviction,
        # True when the signal fired on an earlier bar and RSI has since crossed back past
        # the level that triggered it: the setup the card describes no longer holds.
        "invalidated": sig.invalidated,
        "bars_ago": sig.bars_ago,
        "fired_at": sig.fired_at.isoformat(),
        "bar_time": unix(sig.bar_time),
        "details": sig.details,
        "spark": [_num(v) for v in closes.iloc[-SPARK_BARS:]],
    }


def chart_payload(ticker: str, timeframe: str, df: pd.DataFrame, signals: "list[dict]") -> dict:
    close = df["close"]
    m = macd(close)
    series = {
        "macd": m["macd"], "signal": m["signal"], "hist": m["hist"],
        "rsi": rsi(close), "ema50": ema(close, 50), "ema200": ema(close, 200),
    }
    tail = df.iloc[-CHART_BARS:]
    take = lambda s: [_num(v) for v in s.iloc[-CHART_BARS:]]  # noqa: E731
    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "bars": [
            [unix(ts), _num(r.open), _num(r.high), _num(r.low), _num(r.close), _num(r.volume)]
            for ts, r in zip(tail.index, tail.itertuples())
        ],
        "macd": {"macd": take(series["macd"]), "signal": take(series["signal"]), "hist": take(series["hist"])},
        "rsi": take(series["rsi"]),
        "ema50": take(series["ema50"]),
        "ema200": take(series["ema200"]),
        "signals": signals,
    }
