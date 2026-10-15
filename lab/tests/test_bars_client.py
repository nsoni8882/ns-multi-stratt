import json
from datetime import datetime, timezone

from trader.alpaca import Alpaca

BAR = {"t": "2024-03-04T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}


def test_bars_follow_pagination_and_request_the_timeframe():
    pages = [{"bars": {"AAPL": [BAR]}, "next_page_token": "x"},
             {"bars": {"AAPL": [{**BAR, "t": "2024-03-04T14:35:00Z"}]}, "next_page_token": None}]
    calls = []

    def opener(url, data, headers, method):
        calls.append(url)
        return json.dumps(pages[len(calls) - 1]).encode()

    a = Alpaca("k", "s", opener=opener)
    out = a.bars("AAPL", "5Min", datetime(2024, 3, 1, tzinfo=timezone.utc),
                 datetime(2024, 3, 5, tzinfo=timezone.utc))
    assert [b["t"] for b in out] == ["2024-03-04T14:30:00Z", "2024-03-04T14:35:00Z"]
    assert "timeframe=5Min" in calls[0] and "page_token=x" in calls[1]
    assert "feed=sip" in calls[0] and "adjustment=all" in calls[0]


def test_bars_for_an_unknown_symbol_is_empty_not_an_error():
    a = Alpaca("k", "s", opener=lambda *x: json.dumps({"bars": None, "next_page_token": None}).encode())
    assert a.bars("ZZZZ", "5Min", datetime(2024, 3, 1, tzinfo=timezone.utc),
                  datetime(2024, 3, 2, tzinfo=timezone.utc)) == []
