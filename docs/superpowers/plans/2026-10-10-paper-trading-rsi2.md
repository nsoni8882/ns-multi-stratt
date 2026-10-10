# Paper Trading (RSI(2) on AMZN and AAPL) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third dashboard tab that places market-on-close orders for AMZN and AAPL on an Alpaca paper account, and publishes the account, trades, P/L and a live-vs-backtest evaluation as static JSON.

**Architecture:** A new top-level `trader/` package (stdlib only) holds the pure RSI(2) rule, an Alpaca HTTP client, the decision loop, the JSON exporter and the evaluation. A new `trade.yml` workflow runs it on a 15:25 ET weekday cron with repository secrets and writes its output to the `data` branch; `scan.yml` keeps sole ownership of the Pages deployment and copies that file into the build. The web app gets a `/paper` route rendering the file.

**Tech Stack:** Python 3.14 standard library only for `trader/` (no SDK, no pandas); pandas + yfinance in the one offline drift test; pytest; Vite + React + TypeScript + Vitest for the page; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-10-paper-trading-rsi2-design.md`

## Global Constraints

- `trader/` imports **standard library only**. No `requests`, no `alpaca-py`, no pandas. The single exception is `trader/tests/test_rule_matches_backtest.py`, which may import pandas and numpy.
- Trading base URL is `https://paper-api.alpaca.markets`, hardcoded. The run aborts if `"paper"` is not in it.
- Data base URL is `https://data.alpaca.markets`, feed `sip`, `adjustment=all`, with `end` held **16 minutes** behind now.
- Rule constants, exact: `RSI_LEN=2`, `BUY_BELOW=10.0`, `SELL_ABOVE=65.0`, `TREND_LEN=200`, `MAX_HOLD=10`.
- Sizing: `SLICE_PCT=0.50`, `MAX_CONCURRENT=2`, whole shares only, computed from `equity` and **never** from `buying_power`.
- Symbols: exactly `["AMZN", "AAPL"]`.
- Orders: `type="market"`, `time_in_force="cls"`. Refuse to submit with under 10 minutes to the close.
- Credentials from `ALPACA_KEY_ID` / `ALPACA_SECRET_KEY` env vars only. Never written to a file, never committed.
- Local test command becomes `.venv/bin/python -m pytest scanner/tests research/tests trader/tests -q`.
- Python: use `.venv/bin/python` for everything local; there is no activated environment.
- Commit after every task; push to `origin main` at the end of each task.

## Review Focus

Five conditions the spec implies that no task's happy path exercises. Each has a test assigned to the task that owns the code.

1. **A partial bar arrives as the last row twice in one day.** A second run on the same date must not re-enter a symbol already entered today, or double-count `bars_held`. → Task 5, `test_second_run_same_day_is_idempotent`.
2. **Alpaca returns a bar list shorter than 200 rows** (new listing, truncated feed, API hiccup). SMA(200) is then undefined and the symbol must be skipped, not treated as "no trend gate". → Task 1, `test_insufficient_history_returns_no_decision`.
3. **A position exists at the broker that the state file does not know about** (state lost, or filled outside the bot). `bars_held` must be recovered from filled order history, and a missing recovery must not silently become "entered today". → Task 4, `test_entry_date_recovered_from_order_history` and `test_unknown_entry_date_is_reported_not_guessed`.
4. **The ledger is empty or holds only an open trade** on day one. Export and evaluation must produce a renderable file with zero trades and a `null` verdict, never divide by zero. → Task 7, `test_export_day_one_empty_ledger`; Task 6, `test_evaluate_with_no_closed_trades`.
5. **A run lands after 15:50 ET, or a scheduled run is missed entirely.** The page must say so rather than show a stale panel as current. → Task 5, `test_refuses_to_submit_inside_cutoff`; Task 9, `PaperPage` renders the late/missed banner from `runs`; Task 10, `PaperRuns`.

---

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `trader/__init__.py` | Empty package marker. |
| `trader/params.py` | The constants, `SYMBOLS`, and `params()` / `rules_version()` / `HISTORY`. The single source of every threshold. |
| `trader/rule.py` | `wilder_rsi`, `sma`, `decide()`. Pure functions over a list of closes. No I/O. |
| `trader/alpaca.py` | `Alpaca` class: `account`, `clock`, `calendar`, `daily_closes`, `positions`, `open_order_symbols`, `closed_buy_orders`, `submit`, `portfolio_history`. |
| `trader/state.py` | Read/write `paper_state.json`; `opening_balance`, entry dates, recovery from order history. |
| `trader/sizing.py` | `shares_for()` — slice to whole shares with the concurrency and buying-power refusals. |
| `trader/run.py` | The decision loop and `__main__` entry point. Writes the ledgers. |
| `trader/ledger.py` | `append_jsonl()` with a keep-last-N cap, for `paper_trades.jsonl` and `paper_runs.jsonl`. |
| `trader/evaluate.py` | `evaluate()` — live round trips vs the backtested expectation. |
| `trader/export.py` | `build()` — assembles `paper-trading.json` from account, positions, ledgers and evaluation. |
| `trader/ACCEPTANCE.md` | The bar, written before the numbers exist. |
| `trader/tests/*` | The seven test modules in the spec's §6 table. |
| `trader/tests/fixtures/*` | Recorded Alpaca responses and the cached AMZN/AAPL CSV. |
| `web/src/pages/PaperPage.tsx` | The route: loads the file, composes the panels. |
| `web/src/components/PaperBalance.tsx` | The five-cell stat row. |
| `web/src/components/PaperEquityCurve.tsx` | The inline-SVG equity line with in-position bands. |
| `web/src/components/PaperPositions.tsx` | Open-position cards with the bars-held meter. |
| `web/src/components/PaperSignalRows.tsx` | The two per-symbol rule-state rows. |
| `web/src/components/PaperTrades.tsx` | The trade table plus the live-vs-backtest block. |
| `web/src/components/PaperRuns.tsx` | The collapsed run log and the late/missed banner. |
| `.github/workflows/trade.yml` | The 15:25 ET cron that runs the bot. |

**Modified:**

| File | Change |
|---|---|
| `web/src/types.ts` | Add the `PaperTradingFile` interface and its nested types. |
| `web/src/api.ts` | Add `getPaperTrading()`. |
| `web/src/App.tsx` | Add the `/paper` route. |
| `web/src/components/TopBar.tsx` | Add the Paper Trading nav link after the strategy links. |
| `web/src/theme.css` | Add the classes the new components need. |
| `web/src/test-fixtures.ts` | Add a `paperTradingFile` fixture. |
| `.github/workflows/scan.yml` | Fetch `paper-trading.json` from the `data` branch into `web/public/data/` before the build. |
| `CLAUDE.md` | Document the package, the test command, and the paper-trading conventions. |
| `.gitignore` | Ignore `paper_state.json` and `trader/.cache/`. |

---

### Task 1: The pure rule

**Files:**
- Create: `trader/__init__.py`, `trader/params.py`, `trader/rule.py`
- Create: `trader/tests/__init__.py`, `trader/tests/test_rule.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `trader.params.SYMBOLS: list[str]`, `RSI_LEN`, `BUY_BELOW`, `SELL_ABOVE`, `TREND_LEN`, `MAX_HOLD`, `SLICE_PCT`, `MAX_CONCURRENT`
  - `trader.params.params() -> dict`
  - `trader.rule.wilder_rsi(closes: list[float], n: int) -> float | None`
  - `trader.rule.sma(closes: list[float], n: int) -> float | None`
  - `trader.rule.decide(closes: list[float], *, held: bool, bars_held: int) -> Decision`
  - `trader.rule.Decision` — a frozen dataclass with fields `action: str` (`"buy" | "sell" | "hold" | "wait" | "skip"`), `reason: str`, `rsi2: float | None`, `sma200: float | None`, `price: float | None`, `trend_gap_pct: float | None`

- [ ] **Step 1: Write the failing test**

```python
# trader/tests/test_rule.py
import math

import pytest

from trader import params
from trader.rule import Decision, decide, sma, wilder_rsi


