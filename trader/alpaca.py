"""Alpaca paper-trading and market-data client. Standard library only.

The endpoint is hardcoded to the paper host and trader/run.py refuses to start if that ever
stops being true. `opener` is the injection seam the tests use; nothing in the test suite
performs real I/O.

Two settings here are not arbitrary and are confirmed against Alpaca's docs:
  * Orders go in as market-on-close (`time_in_force="cls"`), which Alpaca rejects after
    15:50 ET -- https://docs.alpaca.markets/docs/orders-at-alpaca
  * `end` on data requests is held 16 minutes back, which is what lets a free account query
    the SIP feed -- https://docs.alpaca.markets/us/docs/market-data-faq
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from trader import params

TRADING = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
FEED = "sip"
END_HOLDBACK = timedelta(minutes=16)


class AlpacaError(RuntimeError):
    def __init__(self, status: int, body: str, method: str, path: str):
        super().__init__(f"{method} {path} -> HTTP {status}: {body[:400]}")
        self.status, self.body = status, body


def _urlopen(url, data, headers, method):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() or b"null"


def minutes_to_close(clock: dict) -> float:
    close_at = datetime.fromisoformat(clock["next_close"])
    now = datetime.fromisoformat(clock["timestamp"])
    return (close_at - now).total_seconds() / 60


def sessions_between(calendar: "list[dict]", after: str, through: str) -> int:
    """Trading sessions in (after, through] -- the backtest's bar count, not calendar days."""
    return len([d for d in calendar if after < d["date"] <= through])


class Alpaca:
    def __init__(self, key: str, secret: str, *, opener=None):
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                         "Content-Type": "application/json"}
        self._open = opener or _urlopen

    def _call(self, base, path, query=None, method="GET", body=None):
        url = base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = json.dumps(body).encode() if body is not None else None
        try:
            return json.loads(self._open(url, data, dict(self._headers), method))
        except urllib.error.HTTPError as e:
            raise AlpacaError(e.code, e.read().decode(), method, path) from None

    def account(self) -> dict:
        return self._call(TRADING, "/v2/account")

    def clock(self) -> dict:
        return self._call(TRADING, "/v2/clock")

    def calendar(self, start: str, end: str) -> "list[dict]":
        return self._call(TRADING, "/v2/calendar", {"start": start, "end": end})

    def positions(self) -> "dict[str, dict]":
        return {p["symbol"]: p for p in self._call(TRADING, "/v2/positions")}

    def open_order_symbols(self) -> "set[str]":
        return {o["symbol"] for o in self._call(TRADING, "/v2/orders", {"status": "open"})}

    def last_filled_buy(self, symbol: str) -> "dict | None":
        """The most recent filled buy, for recovering an entry date without a state file."""
        orders = self._call(TRADING, "/v2/orders",
                            {"status": "closed", "symbols": symbol, "limit": 50,
                             "direction": "desc"})
        for o in orders:
            if o.get("side") == "buy" and o.get("filled_at"):
                return o
        return None

    def daily_closes(self, symbol: str) -> "list[tuple[str, float]]":
        """Adjusted daily closes, oldest first. The last element is today's partial bar."""
        end = datetime.now(timezone.utc) - END_HOLDBACK
        start = (end - timedelta(days=params.LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        out, token = [], None
        while True:
            q = {"symbols": symbol, "timeframe": "1Day", "start": start,
                 "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "adjustment": "all",
                 "feed": FEED, "sort": "asc", "limit": 10000}
            if token:
                q["page_token"] = token
            r = self._call(DATA, "/v2/stocks/bars", q)
            out += [(b["t"][:10], float(b["c"])) for b in (r.get("bars") or {}).get(symbol, [])]
            token = r.get("next_page_token")
            if not token:
                return out

    def submit(self, symbol: str, side: str, qty: int) -> dict:
        return self._call(TRADING, "/v2/orders", method="POST",
                          body={"symbol": symbol, "qty": str(int(qty)), "side": side,
                                "type": "market", "time_in_force": "cls"})

    def portfolio_history(self, period: str = "all") -> dict:
        return self._call(TRADING, "/v2/account/portfolio/history",
                          {"period": period, "timeframe": "1D"})
