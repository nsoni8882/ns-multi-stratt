# What the lab has measured

One entry per idea, pass or fail, with the numbers. A killed idea is recorded here so it is
not re-proposed. The trial ledger (`trials.jsonl` on the `data` branch) is the machine record;
this is the interpretation. Costs are the conservative placeholders in `config.py` (1.5 bps a
side for the top 10 names, 3.0 for the rest) until real spreads are sampled.

## 2026-10-15: Opening-range breakout, stocks in play  (7baf247790f4) — REJECTED

Hypothesis (written before the run): names breaking their first 15-minute high on heavy
relative volume keep going into the late morning; the published version reports a gross edge,
so the question was whether it survives spread and slippage.

Spec: ORB, 5-minute bars, 3-bar opening range, relative-volume filter 1.5x over 14 days,
enter before bar 30, stop 0.6%, target 1.2%, max hold 40 bars. 92-symbol point-in-time liquid
universe, about 1,460 trading days, 4,597 trades. Trial 1 of the ledger; holdout not opened.

| | |
|---|---|
| Net per day | -7.6 bps, t = -5.15 (the bar was t >= 2.50) |
| Both halves | -6.3 / -8.9 bps |
| Without the best year (2021) | -9.5 bps |
| Doubled costs | -13.0 bps |
| Per trade | gross about 0.0 bps, costs 5.5 bps, net -5.5 bps; win rate 37% |
| Exits | stop 2,507 (-65 bps avg), target 1,047 (+115), time 1,038 (+18) |

What it says: there is **no gross edge** for this rule on this universe. Gross return per
trade is zero, so costs are not the cause of the loss, only the amount of it. Of the
trades that reached either the stop or the target, 30% reached the target, which is the 1-in-3
a driftless price gives a 2:1 target-to-stop payoff.
This agrees with the independent replication that found the gross edge gone once costs are
charged. Not re-proposed: a wider stop or a different threshold on the same entry, since there
is no gross edge to preserve. A different mechanism would be a new idea with its own written reason.

## 2026-10-16: Gap-down fade, large caps  (e0370326ed39) — REJECTED

Hypothesis (written before the run): a liquid large cap opening more than 1% under yesterday's
close overshoots in a thin pre-market, and part of the gap is recovered in the first two hours.

Spec: gap fade, 5-minute bars, gap of 1% or more, enter at the second bar, stop 1.5%, target
1.5%, max hold 24 bars. Same 92-symbol universe, 1,447 trading days, 5,040 trades. Trial 2 of
the ledger; holdout not opened.

| | |
|---|---|
| Net per day | -7.6 bps, t = -3.13 (the bar was t >= 2.50) |
| Both halves | -7.0 / -8.3 bps |
| Without the best year (2023) | -9.0 bps |
| Doubled costs | -12.9 bps |
| Per trade | gross -1.1 bps, costs 5.2 bps, net -6.3 bps; win rate 49% |
| Exits | stop 1,476 (-155 bps avg), target 1,392 (+145), time 2,172 (-2) |

What it says: again **no gross edge**. Stops and targets are hit almost equally often (1,476 vs
1,392) at equal distances, which is what a driftless price does, and the trades that reach
neither (43%) average zero. Gap-downs in these names are not recovered on average. Two
rejections in a row on mid-sized stretches say large-cap price at 5-minute resolution carries
no tradeable drift for these rules at these costs; the remaining ideas should be judged against
that, not against the hope that the next threshold is the one.

## 2026-10-16: VWAP reversion, deep stretches only  (943231f1400b) — REJECTED (closest so far)

Hypothesis (written before the run): VWAP-benchmarked execution pulls a stock that is well under
VWAP back toward it; only a deep (1.2%) stretch after the first hour is large enough to clear a
fixed-bps cost. Spec: VWAP reversion, 5-minute bars, 1.2% below VWAP, bars 12 to 60, stop 2%,
target 1%, max hold 36 bars. Same universe, 1,654 trading days, 8,614 trades. Trial 3; holdout
not opened.

