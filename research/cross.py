"""Cross-sectional measurement: rules that rank the whole universe against itself.

Everything in `measure.py` scores one ticker at a time, because both shipped strategies read
one ticker at a time. A relative-strength rule cannot be expressed that way -- "is this name
among the strongest" is a question about the other 499 names -- so the panel lives here.

Two things are deliberately kept from `measure.py` rather than rebuilt: `stats` and
`independent`, which `CrossRow` is shaped to satisfy. The third guard is new and belongs to
this file: a cross-sectional rule fires on many names the same day and those names move
together, so `date_collapsed` averages each date to one observation before taking a t-stat.
That is rule 7 in ACCEPTANCE.md, and it is the number to believe.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

WARMUP = 300  # bars skipped at the start, fixed across variants so every lookback scores the same dates
MIN_NAMES = 100  # a date with fewer ranked names is not a cross-section worth ranking


@dataclass(frozen=True)
class CrossConfig:
    """One reading of "go long the strongest mover".

    `lookback` and `skip` define the momentum window: skip=0 is the raw N-day move, and the
    classic equity momentum definition skips the most recent month because the last few weeks
    of a move reverse rather than continue.
    """

    lookback: int = 5  # bars of momentum ("7-day" on daily bars is a trading week)
    skip: int = 0  # bars excluded at the near end of the momentum window
    rank_min: float = 0.95  # percentile of the cross-section that counts as a leader
    on_entry: bool = True  # fire when a name *enters* the leaders, not every day it leads
    require_price_rising: bool = False  # close above its own 50-bar mean
    require_volume_rising: bool = False  # volume at or above its 20-bar median
    require_momentum_rising: bool = False  # the move is still accelerating
    rising_lookback: int = 5
    vol_window: int = 20
    ma_window: int = 50


# The grid, declared in full before any of it was run. The lookback sweep is the decisive
# axis: the crypto rules being translated are all 7-day, and 7 days in equities is the
# short-term reversal window, so the question is whether the horizon or the idea is wrong.
VARIANTS = {
    "mom-5d": CrossConfig(lookback=5),
    "mom-21d": CrossConfig(lookback=21),
    "mom-63d": CrossConfig(lookback=63),
    "mom-126d": CrossConfig(lookback=126),
    "mom-252d-skip21": CrossConfig(lookback=231, skip=21),  # the textbook 12-1 definition
    # Rules 1 and 2 as written, on the horizon they were written for.
    "mom-5d+volume": CrossConfig(lookback=5, require_volume_rising=True),
    "mom-5d+price": CrossConfig(lookback=5, require_price_rising=True),
    "mom-5d+accelerating": CrossConfig(lookback=5, require_momentum_rising=True),
    "mom-5d-full": CrossConfig(lookback=5, require_price_rising=True, require_volume_rising=True,
                               require_momentum_rising=True),
    # The same confirmations on the horizon equities actually reward, if any does.
    "mom-126d-full": CrossConfig(lookback=126, require_price_rising=True,
                                 require_volume_rising=True, require_momentum_rising=True),
    # "Go long the single strongest" -- rule 2's leader, roughly the top 1%.
    "mom-5d-top1pct": CrossConfig(lookback=5, rank_min=0.99),
    "mom-126d-top1pct": CrossConfig(lookback=126, rank_min=0.99),
    # Every bar it leads rather than only the bar it takes the lead, which is what "keep
    # adding while it stays the leader" means. Scored separately because it is a different
    # cohort, not a stricter one.
    "mom-126d-while-leading": CrossConfig(lookback=126, on_entry=False),
    # --- added after the grid above was run, and marked as such ---
    # The first run put the only positive numbers on the textbook 12-1 window and on the
    # top 1% of the cross-section, which the declared grid never crossed with each other.
    # These two do. They are post-hoc and their bar is correspondingly higher: a result that
    # exists only in a variant chosen after seeing the table is a fitted threshold until an
    # out-of-sample run says otherwise.
    "posthoc-252d-skip21-top1pct": CrossConfig(lookback=231, skip=21, rank_min=0.99),
    "posthoc-252d-skip21-while-leading": CrossConfig(lookback=231, skip=21, on_entry=False),
}


@dataclass(frozen=True)
class Panel:
    close: pd.DataFrame  # dates x tickers
    volume: pd.DataFrame


@dataclass(frozen=True)
class CrossRow:
    """Shaped to satisfy measure.stats and measure.independent, plus the date they lack."""

    ticker: str
    bar: int  # positional index of the signal bar in the panel
    year: int
    date: pd.Timestamp
    side: str
    conviction: str
    fwd: float
    baseline: float


def build_panel(bars: "dict[str, pd.DataFrame]") -> Panel:
    """Align every ticker's closes and volumes onto one date index.

    Names list and de-list, so the panel is ragged: a cell is NaN where that name had no bar
    that day, and every computation below has to treat NaN as "not in the cross-section"
    rather than as a value.
    """
    close = pd.DataFrame({t: df["close"] for t, df in bars.items()}).sort_index()
    volume = pd.DataFrame({t: df["volume"] for t, df in bars.items()}).reindex(close.index)
    return Panel(close=close, volume=volume)


def momentum(close: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    """Return over `lookback` bars ending `skip` bars ago."""
    end = close.shift(skip)
    return end / close.shift(skip + lookback) - 1.0


def leaders(panel: Panel, cfg: CrossConfig) -> pd.DataFrame:
    """Boolean panel: True where this name is in the top `rank_min` of the cross-section.

    Ranked as a percentile of the names that have a momentum reading *that day*, so a day
    early in the sample with 120 names ranks those 120 against each other. Days with fewer
    than MIN_NAMES are dropped rather than ranked.
    """
    mom = momentum(panel.close, cfg.lookback, cfg.skip)
    enough = mom.notna().sum(axis=1) >= MIN_NAMES
    rank = mom.rank(axis=1, pct=True, na_option="keep")
    # `.astype(bool)` is load-bearing, not tidiness: a NaN anywhere makes these panels object
    # dtype, and `~` on an object column is bitwise arithmetic on the underlying ints rather
    # than negation. It silently turns False into -1, which is truthy.
    return (rank >= cfg.rank_min).where(enough, False).fillna(False).astype(bool)


def confirmations(panel: Panel, cfg: CrossConfig) -> pd.DataFrame:
    """The "and volume and price keep rising" half of the rules being translated."""
    ok = pd.DataFrame(True, index=panel.close.index, columns=panel.close.columns, dtype=bool)
    if cfg.require_price_rising:
        ok &= panel.close > panel.close.rolling(cfg.ma_window).mean()
    if cfg.require_volume_rising:
        ok &= panel.volume >= panel.volume.rolling(cfg.vol_window).median()
    if cfg.require_momentum_rising:
        mom = momentum(panel.close, cfg.lookback, cfg.skip)
        ok &= mom > mom.shift(cfg.rising_lookback)
    return ok.fillna(False).astype(bool)


def entries(panel: Panel, cfg: CrossConfig) -> pd.DataFrame:
    """Boolean panel of signal bars.

    With `on_entry` (the default) a name fires on the bar it joins the leaders and not again
    until it has dropped out and come back -- which is what makes a shortlist readable, and
    is also the honest unit for measurement: holding a leader for twenty days is one decision,
    not twenty. `on_entry=False` scores the other reading, where every day of leadership is
    its own signal.
    """
    lead = leaders(panel, cfg) & confirmations(panel, cfg)
    if not cfg.on_entry:
        return lead
    return lead & ~lead.shift(1, fill_value=False).astype(bool)


def score(panel: Panel, cfg: CrossConfig, horizon: int) -> "list[CrossRow]":
    """Forward return of every signal, against the same per-ticker baseline measure.py uses."""
    close = panel.close
    fwd = close.shift(-horizon) / close - 1.0
    scorable = fwd.iloc[WARMUP:len(close) - horizon]
    baseline = scorable.mean(axis=0)  # per ticker, over exactly the bars that can be scored
    fired = entries(panel, cfg).iloc[WARMUP:len(close) - horizon]

    rows = []
    positions = {t: i for i, t in enumerate(close.columns)}
    for date, row in fired.iterrows():
        hits = row[row].index
        if hits.empty:
            continue
        i = close.index.get_loc(date)
        for ticker in hits:
            f, b = fwd.at[date, ticker], baseline[ticker]
            if pd.isna(f) or pd.isna(b):
                continue
            rows.append(CrossRow(ticker, i, date.year, date, "BUY", "standard", float(f), float(b)))
    return rows


def date_collapsed(rows: "list[CrossRow]") -> dict:
    """Rule 7: one observation per date, because leaders rise and fall together.

    Every signal that fired on the same day is averaged into a single alpha before the t-stat,
    so a day that flagged forty names counts once. This is the number that decides a ranked
    strategy.
    """
    if not rows:
        return {"n_dates": 0, "alpha_by_date": float("nan"), "t_by_date": float("nan")}
    by_date: "dict[pd.Timestamp, list[float]]" = {}
    for r in rows:
        by_date.setdefault(r.date, []).append(r.fwd - r.baseline)
    daily = np.array([float(np.mean(v)) for v in by_date.values()])
    t = float(daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily)))) if len(daily) > 1 and daily.std(ddof=1) > 0 else float("nan")
    return {"n_dates": len(daily), "alpha_by_date": float(daily.mean()), "t_by_date": t}


def halves(rows: "list[CrossRow]") -> "tuple[list[CrossRow], list[CrossRow]]":
    """Split by calendar date at the midpoint of the signal range, not per ticker: in a
    cross-sectional rule every name shares one timeline."""
    if not rows:
        return [], []
    dates = sorted({r.date for r in rows})
    mid = dates[len(dates) // 2]
    return [r for r in rows if r.date < mid], [r for r in rows if r.date >= mid]


def drop_best_year(rows: "list[CrossRow]") -> "tuple[int, list[CrossRow]]":
    """ACCEPTANCE rule 4, as a function: the year whose removal hurts most, and the rest."""
    years = {r.year for r in rows}
    if len(years) < 2:
        return 0, rows
    best = max(years, key=lambda y: np.mean([r.fwd - r.baseline for r in rows if r.year == y]))
    return best, [r for r in rows if r.year != best]


def variant(label: str, **overrides) -> CrossConfig:
    """A one-off config for an ad-hoc check, built off the named variant."""
    return replace(VARIANTS[label], **overrides)
