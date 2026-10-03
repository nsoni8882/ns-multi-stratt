# Multi Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and host (GitHub Pages) a site that scans every S&P 500 stock on the Daily and 4H charts with two strategies (MACD + RSI Reversal, Trend Pullback), lists current BUY/SELL signals per strategy, shows a TradingView-style chart per signal, and records every signal in a history database.

**Architecture:** One scheduled GitHub Actions workflow runs a Python scanner (yfinance data, pandas indicators, strategy plugins) that writes JSON for a static Vite + React + TypeScript site and appends signals to a SQLite file on a separate `data` branch; the same workflow builds and deploys the site to Pages. Nothing runs at request time.

**Tech Stack:** Python 3.14, pandas 3, yfinance, SQLite, pytest; Node 22, Vite, React 19, TypeScript, react-router (HashRouter), Lightweight Charts v5, Vitest + Testing Library; GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-10-03-multi-strategy-design.md` (approved). Visual reference: `design-samples/index.html` (direction C).

**Verified:** every code block below was run in a scratch copy before being written here (49 scanner tests incl. a live-Yahoo smoke test, 24 web tests, a production build, a 250-ticker real scan, browser screenshots of the real charts, and the workflow's `data`-branch shell logic against a local bare repo). If a block fails when you paste it, that is a bug in this plan: stop and report rather than improvising.

**Post-review changes (after execution):** a whole-branch review led to these changes, which supersede the code blocks below where they differ: `SignalStore` creates its parent directory; `fetch_bars` retries empty tickers (3 attempts), pauses between batches, and reports tickers with stale last bars as failed; the stale banner counts weekday hours only (threshold 48, not 36); the sector filter resets when the timeframe changes; scheduled workflow runs skip the test steps. See `git log` and the spec.

## Global Constraints

- Project root: `/Users/niksoni/Development/NS-Multi-Stratt`. Python tests run as `.venv/bin/python -m pytest -q` from the root; web commands run from `web/`.
- GitHub user `nsoni8882`, repo `ns-multi-stratt`, site URL `https://nsoni8882.github.io/ns-multi-stratt/`; the Vite `base` comes from one value (`VITE_BASE`, default `/ns-multi-stratt/`) so a later move to an org site only changes that.
- Free data only: Yahoo Finance via `yfinance`. Hourly bars are requested with a 729-day lookback (Yahoo rejects a start exactly 730 days back).
- 4H bars are resampled from 1H regular-session bars into bins 09:30-13:30 ET and 13:30-16:00 ET (OHLCV: first/max/min/last/sum). Daily bars close at 16:00 ET.
- Only **closed** bars are ever evaluated; the in-progress bar is dropped.
- MACD (12, 26, 9); RSI(14, Wilder). Strategy 1 "deep" = bottom/top 10% of the trailing 100 histogram values. RSI levels: Strategy 1 uses 20/80, Strategy 2 uses 40/60; EMAs 50/200.
- A signal stays listed for 3 bars (`bars_ago` 0, 1, 2). Minimum bars: Strategy 1 = 150, Strategy 2 = 250.
- Fail the run (skip deploy and history push) if more than 10% of tickers fail to fetch; fetch in batches of 50.
- Output JSON under `web/public/data/`: `strategies.json`, `<strategy_id>/<timeframe>.json`, `charts/<timeframe>/<ticker>.json` (flagged tickers only, last 250 bars). Timeframe keys are `1d` and `4h`.
- History DB: SQLite `signals.db` on the `data` branch; unique key `(strategy_id, ticker, timeframe, side, fired_at)`; rows are inserted once and never modified.
- Site: hash routing; global 1D/4H selector in the top bar, **default 1D**, stored in the URL as `?tf=4h`; stale-data banner when `updated_at` is over 36 hours old; footer "Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate."
- Design (direction C "Soft Cards"): Lora headings, Inter body, page `#FFFBF6`, terracotta accent `#CC785C` (text `#A5472A`), BUY `#27694B` on `#E3F0E7`, SELL `#9E2F45` on `#F9E4E8`; BUY/SELL always labelled with text and an arrow; all text pairs at least 4.5:1; respect `prefers-reduced-motion`.
- The "Lightweight Charts" attribution logo stays visible (its license requires attribution).

## Review Focus

Inputs and conditions the spec implies but that are easy to get wrong, with the task whose tests pin each one:

1. **An unfinished bar must never produce a signal** (a daily bar before 16:00 ET, a 4H bar still forming, or a 4H group missing its final hourly bar because Yahoo was late). Pinned in Task 6 tests.
2. **Flat prices and NaN gaps** (zero-volatility or halted tickers must not crash or signal; RSI of a flat series is 50, not NaN). Pinned in Tasks 1, 2 and 3.
3. **Tickers with a dot** (`BRK.B`, `BF.B`) must become Yahoo's `BRK-B`, `BF-B`. Pinned in Task 5.
4. **Zero signals** must still produce valid empty JSON files and the site must show "No signals right now." instead of a blank page. Pinned in Tasks 7 and 11.
5. **Reruns and the duplicate DST cron runs** must not duplicate or alter history rows. Pinned in Tasks 4 and 7.

---

### Task 1: Project skeleton and indicators

**Files:**
- Create: `.gitignore`, `requirements.txt`, `scanner/__init__.py`, `scanner/tests/__init__.py`, `scanner/tests/conftest.py`, `scanner/indicators.py`
- Test: `scanner/tests/test_indicators.py`

**Interfaces:**
- Consumes: nothing
- Produces: `ema(series, span)`, `macd(close) -> DataFrame[macd, signal, hist]`, `rsi(close, length=14) -> Series` (Wilder, NaN until bar `length`, flat series = 50), `crossed_above(series, i, level) -> bool` (`series[i-1] < level <= series[i]`), `crossed_below(series, i, level)`; test helper `make_df(closes)` returning a closed-bar frame with `close_time`

- [ ] **Step 1: Initialise the repository and Python environment**

Run from `/Users/niksoni/Development/NS-Multi-Stratt`:

```bash
git init -b main
python3 -m venv .venv
mkdir -p scanner/tests scanner/strategies
touch scanner/__init__.py scanner/tests/__init__.py scanner/strategies/__init__.py
```

Create `requirements.txt`:

```text
pandas>=3.0,<4
numpy>=2
yfinance>=1.7,<2
lxml>=5
requests>=2.32
pytest>=8
```

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.scratch/
*.db
history/
web/node_modules/
web/dist/
web/public/data/
.DS_Store
```

Then:

```bash
.venv/bin/pip install -r requirements.txt
```


- [ ] **Step 2: Commit the spec and design samples**

```bash
git add .gitignore requirements.txt docs design-samples scanner
git commit -m "chore: project skeleton, spec and design samples"
```


- [ ] **Step 3: Write the failing indicator tests**

Also create the shared test helper `scanner/tests/conftest.py` (used by later tasks):

Create `scanner/tests/conftest.py`:

```python
import pandas as pd


def make_df(closes, start="2024-01-01"):
    """Closed-bar DataFrame in the shape strategies expect (daily-style bars)."""
    idx = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": 1000,
            "close_time": idx + pd.Timedelta(hours=20),
        },
        index=idx,
    )
```

Create `scanner/tests/test_indicators.py`:

```python
import numpy as np
import pandas as pd
import pytest

from scanner.indicators import crossed_above, crossed_below, ema, macd, rsi

# Classic Wilder/StockCharts RSI worked example (14-period). StockCharts rounds its
# intermediate averages, so its published values sit ~0.07 above the exact result.
WILDER_CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
]
WILDER_RSI = [70.53, 66.32, 66.55, 69.41, 66.36, 57.97]


def test_rsi_matches_wilder_reference():
    out = rsi(pd.Series(WILDER_CLOSES), 14)
    assert out.iloc[:14].isna().all()
    assert out.iloc[14:].round(2).tolist() == pytest.approx(WILDER_RSI, abs=0.1)


def test_rsi_rising_series_is_100_and_falling_is_0():
    up = pd.Series(np.arange(1.0, 40.0))
    down = pd.Series(np.arange(40.0, 1.0, -1.0))
    assert rsi(up).iloc[-1] == 100.0
    assert rsi(down).iloc[-1] == 0.0


def test_rsi_flat_series_is_50_not_nan():
    out = rsi(pd.Series([10.0] * 40))
    assert out.iloc[-1] == 50.0


def test_rsi_short_series_is_all_nan():
    assert rsi(pd.Series([1.0, 2.0, 3.0])).isna().all()


def test_ema_of_constant_is_constant():
    assert ema(pd.Series([5.0] * 30), 10).iloc[-1] == pytest.approx(5.0)


def test_macd_hist_is_line_minus_signal():
    close = pd.Series(np.linspace(100, 130, 80) + np.sin(np.arange(80)))
    m = macd(close)
    assert (m["hist"] - (m["macd"] - m["signal"])).abs().max() < 1e-12
    # Hand check of the 12/26 EMA difference on the last bar.
    expected = ema(close, 12).iloc[-1] - ema(close, 26).iloc[-1]
    assert m["macd"].iloc[-1] == pytest.approx(expected)


def test_crossed_above_and_below():
    s = pd.Series([25.0, 19.0, 21.0, 18.0])
    assert crossed_above(s, 2, 20) is True
    assert crossed_above(s, 1, 20) is False
    assert crossed_below(s, 1, 20) is True
    assert crossed_below(s, 2, 20) is False


def test_crossed_with_nan_is_false():
    s = pd.Series([np.nan, 21.0])
    assert crossed_above(s, 1, 20) is False
    assert crossed_below(s, 1, 20) is False
```


- [ ] **Step 4: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_indicators.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scanner.indicators'`


- [ ] **Step 5: Implement the indicators**

Create `scanner/indicators.py`:

```python
"""Technical indicators. All functions take and return pandas Series/DataFrames."""
import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's RSI, seeded with a simple average of the first `length` changes."""
    values = close.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) <= length:
        return pd.Series(out, index=close.index)
    delta = np.diff(values, prepend=np.nan)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[1 : length + 1].mean()
    avg_loss = loss[1 : length + 1].mean()
    out[length] = _rsi_value(avg_gain, avg_loss)
    for i in range(length + 1, len(values)):
        avg_gain = (avg_gain * (length - 1) + gain[i]) / length
        avg_loss = (avg_loss * (length - 1) + loss[i]) / length
        out[i] = _rsi_value(avg_gain, avg_loss)
    return pd.Series(out, index=close.index)


def crossed_above(series: pd.Series, i: int, level: float) -> bool:
    """True if series closed below `level` on bar i-1 and at/above it on bar i."""
    return bool(series.iloc[i - 1] < level <= series.iloc[i])


def crossed_below(series: pd.Series, i: int, level: float) -> bool:
    """True if series closed above `level` on bar i-1 and at/below it on bar i."""
    return bool(series.iloc[i - 1] > level >= series.iloc[i])
```


- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_indicators.py`
Expected: 8 passed


- [ ] **Step 7: Commit**

```bash
git add scanner
git commit -m "feat(scanner): EMA, MACD, Wilder RSI and cross helpers"
```



### Task 2: Strategy base types and Strategy 1 (MACD + RSI Reversal)

**Files:**
- Create: `scanner/strategies/base.py`, `scanner/strategies/macd_rsi_reversal.py`
- Test: `scanner/tests/test_macd_rsi_reversal.py`

**Interfaces:**
- Consumes: Task 1: `macd`, `rsi`, `crossed_above`, `crossed_below`, `make_df`
- Produces: `Signal` dataclass (`side`, `bars_ago`, `bar_time`, `fired_at`, `entry_price`, `details`), `SIGNAL_WINDOW = 3`, `make_signal(df, i, side, details) -> Signal`, `Strategy` protocol (`id`, `name`, `description`, `min_bars`, `chart`, `evaluate(df) -> Signal | None`), `MacdRsiReversal` (id `macd-rsi-reversal`), `rule_side(hist, lo, hi, r, i) -> 'BUY'|'SELL'|None`

- [ ] **Step 1: Write the failing Strategy 1 tests**

Create `scanner/tests/test_macd_rsi_reversal.py`:

```python
import numpy as np
import pandas as pd

from scanner.strategies.macd_rsi_reversal import MacdRsiReversal, rule_side
from scanner.tests.conftest import make_df


def series(values):
    return pd.Series(values, dtype=float)


def buy_inputs():
    # Bar index 9 is the signal bar. Histogram was deep (<= lo) at bar 5, then rose 3 bars, still <= 0.
    hist = series([0, 0, 0, 0, -5, -6, -5, -4, -3, -2])
    lo = series([-5.5] * 10)
    hi = series([5.5] * 10)
    rsi = series([50, 50, 50, 50, 30, 25, 22, 21, 19, 21])
    return hist, lo, hi, rsi


def test_rule_buy():
    hist, lo, hi, rsi = buy_inputs()
    assert rule_side(hist, lo, hi, rsi, 9) == "BUY"


def test_rule_buy_needs_deep_histogram():
    hist, lo, hi, rsi = buy_inputs()
    assert rule_side(hist, series([-10.0] * 10), hi, rsi, 9) is None


def test_rule_buy_needs_two_rising_bars():
    hist, lo, hi, rsi = buy_inputs()
    hist.iloc[8] = -1  # bar 8 above bar 9 -> not rising into the signal bar
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_buy_needs_histogram_not_above_zero():
    hist, lo, hi, rsi = buy_inputs()
    hist = hist + 4  # signal bar histogram is now > 0
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_buy_needs_rsi_cross_on_signal_bar():
    hist, lo, hi, rsi = buy_inputs()
    rsi.iloc[8] = 25  # no longer below 20 on the prior bar
    assert rule_side(hist, lo, hi, rsi, 9) is None


def test_rule_sell_is_the_mirror():
    hist, lo, hi, rsi = buy_inputs()
    assert rule_side(-hist, -hi, -lo, 100 - rsi, 9) == "SELL"


