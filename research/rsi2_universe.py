"""Does the daily RSI(2) rule hold beyond AMZN and AAPL?

The live rule (research/rsi2/rsi2_edge_backtest.py: RSI(2) < 10 and close above SMA(200), exit on
RSI(2) > 65 or 10 bars) was measured on two names, and those two may have been picked because
they showed it. This runs the same rule on every name in the point-in-time S&P 500
(`research/pit.py`), a trade counting only if the name was a member on its signal day.

Declared 2026-10-17 before any number existed.

Variants, two and no more:
  rsi2  -- the live rule exactly.
  ibs   -- the same shape with the close-location trigger: IBS = (close-low)/(high-low) < 0.2 and
           close > SMA(200); exit at IBS > 0.8 or 10 bars. A cousin of the same mean-reversion
           mechanism, so it counts as one more look at it, not a new idea.

Bar. Decisive number: `t by week`, the trade's alpha averaged within each calendar week of its
signal date, then a t-stat across weeks. Not by date: holds run up to 10 sessions, so trades
signalled on adjacent days overlap, and a market-wide dip fires dozens of names at once.
All must hold, on the universe *excluding AMZN and AAPL* (they were selected on this rule):
  1. alpha (trade return less the name's own drift over the same hold) positive after 5.5 bps
  2. t by week >= 2.5
  3. positive in both halves, net of cost
  4. positive with the best year removed
  5. >= 500 signal weeks
And, separately reported: where AMZN and AAPL rank among the names by mean net trade return.
"""
import argparse
import importlib.util
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from research import pit
from research.measure import RESULTS_DIR, fetch_history

log = logging.getLogger("rsi2_universe")
COST = 0.00055  # round trip, what the lab charged per trade
MAX_HOLD = 10
SELECTED = ("AMZN", "AAPL")

_spec = importlib.util.spec_from_file_location(
    "rsi2_edge_backtest", Path(__file__).parent / "rsi2" / "rsi2_edge_backtest.py")
_edge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_edge)
wilder_rsi = _edge.wilder_rsi


def signals(df: pd.DataFrame, variant: str) -> "tuple[np.ndarray, np.ndarray]":
    """(entry, exit) booleans per bar, decided on that bar's close."""
    close = df["close"]
    trend = close > close.rolling(200).mean()
    if variant == "rsi2":
        rsi = wilder_rsi(close, 2)
        return ((rsi < 10) & trend).fillna(False).to_numpy(), (rsi > 65).fillna(False).to_numpy()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    ibs = (close - df["low"]) / rng
    return ((ibs < 0.2) & trend).fillna(False).to_numpy(), (ibs > 0.8).fillna(False).to_numpy()


def trades(ticker: str, df: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Same loop as rsi2_edge_backtest.backtest: signal on bar i-1's close, buy that close, so
    the first return earned is bar i's. One position at a time per name."""
    entry, exit_ = signals(df, variant)
    close = df["close"].to_numpy()
    ret = np.r_[np.nan, close[1:] / close[:-1] - 1.0]
    drift = float(np.nanmean(ret))
    rows, i = [], 1
    while i < len(close):
        if entry[i - 1] and not np.isnan(ret[i]):
            gross, hold, j = 0.0, 0, i
            while j < len(close):
                gross += ret[j]; hold += 1
                if exit_[j] or hold >= MAX_HOLD:
                    break
                j += 1
            if j < len(close):  # a trade still open at the end of the data is not scored
                rows.append((ticker, df.index[i - 1], hold, gross - COST, gross - COST - hold * drift))
            i = j + 1
        else:
            i += 1
    return pd.DataFrame(rows, columns=["ticker", "signal", "bars", "net", "alpha"])


def universe_trades(bars: "dict[str, pd.DataFrame]", member: pd.DataFrame, variant: str) -> pd.DataFrame:
    parts = []
    for t, df in bars.items():
        if len(df) < 260 or t not in member.columns:
            continue
        tr = trades(t, df, variant)
        if tr.empty:
            continue
        tr = tr[member[t].reindex(tr["signal"]).fillna(False).to_numpy()]
        if not tr.empty:
            parts.append(tr)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["ticker", "signal", "bars", "net", "alpha"])