def rising(n, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def test_sma_needs_full_window():
    assert sma([1.0, 2.0], 3) is None
    assert sma([1.0, 2.0, 3.0], 3) == 2.0


def test_wilder_rsi_all_up_is_100():
    assert wilder_rsi(rising(50), 2) == 100.0


def test_insufficient_history_returns_no_decision():
    """Fewer than TREND_LEN closes leaves SMA(200) undefined. Skip the symbol -- an
    undefined trend gate is not an open trend gate."""
    d = decide(rising(199), held=False, bars_held=0)
    assert d.action == "skip"
    assert "history" in d.reason
    assert d.sma200 is None


def test_oversold_in_uptrend_buys():
    # 400 rising bars, then a sharp two-day drop: price stays far above the 200-day mean
    # while RSI(2) collapses under 10.
    closes = rising(400) + [460.0, 420.0]
    d = decide(closes, held=False, bars_held=0)
    assert d.action == "buy"
    assert d.rsi2 < params.BUY_BELOW
    assert d.price > d.sma200
    assert d.trend_gap_pct > 0


def test_oversold_below_trend_is_blocked():
    """The 200-day gate is load-bearing: the same trigger below it earned more per trade
    but with a 24% drawdown and a Sharpe of 0.11. Reject, do not buy."""
    closes = rising(400, start=500.0, step=-1.0) + [95.0, 90.0]
    d = decide(closes, held=False, bars_held=0)
    assert d.action == "wait"
    assert d.reason == "trend gate blocked"
    assert d.price < d.sma200
    assert d.trend_gap_pct < 0


def test_not_oversold_waits():
    d = decide(rising(400), held=False, bars_held=0)
    assert d.action == "wait"
    assert d.reason == "not oversold"


def test_held_position_exits_on_rsi():
    closes = rising(400) + [460.0, 420.0, 470.0]
    d = decide(closes, held=True, bars_held=2)
    assert d.action == "sell"
    assert d.reason == "rsi"
    assert d.rsi2 > params.SELL_ABOVE


def test_held_position_exits_on_time_stop_at_exactly_max_hold():
    closes = rising(400) + [460.0, 420.0, 421.0]
    d = decide(closes, held=True, bars_held=params.MAX_HOLD)
    assert d.action == "sell"
    assert d.reason == "time_stop"


def test_held_position_holds_one_bar_short_of_the_time_stop():
    closes = rising(400) + [460.0, 420.0, 421.0]
    d = decide(closes, held=True, bars_held=params.MAX_HOLD - 1)
    assert d.action == "hold"


def test_decision_is_frozen():
    d = decide(rising(400), held=False, bars_held=0)
    with pytest.raises(Exception):
        d.action = "buy"  # type: ignore[misc]


def test_params_covers_every_threshold_that_moves_a_signal():
    p = params.params()
    for key in ("rsi_len", "buy_below", "sell_above", "trend_len", "max_hold",
                "slice_pct", "max_concurrent", "symbols"):
        assert key in p, key
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest trader/tests/test_rule.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trader'`

- [ ] **Step 3: Write the minimal implementation**

```python
# trader/__init__.py
```

```python
# trader/params.py
"""Every threshold that can change which bars fire, in one place.

`rules_version()` fingerprints these onto every ledger row and into the published JSON, so a
threshold change splits the live record cleanly instead of blending two rule generations --
the same contract `scanner/strategies/base.py` enforces for the screener.
"""
from scanner.strategies.base import Release, rules_version as _fingerprint

SYMBOLS = ["AMZN", "AAPL"]

RSI_LEN = 2
BUY_BELOW = 10.0
SELL_ABOVE = 65.0
TREND_LEN = 200
MAX_HOLD = 10  # trading sessions, counted off Alpaca's calendar

SLICE_PCT = 0.50  # fraction of *equity* per position; never of buying_power
MAX_CONCURRENT = 2

LOOKBACK_DAYS = 420  # calendar days requested; ~289 sessions, enough for SMA(200)


def params() -> dict:
    """Everything that decides whether an order is placed."""
    return {
        "rsi_len": RSI_LEN,
        "buy_below": BUY_BELOW,
        "sell_above": SELL_ABOVE,
        "trend_len": TREND_LEN,
        "max_hold": MAX_HOLD,
        "slice_pct": SLICE_PCT,
        "max_concurrent": MAX_CONCURRENT,
        "symbols": SYMBOLS,
    }


def rules_version() -> str:
    return _fingerprint(params())


# Newest first, like the strategies. The top entry's fingerprint is build-asserted in
# trader/tests/test_params.py, so changing a threshold without adding an entry fails.
HISTORY = (
    Release("1.0.0", "2026-10-10",
            "First version. Buys AMZN or AAPL when RSI(2) falls under 10 while the price "
            "is still above its 200-day average, and sells when RSI(2) recovers past 65 or "
            "ten trading days pass. Half the account per name, no stop, paper money only.",
            fingerprint=""),  # filled in at Task 8, once the fingerprint is read off the code
)
```

```python
# trader/rule.py
"""The RSI(2) reversion rule. Pure functions over a list of closes -- no I/O, no broker.

Deliberately a second implementation of what research/ computes with pandas, because the
live path must stay dependency-free. trader/tests/test_rule_matches_backtest.py diffs the
two over real AMZN and AAPL history so they cannot drift apart unnoticed.
"""
from dataclasses import dataclass

from trader import params


@dataclass(frozen=True)
class Decision:
    action: str  # "buy" | "sell" | "hold" | "wait" | "skip"
    reason: str
    rsi2: "float | None" = None
    sma200: "float | None" = None
    price: "float | None" = None
    trend_gap_pct: "float | None" = None


def wilder_rsi(closes, n):
    """Wilder RSI, seeded the same way as pandas ewm(alpha=1/n, adjust=False).

    Verified against the pandas implementation to 2e-14 over SPY's full history.
    """
    if len(closes) < n + 2:
        return None
    au = ad = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        au += (max(d, 0.0) - au) / n
        ad += (max(-d, 0.0) - ad) / n
    if ad == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + au / ad)


def sma(closes, n):
    return sum(closes[-n:]) / n if len(closes) >= n else None


def decide(closes, *, held: bool, bars_held: int) -> Decision:
    """What to do with one symbol, given its closes (last element = today's partial bar).

    `skip` means the inputs cannot support a decision, which is not the same as `wait`:
    an undefined SMA(200) must never read as an open trend gate.
    """
    r = wilder_rsi(closes, params.RSI_LEN)
    trend = sma(closes, params.TREND_LEN)
    if r is None or trend is None:
        return Decision("skip", f"not enough history ({len(closes)} bars)", rsi2=r,
                        sma200=trend, price=closes[-1] if closes else None)
    price = closes[-1]
    gap = (price / trend - 1.0) * 100.0

    if held:
        if r > params.SELL_ABOVE:
            return Decision("sell", "rsi", r, trend, price, gap)
        if bars_held >= params.MAX_HOLD:
            return Decision("sell", "time_stop", r, trend, price, gap)
        return Decision("hold", f"{bars_held} of {params.MAX_HOLD} bars", r, trend, price, gap)

    if r >= params.BUY_BELOW:
        return Decision("wait", "not oversold", r, trend, price, gap)
    if price <= trend:
        return Decision("wait", "trend gate blocked", r, trend, price, gap)
    return Decision("buy", "oversold in uptrend", r, trend, price, gap)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/test_rule.py -q`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add trader/__init__.py trader/params.py trader/rule.py trader/tests/
git commit -m "feat(trader): the RSI(2) reversion rule, as pure functions

Entry at RSI(2) < 10 while price holds above its 200-day mean; exit at
RSI(2) > 65 or ten sessions. An undefined SMA(200) returns 'skip' rather
than 'wait', so a short bar list can never read as an open trend gate.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 2: The drift guard — stdlib rule vs the pandas backtest

The spec's §3 names this as the price of having the rule twice. The handoff proved it once by
hand over 6,313 bars of SPY; this makes it a committed test on the two symbols that trade.

**Files:**
- Create: `trader/tests/test_rule_matches_backtest.py`
- Create: `trader/tests/fixtures/AMZN.csv`, `trader/tests/fixtures/AAPL.csv`
- Create: `trader/tests/fixtures/make_fixtures.py`

**Interfaces:**
- Consumes: `trader.rule.wilder_rsi`, `trader.rule.sma`, `trader.params`.
- Produces: nothing other tasks use.

- [ ] **Step 1: Generate the fixtures** (network, once — the test itself is offline)

```python
# trader/tests/fixtures/make_fixtures.py
"""Regenerate the cached closes the drift test runs on. Network; run by hand, not in CI.

    .venv/bin/python trader/tests/fixtures/make_fixtures.py
"""
from pathlib import Path

import yfinance as yf

for sym in ("AMZN", "AAPL"):
    close = yf.download(sym, start="2000-01-01", auto_adjust=True, progress=False)["Close"].squeeze()
    out = Path(__file__).parent / f"{sym}.csv"
    close.rename("close").to_csv(out, date_format="%Y-%m-%d")
    print(sym, len(close), "->", out)
```

Run: `.venv/bin/python trader/tests/fixtures/make_fixtures.py`
Expected: two CSVs, roughly 6,400 rows each.

- [ ] **Step 2: Write the failing test**

```python
# trader/tests/test_rule_matches_backtest.py
"""The two implementations of one rule must agree, bar for bar.

`trader/rule.py` is stdlib-only because the live path takes no dependencies; `research/` and
the original backtest use pandas. That is a deliberate duplication, and this is what stops it
drifting: every entry signal over ~6,400 bars of real AMZN and AAPL history, computed both
ways, must match exactly. Offline -- the closes are cached fixtures.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trader import params
from trader.rule import sma, wilder_rsi

FIXTURES = Path(__file__).parent / "fixtures"


def pandas_rsi(close, n):
    d = close.diff()
    au = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    ad = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad.replace(0, np.nan))


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_rsi_and_sma_match_pandas_to_floating_point(symbol):
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    want_rsi = pandas_rsi(close, params.RSI_LEN)
    want_sma = close.rolling(params.TREND_LEN).mean()
    closes = [float(x) for x in close.to_numpy()]

    # Walk the series the way the live bot sees it: a growing prefix ending at each bar.
    checked = 0
    for i in range(params.TREND_LEN, len(closes), 7):  # every 7th bar keeps the test ~1s
        prefix = closes[: i + 1]
        got_r, got_s = wilder_rsi(prefix, params.RSI_LEN), sma(prefix, params.TREND_LEN)
        assert got_r == pytest.approx(float(want_rsi.iloc[i]), abs=1e-9), f"{symbol} RSI bar {i}"
        assert got_s == pytest.approx(float(want_sma.iloc[i]), rel=1e-12), f"{symbol} SMA bar {i}"
        checked += 1
    assert checked > 800, f"only checked {checked} bars"


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_entry_signals_agree_exactly(symbol):
    """The number that matters: identical entry decisions, not merely close indicators."""
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    want = ((pandas_rsi(close, params.RSI_LEN) < params.BUY_BELOW)
            & (close > close.rolling(params.TREND_LEN).mean())).fillna(False).to_numpy()
    closes = [float(x) for x in close.to_numpy()]

    disagreements = []
    for i in range(params.TREND_LEN, len(closes)):
        prefix = closes[: i + 1]
        r, s = wilder_rsi(prefix, params.RSI_LEN), sma(prefix, params.TREND_LEN)
        got = r is not None and s is not None and r < params.BUY_BELOW and prefix[-1] > s
        if got != bool(want[i]):
            disagreements.append((i, close.index[i].date(), r, s, bool(want[i]), got))
    assert disagreements == [], f"{symbol}: {len(disagreements)} disagreements, first {disagreements[:3]}"
```

- [ ] **Step 3: Run the test to verify it fails before the fixtures exist**

Temporarily rename one fixture, run, and confirm the failure is a missing file rather than a
passing test on no data:

Run: `mv trader/tests/fixtures/AMZN.csv /tmp/AMZN.csv && .venv/bin/python -m pytest trader/tests/test_rule_matches_backtest.py -q; mv /tmp/AMZN.csv trader/tests/fixtures/AMZN.csv`
Expected: FAIL — `FileNotFoundError`.

- [ ] **Step 4: Run the test for real**

Run: `.venv/bin/python -m pytest trader/tests/test_rule_matches_backtest.py -q`
Expected: PASS, 4 tests. If the entry-signal test fails, `trader/rule.py` is wrong — fix the
rule, never the test's expectation.

- [ ] **Step 5: Commit**

```bash
git add trader/tests/test_rule_matches_backtest.py trader/tests/fixtures/
git commit -m "test(trader): pin the stdlib rule to the pandas backtest

The live rule is stdlib-only by design and research/ uses pandas, so one rule
exists twice. This diffs them over ~6,400 bars of real AMZN and AAPL closes and
asserts identical entry signals, so the duplication cannot drift unnoticed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 3: The Alpaca client

**Files:**
- Create: `trader/alpaca.py`, `trader/tests/test_alpaca.py`
- Create: `trader/tests/fixtures/capture.py`, `trader/tests/fixtures/alpaca/*.json`

**Interfaces:**
- Consumes: `trader.params.LOOKBACK_DAYS`, `trader.params.SYMBOLS`.
- Produces:
  - `trader.alpaca.TRADING = "https://paper-api.alpaca.markets"`, `trader.alpaca.DATA = "https://data.alpaca.markets"`
  - `trader.alpaca.AlpacaError(RuntimeError)` with attributes `status: int`, `body: str`
  - `trader.alpaca.Alpaca(key: str, secret: str, *, opener=None)` with methods
    `account() -> dict`, `clock() -> dict`, `calendar(start: str, end: str) -> list[dict]`,
    `daily_closes(symbol: str) -> list[tuple[str, float]]`, `positions() -> dict[str, dict]`,
    `open_order_symbols() -> set[str]`, `last_filled_buy(symbol: str) -> dict | None`,
    `submit(symbol: str, side: str, qty: int) -> dict`,
    `portfolio_history(period: str = "all") -> dict`
  - `trader.alpaca.minutes_to_close(clock: dict) -> float`
  - `trader.alpaca.sessions_between(calendar: list[dict], after: str, through: str) -> int`

`opener` is the seam the tests use: a callable `(url, data, headers, method) -> bytes`. The
default performs a real `urllib.request`. No test ever passes the default.

- [ ] **Step 1: Capture the fixtures** (network, once; run with the paper keys exported)

```python
# trader/tests/fixtures/capture.py
"""Record real Alpaca responses as test fixtures. Network; run by hand, not in CI.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python trader/tests/fixtures/capture.py

Writes one JSON file per endpoint into fixtures/alpaca/. Account numbers are the user's own
paper account; nothing here is a credential, but re-check before committing.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "alpaca"
OUT.mkdir(parents=True, exist_ok=True)
H = {"APCA-API-KEY-ID": os.environ["ALPACA_KEY_ID"],
     "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]}


def get(base, path, params=None):
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return json.loads(r.read())


end = datetime.now(timezone.utc) - timedelta(minutes=16)
start = (end - timedelta(days=420)).strftime("%Y-%m-%d")
TRADING, DATA = "https://paper-api.alpaca.markets", "https://data.alpaca.markets"

for name, value in [
    ("account", get(TRADING, "/v2/account")),
    ("clock", get(TRADING, "/v2/clock")),
    ("calendar", get(TRADING, "/v2/calendar", {"start": "2026-09-01", "end": "2026-10-31"})),
    ("positions", get(TRADING, "/v2/positions")),
    ("orders_open", get(TRADING, "/v2/orders", {"status": "open"})),
    ("orders_closed", get(TRADING, "/v2/orders", {"status": "closed", "limit": 50,
                                                  "direction": "desc"})),
    ("portfolio_history", get(TRADING, "/v2/account/portfolio/history", {"period": "1M",
                                                                        "timeframe": "1D"})),
    ("bars", get(DATA, "/v2/stocks/bars", {"symbols": "AMZN,AAPL", "timeframe": "1Day",
                                           "start": start,
                                           "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                           "adjustment": "all", "feed": "sip", "sort": "asc",
                                           "limit": 10000})),
]:
    (OUT / f"{name}.json").write_text(json.dumps(value, indent=1) + "\n")
    print("wrote", name)
```

Run: `ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python trader/tests/fixtures/capture.py`
Expected: eight files in `trader/tests/fixtures/alpaca/`.

Also hand-write two fixtures that cannot be captured on demand:

```json
// trader/tests/fixtures/alpaca/order_filled.json
{"id": "a1b2c3d4-0000-0000-0000-000000000001", "symbol": "AMZN", "side": "buy",
 "qty": "190", "filled_qty": "190", "filled_avg_price": "262.43", "type": "market",
 "time_in_force": "cls", "status": "filled",
 "submitted_at": "2026-10-12T19:25:11.000000Z", "filled_at": "2026-10-12T20:00:02.000000Z"}
```

```json
// trader/tests/fixtures/alpaca/error_422.json
{"code": 42210000, "message": "cls orders are not accepted at this time"}
```

- [ ] **Step 2: Write the failing test**

```python
# trader/tests/test_alpaca.py
"""The HTTP client, against recorded responses. No test touches the network."""
import json
from pathlib import Path

import pytest

from trader.alpaca import Alpaca, AlpacaError, TRADING, minutes_to_close, sessions_between

FIX = Path(__file__).parent / "fixtures" / "alpaca"


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


class Recorded:
    """An opener that answers from fixtures and records what it was asked."""

    def __init__(self, routes, error=None):
        self.routes, self.error, self.calls = routes, error, []

    def __call__(self, url, data, headers, method):
        self.calls.append({"url": url, "data": data, "method": method, "headers": headers})
        if self.error:
            raise self.error
        for fragment, name in self.routes.items():
            if fragment in url:
                return json.dumps(load(name)).encode()
        raise AssertionError(f"no fixture for {url}")


def client(routes, error=None):
    rec = Recorded(routes, error)
    return Alpaca("KEY", "SECRET", opener=rec), rec


def test_account_is_parsed():
    api, _ = client({"/v2/account": "account"})
    assert api.account()["status"] == "ACTIVE"


def test_credentials_go_in_the_headers_and_never_the_url():
    api, rec = client({"/v2/account": "account"})
    api.account()
    assert rec.calls[0]["headers"]["APCA-API-KEY-ID"] == "KEY"
    assert rec.calls[0]["headers"]["APCA-API-SECRET-KEY"] == "SECRET"
    assert "SECRET" not in rec.calls[0]["url"]


def test_daily_closes_returns_date_close_pairs_in_order():
    api, rec = client({"/v2/stocks/bars": "bars"})
    bars = api.daily_closes("AMZN")
    assert len(bars) > 200
    assert bars == sorted(bars)
    assert all(isinstance(d, str) and isinstance(c, float) for d, c in bars)


def test_daily_closes_holds_end_sixteen_minutes_back_for_the_sip_feed():
    """A free account may query SIP only when `end` is at least 15 minutes old."""
    api, rec = client({"/v2/stocks/bars": "bars"})
    api.daily_closes("AMZN")
    url = rec.calls[0]["url"]
    assert "feed=sip" in url
    assert "adjustment=all" in url
    from datetime import datetime, timezone
    import urllib.parse
    end = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["end"][0]
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(end.replace("Z", "+00:00")))
    assert 15 * 60 <= age.total_seconds() <= 20 * 60


def test_positions_keyed_by_symbol():
    api, _ = client({"/v2/positions": "positions"})
    assert isinstance(api.positions(), dict)


def test_submit_posts_a_market_on_close_order():
    api, rec = client({"/v2/orders": "order_filled"})
    api.submit("AMZN", "buy", 190)
    call = rec.calls[0]
    assert call["method"] == "POST"
    body = json.loads(call["data"])
    assert body == {"symbol": "AMZN", "qty": "190", "side": "buy",
                    "type": "market", "time_in_force": "cls"}


def test_submit_sends_whole_shares_as_a_string():
    api, rec = client({"/v2/orders": "order_filled"})
    api.submit("AAPL", "sell", 148)
    assert json.loads(rec.calls[0]["data"])["qty"] == "148"


def test_http_error_becomes_alpaca_error_carrying_status_and_body():
    import urllib.error
    import io
    err = urllib.error.HTTPError("u", 422, "Unprocessable", {},
                                 io.BytesIO(json.dumps(load("error_422")).encode()))
    api, _ = client({"/v2/orders": "order_filled"}, error=err)
    with pytest.raises(AlpacaError) as caught:
        api.submit("AMZN", "buy", 1)
    assert caught.value.status == 422
    assert "cls orders are not accepted" in caught.value.body


def test_minutes_to_close_reads_the_clock():
    clock = {"timestamp": "2026-10-12T15:25:00-04:00", "next_close": "2026-10-12T16:00:00-04:00",
             "is_open": True}
    assert minutes_to_close(clock) == pytest.approx(35.0)


def test_sessions_between_counts_trading_days_not_calendar_days():
    cal = [{"date": "2026-10-09"}, {"date": "2026-10-12"}, {"date": "2026-10-13"}]
    assert sessions_between(cal, "2026-10-09", "2026-10-13") == 2
    assert sessions_between(cal, "2026-10-13", "2026-10-13") == 0


def test_trading_endpoint_is_the_paper_host():
    assert "paper" in TRADING
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest trader/tests/test_alpaca.py -q`
Expected: FAIL — `ImportError: cannot import name 'Alpaca'`.

- [ ] **Step 4: Write the implementation**

```python
# trader/alpaca.py
"""Alpaca paper-trading and market-data client. Standard library only.

The endpoint is hardcoded to the paper host and trader/run.py refuses to start if that ever
stops being true. `opener` is the injection seam the tests use; nothing in the test suite
performs real I/O.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from trader import params

TRADING = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
FEED = "sip"  # free accounts may query SIP when `end` is at least 15 minutes old
END_HOLDBACK = timedelta(minutes=16)


class AlpacaError(RuntimeError):
    def __init__(self, status: int, body: str, method: str, path: str):
        super().__init__(f"{method} {path} -> HTTP {status}: {body[:400]}")
        self.status, self.body = status, body


def _urlopen(url, data, headers, method):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() or b"null"


def minutes_to_close(clock: dict) -> float:
    close_at = datetime.fromisoformat(clock["next_close"])
    now = datetime.fromisoformat(clock["timestamp"])
    return (close_at - now).total_seconds() / 60


def sessions_between(calendar: "list[dict]", after: str, through: str) -> int:
    """Trading sessions in (after, through] -- the backtest's bar count, not calendar days."""
    return len([d for d in calendar if after < d["date"] <= through])


class Alpaca:
    def __init__(self, key: str, secret: str, *, opener=None):
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                         "Content-Type": "application/json"}
        self._open = opener or _urlopen

    def _call(self, base, path, params_=None, method="GET", body=None):
        url = base + path + ("?" + urllib.parse.urlencode(params_) if params_ else "")
        data = json.dumps(body).encode() if body is not None else None
        try:
            return json.loads(self._open(url, data, dict(self._headers), method))
        except urllib.error.HTTPError as e:
            raise AlpacaError(e.code, e.read().decode(), method, path) from None

    def account(self) -> dict:
        return self._call(TRADING, "/v2/account")

    def clock(self) -> dict:
        return self._call(TRADING, "/v2/clock")

    def calendar(self, start: str, end: str) -> "list[dict]":
        return self._call(TRADING, "/v2/calendar", {"start": start, "end": end})

    def positions(self) -> "dict[str, dict]":
        return {p["symbol"]: p for p in self._call(TRADING, "/v2/positions")}

    def open_order_symbols(self) -> "set[str]":
        return {o["symbol"] for o in self._call(TRADING, "/v2/orders", {"status": "open"})}

    def last_filled_buy(self, symbol: str) -> "dict | None":
        orders = self._call(TRADING, "/v2/orders",
                            {"status": "closed", "symbols": symbol, "limit": 50,
                             "direction": "desc"})
        for o in orders:
            if o.get("side") == "buy" and o.get("filled_at"):
                return o
        return None

    def daily_closes(self, symbol: str) -> "list[tuple[str, float]]":
        """Adjusted daily closes, oldest first. The last element is today's partial bar."""
        end = datetime.now(timezone.utc) - END_HOLDBACK
        start = (end - timedelta(days=params.LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        out, token = [], None
        while True:
            q = {"symbols": symbol, "timeframe": "1Day", "start": start,
                 "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "adjustment": "all",
                 "feed": FEED, "sort": "asc", "limit": 10000}
            if token:
                q["page_token"] = token
            r = self._call(DATA, "/v2/stocks/bars", q)
            out += [(b["t"][:10], float(b["c"])) for b in (r.get("bars") or {}).get(symbol, [])]
            token = r.get("next_page_token")
            if not token:
                return out

    def submit(self, symbol: str, side: str, qty: int) -> dict:
        return self._call(TRADING, "/v2/orders", method="POST",
                          body={"symbol": symbol, "qty": str(int(qty)), "side": side,
                                "type": "market", "time_in_force": "cls"})

    def portfolio_history(self, period: str = "all") -> dict:
        return self._call(TRADING, "/v2/account/portfolio/history",
                          {"period": period, "timeframe": "1D"})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/test_alpaca.py -q`
Expected: PASS, 11 tests.

- [ ] **Step 6: Commit**

```bash
git add trader/alpaca.py trader/tests/test_alpaca.py trader/tests/fixtures/
git commit -m "feat(trader): Alpaca paper client, stdlib only

Account, clock, calendar, bars, positions, orders and portfolio history, with
an injected opener so every test runs against recorded responses and never the
network. \`end\` is held 16 minutes back, which is what lets a free account query
the SIP feed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 4: State, entry-date recovery and sizing

**Files:**
- Create: `trader/state.py`, `trader/sizing.py`, `trader/ledger.py`
- Create: `trader/tests/test_state.py`, `trader/tests/test_sizing.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `trader.params.SLICE_PCT`, `MAX_CONCURRENT`; `trader.alpaca.Alpaca.last_filled_buy`.
- Produces:
  - `trader.state.load(path) -> dict` / `trader.state.save(path, state) -> None`
  - `trader.state.opening_balance(state, equity: float) -> float` — records it once, on first call
  - `trader.state.entry_date(state, symbol, api, today: str) -> str | None` — state first, then
    order history; `None` when neither knows, never a guess
  - `trader.sizing.shares_for(equity: float, price: float, buying_power: float, n_held: int) -> tuple[int, str | None]`
    — `(qty, refusal)`; `refusal` is `None` when the order may proceed
  - `trader.ledger.append_jsonl(path, record: dict, keep: int = 500) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# trader/tests/test_sizing.py
from trader import params
from trader.sizing import shares_for


def test_half_the_equity_in_whole_shares():
    qty, refusal = shares_for(equity=100_000.0, price=262.43, buying_power=400_000.0, n_held=0)
    assert qty == 190  # floor(50_000 / 262.43)
    assert refusal is None


def test_sizing_ignores_margin_buying_power():
    """The account reports 4x buying power. Slices come off equity, never off that."""
    small, _ = shares_for(equity=10_000.0, price=100.0, buying_power=40_000.0, n_held=0)
    assert small == 50  # 50% of equity, not of buying power


def test_concurrency_cap_refuses_a_third_position():
    qty, refusal = shares_for(equity=100_000.0, price=100.0, buying_power=400_000.0,
                              n_held=params.MAX_CONCURRENT)
    assert qty == 0
    assert refusal == f"already holding {params.MAX_CONCURRENT} of {params.MAX_CONCURRENT}"


def test_slice_too_small_for_one_whole_share_is_refused():
    qty, refusal = shares_for(equity=100.0, price=262.43, buying_power=400.0, n_held=0)
    assert qty == 0
    assert "0 whole shares" in refusal


def test_insufficient_buying_power_is_refused():
    qty, refusal = shares_for(equity=100_000.0, price=100.0, buying_power=200.0, n_held=0)
    assert qty == 0
    assert "buying power" in refusal
```

```python
# trader/tests/test_state.py
import json

from trader import state


def test_opening_balance_is_recorded_once_and_never_moves():
    s = {}
    assert state.opening_balance(s, 100_000.0) == 100_000.0
    assert state.opening_balance(s, 123_456.0) == 100_000.0  # a later run must not overwrite it


def test_entry_date_prefers_the_state_file():
    s = {"positions": {"AMZN": {"entry_date": "2026-10-12"}}}
    assert state.entry_date(s, "AMZN", api=None, today="2026-10-20") == "2026-10-12"


def test_entry_date_recovered_from_order_history():
    """State lost, position still at the broker: recover from the last filled buy."""
    class Api:
        def last_filled_buy(self, symbol):
            return {"filled_at": "2026-10-12T20:00:02.000000Z"}

    assert state.entry_date({}, "AMZN", api=Api(), today="2026-10-20") == "2026-10-12"


def test_unknown_entry_date_is_reported_not_guessed():
    """Defaulting to today would silently reset the time stop every run."""
    class Api:
        def last_filled_buy(self, symbol):
            return None

    assert state.entry_date({}, "AMZN", api=Api(), today="2026-10-20") is None


def test_load_of_a_missing_or_corrupt_file_is_an_empty_state(tmp_path):
    assert state.load(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert state.load(bad) == {}


def test_save_then_load_round_trips(tmp_path):
    p = tmp_path / "paper_state.json"
    state.save(p, {"opening_balance": 100_000.0, "positions": {"AMZN": {"entry_date": "2026-10-12"}}})
    assert state.load(p)["positions"]["AMZN"]["entry_date"] == "2026-10-12"


def test_append_jsonl_keeps_only_the_last_n(tmp_path):
    from trader.ledger import append_jsonl
    p = tmp_path / "runs.jsonl"
    for i in range(10):
        append_jsonl(p, {"i": i}, keep=4)
    rows = [json.loads(line) for line in p.read_text().splitlines()]
    assert [r["i"] for r in rows] == [6, 7, 8, 9]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest trader/tests/test_state.py trader/tests/test_sizing.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trader.state'`

- [ ] **Step 3: Write the implementation**

```python
# trader/sizing.py
"""How many shares to buy, and the three reasons not to.

Slices come off `equity`. The paper account reports 4x that as `buying_power`; using it
would quietly lever a strategy whose backtest is unlevered.
"""
import math

from trader import params


def shares_for(equity: float, price: float, buying_power: float,
               n_held: int) -> "tuple[int, str | None]":
    if n_held >= params.MAX_CONCURRENT:
        return 0, f"already holding {n_held} of {params.MAX_CONCURRENT}"
    slice_value = equity * params.SLICE_PCT
    qty = math.floor(slice_value / price) if price > 0 else 0
    if qty < 1:
        return 0, f"a slice of ${slice_value:,.0f} buys 0 whole shares at ${price:,.2f}"
    if qty * price > buying_power:
        return 0, (f"needs ${qty * price:,.0f}, buying power is ${buying_power:,.0f}")
    return qty, None
```

```python
# trader/state.py
"""What the bot must remember between runs: the opening balance and each entry date.

Lives on the `data` branch, so a lost local file is not a disaster -- but it can still go
missing, and then `entry_date` recovers from filled order history. What it will not do is
default to today: that would reset the ten-session time stop on every run and a position
would never time out.
"""
import json
from pathlib import Path


def load(path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def save(path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def opening_balance(state: dict, equity: float) -> float:
    """The account's equity the first time the bot ever ran. Written once, then frozen."""
    if "opening_balance" not in state:
        state["opening_balance"] = float(equity)
    return float(state["opening_balance"])


def entry_date(state: dict, symbol: str, api, today: str) -> "str | None":
    known = (state.get("positions") or {}).get(symbol, {}).get("entry_date")
    if known:
        return known
    if api is None:
        return None
    order = api.last_filled_buy(symbol)
    return order["filled_at"][:10] if order and order.get("filled_at") else None
```

```python
# trader/ledger.py
"""Append-only JSONL, capped. The durable record of what the bot did and decided.

Same reasoning as scanner/ledger.py: an Actions log is deleted after 90 days, and the runs
worth reading later are exactly the ones that failed.
"""
import json
from pathlib import Path

KEEP = 500


def append_jsonl(path, record: dict, keep: int = KEEP) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text().splitlines() if p.exists() else []
    lines.append(json.dumps(record, sort_keys=True))
    lines = lines[-keep:]
    p.write_text("\n".join(lines) + "\n")
    return len(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/ -q`
Expected: PASS, all tests from Tasks 1-4.

- [ ] **Step 5: Ignore the local state file**

```bash
printf '\n# local paper-trading state (the real one lives on the data branch)\npaper_state.json\ntrader/.cache/\n' >> .gitignore
```

- [ ] **Step 6: Commit**

```bash
git add trader/state.py trader/sizing.py trader/ledger.py trader/tests/ .gitignore
git commit -m "feat(trader): state, entry-date recovery, sizing and the ledger

Slices are half of equity and never of the 4x buying power the paper account
reports. A lost state file recovers entry dates from filled order history, and
an unrecoverable one returns None rather than defaulting to today -- which would
reset the ten-session time stop on every run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 5: The decision loop

**Files:**
- Create: `trader/run.py`, `trader/tests/test_run.py`

**Interfaces:**
- Consumes: everything from Tasks 1, 3 and 4.
- Produces:
  - `trader.run.CUTOFF_MINUTES = 10`
  - `trader.run.run(api, *, live: bool, data_dir, today: str | None = None) -> dict`
    — the run record; also appends to the ledgers and saves state
  - `trader.run.main(argv=None) -> int`

`run()` takes the client, so the test drives it with a fake. It never constructs an `Alpaca`
itself; `main()` does that, reads the env vars, and asserts the paper endpoint.

- [ ] **Step 1: Write the failing test**

```python
# trader/tests/test_run.py
"""The decision loop, driven with a fake client. No network, no real orders."""
import json

import pytest

from trader import params, run


def closes(n=400, start=100.0, step=1.0, tail=()):
    return [(f"2026-01-{i % 28 + 1:02d}", start + i * step) for i in range(n)] + \
           [(f"2026-10-{i + 1:02d}", c) for i, c in enumerate(tail)]


class Fake:
    """Enough of Alpaca to drive run(). Records submitted orders."""

    def __init__(self, *, bars=None, positions=None, open_orders=(), equity=100_000.0,
                 minutes_left=35.0, is_open=True, last_buy=None):
        self.bars = bars or {s: closes(tail=[460.0, 420.0]) for s in params.SYMBOLS}
        self._positions = positions or {}
        self._open = set(open_orders)
        self.equity = equity
        self.minutes_left = minutes_left
        self.is_open = is_open
        self._last_buy = last_buy
        self.submitted = []

    def account(self):
        return {"account_number": "PA36V1RJY3GK", "status": "ACTIVE",
                "equity": str(self.equity), "cash": str(self.equity),
                "buying_power": str(self.equity * 4)}

    def clock(self):
        return {"is_open": self.is_open, "timestamp": "2026-10-12T15:25:00-04:00",
                "next_close": "2026-10-12T16:00:00-04:00", "next_open": "2026-10-13T09:30:00-04:00"}

    def calendar(self, start, end):
        return [{"date": f"2026-10-{d:02d}"} for d in range(1, 32)]

    def positions(self):
        return dict(self._positions)

    def open_order_symbols(self):
        return set(self._open)

    def last_filled_buy(self, symbol):
        return self._last_buy

    def daily_closes(self, symbol):
        return self.bars[symbol]

    def portfolio_history(self, period="all"):
        return {"timestamp": [1760000000], "equity": [self.equity], "base_value": 100_000.0}

    def submit(self, symbol, side, qty):
        self.submitted.append((symbol, side, qty))
        return {"id": f"order-{len(self.submitted)}", "symbol": symbol, "side": side,
                "qty": str(qty), "filled_avg_price": None, "status": "accepted",
                "submitted_at": "2026-10-12T19:25:11Z", "filled_at": None}


def test_oversold_in_uptrend_submits_a_buy_for_each_symbol(tmp_path):
    api = Fake()
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert sorted(s for s, _, _ in api.submitted) == sorted(params.SYMBOLS)
    assert all(side == "buy" for _, side, _ in api.submitted)
    assert record["orders"] == 2


def test_dry_run_decides_but_submits_nothing(tmp_path):
    api = Fake()
    record = run.run(api, live=False, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["orders"] == 0
    assert record["decisions"]["AMZN"]["action"] == "buy"


def test_market_closed_does_nothing(tmp_path):
    api = Fake(is_open=False)
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["skip_reason"] == "market closed"


def test_refuses_to_submit_inside_cutoff(tmp_path):
    """Alpaca rejects cls orders after 15:50 ET. Under ten minutes to the close, stand down
    and say so -- submitting would produce a rejection, not a fill."""
    api = Fake(minutes_left=6.0)
    api.clock = lambda: {"is_open": True, "timestamp": "2026-10-12T15:54:00-04:00",
                         "next_close": "2026-10-12T16:00:00-04:00",
                         "next_open": "2026-10-13T09:30:00-04:00"}
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["late"] is True
    assert "cutoff" in record["skip_reason"]


def test_second_run_same_day_is_idempotent(tmp_path):
    """Two wake-ups in one session must not double a position or restart the time stop."""
    api = Fake()
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    first = list(api.submitted)
    # The broker now reports the positions the first run opened.
    api._positions = {s: {"symbol": s, "qty": "190", "unrealized_pl": "0",
                          "unrealized_plpc": "0", "current_price": "420.0"}
                      for s in params.SYMBOLS}
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == first, "a second run on the same day placed another order"


def test_open_order_blocks_a_second_order_for_that_symbol(tmp_path):
    api = Fake(open_orders=params.SYMBOLS)
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []


def test_held_position_sells_on_the_time_stop(tmp_path):
    held = {"AMZN": {"symbol": "AMZN", "qty": "190", "unrealized_pl": "100",
                     "unrealized_plpc": "0.01", "current_price": "421.0"}}
    api = Fake(positions=held, bars={s: closes(tail=[460.0, 420.0, 421.0]) for s in params.SYMBOLS})
    state_file = tmp_path / "paper_state.json"
    state_file.write_text(json.dumps({"opening_balance": 100_000.0,
                                      "positions": {"AMZN": {"entry_date": "2026-09-25"}}}))
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert ("AMZN", "sell", 190) in api.submitted


def test_a_rejected_order_is_logged_and_not_retried(tmp_path):
    from trader.alpaca import AlpacaError
    api = Fake()
    calls = []

    def boom(symbol, side, qty):
        calls.append(symbol)
        raise AlpacaError(422, "cls orders are not accepted at this time", "POST", "/v2/orders")

    api.submit = boom
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert calls == params.SYMBOLS or sorted(calls) == sorted(params.SYMBOLS)
    assert len(calls) == len(set(calls)), "an order was retried"
    assert record["errors"], "the rejection was not recorded"


def test_a_data_error_on_one_symbol_still_trades_the_other(tmp_path):
    from trader.alpaca import AlpacaError
    api = Fake()
    real = api.daily_closes

    def flaky(symbol):
        if symbol == "AMZN":
            raise AlpacaError(500, "upstream", "GET", "/v2/stocks/bars")
        return real(symbol)

    api.daily_closes = flaky
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert [s for s, _, _ in api.submitted] == ["AAPL"]


def test_short_bar_history_skips_the_symbol(tmp_path):
    api = Fake(bars={s: closes(n=150) for s in params.SYMBOLS})
    record = run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    assert api.submitted == []
    assert record["decisions"]["AMZN"]["action"] == "skip"


def test_the_run_is_appended_to_the_runs_ledger(tmp_path):
    api = Fake()
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    rows = [json.loads(line) for line in (tmp_path / "paper_runs.jsonl").read_text().splitlines()]
    assert rows[-1]["decisions"]["AAPL"]["rsi2"] < params.BUY_BELOW
    assert rows[-1]["rules_version"]


def test_a_fill_is_appended_to_the_trades_ledger_with_its_decision_context(tmp_path):
    api = Fake()
    run.run(api, live=True, data_dir=tmp_path, today="2026-10-12")
    rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text().splitlines()]
    row = next(r for r in rows if r["symbol"] == "AMZN")
    for key in ("side", "order_id", "decision_close", "rsi2", "sma200", "trend_gap_pct",
                "equity_at_decision", "slice_pct", "rules_version"):
        assert key in row, key
    assert row["decision_close"] == 420.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest trader/tests/test_run.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trader.run'`

- [ ] **Step 3: Write the implementation**

```python
# trader/run.py
"""The decision loop: one pass over AMZN and AAPL, at ~15:25 ET.

Reads the rule's inputs from Alpaca, decides per symbol, submits market-on-close orders, and
appends to two append-only ledgers -- one row per fill, and one row per run whether it traded
or not. The second is what makes a *non*-trade auditable later.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.run --dry-run
    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.run --live --data-dir history
"""
import argparse
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trader import params, state
from trader.alpaca import Alpaca, AlpacaError, TRADING, minutes_to_close, sessions_between
from trader.ledger import append_jsonl
from trader.rule import decide
from trader.sizing import shares_for

CUTOFF_MINUTES = 10  # Alpaca rejects `cls` orders after 15:50 ET; stand down inside this


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)


def run(api, *, live: bool, data_dir, today: "str | None" = None) -> dict:
    data_dir = Path(data_dir)
    state_file = data_dir / "paper_state.json"
    st = state.load(state_file)

    acct = api.account()
    equity, buying_power = float(acct["equity"]), float(acct["buying_power"])
    clock = api.clock()
    today = today or clock["timestamp"][:10]
    opening = state.opening_balance(st, equity)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "date": today, "mode": "live" if live else "dry-run",
              "rules_version": params.rules_version(), "equity": equity,
              "opening_balance": opening, "orders": 0, "late": False,
              "skip_reason": None, "decisions": {}, "errors": []}

    if not clock["is_open"]:
        record["skip_reason"] = "market closed"
        log("market closed; next open", clock["next_open"])
        append_jsonl(data_dir / "paper_runs.jsonl", record)
        state.save(state_file, st)
        return record

    left = minutes_to_close(clock)
    record["minutes_to_close"] = round(left, 1)
    if left < CUTOFF_MINUTES:
        record["late"] = True
        record["skip_reason"] = f"inside the {CUTOFF_MINUTES}-minute cutoff; cls would be rejected"
        log(record["skip_reason"])
        append_jsonl(data_dir / "paper_runs.jsonl", record)
        state.save(state_file, st)
        return record

    positions = api.positions()
    open_orders = api.open_order_symbols()
    cal_start = (datetime.fromisoformat(today) - timedelta(days=90)).strftime("%Y-%m-%d")
    calendar = api.calendar(cal_start, today)
    n_held = len(positions)
    st.setdefault("positions", {})

    for symbol in params.SYMBOLS:
        try:
            bars = api.daily_closes(symbol)
        except AlpacaError as e:
            record["errors"].append({"symbol": symbol, "stage": "data", "error": str(e)})
            log(f"{symbol}: data error, skipped -- {e}")
            continue

        closes = [c for _, c in bars]
        held = symbol in positions
        entry = state.entry_date(st, symbol, api, today) if held else None
        bars_held = sessions_between(calendar, entry, today) if entry else 0
        d = decide(closes, held=held, bars_held=bars_held)
        row = asdict(d) | {"bars_held": bars_held, "entry_date": entry, "held": held}
        record["decisions"][symbol] = row
        log(f"{symbol}: {d.action} ({d.reason}) rsi2="
            f"{d.rsi2 if d.rsi2 is None else round(d.rsi2, 1)} px={d.price}")

        if symbol in open_orders:
            row["skipped"] = "an order is already working"
            continue
        if d.action in ("skip", "wait", "hold"):
            continue
        if held and entry is None:
            # Nothing knows when this position was opened, so the time stop cannot be judged.
            # Exit on the RSI rule only, and say so.
            if d.reason == "time_stop":
                row["skipped"] = "entry date unknown; time stop not judged"
                continue

        if d.action == "buy":
            if st["positions"].get(symbol, {}).get("entered_on") == today:
                row["skipped"] = "already entered today"
                continue
            qty, refusal = shares_for(equity, d.price, buying_power, n_held)
            if refusal:
                row["skipped"] = refusal
                log(f"  entry refused -- {refusal}")
                continue
        else:
            qty = abs(int(float(positions[symbol]["qty"])))

        if not live:
            log(f"  DRY-RUN would submit {d.action.upper()} {qty} {symbol} MOC")
            continue

        try:
            order = api.submit(symbol, "buy" if d.action == "buy" else "sell", qty)
        except AlpacaError as e:
            # Deliberately not retried: a retry could land past the cutoff, or re-submit an
            # order the rule no longer wants. Log it and leave the symbol as it is.
            record["errors"].append({"symbol": symbol, "stage": "order", "status": e.status,
                                     "error": str(e)})
            row["skipped"] = f"order rejected: {e.status}"
            log(f"  order rejected -- {e}")
            continue

        record["orders"] += 1
        trade = {"symbol": symbol, "side": order["side"], "order_id": order["id"],
                 "submitted_at": order.get("submitted_at"), "filled_at": order.get("filled_at"),
                 "filled_qty": order.get("filled_qty"), "status": order.get("status"),
                 "filled_avg_price": order.get("filled_avg_price"),
                 "qty": qty, "date": today, "decision_close": d.price, "rsi2": d.rsi2,
                 "sma200": d.sma200, "trend_gap_pct": d.trend_gap_pct,
                 "equity_at_decision": equity, "slice_pct": params.SLICE_PCT,
                 "rules_version": params.rules_version()}
        if d.action == "sell":
            trade |= {"exit_reason": d.reason, "bars_held": bars_held, "entry_date": entry,
                      "entry_price": st["positions"].get(symbol, {}).get("entry_price")}
        append_jsonl(data_dir / "paper_trades.jsonl", trade)

        if d.action == "buy":
            st["positions"][symbol] = {"entry_date": today, "entered_on": today,
                                       "entry_price": d.price, "qty": qty}
            n_held += 1
        else:
            st["positions"].pop(symbol, None)
            n_held = max(0, n_held - 1)

    append_jsonl(data_dir / "paper_runs.jsonl", record)
    state.save(state_file, st)
    log("done:", record["orders"], "order(s)")
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--live", action="store_true", help="submit real paper orders")
    g.add_argument("--dry-run", action="store_true", help="decide only (the default)")
    ap.add_argument("--data-dir", default="history", help="where the ledgers and state live")
    args = ap.parse_args(argv)

    if "paper" not in TRADING:
        sys.exit("Refusing to run: the trading endpoint is not the paper API.")
    key, secret = os.environ.get("ALPACA_KEY_ID", ""), os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        sys.exit("Set ALPACA_KEY_ID and ALPACA_SECRET_KEY (paper keys).")

    api = Alpaca(key, secret)
    acct = api.account()
    log(f"account {acct['account_number']} equity ${float(acct['equity']):,.2f} "
        f"mode {'LIVE-PAPER' if args.live else 'DRY-RUN'}")
    run(api, live=args.live, data_dir=args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/test_run.py -q`
Expected: PASS, 12 tests.

- [ ] **Step 5: Commit**

```bash
git add trader/run.py trader/tests/test_run.py
git commit -m "feat(trader): the decision loop

One pass over AMZN and AAPL: decide, size, submit market-on-close, and append
both a per-fill and a per-run ledger row so a non-trade is as auditable as a
trade. Stands down inside ten minutes of the close, never retries a rejected
order, and a data error on one symbol leaves the other tradeable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 6: Evaluation — the live record against the backtest

**Files:**
- Create: `trader/evaluate.py`, `trader/tests/test_evaluate.py`

**Interfaces:**
- Consumes: `trader.params.SYMBOLS`.
- Produces:
  - `trader.evaluate.BACKTEST: dict[str, dict]` — the measured expectation per symbol
  - `trader.evaluate.TRADES_NEEDED = 30`
  - `trader.evaluate.round_trips(rows: list[dict]) -> list[dict]` — pairs buys with sells
  - `trader.evaluate.evaluate(rows: list[dict]) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# trader/tests/test_evaluate.py
from trader.evaluate import BACKTEST, TRADES_NEEDED, evaluate, round_trips


def buy(symbol, date, price, qty=100, decision=None):
    return {"symbol": symbol, "side": "buy", "date": date, "qty": qty,
            "filled_avg_price": str(price), "decision_close": decision if decision is not None else price,
            "rules_version": "abc123def456"}


def sell(symbol, date, price, qty=100, reason="rsi", bars=3, decision=None):
    return {"symbol": symbol, "side": "sell", "date": date, "qty": qty,
            "filled_avg_price": str(price), "decision_close": decision if decision is not None else price,
            "exit_reason": reason, "bars_held": bars, "rules_version": "abc123def456"}


def test_evaluate_with_no_closed_trades():
    """Day one. A renderable record, no division by zero, and explicitly no verdict."""
    out = evaluate([])
    assert out["trades_closed"] == 0
    assert out["trades_needed"] == TRADES_NEEDED
    assert out["bps_per_trade"] is None
    assert out["win_rate"] is None
    assert out["verdict"] is None


def test_an_open_trade_alone_is_not_a_round_trip():
    out = evaluate([buy("AMZN", "2026-10-12", 262.43)])
    assert out["trades_closed"] == 0
    assert out["verdict"] is None


def test_a_round_trip_is_paired_and_measured():
    rows = [buy("AMZN", "2026-10-12", 100.0), sell("AMZN", "2026-10-15", 103.0, bars=3)]
    trips = round_trips(rows)
    assert len(trips) == 1
    assert trips[0]["pl_pct"] == 3.0
    assert trips[0]["bars_held"] == 3
    assert trips[0]["exit_reason"] == "rsi"
    out = evaluate(rows)
    assert out["trades_closed"] == 1
    assert out["bps_per_trade"] == 300.0
    assert out["win_rate"] == 100.0
    assert out["mean_bars_held"] == 3.0


def test_slippage_is_measured_from_decision_close_against_the_fill():
    """The one approximation in the design: the rule decides on a 15:25 partial bar and
    fills in the closing auction. 100.50 against a 100.00 decision is 50 bps paid."""
    rows = [buy("AMZN", "2026-10-12", 100.5, decision=100.0),
            sell("AMZN", "2026-10-15", 103.0, decision=103.0)]
    out = evaluate(rows)
    assert out["slippage_bps"] == 50.0


def test_two_symbols_are_paired_independently():
    rows = [buy("AMZN", "2026-10-12", 100.0), buy("AAPL", "2026-10-12", 200.0),
            sell("AAPL", "2026-10-14", 206.0, bars=2), sell("AMZN", "2026-10-16", 99.0, bars=4)]
    out = evaluate(rows)
    assert out["trades_closed"] == 2
    assert out["win_rate"] == 50.0
    assert out["per_symbol"]["AAPL"]["bps_per_trade"] == 300.0
    assert out["per_symbol"]["AMZN"]["bps_per_trade"] == -100.0


def test_a_rules_version_change_splits_the_record():
    """Two rule generations must never blend into one number."""
    rows = [buy("AMZN", "2026-10-12", 100.0), sell("AMZN", "2026-10-15", 103.0)]
    rows += [dict(buy("AMZN", "2026-11-12", 100.0), rules_version="zzz999"),
             dict(sell("AMZN", "2026-11-15", 95.0), rules_version="zzz999")]
    out = evaluate(rows)
    assert set(out["per_rules_version"]) == {"abc123def456", "zzz999"}
    assert out["per_rules_version"]["zzz999"]["bps_per_trade"] == -500.0


def test_no_verdict_until_the_bar_is_met():
    rows = []
    for i in range(TRADES_NEEDED - 1):
        rows += [buy("AMZN", f"2026-01-{i % 28 + 1:02d}", 100.0),
                 sell("AMZN", f"2026-02-{i % 28 + 1:02d}", 101.0)]
    assert evaluate(rows)["verdict"] is None


def test_the_backtest_expectation_is_carried_for_both_symbols():
    for symbol in ("AMZN", "AAPL"):
        assert BACKTEST[symbol]["bps_per_trade"] > 0
        assert BACKTEST[symbol]["trades"] > 200
        assert "t_stat" in BACKTEST[symbol]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest trader/tests/test_evaluate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trader.evaluate'`

- [ ] **Step 3: Write the implementation**

```python
# trader/evaluate.py
"""The live record against the backtested expectation.

Two rules this repo already learned the hard way apply here (research/FINDINGS.md):
a pooled number can be one event in disguise, so this always reports a breakdown alongside
the total; and two rule generations must never blend, so everything is also split by
`rules_version`.

The verdict stays None until TRADES_NEEDED round trips exist. With ~13% exposure per name
the two symbols fire roughly 20 round trips a year, so that is about 18 months -- and
reporting a verdict sooner would be reading noise. See trader/ACCEPTANCE.md.
"""
from trader import params

# Measured 2026-10-10 with handoff/rsi2_edge_backtest.py: Yahoo adjusted daily closes,
# 2000-01-01 onward, 5 bps per round trip, randomization test over 2,000 matched
# random-entry simulations. Recorded here so the page can show live against expected.
BACKTEST = {
    "AMZN": {"trades": 232, "bps_per_trade": 150.1, "win_rate": 75.9, "t_stat": 5.53,
             "p_vs_random": 0.002, "max_dd_pct": -27.7, "mean_bars_held": 3.68,
             "positive_years": "19/24", "worst_trade_pct": -16.9},
    "AAPL": {"trades": 245, "bps_per_trade": 117.5, "win_rate": 75.1, "t_stat": 5.10,
             "p_vs_random": 0.010, "max_dd_pct": -32.4, "mean_bars_held": 4.16,
             "positive_years": "23/26", "worst_trade_pct": -18.6},
}

TRADES_NEEDED = 30


def _price(row) -> float:
    """The fill if there is one, else the price the decision was made on."""
    filled = row.get("filled_avg_price")
    return float(filled) if filled not in (None, "", "None") else float(row["decision_close"])


def round_trips(rows: "list[dict]") -> "list[dict]":
    """Pair each buy with the next sell in the same symbol. An unpaired buy is still open."""
    open_buys: "dict[str, dict]" = {}
    trips = []
    for row in sorted(rows, key=lambda r: (r.get("date", ""), r.get("symbol", ""))):
        symbol, side = row["symbol"], row["side"]
        if side == "buy":
            open_buys[symbol] = row
        elif side == "sell" and symbol in open_buys:
            entry = open_buys.pop(symbol)
            entry_px, exit_px = _price(entry), _price(row)
            trips.append({
                "symbol": symbol,
                "entry_date": entry.get("date"), "entry_price": entry_px,
                "exit_date": row.get("date"), "exit_price": exit_px,
                "qty": entry.get("qty"),
                "bars_held": row.get("bars_held"),
                "exit_reason": row.get("exit_reason"),
                "pl": (exit_px - entry_px) * float(entry.get("qty") or 0),
                "pl_pct": round((exit_px / entry_px - 1.0) * 100.0, 4) if entry_px else None,
                "slippage_bps": round((entry_px / float(entry["decision_close"]) - 1.0) * 1e4, 2)
                if entry.get("decision_close") else None,
                "rules_version": row.get("rules_version"),
            })
    return trips


def _stats(trips: "list[dict]") -> dict:
    if not trips:
        return {"trades_closed": 0, "bps_per_trade": None, "win_rate": None,
                "mean_bars_held": None, "slippage_bps": None}
    n = len(trips)
    pls = [t["pl_pct"] for t in trips if t["pl_pct"] is not None]
    bars = [t["bars_held"] for t in trips if t["bars_held"] is not None]
    slip = [t["slippage_bps"] for t in trips if t["slippage_bps"] is not None]
    return {
        "trades_closed": n,
        "bps_per_trade": round(sum(pls) / len(pls) * 100.0, 2) if pls else None,
        "win_rate": round(sum(1 for p in pls if p > 0) / len(pls) * 100.0, 1) if pls else None,
        "mean_bars_held": round(sum(bars) / len(bars), 2) if bars else None,
        "slippage_bps": round(sum(slip) / len(slip), 2) if slip else None,
    }


def _group(trips, key) -> dict:
    out: "dict[str, list]" = {}
    for t in trips:
        out.setdefault(t.get(key) or "unknown", []).append(t)
    return {k: _stats(v) for k, v in out.items()}


def evaluate(rows: "list[dict]") -> dict:
    trips = round_trips(rows)
    out = _stats(trips) | {
        "trades_needed": TRADES_NEEDED,
        "per_symbol": _group(trips, "symbol"),
        "per_rules_version": _group(trips, "rules_version"),
        "per_year": _group([t | {"year": (t["exit_date"] or "")[:4]} for t in trips], "year"),
        "backtest": {s: BACKTEST[s] for s in params.SYMBOLS},
        "trips": trips,
        # No verdict before the bar in trader/ACCEPTANCE.md is met. The page renders the
        # absence rather than hiding the section.
        "verdict": None,
    }
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/test_evaluate.py -q`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add trader/evaluate.py trader/tests/test_evaluate.py
git commit -m "feat(trader): evaluate the live record against the backtest

Pairs fills into round trips and reports bps/trade, win rate, bars held and
decision-vs-fill slippage, always with a per-symbol, per-year and
per-rules_version breakdown beside the pooled number -- the two traps this repo
already hit. No verdict until 30 round trips exist.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 7: The published JSON

**Files:**
- Create: `trader/export.py`, `trader/tests/test_export.py`

**Interfaces:**
- Consumes: `trader.evaluate.evaluate`, `trader.params`, the two ledgers, `trader.state`.
- Produces:
  - `trader.export.build(*, account: dict, positions: dict, history: dict, trade_rows: list[dict], run_rows: list[dict], state: dict, decisions: dict, as_of: str) -> dict`
  - `trader.export.write(path, payload) -> None`
  - `trader.export.main(argv=None) -> int` — reads the ledgers and the live account, writes the file

The shape is the contract in the spec's §6. The web types in Task 9 mirror it exactly.

- [ ] **Step 1: Write the failing test**

```python
# trader/tests/test_export.py
import json

from trader import params
from trader.export import build, write

ACCOUNT = {"equity": "100000", "cash": "100000", "buying_power": "400000"}
HISTORY = {"timestamp": [1760054400, 1760140800], "equity": [100000.0, 100500.0],
           "base_value": 100000.0}
DECISIONS = {
    "AMZN": {"action": "wait", "reason": "not oversold", "rsi2": 64.2, "sma200": 230.1,
             "price": 262.43, "trend_gap_pct": 14.0, "bars_held": 0, "held": False},
    "AAPL": {"action": "hold", "reason": "4 of 10 bars", "rsi2": 31.0, "sma200": 300.0,
             "price": 336.64, "trend_gap_pct": 12.2, "bars_held": 4, "held": True},
}


def test_export_day_one_empty_ledger():
    """Nothing has traded yet. Every panel must still render."""
    out = build(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=[],
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    assert out["account"]["opening_balance"] == 100000.0
    assert out["account"]["total_pl"] == 0.0
    assert out["account"]["deployed_pct"] == 0.0
    assert out["positions"] == []
    assert out["trades"] == []
    assert out["evaluation"]["trades_closed"] == 0
    assert out["evaluation"]["verdict"] is None
    assert len(out["signal_state"]) == len(params.SYMBOLS)
    assert out["rules_version"]
    assert out["as_of"] == "close"


def test_total_and_realised_pl_are_split():
    trades = [
        {"symbol": "AMZN", "side": "buy", "date": "2026-10-12", "qty": 100,
         "filled_avg_price": "100.0", "decision_close": 100.0, "rules_version": "v1"},
        {"symbol": "AMZN", "side": "sell", "date": "2026-10-15", "qty": 100,
         "filled_avg_price": "103.0", "decision_close": 103.0, "exit_reason": "rsi",
         "bars_held": 3, "rules_version": "v1"},
    ]
    out = build(account={"equity": "100300", "cash": "100300", "buying_power": "401200"},
                positions={}, history=HISTORY, trade_rows=trades, run_rows=[],
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    assert out["account"]["realised_pl"] == 300.0
    assert out["account"]["total_pl"] == 300.0
    assert out["account"]["total_pl_pct"] == 0.3
    assert out["account"]["unrealised_pl"] == 0.0


def test_an_open_position_reports_bars_held_against_the_time_stop():
    positions = {"AAPL": {"symbol": "AAPL", "qty": "148", "current_price": "336.64",
                          "unrealized_pl": "592.0", "unrealized_plpc": "0.0121",
                          "avg_entry_price": "332.64"}}
    out = build(account=ACCOUNT, positions=positions, history=HISTORY, trade_rows=[],
                run_rows=[], state={"opening_balance": 100000.0,
                                    "positions": {"AAPL": {"entry_date": "2026-10-06",
                                                           "entry_price": 332.64}}},
                decisions=DECISIONS, as_of="close")
    pos = out["positions"][0]
    assert pos["symbol"] == "AAPL"
    assert pos["qty"] == 148
    assert pos["entry_date"] == "2026-10-06"
    assert pos["bars_held"] == 4
    assert pos["max_hold"] == params.MAX_HOLD
    assert pos["unrealised_pl"] == 592.0
    assert out["account"]["deployed_pct"] > 0


def test_equity_curve_marks_the_days_a_position_was_open():
    runs = [{"date": "2026-10-12", "decisions": {"AMZN": {"held": True}}},
            {"date": "2026-10-13", "decisions": {"AMZN": {"held": False}}}]
    out = build(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=runs,
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    curve = {p["date"]: p for p in out["equity_curve"]}
    assert curve["2026-10-10"]["in_position"] is False or "2026-10-12" in curve
    assert any(p["in_position"] for p in out["equity_curve"]) or out["equity_curve"]


def test_signal_state_carries_a_verdict_per_symbol():
    out = build(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=[],
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    by_symbol = {s["symbol"]: s for s in out["signal_state"]}
    assert by_symbol["AMZN"]["verdict"] == "Waiting"
    assert by_symbol["AAPL"]["verdict"] == "Held"


def test_runs_are_published_newest_first_and_capped_at_ten():
    runs = [{"date": f"2026-09-{d:02d}", "at": f"2026-09-{d:02d}T19:25:00+00:00",
             "mode": "live", "orders": 0, "late": False, "skip_reason": None,
             "decisions": {}} for d in range(1, 21)]
    out = build(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=runs,
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    assert len(out["runs"]) == 10
    assert out["runs"][0]["date"] == "2026-09-20"


def test_the_change_history_is_published_for_the_overlay():
    out = build(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=[],
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    assert out["history"][0]["version"] == out["version"]
    assert out["history"][0]["summary"].strip()
    assert "fingerprint" not in out["history"][0]  # as_dict() does not publish it


def test_write_is_valid_json_with_a_trailing_newline(tmp_path):
    out = build(account=ACCOUNT, positions={}, history=HISTORY, trade_rows=[], run_rows=[],
                state={"opening_balance": 100000.0}, decisions=DECISIONS, as_of="close")
    p = tmp_path / "paper-trading.json"
    write(p, out)
    text = p.read_text()
    assert text.endswith("\n")
    assert json.loads(text)["account"]["equity"] == 100000.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest trader/tests/test_export.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trader.export'`

- [ ] **Step 3: Write the implementation**

```python
# trader/export.py
"""Assemble paper-trading.json -- everything the page renders, in one file.

Written after the decision loop, so it reports the account as the broker sees it rather than
as the bot predicted. scan.yml copies the file into the site build; the trader never deploys.

    ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... python -m trader.export \\
        --data-dir history --out history/paper-trading.json
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scanner.strategies.base import current_version
from trader import evaluate as ev
from trader import params, state
from trader.alpaca import Alpaca, sessions_between

VERDICT_LABEL = {"buy": "Oversold", "sell": "Exiting", "hold": "Held",
                 "wait": "Waiting", "skip": "No data"}
RUNS_SHOWN = 10


def _read_jsonl(path) -> "list[dict]":
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _verdict(decision: dict) -> str:
    if decision.get("action") == "wait" and decision.get("reason") == "trend gate blocked":
        return "Trend gate blocked"
    return VERDICT_LABEL.get(decision.get("action", ""), "Unknown")


def build(*, account: dict, positions: dict, history: dict, trade_rows: "list[dict]",
          run_rows: "list[dict]", state: dict, decisions: dict, as_of: str) -> dict:
    equity = float(account["equity"])
    cash = float(account["cash"])
    opening = float(state.get("opening_balance") or equity)
    evaluation = ev.evaluate(trade_rows)
    realised = round(sum(t["pl"] for t in evaluation["trips"]), 2)

    held = []
    for symbol, p in positions.items():
        entry = (state.get("positions") or {}).get(symbol, {})
        qty = abs(int(float(p["qty"])))
        held.append({
            "symbol": symbol,
            "entry_date": entry.get("entry_date"),
            "entry_price": float(p.get("avg_entry_price") or entry.get("entry_price") or 0.0),
            "qty": qty,
            "price": float(p.get("current_price") or 0.0),
            "unrealised_pl": round(float(p.get("unrealized_pl") or 0.0), 2),
            "unrealised_pl_pct": round(float(p.get("unrealized_plpc") or 0.0) * 100.0, 2),
            "bars_held": (decisions.get(symbol) or {}).get("bars_held"),
            "max_hold": params.MAX_HOLD,
        })
    held.sort(key=lambda p: p["symbol"])
    unrealised = round(sum(p["unrealised_pl"] for p in held), 2)
    deployed = round((equity - cash) / equity * 100.0, 1) if equity else 0.0

    in_position_dates = {r.get("date") for r in run_rows
                         if any(d.get("held") for d in (r.get("decisions") or {}).values())}
    curve = []
    for ts, value in zip(history.get("timestamp") or [], history.get("equity") or []):
        date = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
        curve.append({"date": date, "equity": round(float(value), 2),
                      "in_position": date in in_position_dates})

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "rules_version": params.rules_version(),
        "version": current_version(params.HISTORY),
        # Published so the page's clock-icon overlay can show the same change history the
        # strategy tabs show. Newest first, as params.py declares it.
        "history": [r.as_dict() for r in params.HISTORY],
        "symbols": params.SYMBOLS,
        "account": {
            "opening_balance": round(opening, 2),
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "deployed_pct": deployed,
            "total_pl": round(equity - opening, 2),
            "total_pl_pct": round((equity / opening - 1.0) * 100.0, 3) if opening else 0.0,
            "realised_pl": realised,
            "unrealised_pl": unrealised,
        },
        "equity_curve": curve,
        "positions": held,
        "signal_state": [
            {"symbol": s,
             "rsi2": (decisions.get(s) or {}).get("rsi2"),
             "sma200": (decisions.get(s) or {}).get("sma200"),
             "price": (decisions.get(s) or {}).get("price"),
             "trend_gap_pct": (decisions.get(s) or {}).get("trend_gap_pct"),
             "buy_below": params.BUY_BELOW,
             "sell_above": params.SELL_ABOVE,
             "verdict": _verdict(decisions.get(s) or {}),
             "reason": (decisions.get(s) or {}).get("reason")}
            for s in params.SYMBOLS
        ],
        "trades": sorted(evaluation["trips"], key=lambda t: (t["exit_date"] or ""), reverse=True),
        "evaluation": {k: v for k, v in evaluation.items() if k != "trips"},
        "runs": sorted(run_rows, key=lambda r: r.get("at") or r.get("date") or "",
                       reverse=True)[:RUNS_SHOWN],
    }


def write(path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="history")
    ap.add_argument("--out", default="history/paper-trading.json")
    ap.add_argument("--as-of", default="close", choices=("close", "intraday"))
    args = ap.parse_args(argv)

    api = Alpaca(os.environ["ALPACA_KEY_ID"], os.environ["ALPACA_SECRET_KEY"])
    data_dir = Path(args.data_dir)
    run_rows = _read_jsonl(data_dir / "paper_runs.jsonl")
    payload = build(
        account=api.account(),
        positions=api.positions(),
        history=api.portfolio_history("all"),
        trade_rows=_read_jsonl(data_dir / "paper_trades.jsonl"),
        run_rows=run_rows,
        state=state.load(data_dir / "paper_state.json"),
        decisions=(run_rows[-1].get("decisions") if run_rows else {}) or {},
        as_of=args.as_of,
    )
    write(args.out, payload)
    print(f"wrote {args.out}: {len(payload['trades'])} round trips, "
          f"{len(payload['positions'])} open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/ -q`
Expected: PASS, every trader test from Tasks 1-7.

- [ ] **Step 5: Commit**

```bash
git add trader/export.py trader/tests/test_export.py
git commit -m "feat(trader): publish paper-trading.json

One file holding the account, equity curve, open positions, per-symbol rule
state, paired round trips, the evaluation and the last ten runs. Built after
the decision loop, from the account as the broker reports it, and renderable on
day one with an empty ledger.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 8: The fingerprint, the history and the acceptance bar

This is the task that makes a future threshold change honest: the fingerprint is pinned, so
moving a threshold without recording what changed fails the build.

**Files:**
- Create: `trader/ACCEPTANCE.md`, `trader/tests/test_params.py`
- Modify: `trader/params.py` (fill in the `HISTORY` fingerprint)

**Interfaces:**
- Consumes: `trader.params.HISTORY`, `trader.params.rules_version`, `scanner.strategies.base.current_version`.
- Produces: nothing other tasks use.

- [ ] **Step 1: Write the failing test**

```python
# trader/tests/test_params.py
"""The published history cannot drift out of date, because what would make it stale is what
breaks this test. Same contract as scanner/tests/test_history.py."""
import re

from scanner.strategies.base import current_version
from trader import params


def test_history_is_newest_first():
    dates = [r.date for r in params.HISTORY]
    assert dates == sorted(dates, reverse=True)


def test_every_release_is_semver_and_iso_dated():
    for r in params.HISTORY:
        assert re.fullmatch(r"\d+\.\d+\.\d+", r.version), r.version
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.date), r.date
        assert r.summary.strip()


def test_the_newest_release_fingerprint_matches_the_live_params():
    """Changing a threshold without adding a history entry must fail here."""
    assert params.HISTORY[0].fingerprint == params.rules_version(), (
        "params changed without a new Release entry. Add one to trader/params.py:HISTORY "
        "with fingerprint=" + params.rules_version()
    )


def test_current_version_reads_the_top_entry():
    assert current_version(params.HISTORY) == params.HISTORY[0].version


def test_summaries_name_no_identifiers():
    """Plain English, at the altitude a reader of the site cares about."""
    for r in params.HISTORY:
        for banned in ("RSI_LEN", "SLICE_PCT", "def ", "params.py", "_"):
            assert banned not in r.summary, f"{r.version}: {banned}"


def test_fingerprint_is_stable_across_calls():
    assert params.rules_version() == params.rules_version()
    assert len(params.rules_version()) == 12
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest trader/tests/test_params.py -q`
Expected: FAIL on `test_the_newest_release_fingerprint_matches_the_live_params` — the
`HISTORY` entry from Task 1 has `fingerprint=""`.

- [ ] **Step 3: Read the fingerprint and fill it in**

Run: `.venv/bin/python -c "from trader import params; print(params.rules_version())"`

Paste the printed value into `trader/params.py`, replacing `fingerprint=""` on the `1.0.0`
entry. Do not type it from memory — copy what the command prints.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest trader/tests/test_params.py -q`
Expected: PASS, 6 tests.

- [ ] **Step 5: Write the acceptance bar**

```markdown
<!-- trader/ACCEPTANCE.md -->
# Acceptance — paper trading, RSI(2) on AMZN and AAPL

Written 2026-10-10, **before any live trade existed.** That is the point: a bar set after
the numbers arrive is not a bar.

## What was measured before shipping

`handoff/rsi2_edge_backtest.py`, Yahoo adjusted daily closes from 2000-01-01, 5 bps per
round trip, 2,000 matched random-entry simulations.

| | trades | bps/trade | win % | t | p vs random | max DD | positive years |
|---|---|---|---|---|---|---|---|
| AMZN | 232 | +150.1 | 75.9% | 5.53 | 0.002 | −27.7% | 19/24 |
| AAPL | 245 | +117.5 | 75.1% | 5.10 | 0.010 | −32.4% | 23/26 |

Leave-one-year-out: dropping AMZN's best year leaves +130.0 bps; dropping AAPL's leaves
+110.1. So the result is not one event — the trap `research/FINDINGS.md` describes.

**Known weakness, recorded now so it is not discovered as a surprise later:** both names ran
well below their lifetime average in the most recent years — AMZN +38.3 bps (2024) and +52.4
(2025), AAPL +60.8 (2025) and +35.6 (2026). Still positive, roughly a third the magnitude.
This may be decay or may be two quiet years. The live record is how we find out.

## How many trades a verdict needs

Exposure is ~12–15% of sessions per name, so the two together fire roughly **20 round trips
a year**. A verdict needs about **30 round trips — call it 18 months.** Until then
`evaluation.verdict` stays `null` and the page reports the record without a conclusion.

Reporting a verdict sooner would be reading noise, and this repo has been wrong that way
before.

## What would force a change

| Observation, over 30+ round trips | What changes |
|---|---|
| Realised bps/trade more than one standard error below +150 (AMZN) / +117 (AAPL) | Revisit the rule, starting from the 2024–26 decay above. Measure in `research/` first. |
| Decision-vs-fill slippage worse than 15 bps per round trip | Move the run later, or change order type. **Not** a reason to touch the rule. |
| Realised drawdown beyond −27.7% (AMZN) / −32.4% (AAPL) | Revisit sizing, not the thresholds. |
| Win rate holding but bps/trade collapsing | The left tail is widening. Revisit the no-stop decision — and measure it, since a stop cut returns in the original research. |

## What does not count as evidence

- A single bad trade. The worst backtested trades were −16.9% and −18.6%; both are inside
  expectations, not a signal.
- A flat equity curve. Capital idles ~87% of the time by design.
- Fewer than 30 round trips, however tempting the number looks.

## The procedure for a change

1. Measure the variant in `research/`, on the non-overlapping sample, with the per-year table.
2. Record the number — including if it kills the idea, so it is not re-proposed.
3. Add a `Release` entry to `trader/params.py:HISTORY` with the new fingerprint.
4. The ledger then splits at that date on `rules_version`, and `trader/evaluate.py` reports
   the two generations separately rather than blending them.
```

- [ ] **Step 6: Commit**

```bash
git add trader/params.py trader/ACCEPTANCE.md trader/tests/test_params.py
git commit -m "feat(trader): pin the rules fingerprint and write the acceptance bar

The newest history entry carries the fingerprint of the thresholds it shipped
with and a test asserts they still match, so moving a threshold without saying
what changed fails the build. ACCEPTANCE.md sets the bar at 30 round trips --
written now, before any live trade exists, including the 2024-26 decay in both
names and what would and would not count as evidence against the rule.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 9: Web data layer and the route

**Files:**
- Modify: `web/src/types.ts`, `web/src/api.ts`, `web/src/App.tsx`, `web/src/components/TopBar.tsx`, `web/src/test-fixtures.ts`
- Create: `web/src/pages/PaperPage.tsx`, `web/src/pages/PaperPage.test.tsx`

**Interfaces:**
- Consumes: the JSON contract from Task 7; `useAsync` from `web/src/hooks.ts`; `Loading` / `ErrorState` from `web/src/components/Feedback.tsx`.
- Produces:
  - `types.ts`: `PaperTradingFile`, `PaperAccount`, `PaperPosition`, `PaperSignalState`, `PaperRoundTrip`, `PaperEvaluation`, `PaperRun`, `EquityPoint`
  - `api.ts`: `getPaperTrading(): Promise<PaperTradingFile>`
  - `test-fixtures.ts`: `paperTradingFile: PaperTradingFile`
  - `PaperPage` — the default route component at `/paper`

- [ ] **Step 1: Add the types**

```ts
// web/src/types.ts -- append
/** The paper-trading account's state, as trader/export.py publishes it. */
export interface PaperAccount {
  opening_balance: number;
  equity: number;
  cash: number;
  deployed_pct: number;
  total_pl: number;
  total_pl_pct: number;
  realised_pl: number;
  unrealised_pl: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
  in_position: boolean;
}

export interface PaperPosition {
  symbol: string;
  entry_date: string | null;
  entry_price: number;
  qty: number;
  price: number;
  unrealised_pl: number;
  unrealised_pl_pct: number;
  bars_held: number | null;
  max_hold: number;
}

export interface PaperSignalState {
  symbol: string;
  rsi2: number | null;
  sma200: number | null;
  price: number | null;
  trend_gap_pct: number | null;
  buy_below: number;
  sell_above: number;
  /** "Oversold" | "Waiting" | "Held" | "Trend gate blocked" | "Exiting" | "No data" */
  verdict: string;
  reason: string | null;
}

export interface PaperRoundTrip {
  symbol: string;
  entry_date: string | null;
  entry_price: number;
  exit_date: string | null;
  exit_price: number;
  qty: number | null;
  bars_held: number | null;
  exit_reason: string | null;
  pl: number;
  pl_pct: number | null;
  slippage_bps: number | null;
  rules_version: string | null;
}

export interface PaperStats {
  trades_closed: number;
  bps_per_trade: number | null;
  win_rate: number | null;
  mean_bars_held: number | null;
  slippage_bps: number | null;
}

export interface PaperEvaluation extends PaperStats {
  trades_needed: number;
  per_symbol: Record<string, PaperStats>;
  per_rules_version: Record<string, PaperStats>;
  per_year: Record<string, PaperStats>;
  backtest: Record<string, { trades: number; bps_per_trade: number; win_rate: number; t_stat: number; p_vs_random: number; max_dd_pct: number; mean_bars_held: number; positive_years: string; worst_trade_pct: number }>;
  /** Stays null until trades_closed >= trades_needed. See trader/ACCEPTANCE.md. */
  verdict: string | null;
}

export interface PaperRun {
  at: string;
  date: string;
  mode: string;
  orders: number;
  late: boolean;
  skip_reason: string | null;
  minutes_to_close?: number;
  errors?: { symbol?: string; stage?: string; error?: string }[];
}

export interface PaperTradingFile {
  updated_at: string;
  /** Semver of the trading rules that produced this file. */
  version: string;
  /** Newest first, shown in the clock-icon overlay like the strategy tabs. */
  history: Release[];
  /** What the account figures are marked at. */
  as_of: "close" | "intraday";
  rules_version: string;
  symbols: string[];
  account: PaperAccount;
  equity_curve: EquityPoint[];
  positions: PaperPosition[];
  signal_state: PaperSignalState[];
  trades: PaperRoundTrip[];
  evaluation: PaperEvaluation;
  runs: PaperRun[];
}
```

- [ ] **Step 2: Add the loader and the fixture**

```ts
// web/src/api.ts -- append next to the other getters
export const getPaperTrading = () => getJson<PaperTradingFile>("paper-trading.json");
```

Add `PaperTradingFile` to the existing `import type { ... } from "./types";` line.

```ts
// web/src/test-fixtures.ts -- append
export const paperTradingFile: PaperTradingFile = {
  updated_at: "2026-10-12T20:10:00+00:00",
  as_of: "close",
  rules_version: "abc123def456",
  symbols: ["AMZN", "AAPL"],
  account: {
    opening_balance: 100000, equity: 100592, cash: 50780, deployed_pct: 49.5,
    total_pl: 592, total_pl_pct: 0.592, realised_pl: 0, unrealised_pl: 592,
  },
  equity_curve: [
    { date: "2026-10-09", equity: 100000, in_position: false },
    { date: "2026-10-12", equity: 100592, in_position: true },
  ],
  positions: [{
    symbol: "AAPL", entry_date: "2026-10-06", entry_price: 332.64, qty: 148,
    price: 336.64, unrealised_pl: 592, unrealised_pl_pct: 1.21, bars_held: 4, max_hold: 10,
  }],
  signal_state: [
    { symbol: "AMZN", rsi2: 64.2, sma200: 230.1, price: 262.43, trend_gap_pct: 14,
      buy_below: 10, sell_above: 65, verdict: "Waiting", reason: "not oversold" },
    { symbol: "AAPL", rsi2: 31, sma200: 300, price: 336.64, trend_gap_pct: 12.2,
      buy_below: 10, sell_above: 65, verdict: "Held", reason: "4 of 10 bars" },
  ],
  trades: [],
  evaluation: {
    trades_closed: 0, trades_needed: 30, bps_per_trade: null, win_rate: null,
    mean_bars_held: null, slippage_bps: null, per_symbol: {}, per_rules_version: {},
    per_year: {},
    backtest: {
      AMZN: { trades: 232, bps_per_trade: 150.1, win_rate: 75.9, t_stat: 5.53, p_vs_random: 0.002, max_dd_pct: -27.7, mean_bars_held: 3.68, positive_years: "19/24", worst_trade_pct: -16.9 },
      AAPL: { trades: 245, bps_per_trade: 117.5, win_rate: 75.1, t_stat: 5.1, p_vs_random: 0.01, max_dd_pct: -32.4, mean_bars_held: 4.16, positive_years: "23/26", worst_trade_pct: -18.6 },
    },
    verdict: null,
  },
  runs: [{ at: "2026-10-12T19:25:08+00:00", date: "2026-10-12", mode: "live", orders: 1,
           late: false, skip_reason: null, minutes_to_close: 35 }],
};
```

- [ ] **Step 3: Write the failing page test**

```tsx
// web/src/pages/PaperPage.test.tsx
import { render, screen } from "@testing-library/react";
import { HashRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import { paperTradingFile } from "../test-fixtures";
import { PaperPage } from "./PaperPage";

function show(file = paperTradingFile) {
  vi.spyOn(api, "getPaperTrading").mockResolvedValue(file);
  return render(<HashRouter><PaperPage /></HashRouter>);
}

beforeEach(() => {
  api.clearCache();
  vi.restoreAllMocks();
});

test("shows the opening balance and the total P/L", async () => {
  show();
  expect(await screen.findByText("$100,000")).toBeInTheDocument();
  expect(screen.getByText(/\+\$592/)).toBeInTheDocument();
});

test("says the money is not real", async () => {
  show();
  expect(await screen.findByText(/paper/i)).toBeInTheDocument();
});

test("renders a day-one account with no trades without crashing", async () => {
  const day_one = {
    ...paperTradingFile,
    account: { ...paperTradingFile.account, equity: 100000, total_pl: 0, total_pl_pct: 0,
               unrealised_pl: 0, deployed_pct: 0 },
    positions: [], equity_curve: [], trades: [],
  };
  show(day_one);
  expect(await screen.findByText(/flat/i)).toBeInTheDocument();
});

test("offers no verdict before the acceptance bar is met", async () => {
  show();
  expect(await screen.findByText(/0 of 30/)).toBeInTheDocument();
  expect(screen.queryByText(/verdict:/i)).not.toBeInTheDocument();
});

test("warns when the last run landed past the cutoff", async () => {
  const late = {
    ...paperTradingFile,
    runs: [{ ...paperTradingFile.runs[0], late: true,
             skip_reason: "inside the 10-minute cutoff; cls would be rejected" }],
  };
  show(late);
  expect(await screen.findByRole("status")).toHaveTextContent(/cutoff/i);
});

test("shows an error state with a retry when the file cannot be loaded", async () => {
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(new Error("HTTP 404"));
  render(<HashRouter><PaperPage /></HashRouter>);
  expect(await screen.findByText(/HTTP 404/)).toBeInTheDocument();
});
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd web && npm test -- --run src/pages/PaperPage.test.tsx`
Expected: FAIL — cannot resolve `./PaperPage`.

- [ ] **Step 5: Write the page shell**

Write `web/src/pages/PaperPage.tsx` loading the file with `useAsync(getPaperTrading, [])`,
rendering `<Loading what="paper trading" />` and `<ErrorState .../>` exactly as
`StrategyPage` does, then the panels from Task 10. Until Task 10 lands, render the balance
figures inline so this task's tests pass on their own: the header strip with the `PAPER`
pill and the as-of line, the five stat cells, the flat-account empty state, the
`0 of 30` evaluation line, and a `role="status"` banner when `runs[0].late` is true.

- [ ] **Step 6: Wire the change-history overlay**

The header strip's clock icon opens the existing `HistoryModal`, exactly as `StrategyPage`
does — same component, same props, no new modal:

```tsx
const [showHistory, setShowHistory] = useState(false);
// ...
{showHistory && (
  <HistoryModal
    strategyName="Paper Trading"
    history={data.history}
    onClose={() => setShowHistory(false)}
  />
)}
```

Add to `PaperPage.test.tsx`:

```tsx
test("the clock icon opens the change history", async () => {
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /change history/i }));
  expect(screen.getByRole("dialog")).toHaveTextContent(/first version/i);
});
```

- [ ] **Step 7: Wire the route and the nav link**

```tsx
// web/src/App.tsx -- inside <Routes>, after the strategy route
<Route path="/paper" element={<PaperPage />} />
```

```tsx
// web/src/components/TopBar.tsx -- after the strategies.map(...) block
{/* Not driven by strategies.json: this is a portfolio view, not a signal list. */}
<NavLink to={{ pathname: "/paper", search }}>Paper Trading</NavLink>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd web && npm test -- --run`
Expected: PASS, including the existing suite.

- [ ] **Step 9: Commit**

```bash
git add web/src/types.ts web/src/api.ts web/src/App.tsx web/src/components/TopBar.tsx web/src/test-fixtures.ts web/src/pages/PaperPage.tsx web/src/pages/PaperPage.test.tsx
git commit -m "feat(web): the paper-trading route and its data contract

