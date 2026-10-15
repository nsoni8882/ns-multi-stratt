"""Event-driven backtest. A signal at bar i fills at the open of bar i+1. Inside a bar the
order of events is unknowable from OHLC, so the pessimistic order is used: a gap through the
stop fills at the open, and a bar that touches both stop and target is a stop. Trades are
flat by the session close, so a trade never spans a day."""
from dataclasses import dataclass

import pandas as pd

from lab import config, costs
from lab.data import ET
from lab.families import REGISTRY


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_px: float
    exit_px: float
    bars_held: int
    exit_reason: str
    gross: float
    net: float


def simulate_symbol(df, sig, risk, tier, symbol, cost_mult=1.0) -> "list[Trade]":
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    days, idx, flag = df["day"].to_numpy(), df.index, sig.to_numpy(bool)
    n, trades, i = len(df), [], 0
    while i < n - 1:
        if not flag[i] or days[i + 1] != days[i]:
            i += 1
            continue
        e = i + 1
        entry = o[e]
        stop, target = entry * (1 - risk.stop_pct), entry * (1 + risk.target_pct)
        j, reason, px = e, None, 0.0
        while reason is None:
            if o[j] <= stop:
                reason, px = "stop", o[j]
            elif l[j] <= stop:
                reason, px = "stop", stop
            elif o[j] >= target:
                reason, px = "target", o[j]
            elif h[j] >= target:
                reason, px = "target", target
            elif j - e + 1 >= risk.max_hold_bars:
                reason, px = "time", c[j]
            elif j + 1 >= n or days[j + 1] != days[j]:
                reason, px = "session", c[j]
            else:
                j += 1
        trades.append(Trade(symbol, idx[e], idx[j], float(entry), float(px), j - e + 1, reason,
                            float(px / entry - 1), float(costs.net_return(entry, px, tier, cost_mult))))
        i = j + 1
    return trades


@dataclass
class BacktestResult:
    trades: "list[Trade]"
    size_pct: float

    def frame(self) -> pd.DataFrame:
        cols = ["symbol", "entry_time", "exit_time", "entry_px", "exit_px", "bars_held",
                "exit_reason", "gross", "net"]
        df = pd.DataFrame([[getattr(t, k) for k in cols] for t in self.trades], columns=cols)
        df["day"] = [t.tz_convert(ET).date() for t in df["entry_time"]]
        return df

    def daily_mean(self) -> pd.Series:
        f = self.frame()
        return f.groupby("day")["net"].mean() if len(f) else pd.Series(dtype=float)

    def equity_curve(self) -> pd.DataFrame:
        f = self.frame()
        if f.empty:
            return pd.DataFrame(columns=["t", "equity", "drawdown"])
        ret = (f["net"] * self.size_pct).groupby(f["day"]).sum()
        equity = config.START_EQUITY * (1 + ret).cumprod()
        peak = equity.cummax()
        return pd.DataFrame({"t": list(ret.index), "equity": equity.to_numpy(),
                             "drawdown": (equity / peak - 1).to_numpy()})

    def before(self, ts) -> "BacktestResult":
        return BacktestResult([t for t in self.trades if t.entry_time < ts], self.size_pct)

    def after(self, ts) -> "BacktestResult":
        return BacktestResult([t for t in self.trades if t.entry_time >= ts], self.size_pct)


def run(spec, frames, tiers, *, cost_mult=1.0, allowed=None) -> BacktestResult:
    family = REGISTRY[spec.family]
    every = []
    for symbol, df in frames.items():
        sig = family.signal(df, spec.params)
        if allowed is not None:
            years = allowed.get(symbol, set())
            sig = sig & df["day"].map(lambda d: d.year in years)
        every += simulate_symbol(df, sig, spec.risk, tiers.get(symbol, "large"), symbol, cost_mult)
    kept, open_exits = [], []
    for t in sorted(every, key=lambda t: (t.entry_time, t.symbol)):
        open_exits = [x for x in open_exits if x > t.entry_time]
        if len(open_exits) < spec.risk.max_concurrent:
            kept.append(t)
            open_exits.append(t.exit_time)
    return BacktestResult(kept, spec.risk.size_pct)