def test_evaluate_buy_on_crash_then_bounce():
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    closes = list(np.concatenate([up, down, [down[-1] * 1.06]]))
    sig = MacdRsiReversal().evaluate(make_df(closes))
    assert sig is not None
    assert sig.side == "BUY" and sig.bars_ago == 0
    assert sig.entry_price == closes[-1]
    assert sig.fired_at == make_df(closes)["close_time"].iloc[-1]
    assert sig.details["rsi"] > 20 and sig.details["macd_hist"] <= 0


def test_signal_window_is_three_bars():
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    closes = list(np.concatenate([up, down, [down[-1] * 1.06]]))
    strat = MacdRsiReversal()
    assert strat.evaluate(make_df(closes + [closes[-1]] * 2)).bars_ago == 2
    assert strat.evaluate(make_df(closes + [closes[-1]] * 3)) is None


def test_too_few_bars_returns_none():
    assert MacdRsiReversal().evaluate(make_df([100.0] * 50)) is None


def test_flat_prices_give_no_signal():
    assert MacdRsiReversal().evaluate(make_df([100.0] * 300)) is None


def test_nan_prices_do_not_crash_or_signal():
    closes = [100.0] * 300
    closes[-5] = float("nan")
    assert MacdRsiReversal().evaluate(make_df(closes)) is None
```

The BUY series (180 bars of gentle uptrend, 14 bars of -2% days, then a +6% bounce) is the verified trigger; flat and NaN inputs cover Review Focus item 2.


- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_macd_rsi_reversal.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scanner.strategies.macd_rsi_reversal'`


- [ ] **Step 3: Implement the shared strategy types**

Create `scanner/strategies/base.py`:

```python
"""Shared types for strategies.

A strategy receives a DataFrame of *closed* bars with a UTC DatetimeIndex (bar open)
and columns open, high, low, close, volume, close_time (UTC timestamp of bar close).
"""
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

SIGNAL_WINDOW = 3  # a signal stays listed for bars_ago 0, 1, 2


@dataclass(frozen=True)
class Signal:
    side: str  # "BUY" or "SELL"
    bars_ago: int
    bar_time: pd.Timestamp  # open time of the signal bar
    fired_at: pd.Timestamp  # close time of the signal bar
    entry_price: float  # close of the signal bar
    details: dict = field(default_factory=dict)


class Strategy(Protocol):
    id: str
    name: str
    description: str
    min_bars: int
    chart: dict  # how the site draws this strategy's chart: rsi_levels, macd_deep, emas

    def evaluate(self, df: pd.DataFrame) -> "Signal | None": ...


def make_signal(df: pd.DataFrame, i: int, side: str, details: dict) -> Signal:
    return Signal(
        side=side,
        bars_ago=len(df) - 1 - i,
        bar_time=df.index[i],
        fired_at=df["close_time"].iloc[i],
        entry_price=float(df["close"].iloc[i]),
        details={k: round(float(v), 4) for k, v in details.items()},
    )
```


- [ ] **Step 4: Implement Strategy 1**

Create `scanner/strategies/macd_rsi_reversal.py`:

```python
import pandas as pd

from scanner.indicators import crossed_above, crossed_below, macd, rsi
from scanner.strategies.base import SIGNAL_WINDOW, Signal, make_signal

HIST_WINDOW = 100  # trailing bars used to rank the histogram
HIST_QUANTILE = 0.10  # "deep" = bottom/top 10% of the trailing window
DEEP_LOOKBACK = 5  # bars before the signal bar in which the histogram was deep
RSI_LOW = 20
RSI_HIGH = 80


def rule_side(hist: pd.Series, lo: pd.Series, hi: pd.Series, r: pd.Series, i: int) -> "str | None":
    """Return "BUY", "SELL" or None for bar i. Pure function of the indicator series.

    The RSI "was beyond the level within the last 5 bars" condition is implied by
    the cross on bar i (bar i-1 was beyond the level), so only the cross is tested.
    """
    window = slice(i - DEEP_LOOKBACK, i)
    h, h1, h2 = hist.iloc[i], hist.iloc[i - 1], hist.iloc[i - 2]

    deep_low = bool((hist.iloc[window] <= lo.iloc[window]).any())
    if deep_low and h > h1 > h2 and h <= 0 and crossed_above(r, i, RSI_LOW):
        return "BUY"

    deep_high = bool((hist.iloc[window] >= hi.iloc[window]).any())
    if deep_high and h < h1 < h2 and h >= 0 and crossed_below(r, i, RSI_HIGH):
        return "SELL"
    return None


class MacdRsiReversal:
    id = "macd-rsi-reversal"
    name = "MACD + RSI Reversal"
    description = (
        "BUY when the MACD histogram climbs back from a deep low while RSI(14) crosses "
        "back above 20. SELL is the mirror: histogram falling from a deep high while "
        "RSI(14) crosses back below 80."
    )
    min_bars = 150
    chart = {"rsi_levels": [RSI_LOW, RSI_HIGH], "macd_deep": True, "emas": False}

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        hist = macd(df["close"])["hist"]
        lo = hist.rolling(HIST_WINDOW).quantile(HIST_QUANTILE)
        hi = hist.rolling(HIST_WINDOW).quantile(1 - HIST_QUANTILE)
        r = rsi(df["close"])
        for k in range(SIGNAL_WINDOW):
            i = len(df) - 1 - k
            side = rule_side(hist, lo, hi, r, i)
            if side:
                return make_signal(df, i, side, {"macd_hist": hist.iloc[i], "rsi": r.iloc[i]})
        return None
```


- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_macd_rsi_reversal.py`
Expected: 11 passed


- [ ] **Step 6: Commit**

```bash
git add scanner
git commit -m "feat(scanner): MACD + RSI reversal strategy"
```



### Task 3: Strategy 2 (Trend Pullback) and the registry

**Files:**
- Create: `scanner/strategies/trend_pullback.py`; Modify: `scanner/strategies/__init__.py`
- Test: `scanner/tests/test_trend_pullback.py`

**Interfaces:**
- Consumes: Tasks 1-2: `ema`, `rsi`, `crossed_above/below`, `make_signal`, `SIGNAL_WINDOW`
- Produces: `TrendPullback` (id `trend-pullback`), `STRATEGIES = [MacdRsiReversal(), TrendPullback()]` (order matters: it is the order shown on the site)

- [ ] **Step 1: Write the failing Strategy 2 tests**

Create `scanner/tests/test_trend_pullback.py`:

```python
import numpy as np
import pandas as pd

from scanner.strategies.trend_pullback import TrendPullback, rule_side
from scanner.tests.conftest import make_df


def series(values):
    return pd.Series(values, dtype=float)


def test_rule_buy_in_uptrend_when_rsi_crosses_40():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([38, 41]), 1) == "BUY"


def test_rule_buy_blocked_without_uptrend():
    ema50, ema200 = series([105, 105]), series([100, 100])
    assert rule_side(series([90, 90]), ema50, ema200, series([38, 41]), 1) is None  # close below 200 EMA
    assert rule_side(series([110, 110]), series([95, 95]), ema200, series([38, 41]), 1) is None  # 50 below 200


def test_rule_sell_in_downtrend_when_rsi_crosses_below_60():
    close, ema50, ema200 = series([90, 90]), series([95, 95]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([62, 59]), 1) == "SELL"


def test_rule_no_signal_without_cross():
    close, ema50, ema200 = series([110, 110]), series([105, 105]), series([100, 100])
    assert rule_side(close, ema50, ema200, series([45, 46]), 1) is None


def _uptrend_with_dip():
    up = 100 * np.cumprod(1 + 0.002 + 0.003 * np.sin(np.arange(260) / 3))
    dip = up[-1] * np.cumprod(np.full(3, 1 - 0.015))
    return list(np.concatenate([up, dip, [dip[-1] * 1.01]]))


def test_evaluate_buy_on_pullback_in_uptrend():
    sig = TrendPullback().evaluate(make_df(_uptrend_with_dip()))
    assert sig is not None and sig.side == "BUY" and sig.bars_ago == 0
    assert sig.details["ema50"] > sig.details["ema200"]


def test_evaluate_sell_on_rally_in_downtrend():
    dn = 100 * np.cumprod(1 - 0.002 - 0.003 * np.sin(np.arange(260) / 3))
    rally = dn[-1] * np.cumprod(np.full(3, 1 + 0.015))
    closes = list(np.concatenate([dn, rally, [rally[-1] * 0.99]]))
    sig = TrendPullback().evaluate(make_df(closes))
    assert sig is not None and sig.side == "SELL" and sig.bars_ago == 0


def test_needs_250_bars():
    assert TrendPullback().evaluate(make_df(_uptrend_with_dip()[-200:])) is None


def test_flat_prices_give_no_signal():
    assert TrendPullback().evaluate(make_df([100.0] * 300)) is None
```


- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_trend_pullback.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scanner.strategies.trend_pullback'`


- [ ] **Step 3: Implement Strategy 2 and the registry**

Create `scanner/strategies/trend_pullback.py`:

```python
import pandas as pd

from scanner.indicators import crossed_above, crossed_below, ema, rsi
from scanner.strategies.base import SIGNAL_WINDOW, Signal, make_signal

RSI_BUY_LEVEL = 40
RSI_SELL_LEVEL = 60


def rule_side(close: pd.Series, ema50: pd.Series, ema200: pd.Series, r: pd.Series, i: int) -> "str | None":
    """Return "BUY", "SELL" or None for bar i. The 5-bar RSI lookback in the spec is
    implied by the cross on bar i (bar i-1 was beyond the level)."""
    if close.iloc[i] > ema200.iloc[i] and ema50.iloc[i] > ema200.iloc[i] and crossed_above(r, i, RSI_BUY_LEVEL):
        return "BUY"
    if close.iloc[i] < ema200.iloc[i] and ema50.iloc[i] < ema200.iloc[i] and crossed_below(r, i, RSI_SELL_LEVEL):
        return "SELL"
    return None


class TrendPullback:
    id = "trend-pullback"
    name = "Trend Pullback"
    description = (
        "BUY when price is in an uptrend (above the 200 EMA, with the 50 EMA above it) "
        "and RSI(14) dips below 40 then crosses back above it. SELL is the mirror in a "
        "downtrend with RSI crossing back below 60."
    )
    min_bars = 250
    chart = {"rsi_levels": [RSI_BUY_LEVEL, RSI_SELL_LEVEL], "macd_deep": False, "emas": True}

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        close = df["close"]
        ema50, ema200 = ema(close, 50), ema(close, 200)
        r = rsi(close)
        for k in range(SIGNAL_WINDOW):
            i = len(df) - 1 - k
            side = rule_side(close, ema50, ema200, r, i)
            if side:
                return make_signal(df, i, side, {"rsi": r.iloc[i], "ema50": ema50.iloc[i], "ema200": ema200.iloc[i]})
        return None
```

Create `scanner/strategies/__init__.py`:

```python
from scanner.strategies.macd_rsi_reversal import MacdRsiReversal
from scanner.strategies.trend_pullback import TrendPullback

STRATEGIES = [MacdRsiReversal(), TrendPullback()]
```


- [ ] **Step 4: Run all scanner tests**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (27 so far)


- [ ] **Step 5: Commit**

```bash
git add scanner
git commit -m "feat(scanner): trend pullback strategy and registry"
```



### Task 4: Signal history store

**Files:**
- Create: `scanner/store.py`
- Test: `scanner/tests/test_store.py`

**Interfaces:**
- Consumes: nothing
- Produces: `SignalRecord(strategy_id, ticker, timeframe, side, fired_at, entry_price, details, recorded_at)`, `SignalStore(path)` with `record_signals(list[SignalRecord]) -> int inserted`, `count()`, `close()`; creates the schema on first use; duplicates ignored, existing rows untouched

- [ ] **Step 1: Write the failing store tests**

Create `scanner/tests/test_store.py`:

```python
from scanner.store import SignalRecord, SignalStore


def rec(**kw):
    base = dict(strategy_id="s1", ticker="AAPL", timeframe="1d", side="BUY",
                fired_at="2026-10-02T20:00:00+00:00", entry_price=100.0,
                details={"rsi": 21.5}, recorded_at="2026-10-02T20:05:00+00:00")
    base.update(kw)
    return SignalRecord(**base)


def test_creates_database_and_inserts(tmp_path):
    path = tmp_path / "signals.db"
    store = SignalStore(path)
    assert store.record_signals([rec(), rec(ticker="MSFT")]) == 2
    assert store.count() == 2
    store.close()
    assert path.exists()


def test_duplicate_is_ignored_and_original_row_is_untouched(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.record_signals([rec(entry_price=100.0, recorded_at="2026-10-02T20:05:00+00:00")])
    inserted = store.record_signals([rec(entry_price=999.0, recorded_at="2026-10-03T00:00:00+00:00")])
    assert inserted == 0
    row = store.conn.execute("SELECT entry_price, recorded_at FROM signals").fetchall()
    assert row == [(100.0, "2026-10-02T20:05:00+00:00")]


def test_different_side_or_time_is_a_new_signal(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.record_signals([rec()])
    assert store.record_signals([rec(side="SELL"), rec(fired_at="2026-10-05T20:00:00+00:00")]) == 2


def test_reopening_keeps_data(tmp_path):
    path = tmp_path / "signals.db"
    SignalStore(path).record_signals([rec()])
    assert SignalStore(path).count() == 1


def test_empty_batch_is_fine(tmp_path):
    assert SignalStore(tmp_path / "signals.db").record_signals([]) == 0
```


- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_store.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scanner.store'`


- [ ] **Step 3: Implement the store**

Create `scanner/store.py`:

