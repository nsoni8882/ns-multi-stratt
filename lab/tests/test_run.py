import json

import pytest

from lab import run


def test_help_lists_the_three_commands(capsys):
    with pytest.raises(SystemExit):
        run.main(["--help"])
    out = capsys.readouterr().out
    assert all(c in out for c in ("fetch", "backtest", "export"))


def test_backtest_rejects_a_bad_spec_before_touching_the_network(tmp_path, capsys):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"family": "nope"}))
    assert run.main(["backtest", str(p)]) == 2
    assert "unknown family" in capsys.readouterr().err


def test_export_with_nothing_registered_writes_a_valid_empty_document(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "Registry", lambda: __import__("lab.lifecycle", fromlist=["Registry"]).Registry(tmp_path / "r.json"))
    monkeypatch.setattr(run, "Ledger", lambda: __import__("lab.trials", fromlist=["Ledger"]).Ledger(tmp_path / "t.jsonl"))
    out = tmp_path / "lab.json"
    assert run.main(["export", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["strategies"] == []


def _wire(tmp_path, monkeypatch, ledger_text=None):
    from lab import universe
    from lab.lifecycle import Registry
    from lab.tests.conftest import random_walk, sessions
    from lab.trials import Ledger
    reg_path, led_path = tmp_path / "r.json", tmp_path / "t.jsonl"
    if ledger_text is not None:
        led_path.write_text(ledger_text)
    monkeypatch.setattr(run, "Registry", lambda: Registry(reg_path))
    monkeypatch.setattr(run, "Ledger", lambda: Ledger(led_path))
    monkeypatch.setattr(run, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(run, "_membership", lambda: {2024: ["A"]})
    monkeypatch.setattr(run, "_frames", lambda spec, m: {"A": sessions(random_walk(n_days=40))})
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"name": "g", "family": "gap_fade", "timeframe": "5Min",
                                "params": {"gap_pct": 0.002, "entry_bar": 1},
                                "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                                "hypothesis": "gap downs mean-revert"}))
    return Registry(reg_path), spec


def test_a_gate_crash_does_not_strand_the_spec_in_the_registry(tmp_path, monkeypatch):
    from lab.trials import LedgerError
    reg, spec = _wire(tmp_path, monkeypatch, ledger_text="garbage\n")
    with pytest.raises(LedgerError):
        run.main(["backtest", str(spec)])
    assert reg.all() == {}  # a repaired ledger can evaluate the same spec


def test_backtest_then_export_round_trip_keeps_dates_as_dates(tmp_path, monkeypatch):
    import re
    reg, spec = _wire(tmp_path, monkeypatch)
    assert run.main(["backtest", str(spec)]) == 0
    out = tmp_path / "lab.json"
    assert run.main(["export", "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert len(doc["strategies"]) == 1 and doc["strategies"][0]["stage"] == "rejected"
    for pt in doc["strategies"][0]["equity_curve"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", pt["t"]), pt["t"]
