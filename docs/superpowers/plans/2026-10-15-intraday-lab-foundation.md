# Intraday Lab Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `lab/` package that fetches 5/15-minute bars, runs costed backtests of declarative strategy specs, judges them with a deterministic overfitting-aware gate, records every trial in an append-only ledger, tracks each strategy's lifecycle, and exports a `lab.json` for the (later) Lab tab.

**Architecture:** Strategies are JSON specs (`family` + `params` + `risk`) over a fixed registry of pure causal signal functions. A cost-aware event backtester turns specs into trades; `gate.py` turns trades into a pass/fail with a trial-count-deflated threshold and a sealed holdout; `trials.py` records every verdict. Nothing here places orders.

**Tech Stack:** Python 3.14, pandas>=3.0, numpy, stdlib only otherwise (no scipy, no pyarrow). Reuses `scanner.indicators.rsi` and `trader.alpaca.Alpaca`.

**Spec:** `docs/superpowers/specs/2026-10-15-intraday-lab-foundation-design.md`

## Global Constraints

- Always `.venv/bin/python`; tests: `.venv/bin/python -m pytest lab/tests -q`. No new dependencies in `requirements.txt`.
- Paper only. Nothing in `lab/` submits an order. `trader/alpaca.py` stays hardcoded to the paper host.
- Long-only. Position size is a fraction of **equity**, never `buying_power`.
- Strategies receive **closed bars only** (UTC index = bar open, `close_time` column). A signal at bar *i* fills at the **open of bar i+1**, never at bar *i*'s close.
- Every trade is flat by the session close; no overnight positions.
- Every number that decides a verdict lives in `lab/config.py` and is fingerprinted by `rules_version()`; the newest `HISTORY` entry must match it (a test enforces this).
- Never hand-edit `web/public/data`. `lab/.cache/` and `lab/results/` are gitignored; `lab/trials.jsonl` and `lab/registry.json` are committed.
- Commit in logical units and push to `origin main` after each task. End commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Claims about edge are measured, not asserted; a killed idea is recorded, not retried.

## Review Focus

1. **Early-close days (13:00 ET) and DST weeks** — bar index and 15-minute resampling must stay correct (Task 3 test).
2. **A halted/gappy symbol (missing 5-minute bars)** — the 15-minute bucket is dropped, never filled (Task 3 test).
3. **A spec with an unknown family, an out-of-range, NaN or unknown param, or an empty hypothesis** — rejected with `SpecError`, never a crash mid-backtest (Task 2 tests).
4. **Zero or one trade** — the gate fails with reasons and no division by zero (Task 6 test).
5. **A missing or corrupt ledger line** — the gate refuses to run rather than counting wrong trials (Task 6 test).

---

### Task 1: Config, fingerprint and history

**Files:**
- Create: `lab/__init__.py` (empty), `lab/config.py`, `lab/tests/__init__.py` (empty), `lab/tests/test_config.py`

**Interfaces:**
- Produces: constants below; `params() -> dict`; `rules_version() -> str`; `HISTORY: tuple[Release, ...]` (reuses `trader.params.Release`).

- [ ] **Step 1: Write the failing test** — `lab/tests/test_config.py`

```python
"""The numbers that decide a verdict cannot change without a visible history entry."""
import re

from lab import config


def test_newest_release_fingerprint_matches_live_params():
    assert config.HISTORY[0].fingerprint == config.rules_version(), (
        "lab/config.py changed without a new Release in HISTORY; add one with fingerprint="
        + config.rules_version()
    )


def test_history_is_newest_first_semver_and_plain_english():
    dates = [r.date for r in config.HISTORY]
    assert dates == sorted(dates, reverse=True)
    for r in config.HISTORY:
        assert re.fullmatch(r"\d+\.\d+\.\d+", r.version)
        assert r.summary.strip() and "_" not in r.summary


def test_fingerprint_is_stable():
    assert config.rules_version() == config.rules_version()


def test_every_gate_number_is_in_params():
    p = config.params()
    for key in ("base_t", "min_trades", "min_days", "min_years", "stress_mult", "holdout_months",
                "max_holdout_looks", "holdout_min_ratio", "min_holdout_trades",
                "cost_bps_per_side", "mega_rank", "universe_size"):
        assert key in p, key
```

- [ ] **Step 2: Run it, expect failure**

Run: `.venv/bin/python -m pytest lab/tests/test_config.py -q` → FAIL (`No module named lab.config`).

- [ ] **Step 3: Implement** — `lab/config.py`

```python
"""Every number that decides a verdict, in one place, fingerprinted.

Same contract as trader/params.py: `rules_version()` hashes `params()`, and the newest HISTORY
entry must carry that hash, so moving a threshold without saying so fails the build.
The values are written in lab/ACCEPTANCE.md before any result exists. The cost defaults are
conservative placeholders until quoted spreads are measured (see the spec's open items).
"""
import hashlib
import json

from trader.params import Release

TIMEFRAMES = ("5Min", "15Min")

# One-way cost in bps per side (half-spread + slippage) by liquidity tier.
COST_BPS_PER_SIDE = {"mega": 1.5, "large": 3.0}
MEGA_RANK = 10  # the top-N of the frozen universe are "mega"; the rest "large"
UNIVERSE_SIZE = 50

# The gate.
BASE_T = 2.5  # floor for the (day-level) t statistic; raised by the trial count
MIN_TRADES = 400
MIN_DAYS = 150
MIN_YEARS = 2
STRESS_MULT = 2.0  # costs x2 must still leave positive expectancy
HOLDOUT_MONTHS = 6
MAX_HOLDOUT_LOOKS = 5  # after this many looks the holdout is burned; roll it forward
HOLDOUT_MIN_RATIO = 0.5  # holdout expectancy must be at least this share of development's
MIN_HOLDOUT_TRADES = 30

START_EQUITY = 100_000.0


def params() -> dict:
    return {
        "timeframes": list(TIMEFRAMES),
        "cost_bps_per_side": COST_BPS_PER_SIDE,
        "mega_rank": MEGA_RANK,
        "universe_size": UNIVERSE_SIZE,
        "base_t": BASE_T,
        "min_trades": MIN_TRADES,
        "min_days": MIN_DAYS,
        "min_years": MIN_YEARS,
        "stress_mult": STRESS_MULT,
        "holdout_months": HOLDOUT_MONTHS,
        "max_holdout_looks": MAX_HOLDOUT_LOOKS,
        "holdout_min_ratio": HOLDOUT_MIN_RATIO,
        "min_holdout_trades": MIN_HOLDOUT_TRADES,
    }


def rules_version() -> str:
    return hashlib.sha256(json.dumps(params(), sort_keys=True).encode()).hexdigest()[:12]


HISTORY = (
    Release("1.0.0", "2026-10-15",
            "First version of the lab's bar for a strategy: costs on every trade, a threshold "
            "that rises with every idea tried, and a hidden recent period it must also survive.",
            fingerprint="PLACEHOLDER"),
)
```

- [ ] **Step 4: Fill the real fingerprint, run tests**

Run: `.venv/bin/python -c "from lab import config; print(config.rules_version())"`, paste the output into `fingerprint=` (replacing `PLACEHOLDER`), then `.venv/bin/python -m pytest lab/tests/test_config.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
touch lab/__init__.py lab/tests/__init__.py
git add lab && git commit -m "feat(lab): fingerprinted config for the intraday lab gate

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 2: Strategy specs and the four families

**Files:**
- Create: `lab/spec.py`, `lab/families/__init__.py`, `lab/families/orb.py`, `lab/families/vwap_reversion.py`, `lab/families/rsi2_intraday.py`, `lab/families/gap_fade.py`
- Create: `lab/tests/conftest.py`, `lab/tests/test_spec.py`, `lab/tests/test_families.py`
- Depends on `lab.data.with_session` (Task 3) in the family tests — **do Task 3 first** (reorder: execute Task 3, then this one). The tasks are numbered by dependency of the spec; Task 3 has no dependency on Task 2.

**Interfaces:**
- Consumes: `lab.config.TIMEFRAMES`; `lab.data.with_session(df, timeframe)` (Task 3), a frame with columns `open high low close volume close_time day bar`.
- Produces:
  - Each family module: `DEFAULTS: dict`, `BOUNDS: dict[str, tuple[float, float]]`, `signal(df, p: dict) -> pd.Series[bool]` (same index as `df`, True at bar *i* means "enter at open of bar i+1", computed from bars ≤ i only).
  - `lab.families.REGISTRY: dict[str, module]`.
  - `lab.spec`: `SpecError(ValueError)`, `Risk(stop_pct, target_pct, max_hold_bars, size_pct=0.10, max_concurrent=5)`, `Spec(name, family, timeframe, params, risk, hypothesis)` with `.fingerprint() -> str` (12 hex), `.canonical() -> dict`, `Spec.from_dict(d) -> Spec`, `.to_dict() -> dict`.

- [ ] **Step 1: Write the shared fixtures** — `lab/tests/conftest.py`

```python
import numpy as np
import pandas as pd

from lab.data import ET, with_session


def make_days(days, n=78, base=100.0, drift=0.0, vol=1000, start_hm="09:30"):
    """5-minute regular-session bars for each ET day in `days` (list of 'YYYY-MM-DD')."""
    frames = []
    for d in days:
        open_et = pd.Timestamp(f"{d} {start_hm}", tz=ET)
        idx = pd.date_range(open_et, periods=n, freq="5min").tz_convert("UTC")
        close = base + drift * np.arange(n)
        frames.append(pd.DataFrame(
            {"open": close, "high": close * 1.001, "low": close * 0.999, "close": close,
             "volume": float(vol)}, index=idx))
    return pd.concat(frames)


