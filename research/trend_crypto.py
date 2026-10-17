"""Daily trend on major crypto: hold while close > SMA(50), else cash. Crypto trades every day and
is less efficient than US large caps, which is the whole reason to look: every large-cap rule here
came back as drift.

Declared 2026-10-17 before any number existed.

One rule, no variants: long on day t if the close of t-1 was above its SMA(50), else cash. Cost 25 bps
per switch (a fee plus spread allowance, roughly the top of the 10 to 25 bps a side that retail
venues charge). Universe, fixed now: BTC ETH XRP LTC BCH ADA XLM TRX, which were all top-ten names
in early 2018 and still trade. Sample 2018-01 onward, 365-day year.

Survivorship is worse here than anywhere: names that died (EOS, IOTA, NEO and the rest of that
cohort) are absent, so buy-and-hold of this basket is flattered and so is any rule's long leg.
That biases toward buy-and-hold, so a trend rule that wins is not helped by it; a trend rule that
merely ties is a real loss to a survivor-free benchmark.

Bar, on the equal-weight trend basket against the equal-weight buy-and-hold basket, all must hold:
  1. beta-adjusted alpha positive with Newey-West t >= 2.5 (crypto is where an alpha claim is made)
  2. Sharpe at least that of buy-and-hold
  3. max drawdown at least 30% smaller
  4. alpha positive in both halves
  5. alpha positive with the best calendar year removed
Also reported: BTC alone, and the same basket at double the cost.
"""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from research.measure import RESULTS_DIR
from research.trend_etf import alpha_beta, max_dd

log = logging.getLogger("trend_crypto")
UNIVERSE = ["BTC-USD", "ETH-USD", "XRP-USD", "LTC-USD", "BCH-USD", "ADA-USD", "XLM-USD", "TRX-USD"]
SMA, COST, PERIODS, START = 50, 0.0025, 365, "2018-01-01"


def trend_returns(close: pd.Series, cost: float = COST) -> pd.Series:
    ret = close.pct_change()
    avg = close.rolling(SMA).mean()
    on = (close > avg).shift(1, fill_value=False).astype(bool)
    switches = on.astype(int).diff().abs().fillna(0)
    return (ret * on - switches * cost).where(avg.shift(1).notna())


def sharpe(r: pd.Series) -> float:
    return float(r.mean() / r.std() * np.sqrt(PERIODS))


def block(s: pd.Series, b: pd.Series) -> dict:
    a, beta, t = alpha_beta(s, b, lags=10)
    return {"sharpe": sharpe(s), "bench_sharpe": sharpe(b), "max_dd": max_dd(s), "bench_max_dd": max_dd(b),
            "alpha_ann": a * PERIODS, "beta": beta, "t_alpha": t,
            "ann_return": float(s.mean() * PERIODS), "bench_ann_return": float(b.mean() * PERIODS)}


def evaluate(close: pd.DataFrame, cost: float = COST) -> dict:
    rets = close.pct_change()
    trend = pd.DataFrame({t: trend_returns(close[t], cost) for t in close.columns})
    ok = trend.notna().all(axis=1) & rets.notna().all(axis=1)
    strat, bench = trend[ok].mean(axis=1), rets[ok].mean(axis=1)
    mid = strat.index[len(strat) // 2]
    by_year = {int(y): alpha_beta(strat[strat.index.year == y], bench[bench.index.year == y])[0] * PERIODS
               for y in sorted(set(strat.index.year))}
    best = max(by_year, key=by_year.get)
    keep = strat.index.year != best
    return {"all": block(strat, bench), "first_half": block(strat[:mid], bench[:mid]),
            "second_half": block(strat[mid:], bench[mid:]), "best_year": best,
            "without_best_year": block(strat[keep], bench[keep]), "by_year": by_year,
            "span": [str(strat.index[0].date()), str(strat.index[-1].date())]}


def fmt(b: dict) -> str:
    return (f"Sharpe {b['sharpe']:.2f} vs {b['bench_sharpe']:.2f}, max DD {b['max_dd']:.1%} vs {b['bench_max_dd']:.1%}, "
            f"return {b['ann_return']:.1%} vs {b['bench_ann_return']:.1%}, beta {b['beta']:.2f}, "
            f"alpha {b['alpha_ann']:+.1%}/yr (t {b['t_alpha']:+.2f})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "trend-crypto")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raw = yf.download(UNIVERSE, start=START, auto_adjust=True, progress=False)["Close"].dropna()
    log.info("%d days, %s to %s, %d coins", len(raw), raw.index[0].date(), raw.index[-1].date(), raw.shape[1])
    ev, ev2, btc = evaluate(raw), evaluate(raw, COST * 2), evaluate(raw[["BTC-USD"]])
    lines = ["# Daily trend (close > SMA 50) on 8 major crypto", "",
             f"{ev['span'][0]} to {ev['span'][1]}, equal weight, 25 bps a switch.", ""]
    for k in ("all", "first_half", "second_half", "without_best_year"):
        lines.append(f"- {k}{' (' + str(ev['best_year']) + ' removed)' if k == 'without_best_year' else ''}: {fmt(ev[k])}")
    lines += [f"- double cost: {fmt(ev2['all'])}", f"- BTC alone: {fmt(btc['all'])}", "",
              "| year | " + " | ".join(map(str, ev["by_year"])) + " |", "|---|" + "---:|" * len(ev["by_year"]),
              "| alpha/yr | " + " | ".join(f"{v:+.0%}" for v in ev["by_year"].values()) + " |"]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "trend_crypto.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
