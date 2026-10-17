"""Time-series trend on asset-class ETFs: hold while the close is above its 200-day average, else
cash. The best-documented trend effect, and the only candidate left that is a risk premium rather
than a price pattern in large caps.

Declared 2026-10-17 before any number existed.

One rule, no variants: long when close > SMA(200) at yesterday's close, else cash (0%). Cost 5 bps
per switch (a round trip is two). Universe, fixed now: SPY QQQ IWM EFA EEM TLT GLD DBC. Compared
with buying and holding the same equal-weight basket, 2007-2026 (the span DBC and EEM share).

What this can and cannot be. It is not expected to beat buy-and-hold on return; the claim in the
literature is a similar return for a much smaller drawdown. So the bar is risk-adjusted, and all
must hold for the equal-weight trend basket against the equal-weight buy-and-hold basket:
  1. Sharpe ratio at least as high as buy-and-hold
  2. max drawdown at least 30% smaller (in absolute terms)
  3. beta-adjusted alpha positive in both halves of the sample
  4. the same holds with 2008 removed (the drawdown that pays for the whole idea)
Rule 4 is the one most likely to fail: a trend rule can look good on one crash.
Passing this would mean a useful overlay, not an alpha source, and it is reported as that.
"""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from research.measure import RESULTS_DIR

log = logging.getLogger("trend_etf")
UNIVERSE = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "DBC"]
SWITCH_COST = 0.0005
START = "2006-01-01"


def trend_returns(close: pd.Series) -> pd.Series:
    """Daily return of the rule: invested on day t if the close of t-1 was above its SMA(200)."""
    ret = close.pct_change()
    on = (close > close.rolling(200).mean()).shift(1, fill_value=False).astype(bool)
    switches = on.astype(int).diff().abs().fillna(0)
    return (ret * on - switches * SWITCH_COST).where(close.rolling(200).mean().shift(1).notna())


def sharpe(r: pd.Series) -> float:
    return float(r.mean() / r.std() * np.sqrt(252))


def max_dd(r: pd.Series) -> float:
    eq = (1 + r.fillna(0)).cumprod()
    return float((eq / eq.cummax() - 1).min())


def alpha_beta(strat: pd.Series, bench: pd.Series, lags: int = 10) -> "tuple[float, float, float]":
    """OLS of strategy on benchmark with Newey-West errors: daily alpha, beta, t of alpha."""
    d = pd.concat([strat, bench], axis=1).dropna()
    y, x = d.iloc[:, 0].to_numpy(), d.iloc[:, 1].to_numpy()
    X = np.c_[np.ones(len(x)), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = X * (y - X @ b)[:, None]
    S = u.T @ u / len(y)
    for k in range(1, lags + 1):
        G = u[k:].T @ u[:-k] / len(y)
        S += (1 - k / (lags + 1)) * (G + G.T)
    inv = np.linalg.inv(X.T @ X / len(y))
    cov = inv @ S @ inv / len(y)
    return float(b[0]), float(b[1]), float(b[0] / np.sqrt(cov[0, 0]))


def evaluate(close: pd.DataFrame) -> dict:
    rets = close.pct_change()
    trend = pd.DataFrame({t: trend_returns(close[t]) for t in close.columns})
    ok = trend.notna().all(axis=1) & rets.notna().all(axis=1)
    strat, bench = trend[ok].mean(axis=1), rets[ok].mean(axis=1)
    mid = strat.index[len(strat) // 2]

    def block(s, b):
        a, beta, t = alpha_beta(s, b)
        return {"sharpe": sharpe(s), "bench_sharpe": sharpe(b), "max_dd": max_dd(s), "bench_max_dd": max_dd(b),
                "alpha_ann": a * 252, "beta": beta, "t_alpha": t, "ann_return": float(s.mean() * 252),
                "bench_ann_return": float(b.mean() * 252)}
    no2008 = ~strat.index.year.isin([2008])
    return {"all": block(strat, bench), "first_half": block(strat[:mid], bench[:mid]),
            "second_half": block(strat[mid:], bench[mid:]), "without_2008": block(strat[no2008], bench[no2008]),
            "span": [str(strat.index[0].date()), str(strat.index[-1].date())],
            "per_asset": {t: {"sharpe": sharpe(trend[t][ok]), "bench_sharpe": sharpe(rets[t][ok]),
                              "max_dd": max_dd(trend[t][ok]), "bench_max_dd": max_dd(rets[t][ok])} for t in close.columns}}


def fmt(b: dict) -> str:
    return (f"Sharpe {b['sharpe']:.2f} vs {b['bench_sharpe']:.2f}, max DD {b['max_dd']:.1%} vs {b['bench_max_dd']:.1%}, "
            f"return {b['ann_return']:.1%} vs {b['bench_ann_return']:.1%}, beta {b['beta']:.2f}, "
            f"alpha {b['alpha_ann']:+.1%}/yr (t {b['t_alpha']:+.2f})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "trend-etf")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raw = yf.download(UNIVERSE, start=START, auto_adjust=True, progress=False)["Close"].dropna()
    log.info("%d days, %s to %s, %d ETFs", len(raw), raw.index[0].date(), raw.index[-1].date(), raw.shape[1])
    ev = evaluate(raw)
    lines = ["# Time-series trend (close > SMA 200) on 8 asset-class ETFs", "",
             f"{ev['span'][0]} to {ev['span'][1]}, equal-weight basket, 5 bps per switch.", ""]
    for k in ("all", "first_half", "second_half", "without_2008"):
        lines.append(f"- {k}: {fmt(ev[k])}")
    lines += ["", "| ETF | trend Sharpe | hold Sharpe | trend max DD | hold max DD |", "|---|---:|---:|---:|---:|"]
    for t, v in ev["per_asset"].items():
        lines.append(f"| {t} | {v['sharpe']:.2f} | {v['bench_sharpe']:.2f} | {v['max_dd']:.1%} | {v['bench_max_dd']:.1%} |")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "trend_etf.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