def random_walk(n_days=25, seed=7):
    """Seeded multi-day 5-minute series with overnight jumps, so every family can fire."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2024-03-04", periods=n_days).strftime("%Y-%m-%d").tolist()
    price, frames = 100.0, []
    for d in days:
        price *= 1 + rng.normal(0, 0.01)
        steps = price * np.cumprod(1 + rng.normal(0, 0.002, 78))
        close = steps
        open_ = np.concatenate([[price], close[:-1]])
        idx = pd.date_range(pd.Timestamp(f"{d} 09:30", tz=ET), periods=78, freq="5min").tz_convert("UTC")
        frames.append(pd.DataFrame(
            {"open": open_, "high": np.maximum(open_, close) * 1.0005,
             "low": np.minimum(open_, close) * 0.9995, "close": close,
             "volume": rng.integers(500, 1500, 78).astype(float)}, index=idx))
        price = close[-1]
    return pd.concat(frames)


def sessions(raw, tf="5Min"):
    return with_session(raw, tf)
```

- [ ] **Step 2: Write failing family tests** — `lab/tests/test_families.py`

```python
import numpy as np
import pandas as pd
import pytest

from lab.families import REGISTRY, gap_fade, orb, rsi2_intraday, vwap_reversion
from lab.tests.conftest import make_days, random_walk, sessions

PERMISSIVE = {
    "orb": {"range_bars": 1, "last_entry_bar": 70},
    "vwap_reversion": {"dev_pct": 0.001, "min_bar": 1},
    "rsi2_intraday": {"buy_below": 40.0, "trend_len": 10},
    "gap_fade": {"gap_pct": 0.002, "entry_bar": 1},
}


def params_for(name):
    mod = REGISTRY[name]
    return {**mod.DEFAULTS, **PERMISSIVE[name]}


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_signal_never_uses_future_bars(name):
    """The guard that makes LLM-proposed specs safe: truncating the data must not change
    any earlier decision. A family that peeks forward fails here."""
    raw = random_walk()
    full = REGISTRY[name].signal(sessions(raw), params_for(name))
    assert full.sum() > 0, "permissive params should fire at least once on the walk"
    for k in (150, 400, 901, 1500):
        cut = REGISTRY[name].signal(sessions(raw.iloc[:k]), params_for(name))
        assert (cut.to_numpy() == full.iloc[:k].to_numpy()).all(), f"{name} changed at k={k}"


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_defaults_sit_inside_bounds(name):
    mod = REGISTRY[name]
    assert set(mod.DEFAULTS) == set(mod.BOUNDS)
    for k, (lo, hi) in mod.BOUNDS.items():
        assert lo <= mod.DEFAULTS[k] <= hi, k


def test_orb_fires_once_per_day_and_only_after_the_range():
    raw = random_walk()
    df = sessions(raw)
    sig = orb.signal(df, {**orb.DEFAULTS, "range_bars": 3, "last_entry_bar": 70})
    assert (df.loc[sig, "bar"] >= 3).all()
    assert (df[sig].groupby("day").size() <= 1).all()


def test_orb_volume_filter_blocks_the_first_day():
    df = sessions(random_walk())
    sig = orb.signal(df, {**orb.DEFAULTS, "range_bars": 1, "min_rvol": 0.5})
    first_day = df["day"].iloc[0]
    assert not sig[df["day"] == first_day].any()  # no prior days -> no relative volume


def test_gap_fade_only_after_a_down_gap():
    up = make_days(["2024-03-04"], base=100).iloc[:78]
    nxt_up = make_days(["2024-03-05"], base=105)
    nxt_dn = make_days(["2024-03-06"], base=95)
    df = sessions(pd.concat([up, nxt_up, nxt_dn]))
    sig = gap_fade.signal(df, {"gap_pct": 0.01, "entry_bar": 1})
    fired_days = set(df.loc[sig, "day"])
    assert len(fired_days) == 1 and next(iter(fired_days)).day == 6


def test_vwap_reversion_silent_when_price_sits_on_vwap():
    df = sessions(make_days(["2024-03-04", "2024-03-05"]))
    assert not vwap_reversion.signal(df, {**vwap_reversion.DEFAULTS, "dev_pct": 0.001}).any()


def test_rsi2_requires_price_above_trend():
    falling = sessions(make_days(["2024-03-04", "2024-03-05"], drift=-0.05))
    sig = rsi2_intraday.signal(falling, {**rsi2_intraday.DEFAULTS, "trend_len": 20, "buy_below": 40.0})
    assert not sig.any()  # a steady decline never closes above its own average
```

- [ ] **Step 3: Write failing spec tests** — `lab/tests/test_spec.py`

```python
import math

import pytest

from lab.spec import Spec, SpecError

GOOD = {
    "name": "ORB-3", "family": "orb", "timeframe": "5Min",
    "params": {"range_bars": 3},
    "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 40},
    "hypothesis": "Stocks that break the first 15 minutes high on heavy volume keep going.",
}


def test_defaults_are_filled_and_fingerprint_is_stable():
    a = Spec.from_dict(GOOD)
    assert a.params["last_entry_bar"] == 30
    b = Spec.from_dict({**GOOD, "name": "renamed", "hypothesis": "different words"})
    assert a.fingerprint() == b.fingerprint()  # name and prose do not change behaviour
    c = Spec.from_dict({**GOOD, "params": {"range_bars": 4}})
    assert a.fingerprint() != c.fingerprint()


def test_round_trips_through_dict():
    a = Spec.from_dict(GOOD)
    assert Spec.from_dict(a.to_dict()).fingerprint() == a.fingerprint()


@pytest.mark.parametrize("patch", [
    {"family": "nope"},
    {"timeframe": "1Min"},
    {"params": {"range_bars": 999}},
    {"params": {"range_bars": math.nan}},
    {"params": {"surprise": 1}},
    {"params": {"range_bars": "3"}},
    {"hypothesis": "   "},
    {"risk": {"stop_pct": 0.0, "target_pct": 0.02, "max_hold_bars": 40}},
    {"risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 0}},
    {"risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 40, "size_pct": 0.9}},
])
def test_bad_specs_are_rejected_not_crashed(patch):
    with pytest.raises(SpecError):
        Spec.from_dict({**GOOD, **patch})
```

- [ ] **Step 4: Run both, expect failure** — `.venv/bin/python -m pytest lab/tests/test_families.py lab/tests/test_spec.py -q` → FAIL (modules missing).

- [ ] **Step 5: Implement the families**

`lab/families/__init__.py`
```python
"""The fixed menu. A family is a pure, causal function of closed bars; adding one is an
ordinary code change with tests, never something an LLM does at run time."""
from lab.families import gap_fade, orb, rsi2_intraday, vwap_reversion

REGISTRY = {
    "orb": orb,
    "vwap_reversion": vwap_reversion,
    "rsi2_intraday": rsi2_intraday,
    "gap_fade": gap_fade,
}
```

`lab/families/orb.py`
```python
"""Opening-range breakout, long only. Enter on the first close above the opening range's high.

