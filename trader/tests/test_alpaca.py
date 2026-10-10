"""The HTTP client, against recorded responses. No test touches the network."""
import io
import json
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trader.alpaca import TRADING, Alpaca, AlpacaError, minutes_to_close, sessions_between

FIX = Path(__file__).parent / "fixtures" / "alpaca"


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


class Recorded:
    """An opener that answers from fixtures and records what it was asked."""

    def __init__(self, routes, error=None):
        self.routes, self.error, self.calls = routes, error, []

    def __call__(self, url, data, headers, method):
        self.calls.append({"url": url, "data": data, "method": method, "headers": headers})
        if self.error:
            raise self.error
        for fragment, name in self.routes.items():
            if fragment in url:
                return json.dumps(load(name)).encode()
        raise AssertionError(f"no fixture for {url}")


def client(routes, error=None):
    rec = Recorded(routes, error)
    return Alpaca("KEY", "SECRET", opener=rec), rec


def test_account_is_parsed():
    api, _ = client({"/v2/account": "account"})
    assert api.account()["status"] == "ACTIVE"


def test_credentials_go_in_the_headers_and_never_the_url():
    api, rec = client({"/v2/account": "account"})
    api.account()
    assert rec.calls[0]["headers"]["APCA-API-KEY-ID"] == "KEY"
    assert rec.calls[0]["headers"]["APCA-API-SECRET-KEY"] == "SECRET"
    assert "SECRET" not in rec.calls[0]["url"]


def test_daily_closes_returns_date_close_pairs_in_order():
    api, _ = client({"/v2/stocks/bars": "bars"})
    bars = api.daily_closes("AMZN")
    assert len(bars) > 200
    assert bars == sorted(bars)
    assert all(isinstance(d, str) and isinstance(c, float) for d, c in bars)


def test_daily_closes_holds_end_sixteen_minutes_back_for_the_sip_feed():
    """A free account may query SIP only when `end` is at least 15 minutes old."""
    api, rec = client({"/v2/stocks/bars": "bars"})
    api.daily_closes("AMZN")
    url = rec.calls[0]["url"]
    assert "feed=sip" in url
    assert "adjustment=all" in url
    end = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["end"][0]
    age = datetime.now(timezone.utc) - datetime.fromisoformat(end.replace("Z", "+00:00"))
    assert 15 * 60 <= age.total_seconds() <= 20 * 60


def test_positions_keyed_by_symbol():
    api, _ = client({"/v2/positions": "positions"})
    assert isinstance(api.positions(), dict)


def test_submit_posts_a_market_on_close_order():
    api, rec = client({"/v2/orders": "order_filled"})
    api.submit("AMZN", "buy", 190)
    call = rec.calls[0]
    assert call["method"] == "POST"
    assert json.loads(call["data"]) == {"symbol": "AMZN", "qty": "190", "side": "buy",
                                        "type": "market", "time_in_force": "cls"}


def test_submit_sends_whole_shares_as_a_string():
    api, rec = client({"/v2/orders": "order_filled"})
    api.submit("AAPL", "sell", 148)
    assert json.loads(rec.calls[0]["data"])["qty"] == "148"


def test_http_error_becomes_alpaca_error_carrying_status_and_body():
    err = urllib.error.HTTPError("u", 422, "Unprocessable", {},
                                 io.BytesIO(json.dumps(load("error_422")).encode()))
    api, _ = client({"/v2/orders": "order_filled"}, error=err)
    with pytest.raises(AlpacaError) as caught:
        api.submit("AMZN", "buy", 1)
    assert caught.value.status == 422
    assert "cls orders are not accepted" in caught.value.body


def test_minutes_to_close_reads_the_clock():
    clock = {"timestamp": "2026-10-12T15:25:00-04:00", "next_close": "2026-10-12T16:00:00-04:00",
             "is_open": True}
    assert minutes_to_close(clock) == pytest.approx(35.0)


def test_sessions_between_counts_trading_days_not_calendar_days():
    cal = [{"date": "2026-10-09"}, {"date": "2026-10-12"}, {"date": "2026-10-13"}]
    assert sessions_between(cal, "2026-10-09", "2026-10-13") == 2
    assert sessions_between(cal, "2026-10-13", "2026-10-13") == 0


def test_trading_endpoint_is_the_paper_host():
    assert "paper" in TRADING