def by_week(tr: pd.DataFrame) -> dict:
    """Alpha averaged within each calendar week of the signal date, then a t across weeks."""
    if tr.empty:
        return {"weeks": 0, "alpha": float("nan"), "t": float("nan")}
    wk = tr.groupby(tr["signal"].dt.tz_localize(None).dt.to_period("W"))["alpha"].mean()
    sd = wk.std(ddof=1)
    return {"weeks": len(wk), "alpha": float(wk.mean()),
            "t": float(wk.mean() / (sd / np.sqrt(len(wk)))) if len(wk) > 1 and sd > 0 else float("nan")}


def summary(tr: pd.DataFrame) -> dict:
    return by_week(tr) | {"trades": len(tr), "net_mean": float(tr["net"].mean()) if len(tr) else float("nan"),
                          "win": float((tr["net"] > 0).mean()) if len(tr) else float("nan")}


def evaluate(tr: pd.DataFrame) -> dict:
    mid = tr["signal"].sort_values().iloc[len(tr) // 2] if len(tr) else None
    years = tr["signal"].dt.year
    best = years[tr.groupby(years)["alpha"].transform("mean").idxmax()] if len(tr) else None
    return {"all": summary(tr),
            "first_half": summary(tr[tr["signal"] < mid]) if mid is not None else {},
            "second_half": summary(tr[tr["signal"] >= mid]) if mid is not None else {},
            "best_year": int(best) if best is not None else None,
            "without_best_year": summary(tr[years != best]) if best is not None else {},
            "by_year": {int(y): float(v) for y, v in tr.groupby(years)["alpha"].mean().items()}}


def selected_rank(tr: pd.DataFrame) -> dict:
    per = tr.groupby("ticker")["net"].mean().sort_values(ascending=False)
    return {t: {"rank": int(list(per.index).index(t)) + 1, "of": len(per), "net_bps": float(per[t] * 1e4)}
            for t in SELECTED if t in per.index} | {"median_net_bps": float(per.median() * 1e4)}


def fmt(s: dict) -> str:
    return (f"{s['trades']:,} trades, {s['weeks']} weeks, alpha {s['alpha']:+.2%}, "
            f"**t by week {s['t']:+.2f}**, net/trade {s['net_mean'] * 1e4:+.0f} bps, win {s['win']:.0%}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "rsi2-universe")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    member = pit.load()
    bars = fetch_history(sorted(member.columns), 12, pd.Timestamp.now(tz="UTC"))
    log.info("%d symbols with prices", len(bars))
    lines = ["# RSI(2) across the point-in-time S&P 500", "", f"{len(bars)} symbols with prices. "
             "Alpha = trade return net of 5.5 bps less the name's own drift over the hold. "
             "Decisive: t by week, on the universe excluding AMZN and AAPL.", ""]
    for variant in ("rsi2", "ibs"):
        tr = universe_trades(bars, member, variant)
        rest = tr[~tr["ticker"].isin(SELECTED)]
        ev, rank = evaluate(rest), selected_rank(tr)
        lines += [f"## {variant}", "", f"- all names: {fmt(summary(tr))}", f"- excluding AMZN/AAPL: {fmt(ev['all'])}",
                  f"- first half: {fmt(ev['first_half'])}", f"- second half: {fmt(ev['second_half'])}",
                  f"- without {ev['best_year']}: {fmt(ev['without_best_year'])}",
                  f"- AMZN/AAPL among names by mean net trade: {rank}", "",
                  "| year | " + " | ".join(map(str, ev["by_year"])) + " |",
                  "|---|" + "---:|" * len(ev["by_year"]),
                  "| alpha | " + " | ".join(f"{v:+.2%}" for v in ev["by_year"].values()) + " |", ""]
        log.info("%s: rest %s", variant, fmt(ev["all"]))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "rsi2_universe.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
