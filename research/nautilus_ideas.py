"""Two textbook trend rules from the Nautilus Trader examples, on the point-in-time S&P 500.

Declared 2026-10-21 before any number existed. Nautilus ships an EMA-cross strategy and an
indicator library with Donchian channels; neither is a researched edge, so each gets one look.

Rules, one each, no variants and no tuning after the fact:
  ema  -- long while EMA(10) > EMA(20) of the close (the Nautilus EMACross defaults), else cash.
  dch  -- long after a close above the prior 20-day high, flat after a close below the prior
          10-day low (Donchian 20/10), else hold the last state.
The state is read at yesterday's close and earns today's return. Cost 5.5 bps per round trip
(2.75 bps a switch), the figure used everywhere else in this tree. A name counts on a day only
if it was an index member that day (`research/pit.py`).

The portfolio is equal weight over the members with a price that day; a flat name earns 0. It is
compared with the equal-weight hold of the same members, by regression with Newey-West errors,
because a trend rule is mostly less market exposure and only the intercept is an edge.

Bar. All must hold, on daily alpha net of cost:
  1. alpha positive and t >= 2.5
  2. alpha positive in both halves of the sample
  3. alpha positive with the best calendar year removed
  4. alpha positive with 2020 removed (the one crash in the sample)
Failing 1 ends it. Passing means an overlay-or-edge worth a second look, not a shipped strategy:
the survivorship hole `pit.coverage` reports still flatters anything long.
"""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from research import pit
from research.measure import RESULTS_DIR, fetch_history
from research.trend_etf import alpha_beta, max_dd, sharpe

log = logging.getLogger("nautilus_ideas")
SWITCH_COST = 0.00055 / 2


def state_ema(df: pd.DataFrame) -> pd.Series:
    c = df["close"]
    return c.ewm(span=10, adjust=False).mean() > c.ewm(span=20, adjust=False).mean()


def state_dch(df: pd.DataFrame) -> pd.Series:
    c = df["close"]
    up = c > c.shift(1).rolling(20).max()
    down = c < c.shift(1).rolling(10).min()
    s = pd.Series(np.nan, index=c.index)
    s[up] = 1.0
    s[down & ~up] = 0.0
    return s.ffill().fillna(0.0).astype(bool)


RULES = {"ema": state_ema, "dch": state_dch}


def returns(close: pd.DataFrame, bars: "dict[str, pd.DataFrame]", rule: str) -> pd.DataFrame:
    """Daily strategy return per name; NaN before the rule has warmed up (200 bars)."""
    out = {}
    for t, df in bars.items():
        on = RULES[rule](df).shift(1, fill_value=False).astype(float)
        sw = on.diff().abs().fillna(0.0)
        r = df["close"].pct_change() * on - sw * SWITCH_COST
        out[t] = r.where(df["close"].rolling(200).mean().shift(1).notna())
    return pd.DataFrame(out).reindex(close.index)


def portfolio(strat: pd.DataFrame, hold: pd.DataFrame, member: pd.DataFrame) -> "tuple[pd.Series, pd.Series]":
    m = member.reindex(index=strat.index, columns=strat.columns).fillna(False).astype(bool)
    ok = m & strat.notna() & hold.notna()
    return strat.where(ok).mean(axis=1).dropna(), hold.where(ok).mean(axis=1).dropna()


def block(s: pd.Series, b: pd.Series) -> dict:
    a, beta, t = alpha_beta(s, b)
    return {"alpha_ann": a * 252, "beta": beta, "t": t, "sharpe": sharpe(s), "bench_sharpe": sharpe(b),
            "max_dd": max_dd(s), "bench_max_dd": max_dd(b), "ret": float(s.mean() * 252),
            "bench_ret": float(b.mean() * 252)}


def evaluate(s: pd.Series, b: pd.Series) -> dict:
    mid = s.index[len(s) // 2]
    yr = s.index.year
    per_year = {int(y): alpha_beta(s[yr == y], b[yr == y])[0] * 252 for y in sorted(set(yr))}
    best = max(per_year, key=per_year.get)
    return {"all": block(s, b), "first_half": block(s[:mid], b[:mid]), "second_half": block(s[mid:], b[mid:]),
            "without_best_year": block(s[yr != best], b[yr != best]), "best_year": best,
            "without_2020": block(s[yr != 2020], b[yr != 2020]), "by_year": per_year,
            "span": [str(s.index[0].date()), str(s.index[-1].date())]}


def verdict(ev: dict) -> "tuple[bool, list[str]]":
    checks = {"alpha>0 and t>=2.5": ev["all"]["alpha_ann"] > 0 and ev["all"]["t"] >= 2.5,
              "both halves positive": ev["first_half"]["alpha_ann"] > 0 and ev["second_half"]["alpha_ann"] > 0,
              "positive without best year": ev["without_best_year"]["alpha_ann"] > 0,
              "positive without 2020": ev["without_2020"]["alpha_ann"] > 0}
    return all(checks.values()), [f"{'PASS' if v else 'FAIL'} {k}" for k, v in checks.items()]


def fmt(b: dict) -> str:
    return (f"alpha {b['alpha_ann']:+.1%}/yr (t {b['t']:+.2f}), beta {b['beta']:.2f}, Sharpe {b['sharpe']:.2f} vs "
            f"{b['bench_sharpe']:.2f}, max DD {b['max_dd']:.1%} vs {b['bench_max_dd']:.1%}, "
            f"return {b['ret']:.1%} vs {b['bench_ret']:.1%}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "nautilus-ideas")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    member = pit.load()
    bars = fetch_history(sorted(member.columns), 12, pd.Timestamp.now(tz="UTC"))
    close = pd.DataFrame({t: d["close"] for t, d in bars.items()})
    hold = close.pct_change()
    cov = pit.coverage(member, close)
    log.info("%d names with prices; coverage by year %s", close.shape[1], {y: round(v, 2) for y, v in cov.items()})
    lines = ["# Nautilus example rules on the point-in-time S&P 500", "",
             f"Price coverage of member-days by year: {', '.join(f'{y} {v:.0%}' for y, v in cov.items())}", ""]
    for rule in RULES:
        s, b = portfolio(returns(close, bars, rule), hold, member)
        ev = evaluate(s, b)
        ok, checks = verdict(ev)
        lines += [f"## {rule}: {'PASSES' if ok else 'FAILS'} ({ev['span'][0]} to {ev['span'][1]})", ""]
        lines += [f"- {k}: {fmt(ev[k])}" for k in ("all", "first_half", "second_half", "without_best_year", "without_2020")]
        lines += [f"- best year: {ev['best_year']}", f"- by year (alpha/yr): "
                  + ", ".join(f"{y} {a:+.1%}" for y, a in ev["by_year"].items()), ""] + [f"- {c}" for c in checks] + [""]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "nautilus_ideas.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
