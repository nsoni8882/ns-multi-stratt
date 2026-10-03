import pandas as pd

from scanner import market as m


def ts(s):
    return pd.Timestamp(s, tz="UTC")


def due(day):
    (session,) = m.sessions(ts(f"{day} 00:00"), ts(f"{day} 23:59"))
    return m.update_due_times(session)


def test_regular_summer_session_has_two_updates():
    # Fri 2 Oct 2026 (EDT): bars close 13:30 and 16:00 ET = 17:30 and 20:00 UTC, +5 minutes.
    assert due("2026-10-02") == [ts("2026-10-02 17:35"), ts("2026-10-02 20:05")]


def test_winter_session_uses_the_winter_utc_offset():
    assert due("2026-12-15") == [ts("2026-12-15 18:35"), ts("2026-12-15 21:05")]


def test_early_close_day_has_a_single_update_at_the_close():
    # Day after Thanksgiving closes 13:00 ET (18:00 UTC); the first 4H bar would end after the close.
    assert due("2026-11-27") == [ts("2026-11-27 18:05")]


def test_weekends_and_holidays_have_no_sessions():
    assert m.sessions(ts("2026-10-03 00:00"), ts("2026-10-04 23:59")) == []  # Sat, Sun
    assert m.sessions(ts("2026-11-26 00:00"), ts("2026-11-26 23:59")) == []  # Thanksgiving
    assert m.sessions(ts("2026-07-03 00:00"), ts("2026-07-03 23:59")) == []  # Independence Day (observed)


def test_latest_and_next_due_skip_the_weekend():
    assert m.latest_due(ts("2026-10-03 12:00")) == ts("2026-10-02 20:05")
    assert m.latest_due(ts("2026-10-05 13:00")) == ts("2026-10-02 20:05")  # Monday before the first bar closes
    assert m.latest_due(ts("2026-10-05 17:36")) == ts("2026-10-05 17:35")
    assert m.next_due(ts("2026-10-03 12:00")) == ts("2026-10-05 17:35")
    assert m.next_due(ts("2026-10-05 17:36")) == ts("2026-10-05 20:05")


def test_is_behind():
    sat = ts("2026-10-03 12:00")
    assert not m.is_behind(sat, ts("2026-10-02 20:07"))  # got Friday's close
    assert m.is_behind(sat, ts("2026-10-02 17:36"))  # missed Friday's last bar
    assert not m.is_behind(ts("2026-10-05 17:40"), ts("2026-10-05 17:36"))
    assert m.is_behind(ts("2026-10-05 17:40"), ts("2026-10-02 20:07"))  # Monday's first update is due


def test_holiday_needs_no_update_but_the_short_day_after_does():
    wed_close = ts("2026-11-25 21:07")  # close is 21:00 UTC in winter
    assert not m.is_behind(ts("2026-11-26 15:00"), wed_close)  # Thanksgiving: nothing is due
    assert m.is_behind(ts("2026-11-27 18:10"), wed_close)  # early-close day after


def test_payload_lists_sessions_holidays_and_early_closes():
    p = m.market_payload(ts("2026-11-20 12:00"))
    by_date = {s["date"]: s for s in p["sessions"]}
    assert by_date["2026-11-27"]["early"] is True and by_date["2026-11-25"]["early"] is False
    assert by_date["2026-11-25"]["open"] == "2026-11-25T14:30:00+00:00"
    names = {h["date"]: h["name"] for h in p["holidays"]}
    assert names["2026-11-26"] == "Thanksgiving"
    assert "2026-11-21" not in names  # Saturdays are not listed as holidays
    assert p["updated_at"] == "2026-11-20T12:00:00+00:00"
    assert min(by_date) <= "2026-11-06" and max(by_date) >= "2026-12-30"  # 14 days back, 45 ahead


def test_gate_runs_pushes_and_manual_runs_always():
    sat = ts("2026-10-03 12:00")
    assert m.should_run("push", sat, ts("2026-10-02 20:07"))[0] is True
    assert m.should_run("workflow_dispatch", sat, ts("2026-10-02 20:07"))[0] is True


def test_gate_scheduled_run_only_when_an_update_is_due():
    sat = ts("2026-10-03 12:00")
    assert m.should_run("schedule", sat, ts("2026-10-02 20:07"))[0] is False
    assert m.should_run("schedule", sat, ts("2026-10-02 17:36"))[0] is True
    assert m.should_run("schedule", sat, None)[0] is True  # unknown state (e.g. first deploy): scan
