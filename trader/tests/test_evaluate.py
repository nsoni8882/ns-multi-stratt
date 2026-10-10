import pytest

from trader.evaluate import BACKTEST, TRADES_NEEDED, evaluate, round_trips


def buy(symbol, date, price, qty=100, decision=None):
    return {"symbol": symbol, "side": "buy", "date": date, "qty": qty,
            "filled_avg_price": str(price),
            "decision_close": decision if decision is not None else price,
            "rules_version": "abc123def456"}


def sell(symbol, date, price, qty=100, reason="rsi", bars=3, decision=None):
    return {"symbol": symbol, "side": "sell", "date": date, "qty": qty,
            "filled_avg_price": str(price),
            "decision_close": decision if decision is not None else price,
            "exit_reason": reason, "bars_held": bars, "rules_version": "abc123def456"}


def test_evaluate_with_no_closed_trades():
    """Day one. A renderable record, no division by zero, and explicitly no verdict."""
    out = evaluate([])
    assert out["trades_closed"] == 0
    assert out["trades_needed"] == TRADES_NEEDED
    assert out["bps_per_trade"] is None
    assert out["win_rate"] is None
    assert out["verdict"] is None


def test_an_open_trade_alone_is_not_a_round_trip():
    out = evaluate([buy("AMZN", "2026-10-12", 262.43)])
    assert out["trades_closed"] == 0
    assert out["verdict"] is None


def test_a_round_trip_is_paired_and_measured():
    rows = [buy("AMZN", "2026-10-12", 100.0), sell("AMZN", "2026-10-15", 103.0, bars=3)]
    trips = round_trips(rows)
    assert len(trips) == 1
    assert trips[0]["pl_pct"] == 3.0
    assert trips[0]["bars_held"] == 3
    assert trips[0]["exit_reason"] == "rsi"
    out = evaluate(rows)
    assert out["trades_closed"] == 1
    assert out["bps_per_trade"] == 300.0
    assert out["win_rate"] == 100.0
    assert out["mean_bars_held"] == 3.0


def test_slippage_is_measured_from_decision_close_against_the_fill():
    """The one approximation in the design: the rule decides on a 15:25 partial bar and
    fills in the closing auction. 100.50 against a 100.00 decision is 50 bps paid."""
    rows = [buy("AMZN", "2026-10-12", 100.5, decision=100.0),
            sell("AMZN", "2026-10-15", 103.0, decision=103.0)]
    assert evaluate(rows)["slippage_bps"] == 50.0


def test_two_symbols_are_paired_independently():
    rows = [buy("AMZN", "2026-10-12", 100.0), buy("AAPL", "2026-10-12", 200.0),
            sell("AAPL", "2026-10-14", 206.0, bars=2), sell("AMZN", "2026-10-16", 99.0, bars=4)]
    out = evaluate(rows)
    assert out["trades_closed"] == 2
    assert out["win_rate"] == 50.0
    assert out["per_symbol"]["AAPL"]["bps_per_trade"] == 300.0
    assert out["per_symbol"]["AMZN"]["bps_per_trade"] == -100.0


def test_a_rules_version_change_splits_the_record():
    """Two rule generations must never blend into one number."""
    rows = [buy("AMZN", "2026-10-12", 100.0), sell("AMZN", "2026-10-15", 103.0)]
    rows += [dict(buy("AMZN", "2026-11-12", 100.0), rules_version="zzz999"),
             dict(sell("AMZN", "2026-11-15", 95.0), rules_version="zzz999")]
    out = evaluate(rows)
    assert set(out["per_rules_version"]) == {"abc123def456", "zzz999"}
    assert out["per_rules_version"]["zzz999"]["bps_per_trade"] == -500.0


def test_no_verdict_until_the_bar_is_met():
    rows = []
    for i in range(TRADES_NEEDED - 1):
        rows += [buy("AMZN", f"2026-01-{i % 28 + 1:02d}", 100.0),
                 sell("AMZN", f"2026-02-{i % 28 + 1:02d}", 101.0)]
    assert evaluate(rows)["verdict"] is None


def test_the_backtest_expectation_is_carried_for_both_symbols():
    for symbol in ("AMZN", "AAPL"):
        assert BACKTEST[symbol]["bps_per_trade"] > 0
        assert BACKTEST[symbol]["trades"] > 200
        assert "t_stat" in BACKTEST[symbol]


