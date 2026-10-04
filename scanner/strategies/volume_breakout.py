"""Candidate third strategy: the high-volume breakout.

**Not registered in `STRATEGIES`.** This module exists to be measured. It ships only if it
clears the six rules in `research/ACCEPTANCE.md`, which were written before any of its
numbers existed.

Why this setup and not another volume idea. The one volume effect with independent evidence
behind it outside this repo is the *high-volume return premium*: stocks that trade unusually
heavily over a day or a week tend to outperform over the following month (Gervais, Kaniel and
Mingelgrin, 2001, on NYSE names). The reading is that a volume spike is attention — the name
gets onto more screens, and the visibility itself is worth something for a few weeks. That
effect is the core gate here (`min_rvol`), and everything else in the config is a confluence
condition layered on top of it so each one can be scored separately:

* a breakout — the spike comes on a close at a new N-bar high, not on a collapse;
* a trend filter — above the 200 EMA, so it is an advance rather than a dead-cat bounce;
* close strength — the bar closed in the top of its own range, so the buyers held the day;
* a quiet base — the bars before the spike traded *below* normal, which is the one volume
  reading that has ever measured positive in this repo (`FINDINGS.md`, dryup-0.9);
* OBV above its own average — the flow was already accumulating.

The two existing strategies both fire on an RSI cross. This one never looks at RSI, which is
what gives it a chance of passing rule 6 (not a relabelling of the other two).

Long only. The short legs of both existing strategies measured worthless-to-harmful over the
same 12 years, and there is no reason to expect the mirror of an attention effect to work.
"""
from dataclasses import asdict, dataclass

import pandas as pd

from scanner.indicators import ema, obv, rel_volume
from scanner.strategies.base import SIGNAL_WINDOW, STANDARD, Release, Signal, make_signal

MIN_BARS = 400  # the EMA200 seeding bound from TrendPullback; held constant so variants compare
RVOL_WINDOW = 20
BREAKOUT_LOOKBACK = 50
BASE_WINDOW = 20  # bars before the spike that "quiet base" is measured over


@dataclass(frozen=True)
class VolumeBreakoutConfig:
    """Gates, each one a separate reading of "the volume means something".

    `min_rvol` is the core effect and is always on; everything else defaults to off so the
    core can be scored alone first and each confluence condition measured against it.
    """

    min_rvol: float = 2.0  # the spike itself: volume as a multiple of its 20-bar median
    rvol_window: int = RVOL_WINDOW
    require_breakout: bool = False  # close is the highest close of the lookback
    breakout_lookback: int = BREAKOUT_LOOKBACK
    require_uptrend: bool = False  # close above the 200 EMA
    min_close_strength: "float | None" = None  # (close-low)/(high-low), 1.0 = closed on the high
    max_base_rvol: "float | None" = None  # the bars before the spike traded below normal
    base_window: int = BASE_WINDOW
    require_obv_above_ema: bool = False
    obv_ema_span: int = 20


DEFAULT_CONFIG = VolumeBreakoutConfig()

VARIANTS = {
    # The core effect on its own, at three strengths. If the premium is here at all it should
    # show up in these three and get stronger as the threshold rises.
    "spike-1.5x": VolumeBreakoutConfig(min_rvol=1.5),
    "spike-2x": DEFAULT_CONFIG,
    "spike-3x": VolumeBreakoutConfig(min_rvol=3.0),
    # One confluence condition at a time, on the 2x spike.
    "spike+breakout": VolumeBreakoutConfig(require_breakout=True),
    "spike+uptrend": VolumeBreakoutConfig(require_uptrend=True),
    "spike+strong-close": VolumeBreakoutConfig(min_close_strength=0.6),
    "spike+quiet-base": VolumeBreakoutConfig(max_base_rvol=0.9),
    "spike+obv": VolumeBreakoutConfig(require_obv_above_ema=True),
    # The whole thesis at once, and the same thing without the trend filter, so the filter's
    # contribution can be read off the pair rather than assumed.
    "full": VolumeBreakoutConfig(require_breakout=True, require_uptrend=True,
                                 min_close_strength=0.6, max_base_rvol=0.9),
    "full-no-trend": VolumeBreakoutConfig(require_breakout=True, min_close_strength=0.6,
                                          max_base_rvol=0.9),
}


