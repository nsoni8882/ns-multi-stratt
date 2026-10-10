# Paper Trading — RSI(2) reversion on AMZN and AAPL

**Date:** 2026-10-10
**Status:** Design, approved in conversation. Not implemented.
**Supersedes nothing.** Adds a third tab alongside the two screener strategies.

---

## 1. What this is, and what it is not

A third strategy on the dashboard that **places orders** on an Alpaca **paper** account,
long only, on two symbols: AMZN and AAPL. It is the first thing in this repo that takes an
action rather than publishing a list, and the design is shaped mostly by keeping that
action away from everything that already works.

It is not live trading, not a recommendation engine, and not a change to the screener. The
two existing strategies keep their contract exactly: a pure sweep that writes static JSON.

### The rule

Carried unchanged from the validated research in `handoff/` (see §2):

| | |
|---|---|
| Entry | Wilder `RSI(2) < 10` **and** `Close > SMA(200)` → buy at that day's close |
| Exit | `RSI(2) > 65` **or** 10 trading days elapsed → sell at that day's close |
| Direction | Long only. No short leg, no margin. |
| Stop loss | **None, deliberately.** A stop cuts the trades that go on to revert. |
| Sizing | 50% of account equity per name, whole shares only |
| Concurrency | Both names may be held at once; nothing else is traded |
| Cost assumed in backtest | 5 bps per round trip |

Exposure is roughly 12–15% of days per name. This is a capital-efficiency overlay, not a
standalone equity curve, and the page must say so rather than let a flat line read as a
bug.

---

## 2. The evidence, and its limits

Measured 2026-10-10 with `handoff/rsi2_edge_backtest.py` (Yahoo adjusted daily closes,
2000-01-01 → today, 5 bps per round trip, randomization test = 2,000 matched random-entry
simulations with the same trade count and holding period).

| | trades | bps/trade | win % | t | p vs random | max DD | exposure |
|---|---|---|---|---|---|---|---|
| AMZN | 232 | +150.1 | 75.9% | 5.53 | 0.002 | −27.7% | 12.2% |
| AAPL | 245 | +117.5 | 75.1% | 5.10 | 0.010 | −32.4% | 14.6% |
| SPY (reference) | 214 | +61.8 | 81.3% | 5.31 | 0.002 | −16.4% | 11.0% |