`min_rvol` is the "stocks in play" filter: the opening range's volume against its own average
over the previous `rvol_days` days. 0 turns it off.
"""
import pandas as pd

DEFAULTS = {"range_bars": 3, "last_entry_bar": 30, "min_rvol": 0.0, "rvol_days": 14}
BOUNDS = {"range_bars": (1, 12), "last_entry_bar": (4, 70), "min_rvol": (0.0, 10.0),
          "rvol_days": (3, 60)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    n = int(p["range_bars"])
    in_range = df["bar"] < n
    high = df["high"].where(in_range).groupby(df["day"]).transform("max")
    cond = (df["bar"] >= n) & (df["bar"] <= p["last_entry_bar"]) & (df["close"] > high)
    if p["min_rvol"] > 0:
        or_vol = df["volume"].where(in_range).groupby(df["day"]).sum()
        prior = or_vol.shift(1).rolling(int(p["rvol_days"]), min_periods=1).mean()
        rvol = pd.Series((or_vol / prior).reindex(df["day"]).to_numpy(), index=df.index)
        cond &= rvol >= p["min_rvol"]
    return cond & (cond.groupby(df["day"]).cumsum() == 1)
```

`lab/families/vwap_reversion.py`
```python
"""Buy a stretch below the session VWAP, once per day. VWAP accumulates from the open, so
bar i only ever sees bars up to i."""
import numpy as np
import pandas as pd

DEFAULTS = {"dev_pct": 0.006, "min_bar": 6, "last_entry_bar": 60}
BOUNDS = {"dev_pct": (0.001, 0.03), "min_bar": (1, 40), "last_entry_bar": (5, 70)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = (typical * df["volume"]).groupby(df["day"]).cumsum()
    vol = df["volume"].groupby(df["day"]).cumsum().replace(0, np.nan)
    vwap = pv / vol
    cond = ((df["bar"] >= p["min_bar"]) & (df["bar"] <= p["last_entry_bar"])
            & (df["close"] < vwap * (1 - p["dev_pct"])))
    return cond & (cond.groupby(df["day"]).cumsum() == 1)
```

`lab/families/rsi2_intraday.py`
```python
"""The daily RSI(2) reversion idea on intraday bars: oversold while still above a trend average."""
import pandas as pd

from scanner.indicators import rsi

DEFAULTS = {"rsi_len": 2, "buy_below": 10.0, "trend_len": 78, "last_entry_bar": 70}
BOUNDS = {"rsi_len": (2, 14), "buy_below": (1.0, 40.0), "trend_len": (10, 400),
          "last_entry_bar": (5, 77)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    r = rsi(df["close"], int(p["rsi_len"]))
    trend = df["close"].rolling(int(p["trend_len"])).mean()
    return (r < p["buy_below"]) & (df["close"] > trend) & (df["bar"] <= p["last_entry_bar"])
```

`lab/families/gap_fade.py`
```python
"""Fade a gap down: buy at `entry_bar` when the open is more than `gap_pct` under the prior
session's close. The prior close is the shifted last close of the *previous* day, so the
current day never contributes to its own gap."""
import pandas as pd

DEFAULTS = {"gap_pct": 0.01, "entry_bar": 1}
BOUNDS = {"gap_pct": (0.002, 0.10), "entry_bar": (0, 10)}


def signal(df: pd.DataFrame, p: dict) -> pd.Series:
    day_open = df["open"].where(df["bar"] == 0).groupby(df["day"]).transform("max")
    prev_close = df["close"].groupby(df["day"]).last().shift(1).reindex(df["day"]).to_numpy()
    gap = day_open.to_numpy() / prev_close - 1
    return pd.Series((df["bar"].to_numpy() == int(p["entry_bar"])) & (gap < -p["gap_pct"]),
                     index=df.index)
```

- [ ] **Step 6: Implement `lab/spec.py`**

```python
"""A strategy is data: a family from the fixed registry, its parameters, and its risk rules.
Specs arrive from the owner or from the /lab skill; validation here is what stands between a
bad proposal and a crash (or a lookahead) mid-backtest."""
import hashlib
import json
import math
from dataclasses import asdict, dataclass

from lab import config
from lab.families import REGISTRY


class SpecError(ValueError):
    pass


RISK_BOUNDS = {"stop_pct": (0.0005, 0.10), "target_pct": (0.0005, 0.20),
               "max_hold_bars": (1, 78), "size_pct": (0.01, 0.25), "max_concurrent": (1, 20)}


def _number(name, value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpecError(f"{name} must be a finite number, got {value!r}")
    if not lo <= value <= hi:
        raise SpecError(f"{name}={value} outside [{lo}, {hi}]")
    return value


@dataclass(frozen=True)
class Risk:
    stop_pct: float
    target_pct: float
    max_hold_bars: int
    size_pct: float = 0.10
    max_concurrent: int = 5

    def __post_init__(self):
        for k, (lo, hi) in RISK_BOUNDS.items():
            _number(f"risk.{k}", getattr(self, k), lo, hi)


@dataclass(frozen=True)
class Spec:
    name: str
    family: str
    timeframe: str
    params: dict
    risk: Risk
    hypothesis: str

    @classmethod
    def from_dict(cls, d: dict) -> "Spec":
        family = d.get("family")
        if family not in REGISTRY:
            raise SpecError(f"unknown family {family!r}; choose from {sorted(REGISTRY)}")
        if d.get("timeframe") not in config.TIMEFRAMES:
            raise SpecError(f"timeframe must be one of {config.TIMEFRAMES}")
        if not str(d.get("hypothesis", "")).strip():
            raise SpecError("a hypothesis is required, and must be written before testing")
        mod = REGISTRY[family]
        given = dict(d.get("params") or {})
        unknown = set(given) - set(mod.DEFAULTS)
        if unknown:
            raise SpecError(f"unknown params for {family}: {sorted(unknown)}")
        params = {**mod.DEFAULTS, **given}
        for k, (lo, hi) in mod.BOUNDS.items():
            _number(f"params.{k}", params[k], lo, hi)
        try:
            risk = Risk(**d["risk"])
        except (KeyError, TypeError) as e:
            raise SpecError(f"risk is invalid: {e}") from None
        return cls(str(d.get("name") or family), family, d["timeframe"], params, risk,
                   str(d["hypothesis"]).strip())

    def canonical(self) -> dict:
        """What changes behaviour: not the name, not the prose."""
        return {"family": self.family, "timeframe": self.timeframe,
                "params": dict(sorted(self.params.items())), "risk": asdict(self.risk)}

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.canonical(), sort_keys=True).encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {"name": self.name, "hypothesis": self.hypothesis, **self.canonical()}
```

- [ ] **Step 7: Run tests (after Task 3 exists)** — `.venv/bin/python -m pytest lab/tests/test_families.py lab/tests/test_spec.py -q` → PASS. If a family test fails, fix the family, not the test (the lookahead guard is the point).

- [ ] **Step 8: Commit**

```bash
git add lab && git commit -m "feat(lab): strategy specs and four causal signal families

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 3: Bars — client method, session annotation, 15-minute resample (do this before Task 2)

**Files:**
- Modify: `trader/alpaca.py` (add `bars` method after `daily_closes`)
- Create: `lab/data.py`, `lab/tests/test_data.py`, `lab/tests/test_bars_client.py`

**Interfaces:**
- Produces:
  - `Alpaca.bars(symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]` (raw Alpaca bars `{t,o,h,l,c,v,…}`, oldest first, paginated, split/dividend adjusted, SIP, `end` clipped to now − 16 min).
  - `lab.data`: `ET`, `to_frame(raw) -> DataFrame`, `regular_session(df)`, `with_session(df, timeframe) -> DataFrame` (adds `close_time`, `day`, `bar`), `to_15min(df5) -> DataFrame`, `closed_only(df, now)`, `dev_cutoff(frames: dict[str, DataFrame]) -> Timestamp`, `get(client, symbol, timeframe, start, end, cache_dir=CACHE) -> DataFrame`.

- [ ] **Step 1: Failing client test** — `lab/tests/test_bars_client.py`

```python
import json
from datetime import datetime, timezone

from trader.alpaca import Alpaca

BAR = {"t": "2024-03-04T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}


def test_bars_follow_pagination_and_request_the_timeframe():
    pages = [{"bars": {"AAPL": [BAR]}, "next_page_token": "x"},
             {"bars": {"AAPL": [{**BAR, "t": "2024-03-04T14:35:00Z"}]}, "next_page_token": None}]
    calls = []

    def opener(url, data, headers, method):
        calls.append(url)
        return json.dumps(pages[len(calls) - 1]).encode()

    a = Alpaca("k", "s", opener=opener)
    out = a.bars("AAPL", "5Min", datetime(2024, 3, 1, tzinfo=timezone.utc),
                 datetime(2024, 3, 5, tzinfo=timezone.utc))
    assert [b["t"] for b in out] == ["2024-03-04T14:30:00Z", "2024-03-04T14:35:00Z"]
    assert "timeframe=5Min" in calls[0] and "page_token=x" in calls[1]
    assert "feed=sip" in calls[0] and "adjustment=all" in calls[0]


def test_bars_for_an_unknown_symbol_is_empty_not_an_error():
    a = Alpaca("k", "s", opener=lambda *x: json.dumps({"bars": None, "next_page_token": None}).encode())
    assert a.bars("ZZZZ", "5Min", datetime(2024, 3, 1, tzinfo=timezone.utc),
                  datetime(2024, 3, 2, tzinfo=timezone.utc)) == []
```

- [ ] **Step 2: Failing data tests** — `lab/tests/test_data.py`

```python
import pandas as pd

from lab import data
from lab.tests.conftest import make_days


def test_to_frame_parses_alpaca_bars():
    raw = [{"t": "2024-03-04T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]
    df = data.to_frame(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None and df["close"].iloc[0] == 1.5
    assert data.to_frame([]).empty


def test_regular_session_drops_extended_hours():
    day = make_days(["2024-03-04"])
    pre = make_days(["2024-03-04"], n=1, start_hm="08:00")
    post = make_days(["2024-03-04"], n=1, start_hm="16:00")
    out = data.regular_session(pd.concat([pre, day, post]).sort_index())
    assert len(out) == 78


def test_with_session_numbers_bars_per_day_and_sets_close_time():
    df = data.with_session(make_days(["2024-03-04", "2024-03-05"]), "5Min")
    assert df.groupby("day")["bar"].max().tolist() == [77, 77]
    assert df["bar"].iloc[78] == 0
    assert (df["close_time"] - df.index == pd.Timedelta(minutes=5)).all()


def test_early_close_day_has_fewer_bars_and_still_resamples():
    df5 = make_days(["2024-11-29"], n=42)  # 09:30-13:00 ET
    df15 = data.to_15min(df5)
    assert len(df15) == 14 and df15.index[-1].tz_convert(data.ET).strftime("%H:%M") == "12:45"


def test_dst_week_keeps_session_alignment():
    df5 = pd.concat([make_days(["2024-03-08"]), make_days(["2024-03-11"])])  # US DST starts 03-10
    et = data.to_15min(df5).index.tz_convert(data.ET)
    assert et[0].strftime("%H:%M") == "09:30" and et[26].strftime("%H:%M") == "09:30"


def test_15min_drops_a_bucket_with_a_missing_bar():
    df5 = make_days(["2024-03-04"]).drop(index=lambda i: False)
    gappy = df5.drop(df5.index[4])  # a halted 5-minute bar
    assert len(data.to_15min(df5)) == 26 and len(data.to_15min(gappy)) == 25


def test_closed_only_drops_the_forming_bar():
    df = data.with_session(make_days(["2024-03-04"], n=3), "5Min")
    now = df["close_time"].iloc[1]
    assert len(data.closed_only(df, now)) == 2


def test_dev_cutoff_is_six_months_before_the_latest_bar():
    a = make_days(["2023-01-03"])
    b = make_days(["2024-03-04"])
    cutoff = data.dev_cutoff({"A": pd.concat([a, b])})
    assert cutoff.tz_convert(data.ET).strftime("%Y-%m") == "2023-09"
```

- [ ] **Step 3: Run, expect failure** — `.venv/bin/python -m pytest lab/tests/test_bars_client.py lab/tests/test_data.py -q`

- [ ] **Step 4: Implement `Alpaca.bars`** — add to `trader/alpaca.py`

```python
    def bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> "list[dict]":
        """Raw bars, oldest first, split/dividend adjusted. `end` is held 16 minutes back, which
        is what lets a free account read the SIP feed."""
        end = min(end, datetime.now(timezone.utc) - END_HOLDBACK)
        out, token = [], None
        while True:
            q = {"symbols": symbol, "timeframe": timeframe,
                 "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "adjustment": "all",
                 "feed": FEED, "sort": "asc", "limit": 10000}
            if token:
                q["page_token"] = token
            r = self._call(DATA, "/v2/stocks/bars", q)
            out += (r.get("bars") or {}).get(symbol, [])
            token = r.get("next_page_token")
            if not token:
                return out
```

- [ ] **Step 5: Implement `lab/data.py`**

```python
"""Intraday bars: fetch, cache, session-annotate. Output frames follow the repo convention:
UTC index = bar open, a `close_time` column, and only closed bars. `day` (ET date) and `bar`
(0-based index within the session) are added for the families."""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from lab import config

ET = "America/New_York"
OHLCV = ["open", "high", "low", "close", "volume"]
BAR_MINUTES = {"5Min": 5, "15Min": 15}
CACHE = Path(__file__).parent / ".cache"
OPEN_MIN, CLOSE_MIN = 9 * 60 + 30, 16 * 60


def to_frame(raw: "list[dict]") -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], tz="UTC"))
    df = pd.DataFrame(raw)
    out = pd.DataFrame({"open": df["o"], "high": df["h"], "low": df["l"], "close": df["c"],
                        "volume": df["v"]}).astype(float)
    out.index = pd.DatetimeIndex(pd.to_datetime(df["t"], utc=True))
    return out[~out.index.duplicated()].sort_index()


def regular_session(df: pd.DataFrame) -> pd.DataFrame:
    et = df.index.tz_convert(ET)
    minutes = et.hour * 60 + et.minute
    return df[(minutes >= OPEN_MIN) & (minutes < CLOSE_MIN)]


def with_session(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    out = df.copy()
    out["close_time"] = out.index + pd.Timedelta(minutes=BAR_MINUTES[timeframe])
    out["day"] = out.index.tz_convert(ET).date
    out["bar"] = out.groupby("day").cumcount()
    return out


def to_15min(df5: pd.DataFrame) -> pd.DataFrame:
    """Three 5-minute bars make one 15-minute bar. A bucket missing any (a halt) is dropped,
    never filled, so a partial bar is never presented as closed."""
    et = df5[OHLCV].tz_convert(ET)
    grouped = et.resample("15min")
    agg = grouped.agg({"open": "first", "high": "max", "low": "min", "close": "last",
                       "volume": "sum"})
    return agg[grouped["close"].count() == 3].tz_convert("UTC")


def closed_only(df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    return df[df["close_time"] <= now]


def dev_cutoff(frames: "dict[str, pd.DataFrame]") -> pd.Timestamp:
    """Where development data ends. Everything after it is the sealed holdout, which only
    lab/gate.py may read."""
    latest = max(f.index.max() for f in frames.values())
    return latest - pd.DateOffset(months=config.HOLDOUT_MONTHS)


def _fetch_5min(client, symbol: str, start: datetime, end: datetime, cache_dir: Path) -> pd.DataFrame:
    path = cache_dir / f"{symbol}_5Min.pkl"
    have = pd.read_pickle(path) if path.exists() else to_frame([])
    if len(have):
        start = max(start, have.index.max().to_pydatetime())
    fresh = regular_session(to_frame(client.bars(symbol, "5Min", start, end)))
    df = pd.concat([have, fresh]) if len(have) else fresh
    df = df[~df.index.duplicated(keep="last")].sort_index()
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


def get(client, symbol: str, timeframe: str, start: datetime, end: datetime | None = None,
        cache_dir: Path = CACHE) -> pd.DataFrame:
    end = end or datetime.now(timezone.utc)
    df5 = _fetch_5min(client, symbol, start, end, cache_dir)
    base = df5 if timeframe == "5Min" else to_15min(df5)
    framed = with_session(base, timeframe)
    return closed_only(framed, pd.Timestamp(datetime.now(timezone.utc)))
```

- [ ] **Step 6: Run** — `.venv/bin/python -m pytest lab/tests/test_bars_client.py lab/tests/test_data.py lab/tests/test_alpaca.py trader/tests/test_alpaca.py -q` → PASS. (The last two may not exist by those names; run `trader/tests -q` to confirm nothing in the trader broke.)

- [ ] **Step 7: Commit**

```bash
printf '\n# intraday lab: bar cache and generated results\nlab/.cache/\nlab/results/\n' >> .gitignore
git add .gitignore trader/alpaca.py lab && git commit -m "feat(lab): 5/15-minute bars with session annotation and a bars() client method

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 4: Costs and the backtester

**Files:**
- Create: `lab/costs.py`, `lab/backtest.py`, `lab/tests/test_costs.py`, `lab/tests/test_backtest.py`

**Interfaces:**
- Consumes: `Spec`, `Risk` (Task 2); family `signal`; frames from `lab.data` (columns open/high/low/close/volume/day/bar, UTC index).
- Produces:
  - `costs.tier_for(rank: int) -> str`; `costs.net_return(entry_px, exit_px, tier, mult=1.0) -> float`.
  - `backtest.Trade` (frozen dataclass: `symbol, entry_time, exit_time, entry_px, exit_px, bars_held, exit_reason, gross, net`).
  - `backtest.simulate_symbol(df, sig, risk, tier, symbol, cost_mult=1.0) -> list[Trade]`.
  - `backtest.run(spec, frames, tiers, *, cost_mult=1.0, allowed=None) -> BacktestResult` with `.trades`, `.frame() -> DataFrame[symbol, entry_time, exit_time, entry_px, exit_px, bars_held, exit_reason, gross, net, day]`, `.daily_mean() -> Series(net by ET entry day)`, `.equity_curve() -> DataFrame[t, equity, drawdown]`, `.before(ts)`, `.after(ts)`.

- [ ] **Step 1: Failing cost tests** — `lab/tests/test_costs.py`

```python
import pytest

from lab import config, costs


def test_costs_bite_on_both_sides():
    c = config.COST_BPS_PER_SIDE["large"] * 1e-4
    assert costs.net_return(100.0, 100.0, "large") == pytest.approx((1 - c) / (1 + c) - 1)


def test_stress_multiplier_scales_the_cost():
    assert costs.net_return(100, 101, "mega", mult=2) < costs.net_return(100, 101, "mega")


def test_tiers_by_rank():
    assert costs.tier_for(0) == "mega" and costs.tier_for(config.MEGA_RANK) == "large"
```

- [ ] **Step 2: Failing backtest tests** — `lab/tests/test_backtest.py`

```python
import pandas as pd
import pytest

from lab import backtest
from lab.spec import Risk, Spec
from lab.tests.conftest import make_days, random_walk, sessions

RISK = Risk(stop_pct=0.01, target_pct=0.02, max_hold_bars=20)


def frame(opens, highs, lows, closes):
    base = make_days(["2024-03-04"], n=len(opens))
    base["open"], base["high"], base["low"], base["close"] = opens, highs, lows, closes
    return sessions(base)


def sig_at(df, i):
    s = pd.Series(False, index=df.index)
    s.iloc[i] = True
    return s


def test_entry_is_the_next_bars_open_not_the_signal_bars_close():
    df = frame([100, 101, 101, 101], [100, 101, 101, 101], [100, 101, 101, 101], [100, 100.5, 101, 101])
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.entry_px == 101 and t.exit_reason == "session"


def test_target_fills_at_the_target_price():
    df = frame([100, 100, 100, 100], [100, 100, 102.5, 100], [100, 100, 100, 100], [100] * 4)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.exit_reason == "target" and t.exit_px == pytest.approx(102.0)


def test_stop_wins_when_one_bar_touches_both():
    df = frame([100, 100, 100, 100], [100, 100, 103, 100], [100, 100, 98, 100], [100] * 4)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.exit_reason == "stop"


def test_a_gap_through_the_stop_fills_at_the_open_not_the_stop():
    df = frame([100, 100, 95, 95], [100, 100, 95, 95], [100, 100, 95, 95], [100, 100, 95, 95])
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "mega", "X")
    assert t.exit_px == 95 and t.exit_reason == "stop"


def test_max_hold_closes_the_trade():
    short = Risk(stop_pct=0.05, target_pct=0.2, max_hold_bars=2)
    df = frame([100] * 6, [100] * 6, [100] * 6, [100] * 6)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), short, "mega", "X")
    assert t.exit_reason == "time" and t.bars_held == 2


def test_a_signal_on_the_last_bar_of_the_day_does_not_trade():
    df = frame([100] * 4, [100] * 4, [100] * 4, [100] * 4)
    assert backtest.simulate_symbol(df, sig_at(df, 3), RISK, "mega", "X") == []


def test_no_overlapping_positions_in_one_symbol():
    df = frame([100] * 8, [100] * 8, [100] * 8, [100] * 8)
    sig = pd.Series(True, index=df.index)
    trades = backtest.simulate_symbol(df, sig, RISK, "mega", "X")
    assert all(a.exit_time < b.entry_time or a.exit_time <= b.entry_time
               for a, b in zip(trades, trades[1:]))


def test_costs_are_charged():
    df = frame([100] * 4, [100] * 4, [100] * 4, [100] * 4)
    t, = backtest.simulate_symbol(df, sig_at(df, 0), RISK, "large", "X")
    assert t.gross == 0 and t.net < 0


def spec(**risk):
    return Spec.from_dict({"name": "t", "family": "gap_fade", "timeframe": "5Min",
                           "params": {"gap_pct": 0.002, "entry_bar": 1},
                           "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30, **risk},
                           "hypothesis": "gap downs mean-revert intraday"})


def test_run_respects_the_concurrency_cap():
    frames = {f"S{i}": sessions(random_walk(seed=i)) for i in range(6)}
    tiers = {k: "large" for k in frames}
    res = backtest.run(spec(max_concurrent=1), frames, tiers)
    ordered = sorted(res.trades, key=lambda t: t.entry_time)
    for a, b in zip(ordered, ordered[1:]):
        assert b.entry_time >= a.exit_time
    assert len(backtest.run(spec(max_concurrent=5), frames, tiers).trades) >= len(res.trades)


def test_universe_membership_filters_by_year():
    frames = {"A": sessions(random_walk())}
    open_all = backtest.run(spec(), frames, {"A": "large"})
    none = backtest.run(spec(), frames, {"A": "large"}, allowed={"A": {1999}})
    assert open_all.trades and not none.trades


def test_before_and_after_partition_the_trades():
    frames = {"A": sessions(random_walk())}
    res = backtest.run(spec(), frames, {"A": "large"})
    cut = res.trades[len(res.trades) // 2].entry_time
    assert len(res.before(cut).trades) + len(res.after(cut).trades) == len(res.trades)


def test_empty_result_does_not_divide_by_zero():
    res = backtest.run(spec(), {"A": sessions(make_days(["2024-03-04"]))}, {"A": "large"})
    assert res.trades == [] and res.daily_mean().empty and res.equity_curve().empty
```

- [ ] **Step 3: Run, expect failure.**

- [ ] **Step 4: Implement `lab/costs.py`**

```python
"""What a round trip costs. Charged on both sides, against the trader: you buy above the
price you saw and sell below it. The stress run multiplies this."""
from lab import config


def tier_for(rank: int) -> str:
    return "mega" if rank < config.MEGA_RANK else "large"


def net_return(entry_px: float, exit_px: float, tier: str, mult: float = 1.0) -> float:
    c = config.COST_BPS_PER_SIDE[tier] * mult * 1e-4
    return exit_px * (1 - c) / (entry_px * (1 + c)) - 1
```

- [ ] **Step 5: Implement `lab/backtest.py`**

```python
"""Event-driven backtest. A signal at bar i fills at the open of bar i+1. Inside a bar the
order of events is unknowable from OHLC, so the pessimistic order is used: a gap through the
stop fills at the open, and a bar that touches both stop and target is a stop. Trades are
flat by the session close, so a trade never spans a day."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from lab import config, costs
from lab.data import ET
from lab.families import REGISTRY


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_px: float
    exit_px: float
    bars_held: int
    exit_reason: str
    gross: float
    net: float


