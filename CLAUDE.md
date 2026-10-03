# NS-Multi-Stratt

A personal multi-strategy stock screener. A Python scanner sweeps the S&P 500 on two
timeframes, writes static JSON, and a React site renders it. No server, no live trading.

## Commands

```bash
.venv/bin/python -m pytest scanner/tests research/tests -q   # Python tests (~1s)
cd web && npm test -- --run                                  # web tests (~2s)
.venv/bin/python -m scanner.run --out web/public/data --db signals.db   # full scan (network)
.venv/bin/python -m research.measure                         # backtest variants (network, cached)
```

Always use `.venv/bin/python` — there is no activated environment, and the system Python
lacks the deps. `scanner/tests/test_smoke_network.py` is skipped by default; it hits Yahoo.

## Layout

- `scanner/` — fetch (`data.py`), indicators (`indicators.py`), strategies, export, SQLite
  history (`store.py`), trading-calendar gate (`market.py`). Entry point `run.py`.
- `scanner/strategies/` — one module per strategy, registered in `__init__.py:STRATEGIES`.
  Each exposes `id/name/description/min_bars/chart` and `evaluate(df) -> Signal | None`.
- `research/` — backtesting, kept out of the scan path. `measure.py` is the harness,
  `FINDINGS.md` is the interpretation, `results/` is generated, `.cache/` is gitignored.
- `web/` — Vite + React + TypeScript, reads the JSON the scanner writes.

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

**Conviction tiers** (`base.py`) are `high`/`standard`/`low`, sorted strongest-first by
`CONVICTION_RANK`. They encode measured edge, not enthusiasm.

**Indicator seeding is load-bearing.** EMA200 with `adjust=False` is still seed-biased at 250
bars, which is why `TrendPullback.min_bars` is 400. RSI and ADX are Wilder-smoothed, matching
TradingView rather than a simple rolling mean.

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
