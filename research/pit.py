"""Point-in-time S&P 500 membership, so a cross-section only ranks names that were in the index
on that date.

`research/.cache/sp500_hist.csv` is fja05680/sp500's "Historical Components & Changes (Updated)"
(date, comma-joined tickers; a name that later left carries a `-YYYYMM` suffix). The cache is
gitignored; `fetch_membership` re-pulls it with `gh`.

What this fixes and what it does not: it removes the bias of ranking only today's survivors
against each other. It cannot recover prices Yahoo no longer serves, and those are
disproportionately the names that were acquired or went bankrupt, so `coverage` is reported next
to every result and the remaining bias still flatters buying losers.
"""
import re
import subprocess
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).parent / ".cache" / "sp500_hist.csv"
_SUFFIX = re.compile(r"-\d{6}$")
_FILE = "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"


def fetch_membership(path: Path = CACHE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = subprocess.run(["gh", "api", f"repos/fja05680/sp500/contents/{_FILE}", "-H",
                          "Accept: application/vnd.github.raw"], check=True, capture_output=True)
    path.write_bytes(raw.stdout)
    return path


def symbol(raw: str) -> str:
    """Strip the delisting suffix and use Yahoo's share-class spelling (BRK.B -> BRK-B)."""
    return _SUFFIX.sub("", raw.strip()).replace(".", "-")


def load(path: Path = CACHE, since: str = "2013-01-01") -> pd.DataFrame:
    """Dates x symbols, True where the name was a member that day. Snapshots are on change
    dates, so each is held forward until the next one."""
    if not path.exists():
        fetch_membership(path)
    rows = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    sets = {d: {symbol(t) for t in s.split(",")} for d, s in zip(rows["date"], rows["tickers"])}
    cols = sorted(set().union(*sets.values()))
    snap = pd.DataFrame({c: [c in s for s in sets.values()] for c in cols}, index=list(sets))
    days = pd.bdate_range(max(snap.index.min(), pd.Timestamp(since)), snap.index.max())
    out = snap.reindex(snap.index.union(days)).ffill().reindex(days).fillna(False).astype(bool)
    out.index = out.index.tz_localize("UTC")
    return out


def coverage(member: pd.DataFrame, close: pd.DataFrame) -> "dict[int, float]":
    """Share of member-days that have a price, by year: the size of the hole in the data."""
    have = close.reindex(index=member.index, columns=member.columns).notna()
    got = (member & have).groupby(member.index.year).sum().sum(axis=1)
    want = member.groupby(member.index.year).sum().sum(axis=1)
    return {int(y): float(got[y] / want[y]) for y in want.index}