def simulate_symbol(df, sig, risk, tier, symbol, cost_mult=1.0) -> "list[Trade]":
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    days, idx, flag = df["day"].to_numpy(), df.index, sig.to_numpy(bool)
    n, trades, i = len(df), [], 0
    while i < n - 1:
        if not flag[i] or days[i + 1] != days[i]:
            i += 1
            continue
        e = i + 1
        entry = o[e]
        stop, target = entry * (1 - risk.stop_pct), entry * (1 + risk.target_pct)
        j, reason, px = e, None, 0.0
        while reason is None:
            if o[j] <= stop:
                reason, px = "stop", o[j]
            elif l[j] <= stop:
                reason, px = "stop", stop
            elif o[j] >= target:
                reason, px = "target", o[j]
            elif h[j] >= target:
                reason, px = "target", target
            elif j - e + 1 >= risk.max_hold_bars:
                reason, px = "time", c[j]
            elif j + 1 >= n or days[j + 1] != days[j]:
                reason, px = "session", c[j]
            else:
                j += 1
        trades.append(Trade(symbol, idx[e], idx[j], float(entry), float(px), j - e + 1, reason,
                            float(px / entry - 1), float(costs.net_return(entry, px, tier, cost_mult))))
        i = j + 1
    return trades


@dataclass
class BacktestResult:
    trades: "list[Trade]"
    size_pct: float

    def frame(self) -> pd.DataFrame:
        cols = ["symbol", "entry_time", "exit_time", "entry_px", "exit_px", "bars_held",
                "exit_reason", "gross", "net"]
        df = pd.DataFrame([[getattr(t, k) for k in cols] for t in self.trades], columns=cols)
        df["day"] = [t.tz_convert(ET).date() for t in df["entry_time"]]
        return df

    def daily_mean(self) -> pd.Series:
        f = self.frame()
        return f.groupby("day")["net"].mean() if len(f) else pd.Series(dtype=float)

    def equity_curve(self) -> pd.DataFrame:
        f = self.frame()
        if f.empty:
            return pd.DataFrame(columns=["t", "equity", "drawdown"])
        ret = (f["net"] * self.size_pct).groupby(f["day"]).sum()
        equity = config.START_EQUITY * (1 + ret).cumprod()
        peak = equity.cummax()
        return pd.DataFrame({"t": list(ret.index), "equity": equity.to_numpy(),
                             "drawdown": (equity / peak - 1).to_numpy()})

    def before(self, ts) -> "BacktestResult":
        return BacktestResult([t for t in self.trades if t.entry_time < ts], self.size_pct)

    def after(self, ts) -> "BacktestResult":
        return BacktestResult([t for t in self.trades if t.entry_time >= ts], self.size_pct)


def run(spec, frames, tiers, *, cost_mult=1.0, allowed=None) -> BacktestResult:
    family = REGISTRY[spec.family]
    every = []
    for symbol, df in frames.items():
        sig = family.signal(df, spec.params)
        if allowed is not None:
            years = allowed.get(symbol, set())
            sig = sig & df["day"].map(lambda d: d.year in years)
        every += simulate_symbol(df, sig, spec.risk, tiers.get(symbol, "large"), symbol, cost_mult)
    kept, open_exits = [], []
    for t in sorted(every, key=lambda t: (t.entry_time, t.symbol)):
        open_exits = [x for x in open_exits if x > t.entry_time]
        if len(open_exits) < spec.risk.max_concurrent:
            kept.append(t)
            open_exits.append(t.exit_time)
    return BacktestResult(kept, spec.risk.size_pct)
```

- [ ] **Step 6: Run** — `.venv/bin/python -m pytest lab/tests -q` → PASS (all so far).

- [ ] **Step 7: Commit**

```bash
git add lab && git commit -m "feat(lab): cost model and event-driven intraday backtester

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 5: Statistics, trial ledger, acceptance bar and the gate

