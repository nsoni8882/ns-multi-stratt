# RSI(2) reversion — the research behind the paper-trading tab

These files arrived from a separate session as a handoff and were the only copies in
existence, in no version control anywhere. They are the provenance for `trader/` and for
`docs/superpowers/specs/2026-10-10-paper-trading-rsi2-design.md`.

| File | What it is |
|---|---|
| `rsi2_edge_backtest.py` | The reproducible backtest and randomization test. Re-downloads its own data: `.venv/bin/python research/rsi2/rsi2_edge_backtest.py AMZN AAPL SPY`. This is what produced the numbers in the spec and in `trader/ACCEPTANCE.md`. |
| `rsi2_reversion_edge.pine` | TradingView indicator, Pine v5. BUY/SELL labels, the 200-SMA, in-position shading and grey dots on trend-gate rejections. For checking signals by eye on a chart. |
| `rsi2_reversion_strategy.pine` | The same rule as a TradingView `strategy()`, pre-set to 0.025%/side with `process_orders_on_close=true`. **`trader/tests/test_rule_matches_pine.py` validates the live rule against this file** -- it transcribes this state machine and asserts identical trade lists (AMZN 199, AAPL 214). If you change this file, that test is what tells you the live bot no longer matches it. |

A fourth file, `alpaca_rsi2_bot.py`, was the original stdlib prototype of the live runner on a
ten-ETF watchlist. It was deleted when `trader/` superseded it: keeping a second runnable bot
that submits orders on a different watchlist is a hazard rather than provenance. What was
load-bearing in it -- why market-on-close, why the run must beat 15:50 ET, why `end` is held
16 minutes back -- is recorded in the spec's §3 and in `trader/alpaca.py`.

The published research page, with every chart and caveat:
https://claude.ai/artifact/1xd3S9NBKqwaQqQN3rnMRb

## Method notes worth preserving

Each cost real work and is easy to get wrong on a second pass.

- The honest metric is **return per day held**, measured against the same asset's
  unconditional drift. Raw CAGR flatters or buries a low-exposure signal.
- **A win rate proves nothing alone.** Being long in a rising market wins most days too. The
  randomization test -- matched trade count and holding period, random entry days -- is what
  separates the signal from the drift. Keep it in any new asset test.
- **The 200-day gate is load-bearing.** The same trigger below the 200-day earned more per
  trade (77 bps on SPY) with a 24% drawdown and a Sharpe of 0.11.
- **Entry-delay robustness** is what proves the edge is not a closing-print artifact, and it
  is what justifies the live bot deciding on a partial 15:25 bar.
- Eight variants were screened in-sample on SPY 2000-2014; those first numbers carry selection
  bias. Everything reported afterwards is out-of-sample or a different asset.
- **It does not exist in FX.** GBP/USD measured 11 bps/trade gross -- negative after a 10 bps
  round trip. Measured and killed; do not re-propose it.
