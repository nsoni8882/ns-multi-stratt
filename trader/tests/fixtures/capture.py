#!/usr/bin/env python3
"""Record real Alpaca responses as test fixtures. Network; run by hand, not in CI.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python trader/tests/fixtures/capture.py

Writes one JSON file per endpoint into fixtures/alpaca/. The account number is the user's own
paper account; nothing here is a credential, but re-check before committing.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "alpaca"
OUT.mkdir(parents=True, exist_ok=True)
H = {"APCA-API-KEY-ID": os.environ["ALPACA_KEY_ID"],
     "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]}


def get(base, path, params=None):
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return json.loads(r.read())


end = datetime.now(timezone.utc) - timedelta(minutes=16)
start = (end - timedelta(days=420)).strftime("%Y-%m-%d")
TRADING, DATA = "https://paper-api.alpaca.markets", "https://data.alpaca.markets"

for name, value in [
    ("account", get(TRADING, "/v2/account")),
    ("clock", get(TRADING, "/v2/clock")),
    ("calendar", get(TRADING, "/v2/calendar", {"start": "2026-09-01", "end": "2026-10-31"})),
    ("positions", get(TRADING, "/v2/positions")),
    ("orders_open", get(TRADING, "/v2/orders", {"status": "open"})),
    ("orders_closed", get(TRADING, "/v2/orders", {"status": "closed", "limit": 50,
                                                  "direction": "desc"})),
    ("portfolio_history", get(TRADING, "/v2/account/portfolio/history",
                              {"period": "1M", "timeframe": "1D"})),
    ("bars", get(DATA, "/v2/stocks/bars", {"symbols": "AMZN,AAPL", "timeframe": "1Day",
                                           "start": start,
                                           "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                           "adjustment": "all", "feed": "sip", "sort": "asc",
                                           "limit": 10000})),
]:
    (OUT / f"{name}.json").write_text(json.dumps(value, indent=1) + "\n")
    print("wrote", name)
