import pandas as pd

from research import hermes_denied as hd


def row(**kw):
    base = dict(pivot_cross_date="2026-06-25", stop_hit_date=None, tp1_hit_date=None, entry_price=100.0,
                stop_price=94.0, tp1_price=112.0, last_check_price=103.0)
    return pd.Series(base | kw)


def test_a_stop_hit_before_the_pivot_crossed_is_not_a_trade():
    ret, end = hd.outcome(row(stop_hit_date="2026-06-23"))
    assert end == "open" and abs(ret - 0.03) < 1e-9  # the earlier stop belonged to a position that never existed


def test_the_first_event_after_the_cross_wins_and_a_same_day_tie_goes_to_the_stop():
    assert hd.outcome(row(stop_hit_date="2026-06-28", tp1_hit_date="2026-06-30"))[1] == "stop"
    assert hd.outcome(row(stop_hit_date="2026-06-30", tp1_hit_date="2026-06-28"))[1] == "tp1"
    assert hd.outcome(row(stop_hit_date="2026-06-30", tp1_hit_date="2026-06-30"))[1] == "stop"
