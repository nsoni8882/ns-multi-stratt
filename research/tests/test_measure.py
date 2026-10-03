import numpy as np
import pandas as pd
import pytest

from research.measure import (TARGETS, Row, by_year, era_midpoints, independent, measure, pick_tickers,
                              position, scan_ticker, stats, to_markdown, unconditional)
from scanner.strategies.trend_pullback import MIN_BARS, VARIANTS, TrendPullbackConfig
from scanner.tests.conftest import make_df

# Every call below scores Trend Pullback; the reversal strategy has its own run.
PULLBACK = TARGETS["trend-pullback"]

HORIZON = 20


def _meta(tickers=3, bars=9000):
    return {"tickers": tickers, "years": 12, "horizon": 20, "bars": bars, "generated": "2026-10-03",
            "base": {"n": 400000, "mean": 0.0148, "win": 0.576}}


def _row(ticker="AAA", bar=0, side="BUY", conviction="standard", fwd=0.0, baseline=0.0, year=2020):
    return Row(ticker, bar, year, side, conviction, fwd, baseline)


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
    rows = scan_ticker(df, VARIANTS["shipped"], HORIZON, PULLBACK)
    assert rows, "the synthetic uptrend should produce pullback signals"
    assert all(r.bar >= MIN_BARS for r in rows)
    assert all(r.bar < len(df) - HORIZON for r in rows)  # never scored without a full window
    assert all(np.isfinite(r.fwd) for r in rows)


def test_scan_ticker_returns_nothing_without_enough_history():
    assert scan_ticker(make_df(_uptrend(n=MIN_BARS + HORIZON)), VARIANTS["shipped"], HORIZON, PULLBACK) == []


def test_scan_ticker_forward_return_matches_the_raw_close_ratio():
    df = make_df(_uptrend())
    rows = scan_ticker(df, VARIANTS["shipped"], HORIZON, PULLBACK)
    close = df["close"].to_numpy(dtype=float)
    r = rows[0]
    assert r.fwd == pytest.approx(close[r.bar + HORIZON] / close[r.bar] - 1.0)


def test_gated_variants_can_only_ever_remove_shipped_signals():
    """Every gate is a filter on the shipped rule, never a source of new signals."""
    df = make_df(_uptrend())
    shipped = {r.bar for r in scan_ticker(df, VARIANTS["shipped"], HORIZON, PULLBACK) if r.side == "BUY"}
    assert shipped, "fixture must fire under the shipped rule for this to mean anything"
    for cfg in (VARIANTS["adx20"], VARIANTS["adx25"], VARIANTS["rising200"]):
        gated = {r.bar for r in scan_ticker(df, cfg, HORIZON, PULLBACK) if r.side == "BUY"}
        assert gated <= shipped

    blocked = scan_ticker(df, TrendPullbackConfig(adx_min=99), HORIZON, PULLBACK)
    assert [r for r in blocked if r.side == "BUY"] == []  # a gate that nothing can pass


def test_a_lower_rsi_trigger_moves_the_entry_rather_than_filtering_it():
    """rsi35 is not a subset of rsi40: RSI crosses 35 on its way back up before it crosses
    40, so the deeper level buys the same pullback a couple of bars earlier and cheaper.
    Read its alpha as a different entry, not as a stricter filter."""
    df = make_df(_uptrend())
    shipped = sorted(r.bar for r in scan_ticker(df, VARIANTS["shipped"], HORIZON, PULLBACK) if r.side == "BUY")
    deeper = sorted(r.bar for r in scan_ticker(df, VARIANTS["rsi35"], HORIZON, PULLBACK) if r.side == "BUY")
    assert len(deeper) == len(shipped)
    assert all(d < s for d, s in zip(deeper, shipped))
    assert not set(deeper) & set(shipped)


def test_tiered_variant_keeps_the_same_signals_and_only_relabels_them():
    df = make_df(_uptrend())
    shipped = sorted(r.bar for r in scan_ticker(df, VARIANTS["shipped"], HORIZON, PULLBACK) if r.side == "BUY")
    tiered = scan_ticker(df, VARIANTS["tiered-deep-is-strong"], HORIZON, PULLBACK)
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
    out = to_markdown(results, _meta())
    assert "| shipped | BUY |" in out and "| shipped | SELL | 0 |" in out
    assert "3 S&P names, 12y of daily bars" in out
    assert "57.6% of the time" in out  # the do-nothing benchmark is stated, not left implicit


def test_to_markdown_notes_the_overlap_caveat():
    """The naive t-stat is the main trap in this measurement; the report must say so."""
    out = to_markdown({}, _meta(tickers=1, bars=1))
    assert "overlap" in out.lower() and "ignored" in out.lower()


def test_sell_leg_is_scored_as_a_short_against_cash():
    """A stock rising after a SELL is a loss, and the short's alternative is cash, not
    holding the name it shorts -- otherwise a losing short scores positive alpha whenever
    the stock rose less than its own average."""
    rows = [_row(bar=b * 50, side="SELL", fwd=0.03, baseline=0.05) for b in range(10)]
    s = stats(rows, HORIZON, "SELL")
    assert s["mean"] == pytest.approx(-0.03)  # the short lost 3%
    assert s["baseline"] == 0.0
    assert s["alpha"] == pytest.approx(-0.03)
    assert s["win"] == 0.0


