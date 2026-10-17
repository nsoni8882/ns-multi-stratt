"""Hermes funnel diagnostic: what happened to the setups it denied, on a record with no lookahead.

Hermes (the user's earlier swing-trading app) logs every setup its gates blocked, on the day it was
blocked, with the entry, stop and targets it would have used and later price checks. That is a
point-in-time counterfactual no backtest here can give. Usage:
    .venv/bin/python -m research.hermes_denied path/to/tracker.db   (read-only; never committed)

Declared 2026-10-17 before any outcome was looked at (counts and column names only).

What counts as a trade. A breakout setup is only entered when price crosses its pivot, so a stop hit
before `pivot_cross_date` (or with no cross at all) is a trade that never existed: 594 of 1,047
breakout-gate denials are that, and counting them as losses is the contamination to avoid. Only rows
with a `pivot_cross_date` are scored, and only the first event on or after it counts: stop or first
target, whichever date is earlier, a same-day tie going to the stop; neither means marked to the
last checked price. Outcome is the return on the entry price, no cost (a stop or target fill is not a
cost model; that only makes this generous).

Two tests, no more, on the denied rows that crossed plus the setups Hermes actually took:
  1. Does a setup that crosses its pivot make money? Mean outcome positive, t >= 2.5 clustered by
     calendar week of the setup date.
  2. Does the funnel's composite score rank them? Top-third minus bottom-third composite, mean
     outcome difference positive, t >= 2.0 clustered by week.
The sample is one regime (June to October 2026), so a pass would be a lead, not a verdict, and the
numbers are reported with their counts.
"""
import sqlite3
import sys

import numpy as np
import pandas as pd


def load(path: str) -> "tuple[pd.DataFrame, pd.DataFrame]":
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    denied = pd.read_sql("select date, ticker, tier, composite, entry_price, stop_price, tp1_price, "
                         "denial_reason, last_check_price, tp1_hit_date, stop_hit_date, pivot_cross_date "
                         "from denied_setups", con)
    taken = pd.read_sql("select date, ticker, tier, composite, outcome_return, status from recommendations "
                        "where status in ('LOSS','WIN_TP1','WIN_TP2','CLOSED','CLOSED_MANUAL')", con)
    return denied, taken


def outcome(r: pd.Series) -> "tuple[float, str]":
    """Return and what ended it, for one denied setup that crossed its pivot."""
    cross = pd.Timestamp(r["pivot_cross_date"])
    stop = pd.Timestamp(r["stop_hit_date"]) if pd.notna(r["stop_hit_date"]) else None
    tp1 = pd.Timestamp(r["tp1_hit_date"]) if pd.notna(r["tp1_hit_date"]) else None
    stop = stop if stop is not None and stop >= cross else None
    tp1 = tp1 if tp1 is not None and tp1 >= cross else None
    e = r["entry_price"]
    if stop is not None and (tp1 is None or stop <= tp1):
        return r["stop_price"] / e - 1.0, "stop"
    if tp1 is not None:
        return r["tp1_price"] / e - 1.0, "tp1"
    return (r["last_check_price"] / e - 1.0 if pd.notna(r["last_check_price"]) else np.nan), "open"


def scored(denied: pd.DataFrame, taken: pd.DataFrame) -> pd.DataFrame:
    d = denied[denied["pivot_cross_date"].notna() & (denied["entry_price"] > 0)].copy()
    res = d.apply(outcome, axis=1, result_type="expand")
    d["ret"], d["end"] = res[0], res[1]
    d["source"] = "denied:" + d["denial_reason"]
    t = taken.rename(columns={"outcome_return": "ret"}).copy()
    t["ret"] = t["ret"] / 100.0
    t["end"], t["source"] = t["status"].str.lower(), "taken"
    cols = ["date", "ticker", "tier", "composite", "ret", "end", "source"]
    return pd.concat([d[cols], t[cols]], ignore_index=True).dropna(subset=["ret", "composite"])


def cluster_t(df: pd.DataFrame, value: str = "ret") -> dict:
    """Mean of `value`, t clustered by calendar week of the setup date."""
    x = df[value]
    if len(x) < 3:
        return {"n": len(x), "mean": float("nan"), "t": float("nan")}
    m = x.mean()
    g = (x - m).groupby(pd.to_datetime(df["date"]).dt.to_period("W")).sum()
    se = np.sqrt((g ** 2).sum()) / len(x)
    return {"n": len(x), "mean": float(m), "t": float(m / se) if se > 0 else float("nan")}


def tercile_spread(df: pd.DataFrame) -> dict:
    lo, hi = df["composite"].quantile([1 / 3, 2 / 3])
    top, bot = df[df["composite"] >= hi], df[df["composite"] <= lo]
    diff = pd.concat([top.assign(w=1.0), bot.assign(w=-1.0)])
    diff["v"] = diff["ret"] * diff["w"] * 2  # mean of the signed rows is half the difference
    out = cluster_t(diff.assign(ret=diff["v"]))
    return out | {"top_mean": float(top["ret"].mean()), "bottom_mean": float(bot["ret"].mean()),
                  "n_top": len(top), "n_bottom": len(bot)}


def main(path: str) -> int:
    denied, taken = load(path)
    df = scored(denied, taken)
    print(f"{len(df)} setups that crossed their pivot or were taken "
          f"({(df['source'] == 'taken').sum()} taken), {df['date'].min()} to {df['date'].max()}")
    print("\nended by:", df["end"].value_counts().to_dict())
    print("\nTest 1, mean outcome and clustered t:")
    for name, g in [("all", df)] + [(s, g) for s, g in df.groupby("source")]:
        c = cluster_t(g)
        print(f"  {name:28s} n={c['n']:4d} mean {c['mean']:+.2%} t {c['t']:+.2f}")
    s = tercile_spread(df)
    print(f"\nTest 2, composite top third {s['top_mean']:+.2%} (n={s['n_top']}) vs bottom third "
          f"{s['bottom_mean']:+.2%} (n={s['n_bottom']}): difference {s['mean']:+.2%}, clustered t {s['t']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
