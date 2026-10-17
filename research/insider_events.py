"""Do open-market insider purchases predict returns in S&P 500 names?

Free, point-in-time data: the SEC's Insider Transactions Data Sets (Form 4, quarterly bulk files,
`research/.cache/sec_insider/`). A purchase is known to the market on its *filing* date, so the
earliest entry is the close of the first trading day after the filing date (filings land after the
close as often as before it). The Hermes funnel reads these same filings per ticker for one score
bonus; this measures the signal on its own, across the point-in-time S&P 500.

Declared 2026-10-17 before any number existed.

A purchase: Form 4 (not 4/A), transaction code P (open-market buy), acquired, by an officer or
director (not a 10%-owner alone). Per filing and owner the shares x price are summed.
Variants, four and no more (two definitions x two horizons):
  single  -- any such purchase of at least $100,000 by one insider. Signal on its filing date.
  cluster -- at least two different insiders each buying at least $25,000 within 30 calendar days.
             Signal on the filing date of the second.
  A ticker re-signals only after the horizon has run out. Horizons: 20 and 60 trading days.

Alpha: the forward return from the entry close, less the name's own mean forward return over the
same horizon, less 5.5 bps of cost. Universe: names that were S&P 500 members on the signal date
(`research/pit.py`) with Yahoo prices.

Bar. Decisive number is trade-weighted alpha with a t-statistic clustered by calendar month
(insider buying clusters in selloffs, and a mean of monthly means would over-weight quiet months,
the mistake the RSI(2) test made). All must hold:
  1. alpha positive after cost
  2. clustered t >= 2.5
  3. positive in both halves of the sample
  4. positive with the best calendar year removed
  5. at least 300 signals
"""
import argparse
import io
import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research import pit
from research.measure import RESULTS_DIR, fetch_history

log = logging.getLogger("insider_events")
CACHE = Path(__file__).parent / ".cache" / "sec_insider"
COST = 0.00055
VARIANTS = {"single-20": ("single", 20), "single-60": ("single", 60),
            "cluster-20": ("cluster", 20), "cluster-60": ("cluster", 60)}


def _read(z: zipfile.ZipFile, name: str, cols: "list[str]") -> pd.DataFrame:
    with z.open(name) as f:
        return pd.read_csv(f, sep="\t", usecols=cols, dtype=str, low_memory=False)


