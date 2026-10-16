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
