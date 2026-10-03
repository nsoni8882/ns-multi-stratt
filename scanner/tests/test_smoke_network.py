"""End-to-end check against live Yahoo data. Skipped unless RUN_NETWORK=1."""
import json
import os

import pandas as pd
import pytest

from scanner.run import run

pytestmark = pytest.mark.skipif(not os.environ.get("RUN_NETWORK"), reason="set RUN_NETWORK=1 to hit Yahoo")


def test_scan_five_real_tickers(tmp_path):
    universe = pd.DataFrame({
        "ticker": ["AAPL", "MSFT", "XOM", "JPM", "BRK-B"],
        "name": ["Apple", "Microsoft", "Exxon", "JPMorgan", "Berkshire"],
        "sector": ["IT", "IT", "Energy", "Financials", "Financials"],
    })
    out = tmp_path / "data"
    run(out, tmp_path / "signals.db", universe=universe)
    summary = json.loads((out / "strategies.json").read_text())
    assert [s["id"] for s in summary["strategies"]] == ["macd-rsi-reversal", "trend-pullback"]
    for strategy in summary["strategies"]:
        for tf in ("4h", "1d"):
            data = json.loads((out / strategy["id"] / f"{tf}.json").read_text())
            assert isinstance(data["signals"], list)
