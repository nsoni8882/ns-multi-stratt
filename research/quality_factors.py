"""Do quality factors from free SEC filings beat the S&P 500 universe they are drawn from?

Free, point-in-time data: the SEC's companyfacts API (every XBRL fact a company has filed, with the
filing date and form). A 10-K's numbers are used from the day after it was filed, first-reported
value only (restatements are ignored, as a live user would not have had them). Names map to CIKs
through the Form 4 filings already cached for the insider test.

Declared 2026-10-17 before any number existed.

Two factors, from the latest 10-K filed within the previous 15 months, computed as of each month-end:
  profitability -- gross profit / total assets (Novy-Marx), gross profit = GrossProfit, else revenue
                   less cost of revenue. High is good.
  accruals      -- (net income - operating cash flow) / total assets (Sloan). Low is good.
Each month: among S&P 500 members that day with the factor and a next-month price, hold the best
quintile equal weight for one month. Excess return = that quintile less the equal-weight average of
all names with the factor that month. Long only (nothing here shorts); the long-short spread is
printed for information and decides nothing. Cost: 11 bps on the traded fraction each month
(5.5 bps a side), taken from the measured turnover.

Bar, on the long-only monthly excess return net of cost. All must hold:
  1. mean excess positive after cost
  2. Newey-West (3 lags) t >= 2.5
  3. positive in both halves
  4. positive with the best calendar year removed
  5. at least 100 months
Coverage (names with the factor / members) is reported: financials have no gross profit.
"""
import argparse
import json
import logging
import time
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from research import pit
from research.insider_events import CACHE as INSIDER_CACHE
from research.measure import RESULTS_DIR, fetch_history

log = logging.getLogger("quality_factors")
FACTS = Path(__file__).parent / ".cache" / "sec_facts"
UA = "NS-Multi-Stratt research nikunj.sap@gmail.com"
COST_PER_SIDE = 0.00055
REVENUE = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
           "RevenueFromContractWithCustomerIncludingAssessedTax"]
COGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]
CFO = ["NetCashProvidedByUsedInOperatingActivities"]


def cik_map() -> "dict[str, str]":
    """Symbol -> CIK from the Form 4 submissions (most frequent CIK per symbol)."""
    seen: "dict[str, Counter]" = {}
    for p in sorted(INSIDER_CACHE.glob("*_form345.zip")):
        with zipfile.ZipFile(p) as z, z.open("SUBMISSION.tsv") as f:
            d = pd.read_csv(f, sep="\t", usecols=["ISSUERCIK", "ISSUERTRADINGSYMBOL"], dtype=str)
        for c, s in zip(d["ISSUERCIK"], d["ISSUERTRADINGSYMBOL"]):
            if isinstance(s, str) and isinstance(c, str):
                seen.setdefault(s.upper().strip().replace(".", "-"), Counter())[c] += 1
    return {s: c.most_common(1)[0][0] for s, c in seen.items()}


def fetch_facts(cik: str) -> "dict | None":
    path = FACTS / f"{cik}.json"
    if path.exists():
        return json.loads(path.read_text()) if path.stat().st_size > 2 else None
    FACTS.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",
                                 headers={"User-Agent": UA})
    try:
        body = urllib.request.urlopen(req, timeout=30).read()
        data = json.loads(body)
    except Exception:
        path.write_text("{}")
        return None
    path.write_text(json.dumps(data))
    time.sleep(0.15)  # the SEC allows 10 requests a second; stay well under
    return data


def _annual(facts: dict, tags: "list[str]") -> "dict[str, tuple[float, str, str]]":
    """accession -> (value, period end, filed) for ~12-month 10-K values, first tag that has any."""
    for tag in tags:
        rows = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
        out = {}
        for r in rows:
            if r.get("form") != "10-K" or "start" not in r:
                continue
            days = (pd.Timestamp(r["end"]) - pd.Timestamp(r["start"])).days
            if 350 <= days <= 380 and r["accn"] not in out:
                out[r["accn"]] = (float(r["val"]), r["end"], r["filed"])
        if out:
            return out
    return {}


def _assets(facts: dict) -> "dict[str, float]":
    rows = facts.get("facts", {}).get("us-gaap", {}).get("Assets", {}).get("units", {}).get("USD", [])
    return {r["accn"]: float(r["val"]) for r in rows if r.get("form") == "10-K" and "start" not in r}


def annual_features(facts: dict) -> pd.DataFrame:
    """One row per 10-K: filed date, gross profitability and accruals (NaN where not computable)."""
    assets, rev, cogs, ni, cfo = _assets(facts), _annual(facts, REVENUE), _annual(facts, COGS), \
        _annual(facts, ["NetIncomeLoss"]), _annual(facts, CFO)
    gp = _annual(facts, ["GrossProfit"])
    rows = []
    for accn, a in assets.items():
        base = (rev.get(accn) or gp.get(accn) or ni.get(accn) or (0, None, None))
        if base[2] is None or a <= 0:
            continue
        g = gp[accn][0] if accn in gp else (rev[accn][0] - cogs[accn][0] if accn in rev and accn in cogs else np.nan)
        acc = (ni[accn][0] - cfo[accn][0]) / a if accn in ni and accn in cfo else np.nan
        rows.append((pd.Timestamp(base[2]), g / a if g == g else np.nan, acc))
    return pd.DataFrame(rows, columns=["filed", "profitability", "accruals"]).sort_values("filed")


