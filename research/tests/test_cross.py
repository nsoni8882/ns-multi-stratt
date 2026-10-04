"""The cross-sectional harness. A ranking bug would not crash, it would quietly produce a
plausible table, so the panel mechanics are pinned here."""
import numpy as np
import pandas as pd
import pytest

from research import cross


def panel_of(close: dict, volume: dict | None = None, periods: int | None = None) -> cross.Panel:
    n = periods or len(next(iter(close.values())))
    idx = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    c = pd.DataFrame({k: pd.Series(v, index=idx, dtype=float) for k, v in close.items()})
    v = pd.DataFrame({k: pd.Series(vv, index=idx, dtype=float) for k, vv in (volume or {}).items()}) \
        if volume else pd.DataFrame(1.0, index=idx, columns=c.columns)
    return cross.Panel(close=c, volume=v)


def test_momentum_is_the_return_over_the_window_ending_skip_bars_ago():
    p = panel_of({"A": [1, 2, 4, 8, 16]})
    assert cross.momentum(p.close, 2, 0)["A"].iloc[4] == pytest.approx(3.0)  # 16/4 - 1
    assert cross.momentum(p.close, 2, 1)["A"].iloc[4] == pytest.approx(3.0)  # 8/2 - 1


def test_leaders_rank_each_date_against_that_date_only(monkeypatch):
    monkeypatch.setattr(cross, "MIN_NAMES", 2)
    # B doubles while A crawls, so B leads from the bar the window covers the move.
    p = panel_of({"A": [10, 10, 10, 10], "B": [10, 10, 10, 20]})
    lead = cross.leaders(p, cross.CrossConfig(lookback=1, rank_min=0.9))
    assert bool(lead["B"].iloc[3]) and not bool(lead["A"].iloc[3])


def test_a_date_with_too_few_names_ranks_nobody():
    p = panel_of({"A": [1, 2, 3], "B": [1, 1, 1]})  # 2 names, MIN_NAMES is 100
    assert not cross.leaders(p, cross.CrossConfig(lookback=1)).to_numpy().any()


def test_entry_fires_on_joining_the_leaders_not_every_day_it_leads(monkeypatch):
    monkeypatch.setattr(cross, "MIN_NAMES", 2)
    p = panel_of({"A": [10] * 6, "B": [10, 10, 20, 30, 40, 50]})
    cfg = cross.CrossConfig(lookback=1, rank_min=0.9)
    on_entry = cross.entries(p, cfg)["B"].sum()
    while_leading = cross.entries(p, cross.CrossConfig(lookback=1, rank_min=0.9, on_entry=False))["B"].sum()
    assert on_entry == 1 and while_leading > on_entry


def test_volume_confirmation_rejects_a_quiet_bar(monkeypatch):
    monkeypatch.setattr(cross, "MIN_NAMES", 2)
    n = 30
    p = panel_of({"A": list(np.linspace(10, 10, n)), "B": list(np.linspace(10, 40, n))},
                 {"A": [100.0] * n, "B": [100.0] * (n - 1) + [10.0]})
    cfg = cross.CrossConfig(lookback=5, rank_min=0.9, require_volume_rising=True, on_entry=False)
    assert not bool(cross.entries(p, cfg)["B"].iloc[-1])  # last bar trades a tenth of normal


def test_date_collapse_counts_a_day_once_however_many_names_it_flagged():
    day = pd.Timestamp("2021-06-01", tz="UTC")
    other = pd.Timestamp("2021-06-02", tz="UTC")
    rows = [cross.CrossRow(f"T{i}", 1, 2021, day, "BUY", "standard", 0.10, 0.0) for i in range(40)]
    rows.append(cross.CrossRow("Z", 2, 2021, other, "BUY", "standard", -0.10, 0.0))
    c = cross.date_collapsed(rows)
    assert c["n_dates"] == 2  # not 41
    assert c["alpha_by_date"] == pytest.approx(0.0)  # +10% day and -10% day, equally weighted


def test_halves_split_by_date_not_per_ticker():
    dates = pd.date_range("2020-01-01", periods=4, freq="D", tz="UTC")
    rows = [cross.CrossRow("A", i, 2020, d, "BUY", "standard", 0.0, 0.0) for i, d in enumerate(dates)]
    first, second = cross.halves(rows)
    assert [r.date for r in first] == list(dates[:2])
    assert [r.date for r in second] == list(dates[2:])


def test_drop_best_year_removes_the_year_that_flatters_it():
    rows = ([cross.CrossRow("A", 1, 2020, pd.Timestamp("2020-01-01", tz="UTC"), "BUY", "standard", 0.5, 0.0)]
            + [cross.CrossRow("A", 2, 2021, pd.Timestamp("2021-01-01", tz="UTC"), "BUY", "standard", 0.01, 0.0)])
    year, rest = cross.drop_best_year(rows)
    assert year == 2020 and [r.year for r in rest] == [2021]


def test_score_uses_the_same_forward_window_and_baseline_shape_as_measure(monkeypatch):
    monkeypatch.setattr(cross, "MIN_NAMES", 2)
    monkeypatch.setattr(cross, "WARMUP", 2)
    n = 20
    p = panel_of({"A": [10.0] * n, "B": [10.0 + i for i in range(n)]})
    # on_entry=False so the fixture produces more than the single joining bar, which the
    # warm-up would otherwise cut.
    rows = cross.score(p, cross.CrossConfig(lookback=1, rank_min=0.9, on_entry=False), horizon=2)
    assert rows and all(r.side == "BUY" for r in rows)
    r = rows[0]
    i = p.close.index.get_loc(r.date)
    assert r.fwd == pytest.approx(p.close[r.ticker].iloc[i + 2] / p.close[r.ticker].iloc[i] - 1)
