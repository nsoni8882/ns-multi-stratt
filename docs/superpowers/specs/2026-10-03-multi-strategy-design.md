# Multi Strategy — Design Spec

> **Historical.** This is the MVP spec/plan as approved on 2026-10-03, kept as the record of
> what was decided and why. It is not the current description of the system: among other things,
> both strategies have since stopped publishing SELL signals. For how the program works today see
> `CLAUDE.md`, `README.md` and `research/FINDINGS.md`.

Date: 2026-10-03
Status: Approved by owner (2026-10-03), including section 6.1 visual design

## 1. Purpose and scope

A static website that scans every S&P 500 stock on the 4H and Daily timeframes and lists the stocks currently showing a BUY or SELL signal, one page per strategy.

- **Audience:** the owner and a small group of friends. Public URL, informal. Footer carries a "Not financial advice" disclaimer.
- **Hosting:** GitHub Pages, repo `nsoni8882/ns-multi-stratt`, URL `https://nsoni8882.github.io/ns-multi-stratt/`. The user may later move it to an org named `ns-multi-stratt` to get `ns-multi-stratt.github.io`; the site must therefore take its base path from one config value.
- **Data:** free sources only (Yahoo Finance via `yfinance`).
- **MVP strategies:** (1) MACD + RSI reversal, (2) trend pullback.

### Non-goals (MVP)
- No backend, accounts, alerts/notifications, or backtesting.
- No cross-strategy "confluence" list.
- No chart for tickers that are not currently flagged.
- No signal validation or performance page yet. Signals are *recorded* from day one (section 5) so that validation can be built later (section 11).

## 2. Architecture

One scheduled GitHub Actions workflow does everything. The site is deployed from generated JSON, and every signal is also recorded in a SQLite history database kept on a separate `data` branch:

```
Wikipedia (S&P 500 list) ─┐
yfinance (1H→4H, daily) ──┼─> Python scanner ─┬─> JSON files ─> Vite build ─> deploy-pages
                          │                   └─> SQLite (data branch)  [signal history]
```

The site is fully static. Browsers only read the generated JSON. The database is never read by the site in the MVP.

### 2.1 Workflow (`.github/workflows/scan.yml`)
- **Triggers:** `schedule`, `workflow_dispatch`, and `push` to `main`.
- **Schedule:** see 2.3. Cron entries are only wake-up calls; a `gate` job decides whether a scheduled run actually scans.
- **Permissions:** `contents: write` (push to the `data` branch), `pages: write`, `id-token: write`.
- **Concurrency:** a single concurrency group so overlapping runs queue instead of racing on the database push.
- **Steps:** checkout `main`, check out the `data` branch into `./history`, set up Python and Node, install, run scanner (reads and updates `history/signals.db`, writes JSON to `public/data/`), build site, upload and deploy the Pages artifact, then commit and push `history/signals.db` to `data` (only after a successful deploy, and only if the file changed).
- **Failure policy:** scheduled runs skip the test steps (pushes and manual runs run them), so dependency drift cannot block a data refresh; if more than 10% of tickers fail to fetch, or the universe or data step fails entirely, the scanner exits non-zero. The deploy and database push are skipped, and the previous site stays live.
- **First run:** if the `data` branch does not exist, the workflow creates it as an orphan branch with an empty database.

### 2.3 Trading calendar and schedule

The scanner uses the `exchange_calendars` XNYS calendar (weekends, NYSE holidays, early closes, DST). An **update is due** 5 minutes after each bar close: the first 4H bar (open + 4h, i.e. 13:30 ET) and the final bar at the close (16:00 ET), or a single update at the close on early-close days.