A third tab at /paper, hand-added to the nav because it is a portfolio view
rather than a signal list. Renders on day one with an empty ledger, offers no
verdict before 30 round trips, and says when a run landed past the cutoff.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 10: The panels

**REQUIRED SUB-SKILL:** invoke `frontend-design` before writing these components, and
`dataviz` before writing any part of the equity curve. The page must read as the same
product as the two strategy tabs, not an admin panel.

**Files:**
- Create: `web/src/components/PaperBalance.tsx`, `PaperEquityCurve.tsx`, `PaperPositions.tsx`, `PaperSignalRows.tsx`, `PaperTrades.tsx`, `PaperRuns.tsx`
- Create: `web/src/components/PaperPanels.test.tsx`
- Modify: `web/src/pages/PaperPage.tsx` (compose them), `web/src/theme.css`

**Interfaces:**
- Consumes: the types from Task 9.
- Produces, each a named export taking exactly one prop object:
  - `PaperBalance({ account }: { account: PaperAccount })`
  - `PaperEquityCurve({ curve, opening }: { curve: EquityPoint[]; opening: number })`
  - `PaperPositions({ positions }: { positions: PaperPosition[] })`
  - `PaperSignalRows({ state }: { state: PaperSignalState[] })` — named *Rows* because `PaperSignalState` is already the type
  - `PaperTrades({ trades, evaluation }: { trades: PaperRoundTrip[]; evaluation: PaperEvaluation })`
  - `PaperRuns({ runs }: { runs: PaperRun[] })`

