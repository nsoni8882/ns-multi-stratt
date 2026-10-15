# Intraday Lab — foundation (sub-project 1 of 4)

Written 2026-10-15. Status: **draft for review.** Paper money only (Alpaca paper endpoint); no real money anywhere.

## Intent

Build a foundation that can *test, trade and retire* intraday strategies (5- and 15-minute bars) on
an Alpaca **paper** account, and keep looking until something survives honest testing. An LLM,
run periodically by the owner through a `/lab` skill, proposes, inspects and adapts strategies.
Deterministic code, not the LLM, decides whether anything passes.

Success is **not** "a strategy that backtests well." Success is: every idea gets a fair, costed,
deflated verdict; nothing reaches paper money without clearing the gate and the owner's approval;
and "no strategy found" is a valid, recorded outcome. A loop that cannot return that answer will
eventually overfit its way to a false positive — the trap `research/ACCEPTANCE.md` already records.

## Decomposition

| # | Sub-project | Status |
|---|---|---|
| **1** | **Intraday data, costed backtester, overfitting gate, trial ledger, strategy-spec format, lab.json contract** | **this spec** |
| 2 | Shadow mode (signals, no orders) and the paper executor (brackets, intraday loop workflow) | later spec |
| 3 | The `/lab` skill and proposal workflow | later spec |
| 4 | The **Lab** tab (web) | later spec; its data contract is fixed here |

Each later piece gets its own spec → plan. Sub-project 1 must be useful alone: it can reject every
idea before any order exists.

## Universe: a fixed liquid set, never "all US stocks"

**Recommendation: the 50 most liquid S&P 500 names by trailing dollar volume, with membership
frozen per year (point-in-time), as the research universe. S&P 500 is the robustness check. All US
stocks is out.**

Why not all US stocks:
- **Costs.** Spread on illiquid names routinely exceeds any 5-minute edge. The ORB paper's headline
  came from charging no spread or slippage; an independent replication found net zero. Wide universes
  mostly add names where the cost model, not the strategy, decides the result.
- **Multiple testing.** Strategies × parameters × symbols multiplies the trial count. A wider
  universe raises the deflated bar and buys false positives, not information.
- **Fills.** Paper fills ignore queue position and impact. That flatters thin stocks most.
- **Data.** ~8,000 symbols × 78 bars × 252 days × years is hundreds of millions of rows to fetch
  within Alpaca's rate limits, for names we could not trade credibly anyway.
- **Survivorship.** "All stocks today" excludes the delisted; point-in-time membership of a small
  liquid set is tractable, the full market is not.

"Stocks in Play" style selection (unusual relative volume that day) is a *strategy filter* inside
the universe, not a wider universe. The universe is a versioned config, fingerprinted like params.

## Components

All under a new `lab/` package. Stdlib-only where it sits on the order path later; the research side
may use pandas, like `research/`.

1. **`lab/data.py`** — Alpaca historical 5-min bars, SIP feed with the 16-minute end holdback (same
   mechanism as `trader/alpaca.py`), cached to `lab/.cache/` (gitignored). Adjusted for splits and
   dividends. Session-aware: regular hours only, early-close days from Alpaca's calendar. Bars
   carry `close_time`; only **closed** bars are ever passed to a strategy (repo rule).
   15-minute bars are resampled from 5-minute, never fetched separately, so the two cannot disagree.
2. **`lab/spec.py`** — the strategy-spec format. A strategy is a declarative, JSON-serialisable
   spec: `family` (from a fixed registry) + `params` + `universe filter` + `risk` (stop, target,
   max hold in bars, max concurrent, size as % of **equity**). LLM-proposed ideas arrive as specs,
   never as code. A spec's `fingerprint` hashes its canonical JSON, mirroring `rules_version()`.
3. **`lab/families/`** — the registry. Initial families: opening-range breakout, VWAP reversion,
   intraday RSI(2) reversion, gap fade. Each is a pure function over closed bars. Adding a family
   is a normal code change with tests, not something the LLM does at run time.
