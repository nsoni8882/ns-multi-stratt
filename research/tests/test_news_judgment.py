import json
from datetime import datetime, timezone

import pytest

from research import news_judgment as nj

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Acme cuts full-year guidance after weak harvest</title>
    <pubDate>Thu, 02 Oct 2026 14:00:00 +0000</pubDate>
    <description>The company   said   margins would be lower.</description>
  </item>
  <item>
    <title>3 stocks to watch this week</title>
    <pubDate>Wed, 01 Oct 2026 09:00:00 +0000</pubDate>
    <description/>
  </item>
  <item><title/><description>no title, must be dropped</description></item>
</channel></rss>"""

ROW = {
    "ticker": "ADM", "name": "Archer Daniels Midland", "sector": "Consumer Staples",
    "price": 80.45, "side": "BUY", "conviction": "standard", "bars_ago": 0,
    "fired_at": "2026-10-02T20:00:00+00:00", "bar_time": 1790899200,
    "details": {"rsi": 42.93, "rsi_level": 40.0}, "spark": [1, 2],
}

RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "adverse_company_event": {"type": "noul", "noul": 0.87},
        "substantive_company_news": {"type": "noul", "noul": 0.93},
    },
    "usage": {"input_tokens": 412, "output_tokens": 20},
}


def test_parse_feed_keeps_titled_items_and_squashes_whitespace():
    items = nj.parse_feed(FEED)
    assert [h.title for h in items] == [
        "Acme cuts full-year guidance after weak harvest",
        "3 stocks to watch this week",
    ]
    assert items[0].summary == "The company said margins would be lower."
    assert items[0].published.startswith("Thu, 02 Oct 2026")


def test_parse_feed_honours_the_limit():
    assert len(nj.parse_feed(FEED, limit=1)) == 1


def test_state_carries_the_news_and_the_move_it_has_to_explain():
    state = nj.build_state(ROW, "trend-pullback", "1d", nj.parse_feed(FEED))
    assert state["company"]["ticker"] == "ADM"
    assert state["signal"]["direction"] == "BUY"
    # The model needs to know which price move it is being asked about.
    assert "fell then began to recover" in state["signal"]["what_the_rules_saw"]
    assert "uptrend" in state["signal"]["what_the_rules_saw"]
    assert "42.9" in state["signal"]["what_the_rules_saw"]
    assert "40 trigger" in state["signal"]["what_the_rules_saw"]
    assert len(state["recent_news"]) == 2


def test_state_reads_without_indicator_details():
    bare = ROW | {"details": {}}
    sentence = nj.build_state(bare, "trend-pullback", "1d", [])["signal"]["what_the_rules_saw"]
    assert sentence.endswith("uptrend.")


def test_sell_state_describes_the_opposite_move():
    sentence = nj.build_state(ROW | {"side": "SELL"}, "trend-pullback", "1d",
                              [])["signal"]["what_the_rules_saw"]
    assert "rose then began to roll over" in sentence and "downtrend" in sentence


def test_questions_are_nouls_phrased_so_high_means_yes():
    assert set(nj.QUESTIONS) == {"adverse_company_event", "substantive_company_news"}
    for q in nj.QUESTIONS.values():
        assert q["type"] == "noul"
        assert set(q["criteria"]) == {"true", "false"}


def test_judge_sends_one_request_with_both_questions():
    sent = {}

    class FakeSession:
        def post(self, url, **kw):
            sent["url"], sent["kw"] = url, kw
            return FakeResponse(RESPONSE)

    out = nj.judge({"company": {}}, "k-123", FakeSession())
    assert out == RESPONSE
    assert sent["url"] == nj.API_URL
    assert sent["kw"]["headers"]["Authorization"] == "Bearer k-123"
    body = sent["kw"]["json"]
    assert body["model"] == nj.MODEL
    assert set(body["questions"]) == set(nj.QUESTIONS)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_record_joins_the_judgment_to_the_bar_it_was_made_about():
    now = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)
    rec = nj.to_record(ROW, "trend-pullback", "1d", nj.parse_feed(FEED), RESPONSE, now)
    assert rec["bar_time"] == ROW["bar_time"]
    assert rec["answers"] == {"adverse_company_event": 0.87, "substantive_company_news": 0.93}
    assert rec["model"] == "jev-1.13.0"
    assert rec["headline_count"] == 2
    assert rec["recorded_at"] == "2026-10-03T18:00:00+00:00"


def test_a_signal_is_never_judged_twice(tmp_path):
    path = tmp_path / "2026-10.jsonl"
    rec = nj.to_record(ROW, "trend-pullback", "1d", [], RESPONSE)
    nj.append(path, [rec])
    assert nj.already_judged(path) == {("trend-pullback", "1d", "ADM", 1790899200)}
    # A second run on the same month's file sees it and skips.
    nj.append(path, [rec | {"ticker": "BMY"}])
    assert len(nj.already_judged(path)) == 2


def test_already_judged_is_empty_before_the_first_run(tmp_path):
    assert nj.already_judged(tmp_path / "nothing.jsonl") == set()


def test_load_signals_reads_every_published_list_but_not_the_charts(tmp_path):
    for name in ("trend-pullback", "macd-rsi-reversal"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "1d.json").write_text(json.dumps({"signals": [ROW]}))
    (tmp_path / "charts").mkdir()
    (tmp_path / "charts" / "ADM.json").write_text(json.dumps({"bars": []}))
    found = nj.load_signals(tmp_path)
    assert sorted({s[0] for s in found}) == ["macd-rsi-reversal", "trend-pullback"]
    assert all(s[1] == "1d" for s in found)


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(nj.MissingKey, match="TYPESAFE_API_KEY"):
        nj.api_key()


def test_dry_run_calls_typesafe_for_nothing(tmp_path, monkeypatch, capsys):
    (tmp_path / "trend-pullback").mkdir()
    (tmp_path / "trend-pullback" / "1d.json").write_text(json.dumps({"signals": [ROW]}))
    monkeypatch.setattr(nj, "fetch_headlines", lambda t, s=None: nj.parse_feed(FEED))
    monkeypatch.setattr(nj, "judge", lambda *a, **k: pytest.fail("dry run must not call the API"))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert nj.run(tmp_path, tmp_path / "out", dry_run=True) == 0
    assert "Archer Daniels Midland" in capsys.readouterr().out


def test_run_records_one_line_per_signal_and_skips_a_dead_feed(tmp_path, monkeypatch):
    (tmp_path / "trend-pullback").mkdir()
    rows = [ROW, ROW | {"ticker": "BMY", "bar_time": 1790899201}]
    (tmp_path / "trend-pullback" / "1d.json").write_text(json.dumps({"signals": rows}))

    def flaky(ticker, session=None):
        if ticker == "BMY":
            raise RuntimeError("feed down")
        return nj.parse_feed(FEED)

    monkeypatch.setattr(nj, "fetch_headlines", flaky)
    monkeypatch.setattr(nj, "judge", lambda *a, **k: RESPONSE)
    monkeypatch.setattr(nj.time, "sleep", lambda s: None)
    monkeypatch.setenv("TYPESAFE_API_KEY", "k-123")

    out = tmp_path / "out"
    assert nj.run(tmp_path, out) == 1  # the dead feed is skipped, not fatal
    written = [json.loads(l) for l in nj.record_path(out_dir=out).read_text().splitlines()]
    assert [r["ticker"] for r in written] == ["ADM"]
    # Re-running judges nothing again.
    assert nj.run(tmp_path, out) == 0
