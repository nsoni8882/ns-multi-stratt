import numpy as np
import pandas as pd
import pytest

from lab import config, gate
from lab.spec import Spec
from lab.tests.conftest import random_walk, sessions
from lab.trials import Ledger


def trades_from_daily(net_by_day, per_day=3):
    rows = [(d, v) for d, v in net_by_day for _ in range(per_day)]
    return pd.DataFrame(rows, columns=["day", "net"])


def series(seed, mean, years=3, sd=0.004):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-01-04", periods=250 * years).date
    return list(zip(days, rng.normal(mean, sd, len(days))))


def verdict(checks):
    return {c.name: c.ok for c in checks}


def test_a_planted_edge_passes_every_development_check():
    checks, m = gate.dev_checks(trades_from_daily(series(1, 0.002)), 0.001, 2.5)
    assert all(c.ok for c in checks), verdict(checks)
    assert m["n_trades"] >= config.MIN_TRADES


def test_pure_noise_fails_the_t_bar():
    checks, _ = gate.dev_checks(trades_from_daily(series(2, 0.0)), 0.0, 2.5)
    assert not all(c.ok for c in checks)


def test_an_edge_from_one_year_fails_drop_best_year():
    days = series(3, 0.0)
    bumped = [(d, v + (0.01 if d.year == 2021 else -0.0005)) for d, v in days]
    v = verdict(gate.dev_checks(trades_from_daily(bumped), 0.001, 2.5)[0])
    assert v["positive_expectancy"] and not v["drop_best_year"]


def test_a_higher_threshold_can_fail_the_same_edge():
    t = trades_from_daily(series(4, 0.0008))
    low = verdict(gate.dev_checks(t, 0.0005, 2.0)[0])["deflated_t"]
    high = verdict(gate.dev_checks(t, 0.0005, 30.0)[0])["deflated_t"]
    assert low and not high


@pytest.mark.parametrize("n", [0, 1])
def test_zero_or_one_trade_fails_with_reasons_and_no_crash(n):
    t = trades_from_daily([(pd.Timestamp("2024-03-04").date(), 0.01)] * n, per_day=1)
    checks, m = gate.dev_checks(t, 0.0, 2.5)
    assert not all(c.ok for c in checks) and not verdict(checks)["min_trades"]


SPEC = Spec.from_dict({"name": "t", "family": "gap_fade", "timeframe": "5Min",
                       "params": {"gap_pct": 0.002, "entry_bar": 1},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "gap downs mean-revert"})


def test_evaluate_records_the_trial_and_refuses_a_repeat(tmp_path):
    led = Ledger(tmp_path / "t.jsonl")
    frames = {"A": sessions(random_walk(n_days=40))}
    res = gate.evaluate(SPEC, frames, {"A": "large"}, None, led)
    assert not res.passed and led.count() == 1
    assert led.read()[0]["fingerprint"] == SPEC.fingerprint()
    with pytest.raises(gate.AlreadyTried):
        gate.evaluate(SPEC, frames, {"A": "large"}, None, led)
    assert led.count() == 1


def test_evaluate_refuses_a_corrupt_ledger_without_a_verdict(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("garbage\n")
    with pytest.raises(Exception):
        gate.evaluate(SPEC, {"A": sessions(random_walk())}, {"A": "large"}, None, Ledger(p))


def test_the_holdout_is_burned_after_the_allowed_looks(tmp_path, monkeypatch):
    led = Ledger(tmp_path / "t.jsonl")
    for i in range(config.MAX_HOLDOUT_LOOKS):
        led.append({"fingerprint": f"x{i}", "holdout_look": True})
    monkeypatch.setattr(gate, "dev_checks", lambda *a, **k: ([gate.Check("all", True, "")], {"mean_bps": 5, "n_trades": 0, "t": 0}))
    res = gate.evaluate(SPEC, {"A": sessions(random_walk())}, {"A": "large"}, None, led)
    assert not res.passed and any("exhausted" in c.detail for c in res.checks)
