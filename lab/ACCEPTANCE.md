# The bar an intraday strategy has to clear

Written 2026-10-15, before any strategy had been run. A bar set after the numbers arrive is
not a bar. The thresholds live in `lab/config.py` and are fingerprinted; this file says why.

A strategy passes only if **all** hold on net-of-cost results, judged on development data:

1. **Enough evidence:** at least 400 trades on at least 150 distinct days.
2. **Positive expectancy** on the day-level series. The day is the unit, not the trade:
   trades on one day share a market, so trade-level t-stats run far too high. **And positive
   per trade** (added 2026-10-16): the day mean weights a quiet day like a crowded one, but money
   follows the trades, so a strategy that wins quiet days and loses crowded ones must not pass.
   Found on the deep VWAP stretch: +3.7 bps on the day mean, -6.0 bps per trade.
3. **Deflated t:** the day-level t must reach `max(2.5, E[max t over N null trials])`, where N is
   the number of strategies ever evaluated (the trial ledger). Every idea tried — kept or
   rejected — raises the bar for the next, so searching harder cannot manufacture a pass.
4. **Both halves positive** when development is split in time.
5. **No single year carries it:** drop the best year, expectancy stays positive (needs 2+ years).
6. **Cost stress:** with costs doubled, expectancy is still positive, on both the day mean and
   the per-trade mean.
7. **Sealed holdout:** a fixed window (`HOLDOUT_START` in config, currently 2026-04-15) is never read by search or by the LLM. Only if
   1-6 pass is the holdout opened, once per strategy, and it must show at least 30 trades,
   positive expectancy, and at least half of development's. The caller sees pass/fail, not numbers.
   After 5 looks at a window it is burned. Rolling it forward means changing `HOLDOUT_START` and adding a Release entry; looks are counted per window, so the roll is explicit and recorded, never implicit.

A strategy fingerprint can be evaluated once. A rejected fingerprint is recorded, not retried
with a nudged threshold — nudging produces a new fingerprint, a new trial, and a higher bar.
"No strategy found" is a valid outcome of the lab.

## What this does not claim

The deflated threshold is the expected maximum of N independent null t-statistics, in the
spirit of the Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014). It is not that exact
statistic, and trials are not truly independent, so it is an approximation to be read as
"the bar rises with the search", not as a p-value.
