import pandas as pd

from lab import data
from lab.tests.conftest import make_days


def test_to_frame_parses_alpaca_bars():
    raw = [{"t": "2024-03-04T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]
    df = data.to_frame(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None and df["close"].iloc[0] == 1.5
    assert data.to_frame([]).empty


def test_regular_session_drops_extended_hours():
    day = make_days(["2024-03-04"])
    pre = make_days(["2024-03-04"], n=1, start_hm="08:00")
    post = make_days(["2024-03-04"], n=1, start_hm="16:00")
    out = data.regular_session(pd.concat([pre, day, post]).sort_index())
    assert len(out) == 78


def test_with_session_numbers_bars_per_day_and_sets_close_time():
    df = data.with_session(make_days(["2024-03-04", "2024-03-05"]), "5Min")
    assert df.groupby("day")["bar"].max().tolist() == [77, 77]
    assert df["bar"].iloc[78] == 0
    assert (df["close_time"] - df.index == pd.Timedelta(minutes=5)).all()


def test_early_close_day_has_fewer_bars_and_still_resamples():
    df5 = make_days(["2024-11-29"], n=42)  # 09:30-13:00 ET
    df15 = data.to_15min(df5)
    assert len(df15) == 14 and df15.index[-1].tz_convert(data.ET).strftime("%H:%M") == "12:45"


def test_dst_week_keeps_session_alignment():
    df5 = pd.concat([make_days(["2024-03-08"]), make_days(["2024-03-11"])])  # US DST starts 03-10
    et = data.to_15min(df5).index.tz_convert(data.ET)
    assert et[0].strftime("%H:%M") == "09:30" and et[26].strftime("%H:%M") == "09:30"


def test_15min_drops_a_bucket_with_a_missing_bar():
    df5 = make_days(["2024-03-04"])
    gappy = df5.drop(df5.index[4])  # a halted 5-minute bar
    assert len(data.to_15min(df5)) == 26 and len(data.to_15min(gappy)) == 25


def test_closed_only_drops_the_forming_bar():
    df = data.with_session(make_days(["2024-03-04"], n=3), "5Min")
    now = df["close_time"].iloc[1]
    assert len(data.closed_only(df, now)) == 2


def test_dev_cutoff_is_six_months_before_the_latest_bar():
    a = make_days(["2023-01-03"])
    b = make_days(["2024-03-04"])
    cutoff = data.dev_cutoff({"A": pd.concat([a, b])})
    assert cutoff.tz_convert(data.ET).strftime("%Y-%m") == "2023-09"