```python
"""Signal history in SQLite. Rows are inserted once and never modified."""
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    side TEXT NOT NULL,
    fired_at TEXT NOT NULL,
    entry_price REAL NOT NULL,
    details TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (strategy_id, ticker, timeframe, side, fired_at)
)
"""


@dataclass(frozen=True)
class SignalRecord:
    strategy_id: str
    ticker: str
    timeframe: str
    side: str
    fired_at: str  # ISO-8601 UTC
    entry_price: float
    details: dict
    recorded_at: str  # ISO-8601 UTC


class SignalStore:
    def __init__(self, path: "str | Path"):
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def record_signals(self, records: "list[SignalRecord]") -> int:
        """Insert records, ignoring ones already stored. Returns the number inserted."""
        before = self.conn.total_changes
        self.conn.executemany(
            "INSERT OR IGNORE INTO signals "
            "(strategy_id, ticker, timeframe, side, fired_at, entry_price, details, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (r.strategy_id, r.ticker, r.timeframe, r.side, r.fired_at, r.entry_price,
                 json.dumps(r.details, sort_keys=True), r.recorded_at)
                for r in records
            ],
        )
        self.conn.commit()
        return self.conn.total_changes - before

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
```


- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_store.py`
Expected: 5 passed


- [ ] **Step 5: Commit**

```bash
git add scanner
git commit -m "feat(scanner): SQLite signal history store"
```



### Task 5: S&P 500 universe

**Files:**
- Create: `scanner/universe.py`, `scanner/universe_fallback.csv` (generated)
- Test: `scanner/tests/test_universe.py`

**Interfaces:**
- Consumes: nothing
- Produces: `parse_universe(html) -> DataFrame[ticker, name, sector]` (dots become dashes), `fetch_universe()` (raises if fewer than 450 rows), `load_universe(fallback=FALLBACK_CSV)` (falls back to the CSV on any failure)

- [ ] **Step 1: Write the failing universe tests**

Create `scanner/tests/test_universe.py`:

```python
import pandas as pd
import pytest

from scanner import universe
from scanner.universe import load_universe, parse_universe

HTML = """
<table class="wikitable sortable">
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>Date added</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td><td>1982</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td><td>2010</td></tr>
<tr><td>BF.B</td><td>Brown-Forman</td><td>Consumer Staples</td><td>1982</td></tr>
</table>
"""


def test_parse_universe_columns_and_dot_to_dash():
    df = parse_universe(HTML)
    assert df.columns.tolist() == ["ticker", "name", "sector"]
    assert df["ticker"].tolist() == ["AAPL", "BRK-B", "BF-B"]
    assert df.loc[0, "sector"] == "Information Technology"


def test_load_universe_falls_back_when_scrape_fails(monkeypatch, tmp_path):
    csv = tmp_path / "fallback.csv"
    pd.DataFrame({"ticker": ["AAPL"], "name": ["Apple"], "sector": ["IT"]}).to_csv(csv, index=False)

    def boom():
        raise RuntimeError("wikipedia down")

    monkeypatch.setattr(universe, "fetch_universe", boom)
    assert load_universe(csv)["ticker"].tolist() == ["AAPL"]


def test_fetch_rejects_suspiciously_small_table(monkeypatch):
    class Resp:
        text = HTML
        def raise_for_status(self): pass

    monkeypatch.setattr(universe.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(ValueError):
        universe.fetch_universe()
```


- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_universe.py`
Expected: FAIL, `ImportError: cannot import name 'universe' from 'scanner'`


- [ ] **Step 3: Implement the universe loader**

Create `scanner/universe.py`:

```python
"""S&P 500 constituents: scrape Wikipedia, fall back to a committed snapshot."""
import argparse
import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FALLBACK_CSV = Path(__file__).parent / "universe_fallback.csv"
MIN_EXPECTED = 450  # a scrape returning fewer rows is treated as broken

log = logging.getLogger(__name__)


def parse_universe(html: str) -> pd.DataFrame:
    """Parse the Wikipedia constituents table into columns ticker, name, sector."""
    table = pd.read_html(StringIO(html), match="Symbol")[0]
    out = table.rename(columns={"Symbol": "ticker", "Security": "name", "GICS Sector": "sector"})
    out = out[["ticker", "name", "sector"]].copy()
    out["ticker"] = out["ticker"].astype(str).str.strip().str.replace(".", "-", regex=False)
    return out.drop_duplicates("ticker").reset_index(drop=True)


def fetch_universe() -> pd.DataFrame:
    resp = requests.get(WIKI_URL, headers={"User-Agent": "ns-multi-stratt/1.0 (personal screener)"}, timeout=30)
    resp.raise_for_status()
    df = parse_universe(resp.text)
    if len(df) < MIN_EXPECTED:
        raise ValueError(f"universe scrape returned only {len(df)} rows")
    return df


def load_universe(fallback: Path = FALLBACK_CSV) -> pd.DataFrame:
    try:
        return fetch_universe()
    except Exception as exc:
        log.warning("universe scrape failed (%s); using %s", exc, fallback)
        return pd.read_csv(fallback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh the committed universe snapshot")
    parser.parse_args()
    fetch_universe().to_csv(FALLBACK_CSV, index=False)
    print(f"wrote {FALLBACK_CSV}")
```


- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_universe.py`
Expected: 3 passed


- [ ] **Step 5: Generate the committed fallback snapshot**

```bash
.venv/bin/python -m scanner.universe
wc -l scanner/universe_fallback.csv
grep -c "BRK-B" scanner/universe_fallback.csv
```

Expected: about 504 lines (503 tickers plus header) and `1` match for `BRK-B`. This needs internet access.


- [ ] **Step 6: Commit**

```bash
git add scanner
git commit -m "feat(scanner): S&P 500 universe loader with committed fallback"
```



### Task 6: Data layer (fetch, 4H resample, closed bars only)

**Files:**
- Create: `scanner/data.py`
- Test: `scanner/tests/test_data.py`

**Interfaces:**
- Consumes: nothing
- Produces: `to_daily(raw, now)`, `to_four_hour(raw, now)` (both return a frame indexed by UTC bar-open time with `open, high, low, close, volume, close_time`, closed bars only), `fetch_bars(tickers, timeframe, now) -> (dict[ticker, DataFrame], list[failed tickers])` where `timeframe` is `"1d"` or `"4h"`

- [ ] **Step 1: Write the failing data tests**

Create `scanner/tests/test_data.py`:

```python
import pandas as pd
import pytest

from scanner.data import to_daily, to_four_hour

ET = "America/New_York"


def hourly(day, hours, price=100.0):
    """1H bars on `day` starting at each (hour, minute) in `hours`, tz-aware ET like Yahoo's."""
    idx = [pd.Timestamp(f"{day} {h:02d}:{m:02d}").tz_localize(ET) for h, m in hours]
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": [price + i for i in range(n)],
            "High": [price + i + 2 for i in range(n)],
            "Low": [price + i - 2 for i in range(n)],
            "Close": [price + i + 1 for i in range(n)],
            "Volume": [10] * n,
        },
        index=pd.DatetimeIndex(idx).tz_convert("UTC"),
    )


FULL_DAY = [(9, 30), (10, 30), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30)]
AFTER_CLOSE = pd.Timestamp("2026-09-30 22:00", tz="UTC")  # 18:00 ET


def test_four_hour_bins_and_aggregation():
    out = to_four_hour(hourly("2026-09-30", FULL_DAY), AFTER_CLOSE)
    assert len(out) == 2
    first, second = out.iloc[0], out.iloc[1]
    # First bar: 09:30-13:30 ET = hourly bars 0..3; second: 13:30-16:00 ET = bars 4..6.
    assert (first["open"], first["close"], first["high"], first["low"], first["volume"]) == (100, 104, 105, 98, 40)
    assert (second["open"], second["close"], second["high"], second["low"], second["volume"]) == (104, 107, 108, 102, 30)
    assert out.index[0] == pd.Timestamp("2026-09-30 13:30", tz="UTC")  # 09:30 ET (EDT)
    assert out["close_time"].tolist() == [
        pd.Timestamp("2026-09-30 17:30", tz="UTC"),  # 13:30 ET
        pd.Timestamp("2026-09-30 20:00", tz="UTC"),  # 16:00 ET
    ]


def test_four_hour_drops_bar_that_has_not_closed_yet():
    now = pd.Timestamp("2026-09-30 19:00", tz="UTC")  # 15:00 ET, second bar still forming
    out = to_four_hour(hourly("2026-09-30", FULL_DAY[:6]), now)
    assert len(out) == 1
    assert out["close_time"].iloc[0] == pd.Timestamp("2026-09-30 17:30", tz="UTC")


def test_four_hour_drops_group_missing_its_last_hourly_bar():
    # Past 16:05 ET but Yahoo has not delivered the 15:30 bar yet.
    out = to_four_hour(hourly("2026-09-30", FULL_DAY[:6]), AFTER_CLOSE)
    assert len(out) == 1


def test_four_hour_early_close_day_has_single_bar():
    out = to_four_hour(hourly("2026-11-27", FULL_DAY[:4]), pd.Timestamp("2026-11-27 19:00", tz="UTC"))
    assert len(out) == 1


def test_four_hour_uses_correct_utc_offset_in_winter():
    out = to_four_hour(hourly("2026-12-15", FULL_DAY), pd.Timestamp("2026-12-15 23:00", tz="UTC"))
    assert out.index[0] == pd.Timestamp("2026-12-15 14:30", tz="UTC")  # 09:30 ET (EST)


def test_four_hour_ignores_rows_without_close():
    raw = hourly("2026-09-30", FULL_DAY)
    raw.iloc[2, raw.columns.get_loc("Close")] = float("nan")
    assert len(to_four_hour(raw, AFTER_CLOSE)) == 2


def _daily(dates):
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    n = len(idx)
    return pd.DataFrame({"Open": [1.0] * n, "High": [2.0] * n, "Low": [0.5] * n, "Close": [1.5] * n, "Volume": [5] * n}, index=idx)


def test_daily_close_time_is_1600_et_and_today_is_dropped_until_close():
    raw = _daily(["2026-09-29", "2026-09-30"])
    during = to_daily(raw, pd.Timestamp("2026-09-30 15:00", tz="UTC"))  # 11:00 ET
    assert len(during) == 1
    after = to_daily(raw, AFTER_CLOSE)
    assert len(after) == 2
    assert after["close_time"].iloc[-1] == pd.Timestamp("2026-09-30 20:00", tz="UTC")
    assert after.index[-1] == pd.Timestamp("2026-09-30", tz="UTC")


def test_daily_accepts_tz_aware_index():
    raw = _daily(["2026-09-29", "2026-09-30"])
    raw.index = raw.index.tz_localize(ET)
    out = to_daily(raw, AFTER_CLOSE)
    assert out.index.tolist() == [pd.Timestamp("2026-09-29", tz="UTC"), pd.Timestamp("2026-09-30", tz="UTC")]
```

These pin Review Focus item 1: an in-progress daily bar, an in-progress 4H bar, and a 4H group missing its last hourly bar are all dropped; early-close days and winter UTC offsets are handled.


- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_data.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scanner.data'`


- [ ] **Step 3: Implement the data layer**

Create `scanner/data.py`:

```python
"""Fetch Yahoo bars and shape them into closed-bar DataFrames.

Output frame: UTC DatetimeIndex (bar open; midnight UTC of the trading date for daily bars),
columns open, high, low, close, volume, close_time (UTC). Only closed bars are returned.
"""
import logging
import time

import pandas as pd
import yfinance as yf

ET = "America/New_York"
OHLCV = ["open", "high", "low", "close", "volume"]
BATCH_SIZE = 50
HOURLY_LOOKBACK_DAYS = 729  # Yahoo rejects requests reaching back 730 days
MIDDAY = pd.Timedelta(hours=13, minutes=30)  # end of the first 4H bar (ET)
CLOSE = pd.Timedelta(hours=16)  # end of the second 4H bar / daily bar (ET)

log = logging.getLogger(__name__)


def _clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=str.lower)[OHLCV]
    return df.dropna(subset=["close"])


def _et_timestamp(day, offset: pd.Timedelta) -> pd.Timestamp:
    return pd.Timestamp(f"{day} 00:00").tz_localize(ET) + offset


def to_daily(raw: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Daily bars with a US-market 16:00 ET close time; drops bars not yet closed."""
    df = _clean(raw)
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    days = idx.normalize()
    close_time = [_et_timestamp(d.date(), CLOSE).tz_convert("UTC") for d in days]
    out = df.set_axis(days.tz_localize("UTC"))
    out["close_time"] = pd.DatetimeIndex(close_time)
    return out[out["close_time"] <= now]


def to_four_hour(raw: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Resample 1H regular-session bars into 4H bars: 09:30-13:30 and 13:30-16:00 ET.

    A group is dropped if its boundary is still in the future, or if its final hourly bar
    is missing (so a partially delivered bar is never treated as closed).
    """
    df = _clean(raw)
    et = df.index.tz_convert(ET)
    minutes = et.hour * 60 + et.minute
    grouped = df.assign(ts=et, half=(minutes >= 13 * 60 + 30).astype(int), day=et.date).groupby(["day", "half"])
    out = grouped.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), start=("ts", "min"), last=("ts", "max"),
    )
    boundary = [
        _et_timestamp(day, MIDDAY if half == 0 else CLOSE)
        for day, half in out.index
    ]
    out["close_time"] = pd.DatetimeIndex(boundary).tz_convert("UTC")
    complete = pd.Series([last >= b - pd.Timedelta(hours=1) for last, b in zip(out["last"], boundary)], index=out.index)
    out = out[complete & (out["close_time"] <= now)]
    out = out.set_axis(pd.DatetimeIndex(out["start"]).tz_convert("UTC"))
    return out[OHLCV + ["close_time"]]


def _download(tickers: "list[str]", timeframe: str, now: pd.Timestamp, attempts: int = 3) -> pd.DataFrame:
    if timeframe == "1d":
        kwargs = {"period": "2y", "interval": "1d"}
    else:
        start = (now - pd.Timedelta(days=HOURLY_LOOKBACK_DAYS)).date()
        kwargs = {"start": start, "interval": "1h"}
    for attempt in range(1, attempts + 1):
        try:
            return yf.download(tickers, group_by="ticker", auto_adjust=True, threads=True, progress=False, **kwargs)
        except Exception as exc:  # network / rate limit
            log.warning("download attempt %d/%d failed: %s", attempt, attempts, exc)
            time.sleep(5 * attempt)
    return pd.DataFrame()


def fetch_bars(tickers: "list[str]", timeframe: str, now: pd.Timestamp) -> "tuple[dict[str, pd.DataFrame], list[str]]":
    """Return ({ticker: closed-bar frame}, [tickers that returned no usable data])."""
    shape = to_daily if timeframe == "1d" else to_four_hour
    bars, failed = {}, []
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i : i + BATCH_SIZE]
        raw = _download(chunk, timeframe, now)
        for ticker in chunk:
            try:
                sub = raw[ticker].dropna(how="all") if ticker in raw.columns.get_level_values(0) else None
                frame = shape(sub, now) if sub is not None and not sub.empty else None
            except Exception as exc:
                log.warning("%s %s: %s", ticker, timeframe, exc)
                frame = None
            if frame is None or frame.empty:
                failed.append(ticker)
            else:
                bars[ticker] = frame
    return bars, failed
```


- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_data.py`
Expected: 8 passed


- [ ] **Step 5: Live check against Yahoo (manual, needs internet)**

```bash
.venv/bin/python - <<'EOF'
import pandas as pd
from scanner.data import fetch_bars
now = pd.Timestamp.now(tz="UTC")
for tf in ("1d", "4h"):
    bars, failed = fetch_bars(["AAPL", "BRK-B", "ZZZZNOPE"], tf, now)
    print(tf, sorted(bars), failed, len(bars["AAPL"]))
EOF
```

Expected: `1d ['AAPL', 'BRK-B'] ['ZZZZNOPE'] ~500` and `4h ['AAPL', 'BRK-B'] ['ZZZZNOPE'] ~990`. The invalid ticker lands in the failed list; nothing crashes.


- [ ] **Step 6: Commit**

```bash
git add scanner
git commit -m "feat(scanner): fetch Yahoo bars, resample 1H to 4H, drop unfinished bars"
```



### Task 7: JSON export and run orchestrator

**Files:**
- Create: `scanner/export.py`, `scanner/run.py`
- Test: `scanner/tests/test_run.py`, `scanner/tests/test_smoke_network.py`

**Interfaces:**
- Consumes: Tasks 2-6: `STRATEGIES`, `Signal`, `SignalStore`, `SignalRecord`, `load_universe`, `fetch_bars`, `macd`, `rsi`, `ema`
- Produces: `run(out_dir, db_path, now=None, universe=None, fetch=fetch_bars, strategies=STRATEGIES) -> {hits, recorded}`, `ScanError`, CLI `python -m scanner.run --out DIR --db FILE` (exit 1 on `ScanError`); the JSON files described in Global Constraints. Signal rows: `ticker, name, sector, price, side, bars_ago, fired_at, bar_time, details, spark` (last 30 closes); `strategies.json` entries include `chart: {rsi_levels, macd_deep, emas}`; chart files: `ticker, timeframe, bars, macd{macd,signal,hist}, rsi, ema50, ema200, signals[{strategy_id, side, bar_time}]`

- [ ] **Step 1: Write the failing export/run tests**

Create `scanner/tests/test_run.py`:

```python
import json

import numpy as np
import pandas as pd
import pytest

from scanner.run import ScanError, run
from scanner.store import SignalStore
from scanner.strategies import STRATEGIES
from scanner.tests.conftest import make_df

NOW = pd.Timestamp("2026-10-02 21:00", tz="UTC")


def buy_closes():
    up = 100 * np.cumprod(1 + 0.001 + 0.002 * np.sin(np.arange(180)))
    down = up[-1] * np.cumprod(np.full(14, 0.98))
    return list(np.concatenate([up, down, [down[-1] * 1.06]]))


UNIVERSE = pd.DataFrame({
    "ticker": ["AAA", "BBB", "CCC"],
    "name": ["Alpha", "Beta", "Gamma"],
    "sector": ["Tech", "Tech", "Energy"],
})


def fake_fetch(tickers, timeframe, now):
    bars = {"AAA": make_df(buy_closes()), "BBB": make_df([100.0] * 300), "CCC": make_df([100.0] * 300)}
    return bars, []


def test_run_writes_json_and_records_signals(tmp_path):
    out, db = tmp_path / "data", tmp_path / "signals.db"
    result = run(out, db, now=NOW, universe=UNIVERSE, fetch=fake_fetch)
    assert result["hits"] == 2  # AAA flagged on 4h and 1d by the MACD+RSI strategy
    summary = json.loads((out / "strategies.json").read_text())
    s1 = next(s for s in summary["strategies"] if s["id"] == "macd-rsi-reversal")
    assert s1["timeframes"]["1d"] == {"buy": 1, "sell": 0}
    rows = json.loads((out / "macd-rsi-reversal" / "1d.json").read_text())["signals"]
    assert [r["ticker"] for r in rows] == ["AAA"]
    assert rows[0]["name"] == "Alpha" and rows[0]["side"] == "BUY" and rows[0]["bars_ago"] == 0
    assert len(rows[0]["spark"]) == 30 and rows[0]["spark"][-1] == rows[0]["price"]
    assert s1["chart"] == {"rsi_levels": [20, 80], "macd_deep": True, "emas": False}
    chart = json.loads((out / "charts" / "1d" / "AAA.json").read_text())
    assert len(chart["bars"]) == len(chart["rsi"]) == len(chart["macd"]["hist"]) == 195  # all bars, under the 250 cap
    assert chart["signals"][0]["side"] == "BUY"
    assert not (out / "charts" / "1d" / "BBB.json").exists()  # only flagged tickers get charts
    assert SignalStore(db).count() == 2


def test_rerun_does_not_duplicate_history(tmp_path):
    out, db = tmp_path / "data", tmp_path / "signals.db"
    run(out, db, now=NOW, universe=UNIVERSE, fetch=fake_fetch)
    second = run(out, db, now=NOW + pd.Timedelta(hours=1), universe=UNIVERSE, fetch=fake_fetch)
    assert second["recorded"] == 0
    assert SignalStore(db).count() == 2


def test_no_signals_still_writes_valid_empty_files(tmp_path):
    out = tmp_path / "data"
    flat = lambda t, tf, n: ({"AAA": make_df([100.0] * 300)}, [])  # noqa: E731
    run(out, tmp_path / "s.db", now=NOW, universe=UNIVERSE.iloc[:1], fetch=flat)
    for strat in STRATEGIES:
        for tf in ("4h", "1d"):
            assert json.loads((out / strat.id / f"{tf}.json").read_text())["signals"] == []
    assert not (out / "charts").exists()


def test_too_many_failed_tickers_aborts_before_writing(tmp_path):
    out = tmp_path / "data"
    failing = lambda t, tf, n: ({}, list(t))  # noqa: E731
    with pytest.raises(ScanError):
        run(out, tmp_path / "s.db", now=NOW, universe=UNIVERSE, fetch=failing)
    assert not out.exists()


def test_chart_is_capped_at_250_bars(tmp_path):
    long_buy = [100.0] * 100 + buy_closes()  # 295 bars, ends on the BUY bounce
    fetch = lambda t, tf, n: ({"AAA": make_df(long_buy)}, [])  # noqa: E731
    run(tmp_path / "data", tmp_path / "s.db", now=NOW, universe=UNIVERSE.iloc[:1], fetch=fetch)
    chart = json.loads((tmp_path / "data" / "charts" / "1d" / "AAA.json").read_text())
    assert len(chart["bars"]) == 250
```

These pin Review Focus items 4 and 5: zero signals still write valid empty files, and reruns never duplicate history. Also create the opt-in live smoke test:

Create `scanner/tests/test_smoke_network.py`:

```python
"""End-to-end check against live Yahoo data. Skipped unless RUN_NETWORK=1."""
import json
import os

import pandas as pd
import pytest

from scanner.run import run

pytestmark = pytest.mark.skipif(not os.environ.get("RUN_NETWORK"), reason="set RUN_NETWORK=1 to hit Yahoo")


def test_scan_five_real_tickers(tmp_path):
    universe = pd.DataFrame({
        "ticker": ["AAPL", "MSFT", "XOM", "JPM", "BRK-B"],
        "name": ["Apple", "Microsoft", "Exxon", "JPMorgan", "Berkshire"],
        "sector": ["IT", "IT", "Energy", "Financials", "Financials"],
    })
    out = tmp_path / "data"
    run(out, tmp_path / "signals.db", universe=universe)
    summary = json.loads((out / "strategies.json").read_text())
    assert [s["id"] for s in summary["strategies"]] == ["macd-rsi-reversal", "trend-pullback"]
    for strategy in summary["strategies"]:
        for tf in ("4h", "1d"):
            data = json.loads((out / strategy["id"] / f"{tf}.json").read_text())
            assert isinstance(data["signals"], list)
```


- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest -q scanner/tests/test_run.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scanner.run'`


- [ ] **Step 3: Implement the exporters and the run orchestrator**

Create `scanner/export.py`:

```python
"""Write the JSON files the website reads."""
import json
import math
from pathlib import Path

import pandas as pd

from scanner.indicators import ema, macd, rsi

CHART_BARS = 250


def unix(ts: pd.Timestamp) -> int:
    return int(ts.timestamp())


def _num(value) -> "float | None":
    return None if value is None or pd.isna(value) or math.isinf(value) else round(float(value), 4)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, allow_nan=False, separators=(",", ":")))


SPARK_BARS = 30


def signal_row(ticker: str, name: str, sector: str, sig, closes: pd.Series) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "price": round(sig.entry_price, 4),
        "side": sig.side,
        "bars_ago": sig.bars_ago,
        "fired_at": sig.fired_at.isoformat(),
        "bar_time": unix(sig.bar_time),
        "details": sig.details,
        "spark": [_num(v) for v in closes.iloc[-SPARK_BARS:]],
    }


def chart_payload(ticker: str, timeframe: str, df: pd.DataFrame, signals: "list[dict]") -> dict:
    close = df["close"]
    m = macd(close)
    series = {
        "macd": m["macd"], "signal": m["signal"], "hist": m["hist"],
        "rsi": rsi(close), "ema50": ema(close, 50), "ema200": ema(close, 200),
    }
    tail = df.iloc[-CHART_BARS:]
    take = lambda s: [_num(v) for v in s.iloc[-CHART_BARS:]]  # noqa: E731
    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "bars": [
            [unix(ts), _num(r.open), _num(r.high), _num(r.low), _num(r.close), _num(r.volume)]
            for ts, r in zip(tail.index, tail.itertuples())
        ],
        "macd": {"macd": take(series["macd"]), "signal": take(series["signal"]), "hist": take(series["hist"])},
        "rsi": take(series["rsi"]),
        "ema50": take(series["ema50"]),
        "ema200": take(series["ema200"]),
        "signals": signals,
    }
```

Create `scanner/run.py`:

```python
"""Scan the S&P 500, write site JSON, record signals. Usage: python -m scanner.run --out DIR --db FILE"""
import argparse
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scanner.data import fetch_bars
from scanner.export import chart_payload, signal_row, write_json
from scanner.store import SignalRecord, SignalStore
from scanner.strategies import STRATEGIES
from scanner.strategies.base import Signal
from scanner.universe import load_universe

TIMEFRAMES = ("4h", "1d")
MAX_FAILURE_RATE = 0.10

log = logging.getLogger("scanner")


class ScanError(RuntimeError):
    pass


@dataclass(frozen=True)
class Hit:
    strategy_id: str
    timeframe: str
    ticker: str
    signal: Signal


def scan(bars_by_tf: dict, strategies) -> "list[Hit]":
    hits = []
    for tf, bars in bars_by_tf.items():
        for ticker, df in bars.items():
            for strat in strategies:
                try:
                    sig = strat.evaluate(df)
                except Exception:
                    log.exception("%s failed on %s %s", strat.id, ticker, tf)
                    continue
                if sig:
                    hits.append(Hit(strat.id, tf, ticker, sig))
    return hits


def run(out_dir: Path, db_path: Path, now: "pd.Timestamp | None" = None,
        universe: "pd.DataFrame | None" = None, fetch=fetch_bars, strategies=STRATEGIES) -> dict:
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    universe = universe if universe is not None else load_universe()
    tickers = universe["ticker"].tolist()
    meta = universe.set_index("ticker")

    bars_by_tf = {}
    for tf in TIMEFRAMES:
        bars_by_tf[tf], failed = fetch(tickers, tf, now)
        log.info("%s: %d fetched, %d failed", tf, len(bars_by_tf[tf]), len(failed))
        if len(failed) / len(tickers) > MAX_FAILURE_RATE:
            raise ScanError(f"{len(failed)}/{len(tickers)} tickers failed for {tf}")

    hits = scan(bars_by_tf, strategies)
    updated_at = now.isoformat()

    shutil.rmtree(out_dir, ignore_errors=True)
    summaries = []
    for strat in strategies:
        counts = {}
        for tf in TIMEFRAMES:
            rows = [
                signal_row(h.ticker, meta.at[h.ticker, "name"], meta.at[h.ticker, "sector"], h.signal,
                           bars_by_tf[tf][h.ticker]["close"])
                for h in hits if h.strategy_id == strat.id and h.timeframe == tf
            ]
            rows.sort(key=lambda r: (r["bars_ago"], r["ticker"]))
            write_json(out_dir / strat.id / f"{tf}.json", {"updated_at": updated_at, "signals": rows})
            counts[tf] = {
                "buy": sum(r["side"] == "BUY" for r in rows),
                "sell": sum(r["side"] == "SELL" for r in rows),
            }
        summaries.append({"id": strat.id, "name": strat.name, "description": strat.description,
                          "chart": strat.chart, "timeframes": counts})
    write_json(out_dir / "strategies.json", {"updated_at": updated_at, "strategies": summaries})

    flagged = {(h.timeframe, h.ticker) for h in hits}
    for tf, ticker in sorted(flagged):
        marks = [
            {"strategy_id": h.strategy_id, "side": h.signal.side, "bar_time": int(h.signal.bar_time.timestamp())}
            for h in hits if h.timeframe == tf and h.ticker == ticker
        ]
        write_json(out_dir / "charts" / tf / f"{ticker}.json", chart_payload(ticker, tf, bars_by_tf[tf][ticker], marks))

    store = SignalStore(db_path)
    inserted = store.record_signals([
        SignalRecord(h.strategy_id, h.ticker, h.timeframe, h.signal.side, h.signal.fired_at.isoformat(),
                     h.signal.entry_price, h.signal.details, updated_at)
        for h in hits
    ])
    store.close()
    log.info("%d signals found, %d new recorded", len(hits), inserted)
    return {"hits": len(hits), "recorded": inserted}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(args.out, args.db)
    except ScanError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```