**Design constraints, from the spec's §7:**

- Reuse the existing vocabulary: `.stats`/`.stat` for the balance row, `.bigcard` for position
  cards, `.pill` for verdicts, `.num` for every figure, `var(--buy)`/`var(--sell)` for signed
  values. Add new classes only where none fits, prefixed `paper-`.
- The equity curve is inline SVG, no charting dependency — `Sparkline.tsx` is the precedent.
  Shade the `in_position` spans so idleness reads as deliberate.
- Every number is tabular (`.num`), signed where it is a change, and `$` formatted via
  `Intl.NumberFormat`.
- The bars-held meter is a labelled progress element, not a bare bar: screen readers must get
  "4 of 10 bars".
- No panel may render `NaN`, `null`, `undefined` or `--`. A missing value renders as an em
  dash with a `title` explaining why. The literal `--` once shipped in the history overlay and
  every test accepted it.

- [ ] **Step 1: Write the failing tests**

```tsx
// web/src/components/PaperPanels.test.tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { paperTradingFile } from "../test-fixtures";
import { PaperBalance } from "./PaperBalance";
import { PaperEquityCurve } from "./PaperEquityCurve";
import { PaperPositions } from "./PaperPositions";
import { PaperRuns } from "./PaperRuns";
import { PaperSignalRows } from "./PaperSignalRows";
import { PaperTrades } from "./PaperTrades";

const f = paperTradingFile;

test("balance shows all five figures with the P/L signed", () => {
  render(<PaperBalance account={f.account} />);
  expect(screen.getByText("Opening balance")).toBeInTheDocument();
  expect(screen.getByText("$100,000")).toBeInTheDocument();
  expect(screen.getByText(/\+\$592/)).toBeInTheDocument();
  expect(screen.getByText(/49\.5%/)).toBeInTheDocument();
});

test("a negative total P/L is coloured as a loss and carries its sign", () => {
  render(<PaperBalance account={{ ...f.account, total_pl: -1234.5, total_pl_pct: -1.23 }} />);
  const pl = screen.getByText(/-\$1,234/);
  expect(pl.className).toMatch(/sell/);
});

test("equity curve draws a path and marks the in-position days", () => {
  const { container } = render(<PaperEquityCurve curve={f.equity_curve} opening={100000} />);
  expect(container.querySelector("path")).toBeTruthy();
  expect(container.querySelectorAll("rect").length).toBeGreaterThan(0);
});

test("an empty equity curve renders an explanation, not an empty box", () => {
  render(<PaperEquityCurve curve={[]} opening={100000} />);
  expect(screen.getByText(/no history yet/i)).toBeInTheDocument();
});

test("a position shows its bars-held meter accessibly", () => {
  render(<PaperPositions positions={f.positions} />);
  expect(screen.getByText("AAPL")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAccessibleName(/4 of 10 bars/i);
});

test("no open positions explains the idleness instead of showing nothing", () => {
  render(<PaperPositions positions={[]} />);
  expect(screen.getByText(/flat/i)).toBeInTheDocument();
  expect(screen.getByText(/13%/)).toBeInTheDocument();
});

test("signal state shows the threshold each symbol is measured against", () => {
  render(<PaperSignalRows state={f.signal_state} />);
  expect(screen.getByText("Waiting")).toBeInTheDocument();
  expect(screen.getByText("Held")).toBeInTheDocument();
  expect(screen.getAllByText(/10/).length).toBeGreaterThan(0);
});

test("a blocked trend gate is named as such", () => {
  render(<PaperSignalRows state={[{ ...f.signal_state[0], verdict: "Trend gate blocked",
                                     trend_gap_pct: -3.2 }]} />);
  expect(screen.getByText("Trend gate blocked")).toBeInTheDocument();
});

test("no trades yet says how many are needed and gives no verdict", () => {
  render(<PaperTrades trades={[]} evaluation={f.evaluation} />);
  expect(screen.getByText(/0 of 30/)).toBeInTheDocument();
  expect(screen.queryByText(/verdict/i)).not.toBeInTheDocument();
});

test("a closed round trip shows its exit reason and P/L", () => {
  const trade = { symbol: "AMZN", entry_date: "2026-10-12", entry_price: 100,
                  exit_date: "2026-10-15", exit_price: 103, qty: 100, bars_held: 3,
                  exit_reason: "rsi", pl: 300, pl_pct: 3, slippage_bps: 0,
                  rules_version: "abc123def456" };
  render(<PaperTrades trades={[trade]} evaluation={{ ...f.evaluation, trades_closed: 1,
                                                     bps_per_trade: 300, win_rate: 100,
                                                     mean_bars_held: 3 }} />);
  expect(screen.getByText("RSI exit")).toBeInTheDocument();
  expect(screen.getByText(/\+3\.00%/)).toBeInTheDocument();
  expect(screen.getByText(/150\.1/)).toBeInTheDocument(); // the backtest beside it
});

test("a time-stopped exit is labelled in plain English", () => {
  const trade = { symbol: "AAPL", entry_date: "2026-10-01", entry_price: 100,
                  exit_date: "2026-10-15", exit_price: 99, qty: 10, bars_held: 10,
                  exit_reason: "time_stop", pl: -10, pl_pct: -1, slippage_bps: null,
                  rules_version: "abc123def456" };
  render(<PaperTrades trades={[trade]} evaluation={f.evaluation} />);
  expect(screen.getByText("Time stop")).toBeInTheDocument();
});

test("a missing value renders an em dash with an explanation, never a literal double hyphen", () => {
  const trade = { symbol: "AAPL", entry_date: null, entry_price: 100, exit_date: null,
                  exit_price: 0, qty: null, bars_held: null, exit_reason: null, pl: 0,
                  pl_pct: null, slippage_bps: null, rules_version: null };
  const { container } = render(<PaperTrades trades={[trade]} evaluation={f.evaluation} />);
  expect(container.textContent).not.toContain("--");
  expect(container.textContent).toContain("—");
});

test("the run log lists the last runs and what each decided", () => {
  render(<PaperRuns runs={f.runs} />);
  expect(screen.getByText(/1 order/)).toBeInTheDocument();
});

test("a missed or late run is announced", () => {
  render(<PaperRuns runs={[{ ...f.runs[0], late: true, skip_reason: "inside the cutoff" }]} />);
  expect(screen.getByRole("status")).toHaveTextContent(/cutoff/i);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd web && npm test -- --run src/components/PaperPanels.test.tsx`
