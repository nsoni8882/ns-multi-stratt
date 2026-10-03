"""Measure Trend Pullback variants over a long daily history.

Usage:
    python -m research.measure --tickers 165 --years 12 --horizon 20

For every bar in the sample this evaluates the same `rule_side` the live scanner uses, then
scores the forward return over `horizon` bars against a buy-and-hold baseline for the same
ticker over the same window. Writes a markdown table and the raw per-signal rows to
research/results/.

Two statistical cautions are built in rather than left to the reader:

* **Overlap.** Signals from one ticker fire in clusters, so their 20-bar windows overlap and
  a naive t-stat over all of them is badly overstated. Every table reports an independent
  sample too -- signals thinned per ticker and side so no two windows overlap -- and the
  independent t is the one to believe.
* **Baseline.** "Alpha" is the signal's forward return minus the mean forward return of all
  bars of that same ticker in the same window, so a name that simply drifted up over 12 years
  gets no credit for that drift.

Survivorship: the universe is today's S&P 500, so names that fell out of the index over the
window are absent. This inflates every variant's raw return roughly equally, which is why
alpha against the per-ticker baseline is the number compared, not the raw mean.
"""
import argparse
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from scanner.data import to_daily
from scanner.strategies.trend_pullback import VARIANTS, MIN_BARS, TrendPullback, rule_side
from scanner.universe import load_universe

CACHE_DIR = Path(__file__).parent / ".cache"
RESULTS_DIR = Path(__file__).parent / "results"
BATCH = 40
PAUSE = 1.5

log = logging.getLogger("measure")


# --- data -------------------------------------------------------------------------------

def _download(tickers: "list[str]", years: int) -> pd.DataFrame:
    for attempt in range(1, 4):
        try:
            return yf.download(tickers, period=f"{years}y", interval="1d", group_by="ticker",
                               auto_adjust=True, threads=True, progress=False)
        except Exception as exc:
            log.warning("attempt %d/3 failed: %s", attempt, exc)
            time.sleep(5 * attempt)
    return pd.DataFrame()