- [ ] **Step 4: Run the whole scanner suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (48 passed; the smoke test is skipped without RUN_NETWORK)

Then the live smoke test and a bigger real run (needs internet):

```bash
RUN_NETWORK=1 .venv/bin/python -m pytest -q scanner/tests/test_smoke_network.py
.venv/bin/python -m scanner.run --out .scratch/data --db .scratch/signals.db
```

Expected: the smoke test passes; the full run logs `4h: ~500 fetched` and `1d: ~500 fetched` with few failures and finishes in a few minutes. Then `rm -rf .scratch`.


- [ ] **Step 5: Commit**

```bash
git add scanner
git commit -m "feat(scanner): JSON export, run orchestrator, failure threshold"
```



### Task 8: Web scaffold and pure logic

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`, `web/src/test-setup.ts`, `web/src/types.ts`, `web/src/api.ts`, `web/src/lib/filters.ts`, `web/src/lib/stats.ts`, `web/src/lib/chartData.ts`, `web/src/test-fixtures.ts`
- Test: `web/src/lib/filters.test.ts`, `web/src/lib/stats.test.ts`, `web/src/lib/chartData.test.ts`

**Interfaces:**
- Consumes: the JSON contract from Task 7
- Produces: types (`Timeframe`, `Side`, `ChartConfig`, `StrategySummary`, `StrategiesFile`, `SignalRow`, `SignalsFile`, `ChartFile`); `getJson`, `getStrategies()`, `getSignals(id, tf)`, `getChart(tf, ticker)`; `filterSignals(rows, filters)`, `sectorsOf(rows)`, `barsAgoLabel(n)`, `isStale(updatedAt, now, hours=36)`, `DEFAULT_FILTERS`, `ALL_SECTORS`; `quantile(values, q)`; `buildChartData(chart, config, strategyId) -> BuiltChart`, `COLORS`; test helpers `strategies`, `signals`, `chart`, `stubFetch(fail?, overrides?)`

- [ ] **Step 1: Scaffold the web project**

```bash
mkdir -p web/src/{components,pages,lib} web/public
cd web
```

Create `web/package.json`:

```json
{
  "name": "multi-strategy-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run",
    "preview": "vite preview"
  }
}
```

Then install (this writes the dependency versions and `package-lock.json`; commit both):

```bash
npm i react react-dom react-router-dom lightweight-charts
npm i -D vite @vitejs/plugin-react typescript vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @types/react @types/react-dom @types/node
```

Verified with: lightweight-charts 5.2, react 19.3, react-router-dom 7.18, vite 8.3, vitest 5.0, typescript 7.0, @vitejs/plugin-react 6.1. These APIs are version-sensitive: if a later major breaks a block, pin to these versions.

Create `web/vite.config.ts`:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Pages serves the site under /<repo>/. Override with VITE_BASE for a custom domain or org site.
  base: process.env.VITE_BASE ?? "/ns-multi-stratt/",
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test-setup.ts" },
});
```

Create `web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "noEmit": true,
    "types": ["node", "vite/client", "vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

Create `web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Multi Strategy</title>
    <meta name="description" content="S&P 500 strategy signals on the Daily and 4H charts." />
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='9' fill='%23CC785C'/%3E%3C/svg%3E" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Lora:wght@500;600&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `web/src/test-setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

Create `web/src/types.ts`:

```typescript
export type Timeframe = "1d" | "4h";
export type Side = "BUY" | "SELL";

export interface ChartConfig {
  rsi_levels: [number, number];
  macd_deep: boolean;
  emas: boolean;
}

export interface StrategySummary {
  id: string;
  name: string;
  description: string;
  chart: ChartConfig;
  timeframes: Record<Timeframe, { buy: number; sell: number }>;
}

export interface StrategiesFile {
  updated_at: string;
  strategies: StrategySummary[];
}

export interface SignalRow {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  side: Side;
  bars_ago: number;
  fired_at: string;
  bar_time: number;
  details: Record<string, number>;
  spark: (number | null)[];
}

export interface SignalsFile {
  updated_at: string;
  signals: SignalRow[];
}

export interface ChartFile {
  ticker: string;
  timeframe: Timeframe;
  /** [unix seconds, open, high, low, close, volume] */
  bars: [number, number, number, number, number, number][];
  macd: { macd: (number | null)[]; signal: (number | null)[]; hist: (number | null)[] };
  rsi: (number | null)[];
  ema50: (number | null)[];
  ema200: (number | null)[];
  signals: { strategy_id: string; side: Side; bar_time: number }[];
}
```


- [ ] **Step 2: Write the failing logic tests**

Create `web/src/test-fixtures.ts`:

```typescript
import type { ChartFile, SignalRow, SignalsFile, StrategiesFile } from "./types";

export const UPDATED = new Date().toISOString();

export const strategies: StrategiesFile = {
  updated_at: UPDATED,
  strategies: [
    {
      id: "macd-rsi-reversal",
      name: "MACD + RSI Reversal",
      description: "Histogram climbs from a deep low while RSI crosses back above 20.",
      chart: { rsi_levels: [20, 80], macd_deep: true, emas: false },
      timeframes: { "1d": { buy: 1, sell: 1 }, "4h": { buy: 1, sell: 0 } },
    },
    {
      id: "trend-pullback",
      name: "Trend Pullback",
      description: "Pullback in an established trend.",
      chart: { rsi_levels: [40, 60], macd_deep: false, emas: true },
      timeframes: { "1d": { buy: 0, sell: 0 }, "4h": { buy: 0, sell: 0 } },
    },
  ],
};

const row = (over: Partial<SignalRow>): SignalRow => ({
  ticker: "XOM", name: "Exxon Mobil", sector: "Energy", price: 108.42, side: "BUY", bars_ago: 0,
  fired_at: "2026-10-02T20:00:00+00:00", bar_time: 1790899200, details: {}, spark: [1, 2, 3, 2, 3],
  ...over,
});

export const signals: Record<string, SignalsFile> = {
  "macd-rsi-reversal/1d.json": {
    updated_at: UPDATED,
    signals: [row({}), row({ ticker: "NVDA", name: "NVIDIA", sector: "Information Technology", side: "SELL", bars_ago: 1 })],
  },
  "macd-rsi-reversal/4h.json": { updated_at: UPDATED, signals: [row({ ticker: "AAL", name: "American Airlines", sector: "Industrials" })] },
  "trend-pullback/1d.json": { updated_at: UPDATED, signals: [] },
  "trend-pullback/4h.json": { updated_at: UPDATED, signals: [] },
};

export const chart: ChartFile = {
  ticker: "XOM", timeframe: "1d",
  bars: [[1, 10, 12, 9, 11, 100], [2, 11, 13, 10, 12, 100], [3, 12, 14, 11, 13, 100]],
  macd: { macd: [null, 0.1, 0.2], signal: [null, 0.05, 0.1], hist: [null, 0.05, 0.1] },
  rsi: [null, 40, 45], ema50: [10, 11, 12], ema200: [9, 9, 9],
  signals: [{ strategy_id: "macd-rsi-reversal", side: "BUY", bar_time: 3 }],
};

/** fetch stub serving the fixtures; any key in `fail` returns HTTP 500. */
export function stubFetch(fail: string[] = [], overrides: Record<string, unknown> = {}) {
  const table: Record<string, unknown> = { "strategies.json": strategies, "charts/1d/XOM.json": chart, ...signals, ...overrides };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const key = Object.keys(table).find((k) => url.endsWith(`data/${k}`));
      if (!key || fail.includes(key)) return new Response("nope", { status: 500 });
      return new Response(JSON.stringify(table[key]), { status: 200 });
    }),
  );
}
```

Create `web/src/lib/filters.test.ts`:

```typescript
import { signals } from "../test-fixtures";
import { ALL_SECTORS, DEFAULT_FILTERS, barsAgoLabel, filterSignals, isStale, sectorsOf } from "./filters";

const rows = signals["macd-rsi-reversal/1d.json"].signals;

describe("filterSignals", () => {
  it("returns everything by default", () => {
    expect(filterSignals(rows, DEFAULT_FILTERS)).toHaveLength(2);
  });
  it("filters by side, sector and query (ticker or name, case-insensitive)", () => {
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, side: "SELL" }).map((r) => r.ticker)).toEqual(["NVDA"]);
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, sector: "Energy" }).map((r) => r.ticker)).toEqual(["XOM"]);
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, query: " exxon " }).map((r) => r.ticker)).toEqual(["XOM"]);
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, query: "nv" }).map((r) => r.ticker)).toEqual(["NVDA"]);
  });
  it("returns an empty list when nothing matches", () => {
    expect(filterSignals(rows, { ...DEFAULT_FILTERS, query: "zzz" })).toEqual([]);
  });
});

it("sectorsOf lists unique sectors alphabetically after 'All sectors'", () => {
  expect(sectorsOf(rows)).toEqual([ALL_SECTORS, "Energy", "Information Technology"]);
  expect(sectorsOf([])).toEqual([ALL_SECTORS]);
});

it("barsAgoLabel", () => {
  expect(barsAgoLabel(0)).toBe("Latest bar");
  expect(barsAgoLabel(1)).toBe("1 bar ago");
  expect(barsAgoLabel(2)).toBe("2 bars ago");
});

it("isStale is true only after 36 hours", () => {
  const now = new Date("2026-10-03T12:00:00Z");
  expect(isStale("2026-10-02T12:00:00Z", now)).toBe(false);
  expect(isStale("2026-10-01T23:00:00Z", now)).toBe(true);
});
```

Create `web/src/lib/stats.test.ts`:

```typescript
import { quantile } from "./stats";

it("interpolates linearly like pandas", () => {
  expect(quantile([1, 2, 3, 4, 5], 0.5)).toBe(3);
  expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5);
  expect(quantile([0, 10], 0.1)).toBeCloseTo(1);
  expect(quantile([5], 0.9)).toBe(5);
});
```

Create `web/src/lib/chartData.test.ts`:

```typescript
import { chart } from "../test-fixtures";
import type { ChartFile } from "../types";
import { COLORS, buildChartData } from "./chartData";

const macdCfg = { rsi_levels: [20, 80] as [number, number], macd_deep: true, emas: false };
const trendCfg = { rsi_levels: [40, 60] as [number, number], macd_deep: false, emas: true };

it("drops null points and keeps candle times", () => {
  const b = buildChartData(chart, macdCfg, "macd-rsi-reversal");
  expect(b.candles.map((c) => c.time)).toEqual([1, 2, 3]);
  expect(b.rsi).toEqual([{ time: 2, value: 40 }, { time: 3, value: 45 }]);
  expect(b.macd).toHaveLength(2);
});

it("puts a BUY arrow below the signal candle and a SELL arrow above it, only for this strategy", () => {
  const two: ChartFile = {
    ...chart,
    signals: [
      { strategy_id: "macd-rsi-reversal", side: "BUY", bar_time: 3 },
      { strategy_id: "trend-pullback", side: "SELL", bar_time: 2 },
    ],
  };
  const mine = buildChartData(two, macdCfg, "macd-rsi-reversal").markers;
  expect(mine).toEqual([{ time: 3, position: "belowBar", shape: "arrowUp", color: COLORS.up, text: "BUY" }]);
  const other = buildChartData(two, trendCfg, "trend-pullback").markers;
  expect(other).toEqual([{ time: 2, position: "aboveBar", shape: "arrowDown", color: COLORS.down, text: "SELL" }]);
});

it("colours the histogram in four shades", () => {
  const c: ChartFile = { ...chart, macd: { ...chart.macd, hist: [1, 2, 1, -1, -2, -1] }, bars: Array.from({ length: 6 }, (_, i) => [i + 1, 1, 1, 1, 1, 1]) };
  const colors = buildChartData(c, macdCfg, "x").hist.map((h) => h.color);
  // first bar has no previous value (treated as rising); then: grow, shrink, drop below zero, deepen, shrink
  expect(colors).toEqual([COLORS.up, COLORS.up, COLORS.upLight, COLORS.down, COLORS.down, COLORS.downLight]);
});

it("shows the deep thresholds only for strategies that ask for them (needs 20+ recent values)", () => {
  const n = 120;
  const long: ChartFile = {
    ...chart,
    bars: Array.from({ length: n }, (_, i) => [i + 1, 1, 1, 1, 1, 1]),
    macd: { macd: Array(n).fill(0), signal: Array(n).fill(0), hist: Array.from({ length: n }, (_, i) => i - 60) },
    rsi: Array(n).fill(50), ema50: Array(n).fill(1), ema200: Array(n).fill(1),
  };
  const on = buildChartData(long, macdCfg, "x");
  expect(on.deepLow).toBeLessThan(on.deepHigh!);
  expect(buildChartData(long, trendCfg, "x").deepLow).toBeNull();
  expect(buildChartData(chart, macdCfg, "x").deepLow).toBeNull(); // only 2 valid hist values
});

it("includes EMAs only when the strategy config asks for them, and carries RSI levels", () => {
  expect(buildChartData(chart, macdCfg, "x").ema50).toEqual([]);
  expect(buildChartData(chart, trendCfg, "x").ema50).toHaveLength(3);
  expect(buildChartData(chart, trendCfg, "x").rsiLevels).toEqual([40, 60]);
});
```