**Files:**
- Create: `lab/ACCEPTANCE.md` (written FIRST), `lab/stats.py`, `lab/trials.py`, `lab/gate.py`
- Create: `lab/tests/test_stats.py`, `lab/tests/test_trials.py`, `lab/tests/test_gate.py`, `lab/tests/test_sealed.py`

**Interfaces:**
- Produces:
  - `stats.t_stat(x: np.ndarray) -> float`; `stats.deflated_threshold(n_trials: int, base: float) -> float`.
  - `trials.LedgerError`, `trials.Ledger(path=DEFAULT)` with `.read() -> list[dict]`, `.count() -> int`, `.has(fp) -> bool`, `.holdout_looks() -> int`, `.append(rec: dict) -> None`.
  - `gate.Check(name, ok, detail)`, `gate.GateResult(passed, checks, metrics, fingerprint, holdout_look)`, `gate.AlreadyTried`, `gate.dev_checks(trades: DataFrame[day, net], stress_mean: float, threshold: float) -> tuple[list[Check], dict]`, `gate.evaluate(spec, frames, tiers, allowed, ledger, *, cutoff=None) -> GateResult`.

- [ ] **Step 1: Write the bar before any number exists** — `lab/ACCEPTANCE.md`

```markdown
# The bar an intraday strategy has to clear

Written 2026-10-15, before any strategy had been run. A bar set after the numbers arrive is
not a bar. The thresholds live in `lab/config.py` and are fingerprinted; this file says why.

A strategy passes only if **all** hold on net-of-cost results, judged on development data:

1. **Enough evidence:** at least 400 trades on at least 150 distinct days.
2. **Positive expectancy** on the day-level series. The day is the unit, not the trade:
   trades on one day share a market, so trade-level t-stats run far too high.
3. **Deflated t:** the day-level t must reach `max(2.5, E[max t over N null trials])`, where N is
   the number of strategies ever evaluated (the trial ledger). Every idea tried — kept or
   rejected — raises the bar for the next, so searching harder cannot manufacture a pass.
4. **Both halves positive** when development is split in time.
5. **No single year carries it:** drop the best year, expectancy stays positive (needs 2+ years).
6. **Cost stress:** with costs doubled, expectancy is still positive.
7. **Sealed holdout:** the most recent 6 months are never read by search or by the LLM. Only if
   1-6 pass is the holdout opened, once per strategy, and it must show at least 30 trades,
   positive expectancy, and at least half of development's. The caller sees pass/fail, not numbers.
   After 5 looks the holdout is burned and must be rolled forward; the gate refuses until then.

A strategy fingerprint can be evaluated once. A rejected fingerprint is recorded, not retried
with a nudged threshold — nudging produces a new fingerprint, a new trial, and a higher bar.
"No strategy found" is a valid outcome of the lab.

## What this does not claim

The deflated threshold is the expected maximum of N independent null t-statistics, in the
spirit of the Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014). It is not that exact
statistic, and trials are not truly independent, so it is an approximation to be read as
"the bar rises with the search", not as a p-value.
```

- [ ] **Step 2: Failing stats/ledger tests**

`lab/tests/test_stats.py`
```python
import numpy as np

from lab import stats


def test_t_stat_basics():
    assert stats.t_stat(np.array([1.0])) == 0.0 and stats.t_stat(np.array([2.0, 2.0])) == 0.0
    assert stats.t_stat(np.array([1.0, 2.0, 3.0, 4.0])) > 2.5


def test_threshold_rises_with_trials_and_never_below_base():
    assert stats.deflated_threshold(1, 2.5) == 2.5
    assert stats.deflated_threshold(10, 2.5) >= 2.5
    assert stats.deflated_threshold(10_000, 2.5) > stats.deflated_threshold(100, 2.5) >= 2.5
```

`lab/tests/test_trials.py`
```python
import pytest

from lab.trials import Ledger, LedgerError


def test_append_only_and_counts(tmp_path):
    led = Ledger(tmp_path / "t.jsonl")
    assert led.count() == 0
    led.append({"fingerprint": "a", "verdict": "fail", "holdout_look": False})
    led.append({"fingerprint": "b", "verdict": "pass", "holdout_look": True})
    assert led.count() == 2 and led.has("a") and not led.has("z") and led.holdout_looks() == 1
    assert len((tmp_path / "t.jsonl").read_text().splitlines()) == 2


def test_corrupt_line_is_refused_not_skipped(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"fingerprint": "a"}\nnot json\n')
    with pytest.raises(LedgerError):
        Ledger(p).count()
    with pytest.raises(LedgerError):
        Ledger(p).append({"fingerprint": "b"})  # never extend a ledger we cannot read
```

- [ ] **Step 3: Implement `lab/stats.py` and `lab/trials.py`**

`lab/stats.py`
```python
import math
from statistics import NormalDist

import numpy as np

EULER_GAMMA = 0.5772156649015329


def t_stat(x: np.ndarray) -> float:
    if len(x) < 2:
        return 0.0
    sd = float(np.std(x, ddof=1))
    return 0.0 if sd == 0 else float(np.mean(x)) / (sd / math.sqrt(len(x)))


def deflated_threshold(n_trials: int, base: float) -> float:
    """Expected maximum of n independent null t statistics (Bailey & Lopez de Prado's
    approximation), floored at `base`. One trial needs only the base."""
    if n_trials < 2:
        return base
    inv = NormalDist().inv_cdf
    e_max = (1 - EULER_GAMMA) * inv(1 - 1 / n_trials) + EULER_GAMMA * inv(1 - 1 / (n_trials * math.e))
    return max(base, e_max)
```

`lab/trials.py`
```python
"""The trial ledger: every strategy ever evaluated, pass or fail. Append-only; the count is
what raises the gate's bar, so an unrecorded trial would be a free look."""
import json
from pathlib import Path

DEFAULT = Path(__file__).parent / "trials.jsonl"


class LedgerError(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: Path = DEFAULT):
        self.path = Path(path)

    def read(self) -> "list[dict]":
        if not self.path.exists():
            return []
        rows = []
        for n, line in enumerate(self.path.read_text().splitlines(), 1):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                raise LedgerError(f"{self.path}:{n} is not valid JSON; refusing to count trials") from None
        return rows

    def count(self) -> int:
        return len(self.read())

    def has(self, fingerprint: str) -> bool:
        return any(r.get("fingerprint") == fingerprint for r in self.read())

    def holdout_looks(self) -> int:
        return sum(1 for r in self.read() if r.get("holdout_look"))

    def append(self, rec: dict) -> None:
        self.read()  # validates; a ledger we cannot read is never extended
        with self.path.open("a") as f:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
            f.flush()
```

- [ ] **Step 4: Failing gate tests** — `lab/tests/test_gate.py`

```python
import numpy as np
import pandas as pd
import pytest

from lab import config, gate
from lab.spec import Spec
from lab.tests.conftest import random_walk, sessions
from lab.trials import Ledger


def trades_from_daily(net_by_day, per_day=3):
    rows = [(d, v) for d, v in net_by_day for _ in range(per_day)]
    return pd.DataFrame(rows, columns=["day", "net"])


def series(seed, mean, years=3, sd=0.004):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-01-04", periods=250 * years).date
    return list(zip(days, rng.normal(mean, sd, len(days))))


def verdict(checks):
    return {c.name: c.ok for c in checks}


def test_a_planted_edge_passes_every_development_check():
    checks, m = gate.dev_checks(trades_from_daily(series(1, 0.002)), 0.001, 2.5)
    assert all(c.ok for c in checks), verdict(checks)
    assert m["n_trades"] >= config.MIN_TRADES


def test_pure_noise_fails_the_t_bar():
    checks, _ = gate.dev_checks(trades_from_daily(series(2, 0.0)), 0.0, 2.5)
    assert not all(c.ok for c in checks)


def test_an_edge_from_one_year_fails_drop_best_year():
    days = series(3, 0.0)
    bumped = [(d, v + (0.01 if d.year == 2021 else -0.0005)) for d, v in days]
    v = verdict(gate.dev_checks(trades_from_daily(bumped), 0.001, 2.5)[0])
    assert v["positive_expectancy"] and not v["drop_best_year"]


def test_a_higher_threshold_can_fail_the_same_edge():
    t = trades_from_daily(series(4, 0.0008))
    low = verdict(gate.dev_checks(t, 0.0005, 2.0)[0])["deflated_t"]
    high = verdict(gate.dev_checks(t, 0.0005, 30.0)[0])["deflated_t"]
    assert low and not high


@pytest.mark.parametrize("n", [0, 1])
def test_zero_or_one_trade_fails_with_reasons_and_no_crash(n):
    t = trades_from_daily([(pd.Timestamp("2024-03-04").date(), 0.01)] * n, per_day=1)
    checks, m = gate.dev_checks(t, 0.0, 2.5)
    assert not all(c.ok for c in checks) and not verdict(checks)["min_trades"]


SPEC = Spec.from_dict({"name": "t", "family": "gap_fade", "timeframe": "5Min",
                       "params": {"gap_pct": 0.002, "entry_bar": 1},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "gap downs mean-revert"})


def test_evaluate_records_the_trial_and_refuses_a_repeat(tmp_path):
    led = Ledger(tmp_path / "t.jsonl")
    frames = {"A": sessions(random_walk(n_days=40))}
    res = gate.evaluate(SPEC, frames, {"A": "large"}, None, led)
    assert not res.passed and led.count() == 1
    assert led.read()[0]["fingerprint"] == SPEC.fingerprint()
    with pytest.raises(gate.AlreadyTried):
        gate.evaluate(SPEC, frames, {"A": "large"}, None, led)
    assert led.count() == 1


def test_evaluate_refuses_a_corrupt_ledger_without_a_verdict(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("garbage\n")
    with pytest.raises(Exception):
        gate.evaluate(SPEC, {"A": sessions(random_walk())}, {"A": "large"}, None, Ledger(p))


def test_the_holdout_is_burned_after_the_allowed_looks(tmp_path, monkeypatch):
    led = Ledger(tmp_path / "t.jsonl")
    for i in range(config.MAX_HOLDOUT_LOOKS):
        led.append({"fingerprint": f"x{i}", "holdout_look": True})
    monkeypatch.setattr(gate, "dev_checks", lambda *a, **k: ([gate.Check("all", True, "")], {"mean_bps": 5}))
    res = gate.evaluate(SPEC, {"A": sessions(random_walk())}, {"A": "large"}, None, led)
    assert not res.passed and any("exhausted" in c.detail for c in res.checks)
```

- [ ] **Step 5: Failing sealed-holdout test** — `lab/tests/test_sealed.py`

