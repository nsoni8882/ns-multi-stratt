"""Allocation methods vs equal weight, on the cached S&P universe. Bar: ACCEPTANCE.md, Rule 8.

Ported from davidalmeida90/quant-models (HRP, HCAA, IVP, min-variance). Run with an
environment that has scipy: `python -m research.allocation`. Needs `research/.cache` filled.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.optimize import minimize
from scipy.spatial.distance import squareform

CACHE = Path(__file__).parent / ".cache"
LOOKBACK, BPS, MAX_NAMES = 252, 10, 100


def ivp(cov):
    w = 1 / np.diag(cov.values)
    return pd.Series(w / w.sum(), index=cov.index)


def _cluster_var(cov, items):
    c = cov.loc[items, items]
    w = ivp(c).values
    return float(w @ c.values @ w)


def hrp(cov, corr):
    link = sch.linkage(squareform(((1 - corr) / 2) ** 0.5, checks=False), "single")
    order = [corr.index[i] for i in sch.leaves_list(link)]
    w = pd.Series(1.0, index=order)
    groups = [order]
    while groups:
        groups = [g[j:k] for g in groups for j, k in ((0, len(g) // 2), (len(g) // 2, len(g))) if len(g) > 1]
        for i in range(0, len(groups), 2):
            a, b = _cluster_var(cov, groups[i]), _cluster_var(cov, groups[i + 1])
            w[groups[i]] *= 1 - a / (a + b)
            w[groups[i + 1]] *= a / (a + b)
    return w.reindex(cov.index)


def hcaa(corr):
    link = sch.linkage(squareform(np.sqrt(2 * (1 - corr)), checks=False), "average")
    w = pd.Series(0.0, index=corr.index)

    def rec(node, wt):
        if node.is_leaf():
            w.iloc[node.id] = wt
        else:
            rec(node.left, wt / 2)
            rec(node.right, wt / 2)

    rec(sch.to_tree(link), 1.0)
    return w


def minvar(cov):
    s = cov.values * 252
    n = len(s)
    r = minimize(lambda w: w @ s @ w, np.ones(n) / n, method="SLSQP", bounds=[(0, 1)] * n,
                 constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    return pd.Series(r.x, index=cov.index)


METHODS = {
    "EW": lambda win: pd.Series(1 / win.shape[1], index=win.columns),
    "IVP": lambda win: ivp(win.cov()),
    "HRP": lambda win: hrp(win.cov(), win.corr()),
    "HCAA": lambda win: hcaa(win.corr()),
    "MinVar": lambda win: minvar(win.cov()),
}


def load_returns():
    closes = {}
    for p in CACHE.glob("*_12y.pkl"):
        d = pd.read_pickle(p)
        if len(d) >= 2900 and "close" in d:
            closes[p.name.split("_")[0]] = d["close"]
    px = pd.DataFrame(closes).sort_index().dropna()
    px.index = px.index.tz_localize(None) if px.index.tz else px.index
    rets = px.pct_change().dropna()
    # SDS (inverse S&P ETF), ECH, MMI are funds, not stocks; stale names trade at zero return.
    # Both poisoned the first run: min-variance simply held the inverse ETF.
    rets = rets.drop(columns=[c for c in ("SDS", "ECH", "MMI") if c in rets])
    rets = rets.loc[:, (rets == 0).mean() < 0.01]
    return rets.iloc[:, :MAX_NAMES]


def backtest(rets, fn):
    month_end = set(rets.groupby(rets.index.to_period("M")).tail(1).index)
    w_prev = pd.Series(0.0, index=rets.columns)
    cur, out, turn = None, {}, {}
    for t in rets.index:
        if cur is not None:
            out[t] = float((cur * rets.loc[t]).sum())
        if t in month_end and len(rets.loc[:t]) >= LOOKBACK:
            cur = fn(rets.loc[:t].tail(LOOKBACK)).reindex(rets.columns).fillna(0)
            turn[t] = float((cur - w_prev).abs().sum())
            w_prev = cur
    gross = pd.Series(out)
    net = gross.copy()
    for d, tv in turn.items():
        if d in net.index:
            net[d] -= BPS / 1e4 * tv
    return gross, net, pd.Series(turn)


def monthly(s):
    return (1 + s).groupby(s.index.to_period("M")).prod() - 1


def dd(s):
    c = (1 + s).cumprod()
    return float((c / c.cummax() - 1).min())


def main():
    rets = load_returns()
    print(f"{rets.shape[1]} names, {rets.index[0].date()} to {rets.index[-1].date()}")
    res = {k: backtest(rets, f) for k, f in METHODS.items()}
    ew_m = monthly(res["EW"][1])
    half = len(ew_m) // 2
    rows = []
    for k, (g, n, tv) in res.items():
        m = monthly(n)
        d = (m - ew_m).dropna()
        yr = d.groupby(d.index.year).sum()
        t = d.mean() / (d.std() / np.sqrt(len(d))) if k != "EW" else float("nan")
        beta = float(np.cov(m, ew_m)[0, 1] / ew_m.var())
        rows.append({
            "method": k,
            "sharpe": n.mean() / n.std() * np.sqrt(252),
            "ann_ret%": n.mean() * 252 * 100,
            "maxDD%": dd(n) * 100,
            "beta_EW": beta,
            "diff_t": t,
            "diff_h1%": d.iloc[:half].mean() * 1200 if k != "EW" else np.nan,
            "diff_h2%": d.iloc[half:].mean() * 1200 if k != "EW" else np.nan,
            "diff_ex_best_yr%": (d.sum() - yr.max()) / (len(d) / 12) * 100 if k != "EW" else np.nan,
            "turn/mo": tv.mean(),
            "cost_drag%/yr": (g.mean() - n.mean()) * 252 * 100,
        })
    print(pd.DataFrame(rows).set_index("method").round(2).to_string())


if __name__ == "__main__":
    sys.exit(main())