- [ ] **Step 3: Run to verify failure**

Run: `cd web && npx vitest run`
Expected: FAIL, cannot resolve `./filters`, `./stats`, `./chartData`


- [ ] **Step 4: Implement the logic modules and API client**

Create `web/src/lib/filters.ts`:

```typescript
import type { Side, SignalRow } from "../types";

export const ALL_SECTORS = "All sectors";

export interface Filters {
  side: "ALL" | Side;
  sector: string;
  query: string;
}

export const DEFAULT_FILTERS: Filters = { side: "ALL", sector: ALL_SECTORS, query: "" };

export function filterSignals(rows: SignalRow[], f: Filters): SignalRow[] {
  const q = f.query.trim().toLowerCase();
  return rows.filter(
    (r) =>
      (f.side === "ALL" || r.side === f.side) &&
      (f.sector === ALL_SECTORS || r.sector === f.sector) &&
      (q === "" || r.ticker.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)),
  );
}

export function sectorsOf(rows: SignalRow[]): string[] {
  return [ALL_SECTORS, ...[...new Set(rows.map((r) => r.sector))].sort()];
}

export function barsAgoLabel(n: number): string {
  return n === 0 ? "Latest bar" : `${n} bar${n === 1 ? "" : "s"} ago`;
}

export function isStale(updatedAt: string, now: Date, hours = 36): boolean {
  return now.getTime() - new Date(updatedAt).getTime() > hours * 3_600_000;
}
```

Create `web/src/lib/stats.ts`:

```typescript
/** Quantile with linear interpolation (matches pandas' default). */
export function quantile(values: number[], q: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
```

Create `web/src/lib/chartData.ts`:

```typescript
import type { UTCTimestamp } from "lightweight-charts";
import type { ChartConfig, ChartFile, Side } from "../types";
import { quantile } from "./stats";

export const COLORS = {
  up: "#27694B",
  upLight: "rgba(39,105,75,0.38)",
  down: "#9E2F45",
  downLight: "rgba(158,47,69,0.38)",
  accent: "#A5472A",
  rsi: "#6B4FA3",
  macd: "#2F5D8A",
  signal: "#C98A2B",
  ema50: "#C98A2B",
  ema200: "#2F5D8A",
};

type Point = { time: UTCTimestamp; value: number };

const t = (s: number) => s as UTCTimestamp;

function line(times: number[], values: (number | null)[]): Point[] {
  const out: Point[] = [];
  values.forEach((v, i) => {
    if (v !== null) out.push({ time: t(times[i]), value: v });
  });
  return out;
}

export interface BuiltChart {
  candles: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[];
  rsi: Point[];
  macd: Point[];
  signal: Point[];
  hist: (Point & { color: string })[];
  ema50: Point[];
  ema200: Point[];
  markers: { time: UTCTimestamp; position: "aboveBar" | "belowBar"; shape: "arrowUp" | "arrowDown"; color: string; text: Side }[];
  deepLow: number | null;
  deepHigh: number | null;
  rsiLevels: [number, number];
  showEmas: boolean;
}

/** Turn the scanner's chart JSON into ready-to-draw series. Pure, so it is unit-tested. */
export function buildChartData(chart: ChartFile, config: ChartConfig, strategyId: string): BuiltChart {
  const times = chart.bars.map((b) => b[0]);
  const histValues = chart.macd.hist;
  const hist = histValues.flatMap((v, i) => {
    if (v === null) return [];
    const prev = i > 0 ? histValues[i - 1] : null;
    const rising = prev === null || v > prev;
    // Four shades: strong when the bar is growing away from zero, light when it is shrinking.
    const color = v >= 0 ? (rising ? COLORS.up : COLORS.upLight) : rising ? COLORS.downLight : COLORS.down;
    return [{ time: t(times[i]), value: v, color }];
  });
  const recent = histValues.slice(-100).filter((v): v is number => v !== null);
  const deep = config.macd_deep && recent.length >= 20;

  return {
    candles: chart.bars.map(([time, open, high, low, close]) => ({ time: t(time), open, high, low, close })),
    rsi: line(times, chart.rsi),
    macd: line(times, chart.macd.macd),
    signal: line(times, chart.macd.signal),
    hist,
    ema50: config.emas ? line(times, chart.ema50) : [],
    ema200: config.emas ? line(times, chart.ema200) : [],
    markers: chart.signals
      .filter((s) => s.strategy_id === strategyId)
      .map((s) => ({
        time: t(s.bar_time),
        position: s.side === "BUY" ? ("belowBar" as const) : ("aboveBar" as const),
        shape: s.side === "BUY" ? ("arrowUp" as const) : ("arrowDown" as const),
        color: s.side === "BUY" ? COLORS.up : COLORS.down,
        text: s.side,
      })),
    deepLow: deep ? quantile(recent, 0.1) : null,
    deepHigh: deep ? quantile(recent, 0.9) : null,
    rsiLevels: config.rsi_levels,
    showEmas: config.emas,
  };
}
```

Create `web/src/api.ts`:

```typescript
import type { ChartFile, SignalsFile, StrategiesFile, Timeframe } from "./types";

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${path}`);
  if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
  return (await res.json()) as T;
}

export const getStrategies = () => getJson<StrategiesFile>("strategies.json");
export const getSignals = (strategyId: string, tf: Timeframe) => getJson<SignalsFile>(`${strategyId}/${tf}.json`);
export const getChart = (tf: Timeframe, ticker: string) => getJson<ChartFile>(`charts/${tf}/${ticker}.json`);
```


- [ ] **Step 5: Run to verify pass**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: 3 test files, all pass; `tsc` prints nothing


- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "feat(web): scaffold, types, filters, chart data builder"
```



### Task 9: Hooks and presentational components

**Files:**
- Create: `web/src/hooks.ts`, `web/src/strategiesContext.tsx`, `web/src/components/{SignalPill,TimeframeToggle,TopBar,Feedback,Sparkline,StockCard}.tsx`

**Interfaces:**
- Consumes: Task 8: types, api, `barsAgoLabel`
- Produces: `useAsync(load, deps) -> {data, error, loading, retry}`; `useTimeframe() -> [tf, setTf]` (URL `?tf=`, default `1d`); `StrategiesProvider`, `useStrategies()`; `SignalPill`, `TimeframeToggle`, `TopBar`, `Loading`, `ErrorState`, `StaleBanner`, `Sparkline`, `StockCard`

- [ ] **Step 1: Create the hooks and shared context**

Create `web/src/hooks.ts`:

```typescript
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Timeframe } from "./types";

export interface AsyncState<T> {
  data?: T;
  error?: Error;
  loading: boolean;
  retry: () => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setState({ loading: true });
    load()
      .then((data) => alive && setState({ data, loading: false }))
      .catch((error: Error) => alive && setState({ error, loading: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  return { ...state, retry };
}

/** Global timeframe, kept in the URL (?tf=4h) so links are shareable. Defaults to 1D. */
export function useTimeframe(): [Timeframe, (tf: Timeframe) => void] {
  const [params, setParams] = useSearchParams();
  const tf: Timeframe = params.get("tf") === "4h" ? "4h" : "1d";
  const setTf = (next: Timeframe) => {
    const p = new URLSearchParams(params);
    if (next === "1d") p.delete("tf");
    else p.set("tf", next);
    setParams(p, { replace: true });
  };
  return [tf, setTf];
}
```

Create `web/src/strategiesContext.tsx`:

```tsx
import { createContext, useContext, type ReactNode } from "react";
import { getStrategies } from "./api";
import { useAsync, type AsyncState } from "./hooks";
import type { StrategiesFile } from "./types";

const Ctx = createContext<AsyncState<StrategiesFile> | null>(null);

export function StrategiesProvider({ children }: { children: ReactNode }) {
  const state = useAsync(getStrategies, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export function useStrategies(): AsyncState<StrategiesFile> {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStrategies must be used inside StrategiesProvider");
  return v;
}
```


- [ ] **Step 2: Create the small components**

Create `web/src/components/SignalPill.tsx`:

```tsx
import type { Side } from "../types";

export function SignalPill({ side }: { side: Side }) {
  return (
    <span className={`pill ${side === "BUY" ? "buy" : "sell"}`}>
      <svg viewBox="0 0 12 12" aria-hidden="true">
        <path d={side === "BUY" ? "M6 2l4 5H2z" : "M6 10L2 5h8z"} fill="currentColor" />
      </svg>
      {side}
    </span>
  );
}
```

Create `web/src/components/TimeframeToggle.tsx`:

```tsx
import { useTimeframe } from "../hooks";

export function TimeframeToggle() {
  const [tf, setTf] = useTimeframe();
  return (
    <div className="seg" role="group" aria-label="Timeframe">
      <button type="button" aria-pressed={tf === "1d"} onClick={() => setTf("1d")}>1D</button>
      <button type="button" aria-pressed={tf === "4h"} onClick={() => setTf("4h")}>4H</button>
    </div>
  );
}
```

Create `web/src/components/TopBar.tsx`:

```tsx
import { NavLink, useLocation } from "react-router-dom";
import { useStrategies } from "../strategiesContext";
import { TimeframeToggle } from "./TimeframeToggle";

export function TopBar() {
  const { data } = useStrategies();
  const { search } = useLocation(); // keep ?tf= when navigating
  return (
    <header className="top">
      <NavLink to={{ pathname: "/", search }} className="brand">Multi Strategy</NavLink>
      <nav aria-label="Primary" className="pillnav">
        <NavLink to={{ pathname: "/", search }} end>Home</NavLink>
        {data?.strategies.map((s) => (
          <NavLink key={s.id} to={{ pathname: `/strategy/${s.id}`, search }}>{s.name}</NavLink>
        ))}
      </nav>
      <TimeframeToggle />
    </header>
  );
}
```

Create `web/src/components/Feedback.tsx`:

```tsx
export function Loading({ what }: { what: string }) {
  return <p className="muted center" role="status">Loading {what}…</p>;
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="errorbox" role="alert">
      <p><strong>Something went wrong.</strong> {error.message}</p>
      <button type="button" className="btn" onClick={onRetry}>Try again</button>
    </div>
  );
}

export function StaleBanner() {
  return (
    <div className="stale" role="status">
      The data looks out of date (last update was over 36 hours ago). The scanner may have paused.
    </div>
  );
}
```

Create `web/src/components/Sparkline.tsx`:

```tsx
export function Sparkline({ values, color }: { values: (number | null)[]; color: string }) {
  const v = values.filter((x): x is number => x !== null);
  if (v.length < 2) return <div className="spark" />;
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const pts = v.map((x, i) => `${((i * 100) / (v.length - 1)).toFixed(1)},${(34 - ((x - lo) / (hi - lo || 1)) * 32).toFixed(1)}`).join(" ");
  return (
    <svg className="spark" viewBox="0 0 100 36" preserveAspectRatio="none" aria-hidden="true">
      <polyline fill="none" stroke={color} strokeWidth="2" points={pts} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
```

Create `web/src/components/StockCard.tsx`:

```tsx
import { barsAgoLabel } from "../lib/filters";
import type { SignalRow } from "../types";
import { Sparkline } from "./Sparkline";
import { SignalPill } from "./SignalPill";

export function StockCard({ row, onOpen }: { row: SignalRow; onOpen: (row: SignalRow) => void }) {
  return (
    <button type="button" className="scard" onClick={() => onOpen(row)} title={`Fired ${new Date(row.fired_at).toLocaleString()}`}>
      <span className="row between">
        <span className="tk">{row.ticker}</span>
        <SignalPill side={row.side} />
      </span>
      <span className="tag">{row.name}</span>
      <Sparkline values={row.spark} color={row.side === "BUY" ? "#27694B" : "#9E2F45"} />
      <span className="row between">
        <span className="num"><strong>${row.price.toFixed(2)}</strong></span>
        <span className="tag">{barsAgoLabel(row.bars_ago)}</span>
      </span>
    </button>
  );
}
```


- [ ] **Step 3: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: no output (these files are exercised by the App tests in Task 11)


- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "feat(web): hooks, strategies context, top bar and card components"
```



### Task 10: Chart view and modal

**Files:**
- Create: `web/src/components/ChartView.tsx`, `web/src/components/ChartModal.tsx`

**Interfaces:**
- Consumes: Task 8: `buildChartData`, `COLORS`, `getChart`; Task 9: `useAsync`, `Loading`, `ErrorState`, `SignalPill`
- Produces: `ChartView({data, config, strategyId})` (3 panes: price + marker + optional EMAs; RSI with strategy levels; MACD with zero line and optional deep thresholds), `ChartModal({row, tf, strategyId, config, onClose})` (Esc and backdrop close, restores focus)

- [ ] **Step 1: Create the chart and the modal**

Create `web/src/components/ChartView.tsx`:

```tsx
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import { COLORS, buildChartData } from "../lib/chartData";
import type { ChartConfig, ChartFile } from "../types";

const ET = "America/New_York";
const dayFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const tickFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const etFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ET });

interface Props {
  data: ChartFile;
  config: ChartConfig;
  strategyId: string;
}

