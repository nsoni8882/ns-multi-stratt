#!/usr/bin/env python3
"""
RSI(2) oversold-in-uptrend mean reversion — reproducible edge test.

RULE (long only, daily bars, no parameters fitted per asset):
  ENTRY  : Wilder RSI(2) < 10  AND  Close > SMA(200)        -> buy at that day's close (MOC)
  EXIT   : RSI(2) > 65  OR  10 bars elapsed                 -> sell at that day's close
  COST   : 5 bps per round trip (configurable)

Usage:  pip install yfinance pandas numpy
        python rsi2_edge_backtest.py SPY QQQ IWM EEM MSFT GBPUSD=X
"""
import sys
import numpy as np
import pandas as pd
import yfinance as yf

START, END, COST_BPS, MAX_HOLD = "2000-01-01", None, 5.0, 10


def wilder_rsi(close, n):
    d = close.diff()
    au = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    ad = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad.replace(0, np.nan))


def backtest(close, cost_bps=COST_BPS, max_hold=MAX_HOLD):
    rsi2 = wilder_rsi(close, 2)
    entry = ((rsi2 < 10) & (close > close.rolling(200).mean())).fillna(False).values
    exit_ = (rsi2 > 65).fillna(False).values
    ret = close.pct_change().values

    trades, pos = [], np.zeros(len(close))
    in_pos, hold, tret, start = False, 0, 0.0, 0
    for i in range(1, len(close)):
        if in_pos:
            tret += ret[i]; pos[i] = 1; hold += 1
            if exit_[i] or hold >= max_hold:
                in_pos = False
                trades.append((close.index[start], close.index[i], hold, tret - cost_bps / 1e4))
        if not in_pos and entry[i - 1] and not np.isnan(ret[i]):
            in_pos, hold, tret, start = True, 1, ret[i], i
            pos[i] = 1
            if exit_[i] or hold >= max_hold:
                in_pos = False
                trades.append((close.index[start], close.index[i], hold, tret - cost_bps / 1e4))

    tr = pd.DataFrame(trades, columns=["entry", "exit", "bars", "ret"])
    daily = pd.Series(pos * np.nan_to_num(ret), index=close.index)
    daily[np.diff(np.r_[0, pos]) == 1] -= cost_bps / 1e4
    return tr, daily, pd.Series(pos, index=close.index)


def randomization_p(close, n_trades, bars, observed_bps, n_sim=2000, seed=7):
    """Null: same number of trades, same holding length, random entry days."""
    r = close.pct_change().dropna().values
    rng = np.random.default_rng(seed)
    sims = [np.mean([r[i:i + bars].sum() for i in rng.integers(0, len(r) - bars, n_trades)]) * 1e4
            for _ in range(n_sim)]
    return float(np.mean(np.array(sims) >= observed_bps)), float(np.mean(sims))


def report(ticker):
    df = yf.download(ticker, start=START, end=END, auto_adjust=True, progress=False)
    if df.empty:
        return None
    close = (df["Close"] if not isinstance(df.columns, pd.MultiIndex) else df["Close"].iloc[:, 0]).dropna()
    tr, daily, pos = backtest(close)
    if len(tr) < 10:
        return None
    bars = int(round(tr.bars.mean())) or 1
    p, rand = randomization_p(close, len(tr), bars, tr.ret.mean() * 1e4)
    eq = (1 + daily.fillna(0)).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    uncond = close.pct_change().mean() * 1e4
    return dict(
        asset=ticker, trades=len(tr), time_in_mkt=pos.mean(),
        avg_trade_bps=tr.ret.mean() * 1e4, win_rate=(tr.ret > 0).mean(),
        avg_bars=tr.bars.mean(),
        bps_per_day_in_pos=tr.ret.mean() / tr.bars.mean() * 1e4,
        uncond_bps_per_day=uncond, random_entry_bps=rand, p_vs_random=p,
        t_stat=tr.ret.mean() / tr.ret.std() * np.sqrt(len(tr)),
        cagr=eq.iloc[-1] ** (1 / yrs) - 1, max_dd=(eq / eq.cummax() - 1).min(),
        sharpe=daily.fillna(0).mean() / daily.fillna(0).std() * np.sqrt(252),
    )


if __name__ == "__main__":
    tickers = sys.argv[1:] or ["SPY", "QQQ", "IWM", "EEM", "MSFT", "GLD", "GBPUSD=X", "EURUSD=X"]
    rows = [r for r in (report(t) for t in tickers) if r]
    out = pd.DataFrame(rows).set_index("asset")
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
    print(out.round(3).to_string())
    print("\nEdge test: avg_trade_bps must beat random_entry_bps (same holding period) with p_vs_random < 0.05.")
