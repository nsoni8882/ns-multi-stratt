import json

from lab import backtest, config, review
from lab.spec import Spec
from lab.tests.conftest import random_walk, sessions
from lab.trials import Ledger

SPEC = Spec.from_dict({"name": "gap", "family": "gap_fade", "timeframe": "5Min",
                       "params": {"gap_pct": 0.002, "entry_bar": 1},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "gap downs mean-revert"})


def seed(tmp_path):
    fp = SPEC.fingerprint()
    res = backtest.run(SPEC, {"A": sessions(random_walk(n_days=40))}, {"A": "large"})
    (tmp_path / "registry.json").write_text(json.dumps({fp: {
        "spec": SPEC.to_dict(), "stage": "rejected", "failure_rules": None, "approved_by": None,
        "history": [{"stage": "proposed", "when": "2026-10-15T00:00:00Z", "reason": "r"},
                    {"stage": "rejected", "when": "2026-10-15T00:01:00Z", "reason": "r"}]}}))
    Ledger(tmp_path / "trials.jsonl").append({
        "fingerprint": fp, "verdict": "fail", "failed": ["deflated_t"], "n_trades": len(res.trades),
        "mean_bps": -3.2, "t": -1.1, "threshold": 2.5, "holdout_look": False})
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / f"{fp}.json").write_text(json.dumps({
        "metrics": {}, "trades": json.loads(res.frame().to_json(orient="split", date_format="iso")),
        "equity": {}}))
    return fp


def test_report_states_the_bar_for_the_next_idea_and_each_verdict(tmp_path):
    fp = seed(tmp_path)
    out = review.report(tmp_path)
    assert "ideas tried: 1" in out and "t >= 2.50" in out
    assert f"[REJECTED] gap  ({fp}" in out and "failed: deflated_t" in out
    assert "hypothesis: gap downs mean-revert" in out


def test_diagnostics_say_where_the_money_went(tmp_path):
    seed(tmp_path)
    out = review.report(tmp_path)
    assert "per trade: gross" in out and "exits:" in out and "by hour (ET):" in out
    assert "worst symbols:" in out


def test_an_empty_lab_reports_itself(tmp_path):
    out = review.report(tmp_path)
    assert "ideas tried: 0" in out and "No strategies registered yet." in out


def test_the_report_never_prints_a_holdout_figure(tmp_path):
    seed(tmp_path)
    assert "holdout looks: 0 of" in review.report(tmp_path)
    assert config.HOLDOUT_START in review.report(tmp_path)  # the window is named, never its numbers
