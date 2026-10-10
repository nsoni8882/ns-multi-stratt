#!/usr/bin/env python3
"""Regenerate the cached closes the drift test runs on. Network; run by hand, not in CI.

    .venv/bin/python trader/tests/fixtures/make_fixtures.py
"""
from pathlib import Path

import yfinance as yf

for sym in ("AMZN", "AAPL"):
    close = yf.download(sym, start="2000-01-01", auto_adjust=True, progress=False)["Close"].squeeze()
    out = Path(__file__).parent / f"{sym}.csv"
    close.rename("close").to_csv(out, date_format="%Y-%m-%d")
    print(sym, len(close), "->", out)