| | |
|---|---|
| Net per day (each day weighted equally) | +3.7 bps, t = 2.18 (the bar was t >= 2.50) — **fail** |
| Both halves | +2.2 / +5.2 bps — pass |
| Without the best year (2023) | +2.1 bps — pass |
| Doubled costs | -1.6 bps — **fail** |
| Per trade (each trade weighted equally) | gross -0.7 bps, costs 5.3 bps, **net -6.0 bps**; win rate 56% |
| Exits | target 3,508 (+95), stop 1,284 (-205), time 2,728 (-35), session 1,094 (-24) |

**The two expectancies disagree, and that is the finding.** Days with 1 to 4 trades average +12
to +20 bps, days with 5 to 8 trades +1.5 bps, and days with 9 or more trades **-29.6 bps**. 81% of
the trades happen on days with 5 or more. Many names stretch below VWAP at once on a market-wide
down day, and then they all keep falling together: the losses are one correlated event, not
independent trades. The gate's day-level mean counts a quiet +20 day the same as a busy -30
day, so it reads the strategy as marginally positive; the money (trade-weighted, and the equity
curve) says it loses.

This exposes a gap in the gate rather than a reason to loosen it: **positive_expectancy and
cost_stress are measured on the equal-weight day mean, so a strategy that loses money per trade
can still pass them.** It failed anyway here (t, cost stress), so no verdict changes. Proposed to
the owner: add a per-trade expectancy check. It can only make the gate stricter.

A regime filter (trade only when few names are stretched) would be a new idea formed from this
diagnostic, in exactly the way the lab warns about; it needs its own written reason and, if run,
a new trial. It is not proposed here.

## 2026-10-16: the gate now also requires a profit per trade (rules 1.2.0)

Added after the deep VWAP stretch, with the owner's approval: `positive_per_trade`, and the
cost-stress check now takes the worse of the day mean and the per-trade mean. It only makes the
gate stricter. The three earlier verdicts stand (all rejected, none passed the other checks).
The fingerprint now covers the list of checks, so adding or removing one cannot happen without a
`HISTORY` entry. Older ledger rows carry the earlier rules version; the Lab tab shows the new
check as "not measured then" for them rather than as a pass.

## 2026-10-16: Intraday RSI(2) reversion, 15-minute bars  (cb2cfd0510ae) — REJECTED

Hypothesis (written before the run): the daily RSI(2) overshoot (+117 to +150 bps a trade on
AMZN and AAPL) is partly given back on 15-minute bars too, bought only above a two-day average.
Spec: RSI(2) below 5, trend average 52 bars, enter before bar 22, stop 0.8%, target 1.0%, max
hold 8 bars. Same universe, 1,754 trading days, 13,597 trades. Trial 4, the first under rules
1.2.0; holdout not opened.

| | |
|---|---|
| Net per day | -2.4 bps, t = -2.89 (the bar was t >= 2.50) |
| Per trade | gross **+0.3 bps**, costs 5.5 bps, net -5.1 bps; win rate 46% |
| Both halves | -3.0 / -1.8 bps; without 2020: -3.1 bps |
| Doubled costs | -10.6 bps |
| Exits | time 6,429 (+2), stop 2,861 (-85), target 1,741 (+95), session 2,566 (-1) |

## Where four ideas leave the lab (4 tried, 0 passed)

| Idea | Gross per trade | Net per trade |
|---|---|---|
| Opening-range breakout, stocks in play | -0.0 bps | -5.5 |
| Gap-down fade | -1.1 | -6.3 |
| VWAP reversion, deep stretches | -0.7 | -6.0 |
| Intraday RSI(2), 15-minute | +0.3 | -5.1 |

