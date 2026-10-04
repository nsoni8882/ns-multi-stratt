"""Measure relative-strength variants over the same 12 years as research/measure.py.

Usage:
    python -m research.measure_cross --tickers 165 --years 12 --horizon 20

Reuses measure.py's data cache, its per-ticker baseline, its overlap thinning and its stats,
and adds the one guard a ranked rule needs on top: the date-collapsed t-stat from
research/cross.py. Writes research/results/relative_strength.md.
"""
import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from research import cross
from research.measure import RESULTS_DIR, fetch_history, independent, pick_tickers, stats

log = logging.getLogger("measure_cross")


def summarise(rows: "list[cross.CrossRow]", horizon: int) -> dict:
    s = stats(rows, horizon, "BUY") if rows else {"n": 0}
    return s | cross.date_collapsed(rows)


def by_year(rows: "list[cross.CrossRow]") -> "dict[int, float]":
    years: "dict[int, list[float]]" = {}
    for r in rows:
        years.setdefault(r.year, []).append(r.fwd - r.baseline)
    return {y: float(np.mean(v)) for y, v in sorted(years.items())}


def measure(panel: cross.Panel, labels: "list[str]", horizon: int) -> dict:
    out = {}
    for label in labels:
        cfg = cross.VARIANTS[label]
        rows = cross.score(panel, cfg, horizon)
        first, second = cross.halves(rows)
        dropped_year, without = cross.drop_best_year(rows)
        out[label] = {
            "all": summarise(rows, horizon),
            "first_half": summarise(first, horizon),
            "second_half": summarise(second, horizon),
            "dropped_year": dropped_year,
            "without_best_year": summarise(without, horizon),
            "by_year": by_year(rows),
            "names": len({r.ticker for r in rows}),
        }
        log.info("%s: %d signals on %d dates, alpha %.4f t_date %.2f", label, out[label]["all"]["n"],
                 out[label]["all"]["n_dates"], out[label]["all"].get("alpha", float("nan")),
                 out[label]["all"]["t_by_date"])
    return out


HEADER = ("| variant | n | n dates | names | alpha | **alpha by date** | **t by date** | "
          "t indep | win % |")
DIVIDER = "|---|---:|---:|---:|---:|---:|---:|---:|---:|"


def _row(label: str, s: dict) -> str:
    if not s.get("n"):
        return f"| {label} | 0 | | | | | | | |"
    return (f"| {label} | {s['n']:,} | {s['n_dates']:,} | {s.get('names', '')} | "
            f"{s['alpha']:+.2%} | **{s['alpha_by_date']:+.2%}** | **{s['t_by_date']:+.2f}** | "
            f"{s['t_independent']:+.2f} | {s['win']:.1%} |")


def to_markdown(results: dict, meta: dict) -> str:
    years = sorted({y for r in results.values() for y in r["by_year"]})
    lines = [
        "# Relative Strength (cross-sectional momentum) variant measurement",
        "",
        f"{meta['tickers']} S&P names, {meta['years']}y of daily bars, {meta['horizon']}-bar "
        f"forward horizon, alpha per ticker against buy-and-hold. Generated {meta['generated']}.",
        "",
        "**`t by date` is the number that decides this.** A ranked rule flags many names on "
        "the same morning and those names move together, so every signal from one date is "
        "averaged into one observation before the t-stat (ACCEPTANCE.md rule 7). `t indep` "
        "is the per-ticker thinning the other strategies use, shown for comparison; where "
        "the two disagree the date-collapsed one is right.",
        "",
        HEADER, DIVIDER,
    ]
    for label, r in results.items():
        lines.append(_row(label, r["all"] | {"names": r["names"]}))

    lines += ["", "## Sub-period split, by calendar date", "",
              "Every name shares one timeline here, so the split is by date, not per ticker.",
              "", HEADER, DIVIDER]
    for label, r in results.items():
        lines.append(_row(f"{label} (first half)", r["first_half"]))
        lines.append(_row(f"{label} (second half)", r["second_half"]))

    lines += ["", "## With the best year removed (ACCEPTANCE rule 4)", "", HEADER, DIVIDER]
    for label, r in results.items():
        lines.append(_row(f"{label} (without {r['dropped_year']})", r["without_best_year"]))

    lines += ["", "## Per-year alpha", "",
              "| variant | " + " | ".join(str(y) for y in years) + " |",
              "|---|" + "---:|" * len(years)]
    for label, r in results.items():
        cells = [f"{r['by_year'][y]:+.2%}" if y in r["by_year"] else "" for y in years]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", type=int, default=165)
    parser.add_argument("--years", type=int, default=12)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--variants", nargs="*", default=None)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    labels = args.variants or list(cross.VARIANTS)
    unknown = [v for v in labels if v not in cross.VARIANTS]
    if unknown:
        parser.error(f"unknown variants {unknown}; available: {list(cross.VARIANTS)}")

    now = pd.Timestamp.now(tz="UTC")
    bars = fetch_history(pick_tickers(args.tickers), args.years, now)
    usable = {t: df for t, df in bars.items() if len(df) > cross.WARMUP + args.horizon}
    log.info("%d tickers, %d usable", len(bars), len(usable))
    if not usable:
        log.error("no usable history")
        return 1

    panel = cross.build_panel(usable)
    log.info("panel %d dates x %d tickers", len(panel.close), len(panel.close.columns))
    results = measure(panel, labels, args.horizon)
    meta = {"tickers": len(usable), "years": args.years, "horizon": args.horizon,
            "generated": now.strftime("%Y-%m-%d")}

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "relative_strength.md").write_text(to_markdown(results, meta))
    (args.out / "relative_strength.json").write_text(json.dumps({"meta": meta, "results": results},
                                                                indent=2, default=str))
    print(to_markdown(results, meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
