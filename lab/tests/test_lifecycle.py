import pytest

from lab.lifecycle import LifecycleError, Registry
from lab.spec import Spec

SPEC = Spec.from_dict({"name": "t", "family": "orb", "timeframe": "5Min", "params": {},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "breakouts continue"})
RULES = [{"metric": "mean_bps", "op": "lt", "threshold": 0.0, "after_trades": 30}]


def shadowed(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    reg.advance(fp, "backtested", reason="ran the gate")
    reg.advance(fp, "shadow", reason="passed", failure_rules=RULES)
    return reg, fp


def test_the_happy_path_and_persistence(tmp_path):
    reg, fp = shadowed(tmp_path)
    reg.advance(fp, "paper", reason="owner approved", approved_by="owner")
    assert Registry(tmp_path / "r.json").get(fp)["stage"] == "paper"


def test_illegal_jumps_are_refused(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    with pytest.raises(LifecycleError):
        reg.advance(fp, "paper", reason="skip", approved_by="owner")


def test_paper_needs_a_human_approval(tmp_path):
    reg, fp = shadowed(tmp_path)
    with pytest.raises(LifecycleError):
        reg.advance(fp, "paper", reason="auto")


def test_shadow_needs_failure_rules_and_they_cannot_be_edited(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    reg.advance(fp, "backtested", reason="ran")
    with pytest.raises(LifecycleError):
        reg.advance(fp, "shadow", reason="no rules")
    reg.advance(fp, "shadow", reason="ok", failure_rules=RULES)
    assert reg.get(fp)["failure_rules"] == RULES
    with pytest.raises(LifecycleError):
        reg.advance(fp, "paper", reason="try to loosen", approved_by="o", failure_rules=[])


def test_rejected_and_retired_are_terminal_and_not_reregisterable(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    reg.advance(fp, "backtested", reason="ran")
    reg.advance(fp, "rejected", reason="failed t bar")
    with pytest.raises(LifecycleError):
        reg.advance(fp, "shadow", reason="again", failure_rules=RULES)
    with pytest.raises(LifecycleError):
        reg.register(SPEC)


def test_a_tripped_failure_rule_retires_the_strategy(tmp_path):
    reg, fp = shadowed(tmp_path)
    assert reg.apply_failure_rules(fp, {"n_trades": 10, "mean_bps": -5}) == []  # too early
    assert reg.apply_failure_rules(fp, {"n_trades": 40, "mean_bps": 3}) == []
    assert reg.apply_failure_rules(fp, {"n_trades": 40, "mean_bps": -5}) == ["mean_bps lt 0.0"]
    assert reg.get(fp)["stage"] == "retired"