def monthly_excess(features: "dict[str, pd.DataFrame]", close: pd.DataFrame, member: pd.DataFrame, factor: str,
                   best_high: bool) -> pd.DataFrame:
    rows, prev = [], set()
    month_close = close.resample("ME").last()
    for i in range(len(month_ends := list(month_close.index)) - 1):
        t, nxt = month_ends[i], month_ends[i + 1]
        asof = t.tz_localize(None) if t.tzinfo else t
        vals = {}
        for s, f in features.items():
            if s not in member.columns or not bool(member[s].reindex([close.index[close.index <= t][-1]]).fillna(False).iloc[0]):
                continue
            ok = f[(f["filed"] < asof) & (f["filed"] > asof - pd.Timedelta(days=455))]
            if ok.empty or pd.isna(ok.iloc[-1][factor]):
                continue
            r = month_close[s].iloc[i + 1] / month_close[s].iloc[i] - 1.0 if s in month_close.columns else np.nan
            if r == r:
                vals[s] = (float(ok.iloc[-1][factor]), float(r))
        if len(vals) < 50:
            continue
        df = pd.DataFrame(vals, index=["f", "r"]).T
        k = max(len(df) // 5, 1)
        top = df.sort_values("f", ascending=not best_high).head(k)
        bot = df.sort_values("f", ascending=best_high).head(k)
        held = set(top.index)
        turn = 1.0 if not prev else len(held - prev) / len(held)
        prev = held
        rows.append((nxt, top["r"].mean() - df["r"].mean() - 2 * COST_PER_SIDE * turn,
                     top["r"].mean() - bot["r"].mean(), len(df)))
    return pd.DataFrame(rows, columns=["month", "excess", "spread", "names"]).set_index("month")


def nw_t(x: pd.Series, lags: int = 3) -> float:
    """t-statistic of the mean with Newey-West (Bartlett) standard errors."""
    u = x.to_numpy() - x.mean()
    var = u @ u / len(u)
    for k in range(1, lags + 1):
        var += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / len(u)
    return float(x.mean() / np.sqrt(var / len(u)))


def summarize(m: pd.DataFrame) -> dict:
    x = m["excess"]
    t = nw_t(x)
    mid = x.index[len(x) // 2]
    yr = x.groupby(x.index.year).mean()
    best = int(yr.idxmax())
    return {"months": len(x), "mean_m": float(x.mean()), "t": float(t), "first": float(x[:mid].mean()),
            "second": float(x[mid:].mean()), "best_year": best, "without_best": float(x[x.index.year != best].mean()),
            "spread_m": float(m["spread"].mean()), "names": float(m["names"].mean()),
            "by_year": {int(y): float(v) for y, v in yr.items()}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "quality")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    member = pit.load()
    bars = fetch_history(sorted(member.columns), 12, pd.Timestamp.now(tz="UTC"))
    close = pd.DataFrame({t: df["close"] for t, df in bars.items()}).sort_index()
    ciks = cik_map()
    feats, miss = {}, 0
    for i, s in enumerate(sorted(bars)):
        c = ciks.get(s)
        facts = fetch_facts(c) if c else None
        if not facts:
            miss += 1
            continue
        f = annual_features(facts)
        if len(f):
            feats[s] = f
        if i % 100 == 0:
            log.info("facts %d/%d", i, len(bars))
    log.info("%d symbols with features, %d without a CIK or facts", len(feats), miss)
    lines = ["# Quality factors on free SEC filings, point-in-time S&P 500", "",
             f"{len(feats)} of {len(bars)} priced symbols had parseable 10-K facts. Long-only top quintile, "
             "monthly, excess over the equal-weight universe, net of cost.", ""]
    for label, factor, high in (("profitability (gross profit / assets, high)", "profitability", True),
                                ("accruals (low)", "accruals", False)):
        m = monthly_excess(feats, close, member, factor, high)
        if len(m) < 24:
            lines += [f"## {label}", "", f"- only {len(m)} months", ""]
            continue
        s = summarize(m)
        lines += [f"## {label}", "", f"- {s['months']} months, ~{s['names']:.0f} names a month, excess {s['mean_m']*12:+.1%}/yr, "
                  f"NW t {s['t']:+.2f}", f"- first half {s['first']*12:+.1%}/yr, second half {s['second']*12:+.1%}/yr",
                  f"- without {s['best_year']}: {s['without_best']*12:+.1%}/yr",
                  f"- long-short spread (information only): {s['spread_m']*12:+.1%}/yr", "",
                  "| year | " + " | ".join(map(str, s["by_year"])) + " |", "|---|" + "---:|" * len(s["by_year"]),
                  "| excess/yr | " + " | ".join(f"{v*12:+.1%}" for v in s["by_year"].values()) + " |", ""]
        log.info("%s: %.1f%%/yr t %.2f", label, s["mean_m"] * 1200, s["t"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "quality.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
