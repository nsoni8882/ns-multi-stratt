import numpy as np
import pandas as pd

from lab import orderflow_probe as op


def ts(*seconds):
    base = pd.Timestamp("2026-10-16T14:00:00Z")
    return [base + pd.Timedelta(seconds=s) for s in seconds]


def test_lee_ready_classifies_by_midquote_and_tick_rule():
    quotes = pd.DataFrame({"t": ts(0), "bp": [100.0], "ap": [100.10]})  # mid 100.05
    trades = pd.DataFrame({"t": ts(1, 2, 3), "p": [100.10, 100.00, 100.05], "s": [10, 20, 30]})
    out = op.classify(trades, quotes)
    # above mid -> buy; below mid -> sell; at mid -> tick rule (100.00 to 100.05 is an uptick)
    assert list(out["side"]) == [1, -1, 1]
    assert list(out["size"]) == [10, 20, 30]


def test_imbalance_is_signed_volume_share_and_forward_return_is_bps():
    signed = pd.DataFrame({"t": ts(5, 10, 70), "size": [30.0, 10.0, 60.0], "side": [1, -1, -1]})
    minutes = pd.date_range("2026-10-16T14:00:00Z", periods=10, freq="1min")
    mids = pd.Series(np.linspace(100.0, 101.0, 10), index=minutes)
    m = op.minute_imbalance(signed, mids)
    first = m.loc[pd.Timestamp("2026-10-16T14:00:00Z")]
    assert np.isclose(first["imbalance"], (30 - 10) / 40)
    end = mids.resample("1min").last().ffill()
    expected = (end.iloc[6] / end.iloc[1] - 1) * 1e4
    assert np.isclose(first["fwd_bps"], expected)


def test_stats_reports_non_overlapping_rank_correlation():
    n = 200
    imb = np.linspace(-1, 1, n)
    m = pd.DataFrame({"imbalance": imb, "fwd_bps": imb * 2.0},
                     index=pd.date_range("2026-10-16T14:00:00Z", periods=n, freq="1min"))
    res = op.stats(m)
    assert res["n"] == n // op.THIN
    assert res["spearman"] > 0.99
    assert res["top_fifth_bps"] > res["bottom_fifth_bps"]