```python
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]


def test_only_the_gate_reads_trades_after_the_cutoff():
    """`.after(` is how a result is cut to the holdout. If anything but gate.py does it, the
    LLM-facing paths can see the sealed period."""
    offenders = [p.name for p in LAB.rglob("*.py")
                 if "tests" not in p.parts and p.name not in ("gate.py", "backtest.py")
                 and ".after(" in p.read_text()]
    assert offenders == []
```

- [ ] **Step 6: Implement `lab/gate.py`**

```python
"""The deterministic verdict. See lab/ACCEPTANCE.md for the bar and why. The only module
allowed to read the sealed holdout (`BacktestResult.after`); a test enforces it."""
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lab import backtest, config, data, stats


class AlreadyTried(RuntimeError):
    pass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class GateResult:
    passed: bool
    checks: "list[Check]"
    metrics: dict
    fingerprint: str
    holdout_look: bool = False


def _bps(x) -> float:
    return float(x) * 1e4


def dev_checks(trades: pd.DataFrame, stress_mean: float, threshold: float):
    n = len(trades)
    daily = trades.groupby("day")["net"].mean() if n else pd.Series(dtype=float)
    nd = len(daily)
    mean = float(daily.mean()) if nd else 0.0
    t = stats.t_stat(daily.to_numpy())
    half = nd // 2
    h1 = float(daily.iloc[:half].mean()) if half else 0.0
    h2 = float(daily.iloc[half:].mean()) if nd - half else 0.0

    by_year = pd.Series(daily.to_numpy(), index=[d.year for d in daily.index]).groupby(level=0)
    years = by_year.agg(["mean", "sum", "count"]) if nd else pd.DataFrame(columns=["mean", "sum", "count"])
    if len(years) >= config.MIN_YEARS:
        best = years["sum"].idxmax()
        rest = daily[[d.year != best for d in daily.index]]
        no_single_year, year_detail = bool(len(rest) and rest.mean() > 0), f"without {best}: {_bps(rest.mean()):+.1f} bps"
    else:
        no_single_year, year_detail = False, f"{len(years)} year(s) of data, need {config.MIN_YEARS}"

    checks = [
        Check("min_trades", n >= config.MIN_TRADES, f"{n} trades, need {config.MIN_TRADES}"),
        Check("min_days", nd >= config.MIN_DAYS, f"{nd} days, need {config.MIN_DAYS}"),
        Check("positive_expectancy", mean > 0, f"{_bps(mean):+.1f} bps per day"),
        Check("deflated_t", t >= threshold, f"t={t:.2f}, needs {threshold:.2f}"),
        Check("both_halves", h1 > 0 and h2 > 0, f"{_bps(h1):+.1f} / {_bps(h2):+.1f} bps"),
        Check("drop_best_year", no_single_year, year_detail),
        Check("cost_stress", stress_mean > 0, f"{_bps(stress_mean):+.1f} bps at {config.STRESS_MULT}x costs"),
    ]
    wins, losses = trades["net"][trades["net"] > 0].sum(), -trades["net"][trades["net"] < 0].sum()
    sd = float(daily.std(ddof=1)) if nd > 1 else 0.0
    metrics = {
        "n_trades": n, "n_days": nd, "mean_bps": _bps(mean), "t": t, "threshold": threshold,
        "win_rate": float((trades["net"] > 0).mean()) if n else 0.0,
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "sharpe": float(mean / sd * np.sqrt(252)) if sd > 0 else 0.0,
        "halves_bps": [_bps(h1), _bps(h2)],
        "years": {int(y): {"mean_bps": _bps(r["mean"]), "days": int(r["count"])} for y, r in years.iterrows()},
    }
    return checks, metrics


def _holdout_check(hold: "backtest.BacktestResult", dev_mean_bps: float) -> Check:
    f = hold.frame()
    mean = _bps(hold.daily_mean().mean()) if len(f) else 0.0
    ok = len(f) >= config.MIN_HOLDOUT_TRADES and mean > 0 and mean >= config.HOLDOUT_MIN_RATIO * dev_mean_bps
    return Check("holdout", ok, "passed" if ok else "failed")  # never the numbers


def evaluate(spec, frames, tiers, allowed, ledger, *, cutoff=None) -> GateResult:
    fp = spec.fingerprint()
    if ledger.has(fp):
        raise AlreadyTried(f"{fp} was already evaluated; a nudged spec is a new fingerprint and a new trial")
    threshold = stats.deflated_threshold(ledger.count() + 1, config.BASE_T)
    cutoff = cutoff if cutoff is not None else data.dev_cutoff(frames)

    full = backtest.run(spec, frames, tiers, allowed=allowed)
    stress = backtest.run(spec, frames, tiers, allowed=allowed, cost_mult=config.STRESS_MULT).before(cutoff)
    stress_daily = stress.daily_mean()
    checks, metrics = dev_checks(full.before(cutoff).frame(),
                                 float(stress_daily.mean()) if len(stress_daily) else 0.0, threshold)

    looked = False
    if all(c.ok for c in checks):
        if ledger.holdout_looks() >= config.MAX_HOLDOUT_LOOKS:
            checks.append(Check("holdout", False, "holdout exhausted; roll the window forward"))
        else:
            looked = True
            checks.append(_holdout_check(full.after(cutoff), metrics["mean_bps"]))
    passed = all(c.ok for c in checks)
    ledger.append({
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fingerprint": fp,
        "name": spec.name, "family": spec.family, "timeframe": spec.timeframe,
        "params": spec.params, "risk": spec.canonical()["risk"], "hypothesis": spec.hypothesis,
        "verdict": "pass" if passed else "fail",
        "failed": [c.name for c in checks if not c.ok], "threshold": threshold,
        "rules_version": config.rules_version(), "holdout_look": looked,
        "n_trades": metrics["n_trades"], "mean_bps": metrics["mean_bps"], "t": metrics["t"],
    })
    return GateResult(passed, checks, metrics, fp, looked)
```

- [ ] **Step 7: Run** — `.venv/bin/python -m pytest lab/tests -q` → PASS. If `test_the_holdout_is_burned...` fails because `dev_checks` is referenced inside `evaluate` by module-global name, it works with `monkeypatch.setattr(gate, ...)`; do not change the test.

- [ ] **Step 8: Commit**

```bash
git add lab && git commit -m "feat(lab): the deterministic gate, trial ledger and written acceptance bar

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 6: Universe and tiers

**Files:**
- Create: `lab/universe.py`, `lab/tests/test_universe.py`

**Interfaces:**
- Produces: `freeze(dollar_volume: DataFrame, size: int = config.UNIVERSE_SIZE) -> dict[int, list[str]]` (year → symbols, ranked on the **previous** year); `allowed_years(membership) -> dict[str, set[int]]`; `tiers_from(membership) -> dict[str, str]`; `version(membership) -> str`.

- [ ] **Step 1: Failing test** — `lab/tests/test_universe.py`

```python
import pandas as pd

from lab import universe


def dv():
    idx = pd.to_datetime(["2022-06-01", "2023-06-01", "2023-07-03"])
    return pd.DataFrame({"AAA": [9, 1, 1], "BBB": [5, 8, 8], "CCC": [1, 9, 9]}, index=idx)


def test_membership_for_a_year_is_ranked_on_the_year_before():
    m = universe.freeze(dv(), size=2)
    assert m[2023] == ["AAA", "BBB"]     # ranked on 2022
    assert m[2024] == ["CCC", "BBB"]     # ranked on 2023
    assert 2022 not in m                 # no prior year to rank on


def test_allowed_years_and_tiers():
    m = universe.freeze(dv(), size=2)
    assert universe.allowed_years(m) == {"AAA": {2023}, "BBB": {2023, 2024}, "CCC": {2024}}
    t = universe.tiers_from(m)
    assert t["CCC"] == "mega" and t["AAA"] == "large"  # tiers follow the latest year's order


def test_version_changes_when_membership_changes():
    m = universe.freeze(dv(), size=2)
    assert universe.version(m) == universe.version(dict(m))
    assert universe.version(m) != universe.version({**m, 2024: ["AAA"]})
```

- [ ] **Step 2: Implement `lab/universe.py`**

```python
"""A fixed liquid universe, point in time. Membership for year Y is ranked on year Y-1's mean
daily dollar volume, so no year's list knows anything from that year. Survivorship caveat:
candidate symbols come from today's S&P 500, so names that left the index are absent."""
import hashlib
import json

import pandas as pd

from lab import config


def freeze(dollar_volume: pd.DataFrame, size: int = config.UNIVERSE_SIZE) -> "dict[int, list[str]]":
    by_year = dollar_volume.groupby(dollar_volume.index.year).mean()
    return {int(y) + 1: list(row.dropna().sort_values(ascending=False).head(size).index)
            for y, row in by_year.iterrows()}


def allowed_years(membership: "dict[int, list[str]]") -> "dict[str, set[int]]":
    out: "dict[str, set[int]]" = {}
    for year, symbols in membership.items():
        for s in symbols:
            out.setdefault(s, set()).add(year)
    return out


def tiers_from(membership: "dict[int, list[str]]") -> "dict[str, str]":
    from lab import costs
    latest = membership[max(membership)]
    tiers = {s: "large" for s in allowed_years(membership)}
    tiers.update({s: costs.tier_for(rank) for rank, s in enumerate(latest)})
    return tiers


def version(membership: "dict[int, list[str]]") -> str:
    blob = json.dumps({str(k): v for k, v in sorted(membership.items())}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]
```

- [ ] **Step 3: Run and commit**

Run: `.venv/bin/python -m pytest lab/tests/test_universe.py -q` → PASS.

```bash
git add lab && git commit -m "feat(lab): point-in-time liquid universe and liquidity tiers

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 7: Lifecycle registry with frozen failure rules

**Files:**
- Create: `lab/lifecycle.py`, `lab/tests/test_lifecycle.py`

**Interfaces:**
- Consumes: `Spec` (Task 2).
- Produces: `LifecycleError`; `Registry(path=DEFAULT)` with `.register(spec) -> str` (fingerprint), `.advance(fp, to, *, reason, approved_by=None, failure_rules=None)`, `.get(fp) -> dict`, `.all() -> dict[str, dict]`, `.apply_failure_rules(fp, live: dict) -> list[str]` (names of tripped rules; retires the strategy if any). A failure rule is `{"metric": str, "op": "lt"|"gt", "threshold": float, "after_trades": int}`.

- [ ] **Step 1: Failing test** — `lab/tests/test_lifecycle.py`

```python
import pytest

from lab.lifecycle import LifecycleError, Registry
from lab.spec import Spec

SPEC = Spec.from_dict({"name": "t", "family": "orb", "timeframe": "5Min", "params": {},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "breakouts continue"})
RULES = [{"metric": "mean_bps", "op": "lt", "threshold": 0.0, "after_trades": 30}]


def shadowed(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    reg.advance(fp, "backtested", reason="ran the gate")
    reg.advance(fp, "shadow", reason="passed", failure_rules=RULES)
    return reg, fp


def test_the_happy_path_and_persistence(tmp_path):
    reg, fp = shadowed(tmp_path)
    reg.advance(fp, "paper", reason="owner approved", approved_by="owner")
    assert Registry(tmp_path / "r.json").get(fp)["stage"] == "paper"


def test_illegal_jumps_are_refused(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    with pytest.raises(LifecycleError):
        reg.advance(fp, "paper", reason="skip", approved_by="owner")


def test_paper_needs_a_human_approval(tmp_path):
    reg, fp = shadowed(tmp_path)
    with pytest.raises(LifecycleError):
        reg.advance(fp, "paper", reason="auto")


def test_shadow_needs_failure_rules_and_they_cannot_be_edited(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    reg.advance(fp, "backtested", reason="ran")
    with pytest.raises(LifecycleError):
        reg.advance(fp, "shadow", reason="no rules")
    reg.advance(fp, "shadow", reason="ok", failure_rules=RULES)
    assert reg.get(fp)["failure_rules"] == RULES
    with pytest.raises(LifecycleError):
        reg.advance(fp, "paper", reason="try to loosen", approved_by="o", failure_rules=[])


def test_rejected_and_retired_are_terminal_and_not_reregisterable(tmp_path):
    reg = Registry(tmp_path / "r.json")
    fp = reg.register(SPEC)
    reg.advance(fp, "backtested", reason="ran")
    reg.advance(fp, "rejected", reason="failed t bar")
    with pytest.raises(LifecycleError):
        reg.advance(fp, "shadow", reason="again", failure_rules=RULES)
    with pytest.raises(LifecycleError):
        reg.register(SPEC)


def test_a_tripped_failure_rule_retires_the_strategy(tmp_path):
    reg, fp = shadowed(tmp_path)
    assert reg.apply_failure_rules(fp, {"n_trades": 10, "mean_bps": -5}) == []  # too early
    assert reg.apply_failure_rules(fp, {"n_trades": 40, "mean_bps": 3}) == []
    assert reg.apply_failure_rules(fp, {"n_trades": 40, "mean_bps": -5}) == ["mean_bps lt 0.0"]
    assert reg.get(fp)["stage"] == "retired"
```

- [ ] **Step 2: Implement `lab/lifecycle.py`**

```python
"""Where each strategy is in its life, and the rules it was told it would be judged by.

proposed -> backtested -> rejected | shadow -> paper -> kept -> retired
Rejected and retired are terminal for a fingerprint. Failure rules are attached on entry to
shadow and are never editable afterwards: the skill may propose a successor spec, not an excuse.
Moving to paper needs a named human; this module cannot approve for you.
"""
import json
import time
from pathlib import Path

DEFAULT = Path(__file__).parent / "registry.json"
ALLOWED = {
    "proposed": {"backtested"}, "backtested": {"rejected", "shadow"},
    "shadow": {"paper", "retired"}, "paper": {"kept", "retired"},
    "kept": {"retired"}, "rejected": set(), "retired": set(),
}
OPS = {"lt": lambda a, b: a < b, "gt": lambda a, b: a > b}


class LifecycleError(ValueError):
    pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Registry:
    def __init__(self, path: Path = DEFAULT):
        self.path = Path(path)

    def all(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def get(self, fp: str) -> dict:
        try:
            return self.all()[fp]
        except KeyError:
            raise LifecycleError(f"unknown strategy {fp}") from None

    def _save(self, d: dict) -> None:
        self.path.write_text(json.dumps(d, indent=2, sort_keys=True))

    def register(self, spec) -> str:
        d, fp = self.all(), spec.fingerprint()
        if fp in d:
            raise LifecycleError(f"{fp} is already {d[fp]['stage']}; a fingerprint is tried once")
        d[fp] = {"spec": spec.to_dict(), "stage": "proposed", "failure_rules": None,
                 "approved_by": None, "history": [{"stage": "proposed", "when": _now(), "reason": "registered"}]}
        self._save(d)
        return fp

    def advance(self, fp, to, *, reason, approved_by=None, failure_rules=None) -> None:
        d = self.all()
        entry = d.get(fp)
        if entry is None:
            raise LifecycleError(f"unknown strategy {fp}")
        if to not in ALLOWED[entry["stage"]]:
            raise LifecycleError(f"{entry['stage']} -> {to} is not allowed")
        if failure_rules is not None and entry["failure_rules"] is not None:
            raise LifecycleError("failure rules are frozen")
        if to == "shadow":
            if not failure_rules:
                raise LifecycleError("entering shadow requires pre-registered failure rules")
            entry["failure_rules"] = failure_rules
        if to == "paper":
            if not approved_by:
                raise LifecycleError("moving to paper needs a named human approval")
            entry["approved_by"] = approved_by
        entry["stage"] = to
        entry["history"].append({"stage": to, "when": _now(), "reason": reason})
        self._save(d)

    def apply_failure_rules(self, fp: str, live: dict) -> "list[str]":
        entry = self.get(fp)
        tripped = [f"{r['metric']} {r['op']} {r['threshold']}" for r in entry["failure_rules"] or []
                   if live.get("n_trades", 0) >= r["after_trades"]
                   and OPS[r["op"]](live[r["metric"]], r["threshold"])]
        if tripped:
            self.advance(fp, "retired", reason="failure rule tripped: " + "; ".join(tripped))
        return tripped
```

- [ ] **Step 3: Run and commit**

Run: `.venv/bin/python -m pytest lab/tests/test_lifecycle.py -q` → PASS.

```bash
git add lab && git commit -m "feat(lab): strategy lifecycle with frozen failure rules and human approval to paper

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 8: `lab.json` export

**Files:**
- Create: `lab/export.py`, `lab/tests/test_export.py`

**Interfaces:**
- Consumes: `Registry.all()`, `Ledger.read()`, per-strategy results `{fp: {"metrics": dict, "trades": DataFrame (BacktestResult.frame() for the development window), "equity": DataFrame (equity_curve())}}`.
- Produces: `build(registry_rows, ledger_rows, results, *, generated_at, universe_version) -> dict`; `validate(doc) -> list[str]` (problems; empty = valid); `write(path, doc)`.
- Contract (the later Lab tab is a pure renderer of this): top level `meta, account, equity_curve, summary, strategies, positions, trades, trials, runs`; `account/equity_curve/positions/runs` are `null/[]` until paper trading exists (sub-project 2). Each strategy carries `breakdowns`.

- [ ] **Step 1: Failing test** — `lab/tests/test_export.py`

```python
import pandas as pd

from lab import backtest, export
from lab.spec import Spec
from lab.tests.conftest import random_walk, sessions

SPEC = Spec.from_dict({"name": "gap", "family": "gap_fade", "timeframe": "5Min",
                       "params": {"gap_pct": 0.002, "entry_bar": 1},
                       "risk": {"stop_pct": 0.01, "target_pct": 0.02, "max_hold_bars": 30},
                       "hypothesis": "gap downs mean-revert"})


def doc():
    res = backtest.run(SPEC, {"A": sessions(random_walk(n_days=40))}, {"A": "large"})
    fp = SPEC.fingerprint()
    registry = {fp: {"spec": SPEC.to_dict(), "stage": "backtested", "failure_rules": None,
                     "approved_by": None, "history": [{"stage": "backtested", "when": "2026-10-15T00:00:00Z", "reason": "ran"}]}}
    ledger = [{"fingerprint": fp, "verdict": "fail", "failed": ["min_trades"], "when": "2026-10-15T00:00:00Z",
               "name": "gap", "family": "gap_fade"}]
    results = {fp: {"metrics": {"n_trades": len(res.trades), "mean_bps": 1.0}, "trades": res.frame(),
                    "equity": res.equity_curve()}}
    return export.build(registry, ledger, results, generated_at="2026-10-15T00:00:00Z", universe_version="abc")


def test_a_built_document_is_valid_and_json_serialisable():
    import json
    d = doc()
    assert export.validate(d) == []
    json.dumps(d)  # no timestamps, dates or numpy scalars left over


def test_trades_carry_costs_and_every_breakdown_the_tab_needs():
    d = doc()
    t = d["trades"][0]
    assert {"strategy", "symbol", "side", "entry_time", "exit_time", "entry_px", "exit_px",
            "bars_held", "exit_reason", "gross_bps", "cost_bps", "net_bps"} <= set(t)
    b = d["strategies"][0]["breakdowns"]
    assert {"by_symbol", "by_hour", "by_weekday", "daily_pnl", "exit_reasons", "histogram"} <= set(b)


def test_validate_names_what_is_missing():
    d = doc()
    del d["strategies"][0]["stage"]
    d.pop("trials")
    problems = export.validate(d)
    assert any("trials" in p for p in problems) and any("stage" in p for p in problems)


def test_a_strategy_with_no_trades_still_exports():
    d = doc()
    fp = d["strategies"][0]["fingerprint"]
    empty = export.build({fp: {"spec": SPEC.to_dict(), "stage": "rejected", "failure_rules": None, "approved_by": None, "history": []}},
                         [], {fp: {"metrics": {}, "trades": pd.DataFrame(columns=["symbol", "entry_time", "exit_time", "entry_px", "exit_px", "bars_held", "exit_reason", "gross", "net", "day"]), "equity": pd.DataFrame(columns=["t", "equity", "drawdown"])}},
                         generated_at="x", universe_version="y")
    assert export.validate(empty) == [] and empty["trades"] == []
```

- [ ] **Step 2: Implement `lab/export.py`**

```python
"""Writes lab.json, the single contract behind the Lab tab. Everything the page shows is
precomputed here, so the page is a renderer and needs no market logic of its own."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab import config
from lab.data import ET

TOP = ("meta", "account", "equity_curve", "summary", "strategies", "positions", "trades", "trials", "runs")
STRATEGY = ("id", "fingerprint", "name", "family", "stage", "hypothesis", "params", "risk",
            "failure_rules", "backtest", "live", "equity_curve", "history", "breakdowns")
BREAKDOWNS = ("by_symbol", "by_hour", "by_weekday", "daily_pnl", "exit_reasons", "histogram")


def _bps(x) -> float:
    return round(float(x) * 1e4, 2)


def _trade_rows(fp: str, f: pd.DataFrame) -> "list[dict]":
    rows = []
    for r in f.itertuples():
        rows.append({
            "strategy": fp, "symbol": r.symbol, "side": "long",
            "entry_time": r.entry_time.isoformat(), "exit_time": r.exit_time.isoformat(),
            "entry_px": round(float(r.entry_px), 4), "exit_px": round(float(r.exit_px), 4),
            "bars_held": int(r.bars_held), "exit_reason": r.exit_reason,
            "gross_bps": _bps(r.gross), "cost_bps": _bps(r.gross - r.net), "net_bps": _bps(r.net)})
    return rows


def _breakdowns(f: pd.DataFrame) -> dict:
    if f.empty:
        return {k: ([] if k != "exit_reasons" else {}) for k in BREAKDOWNS}
    et = f["entry_time"].dt.tz_convert(ET)
    net = f["net"]

    def grouped(key):
        g = net.groupby(key).agg(["sum", "mean", "count"])
        return [{"key": str(k), "net_bps": _bps(r["mean"]), "total_pct": round(float(r["sum"]) * 100, 3),
                 "trades": int(r["count"])} for k, r in g.iterrows()]

    counts, edges = np.histogram(net.to_numpy() * 1e4, bins=20)
    return {
        "by_symbol": grouped(f["symbol"]), "by_hour": grouped(et.dt.hour),
        "by_weekday": grouped(et.dt.day_name()),
        "daily_pnl": [{"day": str(d), "net_bps": _bps(v)} for d, v in net.groupby(f["day"]).mean().items()],
        "exit_reasons": {k: int(v) for k, v in f["exit_reason"].value_counts().items()},
        "histogram": [{"from_bps": round(float(edges[i]), 2), "to_bps": round(float(edges[i + 1]), 2),
                       "count": int(counts[i])} for i in range(len(counts))],
    }


def build(registry: dict, ledger: "list[dict]", results: dict, *, generated_at: str,
          universe_version: str) -> dict:
    strategies, trades = [], []
    for fp, entry in registry.items():
        res = results.get(fp, {})
        f = res.get("trades", pd.DataFrame())
        curve = res.get("equity", pd.DataFrame(columns=["t", "equity", "drawdown"]))
        spec = entry["spec"]
        strategies.append({
            "id": fp, "fingerprint": fp, "name": spec["name"], "family": spec["family"],
            "stage": entry["stage"], "hypothesis": spec["hypothesis"], "params": spec["params"],
            "risk": spec["risk"], "failure_rules": entry.get("failure_rules"),
            "backtest": res.get("metrics", {}), "live": None,
            "equity_curve": [{"t": str(r.t), "equity": round(float(r.equity), 2),
                              "drawdown": round(float(r.drawdown), 5)} for r in curve.itertuples()],
            "history": entry.get("history", []), "breakdowns": _breakdowns(f),
        })
        trades += _trade_rows(fp, f) if len(f) else []
    live = [s for s in strategies if s["stage"] in ("shadow", "paper", "kept")]
    return {
        "meta": {"generated_at": generated_at, "universe_version": universe_version,
                 "rules_version": config.rules_version(), "trials_total": len(ledger),
                 "holdout_months": config.HOLDOUT_MONTHS, "cost_bps_per_side": config.COST_BPS_PER_SIDE},
        "account": None, "equity_curve": [], "positions": [], "runs": [],
        "summary": {"strategies": len(strategies), "live": len(live),
                    "rejected": sum(s["stage"] == "rejected" for s in strategies),
                    "retired": sum(s["stage"] == "retired" for s in strategies),
                    "trials": len(ledger), "passed": sum(r.get("verdict") == "pass" for r in ledger)},
        "strategies": strategies, "trades": trades, "trials": ledger,
    }


def validate(doc: dict) -> "list[str]":
    problems = [f"missing top-level key: {k}" for k in TOP if k not in doc]
    for s in doc.get("strategies", []):
        problems += [f"strategy {s.get('id', '?')} missing: {k}" for k in STRATEGY if k not in s]
        problems += [f"strategy {s.get('id', '?')} breakdowns missing: {k}"
                     for k in BREAKDOWNS if k not in s.get("breakdowns", {})]
    return problems


def write(path, doc: dict) -> None:
    problems = validate(doc)
    if problems:
        raise ValueError("; ".join(problems))
    Path(path).write_text(json.dumps(doc, separators=(",", ":")))
```

- [ ] **Step 3: Run and commit**

Run: `.venv/bin/python -m pytest lab/tests/test_export.py -q` → PASS.

```bash
git add lab && git commit -m "feat(lab): lab.json export, the contract behind the Lab tab

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

### Task 9: CLI, docs and the full suite

**Files:**
- Create: `lab/run.py`, `lab/tests/test_run.py`
- Modify: `CLAUDE.md` (Commands block + Layout), `docs/superpowers/specs/2026-10-15-intraday-lab-foundation-design.md` (record deviations)

**Interfaces:**
- Consumes: everything above. Credentials from `ALPACA_KEY_ID` / `ALPACA_SECRET_KEY`.
- Produces: `python -m lab.run fetch | backtest SPEC.json | export --out PATH`. `main(argv) -> int`.

- [ ] **Step 1: Failing test** — `lab/tests/test_run.py`

```python
import json

import pytest

from lab import run


def test_help_lists_the_three_commands(capsys):
    with pytest.raises(SystemExit):
        run.main(["--help"])
    out = capsys.readouterr().out
    assert all(c in out for c in ("fetch", "backtest", "export"))


def test_backtest_rejects_a_bad_spec_before_touching_the_network(tmp_path, capsys):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"family": "nope"}))
    assert run.main(["backtest", str(p)]) == 2
    assert "unknown family" in capsys.readouterr().err
```

- [ ] **Step 2: Implement `lab/run.py`**

```python
"""Command line for the lab. `fetch` pulls bars and freezes the universe; `backtest` runs a
spec through the gate (and appends the trial); `export` writes lab.json. Nothing here trades."""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from lab import backtest, data, export, gate, universe
from lab.lifecycle import Registry
from lab.spec import Spec, SpecError
from lab.trials import Ledger

HERE = Path(__file__).parent
MEMBERSHIP = HERE / ".cache" / "membership.json"
RESULTS = HERE / "results"
YEARS_BACK = 8


def _client():
    from trader.alpaca import Alpaca
    return Alpaca(os.environ["ALPACA_KEY_ID"], os.environ["ALPACA_SECRET_KEY"])


def _start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=365 * YEARS_BACK)


def cmd_fetch(args) -> int:
    from scanner.universe import load_universe
    client, start = _client(), _start()
    daily = {}
    for sym in load_universe()["ticker"]:
        raw = client.bars(sym.replace("-", "."), "1Day", start, datetime.now(timezone.utc))
        if raw:
            f = data.to_frame(raw)
            daily[sym] = (f["close"] * f["volume"]).rename(sym)
    dv = pd.DataFrame(daily)
    dv.index = dv.index.tz_localize(None)
    membership = universe.freeze(dv)
    MEMBERSHIP.parent.mkdir(parents=True, exist_ok=True)
    MEMBERSHIP.write_text(json.dumps({str(k): v for k, v in membership.items()}))
    for sym in universe.allowed_years(membership):
        for tf in ("5Min",):
            data.get(client, sym, tf, start)
    print(f"universe {universe.version(membership)}: {len(universe.allowed_years(membership))} symbols")
    return 0


def _membership() -> dict:
    return {int(k): v for k, v in json.loads(MEMBERSHIP.read_text()).items()}


def _frames(spec, membership):
    client, start = _client(), _start()
    return {s: data.get(client, s, spec.timeframe, start) for s in universe.allowed_years(membership)}


def cmd_backtest(args) -> int:
    try:
        spec = Spec.from_dict(json.loads(Path(args.spec).read_text()))
    except SpecError as e:
        print(f"invalid spec: {e}", file=sys.stderr)
        return 2
    membership = _membership()
    frames = _frames(spec, membership)
    tiers, allowed = universe.tiers_from(membership), universe.allowed_years(membership)
    reg, ledger = Registry(), Ledger()
    fp = reg.register(spec)
    try:
        res = gate.evaluate(spec, frames, tiers, allowed, ledger)
    except gate.AlreadyTried as e:
        print(e, file=sys.stderr)
        return 2
    reg.advance(fp, "backtested", reason="gate evaluated")
    if not res.passed:
        reg.advance(fp, "rejected", reason="failed: " + ", ".join(c.name for c in res.checks if not c.ok))
    full = backtest.run(spec, frames, tiers, allowed=allowed).before(data.dev_cutoff(frames))
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{fp}.json").write_text(json.dumps({
        "metrics": res.metrics, "trades": json.loads(full.frame().to_json(orient="split", date_format="iso")),
        "equity": json.loads(full.equity_curve().to_json(orient="split"))}))
    for c in res.checks:
        print(f"{'PASS' if c.ok else 'FAIL'}  {c.name:<20} {c.detail}")
    print("VERDICT:", "pass -> eligible for shadow" if res.passed else "rejected", f"[{fp}]")
    return 0


def cmd_export(args) -> int:
    reg, ledger = Registry().all(), Ledger().read()
    results = {}
    for fp in reg:
        p = RESULTS / f"{fp}.json"
        if p.exists():
            raw = json.loads(p.read_text())
            trades = pd.DataFrame(**raw["trades"])
            for col in ("entry_time", "exit_time"):
                trades[col] = pd.to_datetime(trades[col], utc=True)
            trades["day"] = [t.tz_convert(data.ET).date() for t in trades["entry_time"]]
            results[fp] = {"metrics": raw["metrics"], "trades": trades,
                           "equity": pd.DataFrame(**raw["equity"])}
    mem = _membership() if MEMBERSHIP.exists() else {}
    doc = export.build(reg, ledger, results, universe_version=universe.version(mem) if mem else "none",
                       generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    export.write(args.out, doc)
    print(f"wrote {args.out}: {len(doc['strategies'])} strategies, {len(doc['trades'])} trades")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lab.run", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="freeze the universe and cache 5-minute bars").set_defaults(fn=cmd_fetch)
    b = sub.add_parser("backtest", help="run a spec through the gate")
    b.add_argument("spec")
    b.set_defaults(fn=cmd_backtest)
    e = sub.add_parser("export", help="write lab.json")
    e.add_argument("--out", default="lab.json")
    e.set_defaults(fn=cmd_export)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

Check `scanner.universe` has a `load_universe` function before relying on it: run `grep -n "^def " scanner/universe.py`; if the name differs (e.g. `get_universe`), use the real one — and fix the import, do not invent.

- [ ] **Step 3: Run the lab tests, then the whole suite**

Run: `.venv/bin/python -m pytest lab/tests -q` → PASS; then `.venv/bin/python -m pytest scanner/tests research/tests trader/tests lab/tests -q` → all PASS (~60s).

- [ ] **Step 4: Document** — in `CLAUDE.md` add to the Commands block:

```bash
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m lab.run fetch             # freeze universe, cache 5-min bars
ALPACA_KEY_ID=... ALPACA_SECRET_KEY=... .venv/bin/python -m lab.run backtest spec.json # gate a strategy spec (appends a trial)
.venv/bin/python -m lab.run export --out lab.json                                       # the Lab tab's data
```

and add to Layout: "`lab/` — the intraday lab: declarative strategy specs over a fixed family registry, a costed backtester, a trial-count-deflated gate with a sealed holdout (`ACCEPTANCE.md` is the bar, `trials.jsonl` the append-only record of every idea tried). Nothing in it places orders. Do not edit `config.py`, `gate.py`, `costs.py` or `ACCEPTANCE.md` to make a strategy pass."

In the spec, replace the `lab.json` tree note with: breakdowns live inside each strategy; per-trade chart bars are deferred to the Lab-tab plan because they need stored bars.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(lab): CLI (fetch, backtest, export) and project docs

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push origin main
```

---

## Self-review against the spec

- **Spec coverage:** data (T3), spec format + families (T2), costs (T4), backtest (T4), gate + deflation + holdout + stress + halves + drop-best-year (T5), trial ledger (T5), lifecycle with frozen rules and human approval (T7), `lab.json` contract (T8), universe frozen point-in-time with tiers (T6), pinned protections: fingerprinted config (T1), sealed-holdout grep test (T5), ledger append-only/corrupt-refusal (T5), lookahead guard over every family (T2), CLI + docs (T9).
- **Deliberate deviations from the spec**, recorded so they are not discovered later: (1) breakdowns sit inside each strategy rather than top-level; (2) per-trade chart bars are deferred to the Lab-tab plan (they need stored bars; the export deliberately has no `charts` key yet); (3) the "deflated" threshold is the expected-max-t approximation, stated as such in `ACCEPTANCE.md`; (4) the holdout is enforced by the `.after(` grep test and the single caller in `gate.py`, not by a separate data loader, because families are causal and trades are cut by entry time.
- **Not in this plan (by design):** shadow runs, order submission, the intraday workflow, the `/lab` skill, the web tab. Task 2 is listed before Task 3 for spec order but **executes after it**; the executor should follow the dependency note, not the numbering.
- **Open items that need a number, not code:** the cost defaults in `config.py` are conservative placeholders until quoted spreads are sampled; the Alpaca free-tier history depth and the PDT rule on paper accounts are unconfirmed. Neither blocks the plan; the first affects every verdict and should be measured before any result is believed.
