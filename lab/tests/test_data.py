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


def test_dev_cutoff_is_pinned_not_derived_from_the_latest_bar():
    """The holdout must not drift as new bars arrive, or each look sees a different window."""
    from lab import config
    a = data.dev_cutoff()
    assert a == pd.Timestamp(config.HOLDOUT_START, tz="UTC")
    assert a == data.dev_cutoff()


class FakeClient:
    def __init__(self, frames, calendar):
        self.frames, self.rows, self.cal = list(frames), None, calendar

    def calendar(self, start, end):
        return self.cal

    def bars(self, symbol, timeframe, start, end):
        df = self.frames[self._i()]
        df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        return [{"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": r.open, "h": r.high, "l": r.low,
                 "c": r.close, "v": r.volume} for t, r in df.iterrows()]

    _n = 0

    def _i(self):
        i = min(self._n, len(self.frames) - 1)
        self._n += 1
        return i


def cal_rows(days_close):
    return [{"date": d, "open": "09:30", "close": c} for d, c in days_close]


def test_early_close_afterhours_bars_are_not_session(tmp_path):
    from datetime import datetime, timezone
    full = make_days(["2024-11-29"], n=78)  # prints through 15:55, but the market closed at 13:00
    client = FakeClient([full], cal_rows([("2024-11-29", "13:00")]))
    df = data._fetch_5min(client, "X", datetime(2024, 11, 1, tzinfo=timezone.utc),
                          datetime(2024, 12, 5, tzinfo=timezone.utc), tmp_path)
    assert len(df) == 42 and df.index[-1].tz_convert(data.ET).strftime("%H:%M") == "12:55"


def test_a_split_rebuilds_the_cache_instead_of_stitching_two_price_bases(tmp_path):
    from datetime import datetime, timezone
    days = ["2024-03-04", "2024-03-05", "2024-03-06"]
    pre = make_days(days[:2], base=100.0)
    post = make_days(days, base=100.0)
    post[["open", "high", "low", "close"]] = post[["open", "high", "low", "close"]] / 10  # 10:1, re-based
    client = FakeClient([pre, post], cal_rows([(d, "16:00") for d in days]))
    start, end = datetime(2024, 3, 1, tzinfo=timezone.utc), datetime(2024, 3, 8, tzinfo=timezone.utc)
    data._fetch_5min(client, "X", start, end, tmp_path)           # caches the pre-split history
    df = data._fetch_5min(client, "X", start, end, tmp_path)      # sees a re-based history
    assert df["close"].max() < 20, "old unadjusted bars survived the split"
