"""Hermes denied setups, re-simulated on independent price bars.

`hermes_denied.py` scored Hermes's own recorded hit dates and found +6% a setup (t 6). That is not
believed: 44 of its 106 target hits fall on the pivot-cross day itself, a move to +16% in a day that
cannot be filled at the pivot, and the recorded dates are not ordered within a day. Superseded by
this, which uses only Hermes's levels (entry, stop, first target, setup date) and Yahoo daily bars.

Declared 2026-10-17 before this was run.

Simulation, every denied setup, conservative at each ambiguity:
  trigger  -- entry_price is a buy-stop. First session after the setup date, within 15 sessions,
              whose high reaches it. Filled at max(open, entry_price): a gap up pays the gap.
  exit     -- from the fill bar on: stop if the low reaches the stop level, exited at min(open, stop)
              (a gap down pays the gap); first target if the high reaches it, exited at the target
              level. Both in one bar: the stop. Neither within 30 sessions of the fill: the close
              on the 30th. Cost 11 bps.
Setups that never trigger are not trades and are not scored.

Two tests, the same as before, and no more:
  1. Do triggered setups make money? Mean return positive, t >= 2.5 clustered by calendar week of the
     setup date.
  2. Does the composite score rank them? Top third minus bottom third, difference positive,
     t >= 2.0 clustered by week.
One regime, June to October 2026: a pass is a lead, not a verdict.
"""
import sqlite3
import sys

import numpy as np
import pandas as pd
import yfinance as yf

from research.hermes_denied import cluster_t, tercile_spread

COST = 0.0011
TRIGGER_WINDOW, MAX_HOLD = 15, 30


def load(path: str) -> pd.DataFrame:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    return pd.read_sql("select date, ticker, tier, composite, entry_price, stop_price, tp1_price, denial_reason "
                       "from denied_setups where entry_price > 0 and stop_price > 0 and tp1_price > 0", con)


def simulate(bars: pd.DataFrame, setup_date: str, entry: float, stop: float, tp1: float) -> "tuple[float, str] | None":
    """Return and what ended it for one setup on its ticker's daily bars, None if it never triggered."""
    after = bars[bars.index > pd.Timestamp(setup_date)]
    window = after.iloc[:TRIGGER_WINDOW]
    hit = window[window["High"] >= entry]
    if hit.empty:
        return None
    fill_day = hit.index[0]
    fill = max(float(hit.iloc[0]["Open"]), entry)
    run = after.loc[fill_day:].iloc[:MAX_HOLD]
    for i, (_, b) in enumerate(run.iterrows()):
        if b["Low"] <= stop:
            return min(float(b["Open"]) if i else stop, stop) / fill - 1.0 - COST, "stop"
        if b["High"] >= tp1:
            return tp1 / fill - 1.0 - COST, "tp1"
    return float(run.iloc[-1]["Close"]) / fill - 1.0 - COST, "time" if len(run) >= MAX_HOLD else "open"


def prices(tickers: "list[str]", start: str) -> "dict[str, pd.DataFrame]":
    out = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        raw = yf.download(chunk, start=start, auto_adjust=True, group_by="ticker", threads=True, progress=False)
        for t in chunk:
            try:
                sub = raw[t].dropna(how="all")
            except KeyError:
                continue
            if not sub.empty:
                out[t] = sub
    return out


def main(path: str) -> int:
    d = load(path)
    bars = prices(sorted(d["ticker"].unique()), "2026-05-01")
    print(f"{len(d)} denied setups, {d['ticker'].nunique()} tickers, {len(bars)} with prices")
    rows = []
    for r in d.itertuples():
        if r.ticker not in bars:
            continue
        s = simulate(bars[r.ticker], r.date, r.entry_price, r.stop_price, r.tp1_price)
        if s is not None:
            rows.append((r.date, r.ticker, r.denial_reason, r.composite, s[0], s[1]))
    df = pd.DataFrame(rows, columns=["date", "ticker", "reason", "composite", "ret", "end"])
    print(f"{len(df)} triggered; ended by {df['end'].value_counts().to_dict()}")
    print("\nTest 1, mean return net of cost, t clustered by week:")
    for name, g in [("all", df)] + list(df.groupby("reason")):
        c = cluster_t(g)
        print(f"  {name:22s} n={c['n']:4d} mean {c['mean']:+.2%} t {c['t']:+.2f}")
    s = tercile_spread(df)
    print(f"\nTest 2, composite top third {s['top_mean']:+.2%} (n={s['n_top']}) vs bottom third "
          f"{s['bottom_mean']:+.2%} (n={s['n_bottom']}): difference {s['mean']:+.2%}, t {s['t']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
