import json

from trader import params
from trader.export import build, write

ACCOUNT = {"equity": "100000", "cash": "100000", "buying_power": "400000"}
HISTORY = {"timestamp": [1760054400, 1760140800], "equity": [100000.0, 100500.0],
           "base_value": 100000.0}
DECISIONS = {
    "AMZN": {"action": "wait", "reason": "not oversold", "rsi2": 64.2, "sma200": 230.1,
             "price": 262.43, "trend_gap_pct": 14.0, "bars_held": 0, "held": False},
    "AAPL": {"action": "hold", "reason": "4 of 10 bars", "rsi2": 31.0, "sma200": 300.0,
             "price": 336.64, "trend_gap_pct": 12.2, "bars_held": 4, "held": True},
}


def payload(**over):
    kwargs = dict(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=[],
                  state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    return build(**(kwargs | over))


def test_export_day_one_empty_ledger():
    """Nothing has traded yet. Every panel must still render."""
    out = payload()
    assert out["account"]["opening_balance"] == 100000.0
    assert out["account"]["total_pl"] == 0.0
    assert out["account"]["deployed_pct"] == 0.0
    assert out["positions"] == []
    assert out["trades"] == []
    assert out["evaluation"]["trades_closed"] == 0
    assert out["evaluation"]["verdict"] is None
    assert len(out["signal_state"]) == len(params.SYMBOLS)
    assert out["rules_version"]
    assert out["as_of"] == "close"


def test_total_and_realised_pl_are_split():
    trades = [
        {"symbol": "AMZN", "side": "buy", "date": "2026-10-12", "qty": 100,
         "filled_avg_price": "100.0", "decision_close": 100.0, "rules_version": "v1"},
        {"symbol": "AMZN", "side": "sell", "date": "2026-10-15", "qty": 100,
         "filled_avg_price": "103.0", "decision_close": 103.0, "exit_reason": "rsi",
         "bars_held": 3, "rules_version": "v1"},
    ]
    out = payload(account={"equity": "100300", "cash": "100300", "buying_power": "401200"},
                  trade_rows=trades)
    assert out["account"]["realised_pl"] == 300.0
    assert out["account"]["total_pl"] == 300.0
    assert out["account"]["total_pl_pct"] == 0.3
    assert out["account"]["unrealised_pl"] == 0.0


def test_an_open_position_reports_bars_held_against_the_time_stop():
    positions = {"AAPL": {"symbol": "AAPL", "qty": "148", "current_price": "336.64",
                          "unrealized_pl": "592.0", "unrealized_plpc": "0.0121",
                          "avg_entry_price": "332.64"}}
    out = payload(positions=positions,
                  state={"opening_balance": 100000.0,
                         "positions": {"AAPL": {"entry_date": "2026-10-06",
                                                "entry_price": 332.64}}})
    pos = out["positions"][0]
    assert pos["symbol"] == "AAPL"
    assert pos["qty"] == 148
    assert pos["entry_date"] == "2026-10-06"
    assert pos["bars_held"] == 4
    assert pos["max_hold"] == params.MAX_HOLD
    assert pos["unrealised_pl"] == 592.0


def test_deployed_pct_reflects_capital_at_work():
    positions = {"AAPL": {"symbol": "AAPL", "qty": "148", "current_price": "336.64",
                          "unrealized_pl": "0", "unrealized_plpc": "0",
                          "avg_entry_price": "332.64"}}
    out = payload(account={"equity": "100000", "cash": "50000", "buying_power": "400000"},
                  positions=positions)
    assert out["account"]["deployed_pct"] == 50.0


def test_equity_curve_marks_the_days_a_position_was_open():
    # The dates come from HISTORY's own timestamps, so the fixture cannot drift out of step
    # with them -- hardcoding a pair that did not match is how this test first failed.
    from datetime import datetime, timezone
    held_day, flat_day = [datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
                          for ts in HISTORY["timestamp"]]
    runs = [{"date": held_day, "decisions": {"AMZN": {"held": True}}},
            {"date": flat_day, "decisions": {"AMZN": {"held": False}}}]
    out = payload(run_rows=runs)
    curve = {p["date"]: p["in_position"] for p in out["equity_curve"]}
    assert curve[held_day] is True
    assert curve[flat_day] is False


def test_signal_state_carries_a_verdict_per_symbol():
    by_symbol = {s["symbol"]: s for s in payload()["signal_state"]}
    assert by_symbol["AMZN"]["verdict"] == "Waiting"
    assert by_symbol["AAPL"]["verdict"] == "Held"


def test_a_blocked_trend_gate_is_named_rather_than_called_waiting():
    blocked = {"AMZN": {"action": "wait", "reason": "trend gate blocked", "rsi2": 8.0,
                        "sma200": 300.0, "price": 290.0, "trend_gap_pct": -3.3,
                        "bars_held": 0, "held": False},
               "AAPL": DECISIONS["AAPL"]}
    by_symbol = {s["symbol"]: s for s in payload(decisions=blocked)["signal_state"]}
    assert by_symbol["AMZN"]["verdict"] == "Trend gate blocked"


def test_runs_are_published_newest_first_and_capped_at_ten():
    runs = [{"date": f"2026-09-{d:02d}", "at": f"2026-09-{d:02d}T19:25:00+00:00",
             "mode": "live", "orders": 0, "late": False, "skip_reason": None,
             "decisions": {}} for d in range(1, 21)]
    out = payload(run_rows=runs)
    assert len(out["runs"]) == 10
    assert out["runs"][0]["date"] == "2026-09-20"


def test_the_change_history_is_published_for_the_overlay():
    out = payload()
    assert out["history"][0]["version"] == out["version"]
    assert out["history"][0]["summary"].strip()
    assert "fingerprint" not in out["history"][0]


def test_write_is_valid_json_with_a_trailing_newline(tmp_path):
    p = tmp_path / "paper-trading.json"
    write(p, payload())
    text = p.read_text()
    assert text.endswith("\n")
    assert json.loads(text)["account"]["equity"] == 100000.0