- **Gate job:** runs before the scan. Pushes and manual runs always scan. A scheduled run scans only if an update has come due since the deployed `strategies.json` `updated_at` (read from the live site). Weekends, holidays, the DST duplicate wake-ups and already-up-to-date runs therefore skip themselves, and a missed wake-up is caught by the next one.
- **Cron wake-ups (UTC):** 17:40/18:40 (13:40 ET), 20:10/21:10 (16:10 ET), 17:10/18:10 (13:10 ET, early-close days), and hourly 14:30-23:30 on weekdays as a catch-up.
- **Keep-alive:** GitHub disables scheduled workflows after 60 days without repository activity. A scheduled run makes an empty commit on `main` if the last commit there is more than 45 days old.
- **No manual steps:** everything runs on GitHub Actions (Pages itself is static and runs nothing); nothing needs to be started by hand.

### 2.2 Repository layout
```
scanner/
  universe.py          # fetch S&P 500 list (ticker, name, sector)
  universe_fallback.csv # committed snapshot used if the scrape fails
  data.py              # fetch + resample bars
  indicators.py        # MACD, RSI, EMA
  strategies/
    base.py            # Signal dataclass, Strategy protocol
    macd_rsi_reversal.py
    trend_pullback.py
    __init__.py        # registry
  store.py             # storage layer over SQLite (record_signals, ...)
  export.py            # JSON writers for the site
  market.py            # NYSE calendar: sessions, holidays, update-due times, the scan gate
  run.py               # orchestrates, writes JSON, records signals
  tests/
web/                   # Vite + React + TypeScript
  src/ ...
  public/data/         # generated, git-ignored
.github/workflows/scan.yml
docs/superpowers/specs/
```

## 3. Data layer

- **Universe:** scrape the constituents table from the Wikipedia "List of S&P 500 companies" page (ticker, name, GICS sector). Convert `.` to `-` in tickers (e.g. `BRK.B` to `BRK-B`) for Yahoo. If the scrape fails, fall back to a static snapshot committed in the repo (`scanner/universe_fallback.csv`, seeded once at setup and refreshed manually).
- **Daily bars:** `yfinance` bulk download, 2 years, auto-adjusted.
- **4H bars:** `yfinance` 1H bars (a 729-day lookback, the most Yahoo allows: a start exactly 730 days back is rejected. This gives ~1000 4H bars so the 200/50 EMA parameters work on both timeframes), regular hours only, resampled to 4H bins anchored to the open: 09:30–13:30 and 13:30–16:00 ET (the second bar is 2.5h long). The OHLCV aggregation is first/max/min/last/sum.
- **Closed bars only:** the in-progress bar is dropped (daily bar before 16:00 ET, 4H bar before its close).
- **Minimum history:** a ticker is skipped for a given timeframe if it has fewer bars than the strategy needs (e.g. 250 for Strategy 2, to let the 200 EMA settle). Recently listed tickers are therefore skipped for that timeframe.
- **Rate limiting and freshness:** download in batches of 50 with a pause between batches. yfinance usually returns empty frames rather than raising when throttled, so tickers that come back empty are re-requested (up to 3 attempts, with growing pauses). A ticker whose last closed bar is older than the newest bar in the universe (halted or delisted) is treated as failed, so it counts toward the 10% failure rule and never shows as a fresh signal.

## 4. Strategies

Common rules:
- Evaluated on closed bars of each timeframe independently.
- A signal fires on "bar 0" (the latest closed bar) and stays listed for **3 bars** (bars-ago 0, 1, 2). If both BUY and SELL conditions fall in the window, the most recent one wins.
- Each strategy returns, per ticker/timeframe, `None` or a `Signal` (side, bars_ago, fired_at timestamp, and the key indicator values for display).

### 4.1 Strategy 1: MACD + RSI reversal
Indicators: MACD (12, 26, 9) histogram; RSI(14, Wilder).

**BUY** (all true on the signal bar):
1. The histogram was in the bottom 10% of its trailing 100 bars at some point in the preceding 5 bars ("deep red").
2. The histogram has risen for 2 or more consecutive bars and is still ≤ 0.
3. RSI(14) closed below 20 at some point in the last 5 bars, and now closes above 20 (the cross above 20 occurs on the signal bar).

**SELL**: mirror image: histogram in the top 10% of trailing 100 bars within the last 5 bars, falling for 2+ bars and still ≥ 0, RSI(14) was above 80 in the last 5 bars and crosses below 80 on the signal bar.

