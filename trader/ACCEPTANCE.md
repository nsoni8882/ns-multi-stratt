# Acceptance — paper trading, RSI(2) on AMZN and AAPL

Written 2026-10-10, **before any live trade existed.** That is the point: a bar set after the
numbers arrive is not a bar.

## What was measured before shipping

`research/rsi2/rsi2_edge_backtest.py`, Yahoo adjusted daily closes from 2000-01-01, 5 bps per
round trip, 2,000 matched random-entry simulations.

| | trades | bps/trade | win % | t | p vs random | max DD | positive years |
|---|---|---|---|---|---|---|---|
| AMZN | 232 | +150.1 | 75.9% | 5.53 | 0.002 | −27.7% | 19/24 |
| AAPL | 245 | +117.5 | 75.1% | 5.10 | 0.010 | −32.4% | 23/26 |

Leave-one-year-out: dropping AMZN's best year leaves +130.0 bps; dropping AAPL's leaves
+110.1. So the result is not one event — the trap `research/FINDINGS.md` describes.

The rule the live bot runs is validated three ways, each by a committed test:
`trader/tests/test_rule_matches_backtest.py` pins it to the pandas backtest's entry signals
over ~6,700 bars per symbol, and `trader/tests/test_rule_matches_pine.py` pins it to the
TradingView strategy trade for trade (AMZN 199, AAPL 214 — identical entry bars, prices, bars
held and exit reasons).

**Known weakness, recorded now so it is not discovered as a surprise later:** both names ran
well below their lifetime average in the most recent years — AMZN +38.3 bps (2024) and +52.4
(2025), AAPL +60.8 (2025) and +35.6 (2026). Still positive, roughly a third the magnitude.
This may be decay or may be two quiet years. The live record is how we find out.

## How many trades a verdict needs

Exposure is ~12–15% of sessions per name, so the two together fire roughly **20 round trips a
year**. A verdict needs about **30 round trips — call it 18 months.** Until then
`evaluation.verdict` stays `null` and the page reports the record without a conclusion.

Reporting a verdict sooner would be reading noise, and this repo has been wrong that way
before.

## What would force a change

| Observation, over 30+ round trips | What changes |
|---|---|
| Realised bps/trade more than one standard error below +150 (AMZN) / +117 (AAPL) | Revisit the rule, starting from the 2024–26 decay above. Measure in `research/` first. |
| Decision-vs-fill slippage worse than 15 bps per round trip | Move the run later, or change order type. **Not** a reason to touch the rule. |
| Realised drawdown beyond −27.7% (AMZN) / −32.4% (AAPL) | Revisit sizing, not the thresholds. |
| Win rate holding but bps/trade collapsing | The left tail is widening. Revisit the no-stop decision — and measure it, since a stop cut returns in the original research. |

## What does not count as evidence

- A single bad trade. The worst backtested trades were −16.9% and −18.6%; both are inside
  expectations, not a signal.
- A flat equity curve. Capital idles ~87% of the time by design.
- Fewer than 30 round trips, however tempting the number looks.

## The procedure for a change

1. Measure the variant in `research/`, on the non-overlapping sample, with the per-year table.
2. Record the number — including if it kills the idea, so it is not re-proposed.
3. Add a `Release` entry to `trader/params.py:HISTORY` with the new fingerprint.
4. The ledger then splits at that date on `rules_version`, and `trader/evaluate.py` reports
   the two generations separately rather than blending them.