**Gross return is zero for all four**, from four different mechanisms. That matters more than
the net figures: the cost model is a placeholder, but no cost assumption rescues a gross edge of
about zero. Even free trading would leave these at roughly break-even, nowhere near t >= 2.5.
The daily RSI(2) edge does not carry down to intraday bars in these names. The evidence so far
favours "no tradeable edge in liquid large caps at 5- and 15-minute resolution for simple rules."
Not re-proposed: any threshold change to these four.

## 2026-10-16: measured spreads vs the cost model

Sampled SIP quotes for 40 symbols (the 10 most liquid and 30 spread across the rest of the
universe), one-minute windows at 10:00, 12:30 and 15:00 ET on 8 full sessions (6 to 15 Oct),
960 windows. Half-spread in bps, median (25th to 75th percentile):

| | Measured half-spread | Model, per side (half-spread + slippage) |
|---|---|---|
| Top 10 ("mega") | 0.95 (0.57 to 1.61) | 1.5 |
| The rest ("large") | 1.89 (1.08 to 3.25) | 3.0 |
| By time: 10:00 / 12:30 / 15:00 | 2.45 / 1.36 / 1.25 | |

The model is about 0.55 bps (mega) and 1.1 bps (large) above the measured half-spread, which
is the slippage allowance, so it is **conservative on average and not wildly so**. Two limits:
spreads at 10:00 are about twice those at 15:00, and the opening bars (09:30 to 09:40), where
the opening-range breakout and gap fade enter, were not sampled and are wider still; and quotes
are not fills, so this ignores impact. The model is therefore kept as is. It is not loosened:
no config change, no new fingerprint. None of the four verdicts depends on it, since gross
return was about zero before costs.

## 2026-10-17: two structural changes, both rejected (6 tried, 0 passed)

Both were written as fewer, larger moves held to the close, to answer "gross about zero, costs
eat the rest". Gross turned slightly positive but too small and too noisy to matter.

| Idea | Trades | Gross per trade | Net per trade | t (bar 2.50) |
|---|---|---|---|---|
| ORB trend day, 15-min, rvol >= 3, hold to close (`07d675ae0386`) | 502 | +6.6 bps | +0.9 | 0.36 |
| Large gap-down (>= 3%), hold to close (`758cd45e4cb6`) | 1,292 | +4.6 bps | -0.6 | 0.15 |

Both failed deflated_t, both_halves, drop_best_year and cost_stress; the gap idea also failed
positive_per_trade. Exits: most trades ride to the session close (+59 and +47 bps), stops cost
-205 and -305 bps, the target is almost never hit (3 and 67 trades). So the result is a small
long drift with fat left-tail stops, not a mechanism. Holdout untouched (0 looks).

Rules out: holding large-cap breakouts or 3% gap-downs to the close, at these stops. Not
re-proposed: any stop/target/threshold change to either. Six different ideas have now had gross
return within about +-7 bps a trade against ~5.5 bps costs: the evidence favours "no tradeable
intraday edge in the top-50 large caps with simple long-only rules".

## 2026-10-19: order-flow imbalance vs the next 5 minutes (killed, AAPL probe)

Read-only probe (`lab.orderflow_probe`, run 39261823929): AAPL, the last 20 sessions, two
windows a day (10:00 and 14:00 ET), 70 one-minute bars per window, 560 observations. Signal:
trade-sign order-flow imbalance in each window. Target: forward return over the next 5 minutes.

| Measure | Value |
|---|---|
| Spearman | 0.027 |
| t | 0.63 (bar 2.50) |
| Top fifth, next 5 min | +0.31 bps |
| Bottom fifth, next 5 min | -1.25 bps |

No significant relationship, and the top-to-bottom spread of about 1.6 bps is below the ~5.5 bps
round-trip cost model. Killed. Not re-proposed: imbalance as a 5-minute predictor for AAPL at
these windows. This was a probe, not a gate trial, so no `trials.jsonl` entry.
