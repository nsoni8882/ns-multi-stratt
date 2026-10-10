# NS-Multi-Stratt

A personal multi-strategy stock screener. A Python scanner sweeps the S&P 500 on two
timeframes, writes static JSON, and a React site renders it. No server. Two of the three
strategies only publish lists; the third (`trader/`) submits orders to an Alpaca **paper**
account. No real money anywhere.

## Commands

```bash
.venv/bin/python -m pytest scanner/tests research/tests trader/tests -q   # Python tests (~50s)
cd web && npm test -- --run                                  # web tests (~2s)
.venv/bin/python -m scanner.run --out web/public/data --db signals.db   # full scan (network)
.venv/bin/python -m research.measure                         # backtest variants (network, cached)
.venv/bin/python -m research.news_judgment --dry-run         # news state for live signals, no API call
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m trader.run --dry-run  # decide, place nothing
```

Always use `.venv/bin/python` — there is no activated environment, and the system Python
lacks the deps. `scanner/tests/test_smoke_network.py` is skipped by default; it hits Yahoo.

## Layout

- `scanner/` — fetch (`data.py`), indicators (`indicators.py`), strategies, export, SQLite
  history (`store.py`), trading-calendar gate (`market.py`). Entry point `run.py`.
- `scanner/strategies/` — one module per strategy, registered in `__init__.py:STRATEGIES`.
  Each exposes `id/name/description/min_bars/chart/params/history` and
  `evaluate(df) -> Signal | None`. `params` and `history` are build-asserted; see below.
- `research/` — backtesting, kept out of the scan path. `measure.py` is the per-ticker
  harness and `cross.py`/`measure_cross.py` the cross-sectional one (rules that rank the
  universe against itself, which no shipped strategy does). `FINDINGS.md` is the
  interpretation, `ACCEPTANCE.md` the bar, `results/` is generated, `.cache/` is gitignored.
- `trader/` — the only thing here that *acts*: it places market-on-close orders for AMZN and
  AAPL on an Alpaca **paper** account, on the RSI(2) reversion rule. Stdlib only, hardcoded to
  the paper endpoint, its own `trade.yml` workflow on a 15:25 ET cron. `params.py` holds every
  threshold and fingerprints them, `ACCEPTANCE.md` holds the bar, `evaluate.py` compares the
  live record to the backtest. `research/rsi2/` is the research it came from.
- `web/` — Vite + React + TypeScript, reads the JSON the scanner writes.
- `docs/superpowers/` — the original dated spec and plan. A record of how the MVP was
  decided, not the current contract: both predate the short legs being dropped. This file
  and `research/FINDINGS.md` are the live documents.

Strategies receive a DataFrame of **closed** bars only (UTC index = bar open, plus a
`close_time` column). Never evaluate a partial bar.

## Conventions that matter here

**Claims about market behaviour are measured, not asserted.** The comments in
`scanner/strategies/` carry sample sizes, alphas and t-stats because each one cost a backtest
to establish. When changing a threshold, a lookback or an MA period, measure it with
`research/measure.py` and record the number — and when a measurement kills an idea, write
down that it was killed so it is not re-proposed. Do not add a parameter to a strategy
without a measurement behind it. `research/ACCEPTANCE.md` holds the bar a variant has to
clear to ship, and it is written before the numbers exist, not after.

**Two traps this project has already hit**, both guarded in `research/measure.py`:
- Signals cluster, so their forward windows overlap and a naive t-stat runs 2–3x too high.
  Judge the non-overlapping (`t indep`) column.
- A pooled result can be one event in disguise. Check the per-year table before believing a
  t-stat; a −4.04 in this repo turned out to be February 2020.

**An algorithm change regenerates the published lists automatically.** Any push to `main`
that touches code runs the full scan and redeploys — `scanner.market.should_run` lets every
non-schedule event past the market-hours gate deliberately. Do not hand-edit
`web/public/data`; it is generated. Every strategy declares `params` (the thresholds that
decide a signal) and `base.rules_version()` fingerprints them into `strategies.json` and onto
every history row, so a stale deploy is detectable and two rule generations never blend in
`signals.db`. **A new gate must be added to `params`** or it changes signals without changing
the fingerprint — there is a test pinning this.

**Every strategy carries a visible change history.** `history` on the strategy class is a
newest-first tuple of `Release` entries (semver, date, one or two plain-English lines about
what changed for a signal, no identifiers). It is published in `strategies.json` and shown in
the site's history overlay behind the clock icon next to the strategy name. The newest entry
records the `rules_version` fingerprint it shipped with and `scanner/tests/test_history.py`
asserts it still matches, **so changing a threshold without adding a history entry fails the
build** — that is deliberate, and it is what keeps the published history honest.

**A listed signal whose premise has died is labelled, not hidden.** Both strategies fire on
an RSI cross, so both die the same way: `base.thesis_negated` asks whether a later bar has
crossed back past the level that triggered the signal, and the card says "Setup changed".
Measured before it was wired up — stale BUYs with a dead premise returned *more* than intact
ones (+1.93% vs +1.52%, n=2,717) — so dropping them was the wrong fix for what was only ever
a labelling bug. `test_invalidation.py` pins this. It changes no backtested number: the
harness enters at the signal bar, where no later bar exists yet.

**The chart's overlays have rules of their own.** `web/src/lib/smc.ts` is a port of LuxAlgo's
Smart Money Concepts Pine v5 indicator (CC BY-NC-SA 4.0 — keep the attribution, and keep this
non-commercial), reduced to the six features the chart switches on. It is pure, so it is
unit-tested, and its two deliberate divergences from the Pine are documented at the top of the
file. Candles default to Heikin-Ashi, but **every indicator and overlay is computed from real
closes** — HA closes are an average, and an RSI of an average is not the RSI the scanner
signalled on. The legend says so out loud; do not "fix" it by feeding HA bars to an indicator.

