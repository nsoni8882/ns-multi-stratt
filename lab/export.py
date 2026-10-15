"""Writes lab.json, the single contract behind the Lab tab. Everything the page shows is
precomputed here, so the page is a renderer and needs no market logic of its own."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab import config
from lab.data import ET

TOP = ("meta", "account", "equity_curve", "summary", "strategies", "positions", "trades", "trials", "runs")
STRATEGY = ("id", "fingerprint", "name", "family", "stage", "hypothesis", "params", "risk",
            "failure_rules", "backtest", "live", "equity_curve", "history", "breakdowns")
BREAKDOWNS = ("by_symbol", "by_hour", "by_weekday", "daily_pnl", "exit_reasons", "histogram")


def _bps(x) -> float:
    return round(float(x) * 1e4, 2)


def _trade_rows(fp: str, f: pd.DataFrame) -> "list[dict]":
    return [{
        "strategy": fp, "symbol": r.symbol, "side": "long",
        "entry_time": r.entry_time.isoformat(), "exit_time": r.exit_time.isoformat(),
        "entry_px": round(float(r.entry_px), 4), "exit_px": round(float(r.exit_px), 4),
        "bars_held": int(r.bars_held), "exit_reason": r.exit_reason,
        "gross_bps": _bps(r.gross), "cost_bps": _bps(r.gross - r.net), "net_bps": _bps(r.net)}
        for r in f.itertuples()]


def _breakdowns(f: pd.DataFrame) -> dict:
    if f.empty:
        return {k: ({} if k == "exit_reasons" else []) for k in BREAKDOWNS}
    et = f["entry_time"].dt.tz_convert(ET)
    net = f["net"]

    def grouped(key):
        g = net.groupby(key).agg(["sum", "mean", "count"])
        return [{"key": str(k), "net_bps": _bps(r["mean"]), "total_pct": round(float(r["sum"]) * 100, 3),
                 "trades": int(r["count"])} for k, r in g.iterrows()]

    counts, edges = np.histogram(net.to_numpy() * 1e4, bins=20)
    return {
        "by_symbol": grouped(f["symbol"]), "by_hour": grouped(et.dt.hour),
        "by_weekday": grouped(et.dt.day_name()),
        "daily_pnl": [{"day": str(d), "net_bps": _bps(v)} for d, v in net.groupby(f["day"]).mean().items()],
        "exit_reasons": {k: int(v) for k, v in f["exit_reason"].value_counts().items()},
        "histogram": [{"from_bps": round(float(edges[i]), 2), "to_bps": round(float(edges[i + 1]), 2),
                       "count": int(counts[i])} for i in range(len(counts))],
    }


def build(registry: dict, ledger: "list[dict]", results: dict, *, generated_at: str,
          universe_version: str) -> dict:
    strategies, trades = [], []
    for fp, entry in registry.items():
        res = results.get(fp, {})
        f = res.get("trades", pd.DataFrame())
        curve = res.get("equity", pd.DataFrame(columns=["t", "equity", "drawdown"]))
        spec = entry["spec"]
        strategies.append({
            "id": fp, "fingerprint": fp, "name": spec["name"], "family": spec["family"],
            "stage": entry["stage"], "hypothesis": spec["hypothesis"], "params": spec["params"],
            "risk": spec["risk"], "failure_rules": entry.get("failure_rules"),
            "backtest": res.get("metrics", {}), "live": None,
            "equity_curve": [{"t": str(r.t), "equity": round(float(r.equity), 2),
                              "drawdown": round(float(r.drawdown), 5)} for r in curve.itertuples()],
            "history": entry.get("history", []), "breakdowns": _breakdowns(f),
        })
        if len(f):
            trades += _trade_rows(fp, f)
    live = [s for s in strategies if s["stage"] in ("shadow", "paper", "kept")]
    return {
        "meta": {"generated_at": generated_at, "universe_version": universe_version,
                 "rules_version": config.rules_version(), "trials_total": len(ledger),
                 "holdout_months": config.HOLDOUT_MONTHS, "cost_bps_per_side": config.COST_BPS_PER_SIDE},
        "account": None, "equity_curve": [], "positions": [], "runs": [],
        "summary": {"strategies": len(strategies), "live": len(live),
                    "rejected": sum(s["stage"] == "rejected" for s in strategies),
                    "retired": sum(s["stage"] == "retired" for s in strategies),
                    "trials": len(ledger), "passed": sum(r.get("verdict") == "pass" for r in ledger)},
        "strategies": strategies, "trades": trades, "trials": ledger,
    }


def validate(doc: dict) -> "list[str]":
    problems = [f"missing top-level key: {k}" for k in TOP if k not in doc]
    for s in doc.get("strategies", []):
        problems += [f"strategy {s.get('id', '?')} missing: {k}" for k in STRATEGY if k not in s]
        problems += [f"strategy {s.get('id', '?')} breakdowns missing: {k}"
                     for k in BREAKDOWNS if k not in s.get("breakdowns", {})]
    return problems


def write(path, doc: dict) -> None:
    problems = validate(doc)
    if problems:
        raise ValueError("; ".join(problems))
    Path(path).write_text(json.dumps(doc, separators=(",", ":")))
