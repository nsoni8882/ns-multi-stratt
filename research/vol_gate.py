"""Volatility gates on the RSI(2) rule. Bar: ACCEPTANCE.md, Rule 9. Needs scipy, arch, yfinance.

Run `python -m research.vol_gate`. Gates are decided at the signal bar's close.
"""
import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model

from research.allocation import CACHE, load_returns
from research.rsi2.rsi2_edge_backtest import backtest

START = "2015-01-01"


def garch_forecast(spy_ret):
    """Annualised 21-day-average GJR-GARCH vol per day, params refit each Jan 1 on prior data."""
    r = spy_ret * 100
    out = pd.Series(np.nan, index=r.index)
    for year in range(2015, r.index[-1].year + 1):
        fit = arch_model(r[r.index < f"{year}-01-01"], vol="GARCH", p=1, o=1, q=1, dist="t").fit(disp="off")
        m = arch_model(r, vol="GARCH", p=1, o=1, q=1, dist="t")
        start = int(np.searchsorted(r.index, pd.Timestamp(f"{year}-01-01")))
        end = int(np.searchsorted(r.index, pd.Timestamp(f"{year + 1}-01-01")))
        f = m.forecast(fit.params, horizon=21, start=start, reindex=False).variance.values
        out.iloc[start:end] = np.sqrt(f.mean(axis=1) * 252)[: end - start]
    return out


def load_closes(names):
    out = {}
    for n in names:
        d = pd.read_pickle(CACHE / f"{n}_12y.pkl")["close"]
        d.index = d.index.tz_localize(None) if d.index.tz else d.index
        out[n] = d
    return out


def trades_with_gates(closes, vix, garch):
    rows = []
    for name, c in closes.items():
        tr, _, _ = backtest(c)
        idx = c.index
        for _, t in tr.iterrows():
            i = idx.get_loc(t["entry"])
            sig = idx[i - 1]
            if sig < pd.Timestamp(START) or sig not in vix.index or np.isnan(garch.get(sig, np.nan)):
                continue
            v = float(vix[sig])
            v5 = float(vix.shift(5)[sig])
            rows.append({"name": name, "sig": sig, "ret": t["ret"],
                         "A_skip": v > 25, "B_skip": v / v5 - 1 > 0.20, "C_skip": garch[sig] > v})
    return pd.DataFrame(rows)


def cluster_t(d, skip):
    """kept minus skipped mean, errors clustered by calendar week of signal."""
    d = d.assign(week=d["sig"].dt.to_period("W"), s=skip.astype(int))
    y = d["ret"].values
    x = np.column_stack([np.ones(len(d)), d["s"].values])
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    e = y - x @ beta
    xtx_inv = np.linalg.inv(x.T @ x)
    meat = sum(np.outer(g, g) for g in (x[idx].T @ e[idx] for idx in d.groupby("week").indices.values()))
    se = np.sqrt((xtx_inv @ meat @ xtx_inv)[1, 1])
    return -beta[1], -beta[1] / se  # kept minus skipped


def report(label, d):
    print(f"\n== {label}: {len(d)} trades, ungated mean {d['ret'].mean()*1e4:+.0f} bps")
    for g in "ABC":
        s = d[f"{g}_skip"]
        k, sk = d[~s], d[s]
        if len(sk) < 5:
            print(f"{g}: skips {len(sk)} trades, too few"); continue
        diff, t = cluster_t(d, s)
        h = d["sig"].median()
        halves = [cluster_t(p, p[f"{g}_skip"])[0] * 1e4 if 3 < p[f"{g}_skip"].sum() < len(p) - 3 else np.nan
                  for p in (d[d["sig"] <= h], d[d["sig"] > h])]
        yr = {y: (p[~p[f'{g}_skip']].ret.mean() - p[p[f'{g}_skip']].ret.mean()) * 1e4 for y, p in d.groupby(d.sig.dt.year)
              if p[f"{g}_skip"].any() and (~p[f"{g}_skip"]).any()}
        best = max(yr, key=lambda y: yr[y] * ((p_n := d[d.sig.dt.year == y].shape[0])))  # biggest contributor
        ex = d[d.sig.dt.year != best]
        ex_diff = cluster_t(ex, ex[f"{g}_skip"])[0] * 1e4 if ex[f"{g}_skip"].any() else np.nan
        print(f"{g}: kept n={len(k)} {k.ret.mean()*1e4:+.0f}bps | skipped n={len(sk)} {sk.ret.mean()*1e4:+.0f}bps | "
              f"kept-skipped {diff*1e4:+.0f}bps t={t:+.2f} | halves {halves[0]:+.0f}/{halves[1]:+.0f} | "
              f"ex-{best} {ex_diff:+.0f}")


def main():
    spy = pd.read_pickle(CACHE / "SPY_12y.pkl")["close"]
    spy.index = spy.index.tz_localize(None) if spy.index.tz else spy.index
    spy_full = yf.download("SPY", start="2004-06-01", progress=False, auto_adjust=True)["Close"].squeeze()
    spy_full.index = spy_full.index.tz_localize(None) if spy_full.index.tz else spy_full.index
    vix = yf.download("^VIX", start="2014-01-01", progress=False)["Close"].squeeze()
    vix.index = vix.index.tz_localize(None) if vix.index.tz else vix.index
    garch = garch_forecast(spy_full.pct_change().dropna())
    pool = list(load_returns().columns)
    closes = load_closes(pool)
    report("pool", trades_with_gates(closes, vix, garch))
    report("AMZN+AAPL", trades_with_gates(load_closes(["AMZN", "AAPL"]), vix, garch))


if __name__ == "__main__":
    main()