4. **`lab/costs.py`** — the cost model. Per-side spread as a function of symbol liquidity tier,
   plus a slippage term, plus commission (0 on Alpaca, kept explicit). Defaults are conservative,
   live in code, and are fingerprinted. Fills happen at the **next bar's open**, never the signal
   bar's close.
5. **`lab/backtest.py`** — event-driven backtest over the universe: one position per name, session
   flat by close unless the spec says otherwise, concurrency cap, equity-based sizing. Emits a trade
   list (symbol, entry/exit bar and price, side, bars held, exit reason, gross/net bps).
6. **`lab/gate.py`** — the deterministic verdict. Written before any numbers exist, in
   `lab/ACCEPTANCE.md`, in the same spirit as the other two acceptance files. A candidate passes only
   if **all** hold on net-of-cost results:
   - positive net expectancy per trade on the non-overlapping sample;
   - **deflated** significance: the t / Sharpe threshold is raised by the running trial count
     (Deflated Sharpe Ratio, Bailey & López de Prado 2014), not a fixed t>2;
   - positive in both halves of a time split, and with the best year dropped (the Feb-2020 check);
   - n_independent trades ≥ a floor set in the acceptance file;
   - survives a cost stress (spread ×2) with expectancy still positive;
   - passes once on a **sealed holdout** (most recent N months, never read by search or the LLM).
   The gate returns pass/fail plus the *non-holdout* diagnostics. The holdout curve is never exposed.
7. **`lab/trials.py`** — the append-only **trial ledger** (`lab/trials.jsonl`, committed). Every
   evaluation — passed or rejected — appends: spec fingerprint, family, params, timestamp, universe
   version, result summary, verdict. The count feeds the deflation. A test pins that the gate reads
   the ledger and refuses to run if the entry could not be appended (no unrecorded trials).
8. **`lab/lifecycle.py`** — the state machine each strategy follows:
   `proposed → backtested → (rejected | shadow) → paper → (kept | tuned | retired)`.
   Transitions out of `rejected`/`retired` are terminal for that fingerprint (recorded, not retried).
   `shadow → paper` requires owner approval, recorded in the state file. Pre-registered **failure
   rules** are attached when a strategy enters `shadow` and cannot be edited afterwards:
   e.g. net expectancy < 0 after N trades; drawdown beyond the backtest's worst; realised slippage
   > k× the assumed cost; realised t more than one s.e. below the backtest. A tripped rule retires
   it automatically; the skill may propose a successor spec, never an exemption.
9. **`lab/export.py`** — writes `lab.json` (below) to the `data` branch path, copied into the build
   by `scan.yml` exactly as `paper-trading.json` is. One path to Pages.

### Protections the LLM cannot cross
`lab/gate.py`, `lab/costs.py`, `lab/ACCEPTANCE.md`, the holdout window, and `lab/trials.jsonl`
append-only semantics are pinned by tests (like `trader/tests/test_workflow.py`): editing a
threshold without a history entry fails the build; the trial ledger never shrinks; the holdout
loader is reachable only from `gate.py`. The `/lab` skill (sub-project 3) is told not to touch them.

## The `lab.json` contract (drives the single new tab)

Fixed now so the Lab tab (sub-project 4) is a pure renderer. Everything the owner asked to see is
here; nothing on the page needs a computation the JSON doesn't carry.

