"""Command line for the lab. `fetch` pulls bars and freezes the universe; `backtest` runs a
spec through the gate (and appends the trial); `export` writes lab.json. Nothing here trades."""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import time

from lab import backtest, data, export, gate, lifecycle, trials, universe
from lab.lifecycle import Registry
from lab.spec import Spec, SpecError
from lab.trials import Ledger

HERE = Path(__file__).parent
MEMBERSHIP = HERE / ".cache" / "membership.json"
RESULTS = HERE / "results"
YEARS_BACK = 8


PACE = 0.35  # seconds between calls: well inside Alpaca's 200 requests a minute
RETRIES = 6


class Paced:
    """The Alpaca client with a pause between calls and a backoff on HTTP 429, because a full
    fetch is some 1,500 requests and the plain client has neither."""

    def __init__(self, client, pace: float = PACE, sleep=time.sleep):
        self._c, self._pace, self._sleep = client, pace, sleep

    def _go(self, fn, *a):
        from trader.alpaca import AlpacaError
        for attempt in range(RETRIES):
            self._sleep(self._pace)
            try:
                return fn(*a)
            except AlpacaError as e:
                if e.status != 429 or attempt == RETRIES - 1:
                    raise
                self._sleep(2 ** attempt)

    def bars(self, *a):
        return self._go(self._c.bars, *a)

    def calendar(self, *a):
        return self._go(self._c.calendar, *a)


def _client():
    from trader.alpaca import Alpaca
    return Paced(Alpaca(os.environ["ALPACA_KEY_ID"], os.environ["ALPACA_SECRET_KEY"]))


def configure(data_dir: "str | None") -> None:
    """Keep the registry, the trial ledger, results and the frozen universe in `data_dir`
    (on the `data` branch in CI) instead of the working tree, so the ledger outlives a run."""
    global RESULTS, MEMBERSHIP
    if not data_dir:
        return
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    lifecycle.DEFAULT, trials.DEFAULT = d / "registry.json", d / "trials.jsonl"
    RESULTS, MEMBERSHIP = d / "results", d / "membership.json"


def _start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=365 * YEARS_BACK)


def cmd_fetch(args) -> int:
    from scanner.universe import load_universe
    client, start = _client(), _start()
    daily = {}
    for sym in load_universe()["ticker"]:
        raw = client.bars(sym.replace("-", "."), "1Day", start, datetime.now(timezone.utc))
        if raw:
            f = data.to_frame(raw)
            daily[sym] = (f["close"] * f["volume"]).rename(sym)
    dv = pd.DataFrame(daily)
    dv.index = dv.index.tz_localize(None)
    membership = universe.freeze(dv)
    MEMBERSHIP.parent.mkdir(parents=True, exist_ok=True)
    MEMBERSHIP.write_text(json.dumps({str(k): v for k, v in membership.items()}))
    symbols = universe.allowed_years(membership)
    for sym in symbols:
        data.get(client, sym.replace("-", "."), "5Min", start)
    print(f"universe {universe.version(membership)}: {len(symbols)} symbols")
    return 0


def _membership() -> dict:
    return {int(k): v for k, v in json.loads(MEMBERSHIP.read_text()).items()}


def _frames(spec, membership):
    client, start = _client(), _start()
    return {s: data.get(client, s.replace("-", "."), spec.timeframe, start)
            for s in universe.allowed_years(membership)}


def cmd_backtest(args) -> int:
    try:
        spec = Spec.from_dict(json.loads(Path(args.spec).read_text()))
    except SpecError as e:
        print(f"invalid spec: {e}", file=sys.stderr)
        return 2
    membership = _membership()
    frames = _frames(spec, membership)
    tiers, allowed = universe.tiers_from(membership), universe.allowed_years(membership)
    reg, ledger = Registry(), Ledger()
    if spec.fingerprint() in reg.all():
        print(f"{spec.fingerprint()} is already {reg.get(spec.fingerprint())['stage']}", file=sys.stderr)
        return 2
    try:
        res = gate.evaluate(spec, frames, tiers, allowed, ledger)
    except gate.AlreadyTried as e:
        print(e, file=sys.stderr)
        return 2
    # Only now that a verdict and its ledger row exist is the spec registered, so a crash in
    # the gate never strands a fingerprint in `proposed`.
    fp = reg.register(spec)
    reg.advance(fp, "backtested", reason="gate evaluated")
    if not res.passed:
        reg.advance(fp, "rejected", reason="failed: " + ", ".join(c.name for c in res.checks if not c.ok))
    full = backtest.run(spec, frames, tiers, allowed=allowed).before(data.dev_cutoff())
    curve = full.equity_curve()
    curve["t"] = curve["t"].astype(str)  # dates, not epoch milliseconds, in lab.json
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{fp}.json").write_text(json.dumps({
        "metrics": res.metrics, "trades": json.loads(full.frame().to_json(orient="split", date_format="iso")),
        "equity": json.loads(curve.to_json(orient="split"))}))
    for c in res.checks:
        print(f"{'PASS' if c.ok else 'FAIL'}  {c.name:<20} {c.detail}")
    print("VERDICT:", "pass -> eligible for shadow" if res.passed else "rejected", f"[{fp}]")
    return 0


def cmd_export(args) -> int:
    reg, ledger = Registry().all(), Ledger().read()
    results = {}
    for fp in reg:
        p = RESULTS / f"{fp}.json"
        if p.exists():
            raw = json.loads(p.read_text())
            trades = pd.DataFrame(**raw["trades"])
            for col in ("entry_time", "exit_time"):
                trades[col] = pd.to_datetime(trades[col], utc=True)
            trades["day"] = [t.tz_convert(data.ET).date() for t in trades["entry_time"]]
            results[fp] = {"metrics": raw["metrics"], "trades": trades,
                           "equity": pd.DataFrame(**raw["equity"])}
    mem = _membership() if MEMBERSHIP.exists() else {}
    doc = export.build(reg, ledger, results, universe_version=universe.version(mem) if mem else "none",
                       generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    export.write(args.out, doc)
    print(f"wrote {args.out}: {len(doc['strategies'])} strategies, {len(doc['trades'])} trades")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lab.run", description=__doc__)
    ap.add_argument("--data-dir", help="keep ledger, registry, results and universe here")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="freeze the universe and cache 5-minute bars").set_defaults(fn=cmd_fetch)
    b = sub.add_parser("backtest", help="run a spec through the gate")
    b.add_argument("spec")
    b.set_defaults(fn=cmd_backtest)
    e = sub.add_parser("export", help="write lab.json")
    e.add_argument("--out", default="lab.json")
    e.set_defaults(fn=cmd_export)
    args = ap.parse_args(argv)
    configure(args.data_dir)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