**Per-year check** (this repo's second trap — a pooled t-stat that is one event):

- AMZN: positive in **19 of 24** years. Dropping its best year (2007) leaves +130.0 bps.
- AAPL: positive in **23 of 26** years. Dropping its best year (2010) leaves +110.1 bps.

So the result is not one event. Both survive leave-one-year-out comfortably.

**Three limits that must not be quietly dropped:**

1. **The edge looks weaker recently.** AMZN earned +38.3 bps (2024) and +52.4 (2025)
   against +150 lifetime; AAPL +60.8 (2025) and +35.6 (2026) against +117. Still positive,
   still mostly winning, but roughly a third of the historical magnitude. This may be decay,
   may be two quiet years. The live ledger (§5) is how we find out, and it is the reason
   the evaluation loop is part of the first release rather than a later addition.
2. **The left tail is the price of the 75% win rate.** Worst single trades: AMZN −16.9%,
   AAPL −18.6%. With a 50% slice that is roughly −8% to −9% of the account on one trade.
   There is no stop, by design.
3. **Two names are not a universe.** AMZN and AAPL existed throughout and were picked
   because they backtest well, which is survivorship and selection both. The published
   research validated this rule on index ETFs; these two are a narrower, more concentrated
   bet than the evidence base behind the rule.

Backtest results are not a forecast. This is research, not investment advice.

### Provenance

| Source | What it gives |
|---|---|
| `handoff/rsi2_edge_backtest.py` | The reproducible backtest. Re-downloads its own data. |
| `handoff/alpaca_rsi2_bot.py` | Working prototype of the live runner. Source of the design decisions in §4. |
| `handoff/rsi2_reversion_*.pine` | TradingView indicator and strategy. Not used here; kept for cross-checking. |
| `https://claude.ai/artifact/1xd3S9NBKqwaQqQN3rnMRb` | The original published research page: all charts, tables and caveats. |

---

## 3. Architecture

A new top-level package, beside `scanner/` and `research/`:

```
trader/
  rule.py        # Wilder RSI(2), SMA(200), the entry/exit decision. Pure, stdlib only.
  alpaca.py      # HTTP client: account, clock, calendar, bars, positions, orders.
  run.py         # the decision loop. Entry point: python -m trader.run
  export.py      # builds paper-trading.json from account + ledger + rule state
  state.py       # entry dates and opening balance; persisted on the `data` branch
  evaluate.py    # live record vs backtested expectation
  ACCEPTANCE.md  # the bar, written before the numbers exist
  tests/
```

### Why a separate package and not a third scanner strategy

Considered and rejected: registering the rule in `scanner/strategies/__init__.py:STRATEGIES`
would get a signal tab for free and share `indicators.py`, `store.py` and the
history/`rules_version` machinery.

It is disqualified by `scan.yml`'s deliberate design. The scan runs on five cron wake-ups a
day **and on every push to `main`**, because an algorithm change must regenerate the
published lists — `scanner.market.should_run` lets every non-schedule event straight past
the market-hours gate for exactly that reason. If order submission lived in that workflow,
**merging code would place trades.** It also tolerates losing up to 10% of the universe and
still exiting zero, which is right for a screener and wrong for a broker.

So: different schedule, different secrets, different failure model, different package.
A broken Alpaca API cannot stop the screener publishing, and a bad ticker fetch cannot
stop or distort an order.

**The cost, stated:** the RSI(2) rule now exists twice — pandas in `research/`, stdlib in
`trader/`. The handoff resolved this once by diffing the two over 6,313 bars of SPY. This
spec makes that a committed test (§6), so drift fails the build instead of going unnoticed.

### Execution flow

New workflow `.github/workflows/trade.yml`:

1. **Trigger:** weekday cron at **15:25 ET** (two cron lines so the time holds across EDT
   and EST), plus `workflow_dispatch`. **No `push` trigger** — the opposite of `scan.yml`,
   on purpose: merging code must never submit an order.
2. Clone the `data` branch; read `paper_state.json`.
3. Run `python -m trader.run --live`. Exits early and quietly if `/v2/clock` reports the
   market closed, so holidays need no cron knowledge.
4. Write `paper_state.json`, append to `paper_trades.jsonl` and `paper_runs.jsonl`, and
   write `paper-trading.json`, all on the `data` branch.
5. On failure: open or comment on a single `paper-trade-failure` issue — the pattern
   `scan.yml` already uses for `scan-failure`.

Permissions: `contents: write` and `issues: write`. **Not** `pages: write`.

### Why the trader does not deploy

`scan.yml` owns the single path to GitHub Pages. The trader writes `paper-trading.json` to
the `data` branch; `scan.yml` fetches it into `web/public/data/` before `npm run build`.
Two workflows deploying Pages would race on an environment that permits one deployment at a
time, and the trader is the one that must never be blocked.

**Consequence, accepted:** the dashboard refreshes on the next scan, so a 15:25 ET trade
appears after the 16:10 ET scan — about a 45-minute lag. This is a feature as much as a
cost: the account is then marked at the real closing price rather than the partial-bar
estimate the rule decided on. The page always shows its as-of time, so a stale panel is
never silently stale. If the scan is skipped (holiday), no trading happened either.

### Order mechanics, carried from the prototype

These were settled in the research session; do not relitigate without a reason.

- **Market-on-close** (`type: market`, `time_in_force: cls`) so fills match the backtest's
  closing-price assumption.
- Alpaca **rejects `cls` orders after 15:50 ET**
  (https://docs.alpaca.markets/docs/orders-at-alpaca), so the run must land well before.
  15:25 ET gives ~25 minutes of headroom for Actions cron drift; the run refuses to submit
  with under 10 minutes to the close.
- At 15:25 the close is unknown, so the rule evaluates a **partial daily bar**. Justified:
  in the backtest, buying a full day late still earned 53 bps/trade on SPY. §5 measures
  this approximation's real cost rather than trusting that number.
- `end` on data requests is held **16 minutes back**, which is what lets a free account
  query the SIP feed
  (https://docs.alpaca.markets/us/docs/market-data-faq). Verified working 2026-10-10 on
  both `sip` and `iex`; 289 daily bars returned for a 420-day lookback, enough for SMA(200).
- Bars held are counted from Alpaca's `/v2/calendar` — trading sessions, not calendar days.
- Whole shares only (`cls` requires it).

### Account

Paper account `PA36V1RJY3GK`, verified 2026-10-10: `ACTIVE`, $100,000 equity, $100,000
cash, flat. Opening balance is recorded once, on the first run, from the account's equity.
The account reports $400,000 buying power (4× margin); **sizing is computed off `equity`,
never off `buying_power`.**

Credentials come from `ALPACA_KEY_ID` / `ALPACA_SECRET_KEY` env vars, supplied as GitHub
repository secrets. They are never written to a file and never committed.

---

## 4. Safety invariants

Enforced in code, each with a test:

1. The trading base URL must be the paper host; the run aborts otherwise.
2. Long only. No short orders, no use of margin buying power.
3. One decision per symbol per day. An existing open order for a symbol means skip, never
   stack.
4. A rejected order is **not retried** — it is logged with its reason and the symbol is
   left flat. A blind retry could submit past 15:50, or submit an order the rule no longer
   wants.
5. The workflow has no `push` trigger.
6. Keys only from environment variables. Local state files are gitignored.
7. A data error on one symbol skips that symbol only; the other still trades.

---

## 5. What gets captured, and the evaluation loop

The point is to be able to change the strategy later on evidence gathered here. All files
are append-only on the `data` branch and are never rewritten, so the live record outlives
any change to the rule.

### `paper_trades.jsonl` — one row per fill

- **Order:** `symbol`, `side`, `order_id`, `submitted_at`, `filled_at`, `filled_qty`,
  `filled_avg_price`, `status`
- **Why it fired:** `rsi2`, `sma200`, `trend_gap_pct`, `decision_close` (the partial-bar
  price the rule actually saw), `equity_at_decision`, `slice_pct`
- **On a sell:** `exit_reason` (`rsi` | `time_stop`), `bars_held`, `entry_price`,
  `realised_pl`, `realised_pl_pct`
- **Provenance:** `rules_version` — `base.rules_version()` over the trader's declared
  params, the same fingerprint machinery the scanner uses, so a threshold change splits the
  ledger cleanly instead of blending two rule generations.

`decision_close` against `filled_avg_price` earns its place: it measures the one
approximation this design makes — deciding on a 15:25 partial bar but filling in the
closing auction. The handoff justified that from a backtest; this measures it directly, per
trade, in the account that actually trades.

### `paper_runs.jsonl` — one row per run, trade or no trade

Timestamp, event, market-open state, minutes to close, and the RSI(2) and trend-gate state
for **both** names, plus the decision and any skip reason. This records non-trades too, so
"the rule fired and the bot missed it" is distinguishable from "nothing fired", and a
proposed threshold change can be replayed against the days that did not trade.

### `trader/evaluate.py`

Reads the ledger and reports the live record against the backtest's expectation: bps per
trade, win rate, mean bars held, decision-vs-fill slippage, and each live trade beside what
the backtest produced for the same entry date. Its output goes into `paper-trading.json` so
the page shows live-vs-backtest directly.

It inherits both of this repo's measurement traps: it reports non-overlapping statistics
and a per-period breakdown, never a single pooled number.

### `trader/ACCEPTANCE.md` — written before the numbers exist

With ~13% exposure per name, the two names together fire roughly 20 round trips a year, so
a verdict needs about **30 trades — call it 18 months.** Until then the page reports the
record and explicitly offers no verdict.

What would force a change, stated now so it cannot be rationalised later:

- Realised bps/trade more than one standard error below the backtested +150 (AMZN) / +117
  (AAPL) over 30+ trades → revisit the rule, starting from the 2024–26 decay noted in §2.
- Decision-vs-fill slippage worse than 15 bps per round trip → move the run later or change
  order type. **Not** a reason to touch the rule.
- A realised drawdown beyond the backtested −27.7% / −32.4% → revisit sizing, not the
  thresholds.

Any threshold change follows this repo's existing rule: measure it in `research/` first,
record the number, add a `Release` entry to the strategy's `history`, and let the
`rules_version` fingerprint change so the ledger splits at that date.

---

## 6. Tests

All offline. No test touches the network or the broker.

| Test | What it pins |
|---|---|
| `test_rule.py` | Entry and exit decisions on hand-built series: trend gate rejecting an oversold name below its 200-day, RSI exit, time stop at exactly 10 sessions, insufficient history → no decision. |
| `test_rule_matches_backtest.py` | The drift guard. The stdlib `wilder_rsi`/`sma` diffed against the pandas implementations over real AMZN and AAPL history (cached CSV fixture, offline), asserting 100% signal agreement. |
| `test_alpaca.py` | The HTTP client against recorded fixtures captured from the verified live calls, including an error body and a rejected order. |
| `test_sizing.py` | 50% slices, whole shares, the two-concurrent cap, the buying-power refusal, and that sizing never reads `buying_power`. |
| `test_export.py` | `paper-trading.json` built from fixture ledgers: flat account, one open position, a closed round trip, empty day-one ledger. |
| `test_params.py` | The `rules_version` fingerprint, and the newest `Release` entry asserted to match it — as `scanner/tests/test_history.py` does. Changing a threshold without a history entry fails the build. |
| Web component tests | The three new components against fixture JSON, including the day-one empty state and a missed-run warning. |

`trader/tests` joins the existing invocations: the documented local command in `CLAUDE.md`
becomes `.venv/bin/python -m pytest scanner/tests research/tests trader/tests -q`, and CI's
bare `python -m pytest -q` picks the new directory up without change.

### `paper-trading.json` — the published contract

One file, written by `trader/export.py`, read by the page. Shape:

```
updated_at          ISO timestamp of the run that wrote it
as_of               what the account figures are marked at ("close" | "intraday")
rules_version       fingerprint of the params this run used
account             { opening_balance, equity, cash, deployed_pct,
                      total_pl, total_pl_pct, realised_pl, unrealised_pl }
equity_curve        [ { date, equity, in_position } ]
positions           [ { symbol, entry_date, entry_price, qty, price,
                        unrealised_pl, unrealised_pl_pct, bars_held, max_hold } ]
signal_state        [ { symbol, rsi2, sma200, price, trend_gap_pct, verdict } ]
trades              [ { symbol, entry_date, entry_price, exit_date, exit_price, qty,
                        bars_held, exit_reason, pl, pl_pct, decision_close,
                        slippage_bps, rules_version } ]
evaluation          { trades_closed, trades_needed, bps_per_trade, win_rate,
                      mean_bars_held, slippage_bps,
                      backtest: { AMZN: {...}, AAPL: {...} }, verdict: null }
runs                [ { at, event, decided, orders, skip_reason, late } ]
```

`evaluation.verdict` stays `null` until `trades_closed >= trades_needed` (§5). The page
renders the absence of a verdict, rather than hiding the section.

---

## 7. The page

Third nav tab, **Paper Trading**, at `/paper`. Hand-added to `TopBar` after the two
data-driven strategy links, since it is a portfolio view rather than a signal list and does
not come from `strategies.json`. It reuses the existing warm palette, serif numerals and
`.stat` / `.bigcard` / `.pill` vocabulary so it reads as the same product.

1. **Header strip** — strategy name, the rule in one plain-English line, the clock icon
   opening the same `HistoryModal` the other tabs use, an as-of line ("Account marked at
   Friday's close · last bot run 15:25 ET"), and a `PAPER` pill.
2. **Balance row** — five `.stat` cells: opening balance, current equity, total P/L
   (dollars and percent, signed and coloured), realised P/L, and percent of capital
   deployed. Realised and unrealised are split because at 13% exposure they tell different
   stories.
3. **Equity curve** — equity since inception against the $100,000 opening balance as a flat
   reference, with shaded bands on days a position was open, so flat stretches read as
   deliberate idleness rather than a broken chart. From Alpaca's portfolio-history
   endpoint. Follows the `dataviz` palette.
4. **Open positions** — a card per held name: entry date and price, shares, current price,
   unrealised P/L in dollars and percent, and a bars-held meter ("4 of 10 bars") showing
   how close the time stop is. Empty state explains the idleness.
5. **Live signal state** — two compact rows, AMZN and AAPL: RSI(2) against the 10
   threshold, price against SMA(200) with the gap in percent, and a verdict pill
   (`Oversold`, `Waiting`, `Held`, `Trend gate blocked`). This is why the bot did or did not
   act today.
6. **Trade history** — newest first, round trips paired: symbol, entry date and price, exit
   date and price, shares, bars held, exit reason, P/L in dollars and percent. An open trade
   shows with no exit. Below it the live-vs-backtest comparison from §5, with a count of how
   many of the ~30 trades needed for a verdict are in, and no verdict until then.
7. **Run log**, collapsed — last ten runs with what each decided. A warning banner when a
   scheduled run was missed or landed past the 15:50 ET cutoff, in the spirit of
   `FailingTestsNote`.

Mobile: the stat row wraps to two columns; the trade table becomes stacked cards.

---

## 8. Failure handling

- Per-symbol isolation: a data error skips that symbol, the other still trades.
- A rejected order is logged and left; never retried (§4).
- A run that throws opens or comments on one `paper-trade-failure` issue.
- `paper_runs.jsonl` records every run including failures, so nothing lives only in an
  Actions log that GitHub deletes after 90 days.
- A missed scheduled run is visible on the page, not just in the ledger.

---

## 9. Before the first live run

Order submission is the one path that cannot be verified offline, and the only Alpaca call
still untested — account, clock, positions and bars were all verified against the real
account on 2026-10-10.

The user has chosen **live from the first scheduled run**. So the plan includes a one-off
manual `--dry-run` during Monday 2026-10-12's session, watched, which exercises every
endpoint and the order-construction path without submitting. It is a step in the plan, not
a gate on the schedule.

The paper keys were shared in a chat transcript. They should be rotated in the Alpaca
dashboard once the workflow is running, and the fresh pair re-added as repository secrets.

---

## 10. Out of scope

- Live-money trading. The endpoint is hardcoded to paper and an invariant forbids otherwise.
- Any symbol beyond AMZN and AAPL. Adding one requires its own measurement first.
- A short leg. The research found no edge in one here, and this account's shorting
  capability is deliberately unused.
- Stops, trailing exits, volatility filters, position-size optimisation. Each would be a
  parameter without a measurement behind it, which this repo does not permit.
- Changing the two existing strategies, or the scanner's contract.
