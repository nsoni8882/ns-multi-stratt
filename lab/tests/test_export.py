import json

import pandas as pd

from lab import backtest, export
from lab.spec import Spec
from lab.tests.conftest import random_walk, sessions

SPEC = Spec.from_dict({"name": "gap", "family": "gap_fade", "timeframe": "5Min",
                       "params": {"gap_pct": 0.002, "entry_bar": 1},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "gap downs mean-revert"})


def doc():
    res = backtest.run(SPEC, {"A": sessions(random_walk(n_days=40))}, {"A": "large"})
    fp = SPEC.fingerprint()
    registry = {fp: {"spec": SPEC.to_dict(), "stage": "backtested", "failure_rules": None,
                     "approved_by": None,
                     "history": [{"stage": "backtested", "when": "2026-10-15T00:00:00Z", "reason": "ran"}]}}
    ledger = [{"fingerprint": fp, "verdict": "fail", "failed": ["min_trades"],
               "when": "2026-10-15T00:00:00Z", "name": "gap", "family": "gap_fade"}]
    results = {fp: {"metrics": {"n_trades": len(res.trades), "mean_bps": 1.0}, "trades": res.frame(),
                    "equity": res.equity_curve()}}
    return export.build(registry, ledger, results, generated_at="2026-10-15T00:00:00Z", universe_version="abc")


def test_a_built_document_is_valid_and_json_serialisable():
    d = doc()
    assert export.validate(d) == []
    json.dumps(d)  # no timestamps, dates or numpy scalars left over


def test_trades_carry_costs_and_every_breakdown_the_tab_needs():
    d = doc()
    t = d["trades"][0]
    assert {"strategy", "symbol", "side", "entry_time", "exit_time", "entry_px", "exit_px",
            "bars_held", "exit_reason", "gross_bps", "cost_bps", "net_bps"} <= set(t)
    b = d["strategies"][0]["breakdowns"]
    assert {"by_symbol", "by_hour", "by_weekday", "daily_pnl", "exit_reasons", "histogram"} <= set(b)


def test_validate_names_what_is_missing():
    d = doc()
    del d["strategies"][0]["stage"]
    d.pop("trials")
    problems = export.validate(d)
    assert any("trials" in p for p in problems) and any("stage" in p for p in problems)


def test_a_strategy_with_no_trades_still_exports():
    fp = SPEC.fingerprint()
    cols = ["symbol", "entry_time", "exit_time", "entry_px", "exit_px", "bars_held", "exit_reason",
            "gross", "net", "day"]
    empty = export.build(
        {fp: {"spec": SPEC.to_dict(), "stage": "rejected", "failure_rules": None, "approved_by": None, "history": []}},
        [], {fp: {"metrics": {}, "trades": pd.DataFrame(columns=cols),
                  "equity": pd.DataFrame(columns=["t", "equity", "drawdown"])}},
        generated_at="x", universe_version="y")
    assert export.validate(empty) == [] and empty["trades"] == []
