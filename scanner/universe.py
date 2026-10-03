"""S&P 500 constituents: scrape Wikipedia, fall back to a committed snapshot."""
import argparse
import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FALLBACK_CSV = Path(__file__).parent / "universe_fallback.csv"
MIN_EXPECTED = 450  # a scrape returning fewer rows is treated as broken

log = logging.getLogger(__name__)


def parse_universe(html: str) -> pd.DataFrame:
    """Parse the Wikipedia constituents table into columns ticker, name, sector."""
    table = pd.read_html(StringIO(html), match="Symbol")[0]
    out = table.rename(columns={"Symbol": "ticker", "Security": "name", "GICS Sector": "sector"})
    out = out[["ticker", "name", "sector"]].copy()
    out["ticker"] = out["ticker"].astype(str).str.strip().str.replace(".", "-", regex=False)
    return out.drop_duplicates("ticker").reset_index(drop=True)


def fetch_universe() -> pd.DataFrame:
    resp = requests.get(WIKI_URL, headers={"User-Agent": "ns-multi-stratt/1.0 (personal screener)"}, timeout=30)
    resp.raise_for_status()
    df = parse_universe(resp.text)
    if len(df) < MIN_EXPECTED:
        raise ValueError(f"universe scrape returned only {len(df)} rows")
    return df


def load_universe(fallback: Path = FALLBACK_CSV) -> pd.DataFrame:
    try:
        return fetch_universe()
    except Exception as exc:
        log.warning("universe scrape failed (%s); using %s", exc, fallback)
        return pd.read_csv(fallback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh the committed universe snapshot")
    parser.parse_args()
    fetch_universe().to_csv(FALLBACK_CSV, index=False)
    print(f"wrote {FALLBACK_CSV}")
