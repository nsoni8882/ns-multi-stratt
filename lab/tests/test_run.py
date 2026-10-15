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
