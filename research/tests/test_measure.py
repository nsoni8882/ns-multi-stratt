import numpy as np
import pandas as pd
import pytest

from research.measure import Row, independent, pick_tickers, scan_ticker, stats, to_markdown
from scanner.strategies.trend_pullback import MIN_BARS, VARIANTS, TrendPullbackConfig
from scanner.tests.conftest import make_df

HORIZON = 20


def _row(ticker="AAA", bar=0, side="BUY", conviction="standard", fwd=0.0, baseline=0.0):
    return Row(ticker, bar, side, conviction, fwd, baseline)


def test_independent_thins_overlapping_windows_per_ticker_and_side():
    rows = [_row(bar=b) for b in (0, 5, 19, 20, 25, 40)]
    assert [r.bar for r in independent(rows, HORIZON)] == [0, 20, 40]


def test_independent_keeps_overlaps_from_different_tickers_and_sides():
    rows = [_row(bar=0), _row(bar=1, ticker="BBB"), _row(bar=1, side="SELL")]
    assert len(independent(rows, HORIZON)) == 3


def test_stats_alpha_is_measured_against_the_per_ticker_baseline():
    rows = [_row(bar=b * 50, fwd=0.03, baseline=0.01) for b in range(10)]
    s = stats(rows, HORIZON)
    assert s["mean"] == pytest.approx(0.03) and s["baseline"] == pytest.approx(0.01)
    assert s["alpha"] == pytest.approx(0.02)
    assert s["win"] == 1.0
    assert s["n"] == 10 and s["n_independent"] == 10  # already spaced apart


def test_stats_independent_sample_is_smaller_when_signals_cluster():
    rows = [_row(bar=b, fwd=0.01) for b in range(30)]
    s = stats(rows, HORIZON)
    assert s["n"] == 30 and s["n_independent"] == 2  # bars 0 and 20


def test_stats_of_no_rows_is_just_a_zero_count():
    assert stats([], HORIZON) == {"n": 0}


def test_stats_t_is_nan_when_alpha_has_no_spread():
    """A constant alpha has zero variance -- report NaN rather than an infinite t."""
    s = stats([_row(bar=b * 50, fwd=0.02) for b in range(5)], HORIZON)
    assert np.isnan(s["t_naive"])


def _uptrend(n=MIN_BARS + 240, drift=0.006, drop=0.02, every=45, length=7):
    """A net uptrend that keeps correcting: `length` sharp down bars every `every` bars, so
    RSI genuinely dips under 40 and crosses back -- which is the setup being measured."""
    out, price = [], 100.0
    for i in range(n):
        price *= (1 - drop) if (i % every) < length else (1 + drift)
        out.append(price)
    return out


def test_scan_ticker_finds_signals_and_scores_a_full_forward_window():
    df = make_df(_uptrend())
    rows = scan_ticker(df, VARIANTS["shipped"], HORIZON)
    assert rows, "the synthetic uptrend should produce pullback signals"
    assert all(r.bar >= MIN_BARS for r in rows)
    assert all(r.bar < len(df) - HORIZON for r in rows)  # never scored without a full window
    assert all(np.isfinite(r.fwd) for r in rows)


def test_scan_ticker_returns_nothing_without_enough_history():
    assert scan_ticker(make_df(_uptrend(n=MIN_BARS + HORIZON)), VARIANTS["shipped"], HORIZON) == []


def test_scan_ticker_forward_return_matches_the_raw_close_ratio():
    df = make_df(_uptrend())
    rows = scan_ticker(df, VARIANTS["shipped"], HORIZON)
    close = df["close"].to_numpy(dtype=float)
    r = rows[0]
    assert r.fwd == pytest.approx(close[r.bar + HORIZON] / close[r.bar] - 1.0)


def test_gated_variants_can_only_ever_remove_shipped_signals():
    """Every gate is a filter on the shipped rule, never a source of new signals."""
    df = make_df(_uptrend())
    shipped = {r.bar for r in scan_ticker(df, VARIANTS["shipped"], HORIZON) if r.side == "BUY"}
    assert shipped, "fixture must fire under the shipped rule for this to mean anything"
    for cfg in (VARIANTS["adx20"], VARIANTS["adx25"], VARIANTS["rising200"]):
        gated = {r.bar for r in scan_ticker(df, cfg, HORIZON) if r.side == "BUY"}
        assert gated <= shipped

    blocked = scan_ticker(df, TrendPullbackConfig(adx_min=99), HORIZON)
    assert [r for r in blocked if r.side == "BUY"] == []  # a gate that nothing can pass


def test_a_lower_rsi_trigger_moves_the_entry_rather_than_filtering_it():
    """rsi35 is not a subset of rsi40: RSI crosses 35 on its way back up before it crosses
    40, so the deeper level buys the same pullback a couple of bars earlier and cheaper.
    Read its alpha as a different entry, not as a stricter filter."""
    df = make_df(_uptrend())
    shipped = sorted(r.bar for r in scan_ticker(df, VARIANTS["shipped"], HORIZON) if r.side == "BUY")
    deeper = sorted(r.bar for r in scan_ticker(df, VARIANTS["rsi35"], HORIZON) if r.side == "BUY")
    assert len(deeper) == len(shipped)
    assert all(d < s for d, s in zip(deeper, shipped))
    assert not set(deeper) & set(shipped)


def test_tiered_variant_keeps_the_same_signals_and_only_relabels_them():
    df = make_df(_uptrend())
    shipped = sorted(r.bar for r in scan_ticker(df, VARIANTS["shipped"], HORIZON) if r.side == "BUY")
    tiered = scan_ticker(df, VARIANTS["tiered"], HORIZON)
    assert sorted(r.bar for r in tiered if r.side == "BUY") == shipped
    assert {r.conviction for r in tiered if r.side == "BUY"} - {"high", "standard", "low"} == set()


def test_pick_tickers_is_deterministic_and_spread_across_the_alphabet():
    universe = pd.DataFrame({"ticker": [f"{a}{b}" for a in "ABCDEFGHIJ" for b in "XYZ"]})
    picked = pick_tickers(10, universe)
    assert len(picked) == 10 and picked == pick_tickers(10, universe)
    assert len(set(picked)) == 10
    assert picked[0][0] == "A" and picked[-1][0] == "J"  # not a block of A names


def test_pick_tickers_returns_everything_when_asked_for_more_than_exists():
    universe = pd.DataFrame({"ticker": ["BBB", "AAA", "CCC"]})
    assert pick_tickers(99, universe) == ["AAA", "BBB", "CCC"]


def test_to_markdown_renders_a_row_per_leg():
    results = {"shipped": {"BUY": stats([_row(fwd=0.01)] * 1, HORIZON), "SELL": {"n": 0}, "by_conviction": {}}}
    meta = {"tickers": 3, "years": 12, "horizon": 20, "bars": 9000, "generated": "2026-10-03"}
    out = to_markdown(results, meta)
    assert "| shipped | BUY |" in out and "| shipped | SELL | 0 |" in out
    assert "3 S&P names, 12y of daily bars" in out


def test_to_markdown_notes_the_overlap_caveat():
    """The naive t-stat is the main trap in this measurement; the report must say so."""
    meta = {"tickers": 1, "years": 12, "horizon": 20, "bars": 1, "generated": "2026-10-03"}
    out = to_markdown({}, meta)
    assert "overlap" in out.lower() and "ignored" in out.lower()
