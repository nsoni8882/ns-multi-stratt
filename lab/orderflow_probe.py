"""Kill test for order flow: does signed trade imbalance predict the next five minutes of
midquote return? One stock (AAPL), two hours a session (10:00-11:00 and 14:00-15:00 ET), SIP
trades and quotes. Research only: nothing here reaches the gate or any order. If the rank
correlation is near zero, the idea ends here and the full fetcher is not built.

Usage: ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m lab.orderflow_probe --days 1
"""
import argparse
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trader.alpaca import DATA, FEED, Alpaca

ET = ZoneInfo("America/New_York")
CACHE = Path(__file__).parent / ".cache" / "orderflow"
WINDOWS = ((10, 0), (14, 0))  # ET start hours, one hour each
PACE = 0.35  # seconds between calls, inside Alpaca's 200 a minute
HORIZON = 5  # minutes ahead
THIN = 5  # sample every fifth minute so the forward windows do not overlap
MAX_SANE_BPS = 500


def classify(trades: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    """Lee-Ready: a trade above the prevailing midquote is a buy, below is a sell, and a trade
    at the mid takes the sign of the last price change. Columns in: t, p, s (trades); t, bp, ap
    (quotes). Columns out: t, size, side (+1, -1, or 0 if unknown)."""
    q = quotes[(quotes["bp"] > 0) & (quotes["ap"] > quotes["bp"])].copy()
    q["mid"] = (q["bp"] + q["ap"]) / 2
    spread_bps = (q["ap"] - q["bp"]) / q["mid"] * 1e4
    q = q[spread_bps <= MAX_SANE_BPS]
    t = trades.sort_values("t").reset_index(drop=True)
    t = pd.merge_asof(t, q[["t", "mid"]].sort_values("t"), on="t", direction="backward")
    tick = np.sign(t["p"].diff()).fillna(0)
    side = np.sign(t["p"] - t["mid"]).fillna(0)
    side = np.where(side == 0, tick, side)
    return pd.DataFrame({"t": t["t"], "size": t["s"], "side": side})


def minute_imbalance(signed: pd.DataFrame, mids: pd.Series) -> pd.DataFrame:
    """Per minute: imbalance = (buy - sell) / (buy + sell) on signed volume, and the midquote
    return from that minute's close to HORIZON minutes later, in bps."""
    s = signed[signed["side"] != 0].copy()
    s["buy"] = np.where(s["side"] > 0, s["size"], 0.0)
    s["sell"] = np.where(s["side"] < 0, s["size"], 0.0)
    m = s.set_index("t")[["buy", "sell"]].resample("1min").sum()
    m = m[(m["buy"] + m["sell"]) > 0]
    m["imbalance"] = (m["buy"] - m["sell"]) / (m["buy"] + m["sell"])
    close_mid = mids.resample("1min").last().ffill()
    start = close_mid.reindex(m.index + pd.Timedelta(minutes=1)).to_numpy()
    end = close_mid.reindex(m.index + pd.Timedelta(minutes=1 + HORIZON)).to_numpy()
    m["fwd_bps"] = (end / start - 1) * 1e4
    return m.dropna(subset=["fwd_bps"])


def stats(m: pd.DataFrame) -> dict:
    thin = m.iloc[::THIN]
    rho = thin["imbalance"].rank().corr(thin["fwd_bps"].rank())  # Spearman, no scipy needed
    n = len(thin)
    t = rho * np.sqrt((n - 2) / (1 - rho ** 2)) if n > 3 and abs(rho) < 1 else float("nan")
    ranks = thin["imbalance"].rank(pct=True)
    top = thin.loc[ranks >= 0.8, "fwd_bps"].mean()
    bottom = thin.loc[ranks <= 0.2, "fwd_bps"].mean()
    return {"n": n, "spearman": rho, "t": t, "top_fifth_bps": top, "bottom_fifth_bps": bottom}


def fetch(client, path: str, symbol: str, start: datetime, end: datetime) -> list:
    key = "trades" if path.endswith("trades") else "quotes"
    rows, token = [], None
    while True:
        q = {"symbols": symbol, "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "feed": FEED, "limit": 10000, "sort": "asc"}
        if token:
            q["page_token"] = token
        time.sleep(PACE)
        r = client._call(DATA, path, q)
        rows += (r.get(key) or {}).get(symbol, [])
        token = r.get("next_page_token")
        if not token:
            return rows


def window(client, symbol: str, day: str, hour: int) -> "tuple[pd.DataFrame, pd.DataFrame]":
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{symbol}_{day}_{hour:02d}.pkl"
    if f.exists():
        return pd.read_pickle(f)  # a rerun does not refetch
    et_start = datetime.fromisoformat(f"{day}T{hour:02d}:00:00").replace(tzinfo=ET)
    # pad 10 minutes before so the first trade has a quote and the forward window is covered
    start = (et_start - timedelta(minutes=10)).astimezone(timezone.utc)
    end = (et_start + timedelta(hours=1, minutes=HORIZON + 1)).astimezone(timezone.utc)
    trades = pd.DataFrame(fetch(client, "/v2/stocks/trades", symbol, start, end))
    quotes = pd.DataFrame(fetch(client, "/v2/stocks/quotes", symbol, start, end))
    out = (
        pd.DataFrame({"t": pd.to_datetime(trades["t"], utc=True), "p": trades["p"], "s": trades["s"]})
        if len(trades) else pd.DataFrame(columns=["t", "p", "s"]),
        pd.DataFrame({"t": pd.to_datetime(quotes["t"], utc=True), "bp": quotes["bp"], "ap": quotes["ap"]})
        if len(quotes) else pd.DataFrame(columns=["t", "bp", "ap"]),
    )
    pd.to_pickle(out, f)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="AAPL")
    ap.add_argument("--days", type=int, default=1)
    args = ap.parse_args()
    client = Alpaca(os.environ["ALPACA_KEY_ID"], os.environ["ALPACA_SECRET_KEY"])
    today = datetime.now(timezone.utc).date()
    cal = client.calendar((today - timedelta(days=60)).isoformat(), (today - timedelta(days=3)).isoformat())
    days = [r["date"] for r in cal][-args.days:]
    parts = []
    for day in days:
        for hour, _ in WINDOWS:
            tr, qu = window(client, args.symbol, day, hour)
            if tr.empty or qu.empty:
                print(day, hour, "no data")
                continue
            signed = classify(tr, qu)
            mids = ((qu["bp"] + qu["ap"]) / 2).set_axis(qu["t"])
            m = minute_imbalance(signed, mids)
            m["day"] = day
            parts.append(m)
            print(day, f"{hour:02d}:00", "minutes", len(m), "trades", len(tr))
    m = pd.concat(parts)
    res = stats(m)
    print({k: round(v, 4) if isinstance(v, float) else v for k, v in res.items()})


if __name__ == "__main__":
    main()
