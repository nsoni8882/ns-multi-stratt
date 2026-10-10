import json

from trader import state


def test_opening_balance_is_recorded_once_and_never_moves():
    s = {}
    assert state.opening_balance(s, 100_000.0) == 100_000.0
    assert state.opening_balance(s, 123_456.0) == 100_000.0


def test_entry_date_prefers_the_state_file():
    s = {"positions": {"AMZN": {"entry_date": "2026-10-12"}}}
    assert state.entry_date(s, "AMZN", api=None, today="2026-10-20") == "2026-10-12"


def test_entry_date_recovered_from_order_history():
    """State lost, position still at the broker: recover from the last filled buy."""
    class Api:
        def last_filled_buy(self, symbol):
            return {"filled_at": "2026-10-12T20:00:02.000000Z"}

    assert state.entry_date({}, "AMZN", api=Api(), today="2026-10-20") == "2026-10-12"


def test_unknown_entry_date_is_reported_not_guessed():
    """Defaulting to today would silently reset the time stop on every run."""
    class Api:
        def last_filled_buy(self, symbol):
            return None

    assert state.entry_date({}, "AMZN", api=Api(), today="2026-10-20") is None


def test_load_of_a_missing_or_corrupt_file_is_an_empty_state(tmp_path):
    assert state.load(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert state.load(bad) == {}


def test_save_then_load_round_trips(tmp_path):
    p = tmp_path / "paper_state.json"
    state.save(p, {"opening_balance": 100_000.0,
                   "positions": {"AMZN": {"entry_date": "2026-10-12"}}})
    assert state.load(p)["positions"]["AMZN"]["entry_date"] == "2026-10-12"


def test_append_jsonl_keeps_only_the_last_n(tmp_path):
    from trader.ledger import append_jsonl
    p = tmp_path / "runs.jsonl"
    for i in range(10):
        append_jsonl(p, {"i": i}, keep=4)
    rows = [json.loads(line) for line in p.read_text().splitlines()]
    assert [r["i"] for r in rows] == [6, 7, 8, 9]