Note: RSI(14) < 20 is rare on large caps, so few signals are expected. The thresholds live in one config block so they can be tuned later.

### 4.2 Strategy 2: Trend pullback
Indicators: EMA(50), EMA(200), RSI(14).

**BUY**:
1. Close > EMA(200) and EMA(50) > EMA(200) (uptrend).
2. RSI(14) closed below 40 in the last 5 bars and crosses back above 40 on the signal bar.

**SELL**:
1. Close < EMA(200) and EMA(50) < EMA(200) (downtrend).
2. RSI(14) closed above 60 in the last 5 bars and crosses back below 60 on the signal bar.

### 4.3 Extensibility
A strategy is one module exposing `id`, `name`, `description`, `min_bars`, a `chart` config (`rsi_levels`, `macd_deep`, `emas`, telling the site what to draw), and `evaluate(df) -> Signal | None`, plus an entry in the registry. The frontend discovers strategies from `strategies.json`, so adding one needs no frontend code.

## 5. Output JSON (under `public/data/`)

- `market.json`: `{ updated_at, sessions: [{ date, open, close, early }] (14 days back to 45 ahead, UTC), holidays: [{ date, name }] }`, used by the site for the market status chip and the stale banner.
- `strategies.json`: `{ updated_at, strategies: [{ id, name, description, chart: { rsi_levels, macd_deep, emas }, timeframes: { "4h": {buy, sell}, "1d": {buy, sell} } }] }`
- `<strategy_id>/<timeframe>.json`: `{ updated_at, signals: [{ ticker, name, sector, price, side, bars_ago, fired_at, bar_time, details, spark }] }`
- `charts/<timeframe>/<ticker>.json`: `{ ticker, timeframe, bars: [[t,o,h,l,c,v]...], macd: {macd, signal, hist}, rsi, ema50, ema200 (each aligned with bars, null where undefined), signals: [{ strategy_id, side, bar_time }] }`, written only for tickers flagged by at least one strategy on that timeframe, limited to the most recent 250 bars. `t` and `bar_time` are Unix seconds (bar open); `spark` in a signal row is the last 30 closes.

All timestamps are ISO-8601 UTC. `updated_at` is shown in the viewer's local time.

### 5.1 Signal history database (`signals.db`, SQLite, `data` branch)

Why: the JSON files are overwritten each run, so they cannot support later validation of whether signals were right. Each signal is recorded once, immutably, when it first fires.

Table `signals`:

| column | notes |
|---|---|
| `id` | integer primary key |
| `strategy_id`, `ticker`, `timeframe`, `side` | what fired |
| `fired_at` | UTC timestamp of the signal bar's close |
| `entry_price` | close of the signal bar, never updated |
| `details` | JSON text of the key indicator values at signal time |
| `recorded_at` | UTC timestamp of the run that first saw it |
| unique key | `(strategy_id, ticker, timeframe, side, fired_at)` |

- **Idempotent:** inserts use the unique key (`INSERT OR IGNORE`), so reruns and the duplicate DST cron runs never create duplicates. A signal that stays in the 3-bar window across several runs is recorded once, at its first sighting (bars_ago 0 normally).
- **Immutable:** existing rows are never modified by the scanner.
- **Storage layer:** all database access goes through `store.py`, so the backing store can be swapped (e.g. for a hosted database) without touching strategies.
- **Size:** expected to stay at a few MB per year. If it grows past ~50 MB, revisit.
- **Future table `outcomes`** (not created in the MVP): one row per signal with checkpoint returns and a result, see section 11.

## 6. Frontend (Vite + React + TypeScript)

