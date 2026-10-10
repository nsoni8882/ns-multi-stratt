"""Assemble paper-trading.json -- everything the page renders, in one file.

Written after the decision loop, so it reports the account as the broker sees it rather than
as the bot predicted. scan.yml copies the file into the site build; the trader never deploys.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.export \
        --data-dir history --out history/paper-trading.json
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from trader import evaluate as ev
from trader import params, state
from trader.alpaca import Alpaca

VERDICT_LABEL = {"buy": "Oversold", "sell": "Exiting", "hold": "Held",
                 "wait": "Waiting", "skip": "No data"}
NOT_CHECKED = "Not checked yet"
RUNS_SHOWN = 10


def _read_jsonl(path) -> "list[dict]":
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _verdict(decision: dict) -> str:
    if not decision:
        return NOT_CHECKED
    if decision.get("action") == "wait" and decision.get("reason") == "trend gate blocked":
        return "Trend gate blocked"
    return VERDICT_LABEL.get(decision.get("action", ""), NOT_CHECKED)


def last_decisions(run_rows: "list[dict]", fallback: dict) -> "tuple[dict, str | None]":
    """The most recent run that actually reached a decision, and the day it did.

    A run on a closed market records no decisions, so the newest row is routinely empty --
    every weekend, and every holiday. Reporting "unknown" for both symbols then would throw
    away a perfectly good reading from the last session, which is sitting in the ledger.
    """
    if fallback:
        newest = max((r for r in run_rows if r.get("decisions")),
                     key=lambda r: r.get("at") or "", default=None)
        return fallback, (newest or {}).get("date")
    for row in sorted(run_rows, key=lambda r: r.get("at") or "", reverse=True):
        if row.get("decisions"):
            return row["decisions"], row.get("date")
    return {}, None


def build(*, account: dict, positions: dict, history: dict, trade_rows: "list[dict]",
          run_rows: "list[dict]", state: dict, decisions: dict, as_of: str) -> dict:
    decisions, decided_on = last_decisions(run_rows, decisions)
    equity = float(account["equity"])
    cash = float(account["cash"])
    opening = float(state.get("opening_balance") or equity)
    evaluation = ev.evaluate(trade_rows)
    realised = round(sum(t["pl"] for t in evaluation["trips"]), 2)

    held = []
    for symbol, p in positions.items():
        entry = (state.get("positions") or {}).get(symbol, {})
        held.append({
            "symbol": symbol,
            "entry_date": entry.get("entry_date"),
            "entry_price": float(p.get("avg_entry_price") or entry.get("entry_price") or 0.0),
            "qty": abs(int(float(p["qty"]))),
            "price": float(p.get("current_price") or 0.0),
            "unrealised_pl": round(float(p.get("unrealized_pl") or 0.0), 2),
            "unrealised_pl_pct": round(float(p.get("unrealized_plpc") or 0.0) * 100.0, 2),
            "bars_held": (decisions.get(symbol) or {}).get("bars_held"),
            "max_hold": params.MAX_HOLD,
        })
    held.sort(key=lambda p: p["symbol"])
    unrealised = round(sum(p["unrealised_pl"] for p in held), 2)
    deployed = round((equity - cash) / equity * 100.0, 1) if equity else 0.0

    # Which days the bot was holding something, so the curve can shade them: a flat stretch
    # is deliberate idleness, not a broken chart, and that is the most misread thing here.
    in_position_dates = {r.get("date") for r in run_rows
                         if any(d.get("held") for d in (r.get("decisions") or {}).values())}
    curve = [{"date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"),
              "equity": round(float(value), 2),
              "in_position": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
              in in_position_dates}
             for ts, value in zip(history.get("timestamp") or [], history.get("equity") or [])]

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "rules_version": params.rules_version(),
        "version": params.current_version(params.HISTORY),
        # Published so the page's clock-icon overlay can show the same change history the
        # strategy tabs show. Newest first, as params.py declares it.
        "history": [r.as_dict() for r in params.HISTORY],
        "symbols": params.SYMBOLS,
        # Which session the rule state below was read on. Not always today: a closed market
        # records no decisions, so this is the last day the bot actually looked.
        "signal_state_as_of": decided_on,
        "account": {
            "opening_balance": round(opening, 2),
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "deployed_pct": deployed,
            "total_pl": round(equity - opening, 2),
            "total_pl_pct": round((equity / opening - 1.0) * 100.0, 3) if opening else 0.0,
            "realised_pl": realised,
            "unrealised_pl": unrealised,
        },
        "equity_curve": curve,
        "positions": held,
        "signal_state": [
            {"symbol": s,
             "rsi2": (decisions.get(s) or {}).get("rsi2"),
             "sma200": (decisions.get(s) or {}).get("sma200"),
             "price": (decisions.get(s) or {}).get("price"),
             "trend_gap_pct": (decisions.get(s) or {}).get("trend_gap_pct"),
             "buy_below": params.BUY_BELOW,
             "sell_above": params.SELL_ABOVE,
             "verdict": _verdict(decisions.get(s) or {}),
             "reason": (decisions.get(s) or {}).get("reason")}
            for s in params.SYMBOLS
        ],
        "trades": sorted(evaluation["trips"], key=lambda t: (t["exit_date"] or ""),
                         reverse=True),
        "evaluation": {k: v for k, v in evaluation.items() if k != "trips"},
        "runs": sorted(run_rows, key=lambda r: r.get("at") or r.get("date") or "",
                       reverse=True)[:RUNS_SHOWN],
    }


def write(path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="history")
    ap.add_argument("--out", default="history/paper-trading.json")
    ap.add_argument("--as-of", default="close", choices=("close", "intraday"))
    args = ap.parse_args(argv)

    api = Alpaca(os.environ["ALPACA_KEY_ID"], os.environ["ALPACA_SECRET_KEY"])
    data_dir = Path(args.data_dir)
    run_rows = _read_jsonl(data_dir / "paper_runs.jsonl")
    payload = build(
        account=api.account(),
        positions=api.positions(),
        history=api.portfolio_history("all"),
        trade_rows=_read_jsonl(data_dir / "paper_trades.jsonl"),
        run_rows=run_rows,
        state=state.load(data_dir / "paper_state.json"),
        decisions={},  # build() picks the newest run that reached a decision
        as_of=args.as_of,
    )
    write(args.out, payload)
    print(f"wrote {args.out}: {len(payload['trades'])} round trips, "
          f"{len(payload['positions'])} open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