def parse(zip_path: Path) -> pd.DataFrame:
    """Officer or director open-market purchases from one quarterly file: one row per
    (accession, owner) with the filing date, ticker and total dollar value."""
    with zipfile.ZipFile(zip_path) as z:
        sub = _read(z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERTRADINGSYMBOL"])
        trn = _read(z, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_SHARES",
                                              "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
        own = _read(z, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
    return buys(sub, trn, own)


def buys(sub: pd.DataFrame, trn: pd.DataFrame, own: pd.DataFrame) -> pd.DataFrame:
    sub = sub[(sub["DOCUMENT_TYPE"] == "4") & sub["ISSUERTRADINGSYMBOL"].notna()]
    trn = trn[(trn["TRANS_CODE"] == "P") & (trn["TRANS_ACQUIRED_DISP_CD"] == "A")].copy()
    trn["value"] = pd.to_numeric(trn["TRANS_SHARES"], errors="coerce") * pd.to_numeric(
        trn["TRANS_PRICEPERSHARE"], errors="coerce")
    trn = trn.groupby("ACCESSION_NUMBER", as_index=False)["value"].sum()
    rel = own["RPTOWNER_RELATIONSHIP"].fillna("")
    own = own[rel.str.contains("Officer|Director", case=False)]
    out = sub.merge(trn, on="ACCESSION_NUMBER").merge(own[["ACCESSION_NUMBER", "RPTOWNERCIK"]], on="ACCESSION_NUMBER")
    out["filed"] = pd.to_datetime(out["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
    out["ticker"] = out["ISSUERTRADINGSYMBOL"].str.upper().str.strip().str.replace(".", "-", regex=False)
    return out.dropna(subset=["filed", "value"])[["ticker", "filed", "RPTOWNERCIK", "value"]]


def load_all(cache: Path = CACHE) -> pd.DataFrame:
    parts = [parse(p) for p in sorted(cache.glob("*_form345.zip"))]
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def signal_dates(events: pd.DataFrame, kind: str) -> pd.DataFrame:
    """(ticker, filed) of each signal, before the re-signal lockout."""
    if kind == "single":
        s = events[events["value"] >= 100_000].groupby(["ticker", "filed"], as_index=False).size()
        return s[["ticker", "filed"]]
    e = events[events["value"] >= 25_000].sort_values("filed")
    rows = []
    for t, g in e.groupby("ticker"):
        f, o = g["filed"].to_numpy(), g["RPTOWNERCIK"].to_numpy()
        for i in range(len(g)):
            window = (f >= f[i] - np.timedelta64(30, "D")) & (f <= f[i])
            if len(set(o[window])) >= 2:  # repeats inside one cluster are removed by the re-signal lockout
                rows.append((t, f[i]))
    return pd.DataFrame(rows, columns=["ticker", "filed"]).drop_duplicates()


def score(sig: pd.DataFrame, bars: "dict[str, pd.DataFrame]", member: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Entry at the close of the first trading day after the filing date; alpha net of drift and cost."""
    rows = []
    for t, g in sig.groupby("ticker"):
        if t not in bars or t not in member.columns:
            continue
        close = bars[t]["close"]
        idx = close.index.tz_localize(None) if close.index.tz is not None else close.index
        fwd = (close.shift(-horizon) / close - 1.0).to_numpy()
        base = float(np.nanmean(fwd))
        last = -10**9
        for filed in sorted(g["filed"]):
            i = int(idx.searchsorted(filed, side="right"))  # first bar strictly after the filing date
            if i >= len(close) - horizon or i < last + horizon or np.isnan(fwd[i]):
                continue
            if not bool(member[t].reindex([close.index[i]]).fillna(False).iloc[0]):
                continue
            rows.append((t, close.index[i], fwd[i] - base - COST))
            last = i
    return pd.DataFrame(rows, columns=["ticker", "entry", "alpha"])


def cluster_t(tr: pd.DataFrame) -> dict:
    """Trade-weighted mean alpha, t clustered by calendar month of entry."""
    if len(tr) < 2:
        return {"n": len(tr), "alpha": float("nan"), "t": float("nan")}
    m = tr["alpha"].mean()
    g = (tr["alpha"] - m).groupby(tr["entry"].dt.tz_localize(None).dt.to_period("M")).sum()
    se = np.sqrt((g ** 2).sum()) / len(tr)
    return {"n": len(tr), "alpha": float(m), "t": float(m / se) if se > 0 else float("nan")}


def evaluate(tr: pd.DataFrame) -> dict:
    mid = tr["entry"].sort_values().iloc[len(tr) // 2]
    yr = tr["entry"].dt.year
    best = int(tr.groupby(yr)["alpha"].mean().idxmax())
    return {"all": cluster_t(tr), "first_half": cluster_t(tr[tr["entry"] < mid]),
            "second_half": cluster_t(tr[tr["entry"] >= mid]), "best_year": best,
            "without_best_year": cluster_t(tr[yr != best]),
            "by_year": {int(y): float(v) for y, v in tr.groupby(yr)["alpha"].mean().items()}}


def fmt(s: dict) -> str:
    return f"{s['n']:,} signals, alpha {s['alpha']:+.2%}, clustered t {s['t']:+.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "insider")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    events = load_all()
    log.info("%d officer/director purchases, %s to %s", len(events), events["filed"].min().date(), events["filed"].max().date())
    member = pit.load()
    bars = fetch_history(sorted(member.columns), 12, pd.Timestamp.now(tz="UTC"))
    lines = ["# Insider open-market purchases, point-in-time S&P 500", "",
             f"{len(events):,} officer/director purchases filed {events['filed'].min().date()} to "
             f"{events['filed'].max().date()}; {len(bars)} symbols with prices. Alpha net of drift and 5.5 bps.", ""]
    for label, (kind, horizon) in VARIANTS.items():
        tr = score(signal_dates(events, kind), bars, member, horizon)
        if len(tr) < 20:
            lines += [f"## {label}", "", f"- only {len(tr)} signals", ""]
            continue
        ev = evaluate(tr)
        lines += [f"## {label}", "", f"- all: {fmt(ev['all'])}", f"- first half: {fmt(ev['first_half'])}",
                  f"- second half: {fmt(ev['second_half'])}", f"- without {ev['best_year']}: {fmt(ev['without_best_year'])}", "",
                  "| year | " + " | ".join(map(str, ev["by_year"])) + " |", "|---|" + "---:|" * len(ev["by_year"]),
                  "| alpha | " + " | ".join(f"{v:+.1%}" for v in ev["by_year"].values()) + " |", ""]
        log.info("%s: %s", label, fmt(ev["all"]))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "insider.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