Expected: FAIL — the component modules do not resolve.

- [ ] **Step 3: Write the six components**

Each is one file, one export, no data fetching — `PaperPage` owns loading. The tests above
pin the behaviour; `frontend-design` decides the visual treatment within the constraints.

Exit-reason labels, exactly: `rsi` → `RSI exit`, `time_stop` → `Time stop`, anything else →
the raw value. A `null` reason renders the em dash.

`PaperBalance` in full, as the pattern the other five follow — shared formatters, the em-dash
rule, and signed colouring:

```tsx
// web/src/components/PaperBalance.tsx
import type { PaperAccount } from "../types";

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD",
                                               maximumFractionDigits: 0 });
const signedMoney = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD",
                                                     maximumFractionDigits: 0,
                                                     signDisplay: "always" });

/** Every missing number renders as an em dash with a reason. A literal "--" once shipped. */
export function Figure({ value, format, why }: { value: number | null; format: (n: number) => string; why: string }) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className="muted" title={why}>&mdash;</span>;
  }
  return <>{format(value)}</>;
}

export function PaperBalance({ account }: { account: PaperAccount }) {
  const tone = account.total_pl === 0 ? "" : account.total_pl > 0 ? " buy-text" : " sell-text";
  return (
    <section className="stats" aria-label="Account balance">
      <div className="stat">
        <div className="tag">Opening balance</div>
        <div className="n num">{money.format(account.opening_balance)}</div>
      </div>
      <div className="stat">
        <div className="tag">Current equity</div>
        <div className="n num">{money.format(account.equity)}</div>
      </div>
      <div className="stat">
        <div className="tag">Total P/L</div>
        <div className={`n num${tone}`}>{signedMoney.format(account.total_pl)}</div>
        <div className={`tag num${tone}`}>
          {account.total_pl_pct >= 0 ? "+" : ""}{account.total_pl_pct.toFixed(2)}%
        </div>
      </div>
      <div className="stat">
        <div className="tag">Realised</div>
        <div className="n num">{signedMoney.format(account.realised_pl)}</div>
        <div className="tag">Unrealised {signedMoney.format(account.unrealised_pl)}</div>
      </div>
      <div className="stat">
        <div className="tag">Capital deployed</div>
        <div className="n num">{account.deployed_pct.toFixed(1)}%</div>
        <div className="tag">idle by design</div>
      </div>
    </section>
  );
}
```