/** TradingView-style chart: candles + signal marker, RSI pane with strategy levels, MACD pane. */
export function ChartView({ data, config, strategyId }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const b = buildChartData(data, config, strategyId);
    const intraday = data.timeframe === "4h";
    const toMs = (t: UTCTimestamp) => (t as number) * 1000;

    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#FFFFFF" }, textColor: "#625C55", fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, panes: { separatorColor: "#EFE6DB" } },
      grid: { vertLines: { color: "#F3EBE0" }, horzLines: { color: "#F3EBE0" } },
      rightPriceScale: { borderVisible: false },
      timeScale: {
        borderVisible: false,
        timeVisible: intraday,
        tickMarkFormatter: (t: UTCTimestamp) => (intraday ? etFmt : tickFmt).format(toMs(t)),
      },
      localization: { timeFormatter: (t: UTCTimestamp) => (intraday ? etFmt : dayFmt).format(toMs(t)) },
    });

    // Pane 0: price
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up, borderUpColor: COLORS.up, wickUpColor: COLORS.up,
      downColor: "#FFFFFF", borderDownColor: COLORS.down, wickDownColor: COLORS.down, // hollow = down bar
    }, 0);
    candles.setData(b.candles);
    createSeriesMarkers(candles, b.markers);
    if (b.showEmas) {
      chart.addSeries(LineSeries, { color: COLORS.ema50, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "EMA 50" }, 0).setData(b.ema50);
      chart.addSeries(LineSeries, { color: COLORS.ema200, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "EMA 200" }, 0).setData(b.ema200);
    }

    // Pane 1: RSI with the strategy's own levels (solid, labelled) plus faint 30/50/70 references
    const rsi = chart.addSeries(LineSeries, { color: COLORS.rsi, lineWidth: 2, priceLineVisible: false, title: "RSI 14" }, 1);
    rsi.setData(b.rsi);
    [30, 50, 70].forEach((price) =>
      rsi.createPriceLine({ price, color: "#E0D6C8", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: "" }),
    );
    b.rsiLevels.forEach((price) =>
      rsi.createPriceLine({ price, color: COLORS.accent, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: String(price) }),
    );

    // Pane 2: MACD histogram + lines, zero line, and (Strategy 1) the deep-histogram thresholds
    const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, 2);
    hist.setData(b.hist);
    hist.createPriceLine({ price: 0, color: "#625C55", lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: false, title: "" });
    if (b.deepLow !== null && b.deepHigh !== null) {
      hist.createPriceLine({ price: b.deepHigh, color: COLORS.accent, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "Deep high" });
      hist.createPriceLine({ price: b.deepLow, color: COLORS.accent, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "Deep low" });
    }
    chart.addSeries(LineSeries, { color: COLORS.macd, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "MACD" }, 2).setData(b.macd);
    chart.addSeries(LineSeries, { color: COLORS.signal, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "Signal" }, 2).setData(b.signal);

    // Price gets the most room; RSI and MACD share the rest. Stretch factors survive container resizes.
    const [price, rsiPane, macdPane] = chart.panes();
    price.setStretchFactor(0.56);
    rsiPane.setStretchFactor(0.19);
    macdPane.setStretchFactor(0.25);
    // Show the most recent ~130 bars with room on the right so the last marker label is not clipped.
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, b.candles.length - 130), to: b.candles.length + 6 });

    return () => chart.remove();
  }, [data, config, strategyId]);

  const last = data.signals.find((s) => s.strategy_id === strategyId);
  return (
    <div
      ref={host}
      className="chart-canvas"
      role="img"
      aria-label={`${data.ticker} ${data.timeframe === "1d" ? "daily" : "4 hour"} candlestick chart with RSI and MACD${last ? `, ${last.side} signal marked` : ""}`}
    />
  );
}
```

Create `web/src/components/ChartModal.tsx`:

```tsx
import { useEffect, useRef } from "react";
import { getChart } from "../api";
import { useAsync } from "../hooks";
import type { ChartConfig, SignalRow, Timeframe } from "../types";
import { ChartView } from "./ChartView";
import { ErrorState, Loading } from "./Feedback";
import { SignalPill } from "./SignalPill";

interface Props {
  row: SignalRow;
  tf: Timeframe;
  strategyId: string;
  config: ChartConfig;
  onClose: () => void;
}

export function ChartModal({ row, tf, strategyId, config, onClose }: Props) {
  const chart = useAsync(() => getChart(tf, row.ticker), [tf, row.ticker]);
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [onClose]);

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={`${row.ticker} chart`}>
        <div className="head">
          <div>
            <h2>{row.ticker}</h2>
            <div className="tag">{row.name} · {row.sector} · {tf.toUpperCase()}</div>
          </div>
          <div className="row">
            <SignalPill side={row.side} />
            <button ref={closeBtn} type="button" className="x" aria-label="Close chart" onClick={onClose}>×</button>
          </div>
        </div>
        {chart.loading && <Loading what="chart" />}
        {chart.error && <ErrorState error={chart.error} onRetry={chart.retry} />}
        {chart.data && <ChartView data={chart.data} config={config} strategyId={strategyId} />}
        <div className="legend">
          <span>Arrow marks the candle where the signal fired</span>
          <span>Hollow candle = down bar</span>
          <span>Terracotta lines = this strategy's levels</span>
        </div>
      </div>
    </div>
  );
}
```

This is the one piece with no unit test (it needs a real canvas); it is verified visually in Task 13. Its data preparation is covered by `chartData.test.ts`.


- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: no output


- [ ] **Step 3: Commit**

```bash
git add web
git commit -m "feat(web): TradingView-style chart with signal marker, RSI and MACD levels"
```



### Task 11: Pages, app shell and theme

**Files:**
- Create: `web/src/pages/Home.tsx`, `web/src/pages/StrategyPage.tsx`, `web/src/App.tsx`, `web/src/main.tsx`, `web/src/theme.css`
- Test: `web/src/App.test.tsx`

**Interfaces:**
- Consumes: Tasks 8-10: everything above
- Produces: the complete site; default export `App`

- [ ] **Step 1: Write the failing app tests**

Create `web/src/App.test.tsx`:

```tsx
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { strategies, stubFetch } from "./test-fixtures";

vi.mock("./components/ChartView", () => ({
  ChartView: ({ data, strategyId }: { data: { ticker: string }; strategyId: string }) => (
    <div data-testid="chart">{data.ticker}:{strategyId}</div>
  ),
}));

beforeEach(() => {
  window.location.hash = "#/";
  stubFetch();
});
afterEach(() => vi.unstubAllGlobals());

describe("home", () => {
  it("defaults to 1D and shows totals for the timeframe", async () => {
    render(<App />);
    await screen.findByText("What's moving today");
    expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "4H" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Daily")).toBeInTheDocument();
    const tiles = document.querySelectorAll(".stat .n");
    expect([...tiles].map((n) => n.textContent)).toEqual(["1", "1", "Daily"]);
  });

  it("switches to 4H, updates counts, and keeps the choice in the URL", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("What's moving today");
    await user.click(screen.getByRole("button", { name: "4H" }));
    expect(screen.getByText("4 hour")).toBeInTheDocument();
    expect([...document.querySelectorAll(".stat .n")].map((n) => n.textContent)).toEqual(["1", "0", "4 hour"]);
    expect(window.location.hash).toContain("tf=4h");
    await user.click(screen.getByRole("button", { name: "1D" }));
    expect(window.location.hash).not.toContain("tf=");
  });

  it("starts on 4H when the URL says so", async () => {
    window.location.hash = "#/?tf=4h";
    render(<App />);
    await screen.findByText("4 hour");
  });

  it("shows an error with a working retry when strategies fail to load", async () => {
    stubFetch(["strategies.json"]);
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    stubFetch();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("What's moving today");
  });

  it("warns when the data is stale", async () => {
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2020-01-01T00:00:00Z" } });
    render(<App />);
    expect(await screen.findByText(/looks out of date/)).toBeInTheDocument();
  });
});

describe("strategy page", () => {
  beforeEach(() => {
    window.location.hash = "#/strategy/macd-rsi-reversal";
  });

  it("lists stock cards and filters them", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Exxon Mobil");
    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "SELL" }));
    expect(screen.queryByText("Exxon Mobil")).not.toBeInTheDocument();
    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "All" }));
    await user.type(screen.getByLabelText("Search ticker or name"), "zzz");
    expect(screen.getByText(/No signals match these filters/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("Exxon Mobil")).toBeInTheDocument();
  });

  it("follows the global timeframe selector", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Exxon Mobil");
    await user.click(screen.getByRole("button", { name: "4H" }));
    await screen.findByText("American Airlines");
    expect(screen.queryByText("Exxon Mobil")).not.toBeInTheDocument();
  });

  it("shows an empty state when a strategy has no signals", async () => {
    window.location.hash = "#/strategy/trend-pullback";
    render(<App />);
    expect(await screen.findByText("No signals right now.")).toBeInTheDocument();
  });

  it("shows an error when the signal file fails to load", async () => {
    stubFetch(["macd-rsi-reversal/1d.json"]);
    render(<App />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("opens the chart modal on card click and closes with Escape", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /XOM/ }));
    const dialog = await screen.findByRole("dialog", { name: "XOM chart" });
    await waitFor(() => expect(within(dialog).getByTestId("chart")).toHaveTextContent("XOM:macd-rsi-reversal"));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error inside the modal when the chart file is missing", async () => {
    stubFetch(["charts/1d/XOM.json"]);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /XOM/ }));
    expect(await within(await screen.findByRole("dialog")).findByRole("alert")).toBeInTheDocument();
  });

  it("shows 'unknown strategy' for a bad id", async () => {
    window.location.hash = "#/strategy/nope";
    render(<App />);
    expect(await screen.findByText(/Unknown strategy/)).toBeInTheDocument();
  });
});
```

These pin: the selector defaults to 1D and switches counts and the URL; `?tf=4h` is honoured; error + retry; stale banner; filters and clear-filters; **empty state (Review Focus item 4)**; modal open and Esc close; chart load error; unknown strategy.


- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/App.test.tsx`
Expected: FAIL, cannot resolve `./App`


- [ ] **Step 3: Implement the pages, app shell, entry point and styles**

Create `web/src/pages/Home.tsx`:

```tsx
import { Link, useLocation } from "react-router-dom";
import { ErrorState, Loading } from "../components/Feedback";
import { SignalPill } from "../components/SignalPill";
import { useTimeframe } from "../hooks";
import { useStrategies } from "../strategiesContext";

export function Home() {
  const { data, error, loading, retry } = useStrategies();
  const [tf] = useTimeframe();
  const { search } = useLocation();

  if (loading) return <Loading what="strategies" />;
  if (error || !data) return <ErrorState error={error ?? new Error("No data")} onRetry={retry} />;

  const totals = data.strategies.reduce(
    (a, s) => ({ buy: a.buy + s.timeframes[tf].buy, sell: a.sell + s.timeframes[tf].sell }),
    { buy: 0, sell: 0 },
  );

  return (
    <>
      <section className="hero">
        <h1>What's moving today</h1>
        <p>
          Strategy scans across every S&amp;P 500 stock, refreshed after each 4H and daily close.
          Updated {new Date(data.updated_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}.
        </p>
      </section>
      <div className="stats">
        <div className="stat"><div className="tag">Buy signals</div><div className="n num buy-text">{totals.buy}</div></div>
        <div className="stat"><div className="tag">Sell signals</div><div className="n num sell-text">{totals.sell}</div></div>
        <div className="stat"><div className="tag">Timeframe</div><div className="n">{tf === "1d" ? "Daily" : "4 hour"}</div></div>
      </div>
      <div className="big">
        {data.strategies.map((s, i) => (
          <article key={s.id} className={`bigcard ${i % 2 ? "two" : "one"}`}>
            <h2>{s.name}</h2>
            <p className="muted">{s.description}</p>
            <div className="row">
              <span className="count-pill"><SignalPill side="BUY" /> {s.timeframes[tf].buy}</span>
              <span className="count-pill"><SignalPill side="SELL" /> {s.timeframes[tf].sell}</span>
            </div>
            <Link className="link" to={{ pathname: `/strategy/${s.id}`, search }}>See the stocks →</Link>
          </article>
        ))}
      </div>
    </>
  );
}
```

Create `web/src/pages/StrategyPage.tsx`:

```tsx
import { useCallback, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { getSignals } from "../api";
import { ChartModal } from "../components/ChartModal";
import { ErrorState, Loading } from "../components/Feedback";
import { StockCard } from "../components/StockCard";
import { useAsync, useTimeframe } from "../hooks";
import { ALL_SECTORS, DEFAULT_FILTERS, filterSignals, sectorsOf, type Filters } from "../lib/filters";
import { useStrategies } from "../strategiesContext";
import type { SignalRow } from "../types";

export function StrategyPage() {
  const { id = "" } = useParams();
  const [tf] = useTimeframe();
  const strategies = useStrategies();
  const signals = useAsync(() => getSignals(id, tf), [id, tf]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [open, setOpen] = useState<SignalRow | null>(null);
  const close = useCallback(() => setOpen(null), []);

  const rows = signals.data?.signals ?? [];
  const sectors = useMemo(() => sectorsOf(rows), [rows]);
  const shown = useMemo(() => filterSignals(rows, filters), [rows, filters]);
  const strategy = strategies.data?.strategies.find((s) => s.id === id);

  if (strategies.loading) return <Loading what="strategy" />;
  if (strategies.error) return <ErrorState error={strategies.error} onRetry={strategies.retry} />;
  if (!strategy) return <p className="muted center">Unknown strategy "{id}".</p>;

  return (
    <>
      <section className="hero">
        <h1>{strategy.name}</h1>
        <p>{strategy.description}</p>
      </section>

      <div className="tools">
        <div className="seg" role="group" aria-label="Signal filter">
          {(["ALL", "BUY", "SELL"] as const).map((s) => (
            <button key={s} type="button" aria-pressed={filters.side === s} onClick={() => setFilters({ ...filters, side: s })}>
              {s === "ALL" ? "All" : s}
            </button>
          ))}
        </div>
        <input
          aria-label="Search ticker or name"
          placeholder="Search ticker or name"
          value={filters.query}
          onChange={(e) => setFilters({ ...filters, query: e.target.value })}
        />
        <select aria-label="Sector" value={filters.sector} onChange={(e) => setFilters({ ...filters, sector: e.target.value })}>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {signals.loading && <Loading what="signals" />}
      {signals.error && <ErrorState error={signals.error} onRetry={signals.retry} />}
      {signals.data && (
        shown.length === 0 ? (
          <p className="muted center">
            {rows.length === 0 ? "No signals right now." : "No signals match these filters."}
            {filters !== DEFAULT_FILTERS && rows.length > 0 && (
              <> <button type="button" className="linkbtn" onClick={() => setFilters({ ...DEFAULT_FILTERS, sector: ALL_SECTORS })}>Clear filters</button></>
            )}
          </p>
        ) : (
          <div className="grid">
            {shown.map((r) => <StockCard key={`${r.ticker}-${r.side}`} row={r} onOpen={setOpen} />)}
          </div>
        )
      )}

      {open && <ChartModal row={open} tf={tf} strategyId={strategy.id} config={strategy.chart} onClose={close} />}
    </>
  );
}
```

