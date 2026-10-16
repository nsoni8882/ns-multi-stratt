"""A plain-text status report on the lab, read from a data directory (the `data` branch's
`lab/` folder). Deterministic on purpose: the /lab skill reads this instead of improvising
its own parsing, so every review starts from the same facts.

Only development-window numbers appear. The sealed holdout is never read here -- a result's
trades are cut to the development window before they are saved -- and a strategy's holdout
line is pass or fail, never a figure.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from lab import config, stats
from lab.data import ET


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _trials(path: Path) -> "list[dict]":
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def diagnose(raw: dict) -> "list[str]":
    """Where a strategy's money went, from its saved development trades."""
    f = pd.DataFrame(**raw["trades"])
    if f.empty:
        return ["    no trades"]
    for col in ("gross", "net"):
        f[col] = f[col] * 1e4
    f["cost"] = f["gross"] - f["net"]
    f["hour"] = pd.to_datetime(f["entry_time"], utc=True).dt.tz_convert(ET).dt.hour
    out = [
        f"    per trade: gross {f['gross'].mean():+.1f} bps, costs {-f['cost'].mean():.1f} bps, "
        f"net {f['net'].mean():+.1f} bps; win rate {(f['net'] > 0).mean():.0%}; "
        f"avg hold {f['bars_held'].mean():.1f} bars",
    ]
    by = f.groupby("exit_reason")["net"].agg(["count", "mean"])
    out.append("    exits: " + "; ".join(f"{k} {int(r['count'])} ({r['mean']:+.1f})" for k, r in by.iterrows()))
    hrs = f.groupby("hour")["net"].mean()
    out.append("    by hour (ET): " + ", ".join(f"{h}:{v:+.0f}" for h, v in hrs.items()))
    sym = f.groupby("symbol")["net"].agg(["count", "mean"]).sort_values("mean")
    worst, best = sym.head(3), sym.tail(3)
    out.append("    worst symbols: " + ", ".join(f"{k} {r['mean']:+.1f}" for k, r in worst.iterrows()))
    out.append("    best symbols:  " + ", ".join(f"{k} {r['mean']:+.1f}" for k, r in best.iterrows()))
    return out


def report(data_dir: Path) -> str:
    registry = _load(data_dir / "registry.json", {})
    trials = _trials(data_dir / "trials.jsonl")
    n = len(trials)
    looks = [r for r in trials if r.get("holdout_look")]
    lines = [
        f"Intraday lab  (rules {config.rules_version()}, holdout from {config.HOLDOUT_START})",
        f"  ideas tried: {n}  passed: {sum(r['verdict'] == 'pass' for r in trials)}  "
        f"holdout looks: {len(looks)} of {config.MAX_HOLDOUT_LOOKS}",
        f"  the bar for the NEXT idea: t >= {stats.deflated_threshold(n + 1, config.BASE_T):.2f}",
        "",
    ]
    if not registry:
        lines.append("No strategies registered yet.")
    for fp, e in sorted(registry.items(), key=lambda kv: kv[1]["history"][0]["when"]):
        spec = e["spec"]
        lines += [f"[{e['stage'].upper()}] {spec['name']}  ({fp}, {spec['family']}, {spec['timeframe']})",
                  f"  hypothesis: {spec['hypothesis']}",
                  f"  params: {json.dumps(spec['params'], sort_keys=True)}  risk: {json.dumps(spec['risk'], sort_keys=True)}"]
        t = next((r for r in reversed(trials) if r.get("fingerprint") == fp), None)
        if t:
            lines.append(f"  gate: {t['verdict']}  failed: {', '.join(t['failed']) or 'none'}  "
                         f"({t['n_trades']} trades, {t['mean_bps']:+.1f} bps/day, t {t['t']:.2f} vs {t['threshold']:.2f})")
        lines.append("  history: " + " > ".join(f"{h['stage']}" for h in e["history"]))
        res = data_dir / "results" / f"{fp}.json"
        if res.exists():
            lines += diagnose(json.loads(res.read_text()))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lab.review", description=__doc__)
    ap.add_argument("--data-dir", required=True, help="the lab/ folder of the data branch")
    args = ap.parse_args(argv)
    sys.stdout.write(report(Path(args.data_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
