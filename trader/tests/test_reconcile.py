"""Market-on-close orders are accepted at 15:25 and fill in the 16:00 auction, so everything
the trading run records about a fill is unknown at the time it writes it. Without this step
every published price is the 15:25 decision price wearing a fill's clothes -- and the
decision-vs-fill slippage the acceptance bar depends on is structurally always zero."""
import json

import pytest

from trader.reconcile import needs_settling, settle

ACCEPTED = {"symbol": "AMZN", "side": "buy", "order_id": "o1", "date": "2026-10-12",
            "qty": 190, "status": "accepted", "filled_at": None, "filled_avg_price": None,
            "filled_qty": None, "decision_close": 420.0, "rsi2": 8.0, "sma200": 300.0,
            "trend_gap_pct": 40.0, "equity_at_decision": 100000.0, "slice_pct": 0.5,
            "rules_version": "f5e0af26ffd9"}


class Api:
    def __init__(self, orders):
        self.orders = orders
        self.asked = []

    def order(self, order_id):
        self.asked.append(order_id)
        return self.orders[order_id]


def write(tmp_path, rows):
    p = tmp_path / "paper_trades.jsonl"
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    return p


def rows_of(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_an_accepted_order_needs_settling():
    assert needs_settling([ACCEPTED]) == ["o1"]


def test_a_settled_order_is_not_asked_about_twice():
    filled = ACCEPTED | {"status": "filled", "filled_avg_price": "421.5", "kind": "fill"}
    assert needs_settling([ACCEPTED, filled]) == []


def test_the_fill_price_is_appended_not_overwritten(tmp_path):
    """The ledger is append-only: the decision row stays as the record of what the bot
    believed, and the fill row records what the broker did."""
    path = write(tmp_path, [ACCEPTED])
    api = Api({"o1": {"id": "o1", "status": "filled", "filled_avg_price": "421.5",
                      "filled_qty": "190", "filled_at": "2026-10-12T20:00:02Z"}})
    n = settle(api, path)
    assert n == 1
    rows = rows_of(path)
    assert len(rows) == 2
    assert rows[0]["status"] == "accepted"  # untouched
    fill = rows[1]
    assert fill["kind"] == "fill"
    assert fill["order_id"] == "o1"
    assert fill["filled_avg_price"] == "421.5"
    assert fill["decision_close"] == 420.0  # context carried so slippage can be measured
    assert fill["symbol"] == "AMZN" and fill["side"] == "buy"


def test_a_cancelled_order_is_recorded_as_such_and_never_counted_as_a_trade(tmp_path):
    path = write(tmp_path, [ACCEPTED])
    api = Api({"o1": {"id": "o1", "status": "canceled", "filled_avg_price": None,
                      "filled_qty": "0", "filled_at": None}})
    settle(api, path)
    fill = rows_of(path)[1]
    assert fill["status"] == "canceled"
    assert fill["filled_avg_price"] is None

    from trader.evaluate import round_trips
    assert round_trips(rows_of(path)) == [], "a cancelled order was counted as a trade"


def test_an_order_still_pending_is_left_for_the_next_run(tmp_path):
    path = write(tmp_path, [ACCEPTED])
    api = Api({"o1": {"id": "o1", "status": "pending_new", "filled_avg_price": None,
                      "filled_qty": None, "filled_at": None}})
    assert settle(api, path) == 0
    assert len(rows_of(path)) == 1


def test_an_order_the_broker_has_forgotten_is_recorded_rather_than_retried_forever(tmp_path):
    from trader.alpaca import AlpacaError
    path = write(tmp_path, [ACCEPTED])

    class Gone:
        def order(self, order_id):
            raise AlpacaError(404, "order not found", "GET", f"/v2/orders/{order_id}")

    settle(Gone(), path)
    fill = rows_of(path)[1]
    assert fill["status"] == "unknown"
    assert needs_settling(rows_of(path)) == []


def test_settling_an_empty_ledger_does_nothing(tmp_path):
    path = tmp_path / "paper_trades.jsonl"
    assert settle(Api({}), path) == 0
