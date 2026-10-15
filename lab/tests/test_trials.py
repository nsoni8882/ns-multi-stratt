import pytest

from lab.trials import Ledger, LedgerError


def test_append_only_and_counts(tmp_path):
    led = Ledger(tmp_path / "t.jsonl")
    assert led.count() == 0
    led.append({"fingerprint": "a", "verdict": "fail", "holdout_look": False})
    led.append({"fingerprint": "b", "verdict": "pass", "holdout_look": True})
    assert led.count() == 2 and led.has("a") and not led.has("z") and led.holdout_looks() == 1
    assert len((tmp_path / "t.jsonl").read_text().splitlines()) == 2


def test_corrupt_line_is_refused_not_skipped(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"fingerprint": "a"}\nnot json\n')
    with pytest.raises(LedgerError):
        Ledger(p).count()
    with pytest.raises(LedgerError):
        Ledger(p).append({"fingerprint": "b"})  # never extend a ledger we cannot read


def test_holdout_looks_are_counted_per_window(tmp_path):
    led = Ledger(tmp_path / "t.jsonl")
    led.append({"fingerprint": "a", "holdout_look": True, "holdout_window": "w1"})
    led.append({"fingerprint": "b", "holdout_look": True, "holdout_window": "w2"})
    assert led.holdout_looks("w1") == 1 and led.holdout_looks("w2") == 1 and led.holdout_looks() == 2
