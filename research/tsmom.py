"""Time series momentum on a wide ETF basket. Bar: ACCEPTANCE.md, Rule 10.

Ported from davidalmeida90/quant-models. Needs yfinance (first run downloads, then cached).
Run `python -m research.tsmom`.
"""
import numpy as np
import pandas as pd
import yfinance as yf

from research.allocation import CACHE

ETFS = [
    "SPY", "QQQ", "IWM", "DIA", "MDY", "EFA", "EEM", "EWJ", "EWG", "EWU", "EWZ", "EWY", "EWA", "EWC",
    "FXI", "EWH", "EWW", "TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "AGG", "BWX", "EMB", "GLD", "SLV",
    "USO", "UNG", "DBA", "DBB", "DBC", "DBO", "PPLT", "FXE", "FXY", "FXB", "FXA", "FXF", "FXC", "UUP",
    "IYR", "VNQ", "XLE",
]
COST, VOL_WIN, TARGET, CAP = 2e-4, 60, 0.10, 3.0
DECLARED = (252, 21)
LOOKBACKS = np.unique(np.round(np.logspace(np.log10(5), np.log10(300), 34)).astype(int))
HOLDINGS = np.unique(np.round(np.logspace(np.log10(1), np.log10(250), 36)).astype(int))


def prices():
    f = CACHE / "etf_basket.pkl"
    if f.exists():
        return pd.read_pickle(f)
    raw = yf.download(ETFS, start="2005-01-01", progress=False, auto_adjust=True)["Close"]
    px = raw.dropna(how="all").ffill(limit=3)
    px = px[[c for c in px if px[c].notna().sum() >= 3200]]
    px.to_pickle(f)
    return px


def roll_mean(a, w):
    c = np.cumsum(a, axis=0)
    out = np.zeros_like(a)
    out[w - 1:] = c[w - 1:]
    out[w:] -= c[:-w]
    return out / w


def sharpe(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(252) if x.std(ddof=1) > 0 else 0.0


def nw_alpha(y, x, lags=21):
    """Daily alpha of y on x with Newey-West t. Returns (annual alpha, t, beta)."""
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    xe = X * e[:, None]
    S = xe.T @ xe
    for k in range(1, lags + 1):
        G = xe[k:].T @ xe[:-k]
        S += (1 - k / (lags + 1)) * (G + G.T)
    inv = np.linalg.inv(X.T @ X)
    se = np.sqrt((inv @ S @ inv)[0, 0])
    return b[0] * 252, b[0] / se, b[1]


def main():
    px = prices()
    P = px.to_numpy(float)
    T, N = P.shape
    R = np.zeros_like(P)
    R[1:] = P[1:] / P[:-1] - 1
    R[~np.isfinite(R)] = 0
    live = np.isfinite(P)
    live[0] = False
    vol = np.sqrt(roll_mean(R ** 2, VOL_WIN) * 252)
    scale = np.clip(np.where(vol > 1e-6, TARGET / np.maximum(vol, 1e-6), 0), 0, CAP)
    hold = np.where(live, R, np.nan)
    bh = np.nan_to_num(np.nanmean(hold, axis=1))
    split = T // 2
    print(f"{N} ETFs, {px.index[0].date()} to {px.index[-1].date()}")

    def run(L, H):
        sig = np.zeros_like(P)
        sig[L:] = np.sign(P[L:] / P[:-L] - 1)
        sig[~live] = 0
        pos = roll_mean(sig, int(H)) * scale
        pnl = np.zeros_like(P)
        pnl[1:] = pos[:-1] * R[1:]
        turn = np.zeros_like(P)
        turn[1:] = np.abs(pos[1:] - pos[:-1])
        pnl -= COST * turn
        pnl[~live] = np.nan
        return np.nan_to_num(np.nanmean(pnl, axis=1))

    # sweep: sharpe in each half for every cell
    isr, oos = np.zeros((len(LOOKBACKS), len(HOLDINGS))), np.zeros((len(LOOKBACKS), len(HOLDINGS)))
    for a, L in enumerate(LOOKBACKS):
        for b, H in enumerate(HOLDINGS):
            p = run(L, H)
            isr[a, b], oos[a, b] = sharpe(p[:split]), sharpe(p[split:])
    ia, ib = np.unravel_index(isr.argmax(), isr.shape)
    print(f"sweep: {isr.size} cells | IS-best L={LOOKBACKS[ia]} H={HOLDINGS[ib]} IS {isr[ia, ib]:.2f} -> "
          f"OOS {oos[ia, ib]:.2f} | median OOS {np.median(oos):.2f} | share of cells OOS>0 {(oos > 0).mean():.0%}")

    p = run(*DECLARED)
    idx = px.index
    a, t, beta = nw_alpha(p, bh)
    print(f"\ndeclared L={DECLARED[0]} H={DECLARED[1]}: Sharpe {sharpe(p):.2f} (buy-hold {sharpe(bh):.2f}), "
          f"ann ret {p.mean()*252:.1%} vs {bh.mean()*252:.1%}, beta {beta:.2f}, alpha {a:.1%}/yr t={t:.2f}")
    for name, sl in (("first half", slice(0, split)), ("second half", slice(split, T))):
        a2, t2, _ = nw_alpha(p[sl], bh[sl])
        print(f"  {name}: Sharpe {sharpe(p[sl]):.2f}, alpha {a2:.1%}/yr t={t2:.2f}")
    yrs = idx.year.to_numpy()
    ya = {y: nw_alpha(p[yrs == y], bh[yrs == y])[0] * (yrs == y).sum() / 252 for y in np.unique(yrs) if (yrs == y).sum() > 100}
    best = max(ya, key=ya.get)
    m = yrs != best
    a3, t3, _ = nw_alpha(p[m], bh[m])
    print(f"  without {best} (best year, {ya[best]:+.1%}): alpha {a3:.1%}/yr t={t3:.2f}")
    print("  alpha by year:", {int(y): f"{v:+.1%}" for y, v in ya.items()})


if __name__ == "__main__":
    main()