- **Routing:** hash routing (`/#/strategy/:id`) to avoid Pages 404 problems on refresh. The base path comes from the Vite `base` option (default `/ns-multi-stratt/`).
- **Home:** one card per strategy: name, one-line description, BUY and SELL counts per timeframe, last updated, link.
- **Timeframe selector:** a global 1D / 4H segmented control in the top bar of every page, defaulting to 1D. It applies to the home counts, the strategy stock grids, and the chart, and is kept in the URL hash query (`?tf=4h`) so links are shareable.
- **Strategy page:** BUY / SELL / All filter, sector filter, ticker search, and a grid of stock cards (ticker, name, signal pill, sparkline of recent closes, price, bars ago, fired-at on hover/title). Clicking a card opens the chart modal described in 6.1.
- **States:** loading, empty ("No signals right now"), and fetch-error states for each data load. A stale-data banner appears when a scheduled update (see 2.3) is more than 3 hours overdue and the data predates it; weekends, holidays and early closes never come due, so they cannot trigger it. Without `market.json` it falls back to counting weekday hours (48).
- **Market status:** a line under the top bar, e.g. "Market open · next update today 16:05 ET" or "Market closed · Thanksgiving · next update Fri 27 Nov, 13:05 ET" (Weekend, Pre-market, After hours and Early close today are also shown). Computed in the browser from `market.json` and refreshed every minute; hidden if `market.json` is unavailable.
- **Candle style:** the chart modal has a Heikin-Ashi | Real toggle, Heikin-Ashi by default, remembered in `localStorage`. Only the drawn candles change: RSI, MACD and the EMAs always use real closing prices because the scanner evaluates its signals on real prices, and the BUY/SELL label is anchored to the candle actually drawn.
- **Last updated:** shown in the footer on every page (viewer's local time), not in the page header.
- **iPhone Safari:** `viewport-fit=cover` with safe-area padding, 16px form fields (no focus zoom), 44px touch targets, a swipeable nav row, page scroll locked behind the modal, vertical touch drags scroll the page rather than panning the chart, and no `ctx.roundRect` (missing before Safari 16). Verified in WebKit with iPhone 15 and iPhone SE emulation; not on a physical device.
- **Footer:** "Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate."

### 6.1 Visual design (approved: direction "C · Soft Cards", reference mockup in `design-samples/index.html`)

Modern, light, calm; inspired by the light theme of Claude's own interface (an original design, not a copy of any branding or assets).

- **Palette (CSS variables):** warm off-white page `#FFFBF6`, white cards, soft warm border `#EFE6DB`, text `#2A2623`, muted text `#625C55`, terracotta accent `#CC785C` (fills and focus rings) and darker `#A5472A` for accent text, soft segmented-control background `#F6EDE3`. Strategy cards on the home page use tinted fills (peach `#FDEFE6`, sage `#EAF2EC`).
- **Signal colours:** BUY text `#27694B` on `#E3F0E7`; SELL text `#9E2F45` on `#F9E4E8`. Pills always carry a text label and an arrow icon, never colour alone. All text/background pairs are at least 4.5:1.
- **Typography:** Lora (serif) for headings, Inter for body, tables, and labels; tabular numerals for prices and indicator values.
- **Shape:** large radii (cards 20-24px, pills fully rounded), subtle shadows only on hover, generous whitespace, centered content column (max ~1120px).
- **Layout:**
  - Top bar: wordmark left, pill navigation (Home, one entry per strategy) centered, global 1D/4H segmented control right.
  - Home: hero heading and subtitle with last-updated time, three stat tiles (BUY count, SELL count, current timeframe), then one large tinted card per strategy (name, description, BUY/SELL pills, link).
  - Strategy page: heading and description, filter row (All/BUY/SELL, search, sector), then a responsive grid of stock cards (ticker, name, signal pill, sparkline, price, "N bars ago").
  - Clicking a stock card opens a modal (Esc and the close button dismiss it) with the chart.
- **Chart (TradingView-style):**
  - Candlesticks (up = filled green, down = hollow red), right-hand price axis, faint grid, last-price tag, time axis, and an OHLC header line.
  - The candle where the signal fired gets a labelled arrow marker: green "BUY" arrow below the candle, red "SELL" arrow above it, plus a faint vertical guide through all panes.
  - **RSI pane:** RSI(14) line; the strategy's own levels drawn as solid accent lines with axis tags and a lightly shaded band between them (Strategy 1: 20 and 80; Strategy 2: 40 and 60); faint dashed 30/50/70 reference lines; a dot on the RSI line at the signal bar.
  - **MACD pane (12, 26, 9):** MACD and signal lines, zero line, and a four-shade histogram (stronger colour when the bar is growing, lighter when shrinking). For Strategy 1 the "Deep low" / "Deep high" thresholds (10th and 90th percentile of the trailing 100 histogram values) are drawn as dashed accent lines with axis tags.
  - **Price pane:** for Strategy 2, EMA 50 and EMA 200 overlays.
  - The implementation uses TradingView Lightweight Charts panes with price lines; the mockup only illustrates the look.
- **Motion:** minimal; short fades. Respect `prefers-reduced-motion`.
- **Dark mode:** out of scope for the MVP; colours are CSS variables so it can be added later.
- **Responsive:** one column on phones; the chart scales to the modal width and the modal becomes full-width.

## 7. Error handling

- Per-ticker failures are logged and skipped; the run summary prints counts of fetched, skipped, and flagged tickers.
- Universe scrape failure falls back to the saved list with a warning.
- Hard failures stop the deploy and keep the last good site live.
- If the push to the `data` branch fails after a successful deploy, the workflow is marked failed. The signals are re-detected on the next run if still inside the 3-bar window; otherwise that run's signals are lost from history (accepted for MVP).
- Frontend handles missing or malformed JSON with the error state, never a blank page.

## 8. Testing

- **pytest (scanner):** indicator values against known reference series; each strategy rule on small synthetic fixtures that should and should not fire; bars-ago window logic; closed-bar trimming; 4H resampling bin boundaries.
- **Smoke test:** the scanner end to end on ~5 tickers (marked so it can be skipped offline).
- **Vitest (web):** stock cards render from fixture JSON, the timeframe selector defaults to 1D and switches data, filters work, and empty and error states show.
- **Store tests:** `record_signals` inserts new rows, ignores duplicates, and never alters existing rows; the database is created on first use.
- **Manual:** after the first deploy, check a flagged ticker against TradingView's MACD and RSI.

## 9. Delivery steps (for the plan)

1. Scanner skeleton, universe, data fetch and resample, tests.
2. Indicators and both strategies, tests.
3. JSON writer, signal store (`store.py`), and `run.py`.
4. Web app: home and strategy pages, chart panel.
5. Workflow (including the `data` branch history step), Pages deployment, repo creation under `nsoni8882`.

## 10. Risks and open items

- `yfinance` is unofficial and may rate-limit or break. For friends-only use this is accepted; the 10% failure threshold protects against publishing a half-empty site.
- The Strategy 1 signal count may be very low. Thresholds are configurable; revisit after seeing real output.
- Scheduled workflows on GitHub can be delayed or skipped under load, and are disabled after 60 days of repo inactivity. A manual `workflow_dispatch` is available.
- The history database is only as complete as the scheduled runs. A skipped run can miss a signal whose 3-bar window has passed. Accepted for MVP.
- SQLite in git is a pragmatic choice for a single writer. Concurrent writers are prevented by the workflow concurrency group. If history needs to be queried by the site or by multiple writers, move behind `store.py` to a hosted database.

## 11. Future phase: signal validation (not in MVP)

Out of scope to build now; the MVP only guarantees the data needed for it is recorded. Outline:

- A daily evaluator step reads signals with no outcome yet, pulls the prices after `fired_at`, and writes `outcomes` rows.
- **Candidate rules (to be decided with the owner later):** return after N bars (e.g. 5, 10, 20); hit +X% before −Y% within N bars (WIN / LOSS / EXPIRED); outcome relative to the S&P 500 over the same window.
- Because `entry_price`, `fired_at`, and indicator details are stored immutably, any of these rules can be applied retroactively to all past signals, and rules can be changed without losing data.
- A performance page would show hit rate, average return, and per-strategy / per-timeframe breakdowns. This will require the site to read from the database (e.g. exporting a JSON summary at build time).
