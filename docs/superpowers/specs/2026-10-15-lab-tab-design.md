# The Lab tab (sub-project 4 of 4)

Written 2026-10-15. Status: **draft for review.** Renders `lab.json`, whose contract is fixed by
`2026-10-15-intraday-lab-foundation-design.md` (as amended, and as built in `lab/export.py`).
Paper money only; the page places nothing and computes no market logic.

## Intent

One new tab, "Lab", in the existing site: the place to see every intraday idea the lab has tried,
how it did, why it passed or failed, and (later) what it is trading. It must look like the rest of
the site (cream/terracotta tokens, Instrument Serif/Sans), be attractive and scannable, work on a
phone, and be honest when there is nothing to show.

## Data

- `getLab()` in `web/src/api.ts` reads `lab.json` from the same data directory as the other
  files, using the existing `getJson` path. A 404 is normal before the lab has published; the
  page shows a designed empty state, not an error (same rule as `/paper`).
- `types.ts` gains `LabFile` and friends mirroring `lab/export.py`: `meta`, `summary`,
  `strategies[]` (id, name, family, stage, hypothesis, params, risk, failure_rules, backtest,
  live, equity_curve, history, breakdowns), `trades[]`, `trials[]`, `positions[]`, `runs[]`,
  `account | null`. `backtest.years` keys are strings; money is bps unless named `*_pct`.
- Publishing: `lab.json` reaches Pages the way `paper-trading.json` does (written to the `data`
  branch, copied into the build by `scan.yml`). Wiring the **publishing** workflow is out of scope
  here; until then the page is driven by a committed development fixture and the 404 empty state.
- `web/src/test-fixtures.ts` gains a realistic `labFixture()` (several strategies across stages,
  a passing one with a 12-month equity curve and ~300 trades, rejected ones with failed checks,
  a ledger of ~25 trials). It is for tests and the screenshot check only and is never published.

## Page (top to bottom)

1. **Hero**: "Intraday Lab", a "Paper money" pill, one plain sentence of purpose, and a line
   "N ideas tried · M rejected · bar now t ≥ X" (X is `max(2.5, expected-max-t)` computed from
   `meta.trials_total` by a small pure function `deflatedBar(n)` that mirrors `lab/stats.py` and is
   unit-tested against the same values).
2. **Pipeline strip**: stage chips Proposed → Backtested → Shadow → Paper → Kept with counts,
   Rejected/Retired set apart. A chip filters the strategy list; selection is in the URL search
   params so a view is linkable.
3. **KPI row**: net P&L, return, win rate, profit factor, Sharpe, max drawdown, expectancy (bps),
   for the selected strategy (or all non-rejected). Big serif numbers, small labels, buy/sell tint.
4. **Equity & drawdown**: `lightweight-charts` (already a dependency, loaded through the existing
   lazy chart-chunk pattern, not eagerly), strategy selector, a backtest/live toggle (live is
   disabled with a tooltip until it exists).
5. **Strategy cards**: stage badge, hypothesis, sparkline (the existing `Sparkline`), and the
   **gate checklist** as ✓/✗ rows with the numbers (from `backtest` + `trials[].failed`), failure
   rules as progress bars once shadow/paper, and a history overlay reusing `HistoryModal`.
6. **Active positions**: table; empty state until the executor exists.
7. **Trade history**: filter by strategy / symbol / exit reason, sortable, gross/cost/net bps,
   long lists paginated. A row opens a detail panel (entry, exit, bars held, costs, exit reason).
8. **Where the edge is**: hand-written SVG charts (no new dependency) for P&L by hour of day, by
   weekday and by symbol; the trade-return histogram; and a daily P&L calendar heatmap.
9. **Trial ledger**: searchable list of every idea tried: name, family, verdict, why it failed.
10. **Run log**: `lab.json.runs`, styled like `PaperRuns`; empty until the executor exists.

## Rules the page follows

- Colour never carries meaning alone (✓/✗ glyphs and signed numbers accompany green/red).
- Numbers use `.num` tabular figures; all money/percent formatting goes through one module
  `lib/labFormat.ts` so signs, bps and percentages are consistent and tested.
- Light and dark follow the site's tokens; no new colours are introduced outside `theme.css`.
- Mobile first: one column under ~720px; tables become stacked rows; touch targets >= 44px.
- The load path stays as measured: no eager chart import, no new blocking request. `lab.json` is
  fetched on entering `/lab`, not on the home page, and charts warm on idle like the others.
- Nothing is invented: every figure on the page comes from `lab.json`; the only derivation is
  `deflatedBar`, tested against the Python values.

## Navigation

A "Lab" `NavLink` in `TopBar`, with the timeframe toggle hidden on `/lab` exactly as on `/paper`.
Route `/lab` in `App.tsx`; unknown paths still fall through to "Page not found".

## Components (all under `web/src/components/lab/` unless shared)

`LabPage` (page), `LabHero`, `PipelineStrip`, `LabKpis`, `LabEquityChart`, `StrategyCard`,
`GateChecklist`, `FailureRuleBars`, `PositionsTable`, `TradesTable`, `TradeDetail`, `EdgeCharts`
(`BarsChart`, `Histogram`, `CalendarHeat` as small SVG components), `TrialLedger`, `LabRuns`;
`lib/labFormat.ts`, `lib/labStats.ts` (`deflatedBar`, aggregation helpers).

## Testing

- Unit: `labFormat` (signs, bps, rounding, null), `deflatedBar` against Python-computed values,
  aggregation helpers on the fixture.
- Component (Testing Library, as in `PaperPanels.test.tsx`): hero line and the rising bar; pipeline
  counts and filtering; gate checklist shows ✓/✗ with numbers; trades table filter/sort/paginate;
  empty states for no data, no trades, no positions, no runs; 404 renders the designed empty state.
- Route: `/lab` renders; nav link present; timeframe toggle absent on `/lab`.
- **Visual check** (per CLAUDE.md): build, serve with `vite preview`, drive the Chrome-for-Testing
  binary at 390px and 1280px, light and dark, on the fixture; screenshot and look at them. Unit
  tests pass on copy that reads badly; the screenshot is the check that it looks right.
- Contract guard: a Python test already validates `lab.json` with `export.validate`; add a web test
  that the fixture contains every key the types require.

## Out of scope

Per-trade price charts (need stored bars; arrive with the paper executor), the publishing
workflow, live/shadow data, the `/lab` skill. The page degrades to honest empty states for all of
these.