def test_an_unpaired_sell_is_counted_not_silently_dropped():
    """A sell whose buy is missing from the ledger used to vanish, taking its realised P/L
    with it. This file is the evidence base; a quiet hole in it is the worst failure it has."""
    out = evaluate([sell("AMZN", "2026-10-15", 103.0)])
    assert out["trades_closed"] == 0
    assert out["unpaired_sells"] == 1


def test_a_second_buy_without_a_sell_does_not_erase_the_first():
    rows = [buy("AMZN", "2026-10-12", 100.0), buy("AMZN", "2026-10-13", 101.0),
            sell("AMZN", "2026-10-15", 103.0)]
    out = evaluate(rows)
    assert out["trades_closed"] == 1
    assert out["unpaired_buys"] == 1, "the first buy was dropped without trace"


def test_a_clean_ledger_reports_no_unpaired_fills():
    rows = [buy("AMZN", "2026-10-12", 100.0), sell("AMZN", "2026-10-15", 103.0)]
    out = evaluate(rows)
    assert out["unpaired_buys"] == 0
    assert out["unpaired_sells"] == 0


def accepted(symbol, date, side, order_id, decision, qty=100, **extra):
    return {"symbol": symbol, "side": side, "date": date, "qty": qty, "order_id": order_id,
            "status": "accepted", "filled_avg_price": None, "decision_close": decision,
            "rules_version": "f5e0af26ffd9"} | extra


def fill(symbol, date, side, order_id, decision, price, qty=100, status="filled", **extra):
    return {"kind": "fill", "symbol": symbol, "side": side, "date": date, "qty": qty,
            "order_id": order_id, "status": status, "filled_avg_price": price,
            "decision_close": decision, "rules_version": "f5e0af26ffd9"} | extra


def test_a_settled_order_counts_once_at_the_price_it_filled():
    """Both rows exist for one order -- what the bot believed, and what the broker did. The
    measurement must use the second and must not count the order twice."""
    rows = [accepted("AMZN", "2026-10-12", "buy", "o1", 420.0),
            fill("AMZN", "2026-10-12", "buy", "o1", 420.0, "421.0"),
            accepted("AMZN", "2026-10-15", "sell", "o2", 430.0, exit_reason="rsi", bars_held=3),
            fill("AMZN", "2026-10-15", "sell", "o2", 430.0, "429.5",
                 exit_reason="rsi", bars_held=3)]
    out = evaluate(rows)
    assert out["trades_closed"] == 1
    assert out["unpaired_buys"] == 0
    trip = round_trips(rows)[0]
    assert trip["entry_price"] == 421.0
    assert trip["exit_price"] == 429.5


def test_slippage_is_real_once_the_fill_is_known():
    """The number ACCEPTANCE.md sets a threshold against. It was structurally zero before
    fills were reconciled, because entry price and decision price were the same field."""
    rows = [accepted("AMZN", "2026-10-12", "buy", "o1", 420.0),
            fill("AMZN", "2026-10-12", "buy", "o1", 420.0, "421.0"),
            accepted("AMZN", "2026-10-15", "sell", "o2", 430.0, exit_reason="rsi"),
            fill("AMZN", "2026-10-15", "sell", "o2", 430.0, "430.0", exit_reason="rsi")]
    # Paid 421.00 against a 420.00 decision: 23.8 bps.
    assert evaluate(rows)["slippage_bps"] == pytest.approx(23.81, abs=0.05)


def test_a_cancelled_order_is_not_a_trade():
    rows = [accepted("AMZN", "2026-10-12", "buy", "o1", 420.0),
            fill("AMZN", "2026-10-12", "buy", "o1", 420.0, None, status="canceled")]
    out = evaluate(rows)
    assert out["trades_closed"] == 0
    assert out["unpaired_buys"] == 0, "a cancelled order should not look like an open trade"


def test_an_unsettled_order_is_still_counted_at_its_decision_price():
    """Between 15:25 and the settlement run the page must still show the position honestly,
    rather than dropping it until the broker is asked."""
    rows = [accepted("AMZN", "2026-10-12", "buy", "o1", 420.0),
            accepted("AMZN", "2026-10-15", "sell", "o2", 430.0, exit_reason="rsi")]
    assert evaluate(rows)["trades_closed"] == 1