```
lab.json
├─ meta            generated_at, universe_version, cost_model_version, trials_total, holdout_window
├─ account         equity, cash, day_pnl, total_pnl, as_of            (paper account)
├─ equity_curve    [{t, equity, drawdown}]                            (intraday + daily resolution)
├─ summary         net_pnl, return_pct, win_rate, expectancy_bps, profit_factor, sharpe, max_drawdown,
│                  trades, avg_bars_held, exposure_pct              (overall + per strategy)
├─ strategies[]    id, name, family, fingerprint, stage, params, risk, hypothesis, created, stage_since,
│                  failure_rules[{rule, threshold, current, status}], backtest{...gate diagnostics},
│                  live{trades, net_pnl, expectancy_bps, win_rate, max_drawdown, t_stat, slippage_vs_assumed},
│                  equity_curve[], history[Release…], verdict, retired_reason
├─ positions[]     active: strategy, symbol, side, qty, entry_time, entry_price, mark, unrealised_pnl,
│                  stop, target, bars_held
├─ trades[]        historical: strategy, symbol, side, entry/exit time+price, bars_held, exit_reason,
│                  gross_bps, cost_bps, net_bps, net_pnl, slippage_bps
├─ breakdowns      pnl_by_strategy, pnl_by_symbol, pnl_by_hour_of_day, pnl_by_weekday,
│                  returns_histogram, exit_reason_counts, daily_pnl[] (calendar heatmap)
├─ trials          the ledger: [{when, fingerprint, family, params, verdict, reason}]  (searchable)
├─ charts          per active/recent trade: bars (5m OHLC), entry/exit markers, VWAP, indicators used
└─ runs[]          every executor/loop run: time, strategy, decision, orders, errors  (like paper_runs)
```

The tab (later spec) maps onto this: KPI strip (equity, day/total P&L, win rate, profit factor,
drawdown); equity + drawdown chart; active-positions table with live P&L; historical-trades table
(filter by strategy/symbol/exit reason); per-trade chart with entries/exits and the strategy's
indicators; strategy cards with stage, failure-rule progress bars and backtest-vs-live comparison;
P&L by hour/weekday/symbol and a daily calendar heatmap; trial-ledger view ("N ideas tried, M
rejected, why"); run log. Existing `Paper*` components (equity curve, positions, trades, runs,
charts) are reused where their shape fits.

A static site means the page is a snapshot per publish, not a live feed. Acceptable for paper.

## Testing

- Unit: each family on hand-built bar sequences (entry/exit exactly where expected, **no signal on
  a partial bar**, no use of bar `i+1` at bar `i`); cost model arithmetic; fingerprint stability.
- **Lookahead guard:** a test that shifts future bars and asserts earlier decisions are unchanged,
  run over every registered family. This is the check that makes LLM-proposed specs safe.
- Gate: synthetic random-walk data must fail; a planted edge must pass; a planted edge that exists
  only in one year must fail the drop-best-year rule; the deflation must tighten as trials grow.
- Ledger: append-only, refuses a verdict if the append fails, count monotone.
- Contract: `lab.json` produced from a fixture validates against a schema the web tests share.
- Network smoke test skipped by default, like `test_smoke_network.py`.

## Out of scope here
Order submission, shadow runs, the intraday workflow, the skill, the web tab. Also out: shorting,
options, leverage; sizing off `buying_power` (always equity, per the trader's rule).

## Open items to confirm during planning
- Exact Alpaca free-tier historical limits and 5-min history depth (not confirmed in research).
- Whether the pattern-day-trader rule applies to the paper account at the intended equity — this
  caps round trips per day and may force the holdout/sizing choices.
- The cost-model defaults per liquidity tier, to be measured (quoted spread from Alpaca quotes on a
  sample) before they are fixed, then recorded in `FINDINGS`-style notes.

## Amendments made during implementation (2026-10-15)
- `breakdowns` live inside each strategy in `lab.json`, not at the top level.
- Per-trade chart bars (`charts`) are deferred to the Lab-tab plan; they need stored bars.
- The deflated threshold is the expected maximum of N null t-statistics (an approximation in the
  spirit of the Deflated Sharpe Ratio); `lab/ACCEPTANCE.md` says so.
- The holdout is enforced by the gate being the only module that calls `BacktestResult.after`
  (pinned by `lab/tests/test_sealed.py`), not by a separate data loader.
- After review, the holdout became a fixed window (`HOLDOUT_START` in `lab/config.py`) instead of
  "the latest six months"; looks are counted per window and each ledger row records its window.
