"""Scan the S&P 500, write site JSON, record signals. Usage: python -m scanner.run --out DIR --db FILE"""
import argparse
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scanner.data import fetch_bars
from scanner.export import chart_payload, signal_row, write_json
from scanner.market import market_payload
from scanner.store import SignalRecord, SignalStore
from scanner.strategies import STRATEGIES
from scanner.strategies.base import CONVICTION_RANK, Signal, rules_version
from scanner.universe import load_universe

TIMEFRAMES = ("4h", "1d")
MAX_FAILURE_RATE = 0.10

log = logging.getLogger("scanner")


class ScanError(RuntimeError):
    pass


@dataclass(frozen=True)
class Hit:
    strategy_id: str
    timeframe: str
    ticker: str
    signal: Signal


def scan(bars_by_tf: dict, strategies) -> "list[Hit]":
    hits = []
    for tf, bars in bars_by_tf.items():
        for ticker, df in bars.items():
            for strat in strategies:
                try:
                    sig = strat.evaluate(df)
                except Exception:
                    log.exception("%s failed on %s %s", strat.id, ticker, tf)
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

    bars_by_tf = {}
    for tf in TIMEFRAMES:
        bars_by_tf[tf], failed = fetch(tickers, tf, now)
        log.info("%s: %d fetched, %d failed", tf, len(bars_by_tf[tf]), len(failed))
        if len(failed) / len(tickers) > MAX_FAILURE_RATE:
            raise ScanError(f"{len(failed)}/{len(tickers)} tickers failed for {tf}")

    hits = scan(bars_by_tf, strategies)
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
                          "rules_version": rules_version(strat.params)})
    write_json(out_dir / "strategies.json", {"updated_at": updated_at, "strategies": summaries})
    write_json(out_dir / "market.json", market_payload(now))

    flagged = {(h.timeframe, h.ticker) for h in hits}
    for tf, ticker in sorted(flagged):
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
    return {"hits": len(hits), "recorded": inserted}


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
