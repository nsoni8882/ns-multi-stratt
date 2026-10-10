"""Ask the broker what actually filled, and append the answer to the ledger.

A market-on-close order is submitted at 15:25 and accepted immediately, but it does not fill
until the 16:00 auction. Everything the trading run can record about the fill at that moment
is therefore unknown: no price, no quantity, status "accepted". Left alone, every published
price would be the 15:25 decision price wearing a fill's clothes -- P/L that does not
reconcile with the account equity beside it, and a decision-vs-fill slippage of exactly zero
forever, which is the one number trader/ACCEPTANCE.md sets a threshold against.

Append-only, like the rest of the ledger: the original row stays as the record of what the
bot believed when it acted, and a `kind: "fill"` row records what the broker did.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.reconcile --data-dir history
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from trader.alpaca import Alpaca, AlpacaError
from trader.ledger import append_jsonl

# Alpaca order states that will never change again.
TERMINAL = {"filled", "canceled", "cancelled", "expired", "rejected", "done_for_day",
            "replaced", "stopped", "suspended", "unknown"}


def _read(path) -> "list[dict]":
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def needs_settling(rows: "list[dict]") -> "list[str]":
    """Order ids whose outcome the ledger does not yet know, oldest first."""
    latest: "dict[str, str]" = {}
    order = []
    for row in rows:
        oid = row.get("order_id")
        if not oid:
            continue
        if oid not in latest:
            order.append(oid)
        latest[oid] = row.get("status") or ""
    return [oid for oid in order if latest[oid] not in TERMINAL]


def settle(api, path) -> int:
    """Append a fill row for every order that has reached a terminal state. Returns how many.

    An order the broker no longer knows about is recorded as `unknown` rather than asked
    about on every future run -- `unknown` is terminal, so the ledger stops chasing it.
    """
    rows = _read(path)
    if not rows:
        return 0
    context = {}
    for row in rows:
        if row.get("order_id") and row.get("kind") != "fill":
            context.setdefault(row["order_id"], row)

    appended = 0
    for oid in needs_settling(rows):
        try:
            order = api.order(oid)
        except AlpacaError as e:
            if e.status != 404:
                raise
            order = {"id": oid, "status": "unknown", "filled_avg_price": None,
                     "filled_qty": None, "filled_at": None}
        status = (order.get("status") or "").lower()
        if status not in TERMINAL:
            continue  # still working; the next run will ask again
        src = context.get(oid, {})
        append_jsonl(path, {
            "kind": "fill",
            "order_id": oid,
            "symbol": src.get("symbol") or order.get("symbol"),
            "side": src.get("side") or order.get("side"),
            "date": src.get("date"),
            "qty": src.get("qty"),
            "status": status,
            "filled_at": order.get("filled_at"),
            "filled_qty": order.get("filled_qty"),
            "filled_avg_price": order.get("filled_avg_price"),
            # Carried so the round trip can still be measured against what the rule saw.
            "decision_close": src.get("decision_close"),
            "rsi2": src.get("rsi2"),
            "sma200": src.get("sma200"),
            "trend_gap_pct": src.get("trend_gap_pct"),
            "exit_reason": src.get("exit_reason"),
            "bars_held": src.get("bars_held"),
            "entry_date": src.get("entry_date"),
            "entry_price": src.get("entry_price"),
            "equity_at_decision": src.get("equity_at_decision"),
            "slice_pct": src.get("slice_pct"),
            "rules_version": src.get("rules_version"),
            "settled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        appended += 1
    return appended


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="history")
    args = ap.parse_args(argv)
    api = Alpaca(os.environ["ALPACA_KEY_ID"], os.environ["ALPACA_SECRET_KEY"])
    n = settle(api, Path(args.data_dir) / "paper_trades.jsonl")
    print(f"settled {n} order(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