**The load path is deliberate, not accidental complexity.** `web/index.html` starts the data
requests in a `<script>` before the bundle parses and `api.ts:headStart()` adopts them;
`lib/chartViewLoader.ts` hand-rolls the chart chunk's import because a `Suspense` fallback is
held on screen ~300ms by React's anti-flicker throttle, longer than the fetch it covers; and
charts are warmed on hover and on idle, gated on `wantsPrefetch()` so Save-Data and 2G opt
out. Each of these replaced a measured delay. Simplify one only with a number in hand.

**The trader is deliberately isolated from the scanner.** `scan.yml` re-runs on every push to
`main` because an algorithm change must regenerate the published lists — and that is exactly
why order submission does not live there, since the same trigger would mean merging code
submits orders. `trade.yml` has no `push` trigger, its tests *block* the job rather than being
folded into a health file, and it never deploys: it writes `paper-trading.json` to the `data`
branch and `scan.yml` copies it into the build, so there stays one path to Pages.
`trader/tests/test_workflow.py` pins all of that, because it lives in YAML where nothing else
would catch it being edited away. Sizing comes off `equity` and never off the 4x `buying_power`
the paper account reports. A rejected order is logged and left, never retried — a retry can
land past Alpaca's 15:50 ET cutoff or re-submit an order the rule no longer wants.

**One rule, three implementations, two tests holding them together.** The live rule is
stdlib-only (no pandas on the order path), `research/rsi2/rsi2_edge_backtest.py` is pandas, and
`research/rsi2/rsi2_reversion_strategy.pine` is what you can check on a TradingView chart.
`test_rule_matches_backtest.py` pins the first two to identical entry signals over ~6,700 bars
per symbol, and `test_rule_matches_pine.py` pins the live rule to the Pine strategy trade for
trade (AMZN 199, AAPL 214). Change the rule and both must still pass, or the chart and the bot
have quietly diverged.

**Conviction tiers** (`base.py`) are `high`/`standard`/`low`, sorted strongest-first by
`CONVICTION_RANK`. They encode measured edge, not enthusiasm.

**Indicator seeding is load-bearing.** EMA200 with `adjust=False` is still seed-biased at 250
bars, which is why `TrendPullback.min_bars` is 400. RSI and ADX are Wilder-smoothed, matching
TradingView rather than a simple rolling mean.

## When something goes wrong in production

There is no server and no error tracker, so "production" means the GitHub Actions run and the
JSON it published. Three places to look, in this order:

```bash
gh issue list --label scan-failure                  # a failed scan says so here
gh issue list --label paper-trade-failure           # a failed trading run says so here
git show origin/data:paper_runs.jsonl | tail -5     # every trading run, trade or no trade
gh run list --workflow=scan.yml --limit 10          # did the daily scans pass?
gh run view <id> --log-failed                       # the failing step's output
curl -s https://<owner>.github.io/<repo>/data/health.json | python -m json.tool
git show origin/data:runs.jsonl | tail -20          # every run, success or not
```

`health.json` is written by every **successful** scan and is the record of what that run still
lost: tickers that failed to fetch (a scan is allowed to lose up to 10% of the universe and
exit zero), strategies that threw on individual names, the duration, the test outcomes, and the
`rules_versions` actually published.

A scan that *fails* publishes nothing, so three things cover that case instead. The `record`
job runs `if: always()` and appends one line per run — including skipped and failed ones — to
`runs.jsonl` on the `data` branch (`scanner/ledger.py`, last 500 kept). A failure also opens or
comments on a single `scan-failure` issue, so it is not silent. Both outlive the 90 days
GitHub keeps an Actions log.

Two things that used to be silent and now are not:

- **A scheduled run can deploy from failing code.** Tests still do not *block* a scheduled
  refresh — dependency drift must never stop a data update — but they now run, and
  `scanner.health` folds the outcome into `health.json`. Check
  `published_with_failing_tests`: true means the live site was built from code whose suite
  fails, which is the one case worth acting on immediately.
  The site says this out loud too: `FailingTestsNote` in the footer, driven by the same file.
- **Browser errors are kept by the page itself.** There is no server to receive them, so
  `web/src/lib/errorLog.ts` keeps the last 10 in `localStorage`, two `ErrorBoundary`s (one
  around the chrome, one around the routes) replace the blank-white-screen failure with a
  message, and the footer appears only after something breaks. *Copy details* gives the stack
  trace; *Report* opens a prefilled issue, which is the only automatic route from a browser to
  somewhere readable — and it sends nothing unless the person submits it.

## Visual checks

This Mac has Arc, not Chrome, and **Arc cannot be driven by Playwright** — it launches but
never speaks CDP. The Playwright MCP plugin is pinned to channel `chrome` and fails too. To
look at the UI, serve the built site and drive the bundled Chrome-for-Testing binary
directly (same Blink engine Arc renders with):

```bash
cd web && npm run build && npx vite preview --port 4317 --strictPort &
# then a node script with executablePath set to
# ~/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
```

Worth doing for user-facing copy: unit tests pass on text that reads badly, and a screenshot
caught a literal `--` rendering in the history overlay that every test had accepted.

## Git

Commit every change and push to `origin main` — leave nothing uncommitted. Commit in logical
units as the work goes, not one dump at the end.
