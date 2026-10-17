import pandas as pd

from research import hermes_resim as hr


def bars(rows):
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame([dict(Open=r[1], High=r[2], Low=r[3], Close=r[4]) for r in rows], index=idx)


def test_a_gap_up_through_the_entry_pays_the_gap_and_a_never_triggered_setup_is_not_a_trade():
    b = bars([("2026-06-23", 105, 108, 104, 107), ("2026-06-24", 107, 130, 106, 125)])
    ret, end = hr.simulate(b, "2026-06-22", entry=100, stop=93, tp1=116)
    assert end == "tp1" and abs(ret - (116 / 105 - 1 - hr.COST)) < 1e-9  # filled at the 105 open, not 100
    assert hr.simulate(bars([("2026-06-23", 90, 95, 88, 92)]), "2026-06-22", 100, 93, 116) is None


def test_stop_and_target_in_the_same_bar_is_a_stop_and_a_gap_down_pays_the_gap():
    b = bars([("2026-06-23", 100, 101, 99, 100), ("2026-06-24", 100, 120, 90, 100)])
    assert hr.simulate(b, "2026-06-22", 100, 93, 116)[1] == "stop"
    g = bars([("2026-06-23", 100, 101, 99, 100), ("2026-06-24", 85, 86, 80, 82)])
    ret, end = hr.simulate(g, "2026-06-22", 100, 93, 116)
    assert end == "stop" and abs(ret - (85 / 100 - 1 - hr.COST)) < 1e-9