Export `Figure` from here and use it in the other five for every nullable number
(`bars_held`, `pl_pct`, `slippage_bps`, `rsi2`, `trend_gap_pct`, each `evaluation` statistic),
which is what satisfies the em-dash test.

- [ ] **Step 4: Compose them in `PaperPage`**

Replace the inline balance markup from Task 9 with, in this order: header strip,
`PaperBalance`, `PaperEquityCurve`, `PaperPositions`, `PaperSignalRows`, `PaperTrades`,
`PaperRuns`.

- [ ] **Step 5: Add the styles**

Add the `paper-` classes to `web/src/theme.css`, after the existing card rules. Every colour
is an existing token; define no new hex value. Verify the dark-mode block covers anything new.

- [ ] **Step 6: Run the whole web suite**

Run: `cd web && npm test -- --run`
Expected: PASS, all suites.

- [ ] **Step 7: Look at it**

Per `CLAUDE.md`, Playwright cannot drive Arc on this Mac; serve the build and drive
Chrome-for-Testing directly.

```bash
cd web && npm run build && npx vite preview --port 4317 --strictPort &
```

Then screenshot `http://localhost:4317/#/paper` at 1280×900 and at 390×844 with a node
script whose `executablePath` is
`~/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`.

Check, with eyes, not tests: no literal `--` anywhere; the stat row wraps to two columns at
390px without horizontal scroll; the equity curve's in-position shading is visible; signed
values are coloured the right way round; the empty states read as sentences.

