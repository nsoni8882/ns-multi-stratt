import pandas as pd
import pytest

from scanner import universe
from scanner.universe import load_universe, parse_universe

HTML = """
<table class="wikitable sortable">
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>Date added</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td><td>1982</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td><td>2010</td></tr>
<tr><td>BF.B</td><td>Brown-Forman</td><td>Consumer Staples</td><td>1982</td></tr>
</table>
"""


def test_parse_universe_columns_and_dot_to_dash():
    df = parse_universe(HTML)
    assert df.columns.tolist() == ["ticker", "name", "sector"]
    assert df["ticker"].tolist() == ["AAPL", "BRK-B", "BF-B"]
    assert df.loc[0, "sector"] == "Information Technology"


def test_load_universe_falls_back_when_scrape_fails(monkeypatch, tmp_path):
    csv = tmp_path / "fallback.csv"
    pd.DataFrame({"ticker": ["AAPL"], "name": ["Apple"], "sector": ["IT"]}).to_csv(csv, index=False)

    def boom():
        raise RuntimeError("wikipedia down")

    monkeypatch.setattr(universe, "fetch_universe", boom)
    assert load_universe(csv)["ticker"].tolist() == ["AAPL"]


def test_fetch_rejects_suspiciously_small_table(monkeypatch):
    class Resp:
        text = HTML
        def raise_for_status(self): pass

    monkeypatch.setattr(universe.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(ValueError):
        universe.fetch_universe()
