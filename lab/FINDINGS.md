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
