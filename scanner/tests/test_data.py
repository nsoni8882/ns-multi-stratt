import pandas as pd
import pytest

from scanner.data import to_daily, to_four_hour

ET = "America/New_York"


def hourly(day, hours, price=100.0):
    """1H bars on `day` starting at each (hour, minute) in `hours`, tz-aware ET like Yahoo's."""
    idx = [pd.Timestamp(f"{day} {h:02d}:{m:02d}").tz_localize(ET) for h, m in hours]
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": [price + i for i in range(n)],
            "High": [price + i + 2 for i in range(n)],
            "Low": [price + i - 2 for i in range(n)],
            "Close": [price + i + 1 for i in range(n)],
            "Volume": [10] * n,
        },
        index=pd.DatetimeIndex(idx).tz_convert("UTC"),
    )


FULL_DAY = [(9, 30), (10, 30), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30)]
AFTER_CLOSE = pd.Timestamp("2026-09-30 22:00", tz="UTC")  # 18:00 ET


def test_four_hour_bins_and_aggregation():
    out = to_four_hour(hourly("2026-09-30", FULL_DAY), AFTER_CLOSE)
    assert len(out) == 2
    first, second = out.iloc[0], out.iloc[1]
    # First bar: 09:30-13:30 ET = hourly bars 0..3; second: 13:30-16:00 ET = bars 4..6.
    assert (first["open"], first["close"], first["high"], first["low"], first["volume"]) == (100, 104, 105, 98, 40)
    assert (second["open"], second["close"], second["high"], second["low"], second["volume"]) == (104, 107, 108, 102, 30)
    assert out.index[0] == pd.Timestamp("2026-09-30 13:30", tz="UTC")  # 09:30 ET (EDT)
    assert out["close_time"].tolist() == [
        pd.Timestamp("2026-09-30 17:30", tz="UTC"),  # 13:30 ET
        pd.Timestamp("2026-09-30 20:00", tz="UTC"),  # 16:00 ET
    ]


def test_four_hour_drops_bar_that_has_not_closed_yet():
    now = pd.Timestamp("2026-09-30 19:00", tz="UTC")  # 15:00 ET, second bar still forming
    out = to_four_hour(hourly("2026-09-30", FULL_DAY[:6]), now)
    assert len(out) == 1
    assert out["close_time"].iloc[0] == pd.Timestamp("2026-09-30 17:30", tz="UTC")


def test_four_hour_drops_group_missing_its_last_hourly_bar():
    # Past 16:05 ET but Yahoo has not delivered the 15:30 bar yet.
    out = to_four_hour(hourly("2026-09-30", FULL_DAY[:6]), AFTER_CLOSE)
    assert len(out) == 1


def test_four_hour_early_close_day_has_single_bar():
    out = to_four_hour(hourly("2026-11-27", FULL_DAY[:4]), pd.Timestamp("2026-11-27 19:00", tz="UTC"))
    assert len(out) == 1


def test_four_hour_uses_correct_utc_offset_in_winter():
    out = to_four_hour(hourly("2026-12-15", FULL_DAY), pd.Timestamp("2026-12-15 23:00", tz="UTC"))
    assert out.index[0] == pd.Timestamp("2026-12-15 14:30", tz="UTC")  # 09:30 ET (EST)


def test_four_hour_ignores_rows_without_close():
    raw = hourly("2026-09-30", FULL_DAY)
    raw.iloc[2, raw.columns.get_loc("Close")] = float("nan")
    assert len(to_four_hour(raw, AFTER_CLOSE)) == 2


def _daily(dates):
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    n = len(idx)
    return pd.DataFrame({"Open": [1.0] * n, "High": [2.0] * n, "Low": [0.5] * n, "Close": [1.5] * n, "Volume": [5] * n}, index=idx)


def test_daily_close_time_is_1600_et_and_today_is_dropped_until_close():
    raw = _daily(["2026-09-29", "2026-09-30"])
    during = to_daily(raw, pd.Timestamp("2026-09-30 15:00", tz="UTC"))  # 11:00 ET
    assert len(during) == 1
    after = to_daily(raw, AFTER_CLOSE)
    assert len(after) == 2
    assert after["close_time"].iloc[-1] == pd.Timestamp("2026-09-30 20:00", tz="UTC")
    assert after.index[-1] == pd.Timestamp("2026-09-30", tz="UTC")


def test_daily_accepts_tz_aware_index():
    raw = _daily(["2026-09-29", "2026-09-30"])
    raw.index = raw.index.tz_localize(ET)
    out = to_daily(raw, AFTER_CLOSE)
    assert out.index.tolist() == [pd.Timestamp("2026-09-29", tz="UTC"), pd.Timestamp("2026-09-30", tz="UTC")]


# ---- fetch_bars: retries and stale-bar detection ----
from scanner import data as data_module  # noqa: E402


def _multi(frames):
    return pd.concat(frames, axis=1, sort=True)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(data_module, "RETRY_PAUSE", 0)
    monkeypatch.setattr(data_module, "BATCH_PAUSE", 0)


def test_fetch_retries_tickers_that_come_back_empty(monkeypatch, no_sleep):
    calls = []

    def fake_download(tickers, timeframe, now, attempts=3):
        calls.append(list(tickers))
        if len(calls) == 1:
            return _multi({"AAA": _daily(["2026-09-29", "2026-09-30"])})  # BBB silently missing (throttled)
        return _multi({"BBB": _daily(["2026-09-29", "2026-09-30"])})

    monkeypatch.setattr(data_module, "_download", fake_download)
    bars, failed = data_module.fetch_bars(["AAA", "BBB"], "1d", AFTER_CLOSE)
    assert sorted(bars) == ["AAA", "BBB"] and failed == []
    assert calls == [["AAA", "BBB"], ["BBB"]]  # only the missing ticker is re-requested


def test_fetch_gives_up_after_three_attempts(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(data_module, "_download", lambda t, tf, now, attempts=3: calls.append(list(t)) or pd.DataFrame())
    bars, failed = data_module.fetch_bars(["AAA"], "1d", AFTER_CLOSE)
    assert bars == {} and failed == ["AAA"] and len(calls) == 3


def test_fetch_flags_ticker_whose_last_bar_is_older_than_the_rest(monkeypatch, no_sleep):
    raw = _multi({"AAA": _daily(["2026-09-29", "2026-09-30"]), "BBB": _daily(["2026-09-28", "2026-09-29"])})
    monkeypatch.setattr(data_module, "_download", lambda t, tf, now, attempts=3: raw)
    bars, failed = data_module.fetch_bars(["AAA", "BBB"], "1d", AFTER_CLOSE)
    assert list(bars) == ["AAA"] and failed == ["BBB"]  # BBB (halted/delisted) must not look "fresh"