- [ ] **Step 8: Commit**

```bash
git add web/src/components/Paper*.tsx web/src/components/PaperPanels.test.tsx web/src/pages/PaperPage.tsx web/src/theme.css
git commit -m "feat(web): the paper-trading panels

Balance row, equity curve with in-position shading, open positions with an
accessible bars-held meter, per-symbol rule state, the trade table beside the
backtested expectation, and the run log. Every empty state reads as a sentence,
and a missing value is an em dash with a reason -- never a literal double hyphen.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 11: The workflows

**Files:**
- Create: `.github/workflows/trade.yml`
- Modify: `.github/workflows/scan.yml`

**Interfaces:**
- Consumes: `python -m trader.run`, `python -m trader.export`.
- Produces: `paper-trading.json`, `paper_trades.jsonl`, `paper_runs.jsonl`, `paper_state.json`
  on the `data` branch.

- [ ] **Step 1: Write the trading workflow**

```yaml
# .github/workflows/trade.yml
name: Paper trade

on:
  schedule:
    # 15:25 America/New_York, in both offsets. Cron cannot know about DST or holidays, so
    # both fire year-round and `/v2/clock` decides: a run on a closed market exits quietly.
    # 15:25 rather than 15:40 because Actions cron drifts, sometimes by 20 minutes, and
    # Alpaca rejects market-on-close orders after 15:50 ET.
    - cron: "25 19 * * 1-5" # 15:25 EDT
    - cron: "25 20 * * 1-5" # 15:25 EST
  # Deliberately NO `push` trigger. scan.yml re-runs on every push because an algorithm
  # change must regenerate the published lists; here the same trigger would mean that
  # merging code submits orders. It must not.
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Decide only, submit nothing"
        type: boolean
        default: true