def close_strength(high: pd.Series, low: pd.Series, close: pd.Series, i: int) -> float:
    """Where bar i closed within its own range: 1.0 on the high, 0.0 on the low.

    A doji-flat bar (high == low) has no range to speak of and returns 0.5 rather than
    dividing by zero -- neither strong nor weak.
    """
    h, l, c = float(high.iloc[i]), float(low.iloc[i]), float(close.iloc[i])
    span = h - l
    if span <= 0:
        return 0.5
    return (c - l) / span


def is_breakout(close: pd.Series, i: int, lookback: int) -> bool:
    """True if bar i's close is the highest of the `lookback` bars ending at it."""
    window = close.iloc[max(i - lookback + 1, 0):i + 1]
    return bool(window.notna().all() and float(close.iloc[i]) >= float(window.max()))


def base_rvol(rvol: pd.Series, i: int, window: int) -> float:
    """Mean relative volume over the bars *before* the spike. The spike bar is excluded: it
    is by construction loud, and including it would make every base look busy."""
    prior = rvol.iloc[max(i - window, 0):i].dropna()
    return float(prior.mean()) if not prior.empty else float("nan")


def rule_side(close: pd.Series, high: pd.Series, low: pd.Series, rvol: pd.Series, i: int,
              ema200: "pd.Series | None" = None, obv_dev: "pd.Series | None" = None,
              *, cfg: VolumeBreakoutConfig = DEFAULT_CONFIG) -> "tuple[str, str] | None":
    """Return ("BUY", conviction) for bar i, or None. Pure function of the series.

    A gate whose input is NaN rejects the bar, the same rule the other two strategies use:
    unmeasured is not the same as passing.
    """
    v = rvol.iloc[i]
    if pd.isna(v) or float(v) < cfg.min_rvol:
        return None
    if cfg.require_breakout and not is_breakout(close, i, cfg.breakout_lookback):
        return None
    if cfg.require_uptrend:
        if ema200 is None:
            raise ValueError("require_uptrend is set but no EMA200 series was supplied")
        e = ema200.iloc[i]
        if pd.isna(e) or float(close.iloc[i]) <= float(e):
            return None
    if cfg.min_close_strength is not None:
        if close_strength(high, low, close, i) < cfg.min_close_strength:
            return None
    if cfg.max_base_rvol is not None:
        b = base_rvol(rvol, i, cfg.base_window)
        if pd.isna(b) or b > cfg.max_base_rvol:
            return None
    if cfg.require_obv_above_ema:
        if obv_dev is None:
            raise ValueError("require_obv_above_ema is set but no OBV series was supplied")
        d = obv_dev.iloc[i]
        if pd.isna(d) or float(d) <= 0:
            return None
    return "BUY", STANDARD


class VolumeBreakout:
    id = "volume-breakout"
    name = "Volume Breakout"
    description = (
        "BUY when a stock trades far more than its usual volume. Candidate only: not "
        "published until it clears research/ACCEPTANCE.md."
    )
    min_bars = MIN_BARS
    chart = {"rsi_levels": [], "macd_deep": False, "emas": True}
    history = (
        Release("1.0.0", "2026-10-04",
                "First version, and not published: a candidate measured against the bar "
                "written for a new strategy."),
    )

    def __init__(self, config: VolumeBreakoutConfig = DEFAULT_CONFIG):
        self.config = config

    @property
    def params(self) -> dict:
        return {"min_bars": MIN_BARS} | asdict(self.config)

    def indicators(self, df: pd.DataFrame) -> dict:
        close = df["close"]
        out = {
            "close": close, "high": df["high"], "low": df["low"],
            "rvol": rel_volume(df["volume"], self.config.rvol_window),
            "ema200": None, "obv_dev": None,
        }
        if self.config.require_uptrend:
            out["ema200"] = ema(close, 200)
        if self.config.require_obv_above_ema:
            o = obv(close, df["volume"])
            out["obv_dev"] = o - ema(o, self.config.obv_ema_span)
        return out

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        ind = self.indicators(df)
        last = len(df) - 1
        for k in range(SIGNAL_WINDOW):
            i = last - k
            hit = rule_side(**ind, i=i, cfg=self.config)
            if hit:
                side, conviction = hit
                details = {
                    "rvol": ind["rvol"].iloc[i],
                    "close_strength": close_strength(ind["high"], ind["low"], ind["close"], i),
                    "base_rvol": base_rvol(ind["rvol"], i, self.config.base_window),
                }
                return make_signal(df, i, side, details, conviction)
        return None