def fetch_history(tickers: "list[str]", years: int, now: pd.Timestamp) -> "dict[str, pd.DataFrame]":
    """Daily closed bars per ticker, cached to research/.cache so re-runs are offline."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out, missing = {}, []
    for t in tickers:
        path = CACHE_DIR / f"{t}_{years}y.parquet"
        if path.exists():
            out[t] = pd.read_parquet(path)
        else:
            missing.append(t)

    for i in range(0, len(missing), BATCH):
        chunk = missing[i : i + BATCH]
        raw = _download(chunk, years)
        for t in chunk:
            try:
                sub = raw[t].dropna(how="all") if t in raw.columns.get_level_values(0) else None
                if sub is None or sub.empty:
                    continue
                frame = to_daily(sub, now)
            except Exception as exc:
                log.warning("%s: %s", t, exc)
                continue
            if not frame.empty:
                frame.to_parquet(CACHE_DIR / f"{t}_{years}y.parquet")
                out[t] = frame
        log.info("fetched %d/%d", min(i + BATCH, len(missing)), len(missing))
        if i + BATCH < len(missing):
            time.sleep(PAUSE)
    return out


def pick_tickers(count: int, universe: "pd.DataFrame | None" = None) -> "list[str]":
    """A deterministic stride through the sorted universe -- spreads the sample across the
    alphabet (and so across sectors) instead of taking a block of A names."""
    universe = universe if universe is not None else load_universe()
    universe = sorted(universe["ticker"].tolist())
    if count >= len(universe):
        return universe
    stride = len(universe) / count
    return [universe[int(i * stride)] for i in range(count)]


# --- measurement ------------------------------------------------------------------------

@dataclass(frozen=True)
class Row:
    ticker: str
    bar: int  # positional index of the signal bar
    side: str
    conviction: str
    fwd: float  # forward return over the horizon
    baseline: float  # mean forward return of every scored bar of this ticker


def scan_ticker(df: pd.DataFrame, cfg, horizon: int) -> "list[Row]":
    """Evaluate every bar with enough history, and score the ones that fire."""
    close = df["close"].to_numpy(dtype=float)
    last = len(df) - horizon  # a signal needs a full forward window to be scorable
    if last <= MIN_BARS:
        return []
    fwd = close[horizon:] / close[:-horizon] - 1.0  # fwd[i] is the return from bar i
    baseline = float(np.nanmean(fwd[MIN_BARS:last]))

    ind = TrendPullback(cfg).indicators(df)
    rows = []
    for i in range(MIN_BARS, last):
        hit = rule_side(**ind, i=i, cfg=cfg)
        if hit:
            side, conviction = hit
            rows.append(Row(df.attrs.get("ticker", ""), i, side, conviction, float(fwd[i]), baseline))
    return rows


def independent(rows: "list[Row]", horizon: int) -> "list[Row]":
    """Thin to non-overlapping windows per ticker and side, keeping the earliest of a cluster."""
    kept, last_bar = [], {}
    for r in sorted(rows, key=lambda r: (r.ticker, r.side, r.bar)):
        key = (r.ticker, r.side)
        if key not in last_bar or r.bar - last_bar[key] >= horizon:
            kept.append(r)
            last_bar[key] = r.bar
    return kept


def stats(rows: "list[Row]", horizon: int) -> dict:
    if not rows:
        return {"n": 0}
    alpha = np.array([r.fwd - r.baseline for r in rows])
    fwd = np.array([r.fwd for r in rows])
    ind = independent(rows, horizon)
    ind_alpha = np.array([r.fwd - r.baseline for r in ind])

    def t_stat(x):
        return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 1 and x.std(ddof=1) > 0 else float("nan")

    return {
        "n": len(rows),
        "mean": float(fwd.mean()),
        "baseline": float(np.mean([r.baseline for r in rows])),
        "alpha": float(alpha.mean()),
        "win": float((fwd > 0).mean()),
        "t_naive": t_stat(alpha),
        "n_independent": len(ind),
        "alpha_independent": float(ind_alpha.mean()),
        "t_independent": t_stat(ind_alpha),
    }


def measure(bars: "dict[str, pd.DataFrame]", labels: "list[str]", horizon: int) -> dict:
    results = {}
    for label in labels:
        cfg = VARIANTS[label]
        rows = []
        for ticker, df in bars.items():
            df.attrs["ticker"] = ticker
            rows.extend(scan_ticker(df, cfg, horizon))
        buys = [r for r in rows if r.side == "BUY"]
        sells = [r for r in rows if r.side == "SELL"]
        results[label] = {
            "BUY": stats(buys, horizon),
            "SELL": stats(sells, horizon),
            "by_conviction": {
                c: stats([r for r in buys if r.conviction == c], horizon)
                for c in sorted({r.conviction for r in buys})
            },
        }
        log.info("%s: %d BUY, %d SELL", label, len(buys), len(sells))
    return results


# --- reporting --------------------------------------------------------------------------

HEADER = "| variant | leg | n | mean | baseline | alpha | win % | n indep | alpha indep | t indep |"
DIVIDER = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"


def _row(variant: str, leg: str, s: dict) -> str:
    if not s["n"]:
        return f"| {variant} | {leg} | 0 | | | | | | | |"
    return (f"| {variant} | {leg} | {s['n']:,} | {s['mean']:+.2%} | {s['baseline']:+.2%} | "
            f"{s['alpha']:+.2%} | {s['win']:.1%} | {s['n_independent']:,} | "
            f"{s['alpha_independent']:+.2%} | {s['t_independent']:+.2f} |")


def to_markdown(results: dict, meta: dict) -> str:
    lines = [
        "# Trend Pullback variant measurement",
        "",
        f"{meta['tickers']} S&P names, {meta['years']}y of daily bars "
        f"({meta['bars']:,} scored bars), {meta['horizon']}-bar forward horizon. "
        f"Generated {meta['generated']}.",
        "",
        "`alpha` is the signal's forward return minus the same ticker's mean forward return "
        "over the same window. `n indep` thins signals so no two forward windows overlap, and "
        "`t indep` is the t-stat on that independent sample -- the naive t over all overlapping "
        "signals runs 2-3x higher and should be ignored.",
        "",
        HEADER, DIVIDER,
    ]
    for label, legs in results.items():
        lines.append(_row(label, "BUY", legs["BUY"]))
        lines.append(_row(label, "SELL", legs["SELL"]))
    lines += ["", "## BUY leg by conviction tier", "", HEADER, DIVIDER]
    for label, legs in results.items():
        for tier, s in legs["by_conviction"].items():
            lines.append(_row(label, f"BUY/{tier}", s))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", type=int, default=165)
    parser.add_argument("--years", type=int, default=12)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS))
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    unknown = [v for v in args.variants if v not in VARIANTS]
    if unknown:
        parser.error(f"unknown variants {unknown}; available: {list(VARIANTS)}")

    now = pd.Timestamp.now(tz="UTC")
    tickers = pick_tickers(args.tickers)
    bars = fetch_history(tickers, args.years, now)
    usable = {t: df for t, df in bars.items() if len(df) > MIN_BARS + args.horizon}
    log.info("%d tickers fetched, %d with enough history", len(bars), len(usable))
    if not usable:
        log.error("no usable history")
        return 1

    results = measure(usable, args.variants, args.horizon)
    meta = {
        "tickers": len(usable),
        "years": args.years,
        "horizon": args.horizon,
        "bars": sum(len(df) for df in usable.values()),
        "generated": now.strftime("%Y-%m-%d"),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "trend_pullback.md").write_text(to_markdown(results, meta))
    (args.out / "trend_pullback.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    print(to_markdown(results, meta))
    log.info("wrote %s", args.out / "trend_pullback.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
