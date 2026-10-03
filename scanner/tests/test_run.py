import json

import numpy as np
import pandas as pd
import pytest

from scanner.run import ScanError, run
from scanner.store import SignalStore
from scanner.strategies import STRATEGIES
from scanner.tests.conftest import make_df

NOW = pd.Timestamp("2026-10-02 21:00", tz="UTC")


def buy_closes():
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    return list(np.concatenate([up, down, [down[-1] * 1.06]]))


UNIVERSE = pd.DataFrame({
    "ticker": ["AAA", "BBB", "CCC"],
    "name": ["Alpha", "Beta", "Gamma"],
    "sector": ["Tech", "Tech", "Energy"],
})


def fake_fetch(tickers, timeframe, now):
    bars = {"AAA": make_df(buy_closes()), "BBB": make_df([100.0] * 300), "CCC": make_df([100.0] * 300)}
    return bars, []


def test_run_writes_json_and_records_signals(tmp_path):
    out, db = tmp_path / "data", tmp_path / "signals.db"
    result = run(out, db, now=NOW, universe=UNIVERSE, fetch=fake_fetch)
    assert result["hits"] == 2  # AAA flagged on 4h and 1d by the MACD+RSI strategy
    summary = json.loads((out / "strategies.json").read_text())
    s1 = next(s for s in summary["strategies"] if s["id"] == "macd-rsi-reversal")
    assert s1["timeframes"]["1d"] == {"buy": 1, "sell": 0}
    rows = json.loads((out / "macd-rsi-reversal" / "1d.json").read_text())["signals"]
    assert [r["ticker"] for r in rows] == ["AAA"]
    assert rows[0]["name"] == "Alpha" and rows[0]["side"] == "BUY" and rows[0]["bars_ago"] == 0
    assert rows[0]["conviction"] in ("high", "standard")
    assert len(rows[0]["spark"]) == 30 and rows[0]["spark"][-1] == rows[0]["price"]
    assert s1["chart"] == {"rsi_levels": [20, 25, 80], "macd_deep": True, "emas": False}
    chart = json.loads((out / "charts" / "1d" / "AAA.json").read_text())
    assert len(chart["bars"]) == len(chart["rsi"]) == len(chart["macd"]["hist"]) == 195  # all bars, under the 250 cap
    assert chart["signals"][0]["side"] == "BUY"
    assert not (out / "charts" / "1d" / "BBB.json").exists()  # only flagged tickers get charts
    assert SignalStore(db).count() == 2


def test_rerun_does_not_duplicate_history(tmp_path):
    out, db = tmp_path / "data", tmp_path / "signals.db"
    run(out, db, now=NOW, universe=UNIVERSE, fetch=fake_fetch)
    second = run(out, db, now=NOW + pd.Timedelta(hours=1), universe=UNIVERSE, fetch=fake_fetch)
    assert second["recorded"] == 0
    assert SignalStore(db).count() == 2


def test_no_signals_still_writes_valid_empty_files(tmp_path):
    out = tmp_path / "data"
    flat = lambda t, tf, n: ({"AAA": make_df([100.0] * 300)}, [])  # noqa: E731
    run(out, tmp_path / "s.db", now=NOW, universe=UNIVERSE.iloc[:1], fetch=flat)
    for strat in STRATEGIES:
        for tf in ("4h", "1d"):
            assert json.loads((out / strat.id / f"{tf}.json").read_text())["signals"] == []
    assert not (out / "charts").exists()


def test_too_many_failed_tickers_aborts_before_writing(tmp_path):
    out = tmp_path / "data"
    failing = lambda t, tf, n: ({}, list(t))  # noqa: E731
    with pytest.raises(ScanError):
        run(out, tmp_path / "s.db", now=NOW, universe=UNIVERSE, fetch=failing)
    assert not out.exists()


def test_chart_is_capped_at_250_bars(tmp_path):
    long_buy = [100.0] * 100 + buy_closes()  # 295 bars, ends on the BUY bounce
    fetch = lambda t, tf, n: ({"AAA": make_df(long_buy)}, [])  # noqa: E731
    run(tmp_path / "data", tmp_path / "s.db", now=NOW, universe=UNIVERSE.iloc[:1], fetch=fetch)
    chart = json.loads((tmp_path / "data" / "charts" / "1d" / "AAA.json").read_text())
    assert len(chart["bars"]) == 250


def test_run_writes_market_calendar_json(tmp_path):
    out = tmp_path / "data"
    run(out, tmp_path / "s.db", now=NOW, universe=UNIVERSE, fetch=fake_fetch)
    market = json.loads((out / "market.json").read_text())
    assert market["updated_at"] == NOW.isoformat()
    assert market["sessions"] and {"date", "open", "close", "early"} <= set(market["sessions"][0])
    assert isinstance(market["holidays"], list)


def test_run_publishes_and_records_the_rules_version(tmp_path):
    """An algo change must be visible in the output it produced: the fingerprint goes into
    strategies.json so a stale deploy is detectable, and onto every history row so the two
    rule generations never blend."""
    out, db = tmp_path / "data", tmp_path / "signals.db"
    run(out, db, now=NOW, universe=UNIVERSE, fetch=fake_fetch)

    summary = json.loads((out / "strategies.json").read_text())
    published = {s["id"]: s["rules_version"] for s in summary["strategies"]}
    assert all(len(v) == 12 for v in published.values())
    assert len(set(published.values())) == len(published)  # distinct per strategy

    store = SignalStore(db)
    stored = store.conn.execute(
        "SELECT DISTINCT strategy_id, rules_version FROM signals").fetchall()
    store.close()
    assert stored and all(published[sid] == ver for sid, ver in stored)


def test_rules_version_moves_when_a_strategy_is_reconfigured(tmp_path):
    from scanner.strategies.trend_pullback import TrendPullback, TrendPullbackConfig

    def version_for(strategies, path):
        run(path, path / "s.db", now=NOW, universe=UNIVERSE, fetch=fake_fetch,
            strategies=strategies)
        summary = json.loads((path / "strategies.json").read_text())
        return summary["strategies"][0]["rules_version"]

    shipped = version_for([TrendPullback()], tmp_path / "a")
    gated = version_for([TrendPullback(TrendPullbackConfig(adx_min=20))], tmp_path / "b")
    assert shipped != gated
