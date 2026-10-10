"""Scan the S&P 500, write site JSON, record signals. Usage: python -m scanner.run --out DIR --db FILE"""
import argparse
import logging
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scanner.data import fetch_bars
from scanner.export import chart_payload, signal_row, write_json
# The names trader/ places orders for. Imported rather than duplicated so the two cannot
# disagree about what is traded; trader.params is stdlib-only, so this costs nothing.
from trader.params import SYMBOLS as TRADED_SYMBOLS
from scanner.market import market_payload
from scanner.store import SignalRecord, SignalStore
from scanner.strategies import STRATEGIES
from scanner.strategies.base import CONVICTION_RANK, Signal, current_version, rules_version
from scanner.universe import load_universe

TIMEFRAMES = ("4h", "1d")
MAX_FAILURE_RATE = 0.10
MAX_LISTED_FAILURES = 50  # health.json names the first few; the counts beside them are complete

log = logging.getLogger("scanner")


class ScanError(RuntimeError):
    pass


@dataclass(frozen=True)
class Hit:
    strategy_id: str
    timeframe: str
    ticker: str
    signal: Signal


def scan(bars_by_tf: dict, strategies, errors: "list[dict] | None" = None) -> "list[Hit]":
    """Evaluate every strategy over every fetched frame. A strategy that throws on one ticker
    is skipped rather than failing the scan, so `errors` is where that goes -- it used to leave
    no trace but a line in a CI log that expires."""
    hits = []
    for tf, bars in bars_by_tf.items():
        for ticker, df in bars.items():
            for strat in strategies:
                try:
                    sig = strat.evaluate(df)
                except Exception as exc:
                    log.exception("%s failed on %s %s", strat.id, ticker, tf)
                    if errors is not None:
                        errors.append({"strategy_id": strat.id, "ticker": ticker, "timeframe": tf,
                                       "error": f"{type(exc).__name__}: {exc}"[:300]})
                    continue
                if sig:
                    hits.append(Hit(strat.id, tf, ticker, sig))
    return hits


def run(out_dir: Path, db_path: Path, now: "pd.Timestamp | None" = None,
        universe: "pd.DataFrame | None" = None, fetch=fetch_bars, strategies=STRATEGIES) -> dict:
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    universe = universe if universe is not None else load_universe()
    tickers = universe["ticker"].tolist()
    meta = universe.set_index("ticker")

    started = time.monotonic()
    bars_by_tf, fetch_health = {}, {}
    for tf in TIMEFRAMES:
        bars_by_tf[tf], failed = fetch(tickers, tf, now)
        log.info("%s: %d fetched, %d failed", tf, len(bars_by_tf[tf]), len(failed))
        fetch_health[tf] = {"fetched": len(bars_by_tf[tf]), "failed": len(failed),
                            "failed_tickers": sorted(failed)[:MAX_LISTED_FAILURES]}
        if len(failed) / len(tickers) > MAX_FAILURE_RATE:
            raise ScanError(f"{len(failed)}/{len(tickers)} tickers failed for {tf}")

    strategy_errors: "list[dict]" = []
    hits = scan(bars_by_tf, strategies, strategy_errors)
    updated_at = now.isoformat()

    shutil.rmtree(out_dir, ignore_errors=True)
    summaries = []
    for strat in strategies:
        counts = {}
        for tf in TIMEFRAMES:
            rows = [
                signal_row(h.ticker, meta.at[h.ticker, "name"], meta.at[h.ticker, "sector"], h.signal,
                           bars_by_tf[tf][h.ticker]["close"])
                for h in hits if h.strategy_id == strat.id and h.timeframe == tf
            ]
            # Strongest conviction first, then freshest: a low-conviction short should never
            # head the list just because it fired on the latest bar.
            rows.sort(key=lambda r: (CONVICTION_RANK[r["conviction"]], r["bars_ago"], r["ticker"]))
            write_json(out_dir / strat.id / f"{tf}.json", {"updated_at": updated_at, "signals": rows})
            counts[tf] = {
                "buy": sum(r["side"] == "BUY" for r in rows),
                "sell": sum(r["side"] == "SELL" for r in rows),
            }
        # Published so the site (and a reader of the JSON) can tell which rule generation
        # produced the lists, and so a stale deploy after an algo change is detectable.
        summaries.append({"id": strat.id, "name": strat.name, "description": strat.description,
                          "chart": strat.chart, "timeframes": counts,
                          "rules_version": rules_version(strat.params),
                          "version": current_version(strat.history),
                          "history": [r.as_dict() for r in strat.history]})
    write_json(out_dir / "strategies.json", {"updated_at": updated_at, "strategies": summaries})
    write_json(out_dir / "market.json", market_payload(now))

    # Charts are written for what fired -- plus the names trader/ actually trades, which the
    # paper tab charts every day whether or not they signalled. A traded symbol missing from
    # the universe (a fetch failure) is skipped rather than fatal.
    charted = {(h.timeframe, h.ticker) for h in hits}
    charted |= {(tf, ticker) for tf in bars_by_tf for ticker in TRADED_SYMBOLS
                if ticker in bars_by_tf[tf]}
    for tf, ticker in sorted(charted):
        marks = [
            {"strategy_id": h.strategy_id, "side": h.signal.side, "bar_time": int(h.signal.bar_time.timestamp())}
            for h in hits if h.timeframe == tf and h.ticker == ticker
        ]
        write_json(out_dir / "charts" / tf / f"{ticker}.json", chart_payload(ticker, tf, bars_by_tf[tf][ticker], marks))

    store = SignalStore(db_path)
    versions = {s.id: rules_version(s.params) for s in strategies}
    inserted = store.record_signals([
        SignalRecord(h.strategy_id, h.ticker, h.timeframe, h.signal.side, h.signal.fired_at.isoformat(),
                     h.signal.entry_price, h.signal.details, updated_at, h.signal.conviction,
                     versions[h.strategy_id])
        for h in hits
    ])
    store.close()
    log.info("%d signals found, %d new recorded", len(hits), inserted)

    # Published beside the signal lists so a run that "worked" can still be inspected: a scan
    # is allowed to lose up to 10% of the universe and to have a strategy throw on individual
    # names, and until this file existed both vanished into a CI log that expires after 90 days.
    health = {
        "updated_at": updated_at,
        "duration_seconds": round(time.monotonic() - started, 1),
        "universe": len(tickers),
        "fetch": fetch_health,
        "strategy_errors": strategy_errors[:MAX_LISTED_FAILURES],
        "strategy_error_count": len(strategy_errors),
        "signals": {"found": len(hits), "recorded": inserted},
        "rules_versions": versions,
    }
    write_json(out_dir / "health.json", health)
    return {"hits": len(hits), "recorded": inserted, "health": health}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(args.out, args.db)
    except ScanError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
