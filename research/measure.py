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
from scanner.strategies import macd_rsi_reversal as reversal
from scanner.strategies import trend_pullback as pullback


@dataclass(frozen=True)
class Target:
    """One strategy, in the shape the harness needs. Both strategies expose the same three
    things -- a config per variant, an `indicators(df)` dict and a pure `rule_side` over it --
    so the measurement code below never needs to know which one it is scoring."""

    strategy: type
    rule_side: "callable"
    variants: dict
    min_bars: int
    slug: str


TARGETS = {
    "trend-pullback": Target(pullback.TrendPullback, pullback.rule_side, pullback.VARIANTS,
                             pullback.MIN_BARS, "trend_pullback"),
    "macd-rsi-reversal": Target(reversal.MacdRsiReversal, reversal.rule_side, reversal.VARIANTS,
                                reversal.MIN_BARS, "macd_rsi_reversal"),
}
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
    """Daily closed bars per ticker, cached to research/.cache so re-runs are offline.

    Pickled rather than parquet: the cache is gitignored, local and disposable, which is not
    worth a pyarrow dependency in requirements.txt.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out, missing = {}, []
    for t in tickers:
        path = CACHE_DIR / f"{t}_{years}y.pkl"
        if path.exists():
            out[t] = pd.read_pickle(path)
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
                frame.to_pickle(CACHE_DIR / f"{t}_{years}y.pkl")
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
    year: int  # calendar year of the signal bar
    side: str
    conviction: str
    fwd: float  # forward return over the horizon
    baseline: float  # mean forward return of every scored bar of this ticker


def unconditional(bars: "dict[str, pd.DataFrame]", horizon: int, min_bars: int) -> dict:
    """The do-nothing benchmark: every scored bar's forward return, signal or not. A signal
    win rate only means something next to this -- 58% looks strong until you see that any
    random 20-day hold in this sample wins 58% of the time too."""
    rets = []
    for df in bars.values():
        c = df["close"].to_numpy(dtype=float)
        last = len(df) - horizon
        if last > min_bars:
            rets.append((c[horizon:] / c[:-horizon] - 1.0)[min_bars:last])
    if not rets:
        return {"n": 0}
    all_rets = np.concatenate(rets)
    return {"n": len(all_rets), "mean": float(all_rets.mean()), "win": float((all_rets > 0).mean())}


def by_year(rows: "list[Row]", horizon: int) -> "dict[int, dict]":
    """Per-calendar-year stats for a BUY cohort. A sub-period split can hide a single bad
    quarter; the year table is what shows whether one crash is carrying the whole result."""
    years = {}
    for r in rows:
        years.setdefault(r.year, []).append(r)
    return {y: stats(rs, horizon, "BUY") for y, rs in sorted(years.items())}


def scan_ticker(df: pd.DataFrame, cfg, horizon: int, target: Target) -> "list[Row]":
    """Evaluate every bar with enough history, and score the ones that fire."""
    close = df["close"].to_numpy(dtype=float)
    last = len(df) - horizon  # a signal needs a full forward window to be scorable
    if last <= target.min_bars:
        return []
    fwd = close[horizon:] / close[:-horizon] - 1.0  # fwd[i] is the return from bar i
    baseline = float(np.nanmean(fwd[target.min_bars:last]))

    ind = target.strategy(cfg).indicators(df)
    rows = []
    for i in range(target.min_bars, last):
        hit = target.rule_side(**ind, i=i, cfg=cfg)
        if hit:
            side, conviction = hit
            rows.append(Row(df.attrs.get("ticker", ""), i, df.index[i].year, side, conviction,
                            float(fwd[i]), baseline))
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


def position(r: Row, side: str) -> "tuple[float, float]":
    """(return to the position, the benchmark it has to beat) for one signal.

    A BUY earns the stock's forward return and has to beat holding that same stock, so its
    benchmark is the ticker's own drift. A SELL earns the *negated* forward return -- the
    stock rising is a loss -- and its alternative is sitting in cash, not holding the name
    it is shorting, so its benchmark is zero. Scoring a short against the long baseline
    would make a losing short look like a winner whenever the stock rose less than usual.
    """
    if side == "BUY":
        return r.fwd, r.baseline
    return -r.fwd, 0.0


def stats(rows: "list[Row]", horizon: int, side: str = "BUY") -> dict:
    if not rows:
        return {"n": 0}
    scored = [position(r, side) for r in rows]
    ret = np.array([s[0] for s in scored])
    base = np.array([s[1] for s in scored])
    ind = independent(rows, horizon)
    ind_alpha = np.array([a - b for a, b in (position(r, side) for r in ind)])

    def t_stat(x):
        return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 1 and x.std(ddof=1) > 0 else float("nan")

    return {
        "n": len(rows),
        "mean": float(ret.mean()),
        "baseline": float(base.mean()),
        "alpha": float((ret - base).mean()),
        "win": float((ret > 0).mean()),
        "t_naive": t_stat(ret - base),
        "n_independent": len(ind),
        "alpha_independent": float(ind_alpha.mean()),
        "t_independent": t_stat(ind_alpha),
    }


def era_midpoints(bars: "dict[str, pd.DataFrame]", horizon: int, min_bars: int) -> "dict[str, int]":
    """The bar that splits each ticker's scored range in half, for the sub-period check."""
    return {t: (min_bars + len(df) - horizon) // 2 for t, df in bars.items()}


def measure(bars: "dict[str, pd.DataFrame]", labels: "list[str]", horizon: int,
            target: Target) -> dict:
    mid = era_midpoints(bars, horizon, target.min_bars)
    results = {}
    for label in labels:
        cfg = target.variants[label]
        rows = []
        for ticker, df in bars.items():
            df.attrs["ticker"] = ticker
            rows.extend(scan_ticker(df, cfg, horizon, target))
        buys = [r for r in rows if r.side == "BUY"]
        sells = [r for r in rows if r.side == "SELL"]
        tiers = sorted({r.conviction for r in buys})
        # A finding that only holds in one half of a 12-year sample is a period artefact,
        # so every BUY cohort is reported split as well as pooled.
        def eras(subset):
            first = [r for r in subset if r.bar < mid[r.ticker]]
            second = [r for r in subset if r.bar >= mid[r.ticker]]
            return {"first": stats(first, horizon, "BUY"), "second": stats(second, horizon, "BUY")}

        results[label] = {
            "BUY": stats(buys, horizon, "BUY"),
            "SELL": stats(sells, horizon, "SELL"),
            "by_conviction": {c: stats([r for r in buys if r.conviction == c], horizon, "BUY") for c in tiers},
            "eras": {"BUY": eras(buys)} | {
                f"BUY/{c}": eras([r for r in buys if r.conviction == c]) for c in tiers
            },
            "by_year": {"BUY": by_year(buys, horizon)} | {
                f"BUY/{c}": by_year([r for r in buys if r.conviction == c], horizon) for c in tiers
            },
        }
        log.info("%s: %d BUY, %d SELL", label, len(buys), len(sells))
    return results


# --- reporting --------------------------------------------------------------------------

def _all_years(results: dict) -> "list[int]":
    years = {y for legs in results.values() for c in legs.get("by_year", {}).values() for y in c}
    return sorted(years)


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
        f"({meta['bars']:,} bars fetched, {meta['base']['n']:,} of them scored once the "
        f"warm-up and the trailing forward window are excluded), "
        f"{meta['horizon']}-bar forward horizon. Generated {meta['generated']}.",
        "",
        f"**Do-nothing benchmark:** across those {meta['base']['n']:,} scored bars, a random "
        f"{meta['horizon']}-bar hold returned {meta['base']['mean']:+.2%} and was positive "
        f"{meta['base']['win']:.1%} of the time. Any signal's win rate has to be read against "
        f"that number, not against 50%.",
        "",
        "`mean` is the return to the *position*, so a SELL row is the short's P&L: the stock "
        "rising is a loss. `baseline` is what that position has to beat -- the ticker's own "
        "mean forward return for a BUY (12 years of drift earns no credit), cash for a SELL. "
        "`alpha` is `mean` minus `baseline`.",
        "",
        "`n indep` thins signals so no two forward windows overlap, and `t indep` is the "
        "t-stat on that independent sample -- the naive t over all overlapping signals runs "
        "2-3x higher and should be ignored.",
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

    lines += [
        "",
        "## Sub-period check (each ticker's scored range split in half)",
        "",
        "A cohort that only earns its alpha in one half of the sample is a period artefact.",
        "",
        HEADER, DIVIDER,
    ]
    for label, legs in results.items():
        for cohort, halves in legs.get("eras", {}).items():
            for era, s in halves.items():
                lines.append(_row(f"{label} ({era} half)", cohort, s))

    lines += [
        "",
        "## Per-year alpha by cohort",
        "",
        "One bad quarter can carry a pooled result that a half-and-half split still hides.",
        "",
        "| variant | cohort | " + " | ".join(str(y) for y in _all_years(results)) + " |",
        "|---|---|" + "---:|" * len(_all_years(results)),
    ]
    for label, legs in results.items():
        for cohort, years in legs.get("by_year", {}).items():
            cells = [f"{years[y]['alpha']:+.2%}" if y in years and years[y]["n"] else ""
                     for y in _all_years(results)]
            lines.append(f"| {label} | {cohort} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", type=int, default=165)
    parser.add_argument("--years", type=int, default=12)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--strategy", choices=list(TARGETS), default="trend-pullback")
    parser.add_argument("--variants", nargs="*", default=None)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    target = TARGETS[args.strategy]
    variants = args.variants or list(target.variants)
    unknown = [v for v in variants if v not in target.variants]
    if unknown:
        parser.error(f"unknown variants {unknown}; available: {list(target.variants)}")

    now = pd.Timestamp.now(tz="UTC")
    tickers = pick_tickers(args.tickers)
    bars = fetch_history(tickers, args.years, now)
    usable = {t: df for t, df in bars.items() if len(df) > target.min_bars + args.horizon}
    log.info("%d tickers fetched, %d with enough history", len(bars), len(usable))
    if not usable:
        log.error("no usable history")
        return 1

    results = measure(usable, variants, args.horizon, target)
    meta = {
        "tickers": len(usable),
        "years": args.years,
        "horizon": args.horizon,
        "bars": sum(len(df) for df in usable.values()),
        "generated": now.strftime("%Y-%m-%d"),
        "strategy": args.strategy,
        "base": unconditional(usable, args.horizon, target.min_bars),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{target.slug}.md").write_text(to_markdown(results, meta))
    (args.out / f"{target.slug}.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    print(to_markdown(results, meta))
    log.info("wrote %s", args.out / f"{target.slug}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