permissions:
  contents: write # the ledgers and state live on the `data` branch
  issues: write # a failed run opens or comments on one tracking issue

concurrency:
  group: paper-trade # never let two runs race on the state file
  cancel-in-progress: false

jobs:
  trade:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: Check out the ledgers (data branch)
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          REMOTE="https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
          if git ls-remote --exit-code --heads "$REMOTE" data >/dev/null 2>&1; then
            git clone --quiet --branch data --single-branch --depth 1 "$REMOTE" history
          else
            git init --quiet -b data history
            git -C history remote add origin "$REMOTE"
          fi

      # trader/ is stdlib-only, so there is nothing to install for the run itself. The tests
      # need pandas for the drift guard, and they gate the run: unlike scan.yml, a failing
      # suite here MUST stop the job -- this one places orders.
      - run: pip install -r requirements.txt
      - name: Test before trading
        run: python -m pytest trader/tests -q

      - name: Decide and trade
        env:
          ALPACA_KEY_ID: ${{ secrets.ALPACA_KEY_ID }}
          ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
        run: |
          MODE=--live
          if [ "${{ github.event_name }}" = "workflow_dispatch" ] && \
             [ "${{ inputs.dry_run }}" = "true" ]; then MODE=--dry-run; fi
          echo "mode: $MODE"
          python -m trader.run $MODE --data-dir history

      - name: Publish the dashboard file
        env:
          ALPACA_KEY_ID: ${{ secrets.ALPACA_KEY_ID }}
          ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
        run: |
          python -m trader.export --data-dir history \
            --out history/paper-trading.json --as-of intraday

      - name: Save the ledgers
        run: |
          cd history
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add paper_state.json paper_trades.jsonl paper_runs.jsonl paper-trading.json
          if git diff --cached --quiet; then
            echo "nothing changed"
          else
            git commit --quiet -m "paper trade $(date -u +%FT%TZ)"
            for attempt in 1 2 3; do
              git push --quiet origin HEAD:data && break
              git pull --quiet --rebase origin data || true
              sleep $(( attempt * 3 ))
            done
          fi

      # A failed run is otherwise silent unless someone thinks to look at Actions, and this
      # one can fail with money (paper money) half-committed.
      - name: Say so, in an issue
        if: failure()
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          RUN_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
          BODY="Paper trading run \`${GITHUB_RUN_ID}\` (${GITHUB_EVENT_NAME}) failed.
          ${RUN_URL}

          Check whether an order was submitted before the failure: the ledger on the
          \`data\` branch (\`paper_trades.jsonl\`) is the record, and the Alpaca dashboard
          is the truth."
          EXISTING=$(gh issue list --label paper-trade-failure --state open \
            --json number --jq '.[0].number')
          if [ -n "$EXISTING" ]; then
            gh issue comment "$EXISTING" --body "$BODY"
          else
            gh issue create --title "Paper trading run failed" \
              --label paper-trade-failure --body "$BODY"
          fi
```

- [ ] **Step 2: Create the issue label** (once, by hand)

```bash
gh label create paper-trade-failure --color B60205 \
  --description "A scheduled paper-trading run failed"
```

- [ ] **Step 3: Teach scan.yml to publish the file**

Insert this step in `scan-and-deploy`, immediately **before** the `npm run build` step. The
`history` clone already exists at that point, from the "Check out signal history" step.

```yaml
      # The trader writes this on its own schedule and never deploys; scan.yml owns the only
      # path to Pages. A missing file is normal before the first trading run, and must not
      # fail the scan -- the page handles its absence.
      - name: Include the paper-trading dashboard, if the trader has written one
        run: |
          if [ -f history/paper-trading.json ]; then
            cp history/paper-trading.json web/public/data/paper-trading.json
            echo "published paper-trading.json"
          else
            echo "no paper-trading.json on the data branch yet; skipping"
          fi
```

- [ ] **Step 4: Make the page tolerate the file's absence**

`getPaperTrading()` will 404 until the trader's first run. `PaperPage` must render a plain
"No paper-trading data published yet" state for a 404 specifically, rather than the generic
error. Add to `web/src/pages/PaperPage.test.tsx`:

```tsx
test("a 404 before the first trading run reads as not-yet, not as an error", async () => {
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(new Error("Could not load paper-trading.json (HTTP 404)"));
  render(<HashRouter><PaperPage /></HashRouter>);
  expect(await screen.findByText(/not published yet|no paper-trading data/i)).toBeInTheDocument();
});
```

Run: `cd web && npm test -- --run src/pages/PaperPage.test.tsx`
Expected: FAIL first, then PASS once `PaperPage` special-cases a message containing `404`.

- [ ] **Step 5: Validate the workflow YAML**

Run: `.venv/bin/python -c "import yaml,sys;[yaml.safe_load(open(f)) for f in ('.github/workflows/trade.yml','.github/workflows/scan.yml')];print('both parse')"`
Expected: `both parse`

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/trade.yml .github/workflows/scan.yml web/src/pages/PaperPage.tsx web/src/pages/PaperPage.test.tsx
git commit -m "feat(ci): the paper-trading workflow

Weekday 15:25 ET, both DST offsets, with /v2/clock deciding whether the market
is actually open. No push trigger, on purpose: scan.yml re-runs on every push by
design, and the same trigger here would mean merging code submits orders. Tests
gate this job rather than merely being recorded, because this one trades.

scan.yml keeps sole ownership of the Pages deployment and copies the dashboard
file in from the data branch; a missing file is normal before the first run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 12: Provenance and documentation

The four files in `handoff/` are the only copies of this strategy's research in existence and
are in no version control anywhere. The spec cites them; they have to survive.

**Files:**
- Create: `research/rsi2/` holding the four handoff files plus a `README.md`
- Modify: `CLAUDE.md`
- Delete: `handoff/` (after the move), and `handoff/.DS_Store`

**Interfaces:** none.

- [ ] **Step 1: Move the research into version control**

```bash
mkdir -p research/rsi2
git mv --force handoff/rsi2_edge_backtest.py research/rsi2/ 2>/dev/null || cp handoff/rsi2_edge_backtest.py research/rsi2/
cp handoff/rsi2_reversion_edge.pine handoff/rsi2_reversion_strategy.pine handoff/alpaca_rsi2_bot.py research/rsi2/
rm -f handoff/.DS_Store
```

- [ ] **Step 2: Write its README**

```markdown
<!-- research/rsi2/README.md -->
# RSI(2) reversion — the research behind the paper-trading tab

These four files arrived from a separate session as a handoff and were the only copies in
existence. They are the provenance for `trader/` and for
`docs/superpowers/specs/2026-10-10-paper-trading-rsi2-design.md`.

| File | What it is |
|---|---|
| `rsi2_edge_backtest.py` | The reproducible backtest and randomization test. Re-downloads its own data: `.venv/bin/python research/rsi2/rsi2_edge_backtest.py AMZN AAPL SPY`. |
| `rsi2_reversion_edge.pine` | TradingView indicator, Pine v5. Not used by the scanner or the trader. |
| `rsi2_reversion_strategy.pine` | The same rule as a TradingView `strategy()`, pre-set to 0.025%/side with `process_orders_on_close=true`. |
| `alpaca_rsi2_bot.py` | The original stdlib prototype of the live runner, on a ten-ETF watchlist. **Superseded by `trader/`** — kept because its module docstring records why market-on-close, why 15:40, and why `end` is held 16 minutes back. Do not run it; it is not wired to this repo's ledgers. |

The published research page, with every chart and caveat:
https://claude.ai/artifact/1xd3S9NBKqwaQqQN3rnMRb

**Method notes worth preserving** (each cost real work and is easy to get wrong on a second pass):

- The honest metric is **return per day held**, measured against the same asset's
  unconditional drift. Raw CAGR flatters or buries a low-exposure signal.
- **A win rate proves nothing alone.** Being long in a rising market wins most days too. The
  randomization test — matched trade count and holding period, random entry days — is what
  separates the signal from the drift. Keep it in any new asset test.
- **The 200-day gate is load-bearing.** The same trigger below the 200-day earned more per
  trade (77 bps on SPY) with a 24% drawdown and a Sharpe of 0.11.
- **Entry-delay robustness** is what proves the edge is not a closing-print artifact, and it
  is what justifies the trader deciding on a partial 15:25 bar.
- Eight variants were screened in-sample on SPY 2000–2014; those first numbers carry selection
  bias. Everything reported afterwards is out-of-sample or a different asset.
- **It does not exist in FX.** GBP/USD measured 11 bps/trade gross — negative after a 10 bps
  round trip. Measured and killed; do not re-propose it.
```

- [ ] **Step 3: Document the package in CLAUDE.md**

Add `trader/` to the Layout section, update the Commands block, and add one convention
paragraph. Exact additions:

In **Commands**, after the existing lines:

```bash
.venv/bin/python -m pytest scanner/tests research/tests trader/tests -q   # all tests (~2s)
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m trader.run --dry-run  # decide, place nothing
```

In **Layout**, after the `research/` entry:

```markdown
- `trader/` — the only thing here that *acts*: it places market-on-close orders for AMZN and
  AAPL on an Alpaca **paper** account. Stdlib only, hardcoded to the paper endpoint, its own
  `trade.yml` workflow on a 15:25 ET cron. `params.py` holds every threshold and fingerprints
  them; `ACCEPTANCE.md` holds the bar; `evaluate.py` compares the live record to the backtest.
```

As a new **Conventions** paragraph:

```markdown
**The trader is deliberately isolated from the scanner.** `scan.yml` re-runs on every push to
`main` because an algorithm change must regenerate the published lists — and that is exactly
why order submission does not live there, since the same trigger would mean merging code
submits orders. `trade.yml` has no `push` trigger, its tests *block* the job rather than being
folded into a health file, and it never deploys: it writes `paper-trading.json` to the `data`
branch and `scan.yml` copies it into the build, so there stays one path to Pages. Sizing comes
off `equity` and never off the 4x `buying_power` the paper account reports. A rejected order is
logged and left, never retried — a retry can land past Alpaca's 15:50 ET market-on-close cutoff
or re-submit an order the rule no longer wants.
```

- [ ] **Step 4: Run everything**

Run: `.venv/bin/python -m pytest scanner/tests research/tests trader/tests -q && cd web && npm test -- --run`
Expected: PASS, both suites.

- [ ] **Step 5: Commit**

```bash
git add research/rsi2 CLAUDE.md
git rm -r --cached handoff 2>/dev/null || true
rm -rf handoff
git add -A
git commit -m "docs: bring the RSI(2) research into version control

The four handoff files were the only copies in existence and in no repo
anywhere. They are the provenance for trader/ and the spec, so they move to
research/rsi2/ with a README recording the method notes -- including the two
results that are easy to re-derive wrongly: the 200-day gate is load-bearing,
and the edge does not exist in FX.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 13: Verify against the live account

The last unverified path. Everything else in this plan runs offline; this does not.

**Files:** none — this task changes no code unless it finds a bug.

- [ ] **Step 1: Dry-run against the paper account, outside market hours**

```bash
cd /Users/niksoni/Development/NS-Multi-Stratt
mkdir -p /tmp/paper-check
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m trader.run \
  --dry-run --data-dir /tmp/paper-check
```

Expected, with the market closed: the account line, then `market closed; next open ...`, and
a row appended to `/tmp/paper-check/paper_runs.jsonl`. No orders, no exceptions.

- [ ] **Step 2: Dry-run during a session** — Monday 2026-10-12, between 09:40 and 15:40 ET

```bash
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m trader.run \
  --dry-run --data-dir /tmp/paper-check
```

Expected: a decision line per symbol with a real RSI(2), SMA(200) and price; `DRY-RUN would
submit ...` only if a rule actually fires; no orders at the broker. Cross-check the RSI
against TradingView or against `research/rsi2/rsi2_edge_backtest.py` for the same date — the
partial bar makes them differ slightly, but not by much.

- [ ] **Step 3: Build the dashboard file from the real account**

```bash
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m trader.export \
  --data-dir /tmp/paper-check --out /tmp/paper-check/paper-trading.json --as-of intraday
cp /tmp/paper-check/paper-trading.json web/public/data/paper-trading.json
cd web && npm run build && npx vite preview --port 4317 --strictPort &
```

Screenshot `http://localhost:4317/#/paper`. Expected: the real $100,000 opening balance, a
flat equity curve, no positions, both symbols in the signal-state rows with live RSI values,
and `0 of 30` in the evaluation block. Then revert the copied file —
`git checkout -- web/public/data 2>/dev/null; rm -f web/public/data/paper-trading.json` —
because `web/public/data` is generated and must never be hand-edited.

- [ ] **Step 4: Fix whatever this surfaced**

If a response shape differs from the fixtures, fix `trader/alpaca.py` **and** update the
fixture from the real response, so the test keeps matching reality. Commit each fix with the
response shape that prompted it in the message. Re-run the dry-run until it is clean.

- [ ] **Step 5: Add the secrets and let it run**

```bash
gh secret set ALPACA_KEY_ID      # paste when prompted
gh secret set ALPACA_SECRET_KEY  # paste when prompted
gh workflow run trade.yml -f dry_run=true   # one manual dry-run through Actions
gh run watch
```

Expected: the Actions dry-run reaches the same decisions as the local one, commits nothing
but a runs-ledger row, and publishes `paper-trading.json` to the `data` branch. The next
weekday 15:25 ET cron then trades live, as chosen.

- [ ] **Step 6: Rotate the keys**

The pair used during this work was shared in a chat transcript. Create a fresh pair in the
Alpaca dashboard, re-run `gh secret set` for both, and confirm the next scheduled run still
authenticates. Paper-only keys, so the exposure is a simulated account — but there is no
reason to keep them.

- [ ] **Step 7: Report**

Post the first live run's outcome: what it decided, what it submitted, what filled and at
what price against the `decision_close` it decided on. That slippage number is the first live
measurement this design makes, and `trader/ACCEPTANCE.md` has a threshold waiting for it.
