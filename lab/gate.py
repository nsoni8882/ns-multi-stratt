"""The deterministic verdict. See lab/ACCEPTANCE.md for the bar and why. The only module
allowed to read the sealed holdout (`BacktestResult.after`); a test enforces it."""
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from lab import backtest, config, data, stats


class AlreadyTried(RuntimeError):
    pass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class GateResult:
    passed: bool
    checks: "list[Check]"
    metrics: dict
    fingerprint: str
    holdout_look: bool = False


def _bps(x) -> float:
    return float(x) * 1e4


def dev_checks(trades: pd.DataFrame, stress_mean: float, threshold: float):
    n = len(trades)
    daily = trades.groupby("day")["net"].mean() if n else pd.Series(dtype=float)
    nd = len(daily)
    mean = float(daily.mean()) if nd else 0.0
    t = stats.t_stat(daily.to_numpy())
    half = nd // 2
    h1 = float(daily.iloc[:half].mean()) if half else 0.0
    h2 = float(daily.iloc[half:].mean()) if nd - half else 0.0

    by_year = pd.Series(daily.to_numpy(), index=[d.year for d in daily.index]).groupby(level=0)
    years = by_year.agg(["mean", "sum", "count"]) if nd else pd.DataFrame(columns=["mean", "sum", "count"])
    if len(years) >= config.MIN_YEARS:
        best = years["sum"].idxmax()
        rest = daily[[d.year != best for d in daily.index]]
        no_single_year = bool(len(rest) and rest.mean() > 0)
        year_detail = f"without {best}: {_bps(rest.mean()):+.1f} bps"
    else:
        no_single_year, year_detail = False, f"{len(years)} year(s) of data, need {config.MIN_YEARS}"

    checks = [
        Check("min_trades", n >= config.MIN_TRADES, f"{n} trades, need {config.MIN_TRADES}"),
        Check("min_days", nd >= config.MIN_DAYS, f"{nd} days, need {config.MIN_DAYS}"),
        Check("positive_expectancy", mean > 0, f"{_bps(mean):+.1f} bps per day"),
        Check("deflated_t", t >= threshold, f"t={t:.2f}, needs {threshold:.2f}"),
        Check("both_halves", h1 > 0 and h2 > 0, f"{_bps(h1):+.1f} / {_bps(h2):+.1f} bps"),
        Check("drop_best_year", no_single_year, year_detail),
        Check("cost_stress", stress_mean > 0, f"{_bps(stress_mean):+.1f} bps at {config.STRESS_MULT}x costs"),
    ]
    wins = trades["net"][trades["net"] > 0].sum()
    losses = -trades["net"][trades["net"] < 0].sum()
    sd = float(daily.std(ddof=1)) if nd > 1 else 0.0
    metrics = {
        "n_trades": n, "n_days": nd, "mean_bps": _bps(mean), "t": t, "threshold": threshold,
        "win_rate": float((trades["net"] > 0).mean()) if n else 0.0,
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "sharpe": float(mean / sd * np.sqrt(252)) if sd > 0 else 0.0,
        "halves_bps": [_bps(h1), _bps(h2)],
        "years": {int(y): {"mean_bps": _bps(r["mean"]), "days": int(r["count"])}
                  for y, r in years.iterrows()},
    }
    return checks, metrics


def _holdout_check(hold: "backtest.BacktestResult", dev_mean_bps: float) -> Check:
    f = hold.frame()
    mean = _bps(hold.daily_mean().mean()) if len(f) else 0.0
    ok = len(f) >= config.MIN_HOLDOUT_TRADES and mean > 0 and mean >= config.HOLDOUT_MIN_RATIO * dev_mean_bps
    return Check("holdout", ok, "passed" if ok else "failed")  # never the numbers


def evaluate(spec, frames, tiers, allowed, ledger, *, cutoff=None) -> GateResult:
    fp = spec.fingerprint()
    if ledger.has(fp):
        raise AlreadyTried(f"{fp} was already evaluated; a nudged spec is a new fingerprint and a new trial")
    threshold = stats.deflated_threshold(ledger.count() + 1, config.BASE_T)
    cutoff = cutoff if cutoff is not None else data.dev_cutoff(frames)

    full = backtest.run(spec, frames, tiers, allowed=allowed)
    stress = backtest.run(spec, frames, tiers, allowed=allowed, cost_mult=config.STRESS_MULT).before(cutoff)
    stress_daily = stress.daily_mean()
    checks, metrics = dev_checks(full.before(cutoff).frame(),
                                 float(stress_daily.mean()) if len(stress_daily) else 0.0, threshold)

    looked = False
    if all(c.ok for c in checks):
        if ledger.holdout_looks() >= config.MAX_HOLDOUT_LOOKS:
            checks.append(Check("holdout", False, "holdout exhausted; roll the window forward"))
        else:
            looked = True
            checks.append(_holdout_check(full.after(cutoff), metrics["mean_bps"]))
    passed = all(c.ok for c in checks)
    ledger.append({
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fingerprint": fp,
        "name": spec.name, "family": spec.family, "timeframe": spec.timeframe,
        "params": spec.params, "risk": spec.canonical()["risk"], "hypothesis": spec.hypothesis,
        "verdict": "pass" if passed else "fail",
        "failed": [c.name for c in checks if not c.ok], "threshold": threshold,
        "rules_version": config.rules_version(), "holdout_look": looked,
        "n_trades": metrics["n_trades"], "mean_bps": metrics["mean_bps"], "t": metrics["t"],
    })
    return GateResult(passed, checks, metrics, fp, looked)
