"""The live record against the backtested expectation.

Two rules this repo already learned the hard way apply here (research/FINDINGS.md):
a pooled number can be one event in disguise, so this always reports a breakdown alongside
the total; and two rule generations must never blend, so everything is also split by
`rules_version`.

The verdict stays None until TRADES_NEEDED round trips exist. With ~13% exposure per name
the two symbols fire roughly 20 round trips a year, so that is about 18 months -- and
reporting a verdict sooner would be reading noise. See trader/ACCEPTANCE.md.
"""
from trader import params

# Measured 2026-10-10 with research/rsi2/rsi2_edge_backtest.py: Yahoo adjusted daily closes,
# 2000-01-01 onward, 5 bps per round trip, randomization test over 2,000 matched
# random-entry simulations. Recorded here so the page can show live against expected.
BACKTEST = {
    "AMZN": {"trades": 232, "bps_per_trade": 150.1, "win_rate": 75.9, "t_stat": 5.53,
             "p_vs_random": 0.002, "max_dd_pct": -27.7, "mean_bars_held": 3.68,
             "positive_years": "19/24", "worst_trade_pct": -16.9},
    "AAPL": {"trades": 245, "bps_per_trade": 117.5, "win_rate": 75.1, "t_stat": 5.10,
             "p_vs_random": 0.010, "max_dd_pct": -32.4, "mean_bars_held": 4.16,
             "positive_years": "23/26", "worst_trade_pct": -18.6},
}

TRADES_NEEDED = 30


def _price(row) -> float:
    """The fill if there is one, else the price the decision was made on."""
    filled = row.get("filled_avg_price")
    return float(filled) if filled not in (None, "", "None") else float(row["decision_close"])


def round_trips(rows: "list[dict]") -> "list[dict]":
    """Pair each buy with the next sell in the same symbol. An unpaired buy is still open."""
    open_buys: "dict[str, dict]" = {}
    trips = []
    for row in sorted(rows, key=lambda r: (r.get("date", ""), r.get("symbol", ""))):
        symbol, side = row["symbol"], row["side"]
        if side == "buy":
            open_buys[symbol] = row
        elif side == "sell" and symbol in open_buys:
            entry = open_buys.pop(symbol)
            entry_px, exit_px = _price(entry), _price(row)
            decision = entry.get("decision_close")
            trips.append({
                "symbol": symbol,
                "entry_date": entry.get("date"), "entry_price": entry_px,
                "exit_date": row.get("date"), "exit_price": exit_px,
                "qty": entry.get("qty"),
                "bars_held": row.get("bars_held"),
                "exit_reason": row.get("exit_reason"),
                "pl": round((exit_px - entry_px) * float(entry.get("qty") or 0), 2),
                "pl_pct": round((exit_px / entry_px - 1.0) * 100.0, 4) if entry_px else None,
                "slippage_bps": round((entry_px / float(decision) - 1.0) * 1e4, 2)
                if decision else None,
                "rules_version": row.get("rules_version"),
            })
    return trips


def _stats(trips: "list[dict]") -> dict:
    if not trips:
        return {"trades_closed": 0, "bps_per_trade": None, "win_rate": None,
                "mean_bars_held": None, "slippage_bps": None}
    pls = [t["pl_pct"] for t in trips if t["pl_pct"] is not None]
    bars = [t["bars_held"] for t in trips if t["bars_held"] is not None]
    slip = [t["slippage_bps"] for t in trips if t["slippage_bps"] is not None]
    return {
        "trades_closed": len(trips),
        "bps_per_trade": round(sum(pls) / len(pls) * 100.0, 2) if pls else None,
        "win_rate": round(sum(1 for p in pls if p > 0) / len(pls) * 100.0, 1) if pls else None,
        "mean_bars_held": round(sum(bars) / len(bars), 2) if bars else None,
        "slippage_bps": round(sum(slip) / len(slip), 2) if slip else None,
    }


def _group(trips, key) -> dict:
    out: "dict[str, list]" = {}
    for t in trips:
        out.setdefault(t.get(key) or "unknown", []).append(t)
    return {k: _stats(v) for k, v in out.items()}


def evaluate(rows: "list[dict]") -> dict:
    trips = round_trips(rows)
    return _stats(trips) | {
        "trades_needed": TRADES_NEEDED,
        "per_symbol": _group(trips, "symbol"),
        "per_rules_version": _group(trips, "rules_version"),
        "per_year": _group([t | {"year": (t["exit_date"] or "")[:4]} for t in trips], "year"),
        "backtest": {s: BACKTEST[s] for s in params.SYMBOLS},
        "trips": trips,
        # No verdict before the bar in trader/ACCEPTANCE.md is met. The page renders the
        # absence rather than hiding the section.
        "verdict": None,
    }
