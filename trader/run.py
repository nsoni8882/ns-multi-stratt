"""The decision loop: one pass over AMZN and AAPL, at ~15:25 ET.

Reads the rule's inputs from Alpaca, decides per symbol, submits market-on-close orders, and
appends to two append-only ledgers -- one row per fill, and one row per run whether it traded
or not. The second is what makes a *non*-trade auditable later.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.run --dry-run
    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.run --live --data-dir history
"""
import argparse
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trader import params, state
from trader.alpaca import TRADING, Alpaca, AlpacaError, minutes_to_close, sessions_between
from trader.ledger import append_jsonl
from trader.rule import decide
from trader.sizing import shares_for

# Both bounds are declared in params.py, because each decides whether an order is placed.
CUTOFF_MINUTES = params.CUTOFF_MINUTES
MAX_MINUTES_TO_CLOSE = params.MAX_MINUTES_TO_CLOSE


def provenance() -> dict:
    """Which Actions run produced this row. The Actions log is deleted after 90 days and the
    ledger is not, so without this a row cannot be traced back to the run that wrote it.
    Mirrors what scanner/ledger.py records for the scan."""
    env = os.environ
    run_id = env.get("GITHUB_RUN_ID", "")
    repo = env.get("GITHUB_REPOSITORY", "")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    return {
        "run_id": run_id,
        "sha": env.get("GITHUB_SHA", "")[:12],
        "event": env.get("GITHUB_EVENT_NAME", "local"),
        "url": f"{server}/{repo}/actions/runs/{run_id}" if run_id and repo else "",
    }


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)


def _finish(record, data_dir, st, state_file):
    append_jsonl(data_dir / "paper_runs.jsonl", record)
    state.save(state_file, st)
    return record