def test_buy_and_sell_legs_score_the_same_row_in_opposite_directions():
    r = [_row(bar=0, fwd=0.04, baseline=0.01)]
    assert stats(r, HORIZON, "BUY")["mean"] == pytest.approx(0.04)
    assert stats(r, HORIZON, "SELL")["mean"] == pytest.approx(-0.04)


def test_position_benchmarks_differ_by_side():
    r = _row(fwd=0.02, baseline=0.015)
    assert position(r, "BUY") == (pytest.approx(0.02), pytest.approx(0.015))
    assert position(r, "SELL") == (pytest.approx(-0.02), 0.0)


def test_era_midpoints_split_the_scored_range_not_the_whole_frame():
    bars = {"AAA": make_df(_uptrend(n=MIN_BARS + 200))}
    mid = era_midpoints(bars, HORIZON, MIN_BARS)
    assert mid["AAA"] == (MIN_BARS + MIN_BARS + 200 - HORIZON) // 2
    assert MIN_BARS < mid["AAA"] < MIN_BARS + 200 - HORIZON


def test_measure_reports_each_cohort_split_into_halves():
    bars = {"AAA": make_df(_uptrend()), "BBB": make_df(_uptrend(drift=0.007))}
    out = measure(bars, ["shipped"], HORIZON, PULLBACK)
    eras = out["shipped"]["eras"]
    assert set(eras) >= {"BUY"}
    assert set(eras["BUY"]) == {"first", "second"}
    assert eras["BUY"]["first"]["n"] + eras["BUY"]["second"]["n"] == out["shipped"]["BUY"]["n"]


def test_to_markdown_includes_the_sub_period_section():
    bars = {"AAA": make_df(_uptrend())}
    out = to_markdown(measure(bars, ["shipped"], HORIZON, PULLBACK), _meta(tickers=1, bars=1))
    assert "Sub-period check" in out and "(first half)" in out and "(second half)" in out


def test_by_year_groups_rows_by_signal_year():
    rows = [_row(bar=0, year=2019, fwd=0.01), _row(bar=50, year=2020, fwd=-0.10),
            _row(bar=100, year=2020, fwd=-0.08)]
    out = by_year(rows, HORIZON)
    assert list(out) == [2019, 2020]
    assert out[2020]["n"] == 2 and out[2020]["mean"] == pytest.approx(-0.09)


def test_scan_ticker_tags_rows_with_the_signal_bar_year():
    df = make_df(_uptrend(), start="2015-01-01")
    rows = scan_ticker(df, VARIANTS["shipped"], HORIZON, PULLBACK)
    assert rows and all(r.year == df.index[r.bar].year for r in rows)


def test_to_markdown_renders_a_per_year_column_per_year_seen():
    bars = {"AAA": make_df(_uptrend(), start="2015-01-01")}
    out = to_markdown(measure(bars, ["shipped"], HORIZON, PULLBACK), _meta(tickers=1, bars=1))
    assert "Per-year alpha by cohort" in out and "2016" in out


def test_unconditional_benchmark_covers_every_scored_bar():
    df = make_df(_uptrend())
    base = unconditional({"AAA": df}, HORIZON, MIN_BARS)
    assert base["n"] == len(df) - HORIZON - MIN_BARS
    assert 0.0 <= base["win"] <= 1.0 and np.isfinite(base["mean"])


def test_unconditional_benchmark_of_too_short_history_is_empty():
    assert unconditional({"AAA": make_df(_uptrend(n=MIN_BARS))}, HORIZON, MIN_BARS) == {"n": 0}


# --- the harness is strategy-agnostic ----------------------------------------------------

REVERSAL = TARGETS["macd-rsi-reversal"]


def _crash_then_bounce(n=400):
    """A long drift up, a sharp crash, then a bounce: the shape the reversal strategy looks
    for, repeated so a 12-year-style frame contains several."""
    out = []
    for _ in range(4):
        up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(80)))
        down = up[-1] * np.cumprod(np.full(12, 0.975))
        out.extend(list(up) + list(down) + [down[-1] * 1.05])
    return out


def test_scan_ticker_scores_the_reversal_strategy_too():
    df = make_df(_crash_then_bounce())
    rows = scan_ticker(df, REVERSAL.variants["shipped"], HORIZON, REVERSAL)
    assert all(r.bar >= REVERSAL.min_bars for r in rows)
    assert all(r.side in ("BUY", "SELL") for r in rows)


def test_a_volume_gate_only_removes_reversal_signals():
    """Every gate is a filter on the shipped rule, so a gated run is a subset. If one ever
    added a signal, the gate would be changing the rule rather than narrowing it."""
    df = make_df(_crash_then_bounce())
    df["volume"] = 1000
    shipped = {r.bar for r in scan_ticker(df, REVERSAL.variants["shipped"], HORIZON, REVERSAL)}
    for label in ("capitulation-2x", "obv-divergence", "mfi-confluence"):
        gated = {r.bar for r in scan_ticker(df, REVERSAL.variants[label], HORIZON, REVERSAL)}
        assert gated <= shipped, label


def test_each_target_keeps_its_own_min_bars():
    assert REVERSAL.min_bars != PULLBACK.min_bars
    assert era_midpoints({"A": make_df([100.0] * 500)}, HORIZON, REVERSAL.min_bars) != \
        era_midpoints({"A": make_df([100.0] * 500)}, HORIZON, PULLBACK.min_bars)
