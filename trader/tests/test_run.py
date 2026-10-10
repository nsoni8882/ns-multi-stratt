"""The decision loop, driven with a fake client. No network, no real orders."""
import json

from trader import params, run


def closes(n=400, start=100.0, step=1.0, tail=()):
    return [(f"2026-01-{i % 28 + 1:02d}", start + i * step) for i in range(n)] + \
           [(f"2026-10-{i + 1:02d}", c) for i, c in enumerate(tail)]


class Fake:
    """Enough of Alpaca to drive run(). Records submitted orders."""

    def __init__(self, *, bars=None, positions=None, open_orders=(), equity=100_000.0,
                 is_open=True, last_buy=None):
        self.bars = bars or {s: closes(tail=[460.0, 420.0]) for s in params.SYMBOLS}
        self._positions = positions or {}
        self._open = set(open_orders)
        self.equity = equity
        self.is_open = is_open
        self._last_buy = last_buy
        self.submitted = []

    def account(self):
        return {"account_number": "PA000000TEST", "status": "ACTIVE",
                "equity": str(self.equity), "cash": str(self.equity),
                "buying_power": str(self.equity * 4)}

    def clock(self):
        return {"is_open": self.is_open, "timestamp": "2026-10-12T15:25:00-04:00",
                "next_close": "2026-10-12T16:00:00-04:00",
                "next_open": "2026-10-13T09:30:00-04:00"}

    def calendar(self, start, end):
        return [{"date": f"2026-10-{d:02d}"} for d in range(1, 32)]

    def positions(self):
        return dict(self._positions)

    def open_order_symbols(self):
        return set(self._open)

    def last_filled_buy(self, symbol):
        return self._last_buy

    def daily_closes(self, symbol):
        return self.bars[symbol]

    def portfolio_history(self, period="all"):
        return {"timestamp": [1760000000], "equity": [self.equity], "base_value": 100_000.0}

    def submit(self, symbol, side, qty):
        self.submitted.append((symbol, side, qty))
        return {"id": f"order-{len(self.submitted)}", "symbol": symbol, "side": side,
                "qty": str(qty), "filled_avg_price": None, "status": "accepted",
                "submitted_at": "2026-10-12T19:25:11Z", "filled_at": None}


def held_position(symbol, qty="190", price="421.0"):
    return {symbol: {"symbol": symbol, "qty": qty, "unrealized_pl": "100",
                     "unrealized_plpc": "0.01", "current_price": price,
                     "avg_entry_price": "420.0"}}


def test_oversold_in_uptrend_submits_a_buy_for_each_symbol(tmp_path):
    api = Fake()
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert sorted(s for s, _, _ in api.submitted) == sorted(params.SYMBOLS)
    assert all(side == "buy" for _, side, _ in api.submitted)
    assert record["orders"] == 2


def test_dry_run_decides_but_submits_nothing(tmp_path):
    api = Fake()
    record = run.run(api, live=False, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["orders"] == 0
    assert record["decisions"]["AMZN"]["action"] == "buy"


def test_market_closed_does_nothing(tmp_path):
    api = Fake(is_open=False)
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["skip_reason"] == "market closed"


def test_refuses_to_submit_inside_cutoff(tmp_path):
    """Alpaca rejects cls orders after 15:50 ET. Under ten minutes to the close, stand down
    and say so -- submitting would produce a rejection, not a fill."""
    api = Fake()
    api.clock = lambda: {"is_open": True, "timestamp": "2026-10-12T15:54:00-04:00",
                         "next_close": "2026-10-12T16:00:00-04:00",
                         "next_open": "2026-10-13T09:30:00-04:00"}
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["late"] is True
    assert "cutoff" in record["skip_reason"]


def test_second_run_same_day_is_idempotent(tmp_path):
    """Two wake-ups in one session must not double a position or restart the time stop."""
    api = Fake()
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    first = list(api.submitted)
    api._positions = {s: held_position(s)[s] for s in params.SYMBOLS}
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == first, "a second run on the same day placed another order"


def test_open_order_blocks_a_second_order_for_that_symbol(tmp_path):
    api = Fake(open_orders=params.SYMBOLS)
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []


def test_held_position_sells_on_the_time_stop(tmp_path):
    api = Fake(positions=held_position("AMZN"),
               bars={s: closes(tail=[460.0, 420.0, 421.0]) for s in params.SYMBOLS})
    (tmp_path / "paper_state.json").write_text(json.dumps(
        {"opening_balance": 100_000.0, "positions": {"AMZN": {"entry_date": "2026-09-25"}}}))
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert ("AMZN", "sell", 190) in api.submitted


def test_a_rejected_order_is_logged_and_not_retried(tmp_path):
    from trader.alpaca import AlpacaError
    api = Fake()
    calls = []

    def boom(symbol, side, qty):
        calls.append(symbol)
        raise AlpacaError(422, "cls orders are not accepted at this time", "POST", "/v2/orders")

    api.submit = boom
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert sorted(calls) == sorted(params.SYMBOLS)
    assert len(calls) == len(set(calls)), "an order was retried"
    assert record["errors"], "the rejection was not recorded"


def test_a_data_error_on_one_symbol_still_trades_the_other(tmp_path):
    from trader.alpaca import AlpacaError
    api = Fake()
    real = api.daily_closes

    def flaky(symbol):
        if symbol == "AMZN":
            raise AlpacaError(500, "upstream", "GET", "/v2/stocks/bars")
        return real(symbol)

    api.daily_closes = flaky
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert [s for s, _, _ in api.submitted] == ["AAPL"]


def test_short_bar_history_skips_the_symbol(tmp_path):
    api = Fake(bars={s: closes(n=150) for s in params.SYMBOLS})
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["decisions"]["AMZN"]["action"] == "skip"


def test_the_run_is_appended_to_the_runs_ledger(tmp_path):
    api = Fake()
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    rows = [json.loads(l) for l in (tmp_path / "paper_runs.jsonl").read_text().splitlines()]
    assert rows[-1]["decisions"]["AAPL"]["rsi2"] < params.BUY_BELOW
    assert rows[-1]["rules_version"]


def test_a_fill_is_appended_to_the_trades_ledger_with_its_decision_context(tmp_path):
    api = Fake()
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    rows = [json.loads(l) for l in (tmp_path / "paper_trades.jsonl").read_text().splitlines()]
    row = next(r for r in rows if r["symbol"] == "AMZN")
    for key in ("side", "order_id", "decision_close", "rsi2", "sma200", "trend_gap_pct",
                "equity_at_decision", "slice_pct", "rules_version"):
        assert key in row, key
    assert row["decision_close"] == 420.0