Create `web/src/App.tsx`:

```tsx
import { HashRouter, Route, Routes } from "react-router-dom";
import { StaleBanner } from "./components/Feedback";
import { TopBar } from "./components/TopBar";
import { isStale } from "./lib/filters";
import { Home } from "./pages/Home";
import { StrategyPage } from "./pages/StrategyPage";
import { StrategiesProvider, useStrategies } from "./strategiesContext";

function Shell() {
  const { data } = useStrategies();
  return (
    <>
      <TopBar />
      {data && isStale(data.updated_at, new Date()) && <StaleBanner />}
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/strategy/:id" element={<StrategyPage />} />
          <Route path="*" element={<p className="muted center">Page not found.</p>} />
        </Routes>
      </main>
      <footer className="foot">Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate.</footer>
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <StrategiesProvider>
        <Shell />
      </StrategiesProvider>
    </HashRouter>
  );
}
```

Create `web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./theme.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Create `web/src/theme.css`:

```css
:root {
  --bg: #fffbf6;
  --surface: #ffffff;
  --border: #efe6db;
  --text: #2a2623;
  --muted: #625c55;
  --accent: #a5472a;
  --accent-fill: #cc785c;
  --ring: #cc785c;
  --buy: #27694b;
  --buy-bg: #e3f0e7;
  --sell: #9e2f45;
  --sell-bg: #f9e4e8;
  --seg-bg: #f6ede3;
  --sans: Inter, system-ui, sans-serif;
  --serif: Lora, Georgia, serif;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 var(--sans); }
h1, h2, h3 { font-family: var(--serif); font-weight: 600; margin: 0; letter-spacing: -0.01em; }
a { color: inherit; text-decoration: none; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 3px solid var(--ring); outline-offset: 2px; }
.num { font-variant-numeric: tabular-nums; }
.muted { color: var(--muted); }
.center { text-align: center; padding: 28px 0; }
.row { display: flex; gap: 10px; align-items: center; }
.between { justify-content: space-between; }
.tag { font-size: 12.5px; color: var(--muted); }
.buy-text { color: var(--buy); }
.sell-text { color: var(--sell); }

.top { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 32px; flex-wrap: wrap; }
.brand { font-family: var(--serif); font-size: 22px; font-weight: 600; }
.pillnav { display: flex; gap: 6px; background: var(--seg-bg); padding: 4px; border-radius: 999px; flex-wrap: wrap; }
.pillnav a { padding: 7px 16px; border-radius: 999px; font-weight: 500; color: var(--muted); }
.pillnav a.active { background: var(--surface); color: var(--text); box-shadow: 0 1px 3px rgba(42, 38, 35, 0.12); }

.seg { display: inline-flex; padding: 3px; background: var(--seg-bg); border: 1px solid var(--border); border-radius: 999px; }
.seg button { border: 0; background: transparent; padding: 6px 16px; border-radius: 999px; font-weight: 600; font-size: 14px; min-height: 34px; color: var(--muted); transition: background 0.15s, color 0.15s; }
.seg button[aria-pressed="true"] { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12); }

main { max-width: 1120px; margin: 0 auto; padding: 12px 32px 40px; min-height: 60vh; }
.hero { text-align: center; padding: 20px 0 28px; }
.hero h1 { font-size: 40px; }
.hero p { color: var(--muted); margin: 8px auto 0; max-width: 56ch; }
.foot { padding: 20px 24px; color: var(--muted); font-size: 12.5px; text-align: center; }

.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 16px 20px; }
.stat .n { font-family: var(--serif); font-size: 32px; font-weight: 600; }
.big { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }
.bigcard { border-radius: 24px; padding: 26px; display: flex; flex-direction: column; gap: 14px; border: 1px solid var(--border); }
.bigcard.one { background: #fdefe6; }
.bigcard.two { background: #eaf2ec; }
.bigcard h2 { font-size: 24px; }
.bigcard p { margin: 0; }
.count-pill { display: inline-flex; gap: 6px; align-items: center; font-weight: 600; }
.link { font-weight: 600; color: var(--accent); }

.pill { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 600; white-space: nowrap; }
.pill svg { width: 11px; height: 11px; }
.pill.buy { background: var(--buy-bg); color: var(--buy); }
.pill.sell { background: var(--sell-bg); color: var(--sell); }

.tools { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin: 6px 0 20px; }
.tools input, .tools select { padding: 9px 16px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface); min-height: 42px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
.scard { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 16px 18px; text-align: left; display: flex; flex-direction: column; gap: 8px; transition: box-shadow 0.2s, transform 0.2s; }
.scard:hover { box-shadow: 0 8px 24px rgba(42, 38, 35, 0.09); transform: translateY(-2px); }
.scard .tk { font-family: var(--serif); font-size: 22px; font-weight: 600; }
.spark { width: 100%; height: 36px; display: block; }
.linkbtn { background: none; border: 0; color: var(--accent); font-weight: 600; text-decoration: underline; }
.btn { background: var(--surface); border: 1px solid var(--border); border-radius: 999px; padding: 8px 18px; font-weight: 600; }

.stale { background: #fff4d6; color: #5c4400; padding: 10px 32px; text-align: center; font-size: 14px; }
.errorbox { max-width: 520px; margin: 32px auto; padding: 18px 22px; border: 1px solid var(--sell-bg); background: #fff; border-radius: 16px; text-align: center; }

.modal { position: fixed; inset: 0; background: rgba(42, 38, 35, 0.45); display: flex; align-items: center; justify-content: center; padding: 20px; z-index: 50; }
.sheet { background: var(--surface); border-radius: 24px; max-width: 880px; width: 100%; max-height: 94vh; overflow: auto; padding: 22px; animation: fade 0.18s ease-out; }
.sheet .head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; margin-bottom: 10px; }
.sheet h2 { font-size: 26px; }
.x { border: 1px solid var(--border); background: var(--bg); border-radius: 999px; width: 40px; height: 40px; font-size: 20px; }
.chart-canvas { width: 100%; height: 560px; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--muted); margin-top: 8px; }
@keyframes fade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
@media (max-width: 700px) {
  .stats { grid-template-columns: 1fr; }
  .hero h1 { font-size: 30px; }
  main, .top { padding-left: 16px; padding-right: 16px; }
  .modal { padding: 0; align-items: flex-end; }
  .sheet { border-radius: 24px 24px 0 0; max-height: 96vh; }
  .chart-canvas { height: 480px; }
}
```


- [ ] **Step 4: Run the full web suite, type-check and build**

Run: `cd web && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 24 tests pass; build prints `✓ built`


- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat(web): home and strategy pages, app shell, theme"
```



### Task 12: Workflow, README and publishing

**Files:**
- Create: `.github/workflows/scan.yml`, `README.md`

**Interfaces:**
- Consumes: Tasks 1-11
- Produces: the live site at `https://nsoni8882.github.io/ns-multi-stratt/`, refreshed on the schedule; signal history on the `data` branch

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/scan.yml`:

```yaml
name: Scan and deploy

on:
  schedule:
    # Just after each US 4H bar closes (13:30 and 16:00 ET). Cron is UTC, so both DST offsets are
    # listed; the extra run is harmless because the scanner is idempotent.
    - cron: "35 17,18 * * 1-5"
    - cron: "5 20,21 * * 1-5"
  workflow_dispatch:
  push:
    branches: [main]

permissions:
  contents: write # push the signal history to the `data` branch
  pages: write
  id-token: write

concurrency:
  group: scan-and-deploy # queue overlapping runs so they never race on the history push
  cancel-in-progress: false

jobs:
  scan-and-deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - name: Check out signal history (data branch)
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

      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m pytest -q

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
        working-directory: web
      - run: npm test
        working-directory: web

      # Exits non-zero (skipping everything below) if >10% of tickers fail to fetch.
      - name: Scan the S&P 500
        run: python -m scanner.run --out web/public/data --db history/signals.db

      - run: npm run build
        working-directory: web
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
      - id: deployment
        uses: actions/deploy-pages@v4

      - name: Save signal history
        run: |
          cd history
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add signals.db
          if git diff --cached --quiet; then
            echo "history unchanged"
          else
            git commit --quiet -m "signals $(date -u +%FT%TZ)"
            git push --quiet origin HEAD:data
          fi
```

The `history` clone-or-init and push logic was exercised against a local bare repo (first run creates `data`, an unchanged DB makes no commit, a changed DB is pushed).


- [ ] **Step 2: Create the README**

Create `README.md` (the outer fence below uses four backticks because the content contains code fences):

````markdown
# Multi Strategy

S&P 500 signal screener: two strategies on the Daily and 4H charts, hosted on GitHub Pages.

Live site: https://nsoni8882.github.io/ns-multi-stratt/

Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate.

## How it works

A scheduled GitHub Actions workflow (after each 4H close and the daily close) runs the Python scanner in `scanner/`, writes JSON into `web/public/data/`, builds the Vite site in `web/`, and deploys it to Pages. Every signal is also recorded in `signals.db` on the `data` branch for later validation.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # scanner tests (RUN_NETWORK=1 adds a live Yahoo smoke test)
.venv/bin/python -m scanner.run --out web/public/data --db /tmp/signals.db   # real scan, a few minutes
cd web && npm ci && npm test && npm run dev        # site at http://localhost:5173/ns-multi-stratt/
```

Add a strategy: create a module in `scanner/strategies/`, register it in `scanner/strategies/__init__.py`. The site picks it up from `strategies.json`.
````


- [ ] **Step 3: Verify locally, then commit**

```bash
.venv/bin/python -m pytest -q
(cd web && npm ci && npm test && npm run build)
```

Expected: all green.

```bash
git add .github README.md
git commit -m "ci: scan-and-deploy workflow and README"
```


- [ ] **Step 4: Confirm with the owner, then create the public repo**

Creating a public repository is outward-facing: **ask the owner to confirm before running this.** GitHub Pages on a free account needs a public repo.

```bash
gh auth status
gh repo create nsoni8882/ns-multi-stratt --public --source . --remote origin --description "S&P 500 strategy signals on Daily and 4H charts"
gh api -X POST repos/nsoni8882/ns-multi-stratt/pages -f build_type=workflow
git push -u origin main
```

Pages is enabled before the first push so the first workflow run can deploy.


- [ ] **Step 5: Watch the first run**

```bash
gh run list --limit 3
gh run watch
```

Expected: all steps green. The Scan step takes a few minutes. Then check:

```bash
gh api repos/nsoni8882/ns-multi-stratt/branches/data --jq .name      # -> data
curl -sI https://nsoni8882.github.io/ns-multi-stratt/ | head -1      # -> HTTP/2 200
```

If the run fails with "more than 10% of tickers failed", that is the safety check working: rerun with `gh workflow run scan.yml` and inspect the log for rate limiting.



### Task 13: End-to-end visual verification

**Files:**
- No files changed

**Interfaces:**
- Consumes: Everything above
- Produces: a confirmed working site

- [ ] **Step 1: Run a real scan into the web app**

```bash
.venv/bin/python - <<'EOF'
import logging, pandas as pd, pathlib
logging.basicConfig(level=logging.INFO)
from scanner.run import run
u = pd.read_csv("scanner/universe_fallback.csv").iloc[::2]   # ~250 tickers
run(pathlib.Path("web/public/data"), pathlib.Path(".scratch/e2e.db"), universe=u)
EOF
cd web && npm run build && npx vite preview --port 4173
```

Open `http://localhost:4173/ns-multi-stratt/` in a browser.

- [ ] **Step 2: Check against the approved design**

Walk through and confirm each item (any miss is a bug to fix before declaring done):

- Home loads on **1D** by default; the 1D/4H selector is top-right; switching to 4H changes the counts and the URL gains `?tf=4h`; the nav links keep the choice.
- Each strategy card shows BUY and SELL counts with arrow icons and a "See the stocks" link.
- A strategy page shows a grid of stock cards (ticker, name, signal pill, sparkline, price, bars ago); the All/BUY/SELL filter, search and sector filter work; clearing filters restores the list.
- Clicking a card opens the modal. The chart shows: candles (down bars hollow), a **BUY arrow below** or **SELL arrow above** the signal candle, an RSI pane with the strategy's own levels as labelled terracotta lines (20/80 for MACD + RSI, 40/60 for Trend Pullback), a MACD pane with a zero line and (MACD + RSI strategy only) dashed "Deep high"/"Deep low" lines, EMA 50/200 on the price pane (Trend Pullback only), and the small attribution logo.
- Esc closes the modal and focus returns to the card.
- A phone-width window (390px) has no horizontal scroll and the modal sits at the bottom of the screen.
- With `web/public/data` deleted, the home page shows a clear error with a "Try again" button instead of a blank page.


- [ ] **Step 3: Clean up**

```bash
rm -rf .scratch
```

Stop the preview server. `web/public/data/` is git-ignored, so nothing needs committing.



## After the MVP (not part of this plan)

Signal validation (the `outcomes` table, the evaluator and a performance page) is described in section 11 of the spec. The history database written by this plan already contains everything it needs.