def run(api, *, live: bool, data_dir, today: "str | None" = None) -> dict:
    """Entry point for one pass. Never returns without writing a ledger row."""
    data_dir = Path(data_dir)
    state_file = data_dir / "paper_state.json"
    st = state.load(state_file)

    acct = api.account()
    equity, buying_power = float(acct["equity"]), float(acct["buying_power"])
    cash = float(acct.get("cash") or 0.0)
    clock = api.clock()
    today = today or clock["timestamp"][:10]
    opening = state.opening_balance(st, equity)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "date": today, "mode": "live" if live else "dry-run",
              "rules_version": params.rules_version(), "equity": equity,
              "opening_balance": opening, "orders": 0, "late": False, "early": False,
              "skip_reason": None, "decisions": {}, "errors": [], "crashed": False}
    record |= provenance()

    if not clock["is_open"]:
        record["skip_reason"] = "market closed"
        log("market closed; next open", clock["next_open"])
        return _finish(record, data_dir, st, state_file)

    left = minutes_to_close(clock)
    record["minutes_to_close"] = round(left, 1)
    if left < CUTOFF_MINUTES:
        record["late"] = True
        record["skip_reason"] = (f"inside the {CUTOFF_MINUTES}-minute cutoff; "
                                 "cls orders would be rejected")
        log(record["skip_reason"])
        return _finish(record, data_dir, st, state_file)
    if left > MAX_MINUTES_TO_CLOSE:
        # The winter cron fires at 14:25 ET. Deciding on a bar that far from the close is a
        # different strategy from the backtested one, so stand down and say why.
        record["early"] = True
        record["skip_reason"] = (f"{left:.0f} minutes to the close is too early; this rule "
                                 f"decides within {MAX_MINUTES_TO_CLOSE} minutes of it")
        log(record["skip_reason"])
        return _finish(record, data_dir, st, state_file)

    try:
        positions = api.positions()
        open_orders = api.open_order_symbols()
        cal_start = (datetime.fromisoformat(today) - timedelta(days=90)).strftime("%Y-%m-%d")
        calendar = api.calendar(cal_start, today)
    except Exception as e:  # noqa: BLE001 -- a durable row matters more than the type
        # Without this the run dies here and leaves nothing but an Actions log.
        record["crashed"] = True
        record["errors"].append({"stage": "setup", "error": str(e)})
        log(f"setup failed -- {e}")
        _finish(record, data_dir, st, state_file)
        raise
    n_held = len(positions)
    st.setdefault("positions", {})

    for symbol in params.SYMBOLS:
        try:
            bars = api.daily_closes(symbol)
        except Exception as e:  # noqa: BLE001 -- a timeout must skip one symbol, not the run
            # Deliberately broader than AlpacaError: only HTTPError is converted, so a read
            # timeout or a malformed body would otherwise escape and take the whole run down
            # after the other symbol had already traded.
            record["errors"].append({"symbol": symbol, "stage": "data", "error": str(e)})
            log(f"{symbol}: data error, skipped -- {e}")
            continue

        closes = [c for _, c in bars]
        held = symbol in positions
        entry = state.entry_date(st, symbol, api, today) if held else None
        bars_held = sessions_between(calendar, entry, today) if entry else 0
        d = decide(closes, held=held, bars_held=bars_held)
        row = asdict(d) | {"bars_held": bars_held, "entry_date": entry, "held": held}
        record["decisions"][symbol] = row
        log(f"{symbol}: {d.action} ({d.reason}) "
            f"rsi2={'n/a' if d.rsi2 is None else round(d.rsi2, 1)} px={d.price}")

        if symbol in open_orders:
            row["skipped"] = "an order is already working"
            continue
        if d.action in ("skip", "wait", "hold"):
            continue
        # A held position whose entry date nothing knows cannot have its time stop judged.
        # Exit on the RSI rule only, and say so rather than guessing the date.
        if held and entry is None and d.reason == "time_stop":
            row["skipped"] = "entry date unknown; time stop not judged"
            continue

        if d.action == "buy":
            if st["positions"].get(symbol, {}).get("entered_on") == today:
                row["skipped"] = "already entered today"
                continue
            qty, refusal = shares_for(equity, d.price, buying_power, n_held, cash)
            if refusal:
                row["skipped"] = refusal
                log(f"  entry refused -- {refusal}")
                continue
        else:
            qty = abs(int(float(positions[symbol]["qty"])))

        if not live:
            log(f"  DRY-RUN would submit {d.action.upper()} {qty} {symbol} MOC")
            continue

        try:
            order = api.submit(symbol, "buy" if d.action == "buy" else "sell", qty)
        except Exception as e:  # noqa: BLE001 -- same reasoning as the data call above
            # Deliberately not retried: a retry could land past the cutoff, or re-submit an
            # order the rule no longer wants. Log it and leave the symbol as it is.
            status = getattr(e, "status", None)
            record["errors"].append({"symbol": symbol, "stage": "order", "status": status,
                                     "error": str(e)})
            row["skipped"] = f"order rejected: {status if status else type(e).__name__}"
            log(f"  order rejected -- {e}")
            continue

        record["orders"] += 1
        log(f"  SUBMITTED {d.action.upper()} {qty} {symbol} MOC id={order['id']}")
        trade = {"symbol": symbol, "side": order["side"], "order_id": order["id"],
                 "submitted_at": order.get("submitted_at"), "filled_at": order.get("filled_at"),
                 "filled_qty": order.get("filled_qty"), "status": order.get("status"),
                 "filled_avg_price": order.get("filled_avg_price"),
                 "qty": qty, "date": today, "decision_close": d.price, "rsi2": d.rsi2,
                 "sma200": d.sma200, "trend_gap_pct": d.trend_gap_pct,
                 "equity_at_decision": equity, "slice_pct": params.SLICE_PCT,
                 "rules_version": params.rules_version()}
        if d.action == "sell":
            trade |= {"exit_reason": d.reason, "bars_held": bars_held, "entry_date": entry,
                      "entry_price": st["positions"].get(symbol, {}).get("entry_price")}
        append_jsonl(data_dir / "paper_trades.jsonl", trade)

        if d.action == "buy":
            st["positions"][symbol] = {"entry_date": today, "entered_on": today,
                                       "entry_price": d.price, "qty": qty}
            # The second symbol in this same run must not be sized against cash the first
            # one has already spent.
            cash = max(0.0, cash - qty * d.price)
            n_held += 1
        else:
            st["positions"].pop(symbol, None)
            n_held = max(0, n_held - 1)

    log("done:", record["orders"], "order(s)")
    return _finish(record, data_dir, st, state_file)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--live", action="store_true", help="submit real paper orders")
    g.add_argument("--dry-run", action="store_true", help="decide only (the default)")
    ap.add_argument("--data-dir", default="history", help="where the ledgers and state live")
    args = ap.parse_args(argv)

    if "paper" not in TRADING:
        sys.exit("Refusing to run: the trading endpoint is not the paper API.")
    key, secret = os.environ.get("ALPACA_KEY_ID", ""), os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        sys.exit("Set ALPACA_KEY_ID and ALPACA_SECRET_KEY (paper keys).")

    api = Alpaca(key, secret)
    acct = api.account()
    log(f"account {acct['account_number']} equity ${float(acct['equity']):,.2f} "
        f"mode {'LIVE-PAPER' if args.live else 'DRY-RUN'}")
    run(api, live=args.live, data_dir=args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
